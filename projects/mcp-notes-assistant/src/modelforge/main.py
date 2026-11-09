import json
import math
import os
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from modelforge.notes import (
    add_note as add_note_record,
    delete_note as delete_note_record,
    get_note as get_note_record,
    get_note_by_title as get_note_by_title_record,
    list_notes as list_note_records,
    search_notes as search_note_records,
    update_note as update_note_record,
    weekly_learning_summary as build_weekly_learning_summary,
)

# Create an MCP server instance
mcp = MCPServer("ModelForge")
Result = TypeVar("Result")


def _run_note_operation(operation: Callable[..., Result], *args: Any) -> Result:
    try:
        return operation(*args)
    except ValueError as error:
        raise ToolError(str(error)) from error


def _ollama_url(path: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    return f"{host}{path}"


def _ollama_timeout() -> float:
    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT", "120"))
    except ValueError as error:
        raise RuntimeError("OLLAMA_TIMEOUT must be a positive number") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError("OLLAMA_TIMEOUT must be a positive number")
    return timeout


# Register a tool
@mcp.tool()
def add_note(title: str, content: str) -> dict:
    """Save a learning note with a title and content."""
    return _run_note_operation(add_note_record, title, content)


@mcp.tool()
def list_notes() -> list[dict]:
    """Return all saved learning notes, newest first."""
    return list_note_records()


@mcp.tool()
def search_notes(query: str) -> list[dict]:
    """Find notes containing every keyword in the query."""
    return _run_note_operation(search_note_records, query)


@mcp.tool()
def read_note(note_id: int) -> dict:
    """Read one learning note by its numeric ID."""
    return _run_note_operation(get_note_record, note_id)


@mcp.tool()
def read_note_by_title(title: str) -> dict:
    """Read one note by its exact title, ignoring letter case."""
    return _run_note_operation(get_note_by_title_record, title)


@mcp.tool()
def update_note(note_id: int, title: str, content: str) -> dict:
    """Update a learning note by its numeric ID."""
    return _run_note_operation(update_note_record, note_id, title, content)


@mcp.tool()
def delete_note(note_id: int) -> dict:
    """Delete one learning note by its numeric ID."""
    return _run_note_operation(delete_note_record, note_id)


@mcp.tool()
def weekly_learning_summary() -> dict:
    """Summarize learning notes created during the last seven days."""
    return _run_note_operation(build_weekly_learning_summary)


@mcp.resource(
    "notes://modelforge/notes",
    name="learning_notes",
    description="All saved learning notes, newest first.",
    mime_type="application/json",
)
def learning_notes_resource() -> str:
    """Expose saved learning notes as read-only JSON context."""
    return json.dumps(list_note_records(), ensure_ascii=False, indent=2)


@mcp.prompt(
    name="review_learning_topic",
    title="Review a learning topic",
    description="Create a focused review using saved notes when available.",
)
def review_learning_topic(topic: str) -> list[dict[str, str]]:
    """Prepare a learning-topic review prompt for the selected topic."""
    return [
        {
            "role": "user",
            "content": (
                f"Help me review {topic!r}. Use the ModelForge notes resource "
                "`notes://modelforge/notes` as the source for anything I have "
                "already learned. Explain key ideas, identify gaps or "
                "questions to revisit, and suggest one practical exercise. "
                "Clearly distinguish information from my notes from any "
                "additional general explanation."
            ),
        }
    ]


def _generate_with_ollama(prompt: str, model: str | None = None) -> str:
    payload = json.dumps(
        {
            "model": model or os.getenv("OLLAMA_MODEL", "llama3.2"),
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    request = Request(
        _ollama_url("/api/generate"),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=_ollama_timeout(),
        ) as response:
            result = json.load(response)
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama returned HTTP {error.code}: {details}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            "Could not connect to Ollama. Ensure it is running at "
            f"{_ollama_url('')}."
        ) from error
    except TimeoutError as error:
        raise RuntimeError("The request to Ollama timed out") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Ollama returned invalid JSON") from error
    except UnicodeDecodeError as error:
        raise RuntimeError("Ollama returned invalid text encoding") from error

    if not isinstance(result, dict):
        raise RuntimeError("Ollama response must be a JSON object")
    generated = result.get("response")
    if not isinstance(generated, str):
        raise RuntimeError("Ollama response did not contain a text response")
    return generated


@mcp.tool()
def generate_weekly_learning_summary(model: str | None = None) -> str:
    """Use Ollama to write a learning summary from notes created this week."""
    data = build_weekly_learning_summary()
    if not data["notes"]:
        return data["summary"]

    notes = "\n\n".join(
        f"Title: {note['title']}\nContent: {note['content']}"
        for note in data["notes"]
    )
    prompt = (
        "Create a concise weekly learning summary from these personal notes. "
        "Use headings for Topics learned, Key insights, and Suggested next "
        "steps. Do not invent information that is not present in the notes.\n\n"
        f"{notes}"
    )
    try:
        return _generate_with_ollama(prompt, model)
    except RuntimeError as error:
        raise ToolError(str(error)) from error


if __name__ == "__main__":
    mcp.run()