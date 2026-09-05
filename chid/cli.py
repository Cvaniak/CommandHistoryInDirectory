"""CHID CLI entrypoint."""

import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print("chid 0.2.0")
        return
    print("CHID initialized.")


if __name__ == "__main__":
    main()
