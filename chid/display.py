"""Rich-powered terminal formatting and visual display tables for CHID."""

from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from chid.models import CommandRecord, FlagAnalysisResult, FrequencyStat


def format_duration(duration_ms: int | None) -> str:
    """Format millisecond duration into human-readable representation."""
    if duration_ms is None or duration_ms < 0:
        return ""
    if duration_ms < 1000:
        return f"{duration_ms}ms"
    if duration_ms < 60000:
        return f"{duration_ms / 1000:.1f}s"
    mins = duration_ms // 60000
    secs = (duration_ms % 60000) / 1000
    return f"{mins}m {secs:.0f}s"


def format_status_icon(exit_code: int | None) -> str:
    """Format exit code with semantic categorization badges."""
    if exit_code is None:
        return "[dim]…[/dim]"
    if exit_code == 0:
        return "[bold green]✔[/bold green]"
    if exit_code == 127:
        return "[bold magenta]✘ NotFound[/bold magenta]"
    if exit_code in (2, 64):
        return "[bold yellow]✘ BadArgs[/bold yellow]"
    if exit_code == 126:
        return "[bold red]✘ PermDenied[/bold red]"
    if exit_code == 130:
        return "[dim cyan]✘ Cancelled[/dim cyan]"
    if exit_code == 137:
        return "[bold red]✘ Killed[/bold red]"
    return f"[bold red]✘ {exit_code}[/bold red]"


def format_relative_time(timestamp_ms: int) -> str:
    """Format Unix millisecond timestamp to concise relative time string."""
    diff_sec = max(0, int(time.time()) - (timestamp_ms // 1000))
    if diff_sec < 60:
        return f"{diff_sec}s ago"
    if diff_sec < 3600:
        return f"{diff_sec // 60}m ago"
    if diff_sec < 86400:
        return f"{diff_sec // 3600}h ago"
    if diff_sec < 604800:
        return f"{diff_sec // 86400}d ago"
    return f"{diff_sec // 604800}w ago"


def format_directory_display(dir_path: str, cwd: str | None = None) -> str:
    """Format directory path compactly (relative to cwd or home)."""
    if cwd and dir_path == cwd:
        return "."
    if cwd and dir_path.startswith(cwd + "/"):
        return "./" + dir_path[len(cwd) + 1:]
    home = str(Path.home())
    if dir_path == home:
        return "~"
    if dir_path.startswith(home + "/"):
        return "~/" + dir_path[len(home) + 1:]
    return dir_path


def render_history_table(
    entries: list[FrequencyStat] | list[CommandRecord],
    mode: str,
    title: str = "",
    console: Console | None = None,
    show_dir: bool = False,
    cwd: str | None = None,
) -> None:
    """Render command history entries in a compact Rich table."""
    c = console or Console()
    if not entries:
        c.print("[dim]No matching command history found.[/dim]")
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        title=f"[bold cyan]{title}[/bold cyan]" if title else None,
        title_justify="left",
        pad_edge=False,
        show_edge=True,
    )

    table.add_column("#", style="bold cyan", justify="right", no_wrap=True)

    if mode == "freq":
        table.add_column("Count", justify="right", style="magenta", no_wrap=True)
        table.add_column("%", justify="right", style="green", no_wrap=True)
        table.add_column("Last Run", justify="right", style="dim", no_wrap=True)
        table.add_column("Command", style="white", ratio=1)

        for i, stat in enumerate(entries, 1):  # type: ignore[arg-type]
            table.add_row(
                str(i),
                str(stat.count),
                f"{stat.percentage:.1f}%",
                format_relative_time(stat.last_run_timestamp),
                stat.command,
            )
    else:
        table.add_column("Status", justify="center", no_wrap=True)
        table.add_column("Duration", justify="right", style="yellow", no_wrap=True)
        table.add_column("Time", justify="right", style="dim", no_wrap=True)
        if show_dir:
            table.add_column("Directory", style="blue", no_wrap=True)
        table.add_column("Command", style="white", ratio=1)

        for i, rec in enumerate(entries, 1):  # type: ignore[arg-type]
            row = [
                str(i),
                format_status_icon(rec.exit_code),
                format_duration(rec.duration_ms),
                format_relative_time(rec.timestamp),
            ]
            if show_dir:
                row.append(format_directory_display(rec.directory, cwd))
            row.append(rec.command)
            table.add_row(*row)

    c.print(table)


def render_flag_analysis(
    analysis: FlagAnalysisResult,
    console: Console | None = None,
) -> None:
    """Render flag usage metrics and top common invocations for a tool."""
    c = console or Console()

    header = f"Flag Analysis: [bold green]{analysis.tool}[/bold green]"
    if analysis.subcommand:
        header += f" [bold yellow]{analysis.subcommand}[/bold yellow]"
    header += f" ({analysis.total_invocations} invocations)"

    if analysis.total_invocations == 0:
        c.print(f"[dim]No history found for tool '{analysis.tool}'.[/dim]")
        return

    c.print(f"[bold cyan]{header}[/bold cyan]\n")

    if analysis.flag_stats:
        flag_table = Table(
            box=box.SIMPLE_HEAVY,
            title="[bold]Options & Flags[/bold]",
            title_justify="left",
            pad_edge=False,
            show_edge=True,
        )
        flag_table.add_column("Flag", style="bold yellow", no_wrap=True)
        flag_table.add_column("Count", justify="right", style="magenta", no_wrap=True)
        flag_table.add_column("%", justify="right", style="green", no_wrap=True)

        for stat in analysis.flag_stats:
            flag_table.add_row(
                stat.flag,
                str(stat.count),
                f"{stat.percentage:.1f}%",
            )
        c.print(flag_table)
    else:
        c.print("[dim]No flags recorded for this tool.[/dim]")

    if analysis.common_invocations:
        c.print()
        inv_table = Table(
            box=box.SIMPLE_HEAVY,
            title="[bold]Top Command Patterns[/bold]",
            title_justify="left",
            pad_edge=False,
            show_edge=True,
        )
        inv_table.add_column("Count", justify="right", style="magenta", no_wrap=True)
        inv_table.add_column("Command", style="white", ratio=1)

        for cmd, count in analysis.common_invocations:
            inv_table.add_row(str(count), cmd)

        c.print(inv_table)
