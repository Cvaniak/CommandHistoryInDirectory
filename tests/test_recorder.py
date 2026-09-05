"""Unit tests for execution recording hooks."""

import tempfile
import time
import unittest
from pathlib import Path

from chid.db import get_connection
from chid.recorder import (
    is_blank,
    is_chid_command,
    record_command_finish,
    record_command_start,
    should_ignore,
)


class TestRecorder(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_recorder.sqlite"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_ignore_rules(self) -> None:
        self.assertTrue(is_blank(""))
        self.assertTrue(is_blank("   \t\n"))
        self.assertFalse(is_blank("ls"))

        self.assertTrue(is_chid_command("chid"))
        self.assertTrue(is_chid_command("chid --recent"))
        self.assertTrue(is_chid_command("h --recent", alias="h"))
        self.assertFalse(is_chid_command("git status", alias="h"))

        self.assertTrue(should_ignore("", directory="/tmp"))
        self.assertTrue(should_ignore("  ls", directory="/tmp"))
        self.assertTrue(should_ignore("chid", directory="/tmp"))
        self.assertTrue(should_ignore("h 2", directory="/tmp", alias="h"))
        self.assertFalse(should_ignore("cargo build", directory="/tmp"))

    def test_record_lifecycle(self) -> None:
        rec_id = record_command_start(
            directory=self.temp_dir.name,
            command="python3 script.py",
            session_id="term-1",
            timestamp_ms=1000,
            db_path=self.db_path,
        )
        self.assertIsNotNone(rec_id)

        # Finish execution 250ms later with exit code 0
        finished = record_command_finish(
            session_id="term-1",
            exit_code=0,
            end_timestamp_ms=1250,
            db_path=self.db_path,
        )
        self.assertTrue(finished)

        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM command_history WHERE id = ?", (rec_id,)).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["command"], "python3 script.py")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["duration_ms"], 250)

    def test_repeated_finish_drift_protection(self) -> None:
        rec_id = record_command_start(
            directory=self.temp_dir.name,
            command="make",
            session_id="term-2",
            timestamp_ms=2000,
            db_path=self.db_path,
        )
        self.assertIsNotNone(rec_id)

        # First finish
        first_finish = record_command_finish(
            session_id="term-2",
            exit_code=2,
            end_timestamp_ms=2100,
            db_path=self.db_path,
        )
        self.assertTrue(first_finish)

        # Second finish (e.g. prompt redraw or stray precmd hook)
        second_finish = record_command_finish(
            session_id="term-2",
            exit_code=0,
            end_timestamp_ms=5000,
            db_path=self.db_path,
        )
        self.assertFalse(second_finish)

        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM command_history WHERE id = ?", (rec_id,)).fetchone()
        conn.close()

        # Must preserve original failure exit code and original duration
        self.assertEqual(row["exit_code"], 2)
        self.assertEqual(row["duration_ms"], 100)


if __name__ == "__main__":
    unittest.main()
