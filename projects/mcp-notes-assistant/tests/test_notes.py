import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.server.mcpserver.exceptions import ToolError

from modelforge import notes
from modelforge.main import mcp


class NotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "notes.db"
        self.environment = patch.dict(
            os.environ, {"NOTES_DB_PATH": str(self.database_path)}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_crud_search_and_weekly_summary(self) -> None:
        created = notes.add_note(" Release plan ", " Deploy the release on Friday. ")
        self.assertEqual(created["title"], "Release plan")
        self.assertEqual(created["content"], "Deploy the release on Friday.")
        self.assertEqual(created["created_at"], created["updated_at"])
        self.assertEqual(notes.get_note(created["id"]), created)
        self.assertEqual(notes.get_note_by_title("release PLAN"), created)
        self.assertEqual(notes.search_notes("deploy Friday"), [created])

        updated = notes.update_note(
            created["id"], "Launch plan", "Review the launch checklist."
        )
        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["created_at"], created["created_at"])
        self.assertGreater(updated["updated_at"], created["updated_at"])
        self.assertEqual(notes.list_notes(), [updated])

        summary = notes.weekly_learning_summary()
        self.assertEqual(summary["note_count"], 1)
        self.assertEqual(summary["notes"], [updated])

        self.assertEqual(notes.delete_note(created["id"]), {
            "deleted": True,
            "id": created["id"],
        })
        self.assertEqual(notes.list_notes(), [])

    def test_migrates_legacy_notes_table(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO notes (title, content, created_at) VALUES (?, ?, ?)",
                ("Old note", "Existing content", "2026-01-01T00:00:00+00:00"),
            )

        migrated = notes.get_note(1)
        self.assertEqual(migrated["updated_at"], migrated["created_at"])

    def test_search_treats_like_wildcards_as_literal_characters(self) -> None:
        note_with_percent = notes.add_note("Progress", "100% complete")
        notes.add_note("Everything else", "No percentage here")

        self.assertEqual(notes.search_notes("%"), [note_with_percent])

    def test_default_database_path_uses_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as working_directory:
            with (
                patch.dict(os.environ, {"NOTES_DB_PATH": ""}),
                patch("pathlib.Path.cwd", return_value=Path(working_directory)),
            ):
                self.assertEqual(
                    notes._database_path(),
                    Path(working_directory) / "data" / "notes.db",
                )

    def test_database_connection_is_closed_after_use(self) -> None:
        with notes._connect() as connection:
            pass

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_invalid_note_operations_are_reported_as_tool_errors(self) -> None:
        with self.assertRaisesRegex(ToolError, "title must not be empty"):
            asyncio.run(
                mcp.call_tool(
                    "add_note", {"title": " ", "content": "Some content"}
                )
            )
        with self.assertRaisesRegex(ToolError, "note 123 was not found"):
            asyncio.run(
                mcp.call_tool(
                    "update_note",
                    {"note_id": 123, "title": "Title", "content": "Content"},
                )
            )

    def test_learning_notes_resource_lists_saved_notes_as_json(self) -> None:
        note = notes.add_note("MCP resources", "Resources provide read-only context.")

        async def read_resource() -> list[dict]:
            resources = await mcp.list_resources()
            resource = next(
                item
                for item in resources
                if str(item.uri) == "notes://modelforge/notes"
            )
            self.assertEqual(resource.mime_type, "application/json")
            return await mcp.read_resource(resource.uri)

        contents = asyncio.run(read_resource())
        self.assertEqual(json.loads(contents[0].content), [note])

    def test_ollama_chat_is_not_exposed_as_an_mcp_tool(self) -> None:
        async def list_tool_names() -> set[str]:
            tools = await mcp.list_tools()
            return {tool.name for tool in tools}

        tool_names = asyncio.run(list_tool_names())
        self.assertNotIn("ask_ollama", tool_names)
        self.assertIn("generate_weekly_learning_summary", tool_names)

    def test_learning_topic_prompt_is_discoverable_and_renders_topic(self) -> None:
        async def get_prompt():
            prompts = await mcp.list_prompts()
            prompt = next(
                item for item in prompts if item.name == "review_learning_topic"
            )
            self.assertEqual([argument.name for argument in prompt.arguments], ["topic"])
            return await mcp.get_prompt(
                "review_learning_topic", {"topic": "MCP resources"}
            )

        result = asyncio.run(get_prompt())
        content = result.messages[0].content.text
        self.assertIn("MCP resources", content)
        self.assertIn("notes://modelforge/notes", content)


if __name__ == "__main__":
    unittest.main()
