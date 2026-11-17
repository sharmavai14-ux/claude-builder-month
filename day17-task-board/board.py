"""Day 17: the shared task board. Plain Python and SQLite, no AI here.

Every agent reads and writes this one board. The board is the team's
shared memory: it is saved in board.db, so it survives if the program stops.
"""

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent / "board.db"
MAX_CHAIN = 5  # a piece of work may be handed on at most 5 times


def connect():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row  # rows behave like dictionaries
    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        kind TEXT,                 -- 'write' or 'check'
        title TEXT,
        details TEXT,
        status TEXT DEFAULT 'todo',  -- 'todo', 'doing' or 'done'
        owner TEXT,
        result TEXT,
        parent_id INTEGER          -- the task this one was handed on from
    )""")
    return db


def add_task(kind, title, details, parent_id=None):
    with connect() as db:
        cursor = db.execute(
            "INSERT INTO tasks (kind, title, details, parent_id) VALUES (?, ?, ?, ?)",
            (kind, title, details, parent_id))
        return cursor.lastrowid


def claim_task(kind, owner):
    """Take the oldest 'todo' task of this kind, in one step, so two agents
    can never take the same task. Returns the task, or None."""
    with connect() as db:
        row = db.execute(
            """UPDATE tasks SET status = 'doing', owner = ?
               WHERE id = (SELECT id FROM tasks WHERE status = 'todo' AND kind = ?
                           ORDER BY id LIMIT 1)
               RETURNING *""", (owner, kind)).fetchone()
        return dict(row) if row else None


def get_task(task_id):
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def finish_task(task_id, result):
    with connect() as db:
        db.execute("UPDATE tasks SET status = 'done', result = ? WHERE id = ?",
                   (result, task_id))


def chain_length(task_id):
    """How many hand-offs led to this task."""
    length = 0
    task = get_task(task_id)
    while task and task["parent_id"]:
        length += 1
        task = get_task(task["parent_id"])
    return length


def count(kind=None, status="todo"):
    with connect() as db:
        if kind:
            sql, args = "SELECT COUNT(*) FROM tasks WHERE status = ? AND kind = ?", (status, kind)
        else:
            sql, args = "SELECT COUNT(*) FROM tasks WHERE status = ?", (status,)
        return db.execute(sql, args).fetchone()[0]


def reset_stuck_tasks():
    """If the program stopped halfway, put 'doing' tasks back to 'todo'."""
    with connect() as db:
        return db.execute("UPDATE tasks SET status = 'todo', owner = NULL "
                          "WHERE status = 'doing'").rowcount


def show():
    with connect() as db:
        rows = db.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    print(f"\n{'id':>3}  {'kind':6} {'status':6} {'from':>4}  title")
    for row in rows:
        came_from = row["parent_id"] or ""
        print(f"{row['id']:>3}  {row['kind']:6} {row['status']:6} {came_from:>4}  {row['title']}")