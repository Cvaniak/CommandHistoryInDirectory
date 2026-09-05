"""Unit tests for shell parser and flag analysis."""

import unittest

from chid.parser import (
    analyze_tool_flags,
    extract_executable_and_subcommand,
    extract_flags_from_tokens,
    is_env_assignment,
    is_flag,
    normalize_flag,
    safe_shlex_split,
    split_command_segments,
    strip_wrappers_and_env,
    unpack_short_flags,
)


class TestParser(unittest.TestCase):
    def test_safe_shlex_split_normal(self) -> None:
        tokens = safe_shlex_split('git commit -m "initial commit"')
        self.assertEqual(tokens, ["git", "commit", "-m", "initial commit"])

    def test_safe_shlex_split_unclosed_quote(self) -> None:
        tokens = safe_shlex_split('echo "unclosed quote')
        self.assertIn("echo", tokens)

    def test_split_command_segments_pipeline(self) -> None:
        cmd = 'npm run build && git commit -m "fix" | tee log.txt ; ls -la'
        segments = split_command_segments(cmd)
        self.assertEqual(
            segments,
            ["npm run build", 'git commit -m "fix"', "tee log.txt", "ls -la"],
        )

    def test_split_command_segments_quoted_operator(self) -> None:
        cmd = 'echo "hello && world" | grep hello'
        segments = split_command_segments(cmd)
        self.assertEqual(segments, ['echo "hello && world"', "grep hello"])

    def test_split_command_segments_unclosed_quote_resilience(self) -> None:
        cmd = 'echo "unclosed && not separated'
        segments = split_command_segments(cmd)
        self.assertIsInstance(segments, list)
        self.assertTrue(len(segments) >= 1)

    def test_is_env_assignment(self) -> None:
        self.assertTrue(is_env_assignment("PORT=8080"))
        self.assertTrue(is_env_assignment("NODE_ENV=production"))
        self.assertFalse(is_env_assignment("git"))
        self.assertFalse(is_env_assignment("--flag=value"))

    def test_strip_wrappers_and_env(self) -> None:
        tokens = ["FOO=bar", "DEBUG=1", "sudo", "-u", "admin", "docker", "ps"]
        cleaned = strip_wrappers_and_env(tokens)
        self.assertEqual(cleaned, ["docker", "ps"])

    def test_is_flag(self) -> None:
        self.assertTrue(is_flag("-v"))
        self.assertTrue(is_flag("-rf"))
        self.assertTrue(is_flag("--help"))
        self.assertTrue(is_flag("--output=json"))
        self.assertFalse(is_flag("commit"))
        self.assertFalse(is_flag("- bullet point"))

    def test_normalize_flag(self) -> None:
        self.assertEqual(normalize_flag("--output=json"), "--output")
        self.assertEqual(normalize_flag("-v"), "-v")

    def test_unpack_short_flags(self) -> None:
        self.assertEqual(unpack_short_flags("-rf"), ["-r", "-f"])
        self.assertEqual(unpack_short_flags("-la"), ["-l", "-a"])
        self.assertEqual(unpack_short_flags("-v"), ["-v"])
        self.assertEqual(unpack_short_flags("--force"), ["--force"])

    def test_extract_flags_from_tokens(self) -> None:
        tokens = ["git", "commit", "-m", "- bullet item", "--amend", "-s"]
        flags = extract_flags_from_tokens(tokens)
        self.assertIn("--amend", flags)
        self.assertIn("-s", flags)
        self.assertNotIn("- bullet item", flags)

    def test_extract_executable_and_subcommand(self) -> None:
        tokens = ["git", "-C", "/path/to/repo", "commit", "-m", "message"]
        tool, subcmd, remaining = extract_executable_and_subcommand(tokens)
        self.assertEqual(tool, "git")
        self.assertEqual(subcmd, "commit")
        self.assertIn("-C", remaining)
        self.assertIn("-m", remaining)

    def test_analyze_tool_flags(self) -> None:
        history = [
            'git -C /tmp commit -m "first" --amend',
            'git commit -m "second" -s && echo done',
            'docker build -t app . || git commit -m "third" --amend',
            'ls -la',
        ]

        result = analyze_tool_flags(history, target_tool="git", target_subcommand="commit")
        self.assertEqual(result.total_invocations, 3)
        self.assertEqual(result.tool, "git")
        self.assertEqual(result.subcommand, "commit")

        stats_dict = {item.flag: (item.count, item.percentage) for item in result.flag_stats}
        self.assertIn("--amend", stats_dict)
        self.assertEqual(stats_dict["--amend"], (2, 66.7))
        self.assertIn("-s", stats_dict)
        self.assertEqual(stats_dict["-s"], (1, 33.3))
        self.assertIn("-m", stats_dict)
        self.assertEqual(stats_dict["-m"], (3, 100.0))


if __name__ == "__main__":
    unittest.main()
