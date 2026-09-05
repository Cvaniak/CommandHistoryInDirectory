"""Time parsing and duration boundary calculation for CHID history queries."""

from __future__ import annotations

import datetime
import re
import time

RELATIVE_DURATION_REGEX = re.compile(
    r"^(\d+)\s*(s|sec|seconds?|m|min|minutes?|h|hr|hours?|d|days?|w|weeks?)$",
    re.IGNORECASE,
)


def parse_time_boundary(val: str, is_end: bool = False) -> int:
    """Parse a human relative string, special keyword, or date format into epoch milliseconds."""
    v = val.strip().lower()
    now_ms = int(time.time() * 1000)

    # Relative duration backwards from now (e.g. 30m, 2h, 1d)
    rel_match = RELATIVE_DURATION_REGEX.match(v)
    if rel_match:
        count = int(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if unit.startswith("s"):
            sec = count
        elif unit.startswith("m"):
            sec = count * 60
        elif unit.startswith("h"):
            sec = count * 3600
        elif unit.startswith("d"):
            sec = count * 86400
        elif unit.startswith("w"):
            sec = count * 7 * 86400
        else:
            raise ValueError(f"Unknown time unit in '{val}'")
        return now_ms - (sec * 1000)

    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if v == "now":
        return now_ms
    elif v == "today":
        if is_end:
            dt = today_start.replace(hour=23, minute=59, second=59, microsecond=999000)
        else:
            dt = today_start
        return int(dt.timestamp() * 1000)
    elif v == "yesterday":
        yest_start = today_start - datetime.timedelta(days=1)
        if is_end:
            dt = today_start - datetime.timedelta(milliseconds=1)
        else:
            dt = yest_start
        return int(dt.timestamp() * 1000)

    # Standard ISO formats: YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS]
    try:
        if len(v) == 10 and "-" in v:
            d = datetime.date.fromisoformat(v)
            if is_end:
                dt = datetime.datetime.combine(d, datetime.time.max)
            else:
                dt = datetime.datetime.combine(d, datetime.time.min)
            return int(dt.timestamp() * 1000)

        # Allow simple HH:MM time today
        if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", v):
            t_parts = [int(p) for p in v.split(":")]
            h = t_parts[0]
            m = t_parts[1]
            if len(t_parts) > 2:
                s = t_parts[2]
                us = 999000 if is_end else 0
            else:
                s = 59 if is_end else 0
                us = 999000 if is_end else 0
            dt = today_start.replace(hour=h, minute=m, second=s, microsecond=us)
            return int(dt.timestamp() * 1000)

        dt = datetime.datetime.fromisoformat(v)
        if is_end and len(v) <= 16 and dt.second == 0 and dt.microsecond == 0:
            dt = dt.replace(second=59, microsecond=999000)
        return int(dt.timestamp() * 1000)
    except Exception as e:
        raise ValueError(
            f"Invalid time format '{val}'. Supported formats: '30m', '2h', '1d', 'today', 'yesterday', 'YYYY-MM-DD', 'HH:MM'"
        ) from e


def parse_time_range(val: str) -> tuple[int, int]:
    """Parse a range expression 'START..END' into (since_ms, until_ms)."""
    if ".." not in val:
        raise ValueError("Range must be in the format 'START..END' (e.g. '2026-09-01..2026-09-05' or '2h..30m')")

    parts = val.split("..", 1)
    start_str = parts[0].strip()
    end_str = parts[1].strip()

    start_ms = parse_time_boundary(start_str, is_end=False)
    end_ms = parse_time_boundary(end_str, is_end=True)

    if start_ms > end_ms:
        # In relative durations, e.g. "2h..30m": 2h ago is smaller epoch ms than 30m ago.
        # But if someone wrote "30m..2h", swap them to ensure start <= end.
        start_ms, end_ms = end_ms, start_ms

    return start_ms, end_ms


def get_today_range() -> tuple[int, int]:
    """Return epoch milliseconds for start and end of today."""
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999000)
    return int(today_start.timestamp() * 1000), int(today_end.timestamp() * 1000)


def get_yesterday_range() -> tuple[int, int]:
    """Return epoch milliseconds for start and end of yesterday."""
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yest_start = today_start - datetime.timedelta(days=1)
    yest_end = today_start - datetime.timedelta(milliseconds=1)
    return int(yest_start.timestamp() * 1000), int(yest_end.timestamp() * 1000)


def resolve_time_filters(
    since: str | None = None,
    until: str | None = None,
    last: str | None = None,
    today: bool = False,
    yesterday: bool = False,
    range_str: str | None = None,
) -> tuple[int | None, int | None, str | None]:
    """Validate and resolve time filter combinations into (since_ms, until_ms, label)."""
    preset_count = sum([bool(today), bool(yesterday), bool(range_str), bool(last)])
    if preset_count > 1:
        raise ValueError(
            "Conflicting time filters: specify only one of --today, --yesterday, --last, or --range."
        )
    if preset_count == 1 and (since is not None or until is not None):
        raise ValueError(
            "Cannot combine preset time filters (--today, --yesterday, --last, --range) with --since/--until."
        )

    if today:
        since_ms, until_ms = get_today_range()
        return since_ms, until_ms, "today"
    if yesterday:
        since_ms, until_ms = get_yesterday_range()
        return since_ms, until_ms, "yesterday"
    if range_str:
        since_ms, until_ms = parse_time_range(range_str)
        return since_ms, until_ms, f"range {range_str}"
    if last:
        since_ms = parse_time_boundary(last, is_end=False)
        return since_ms, None, f"last {last}"

    since_ms = parse_time_boundary(since, is_end=False) if since else None
    until_ms = parse_time_boundary(until, is_end=True) if until else None

    if since_ms is not None and until_ms is not None and since_ms > until_ms:
        raise ValueError(f"Start time cannot be after end time (since: {since}, until: {until})")

    label_parts = []
    if since:
        label_parts.append(f"since {since}")
    if until:
        label_parts.append(f"until {until}")
    label = ", ".join(label_parts) if label_parts else None

    return since_ms, until_ms, label
