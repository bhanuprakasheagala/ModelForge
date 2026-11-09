# RAG notes assistant [TO DO]

This folder is the reserved project space for implementing the RAG concepts
in ModelForge. It is intentionally separate from the MCP notes assistant so
retrieval and generation can be built and understood on their own.

The implementation has **not started**. Follow the [RAG tutorial](../../docs/concepts/rag/RAG-Tutorial.md)
and its staged plan before adding code. The first version should preserve a
small, inspectable scope: define test questions, establish a retrieval
baseline, choose a local embedding approach, and add semantic retrieval with
tests before adding generation.

When this becomes a runnable Python project, give it its own `pyproject.toml`,
source package, tests, and data/configuration rules. Add it as a workspace
member in the repository-root `pyproject.toml` at that time.

An MCP-to-RAG integration can be created as a separate later exercise. The
RAG implementation should not depend on the MCP server just because both
projects use notes.
