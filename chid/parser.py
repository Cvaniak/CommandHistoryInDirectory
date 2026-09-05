"""Shell pipeline parsing, tokenization, and command flag analysis."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import shlex

from chid.models import FlagAnalysisResult, FlagStat

FLAG_REGEX = re.compile(r"^--?[a-zA-Z0-9][-a-zA-Z0-9]*(=.*)?$")
ENV_VAR_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

KNOWN_WRAPPERS = {
    "sudo",
    "nohup",
    "time",
    "xargs",
    "env",
    "nice",
    "doas",
    "builtin",
    "command",
}

KNOWN_OPTION_ARGUMENTS = {
    "-m",
    "-C",
    "-c",
    "-o",
    "-f",
    "-i",
    "-u",
    "-p",
    "-t",
    "-e",
    "--message",
    "--file",
    "--output",
    "--user",
    "--host",
    "--config",
    "--directory",
    "--work-tree",
    "--git-dir",
    "--context",
}


def safe_shlex_split(s: str) -> list[str]:
    """Split command string into tokens using shlex, falling back safely on syntax errors."""
    try:
        return shlex.split(s)
    except ValueError:
        # Try closing open quotes before failing
        for quote in ('"', "'"):
            try:
                return shlex.split(s + quote)
            except ValueError:
                pass
        return s.strip().split()


def split_command_segments(command_line: str) -> list[str]:
    """Split a compound command pipeline into individual command segments while respecting quotes."""
    s = command_line.strip()
    if not s:
        return []

    segments: list[str] = []
    current: list[str] = []
    i = 0
    n = len(s)
    in_single = False
    in_double = False
    escaped = False

    while i < n:
        char = s[i]
        if escaped:
            current.append(char)
            escaped = False
            i += 1
            continue

        if char == "\\":
            current.append(char)
            escaped = True
            i += 1
            continue

        if char == "'" and not in_double:
            in_single = not in_single
            current.append(char)
            i += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            current.append(char)
            i += 1
            continue

        if not in_single and not in_double:
            if s[i : i + 2] in ("&&", "||"):
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                i += 2
                continue
            elif char in ("|", ";", "&"):
                seg = "".join(current).strip()
                if seg:
                    segments.append(seg)
                current = []
                i += 1
                continue

        current.append(char)
        i += 1

    seg = "".join(current).strip()
    if seg:
        segments.append(seg)
    return segments


def is_env_assignment(token: str) -> bool:
    """Return True if token matches shell variable assignment syntax (e.g. FOO=bar)."""
    return bool(ENV_VAR_REGEX.match(token))


def strip_wrappers_and_env(tokens: list[str]) -> list[str]:
    """Strip leading environment variable assignments and command execution wrappers."""
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if is_env_assignment(token):
            idx += 1
            continue

        base_tool = Path(token).name
        if base_tool in KNOWN_WRAPPERS:
            idx += 1
            # Skip options for wrappers like sudo or env
            while idx < len(tokens) and tokens[idx].startswith("-"):
                # If wrapper option takes an argument (e.g. -u user)
                if tokens[idx] in {"-u", "-g", "-C", "-i"}:
                    idx += 2
                else:
                    idx += 1
            continue

        break

    return tokens[idx:]


def is_flag(token: str) -> bool:
    """Return True if token is formatted as a valid command line flag."""
    return bool(FLAG_REGEX.match(token))


def normalize_flag(token: str) -> str:
    """Extract base flag name by stripping inline values (e.g. --output=json -> --output)."""
    if "=" in token:
        return token.split("=", 1)[0]
    return token


def unpack_short_flags(token: str) -> list[str]:
    """Unpack combined short flags (e.g. -rf -> ['-r', '-f'])."""
    if token.startswith("-") and not token.startswith("--") and "=" not in token:
        flag_chars = token[1:]
        if len(flag_chars) > 1 and flag_chars.isalnum():
            return [f"-{c}" for c in flag_chars]
    return [token]


def extract_flags_from_tokens(tokens: list[str]) -> list[str]:
    """Extract and normalize all flags from a list of command tokens."""
    flags: list[str] = []
    skip_next = False

    for tok in tokens:
        if skip_next:
            skip_next = False
            continue

        if is_flag(tok):
            norm = normalize_flag(tok)
            if tok.startswith("-") and not tok.startswith("--") and "=" not in tok and len(tok) > 2 and tok[1:].isalnum():
                flags.extend(unpack_short_flags(tok))
            else:
                flags.append(norm)

            if norm in KNOWN_OPTION_ARGUMENTS and "=" not in tok:
                skip_next = True
        else:
            skip_next = False

    return flags


def extract_executable_and_subcommand(
    tokens: list[str],
) -> tuple[str, str | None, list[str]]:
    """Identify tool executable, optional subcommand, and argument tokens."""
    cleaned = strip_wrappers_and_env(tokens)
    if not cleaned:
        return "", None, []

    tool = Path(cleaned[0]).name
    remaining = cleaned[1:]

    # Search for subcommand while skipping global flags
    subcommand: str | None = None
    subcommand_idx: int | None = None
    skip_next = False

    for i, tok in enumerate(remaining):
        if skip_next:
            skip_next = False
            continue

        if is_flag(tok):
            norm = normalize_flag(tok)
            if norm in KNOWN_OPTION_ARGUMENTS and "=" not in tok:
                skip_next = True
            continue

        # Found the first non-flag positional argument
        subcommand = tok
        subcommand_idx = i
        break

    if subcommand_idx is not None:
        args_and_flags = remaining[:subcommand_idx] + remaining[subcommand_idx + 1 :]
    else:
        args_and_flags = remaining

    return tool, subcommand, args_and_flags


def analyze_tool_flags(
    command_lines: list[str],
    target_tool: str,
    target_subcommand: str | None = None,
) -> FlagAnalysisResult:
    """Analyze command history entries for flag usage and common invocations of a target tool."""
    target_tool = target_tool.strip().lower()
    if target_subcommand:
        target_subcommand = target_subcommand.strip().lower()

    total_invocations = 0
    flag_counter: Counter[str] = Counter()
    invocations_counter: Counter[str] = Counter()

    for cmd_line in command_lines:
        segments = split_command_segments(cmd_line)
        for segment in segments:
            tokens = safe_shlex_split(segment)
            if not tokens:
                continue

            tool, subcommand, remaining = extract_executable_and_subcommand(tokens)
            if tool.lower() != target_tool:
                continue

            if target_subcommand and (subcommand is None or subcommand.lower() != target_subcommand):
                continue

            total_invocations += 1
            invocations_counter[segment.strip()] += 1

            flags = extract_flags_from_tokens(remaining)
            for flag in set(flags):
                flag_counter[flag] += 1

    flag_stats: list[FlagStat] = []
    if total_invocations > 0:
        for flag, count in flag_counter.most_common():
            pct = round((count / total_invocations) * 100.0, 1)
            flag_stats.append(FlagStat(flag=flag, count=count, percentage=pct))

    common_invocations = invocations_counter.most_common(10)

    return FlagAnalysisResult(
        tool=target_tool,
        subcommand=target_subcommand,
        total_invocations=total_invocations,
        flag_stats=flag_stats,
        common_invocations=common_invocations,
    )
