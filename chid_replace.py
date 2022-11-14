import sys

from chid_utils import get_destination_path, get_count_uses, get_history_directory_path


def main() -> str:
    if len(sys.argv) <= 2 or not sys.argv[2].startswith("t "):
        return ""

    value = sys.argv[2].split(" ")[1]
    if not value.isnumeric():
        return ""

    value = int(value)

    dir = sys.argv[1]

    history_directory_path = get_history_directory_path()
    destination_path = get_destination_path(history_directory_path, dir)
    destination_file = destination_path / "chid_commands"

    if not destination_file.exists():
        return ""

    with open(destination_file, "r") as file:
        counted_uses = get_count_uses(file)
        if value <= len(counted_uses):
            return str(counted_uses.most_common(value)[-1][0])

    return ""


if __name__ == "__main__":
    result = main()
    print(result, end="")
