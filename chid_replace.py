import sys

from chid_utils import get_root_path


def main() -> str:
    alias = sys.argv[3]

    if len(sys.argv) <= 2 or not (sys.argv[2].startswith("chid ") or sys.argv[2].startswith(f"{alias} ")):
        return ""

    value = sys.argv[2].split(" ")[1]
    if not value.isnumeric():
        return ""

    value = int(value)
    if value == 0:
        return ""

    # dir = sys.argv[1]

    root_path = get_root_path()
    destination_file = root_path / "last_output"

    if not destination_file.exists():
        return ""

    with open(destination_file, "r") as file:
        splited = file.readlines()
        if len(splited) < value:
            return ""
        return splited[value - 1].split(";")[-1]


if __name__ == "__main__":
    result = main()
    print(result, end="")
