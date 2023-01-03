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
    splited = line.strip().split(";")
    if len(splited) != 2:
        raise ValueError
    return tuple(splited)


def get_count_uses(file: TextIOWrapper) -> Counter:
    lines = file.readlines()
    counter = Counter()
    for line in lines:
        try:
            _, command = split_line(line)
            counter[command] += 1
        except ValueError:
            # Better something than nothing
            ...

    return counter
