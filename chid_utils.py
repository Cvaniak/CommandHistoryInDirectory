from __future__ import annotations
from collections import Counter
from io import TextIOWrapper
from pathlib import Path


def get_root_path() -> Path:
    script_directory_path = Path(__file__).resolve().parent
    return script_directory_path


def get_history_directory_path() -> Path:
    script_directory_path = Path(__file__).resolve().parent
    history_directory_path = script_directory_path / "dirs"
    return history_directory_path


def get_destination_path(history_directory_path, dir) -> Path:
    full_dir = Path(history_directory_path.joinpath(*dir.split("/")))
    return full_dir


def split_line(line: str) -> tuple[str, str]:
    timestamp, _, command = line.strip().partition(";")
    return (timestamp, command)


def get_count_uses(file: TextIOWrapper, contain: str = "") -> Counter:
    lines = file.readlines()
    counter = Counter()
    for line in lines:
        try:
            _, command = split_line(line)
            if contain in command:
                counter[command] += 1
        except ValueError:
            # Better something than nothing
            ...

    return counter
