<div align="center">

# ModelForge

### Build AI systems, one concept at a time

ModelForge is a learning monorepo for understanding how modern AI systems are
designed, built, and connected. Concept guides explain the ideas; focused
projects demonstrate them in working code. Projects stay independent unless
a later exercise intentionally connects them.

</div>

---

## Project learning guides

Each tutorial is kept with the project it explains:

| Concept | Learning guide | Related project |
|---|---|---|
| MCP | [Beginner tutorial](projects/mcp-notes-assistant/docs/MCP-Tutorial.md) | [MCP notes assistant](projects/mcp-notes-assistant/README.md) |
| RAG | [Practical tutorial](projects/rag-notes-assistant/RAG-Tutorial.md) | [RAG project space](projects/rag-notes-assistant/README.md) |

## Projects

| Project | Status | Guide |
|---|---|---|
| MCP notes assistant | Runnable learning project | [Project overview and development](projects/mcp-notes-assistant/README.md) |
| RAG notes assistant | Reserved for the upcoming implementation | [Project space](projects/rag-notes-assistant/README.md) |

Each project keeps its implementation, tests, dependencies, and setup
documentation together. See its guide for project-specific setup and commands.

## Workspace development

The root `pyproject.toml` defines a `uv` workspace. Runnable Python projects
are added as workspace members when their implementations begin.

```bash
uv sync
uv workspace list
```

The MCP assistant is the first workspace member. Its tests and build
instructions are documented in the
[MCP project guide](projects/mcp-notes-assistant/README.md).

## Repository layout

```text
projects/
  mcp-notes-assistant/
    docs/         MCP tutorial and project documentation
  rag-notes-assistant/
    RAG-Tutorial.md
```

> **Learning repository:** projects are for understanding and experimenting
> with AI engineering concepts; they are not production-ready services.
