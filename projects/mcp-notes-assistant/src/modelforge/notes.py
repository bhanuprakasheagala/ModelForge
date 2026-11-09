from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


def _database_path() -> Path:
    configured = os.getenv("NOTES_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "data" / "notes.db"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
                """
            )
            columns = connection.execute("PRAGMA table_info(notes)").fetchall()
            if not any(column[1] == "updated_at" for column in columns):
                connection.execute("ALTER TABLE notes ADD COLUMN updated_at TEXT")
                connection.execute(
                    "UPDATE notes SET updated_at = created_at WHERE updated_at IS NULL"
                )
            yield connection
    finally:
        connection.close()


def _note(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def add_note(title: str, content: str) -> dict[str, Any]:
    title = title.strip()
    content = content.strip()
    if not title:
        raise ValueError("title must not be empty")
    if not content:
        raise ValueError("content must not be empty")

    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO notes (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, content, timestamp, timestamp),
        )
        row = connection.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _note(row)


def list_notes() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes ORDER BY created_at DESC"
        ).fetchall()
    return [_note(row) for row in rows]


def search_notes(query: str) -> list[dict[str, Any]]:
    keywords = [keyword for keyword in query.strip().split() if keyword]
    if not keywords:
        raise ValueError("query must not be empty")

    conditions = " AND ".join(
        "(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"
        for _ in keywords
    )
    escaped_keywords = [
        keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        for keyword in keywords
    ]
    parameters = [
        f"%{keyword}%"
        for keyword in escaped_keywords
        for _ in range(2)
    ]
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, title, content, created_at, updated_at FROM notes
            WHERE {conditions}
            ORDER BY created_at DESC
            """,
            parameters,
        ).fetchall()
    return [_note(row) for row in rows]


def get_note(note_id: int) -> dict[str, Any]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"note {note_id} was not found")
    return _note(row)


def get_note_by_title(title: str) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("title must not be empty")

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, title, content, created_at, updated_at FROM notes
            WHERE title = ? COLLATE NOCASE
            ORDER BY created_at DESC
            """,
            (title,),
        ).fetchall()
    if not rows:
        raise ValueError(f"no note titled {title!r} was found")
    if len(rows) > 1:
        raise ValueError(
            f"more than one note is titled {title!r}; use its numeric ID"
        )
    return _note(rows[0])


def update_note(note_id: int, title: str, content: str) -> dict[str, Any]:
    title = title.strip()
    content = content.strip()
    if not title:
        raise ValueError("title must not be empty")
    if not content:
        raise ValueError("content must not be empty")

    updated_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title, content, updated_at, note_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"note {note_id} was not found")
        row = connection.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    return _note(row)


def delete_note(note_id: int) -> dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    if cursor.rowcount == 0:
        raise ValueError(f"note {note_id} was not found")
    return {"deleted": True, "id": note_id}


def weekly_learning_summary() -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, title, content, created_at, updated_at FROM notes
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (since,),
        ).fetchall()
    notes = [_note(row) for row in rows]
    return {
        "period_days": 7,
        "note_count": len(notes),
        "notes": notes,
        "summary": (
            "No notes were added in the last 7 days."
            if not notes
            else "Learning notes from the last 7 days: "
            + "; ".join(note["title"] for note in notes)
        ),
    }
