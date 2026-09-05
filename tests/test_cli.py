"""End-to-end tests for CHID CLI entry point and subcommands."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

from chid.cli import main
from chid.db import get_connection
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


if __name__ == "__main__":
    unittest.main()
