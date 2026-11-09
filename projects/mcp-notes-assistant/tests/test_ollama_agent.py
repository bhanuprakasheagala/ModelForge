import os
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from modelforge import ollama_agent


class FakeSession:
    def __init__(self):
        self.tool_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def initialize(self):
        return None

    async def list_tools(self):
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="read_note",
                    description="Read a note",
                    input_schema={"type": "object"},
                ),
                SimpleNamespace(
                    name="delete_note",
                    description="Delete a note",
                    input_schema={"type": "object"},
                ),
            ]
        )

    async def call_tool(self, name, arguments):
        self.tool_calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(text="Tool completed.")])


class OllamaAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fake_session = FakeSession()

    def _patch_mcp_client(self):
        @asynccontextmanager
        async def fake_stdio_client(_server):
            yield None, None

        return (
            patch.object(ollama_agent, "stdio_client", fake_stdio_client),
            patch.object(
                ollama_agent, "ClientSession", return_value=self.fake_session
            ),
        )

    def test_timeout_setting_must_be_positive(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_TIMEOUT": "0"}):
            with self.assertRaisesRegex(RuntimeError, "must be a positive number"):
                ollama_agent._ollama_timeout()

    async def test_failed_request_does_not_mutate_conversation_history(self) -> None:
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Read note 1."},
        ]
        original_messages = [dict(message) for message in messages]

        patches = self._patch_mcp_client()
        with (
            patches[0],
            patches[1],
            patch.object(
                ollama_agent,
                "_ollama_chat",
                side_effect=RuntimeError("Ollama is unavailable"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Ollama is unavailable"):
                await ollama_agent._chat_with_mcp_tools(messages)

        self.assertEqual(messages, original_messages)

    async def test_tool_inventory_is_added_to_conversation_history(self) -> None:
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Show me the available tools."},
        ]

        patches = self._patch_mcp_client()
        with patches[0], patches[1]:
            answer = await ollama_agent._chat_with_mcp_tools(messages)

        self.assertIn("read_note", answer)
        self.assertEqual(messages[-1], {"role": "assistant", "content": answer})

    async def _run_delete_request(self, confirmation):
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Delete note 7."},
        ]
        tool_response = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "delete_note",
                            "arguments": {"note_id": 7},
                        }
                    }
                ],
            }
        }
        final_response = {
            "message": {
                "role": "assistant",
                "content": "I did not delete the note.",
            }
        }

        patches = self._patch_mcp_client()
        input_patch = (
            patch("builtins.input", side_effect=confirmation)
            if isinstance(confirmation, BaseException)
            else patch("builtins.input", return_value=confirmation)
        )
        with (
            patches[0],
            patches[1],
            patch.object(
                ollama_agent,
                "_ollama_chat",
                side_effect=[tool_response, final_response],
            ),
            input_patch as input_prompt,
        ):
            answer = await ollama_agent._chat_with_mcp_tools(messages)

        input_prompt.assert_called_once()
        self.assertIn("note 7", input_prompt.call_args.args[0])
        return answer, self.fake_session.tool_calls, messages

    async def test_delete_tool_requires_explicit_confirmation(self) -> None:
        answer, tool_calls, _messages = await self._run_delete_request("yes")

        self.assertEqual(tool_calls, [("delete_note", {"note_id": 7})])
        self.assertEqual(answer, "I did not delete the note.")

    async def test_declined_delete_is_not_sent_to_mcp_server(self) -> None:
        answer, tool_calls, messages = await self._run_delete_request("")

        self.assertEqual(tool_calls, [])
        self.assertEqual(answer, "I did not delete the note.")
        self.assertIn("no note was deleted", messages[-2]["content"])

    async def test_delete_is_denied_when_confirmation_input_is_unavailable(self) -> None:
        _answer, tool_calls, messages = await self._run_delete_request(EOFError())

        self.assertEqual(tool_calls, [])
        self.assertIn("no note was deleted", messages[-2]["content"])

    async def test_read_tool_does_not_require_confirmation(self) -> None:
        messages = [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Read note 7."},
        ]
        tool_response = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_note",
                            "arguments": {"note_id": 7},
                        }
                    }
                ],
            }
        }
        final_response = {
            "message": {"role": "assistant", "content": "Here is note 7."}
        }
        patches = self._patch_mcp_client()
        with (
            patches[0],
            patches[1],
            patch.object(
                ollama_agent,
                "_ollama_chat",
                side_effect=[tool_response, final_response],
            ),
            patch("builtins.input", side_effect=AssertionError("unexpected prompt")),
        ):
            answer = await ollama_agent._chat_with_mcp_tools(messages)

        self.assertEqual(answer, "Here is note 7.")
        self.assertEqual(self.fake_session.tool_calls, [("read_note", {"note_id": 7})])


if __name__ == "__main__":
    unittest.main()
