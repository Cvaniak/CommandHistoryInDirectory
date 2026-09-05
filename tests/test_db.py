"""Unit tests for SQLite database connection and schema initialization."""

import tempfile
import unittest
from pathlib import Path

from chid.db import get_connection, immediate_transaction, initialize_schema


class TestDB(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_chid.sqlite"
        self.conn = get_connection(self.db_path)
        initialize_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_schema_created(self) -> None:
        tables = [
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        self.assertIn("command_history", tables)

    def test_indices_created(self) -> None:
        indices = [
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index';"
            ).fetchall()
        ]
        self.assertIn("idx_chid_dir_time", indices)
        self.assertIn("idx_chid_dir_cmd", indices)
        self.assertIn("idx_chid_git_time", indices)
        self.assertIn("idx_chid_git_cmd", indices)
        self.assertIn("idx_chid_session", indices)

    def test_wal_journal_mode(self) -> None:
        mode = self.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

    def test_immediate_transaction(self) -> None:
        with immediate_transaction(self.conn):
            self.conn.execute(
                """
                INSERT INTO command_history (directory, command, timestamp, session_id)
                VALUES ('/test', 'ls', 1000, 'sess-1');
                """
            )
        row = self.conn.execute(
            "SELECT count(*) FROM command_history;"
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_immediate_transaction_rollback(self) -> None:
        try:
            with immediate_transaction(self.conn):
                self.conn.execute(
                    """
                    INSERT INTO command_history (directory, command, timestamp, session_id)
                    VALUES ('/test', 'bad_cmd', 2000, 'sess-2');
                    """
                )
                raise RuntimeError("Forced error")
        except RuntimeError:
            pass

        row = self.conn.execute(
            "SELECT count(*) FROM command_history WHERE command = 'bad_cmd';"
        ).fetchone()
        self.assertEqual(row[0], 0)


if __name__ == "__main__":
    unittest.main()
