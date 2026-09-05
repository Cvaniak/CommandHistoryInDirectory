"""CHID command-line interface entry point and dispatcher."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import chid
from chid.db import get_connection, initialize_schema
from chid.recorder import record_command_finish, record_command_start
from chid.replace import resolve_buffer_replacement, write_session_cache
from chid.utils import find_git_root

INIT_TEMPLATES = {
    "zsh": """# CHID Zsh Plugin Integration
autoload -Uz add-zsh-hook

typeset -g _CHID_LAST_CMD=""
export CHID_SESSION="${CHID_SESSION:-$$}"

_chid_preexec() {
    _CHID_LAST_CMD="$1"
    command chid record-start "$PWD" "$CHID_SESSION" "$1" &>/dev/null &!
}

_chid_precmd() {
    local exit_code=$?
    if [[ -n "$_CHID_LAST_CMD" ]]; then
        command chid record-finish "$CHID_SESSION" "$exit_code" &>/dev/null &!
        _CHID_LAST_CMD=""
    fi
}

_chid_accept_line() {
    local replaced
    replaced=$(command chid replace "$CHID_SESSION" "$BUFFER")
    if [[ -n "$replaced" && "$replaced" != "$BUFFER" ]]; then
        BUFFER="$replaced"
        CURSOR=$#BUFFER
    fi
    zle .accept-line
}

zle -N accept-line _chid_accept_line
add-zsh-hook preexec _chid_preexec
add-zsh-hook precmd _chid_precmd
""",
    "bash": """# CHID Bash Plugin Integration
export CHID_SESSION="${CHID_SESSION:-$$}"
_CHID_LAST_CMD=""

_chid_preexec() {
    _CHID_LAST_CMD="$1"
    command chid record-start "$PWD" "$CHID_SESSION" "$1" &>/dev/null &
}

_chid_prompt_command() {
    local exit_code=$?
    if [ -n "$_CHID_LAST_CMD" ]; then
        command chid record-finish "$CHID_SESSION" "$exit_code" &>/dev/null &
        _CHID_LAST_CMD=""
    fi
}

PROMPT_COMMAND="_chid_prompt_command${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
""",
    "fish": """# CHID Fish Plugin Integration
set -gx CHID_SESSION (string default %self $CHID_SESSION)
set -g _chid_last_cmd ""

function _chid_preexec --on-event fish_preexec
    set -g _chid_last_cmd $argv[1]
    command chid record-start $PWD $CHID_SESSION $argv[1] &>/dev/null &
    disown
end

function _chid_postexec --on-event fish_postexec
    set -l exit_code $status
    if test -n "$_chid_last_cmd"
        command chid record-finish $CHID_SESSION $exit_code &>/dev/null &
        disown
        set -g _chid_last_cmd ""
    end
