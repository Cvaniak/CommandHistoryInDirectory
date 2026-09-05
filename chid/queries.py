"""Query functions for recording and retrieving command history."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from chid.db import immediate_transaction
from chid.models import CommandRecord, FrequencyStat

if TYPE_CHECKING:
    from typing import Sequence

INVALID_EXIT_CODES = (2, 64, 126, 127)


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
    is_global: bool = False,
    recursive: bool = False,
    max_depth: int | None = None,
) -> str:
    """Helper to generate directory, tree, or repository scope WHERE clause."""
    if is_global:
        return "1=1"
    if git_root:
        params.append(git_root)
        return "git_root = ?"
    if recursive:
        clean_dir = directory.rstrip("/")
        params.extend([clean_dir, f"{clean_dir}/%"])
        cond = "(directory = ? OR directory LIKE ?)"
        if max_depth is not None:
            base_slashes = clean_dir.count("/")
            max_slashes = base_slashes + max_depth
            cond += " AND (length(directory) - length(replace(directory, '/', ''))) <= ?"
            params.append(max_slashes)
        return cond
    params.append(directory)
    return "directory = ?"


def query_frequency(
    conn: sqlite3.Connection,
    directory: str,
    limit: int = 20,
    search: str = "",
    git_root: str | None = None,
    include_invalid: bool = False,
    only_invalid: bool = False,
    since_ms: int | None = None,
    until_ms: int | None = None,
    is_global: bool = False,
    recursive: bool = False,
    max_depth: int | None = None,
    session_id: str | None = None,
) -> list[FrequencyStat]:
    """Return command frequency metrics, percentage of total executions, and last run timestamp."""
    count_params: list[object] = []
    scope_cond = _build_scope_clause(
        directory,
        git_root,
        count_params,
        is_global=is_global,
        recursive=recursive,
        max_depth=max_depth,
    )
    search_cond = ""
    if search:
        search_cond = " AND command LIKE ?"
        count_params.append(f"%{search}%")

    time_cond = ""
    if since_ms is not None:
        time_cond += " AND timestamp >= ?"
        count_params.append(since_ms)
    if until_ms is not None:
        time_cond += " AND timestamp <= ?"
        count_params.append(until_ms)

    session_cond = ""
    if session_id:
        session_cond = " AND session_id = ?"
        count_params.append(session_id)

    if only_invalid:
        valid_cond = f" AND exit_code IN ({','.join(str(c) for c in INVALID_EXIT_CODES)})"
    elif not include_invalid:
        valid_cond = f" AND (exit_code IS NULL OR exit_code NOT IN ({','.join(str(c) for c in INVALID_EXIT_CODES)}))"
    else:
        valid_cond = ""

    total_query = f"SELECT COUNT(*) AS total FROM command_history WHERE {scope_cond}{search_cond}{time_cond}{session_cond}{valid_cond};"
    total_row = conn.execute(total_query, count_params).fetchone()
    total_count = total_row["total"] if total_row else 0

    if total_count == 0:
        return []

    stats_params: list[object] = []
    scope_cond_stats = _build_scope_clause(
        directory,
        git_root,
        stats_params,
        is_global=is_global,
        recursive=recursive,
        max_depth=max_depth,
    )
    if search:
        stats_params.append(f"%{search}%")
    if since_ms is not None:
        stats_params.append(since_ms)
    if until_ms is not None:
        stats_params.append(until_ms)
    if session_id:
        stats_params.append(session_id)
    stats_params.append(limit)

    stats_query = f"""
    SELECT
        command,
        COUNT(*) AS cmd_count,
        MAX(timestamp) AS last_run
    FROM command_history
    WHERE {scope_cond_stats}{search_cond}{time_cond}{session_cond}{valid_cond}
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
    include_invalid: bool = False,
    only_invalid: bool = False,
    since_ms: int | None = None,
    until_ms: int | None = None,
    is_global: bool = False,
    recursive: bool = False,
    max_depth: int | None = None,
    session_id: str | None = None,
) -> list[CommandRecord]:
    """Return recent command executions sorted by timestamp descending."""
    params: list[object] = []
    scope_cond = _build_scope_clause(
        directory,
        git_root,
        params,
        is_global=is_global,
        recursive=recursive,
        max_depth=max_depth,
    )

    conditions = [scope_cond]
    if search:
        conditions.append("command LIKE ?")
        params.append(f"%{search}%")

    if since_ms is not None:
        conditions.append("timestamp >= ?")
        params.append(since_ms)
    if until_ms is not None:
        conditions.append("timestamp <= ?")
        params.append(until_ms)

    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)

    if only_invalid:
        conditions.append(f"exit_code IN ({','.join(str(c) for c in INVALID_EXIT_CODES)})")
    elif success_only:
        conditions.append("exit_code = 0")
    elif failed_only:
        conditions.append("exit_code != 0 AND exit_code IS NOT NULL")
    elif not include_invalid:
        conditions.append(
            f"(exit_code IS NULL OR exit_code NOT IN ({','.join(str(c) for c in INVALID_EXIT_CODES)}))"
        )

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
    include_invalid: bool = False,
    only_invalid: bool = False,
    since_ms: int | None = None,
    until_ms: int | None = None,
    is_global: bool = False,
    recursive: bool = False,
    max_depth: int | None = None,
    session_id: str | None = None,
) -> list[CommandRecord]:
    """Return command executions sorted by timestamp ascending (earliest first)."""
    params: list[object] = []
    scope_cond = _build_scope_clause(
        directory,
        git_root,
        params,
        is_global=is_global,
        recursive=recursive,
        max_depth=max_depth,
    )

    conditions = [scope_cond]
    if search:
        conditions.append("command LIKE ?")
        params.append(f"%{search}%")

    if since_ms is not None:
        conditions.append("timestamp >= ?")
        params.append(since_ms)
    if until_ms is not None:
        conditions.append("timestamp <= ?")
        params.append(until_ms)

    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)

    if only_invalid:
        conditions.append(f"exit_code IN ({','.join(str(c) for c in INVALID_EXIT_CODES)})")
    elif not include_invalid:
        conditions.append(
            f"(exit_code IS NULL OR exit_code NOT IN ({','.join(str(c) for c in INVALID_EXIT_CODES)}))"
        )

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
    include_invalid: bool = False,
    since_ms: int | None = None,
    until_ms: int | None = None,
    is_global: bool = False,
    recursive: bool = False,
    max_depth: int | None = None,
    session_id: str | None = None,
) -> list[str]:
    """Return distinct commands containing keyword, ordered by most recent occurrence."""
    params: list[object] = []
    scope_cond = _build_scope_clause(
        directory,
        git_root,
        params,
        is_global=is_global,
        recursive=recursive,
        max_depth=max_depth,
    )
    params.append(f"%{keyword}%")

    time_cond = ""
    if since_ms is not None:
        time_cond += " AND timestamp >= ?"
        params.append(since_ms)
    if until_ms is not None:
        time_cond += " AND timestamp <= ?"
        params.append(until_ms)

    session_cond = ""
    if session_id:
        session_cond = " AND session_id = ?"
        params.append(session_id)

    valid_cond = ""
    if not include_invalid:
        valid_cond = f" AND (exit_code IS NULL OR exit_code NOT IN ({','.join(str(c) for c in INVALID_EXIT_CODES)}))"

    query = f"""
    SELECT command, MAX(timestamp) AS last_seen
    FROM command_history
    WHERE {scope_cond} AND command LIKE ?{time_cond}{session_cond}{valid_cond}
    GROUP BY command
    ORDER BY last_seen DESC;
    """
    return [row["command"] for row in conn.execute(query, params)]


def delete_directory_history(
    conn: sqlite3.Connection,
    directory: str,
    recursive: bool = False,
    is_global: bool = False,
) -> int:
    """Delete history entries for a given directory, tree, or globally. Return number of deleted records."""
    if is_global:
        query = "DELETE FROM command_history;"
        params: tuple[object, ...] = ()
    elif recursive:
        clean_dir = directory.rstrip("/")
        query = "DELETE FROM command_history WHERE directory = ? OR directory LIKE ?;"
        params = (clean_dir, f"{clean_dir}/%")
    else:
        query = "DELETE FROM command_history WHERE directory = ?;"
        params = (directory,)

    with immediate_transaction(conn):
        cursor = conn.execute(query, params)
        return cursor.rowcount
