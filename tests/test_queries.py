"""Unit tests for CHID query helpers."""

import tempfile
import unittest
from pathlib import Path

from chid.db import get_connection, initialize_schema
from chid.models import CommandRecord
from chid.queries import (
    delete_directory_history,
    insert_command,
    query_first,
    query_frequency,
    query_matching_commands,
    query_recent,
    update_command_completion,
)


class TestQueries(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_queries.sqlite"
        self.conn = get_connection(self.db_path)
        initialize_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_insert_and_recent(self) -> None:
        rec1 = CommandRecord(
            directory="/project",
            command="git status",
            timestamp=1000,
            session_id="sess-1",
            git_root="/project",
        )
        rec2 = CommandRecord(
            directory="/project",
            command="pytest",
            timestamp=2000,
            session_id="sess-1",
            git_root="/project",
        )
        id1 = insert_command(self.conn, rec1)
        id2 = insert_command(self.conn, rec2)
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)

        recent = query_recent(self.conn, directory="/project", limit=10)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0].command, "pytest")
        self.assertEqual(recent[1].command, "git status")

    def test_completion_update_safety(self) -> None:
        # Insert two commands in same session
        insert_command(
            self.conn,
            CommandRecord(
                directory="/project",
                command="cmd1",
                timestamp=1000,
                session_id="s1",
                exit_code=0,
                duration_ms=10,
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/project",
                command="cmd2",
                timestamp=2000,
                session_id="s1",
            ),
        )

        # First update should target cmd2 (exit_code IS NULL)
        updated = update_command_completion(
            self.conn, session_id="s1", exit_code=42, duration_ms=150
        )
        self.assertTrue(updated)

        recent = query_recent(self.conn, directory="/project")
        self.assertEqual(recent[0].command, "cmd2")
        self.assertEqual(recent[0].exit_code, 42)
        self.assertEqual(recent[0].duration_ms, 150)
        self.assertEqual(recent[1].command, "cmd1")
        self.assertEqual(recent[1].exit_code, 0)
        self.assertEqual(recent[1].duration_ms, 10)

        # Repeated update should return False since no unfinished command exists in s1
        repeat_updated = update_command_completion(
            self.conn, session_id="s1", exit_code=0, duration_ms=50
        )
        self.assertFalse(repeat_updated)
        # Previous records untouched
        recent_after = query_recent(self.conn, directory="/project")
        self.assertEqual(recent_after[0].exit_code, 42)

    def test_frequency_calculation(self) -> None:
        for _ in range(3):
            insert_command(
                self.conn,
                CommandRecord(
                    directory="/work",
                    command="npm test",
                    timestamp=1000,
                    session_id="s1",
                ),
            )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/work",
                command="git diff",
                timestamp=2000,
                session_id="s1",
            ),
        )

        freq = query_frequency(self.conn, directory="/work")
        self.assertEqual(len(freq), 2)
        self.assertEqual(freq[0].command, "npm test")
        self.assertEqual(freq[0].count, 3)
        self.assertEqual(freq[0].percentage, 75.0)
        self.assertEqual(freq[1].command, "git diff")
        self.assertEqual(freq[1].count, 1)
        self.assertEqual(freq[1].percentage, 25.0)

    def test_search_and_repo_filtering(self) -> None:
        insert_command(
            self.conn,
            CommandRecord(
                directory="/repo/sub1",
                command="cargo check",
                timestamp=100,
                session_id="s1",
                git_root="/repo",
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/repo/sub2",
                command="cargo build --release",
                timestamp=200,
                session_id="s1",
                git_root="/repo",
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/other",
                command="cargo build",
                timestamp=300,
                session_id="s1",
                git_root=None,
            ),
        )

        # Repo scoping
        repo_recent = query_recent(
            self.conn, directory="/repo/sub1", git_root="/repo"
        )
        self.assertEqual(len(repo_recent), 2)

        # Search filtering
        search_res = query_recent(
            self.conn, directory="/repo/sub1", git_root="/repo", search="release"
        )
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0].command, "cargo build --release")

    def test_query_first(self) -> None:
        insert_command(
            self.conn,
            CommandRecord(
                directory="/test", command="first", timestamp=10, session_id="s1"
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/test", command="second", timestamp=20, session_id="s1"
            ),
        )
        first_records = query_first(self.conn, directory="/test")
        self.assertEqual(first_records[0].command, "first")
        self.assertEqual(first_records[1].command, "second")

    def test_query_matching_commands(self) -> None:
        insert_command(
            self.conn,
            CommandRecord(
                directory="/dir", command="docker run -it", timestamp=10, session_id="s1"
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/dir", command="docker ps", timestamp=20, session_id="s1"
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/dir", command="docker run -d", timestamp=30, session_id="s1"
            ),
        )
        matches = query_matching_commands(self.conn, directory="/dir", keyword="run")
        self.assertEqual(matches, ["docker run -d", "docker run -it"])

    def test_delete_directory_history(self) -> None:
        insert_command(
            self.conn,
            CommandRecord(
                directory="/to_delete", command="ls", timestamp=1, session_id="s1"
            ),
        )
        insert_command(
            self.conn,
            CommandRecord(
                directory="/keep", command="ls", timestamp=2, session_id="s1"
            ),
        )
        deleted = delete_directory_history(self.conn, "/to_delete")
        self.assertEqual(deleted, 1)
        self.assertEqual(len(query_recent(self.conn, "/to_delete")), 0)
        self.assertEqual(len(query_recent(self.conn, "/keep")), 1)

    def test_invalid_command_filtering(self) -> None:
        # Valid command
        insert_command(
            self.conn,
            CommandRecord(directory="/app", command="pytest", timestamp=100, session_id="s1", exit_code=0),
        )
        # Runtime failure (e.g. tests failed)
        insert_command(
            self.conn,
            CommandRecord(directory="/app", command="npm test", timestamp=200, session_id="s1", exit_code=1),
        )
        # Bad arguments / syntax error (exit code 2)
        insert_command(
            self.conn,
            CommandRecord(directory="/app", command="grep --invalid-flag", timestamp=300, session_id="s1", exit_code=2),
        )
        # Command not found typo (exit code 127)
        insert_command(
            self.conn,
            CommandRecord(directory="/app", command="pythn main.py", timestamp=400, session_id="s1", exit_code=127),
        )

        # Default query should filter out exit codes 2 and 127
        recent = query_recent(self.conn, directory="/app")
        self.assertEqual(len(recent), 2)
        cmd_names = [r.command for r in recent]
        self.assertIn("npm test", cmd_names)
        self.assertIn("pytest", cmd_names)
        self.assertNotIn("grep --invalid-flag", cmd_names)
        self.assertNotIn("pythn main.py", cmd_names)

        # include_invalid=True should return all 4
        all_recent = query_recent(self.conn, directory="/app", include_invalid=True)
        self.assertEqual(len(all_recent), 4)

        # only_invalid=True should return only 2 and 127
        invalid_only = query_recent(self.conn, directory="/app", only_invalid=True)
        self.assertEqual(len(invalid_only), 2)
        inv_names = [r.command for r in invalid_only]
        self.assertIn("grep --invalid-flag", inv_names)
        self.assertIn("pythn main.py", inv_names)

    def test_time_based_query_filtering(self) -> None:
        # Insert commands across timestamps: 1000, 2000, 3000, 4000
        for ts, cmd in [(1000, "git fetch"), (2000, "git pull"), (3000, "git status"), (4000, "git pull")]:
            insert_command(
                self.conn,
                CommandRecord(
                    directory="/time_test",
                    command=cmd,
                    timestamp=ts,
                    session_id="s1",
                    exit_code=0,
                ),
            )

        # 1. query_recent with since_ms=2500 -> 3000 and 4000
        recent_since = query_recent(self.conn, directory="/time_test", since_ms=2500)
        self.assertEqual(len(recent_since), 2)
        self.assertEqual([r.timestamp for r in recent_since], [4000, 3000])

        # 2. query_recent with until_ms=2500 -> 1000 and 2000
        recent_until = query_recent(self.conn, directory="/time_test", until_ms=2500)
        self.assertEqual(len(recent_until), 2)
        self.assertEqual([r.timestamp for r in recent_until], [2000, 1000])

        # 3. query_recent with bounded window [1500, 3500] -> 2000 and 3000
        recent_window = query_recent(self.conn, directory="/time_test", since_ms=1500, until_ms=3500)
        self.assertEqual(len(recent_window), 2)
        self.assertEqual([r.timestamp for r in recent_window], [3000, 2000])

        # 4. query_first with bounded window [1500, 3500] -> 2000 and 3000 in ascending order
        first_window = query_first(self.conn, directory="/time_test", since_ms=1500, until_ms=3500)
        self.assertEqual(len(first_window), 2)
        self.assertEqual([r.timestamp for r in first_window], [2000, 3000])

        # 5. query_frequency with time filtering
        # Over all time: total=4, "git pull"=2 (50%)
        # For since_ms=2500: total=2 ("git status"=1, "git pull"=1), each 50%
        freq = query_frequency(self.conn, directory="/time_test", since_ms=2500)
        self.assertEqual(len(freq), 2)
        self.assertEqual(freq[0].count, 1)
        self.assertEqual(freq[0].percentage, 50.0)

        # 6. query_matching_commands with time window
        matches = query_matching_commands(self.conn, directory="/time_test", keyword="pull", until_ms=2500)
        self.assertEqual(matches, ["git pull"])
        no_matches = query_matching_commands(self.conn, directory="/time_test", keyword="fetch", since_ms=2500)
        self.assertEqual(no_matches, [])


if __name__ == "__main__":
    unittest.main()

