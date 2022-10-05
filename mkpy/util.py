import sys

from types import TracebackType
from pathlib import Path

mkpy_path = Path(__file__).parent


def trim_library_code_from_traceback(
    traceback: TracebackType, has_left_python_library: bool = False
) -> TracebackType:
    traceback_file = Path(traceback.tb_frame.f_code.co_filename)
    is_in_mkpy = traceback_file.is_relative_to(mkpy_path)

    if has_left_python_library and not is_in_mkpy:
        return traceback

    if not has_left_python_library and is_in_mkpy:
        return trim_library_code_from_traceback(traceback.tb_next, True)

    return trim_library_code_from_traceback(traceback.tb_next, has_left_python_library)


def log_message(message: str):
    print(f"mkpy: {message}")


def exit_with_error_message(message: str):
    print(f"mkpy: *** {message}", file=sys.stderr)
    exit(1)
