"""Configuration and path resolution for CHID."""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """Return directory for persistent CHID data (database)."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    return base / "chid"


def get_database_path() -> Path:
    """Return path to SQLite history database."""
    override = os.environ.get("CHID_DB_PATH")
    if override:
        return Path(override)
    return get_data_dir() / "history.sqlite"


def get_cache_dir() -> Path:
    """Return directory for ephemeral caches (e.g. session command buffers)."""
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base = Path(xdg_cache)
    else:
        base = Path.home() / ".cache"
    return base / "chid"


def get_session_cache_path(session_id: str) -> Path:
    """Return path to temporary session cache file."""
    return get_cache_dir() / "sessions" / f"{session_id}.cache"
