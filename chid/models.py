"""Data models for CHID history records, query statistics, and flag analysis."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandRecord:
    """Represents a recorded command execution event."""

    directory: str
    command: str
    timestamp: int  # Unix epoch milliseconds
    id: int | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    session_id: str = ""
    git_root: str | None = None


@dataclass(frozen=True, slots=True)
class FrequencyStat:
    """Aggregated execution metrics for a specific command."""

    command: str
    count: int
    percentage: float
    last_run_timestamp: int


@dataclass(frozen=True, slots=True)
class FlagStat:
    """Frequency and percentage metrics for a specific command flag."""

    flag: str
    count: int
    percentage: float


@dataclass(frozen=True, slots=True)
class FlagAnalysisResult:
    """Aggregated flag and pattern analysis for a tool or subcommand."""

    tool: str
    subcommand: str | None
    total_invocations: int
    flag_stats: list[FlagStat]
    common_invocations: list[tuple[str, int]]
