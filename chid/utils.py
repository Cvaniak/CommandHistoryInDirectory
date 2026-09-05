"""General utility functions for path resolution and command sanitization."""

from pathlib import Path


def find_git_root(path: Path | str) -> Path | None:
    """Find Git repository root by walking upward from the given path in pure Python."""
    current = Path(path).resolve()
    while True:
        git_target = current / ".git"
        if git_target.is_dir() or git_target.is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent


def sanitize_command(command: str) -> str:
    """Strip extraneous leading/trailing whitespace from command string."""
    return command.strip()
