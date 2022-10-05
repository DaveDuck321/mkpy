import multiprocessing
import os

from argparse import ArgumentParser
from pathlib import Path

from .make import MKPY_Exception, run_make
from .util import exit_with_error_message, log_message

# fmt: off
parser = ArgumentParser("mkpy", description="GNU-make without the archaic scripting language")
parser.add_argument("target", type=str, default="default", nargs="?", help="target to make")
parser.add_argument("--file", "-f", type=Path, default=Path("makefile.py"), help="the makefile to run")
parser.add_argument("--jobs", "-j", metavar="N", type=int, default=multiprocessing.cpu_count(), help="allow N jobs at once")
parser.add_argument("--directory", "-C", type=Path, help="change to DIRECTORY before running makefile")
# fmt: on

args = parser.parse_args()

try:
    if args.directory is not None:
        os.chdir(args.directory)
        log_message(f"Entering directory '{args.directory}'")
except:
    exit_with_error_message(f"Cannot enter directory '{args.directory}'")

try:
    # Note: Exec is necessary: Python importlib doesn't work after an os.chdir
    #   This also avoids generating a garbage __pycache__
    exec(args.file.read_text())
except FileNotFoundError as exception:
    exit_with_error_message(exception)

try:
    run_make(args.target, args.jobs)
except MKPY_Exception as exception:
    exit_with_error_message(exception)

log_message("Success!")