end
""",
}


def _get_active_session_id() -> str:
    """Resolve session ID from environment or parent PID."""
    return os.environ.get("CHID_SESSION") or str(os.getppid())


def _handle_record_start(args: list[str]) -> None:
    """Fast-path handler for pre-execution recording."""
    alias: str | None = None
    clean_args: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("--alias", "-a") and i + 1 < len(args):
            alias = args[i + 1]
            i += 2
        else:
            clean_args.append(args[i])
            i += 1

    if len(clean_args) < 3:
        return

    directory = clean_args[0]
    session_id = clean_args[1]
    command = " ".join(clean_args[2:])
    record_command_start(directory=directory, command=command, session_id=session_id, alias=alias)


def _handle_record_finish(args: list[str]) -> None:
    """Fast-path handler for command completion recording."""
    if len(args) < 2:
        return
    session_id = args[0]
    try:
        exit_code = int(args[1])
    except ValueError:
        exit_code = 0
    record_command_finish(session_id=session_id, exit_code=exit_code)


def _handle_replace(args: list[str]) -> None:
    """Fast-path handler for interactive buffer replacement."""
    alias: str | None = None
    clean_args: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("--alias", "-a") and i + 1 < len(args):
            alias = args[i + 1]
            i += 2
        else:
            clean_args.append(args[i])
            i += 1

    if len(clean_args) < 2:
        if clean_args:
            sys.stdout.write(" ".join(clean_args))
        return

    session_id = clean_args[0]
    buffer_text = " ".join(clean_args[1:])
    replacement = resolve_buffer_replacement(session_id=session_id, buffer_text=buffer_text, alias=alias)
    sys.stdout.write(replacement)


def _handle_init(args: list[str]) -> None:
    """Print shell hook integration script."""
    shell = args[0].lower() if args else "zsh"
    plugin_path = Path(__file__).parent / "plugins" / f"chid.{shell}"
    if plugin_path.is_file():
        print(plugin_path.read_text(encoding="utf-8").strip())
        return

    template = INIT_TEMPLATES.get(shell)
    if template:
        print(template.strip())
    else:
        sys.stderr.write(f"Unknown shell '{shell}'. Supported shells: zsh, bash, fish\n")
        sys.exit(1)


def _run_query_cli(argv: list[str]) -> None:
    """Handle interactive user queries and history inspection."""
    parser = argparse.ArgumentParser(
        prog="chid",
        description="Command History In Directory - Recency, frequency, and flag analysis.",
    )
    parser.add_argument("--version", "-V", action="version", version=f"chid {chid.__version__}")
    parser.add_argument(
        "-r",
        "--recent",
        action="store_true",
        help="Display command history sorted by recency (last executed first).",
    )
    parser.add_argument(
        "-f",
        "--freq",
        action="store_true",
        help="Display command history sorted by frequency (default).",
    )
    parser.add_argument(
        "--first",
        action="store_true",
        help="Display command history sorted by earliest execution first.",
    )
    parser.add_argument(
        "-n",
        "-l",
        "--limit",
        type=int,
        default=20,
        help="Maximum number of history records to display (default: 20).",
    )
    parser.add_argument(
        "-s",
        "-q",
        "--search",
        type=str,
        default="",
        help="Filter command history by keyword substring.",
    )
    parser.add_argument(
        "-R",
        "--repo",
        action="store_true",
        help="Scope search to the current Git repository root instead of the current directory.",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Include all commands, including typos and bad parameters (filtered out by default).",
    )
    parser.add_argument(
        "--invalid",
        "--bad",
        action="store_true",
        help="Display only commands that were incorrect (e.g. typos, command not found) or had invalid parameters.",
    )
    parser.add_argument(
        "-F",
        "--flags",
        nargs="+",
        metavar="TOOL",
        help="Analyze flag and subcommand usage for the specified tool (e.g. --flags git commit).",
    )
    parser.add_argument(
        "--success",
        action="store_true",
        help="Filter for successful commands (exit code 0).",
    )
    parser.add_argument(
        "--failed",
        action="store_true",
        help="Filter for failed commands (non-zero exit code).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all command history for the current directory.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw command lines without formatting or tables (one per line).",
    )
    parser.add_argument(
        "index",
        nargs="?",
        type=int,
        help="Optional index from last display to resolve directly.",
    )

    args = parser.parse_args(argv)

    session_id = _get_active_session_id()
    cwd = str(Path.cwd().resolve())
    git_root_path = find_git_root(cwd)
    git_root = str(git_root_path) if (args.repo and git_root_path) else None

    # Handle direct positional index request e.g. `chid 2`
    if args.index is not None:
        replaced = resolve_buffer_replacement(session_id, f"chid {args.index}")
        print(replaced)
        return

    conn = get_connection()
    initialize_schema(conn)

    from chid.queries import (
        delete_directory_history,
        query_first,
        query_frequency,
        query_recent,
    )

    if args.clear:
        deleted = delete_directory_history(conn, cwd)
        print(f"Cleared {deleted} history records for {cwd}.")
        conn.close()
        return

    from chid.display import render_flag_analysis, render_history_table

    if args.flags:
        target_tool = args.flags[0]
        target_subcommand = args.flags[1] if len(args.flags) > 1 else None

        # Fetch recent commands to analyze flags
        all_records = query_recent(
            conn,
            directory=cwd,
            limit=1000,
            git_root=git_root,
            include_invalid=args.all,
        )
        conn.close()

        from chid.parser import analyze_tool_flags

        cmd_lines = [rec.command for rec in all_records]
        analysis = analyze_tool_flags(cmd_lines, target_tool, target_subcommand)
        render_flag_analysis(analysis)
        return

    # Determine display mode
    if args.invalid or args.recent or args.success or args.failed:
        mode = "recent"
        records = query_recent(
            conn,
            directory=cwd,
            limit=args.limit,
            search=args.search,
            git_root=git_root,
            success_only=args.success,
            failed_only=args.failed,
            include_invalid=args.all,
            only_invalid=args.invalid,
        )
        commands = [r.command for r in records]
        title_scope = f"Repo: {git_root}" if git_root else f"Dir: {cwd}"
        if args.invalid:
            title = f"Invalid Commands & Parameter Errors ({title_scope})"
        else:
            title = f"Recent Commands ({title_scope})"
        entries = records
    elif args.first:
        mode = "first"
        records = query_first(
            conn,
            directory=cwd,
            limit=args.limit,
            search=args.search,
            git_root=git_root,
            include_invalid=args.all,
            only_invalid=args.invalid,
        )
        commands = [r.command for r in records]
        title_scope = f"Repo: {git_root}" if git_root else f"Dir: {cwd}"
        title = f"Chronological Commands ({title_scope})"
        entries = records
    else:
        # Default: frequency mode
        mode = "freq"
        freq_stats = query_frequency(
            conn,
            directory=cwd,
            limit=args.limit,
            search=args.search,
            git_root=git_root,
            include_invalid=args.all,
            only_invalid=args.invalid,
        )
        commands = [s.command for s in freq_stats]
        title_scope = f"Repo: {git_root}" if git_root else f"Dir: {cwd}"
        title = f"Frequent Commands ({title_scope})"
        entries = freq_stats

    conn.close()

    # Cache displayed commands for session buffer replacement
    if commands:
        write_session_cache(session_id, commands)

    if args.raw:
        for cmd in commands:
            print(cmd)
    else:
        render_history_table(entries, mode=mode, title=title)


def main() -> None:
    """Main CLI dispatcher routing between fast shell hooks and interactive display."""
    if len(sys.argv) > 1:
        hook_cmd = sys.argv[1]
        if hook_cmd in ("--version", "-V"):
            print(f"chid {chid.__version__}")
            return
        elif hook_cmd == "record-start":
            _handle_record_start(sys.argv[2:])
            return
        elif hook_cmd == "record-finish":
            _handle_record_finish(sys.argv[2:])
            return
        elif hook_cmd == "replace":
            _handle_replace(sys.argv[2:])
            return
        elif hook_cmd == "init":
            _handle_init(sys.argv[2:])
            return

    _run_query_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
