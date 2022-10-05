import sys


def log_message(message: str):
    print(f"mkpy: {message}")


def exit_with_error_message(message: str):
    print(f"mkpy: *** {message}", file=sys.stderr)
    exit(1)
