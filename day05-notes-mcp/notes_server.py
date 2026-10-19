import sqlite3
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer

# The database file lives in the same folder as this script.
DB_PATH = Path(__file__).parent / "notes.db"

mcp = MCPServer("notes")


def open_db():
    """Open the database and make sure the notes table exists."""
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS notes (
               id      INTEGER PRIMARY KEY AUTOINCREMENT,
               title   TEXT NOT NULL,
               body    TEXT NOT NULL,
               created TEXT NOT NULL
           )"""
    )
    return db


@mcp.tool()
def add_note(title: str, body: str) -> str:
    """Save a new note.

    Args:
        title: A short title for the note, like "Day 5 ideas".
        body: The full text of the note.
    """
    created = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open_db() as db:
        cursor = db.execute(
            "INSERT INTO notes (title, body, created) VALUES (?, ?, ?)",
            (title, body, created),
        )
        new_id = cursor.lastrowid
    return f"Saved note #{new_id}: {title}"


@mcp.tool()
def list_notes(limit: int = 10) -> str:
    """List the most recent notes, newest first.

    Args:
        limit: How many notes to show (default 10).
    """
    with open_db() as db:
        rows = db.execute(
            "SELECT id, title, created FROM notes ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    if not rows:
        return "There are no notes yet."
    return "\n".join(f"#{id} [{created}] {title}" for id, title, created in rows)


@mcp.tool()
def search_notes(query: str) -> str:
    """Find notes whose title or body contains the given words.

    Args:
        query: The word or phrase to look for (not case sensitive).
    """
    pattern = f"%{query}%"
    with open_db() as db:
        rows = db.execute(
            "SELECT id, title, body, created FROM notes "
            "WHERE title LIKE ? OR body LIKE ? ORDER BY id DESC",
            (pattern, pattern),
        ).fetchall()
    if not rows:
        return f"No notes mention '{query}'."
    return "\n\n".join(
        f"#{id} [{created}] {title}\n{body}" for id, title, body, created in rows
    )


if __name__ == "__main__":
    mcp.run()  # "stdio": talk to Claude Code through standard input/output