"""End-to-end tests for CHID CLI entry point and subcommands."""

import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from chid.cli import main
from chid.db import get_connection, initialize_schema
from chid.replace import resolve_buffer_replacement, write_session_cache


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cli.sqlite"
        self.cache_dir = Path(self.temp_dir.name) / "cache"

        self.old_db = os.environ.get("CHID_DB_PATH")
        self.old_cache = os.environ.get("XDG_CACHE_HOME")
        self.old_session = os.environ.get("CHID_SESSION")

        os.environ["CHID_DB_PATH"] = str(self.db_path)
        os.environ["XDG_CACHE_HOME"] = str(self.cache_dir)
        os.environ["CHID_SESSION"] = "test-session-cli"

    def tearDown(self) -> None:
        if self.old_db is not None:
            os.environ["CHID_DB_PATH"] = self.old_db
        else:
            os.environ.pop("CHID_DB_PATH", None)

        if self.old_cache is not None:
            os.environ["XDG_CACHE_HOME"] = self.old_cache
        else:
            os.environ.pop("XDG_CACHE_HOME", None)

        if self.old_session is not None:
            os.environ["CHID_SESSION"] = self.old_session
        else:
            os.environ.pop("CHID_SESSION", None)

        self.temp_dir.cleanup()

    def _run_cli(self, args: list[str]) -> tuple[str, str]:
        saved_argv = sys.argv
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        out = io.StringIO()
        err = io.StringIO()
        try:
            sys.argv = ["chid"] + args
            sys.stdout = out
            sys.stderr = err
            main()
            return out.getvalue(), err.getvalue()
        finally:
            sys.argv = saved_argv
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr

    def test_version_flag(self) -> None:
        try:
            out, _ = self._run_cli(["--version"])
        except SystemExit:
            out = ""
        # argparse --version calls print and exits
        # Note: in unittest, sys.exit may be raised
        # Let's verify chid.__version__
        import chid
        self.assertEqual(chid.__version__, "0.2.0")

    def test_record_start_and_finish_hyphen_command(self) -> None:
        # Command starting with hyphen e.g. "-rf /tmp/bad"
        out, _ = self._run_cli(["record-start", self.temp_dir.name, "test-session-cli", "-rf /tmp/bad"])
        self.assertEqual(out, "")

        conn = get_connection(self.db_path)
        row = conn.execute("SELECT * FROM command_history WHERE session_id = 'test-session-cli';").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["command"], "-rf /tmp/bad")
        self.assertIsNone(row["exit_code"])

        # Finish execution
        out, _ = self._run_cli(["record-finish", "test-session-cli", "0"])
        row_after = conn.execute("SELECT * FROM command_history WHERE session_id = 'test-session-cli';").fetchone()
        conn.close()

        self.assertIsNotNone(row_after)
        self.assertEqual(row_after["exit_code"], 0)

    def test_replace_hook(self) -> None:
        write_session_cache("test-session-cli", ["git status", "pytest -v"])
        out, _ = self._run_cli(["replace", "test-session-cli", "chid 2"])
        self.assertEqual(out, "pytest -v")

    def test_init_subcommand(self) -> None:
        out_zsh, _ = self._run_cli(["init", "zsh"])
        self.assertIn("add-zsh-hook", out_zsh)

        out_bash, _ = self._run_cli(["init", "bash"])
        self.assertIn("PROMPT_COMMAND", out_bash)

        out_fish, _ = self._run_cli(["init", "fish"])
        self.assertIn("fish_preexec", out_fish)

    def test_query_recent_and_raw(self) -> None:
        self._run_cli(["record-start", str(Path.cwd().resolve()), "test-session-cli", "npm install"])
        self._run_cli(["record-finish", "test-session-cli", "0"])

        self._run_cli(["record-start", str(Path.cwd().resolve()), "test-session-cli", "cargo build"])
        self._run_cli(["record-finish", "test-session-cli", "1"])

        out, _ = self._run_cli(["-r", "--raw"])
        lines = out.strip().split("\n")
        self.assertEqual(lines, ["cargo build", "npm install"])

    def test_clear_history(self) -> None:
        cwd = str(Path.cwd().resolve())
        self._run_cli(["record-start", cwd, "test-session-cli", "echo test"])
        self._run_cli(["record-finish", "test-session-cli", "0"])

        out, _ = self._run_cli(["--clear"])
        self.assertIn("Cleared", out)

        out_after, _ = self._run_cli(["-r", "--raw"])
        self.assertEqual(out_after.strip(), "")

    def test_invalid_and_all_cli_flags(self) -> None:
        cwd = str(Path.cwd().resolve())
        # Valid command
        self._run_cli(["record-start", cwd, "test-session-cli", "git status"])
        self._run_cli(["record-finish", "test-session-cli", "0"])

        # Typo / not found
        self._run_cli(["record-start", cwd, "test-session-cli", "gitt branch"])
        self._run_cli(["record-finish", "test-session-cli", "127"])

        # Bad arguments
        self._run_cli(["record-start", cwd, "test-session-cli", "grep --wrong-flag"])
        self._run_cli(["record-finish", "test-session-cli", "2"])

        # Default query hides typos and bad args
        out_default, _ = self._run_cli(["-r", "--raw"])
        cmds = out_default.strip().split("\n")
        self.assertIn("git status", cmds)
        self.assertNotIn("gitt branch", cmds)
        self.assertNotIn("grep --wrong-flag", cmds)

        # --all shows everything
        out_all, _ = self._run_cli(["-r", "-a", "--raw"])
        cmds_all = out_all.strip().split("\n")
        self.assertIn("git status", cmds_all)
        self.assertIn("gitt branch", cmds_all)
        self.assertIn("grep --wrong-flag", cmds_all)

        # --invalid shows only the bad commands
        out_inv, _ = self._run_cli(["--invalid", "--raw"])
        cmds_inv = out_inv.strip().split("\n")
        self.assertNotIn("git status", cmds_inv)
        self.assertIn("gitt branch", cmds_inv)
        self.assertIn("grep --wrong-flag", cmds_inv)

    def test_time_filtering_cli(self) -> None:
        cwd = str(Path.cwd().resolve())
        conn = get_connection(self.db_path)
        initialize_schema(conn)
        now_ms = int(time.time() * 1000)

        # 1. Command run right now (1s ago)
        # 2. Command run 2 hours ago
        # 3. Command run yesterday (26 hours ago)
        # 4. Command run 3 days ago (72 hours ago)
        records = [
            ("echo now", now_ms - 1000),
            ("echo 2hours_ago", now_ms - 2 * 3600 * 1000),
            ("echo yesterday", now_ms - 26 * 3600 * 1000),
            ("echo 3days_ago", now_ms - 72 * 3600 * 1000),
        ]
        for cmd, ts in records:
            conn.execute(
                "INSERT INTO command_history (directory, command, timestamp, session_id, exit_code) VALUES (?, ?, ?, ?, 0);",
                (cwd, cmd, ts, "s-time"),
            )
        conn.close()

        # Test --last 30m
        out_last, _ = self._run_cli(["-r", "--raw", "--last", "30m"])
        cmds_last = [c for c in out_last.strip().split("\n") if c]
        self.assertEqual(cmds_last, ["echo now"])

        # Test --since / --after 3h
        out_since, _ = self._run_cli(["-r", "--raw", "--since", "3h"])
        cmds_since = [c for c in out_since.strip().split("\n") if c]
        self.assertIn("echo now", cmds_since)
        self.assertIn("echo 2hours_ago", cmds_since)
        self.assertNotIn("echo yesterday", cmds_since)

        # Test --until / --before 3h
        out_until, _ = self._run_cli(["-r", "--raw", "--until", "3h"])
        cmds_until = [c for c in out_until.strip().split("\n") if c]
        self.assertNotIn("echo now", cmds_until)
        self.assertNotIn("echo 2hours_ago", cmds_until)
        self.assertIn("echo yesterday", cmds_until)
        self.assertIn("echo 3days_ago", cmds_until)

        # Test --range 3h..1h
        out_range, _ = self._run_cli(["-r", "--raw", "--range", "3h..1h"])
        cmds_range = [c for c in out_range.strip().split("\n") if c]
        self.assertEqual(cmds_range, ["echo 2hours_ago"])

        # Test conflicting flags raise SystemExit (via parser.error)
        with self.assertRaises(SystemExit):
            self._run_cli(["--today", "--yesterday"])

        with self.assertRaises(SystemExit):
            self._run_cli(["--since", "invalid_time_xyz"])


if __name__ == "__main__":
    unittest.main()

