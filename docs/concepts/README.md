# Concepts and projects

ModelForge is a learning monorepo. **Concept guides explain ideas**;
**project folders contain runnable implementations**. Each concept can be
learned and tested independently. An integration between concepts should be a
deliberate project, not an accidental dependency.

## Current learning areas

| Concept | Guide | Runnable project |
|---|---|---|
| MCP | [MCP beginner tutorial](./mcp/MCP-Tutorial.md) | [MCP notes assistant](../../projects/mcp-notes-assistant/README.md) |
| RAG | [RAG tutorial](./rag/RAG-Tutorial.md) | [RAG project space](../../projects/rag-notes-assistant/README.md) |

## Adding a future concept

1. Add its conceptual tutorial under `docs/concepts/<concept>/`.
2. Give its runnable implementation a focused folder under `projects/`.
3. Keep implementation, dependencies, tests, and project setup with that
   project.
4. Add a workspace member to the root `pyproject.toml` when it becomes a
   runnable Python project.
5. Link it here and in the root README.
6. Create a separate integration project only when the learning goal is to
   connect concepts.

Do not create a shared package merely to avoid small duplication. Extract
shared code when multiple projects demonstrate a real common responsibility
and its API can be kept stable.
