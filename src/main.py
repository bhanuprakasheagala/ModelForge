import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server import MCPServer

from notes import (
    add_note as add_note_record,
    delete_note as delete_note_record,
    get_note as get_note_record,
    get_note_by_title as get_note_by_title_record,
    list_notes as list_note_records,
    search_notes as search_note_records,
    weekly_learning_summary as build_weekly_learning_summary,
)

# Create an MCP server instance
mcp = MCPServer("ModelForge")


def _ollama_url(path: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    return f"{host}{path}"


# Register a tool
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Adds two numbers and returns the result."""
    return a + b

@mcp.tool()
def subtract_numbers(a: int, b: int) -> int:
    """Subtracts the second number from the first and returns the result."""
    return a - b

@mcp.tool()
def greet_user(name: str) -> str:
    """Greets the user with their name."""
    return f"Hello, {name}!, Welcome to MCP."


@mcp.tool()
def add_note(title: str, content: str) -> dict:
    """Save a learning note with a title and content."""
    return add_note_record(title, content)


@mcp.tool()
def list_notes() -> list[dict]:
    """Return all saved learning notes, newest first."""
    return list_note_records()


@mcp.tool()
def search_notes(query: str) -> list[dict]:
    """Find notes containing every keyword in the query."""
    return search_note_records(query)


@mcp.tool()
def read_note(note_id: int) -> dict:
    """Read one learning note by its numeric ID."""
    return get_note_record(note_id)


@mcp.tool()
def read_note_by_title(title: str) -> dict:
    """Read one note by its exact title, ignoring letter case."""
    return get_note_by_title_record(title)


@mcp.tool()
def delete_note(note_id: int) -> dict:
    """Delete one learning note by its numeric ID."""
    return delete_note_record(note_id)


@mcp.tool()
def weekly_learning_summary() -> dict:
    """Summarize learning notes created during the last seven days."""
    return build_weekly_learning_summary()


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
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
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
    return _generate_with_ollama(prompt, model)


@mcp.tool()
def ask_ollama(prompt: str, model: str | None = None) -> str:
    """Generate a response from a local Ollama model."""
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    return _generate_with_ollama(prompt, model)


if __name__ == "__main__":
    mcp.run()