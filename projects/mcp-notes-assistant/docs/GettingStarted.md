# Getting started

ModelForge requires Python 3.12+, [`uv`](https://docs.astral.sh/uv/), and
[Ollama](https://ollama.com/) for the natural-language client. Node.js/npm is
also needed if you want to use MCP Inspector.

## Install

Run commands from the repository root:

```bash
uv sync
ollama pull llama3.2
```

Ollama may already be running as a desktop service. If it is not, start it:

```bash
ollama serve
```

Check that it is available:

```bash
curl http://127.0.0.1:11434/api/tags
```

## Try the MCP tools

Start MCP Inspector:

```bash
uv run --package modelforge mcp dev projects/mcp-notes-assistant/src/modelforge/main.py
```

Inspector lets you discover and call tools directly, without relying on an
LLM to choose one. Try adding a note, reading it by ID, searching, updating,
and deleting a test note. When deleting in Inspector, make sure you intend to
remove that note before invoking the tool. Open the **Resources** section to
list and read `notes://modelforge/notes`; compare this read-only JSON snapshot
with the `list_notes` tool. Open **Prompts**, select **Review a learning
topic**, enter a topic such as `MCP resources`, and inspect the prepared
message.

## Chat with Ollama

Start the interactive client:

```bash
uv run --package modelforge python -m modelforge.ollama_agent
```

Example requests:

```text
Save a note titled Grocery list with milk, rice, and vegetables.
Show my notes about groceries.
Read the note titled Grocery list.
Generate my weekly learning summary.
```

Enter `exit` or `quit` to end the chat. For one request without entering
interactive mode:

```bash
uv run --package modelforge python -m modelforge.ollama_agent "Search my notes for deployment"
```

Before the Ollama client deletes a note, it displays the requested note ID and
requires you to type `yes`. The default is no; if confirmation input is
unavailable, the client cancels the deletion.

The installed server command is also available:

```bash
uv run --package modelforge modelforge
```

## Configuration and data

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama API address |
| `OLLAMA_MODEL` | `llama3.2` | Model used for generation and chat |
| `OLLAMA_TIMEOUT` | `120` | Request timeout in seconds; must be positive |
| `NOTES_DB_PATH` | `data/notes.db` from the current directory | SQLite file location |

Example:

```bash
OLLAMA_MODEL=llama3.2 \
OLLAMA_TIMEOUT=180 \
NOTES_DB_PATH="$HOME/learning-notes.db" \
uv run --package modelforge python -m modelforge.ollama_agent
```

The default database path is relative to the process's current working
directory. Run from the repository root to use the project's `data/notes.db`.
Processes that should share notes must use the same path. If an earlier run
created `src/data/notes.db`, select it explicitly with
`NOTES_DB_PATH=src/data/notes.db`; the application will not move databases.

Generated summaries send note titles and contents to the Ollama server at
`OLLAMA_HOST`. The default is local. If you configure a remote host, note
contents are sent to that host.

## Troubleshooting

### Ollama connection refused

Check that the server is running and that `OLLAMA_HOST` points to the right
address:

```bash
echo "$OLLAMA_HOST"
ollama list
curl http://127.0.0.1:11434/api/tags
```

### Inspector and chat show different notes

Compare `NOTES_DB_PATH` in each process. If it is unset, both processes use a
database relative to their own current working directories. Run them from the
project root or set the same explicit path for both.

### Ollama chooses the wrong tool

Use precise language, such as “Read the note with ID 2” or “Read the note with
the exact title Project meeting.” Test a tool directly in Inspector to separate
model tool-selection issues from server or database issues.

# Learning path

Follow one request through the project rather than trying to understand every
file at once.

For a conceptual guide to MCP roles, capabilities, protocol flow, transports,
and security, see the
[MCP beginner tutorial](MCP-Tutorial.md).
For a practical introduction to retrieval-augmented generation, see the
[RAG tutorial](../../rag-notes-assistant/RAG-Tutorial.md).

## Trace a request

After following the setup steps above, ask:

```text
Read the note titled Project meeting
```

Trace the request:

1. Ollama identifies the intent and selects `read_note_by_title`.
2. `ollama_agent.py` receives the tool call.
3. The MCP client sends it to the server in `main.py`.
4. The tool wrapper calls the matching function in `notes.py`.
5. SQLite retrieves the note.
6. The result returns through MCP and Ollama responds in natural language.

The model chooses what may help; the application validates and performs the
operation.

## Practice with the tools

In MCP Inspector, create a test note, then:

1. Read it by ID and by exact title.
2. Search with one keyword, then multiple keywords.
3. Update it and confirm its `created_at` is unchanged.
4. Try an unknown ID and an empty title to see expected error handling.
5. Retrieve the deterministic weekly summary.
6. Delete the test note after confirming it is safe to remove.

## Exercises

1. **Add a tool:** implement `count_notes()` in `notes.py` and expose it in
   `main.py`.
2. **Extend the schema:** add a category column and update schema, insert,
   migration, and select behavior.
3. **Compare retrieval and generation:** inspect
   `weekly_learning_summary()` and compare it with
   `generate_weekly_learning_summary()`.
4. **Try semantic retrieval:** generate note embeddings and compare
   similarity-based results with keyword search.
5. **Inspect deletion safety:** trace the confirmation guard in
   `ollama_agent.py` and the approval, refusal, and unavailable-input tests.
   Compare this conversational client behavior with direct calls in Inspector.

Run the automated checks from the project root:

```bash
uv run --package modelforge python -m unittest discover -s projects/mcp-notes-assistant/tests
uv build --package modelforge
```
