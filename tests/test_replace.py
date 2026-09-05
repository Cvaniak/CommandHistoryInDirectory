"""Unit tests for session command buffer replacement."""

import os
import tempfile
import unittest
from pathlib import Path

from chid.replace import (
    parse_buffer_request,
    resolve_buffer_replacement,
    write_session_cache,
)


class TestReplace(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_cache_home = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = self.temp_dir.name

    def tearDown(self) -> None:
        if self.old_cache_home is not None:
            os.environ["XDG_CACHE_HOME"] = self.old_cache_home
        else:
            os.environ.pop("XDG_CACHE_HOME", None)
        self.temp_dir.cleanup()

    def test_parse_buffer_request(self) -> None:
        self.assertEqual(parse_buffer_request("chid 1"), 1)
        self.assertEqual(parse_buffer_request("chid   42  "), 42)
        self.assertEqual(parse_buffer_request("h 3", alias="h"), 3)
        self.assertEqual(parse_buffer_request("h   5  ", alias="h"), 5)
        self.assertIsNone(parse_buffer_request("chid"))
        self.assertIsNone(parse_buffer_request("chid --recent"))
        self.assertIsNone(parse_buffer_request("git commit"))
        self.assertIsNone(parse_buffer_request("h status", alias="h"))

    def test_session_cache_and_resolution(self) -> None:
        commands = [
            "git status",
            'echo "semi;colon" | grep semi && echo ok',
            "pytest -v",
        ]
        write_session_cache("sess-1", commands)

        # Valid 1-based resolutions
        self.assertEqual(resolve_buffer_replacement("sess-1", "chid 1"), "git status")
        self.assertEqual(
            resolve_buffer_replacement("sess-1", "chid 2"),
            'echo "semi;colon" | grep semi && echo ok',
        )
        self.assertEqual(resolve_buffer_replacement("sess-1", "chid 3"), "pytest -v")

        # Out of bounds retains original buffer
        self.assertEqual(resolve_buffer_replacement("sess-1", "chid 99"), "chid 99")

        # Non-matching buffer retained
        self.assertEqual(
            resolve_buffer_replacement("sess-1", "ls -la"),
            "ls -la",
        )

    def test_session_isolation(self) -> None:
        write_session_cache("sess-A", ["cmdA1", "cmdA2"])
        write_session_cache("sess-B", ["cmdB1", "cmdB2"])

        self.assertEqual(resolve_buffer_replacement("sess-A", "chid 1"), "cmdA1")
        self.assertEqual(resolve_buffer_replacement("sess-B", "chid 1"), "cmdB1")


if __name__ == "__main__":
    unittest.main()
