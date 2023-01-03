from pathlib import Path
import sys
from typing import Optional

from chid_utils import get_destination_path, get_count_uses, get_history_directory_path, get_root_path, split_line
import argparse

try:
    from rich import print
except ImportError:
    ...


def display_by_occurance(destination_file: Path, reverse: bool, limit: Optional[int] = None) -> list[tuple[str]]:
    with open(destination_file, "r") as file:
        w = file.readlines()
        if reverse:
            w = reversed(w)

        s = set()
        index = 0
        result = []
        for line in w:
            time, command = split_line(line)
            if command not in s:
                index += 1
                s.add(command)
                # Index;Time;Percent;Command
                result.append(f"{index};{time};;{command}")
            if limit is not None and limit <= index:
                return result
        return result


def display_by_frequency(destination_file: Path, limit: Optional[int] = None) -> list[tuple[str]]:
    with open(destination_file, "r") as file:
        counted_uses = get_count_uses(file)

        total = sum(counted_uses.values())
        result = []
        for index, line in enumerate(counted_uses.most_common(limit)):
            command, occurence = line
            # Index;Time;Percent;Command
            result.append(f"{index+1};;{occurence/total:4.2%};{command}")
        return result


def delete_commands(destination_file: Path) -> None:
    destination_file.unlink(missing_ok=True)


def check_positive(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue


def save_to_file(output):
    root_path = get_root_path()
    with open(root_path / "last_output", "w") as file:
        for line in output:
            file.write(line)
            file.write("\n")


def display(output):
    ln = len(str(len(output)))
    for line in output:
        index, time, percent, command = line.split(";")
        if index:
            print(f"{index:<{ln}} ", end="")
        if percent:
            print(f"{percent:>6} ", end="")
        if command:
            print(f"{command} ", end="")
        print()


def main():
    parser = argparse.ArgumentParser(prog="chid", description="Find history for current directory", epilog="")

    parser.add_argument("dir", help=argparse.SUPPRESS)
    parser.add_argument("alias", help=argparse.SUPPRESS)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-sl", "--last-occurance", action="store_true", help="Sort by last execution")
    group.add_argument("-sf", "--first-occurance", action="store_true", help="Sort by first execution")
    parser.add_argument("-l", "--limit", type=check_positive, help="Limit size of output", default=20)
    parser.add_argument("-d", "--delete", action="store_true", default=False)

    args = parser.parse_args()
    dir = args.dir
    limit = args.limit

    history_directory_path = get_history_directory_path()
    destination_path = get_destination_path(history_directory_path, dir)
    destination_file = destination_path / "chid_commands"

    if not destination_file.exists():
        return

    if args.delete:
        delete_commands(destination_file)
        sys.exit()

    if args.first_occurance:
        output = display_by_occurance(destination_file, False, limit)
    elif args.last_occurance:
        output = display_by_occurance(destination_file, True, limit)
    else:
        output = display_by_frequency(destination_file, limit)

    save_to_file(output)
    display(output)


if __name__ == "__main__":
    """ """
    main()
