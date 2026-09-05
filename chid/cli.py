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
    scope_group = parser.add_argument_group("Scope & Directory Hierarchy")
    scope_group.add_argument(
        "-R",
        "--repo",
        action="store_true",
        help="Scope search to the current Git repository root instead of the current directory.",
    )
    scope_group.add_argument(
        "-g",
        "--global",
        dest="global_scope",
        action="store_true",
        help="Search command history globally across all directories.",
    )
    scope_group.add_argument(
        "-d",
        "--dir",
        type=str,
        metavar="PATH",
        help="Target a specific directory instead of the current working directory.",
    )
    scope_group.add_argument(
        "-u",
        "--up",
        "--parent",
        nargs="?",
        const=1,
        type=int,
        metavar="N",
        help="Target N directory levels up from the current directory (default: 1).",
    )
    scope_group.add_argument(
        "-t",
        "--tree",
        "--recursive",
        action="store_true",
        help="Recursively include history from all child subdirectories of the target directory.",
    )
    scope_group.add_argument(
        "--depth",
        "--level",
        type=int,
        metavar="N",
        help="Maximum subdirectory depth when searching recursively with --tree (default: unlimited).",
    )
    scope_group.add_argument(
        "-S",
        "--this-session",
        action="store_true",
        help="Filter commands executed strictly in the current shell session.",
    )
    scope_group.add_argument(
        "--show-dir",
        dest="show_dir",
        action="store_true",
        default=None,
        help="Display directory column in history table.",
    )
    scope_group.add_argument(
        "--no-dir",
        dest="show_dir",
        action="store_false",
        help="Hide directory column in history table.",
    )
    time_group = parser.add_argument_group("Time Filters")
    time_group.add_argument(
        "--since",
        "--after",
        type=str,
        metavar="TIME",
        help="Show commands executed after given time (e.g. 30m, 2h, 1d, 2026-09-01, 14:00).",
    )
    time_group.add_argument(
        "--until",
        "--before",
        type=str,
        metavar="TIME",
        help="Show commands executed before given time.",
    )
    time_group.add_argument(
        "--last",
        type=str,
        metavar="DURATION",
        help="Show commands from the last duration (e.g. 15m, 2h, 1d).",
    )
    time_group.add_argument(
        "--today",
        action="store_true",
        help="Show commands executed today.",
    )
    time_group.add_argument(
        "--yesterday",
        action="store_true",
        help="Show commands executed yesterday.",
    )
    time_group.add_argument(
        "--range",
        type=str,
        metavar="START..END",
        help="Show commands within a time range (e.g. '2026-09-01..2026-09-05' or '2h..30m').",
    )
    parser.add_argument(
        "index",
        nargs="?",
        type=int,
        help="Optional index from last display to resolve directly.",
    )

    args = parser.parse_args(argv)

    # Scope validation
    if args.global_scope and (args.dir or args.up is not None or args.tree or args.repo):
        parser.error("Cannot combine --global with directory scope flags (--dir, --up, --tree, --repo).")

    if args.depth is not None:
        if not args.tree:
            parser.error("--depth/--level requires --tree/--recursive to be enabled.")
        if args.depth < 1:
            parser.error("--depth/--level must be at least 1.")

    if args.up is not None and args.up < 1:
        parser.error("--up/--parent level must be at least 1.")

    from chid.time_utils import resolve_time_filters

    try:
        since_ms, until_ms, time_label = resolve_time_filters(
            since=args.since,
            until=args.until,
            last=args.last,
            today=args.today,
            yesterday=args.yesterday,
            range_str=args.range,
        )
    except ValueError as e:
        parser.error(str(e))

    session_id = _get_active_session_id()
    target_session = session_id if args.this_session else None
    cwd = str(Path.cwd().resolve())

    # Resolve target directory
    if args.dir:
        target_path = Path(args.dir).expanduser().resolve()
    else:
        target_path = Path(cwd)

    if args.up is not None:
        target_path = target_path.parents[min(args.up - 1, len(target_path.parents) - 1)]

    target_dir = str(target_path)
    git_root_path = find_git_root(target_dir) if args.repo else None
    git_root = str(git_root_path) if git_root_path else None

    if args.show_dir is not None:
        show_dir = args.show_dir
    else:
        show_dir = bool(args.global_scope or args.tree or (args.repo and git_root))

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
        deleted = delete_directory_history(
            conn,
            target_dir,
            recursive=args.tree,
            is_global=args.global_scope,
        )
        if args.global_scope:
            print(f"Cleared {deleted} history records globally.")
        elif args.tree:
            print(f"Cleared {deleted} history records for tree {target_dir}/**.")
        else:
            print(f"Cleared {deleted} history records for {target_dir}.")
        conn.close()
        return

    from chid.display import render_flag_analysis, render_history_table

    if args.flags:
        target_tool = args.flags[0]
        target_subcommand = args.flags[1] if len(args.flags) > 1 else None

        # Fetch recent commands to analyze flags
        all_records = query_recent(
            conn,
            directory=target_dir,
            limit=1000,
            git_root=git_root,
            include_invalid=args.all,
            since_ms=since_ms,
            until_ms=until_ms,
            is_global=args.global_scope,
            recursive=args.tree,
            max_depth=args.depth,
            session_id=target_session,
        )
        conn.close()

        from chid.parser import analyze_tool_flags

        cmd_lines = [rec.command for rec in all_records]
        analysis = analyze_tool_flags(cmd_lines, target_tool, target_subcommand)
        render_flag_analysis(analysis)
        return

    if args.global_scope:
        scope_desc = "Global (All Directories)"
    elif git_root:
        scope_desc = f"Repo: {git_root}"
    elif args.tree:
        if args.depth:
            scope_desc = f"Tree: {target_dir}/** (depth {args.depth})"
        else:
            scope_desc = f"Tree: {target_dir}/**"
    else:
        scope_desc = f"Dir: {target_dir}"

    if args.this_session:
        scope_desc += f", session: {session_id[:8]}"

    scope_str = f"{scope_desc}, {time_label}" if time_label else scope_desc

    # Determine display mode
    if args.invalid or args.recent or args.success or args.failed:
        mode = "recent"
        records = query_recent(
            conn,
            directory=target_dir,
            limit=args.limit,
            search=args.search,
            git_root=git_root,
            success_only=args.success,
            failed_only=args.failed,
            include_invalid=args.all,
            only_invalid=args.invalid,
            since_ms=since_ms,
            until_ms=until_ms,
            is_global=args.global_scope,
            recursive=args.tree,
            max_depth=args.depth,
            session_id=target_session,
        )
        commands = [r.command for r in records]
        if args.invalid:
            title = f"Invalid Commands & Parameter Errors ({scope_str})"
        else:
            title = f"Recent Commands ({scope_str})"
        entries = records
    elif args.first:
        mode = "first"
        records = query_first(
            conn,
            directory=target_dir,
            limit=args.limit,
            search=args.search,
            git_root=git_root,
            include_invalid=args.all,
            only_invalid=args.invalid,
            since_ms=since_ms,
            until_ms=until_ms,
            is_global=args.global_scope,
            recursive=args.tree,
            max_depth=args.depth,
            session_id=target_session,
        )
        commands = [r.command for r in records]
        title = f"Chronological Commands ({scope_str})"
        entries = records
    else:
        # Default: frequency mode
        mode = "freq"
        freq_stats = query_frequency(
            conn,
            directory=target_dir,
            limit=args.limit,
            search=args.search,
            git_root=git_root,
            include_invalid=args.all,
            only_invalid=args.invalid,
            since_ms=since_ms,
            until_ms=until_ms,
            is_global=args.global_scope,
            recursive=args.tree,
            max_depth=args.depth,
            session_id=target_session,
        )
        commands = [s.command for s in freq_stats]
        title = f"Frequent Commands ({scope_str})"
        entries = freq_stats

    conn.close()

    # Cache displayed commands for session buffer replacement
    if commands:
        write_session_cache(session_id, commands)

    if args.raw:
        for cmd in commands:
            print(cmd)
    else:
        render_history_table(entries, mode=mode, title=title, show_dir=show_dir, cwd=cwd)


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
