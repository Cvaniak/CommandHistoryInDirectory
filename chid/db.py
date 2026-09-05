"""SQLite database connection and schema management for CHID."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from chid.config import get_database_path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS command_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    directory TEXT NOT NULL,
    command TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    exit_code INTEGER DEFAULT NULL,
    duration_ms INTEGER DEFAULT NULL,
    session_id TEXT NOT NULL,
    git_root TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_chid_dir_time ON command_history(directory, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chid_dir_cmd ON command_history(directory, command);
CREATE INDEX IF NOT EXISTS idx_chid_git_time ON command_history(git_root, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chid_git_cmd ON command_history(git_root, command);
CREATE INDEX IF NOT EXISTS idx_chid_session ON command_history(session_id, id DESC);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create and return a configured SQLite connection.

    Sets autocommit mode (isolation_level=None) so BEGIN IMMEDIATE transactions
    can be managed explicitly and safely.
    """
    if db_path is None:
        db_path = get_database_path()

    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        path_str = str(db_path)
    else:
        path_str = str(db_path)
        if path_str != ":memory:":
            Path(path_str).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path_str, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 500;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema, indices, and WAL journal mode."""
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript(SCHEMA_SQL)


@contextmanager
def immediate_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Execute a block within an IMMEDIATE write transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
