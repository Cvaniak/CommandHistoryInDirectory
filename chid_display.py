import sys
from collections import Counter

from chid_utils import get_destination_path, get_count_uses, get_history_directory_path


def main():
    dir = sys.argv[1]

    history_directory_path = get_history_directory_path()
    destination_path = get_destination_path(history_directory_path, dir)
    destination_file = destination_path / "chid_commands"

    if not destination_file.exists():
        return

    with open(destination_file, "r") as file:
        counted_uses = get_count_uses(file)

        total = sum(counted_uses.values())
        for index, line in enumerate(counted_uses.most_common()):
            command, occurence = line
            print(f"{index+1:<2} {occurence/total:>4.0%}", command)


if __name__ == "__main__":
    """ """
    main()
