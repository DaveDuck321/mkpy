import re
import subprocess
import sys

from functools import partial
from pathlib import Path
from types import TracebackType

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


def sh(command: str):
    print(command)
    subprocess.check_call(command, shell=True)


def format_with_regex(regex: str, format_str: str, input_string: str):
    match = re.compile(regex).fullmatch(input_string)
    return format_str.format(*match.groups())


def format_list_with_regex(regex: str, format_str: str, input_strings: list[str]):
    return list(map(partial(format_with_regex, regex, format_str), input_strings))


def log_message(message: str):
    print(f"mkpy: {message}")


def exit_with_error_message(message: str):
    print(f"mkpy: *** {message}", file=sys.stderr)
    exit(1)
