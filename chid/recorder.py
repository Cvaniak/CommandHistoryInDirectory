"""Command execution recording lifecycle hooks for shell integration."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import time
from typing import TYPE_CHECKING

from chid.db import get_connection, initialize_schema
from chid.models import CommandRecord
from chid.queries import insert_command, update_command_completion
from chid.utils import find_git_root, sanitize_command

if TYPE_CHECKING:
    from pathlib import Path


def is_blank(command: str) -> bool:
    """Return True if command is empty or whitespace-only."""
    return not command or not command.strip()


def is_chid_command(command: str, alias: str | None = None) -> bool:
    """Return True if the command is an invocation of chid or its alias."""
    parts = command.strip().split()
    if not parts:
        return False

    first_word = Path(parts[0]).name
    if first_word == "chid":
        return True
    if alias and first_word == alias:
        return True
    return False


def should_ignore(command: str, directory: str = "", alias: str | None = None) -> bool:
    """Determine whether the command should be ignored from history recording."""
    if is_blank(command):
        return True
    # Ignore commands starting with whitespace (standard shell convention for transient commands)
    if command.startswith(" ") or command.startswith("\t"):
        return True
    if is_chid_command(command, alias=alias):
        return True
    return False


def record_command_start(
    directory: str,
    command: str,
    session_id: str,
    alias: str | None = None,
    timestamp_ms: int | None = None,
    db_path: Path | str | None = None,
) -> int | None:
    """Record the start of a command execution in the database."""
    if should_ignore(command, directory=directory, alias=alias):
        return None

    sanitized = sanitize_command(command)
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)

    git_root_path = find_git_root(directory)
    git_root = str(git_root_path) if git_root_path else None

    try:
        conn = get_connection(db_path)
        try:
            initialize_schema(conn)
            record = CommandRecord(
                directory=str(Path(directory).resolve()),
                command=sanitized,
                timestamp=ts,
                session_id=session_id,
                git_root=git_root,
            )
            return insert_command(conn, record)
        finally:
            conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        # Fail-safe: database errors must never interrupt the shell
        return None


def record_command_finish(
    session_id: str,
    exit_code: int,
    end_timestamp_ms: int | None = None,
    db_path: Path | str | None = None,
) -> bool:
    """Record completion status and calculate duration for the last running command in session."""
    end_ts = end_timestamp_ms if end_timestamp_ms is not None else int(time.time() * 1000)

    try:
        conn = get_connection(db_path)
        try:
            # Locate the start timestamp of the latest unfinished command in this session
            row = conn.execute(
                """
                SELECT id, timestamp FROM command_history
                WHERE session_id = ? AND exit_code IS NULL
                ORDER BY id DESC LIMIT 1;
                """,
                (session_id,),
            ).fetchone()

            if not row:
                return False

            start_ts = row["timestamp"]
            duration_ms = max(0, end_ts - start_ts)
            return update_command_completion(
                conn,
                session_id=session_id,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )
        finally:
            conn.close()
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return False
