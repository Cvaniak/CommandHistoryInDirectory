"""Session-isolated command buffer replacement for shell command execution."""

from __future__ import annotations

import json
from pathlib import Path
import re

from chid.config import get_session_cache_path


def write_session_cache(session_id: str, formatted_commands: list[str]) -> None:
    """Store the current session list of displayed commands to JSON session cache."""
    cache_path = get_session_cache_path(session_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = cache_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(formatted_commands, f)
    temp_path.replace(cache_path)


def parse_buffer_request(buffer_text: str, alias: str | None = None) -> int | None:
    """Extract a 1-based numeric command index from buffer text like 'chid 3' or '<alias> 3'."""
    trimmed = buffer_text.strip()
    if not trimmed:
        return None

    # Match 'chid <digits>' or '<alias> <digits>'
    pattern = r"^(?:chid|" + (re.escape(alias) if alias else r"(?! )") + r")\s+(\d+)$"
    match = re.match(pattern, trimmed)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def resolve_buffer_replacement(
    session_id: str,
    buffer_text: str,
    alias: str | None = None,
) -> str:
    """Resolve a command index request to the original command line from the session cache."""
    idx = parse_buffer_request(buffer_text, alias=alias)
    if idx is None or idx < 1:
        return buffer_text

    cache_path = get_session_cache_path(session_id)
    if not cache_path.is_file():
        return buffer_text

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            commands: list[str] = json.load(f)

        if 1 <= idx <= len(commands):
            return commands[idx - 1]
    except (json.JSONDecodeError, OSError):
        pass

    return buffer_text
