import sys

from chid_utils import get_destination_path, get_history_directory_path


def main():
    if len(sys.argv) < 5:
        return

    dir = sys.argv[1]
    command = sys.argv[2].strip()
    date = sys.argv[3]
    alias = sys.argv[4]

    history_directory_path = get_history_directory_path()

    # Do not allow to create new history inside history directory
    if dir.startswith(str(history_directory_path)):
        return

    if command.startswith("chid ") or command.startswith(f"{alias} ") or command in [alias, "chid", ""]:
        return

    destination_path = get_destination_path(history_directory_path, dir)
    destination_path.mkdir(parents=True, exist_ok=True)
    destination_file = destination_path / "chid_commands"

    with open(destination_file, "a") as file:
        file.write(f"{date};{repr(command)[1:-1]}\n")


if __name__ == "__main__":
    """
    Arguments: Directory, Command, Date, Alias
    """
    main()
