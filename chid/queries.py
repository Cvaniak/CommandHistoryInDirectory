"""Query functions for recording and retrieving command history."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from chid.db import immediate_transaction
from chid.models import CommandRecord, FrequencyStat

if TYPE_CHECKING:
    from typing import Sequence


def insert_command(conn: sqlite3.Connection, record: CommandRecord) -> int:
    """Insert a new command record within an immediate transaction and return its ID."""
    query = """
    INSERT INTO command_history (directory, command, timestamp, exit_code, duration_ms, session_id, git_root)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """
    with immediate_transaction(conn):
        cursor = conn.execute(
            query,
            (
                record.directory,
                record.command,
                record.timestamp,
                record.exit_code,
                record.duration_ms,
                record.session_id,
                record.git_root,
            ),
        )
        return int(cursor.lastrowid)


def update_command_completion(
    conn: sqlite3.Connection,
    session_id: str,
    exit_code: int,
    duration_ms: int,
) -> bool:
    """Update exit code and duration for the most recent unfinished command in the given session."""
    query = """
    UPDATE command_history
    SET exit_code = ?, duration_ms = ?
    WHERE id = (
        SELECT id FROM command_history
        WHERE session_id = ? AND exit_code IS NULL
        ORDER BY id DESC LIMIT 1
    );
    """
    with immediate_transaction(conn):
        cursor = conn.execute(query, (exit_code, duration_ms, session_id))
        return cursor.rowcount > 0


def _build_scope_clause(
    directory: str,
    git_root: str | None,
    params: list[object],
) -> str:
    """Helper to generate directory or repository scope WHERE clause."""
    if git_root:
        params.append(git_root)
        return "git_root = ?"
    params.append(directory)
    return "directory = ?"


def query_frequency(
    conn: sqlite3.Connection,
    directory: str,
    limit: int = 20,
    search: str = "",
    git_root: str | None = None,
) -> list[FrequencyStat]:
    """Return command frequency metrics, percentage of total executions, and last run timestamp."""
    count_params: list[object] = []
    scope_cond = _build_scope_clause(directory, git_root, count_params)
    search_cond = ""
    if search:
        search_cond = " AND command LIKE ?"
        count_params.append(f"%{search}%")

    total_query = f"SELECT COUNT(*) AS total FROM command_history WHERE {scope_cond}{search_cond};"
    total_row = conn.execute(total_query, count_params).fetchone()
    total_count = total_row["total"] if total_row else 0

    if total_count == 0:
        return []

    stats_params: list[object] = []
    scope_cond_stats = _build_scope_clause(directory, git_root, stats_params)
    if search:
        stats_params.append(f"%{search}%")
    stats_params.append(limit)

    stats_query = f"""
    SELECT
        command,
        COUNT(*) AS cmd_count,
        MAX(timestamp) AS last_run
    FROM command_history
    WHERE {scope_cond_stats}{search_cond}
    GROUP BY command
    ORDER BY cmd_count DESC, last_run DESC
    LIMIT ?;
    """

    results: list[FrequencyStat] = []
    for row in conn.execute(stats_query, stats_params):
        cmd_count = row["cmd_count"]
        percentage = (cmd_count / total_count) * 100.0
        results.append(
            FrequencyStat(
                command=row["command"],
                count=cmd_count,
                percentage=round(percentage, 1),
                last_run_timestamp=row["last_run"],
            )
        )
    return results


def query_recent(
    conn: sqlite3.Connection,
    directory: str,
    limit: int = 20,
    search: str = "",
    git_root: str | None = None,
    success_only: bool = False,
    failed_only: bool = False,
) -> list[CommandRecord]:
    """Return recent command executions sorted by timestamp descending."""
    params: list[object] = []
    scope_cond = _build_scope_clause(directory, git_root, params)

    conditions = [scope_cond]
    if search:
        conditions.append("command LIKE ?")
        params.append(f"%{search}%")
    if success_only:
        conditions.append("exit_code = 0")
    elif failed_only:
        conditions.append("exit_code != 0 AND exit_code IS NOT NULL")

    where_str = " AND ".join(conditions)
    params.append(limit)

    query = f"""
    SELECT id, directory, command, timestamp, exit_code, duration_ms, session_id, git_root
    FROM command_history
    WHERE {where_str}
    ORDER BY timestamp DESC
    LIMIT ?;
    """

    records: list[CommandRecord] = []
    for row in conn.execute(query, params):
        records.append(
            CommandRecord(
                id=row["id"],
                directory=row["directory"],
                command=row["command"],
                timestamp=row["timestamp"],
                exit_code=row["exit_code"],
                duration_ms=row["duration_ms"],
                session_id=row["session_id"],
                git_root=row["git_root"],
            )
        )
    return records


def query_first(
    conn: sqlite3.Connection,
    directory: str,
    limit: int = 20,
    search: str = "",
    git_root: str | None = None,
) -> list[CommandRecord]:
    """Return command executions sorted by timestamp ascending (earliest first)."""
    params: list[object] = []
    scope_cond = _build_scope_clause(directory, git_root, params)

    conditions = [scope_cond]
    if search:
        conditions.append("command LIKE ?")
        params.append(f"%{search}%")

    where_str = " AND ".join(conditions)
    params.append(limit)

    query = f"""
    SELECT id, directory, command, timestamp, exit_code, duration_ms, session_id, git_root
    FROM command_history
    WHERE {where_str}
    ORDER BY timestamp ASC
    LIMIT ?;
    """

    records: list[CommandRecord] = []
    for row in conn.execute(query, params):
        records.append(
            CommandRecord(
                id=row["id"],
                directory=row["directory"],
                command=row["command"],
                timestamp=row["timestamp"],
                exit_code=row["exit_code"],
                duration_ms=row["duration_ms"],
                session_id=row["session_id"],
                git_root=row["git_root"],
            )
        )
    return records


def query_matching_commands(
    conn: sqlite3.Connection,
    directory: str,
    keyword: str,
    git_root: str | None = None,
) -> list[str]:
    """Return distinct commands containing keyword, ordered by most recent occurrence."""
    params: list[object] = []
    scope_cond = _build_scope_clause(directory, git_root, params)
    params.append(f"%{keyword}%")

    query = f"""
    SELECT command, MAX(timestamp) AS last_seen
    FROM command_history
    WHERE {scope_cond} AND command LIKE ?
    GROUP BY command
    ORDER BY last_seen DESC;
    """
    return [row["command"] for row in conn.execute(query, params)]


def delete_directory_history(conn: sqlite3.Connection, directory: str) -> int:
    """Delete all history entries for a given directory. Return number of deleted records."""
    query = "DELETE FROM command_history WHERE directory = ?;"
    with immediate_transaction(conn):
        cursor = conn.execute(query, (directory,))
        return cursor.rowcount
