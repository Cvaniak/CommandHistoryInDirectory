"""Tests for CHID packaging and baseline CLI entry point."""

import io
import sys
import unittest

import chid
import chid.cli


class TestPackaging(unittest.TestCase):
    def test_package_version(self) -> None:
        self.assertEqual(chid.__version__, "0.2.0")

    def test_cli_version_flag(self) -> None:
        saved_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            sys.argv = ["chid", "--version"]
            chid.cli.main()
            self.assertEqual(sys.stdout.getvalue().strip(), "chid 0.2.0")
        finally:
            sys.stdout = saved_stdout

    def test_cli_default_invocation(self) -> None:
        saved_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            sys.argv = ["chid"]
            chid.cli.main()
            output = sys.stdout.getvalue().strip()
            # Default empty history displays notice or table
            self.assertTrue(
                "No matching command history found" in output
                or "Frequent Commands" in output
            )
        finally:
            sys.stdout = saved_stdout


if __name__ == "__main__":
    unittest.main()
