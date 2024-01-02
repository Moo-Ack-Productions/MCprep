# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""MCprep unit test runner

Example usage:

# Run all tests for the first blender exec listed in blender_execs.txt
python3 run_tests.py

# Run all tests across all available versions of blender in blender_execs.txt
python3 run_tests.py -a

# Run a specific test, across specific versions of blender
python3 run_tests.py -v 3.6,3.5 -t test_disable_enable

Run script with -h to see all options. Must run with bpy-addon-build installed
"""

from enum import Enum
from typing import List
import argparse
import os
import subprocess
import sys
import time


COMPILE_CMD = ["bpy-addon-build", "--during-build", "dev"]
DATA_CMD = ["python", "mcprep_data_refresh.py", "-auto"]  # TODO, include in build
DCC_EXES = "blender_execs.txt"
TEST_RUNNER = os.path.join("test_files", "test_runner.py")
TEST_CSV_OUTPUTS = "test_results.csv"
SPACER = "-" * 79


class TestSpeed(Enum):
    """Which tests to run."""
    SLOW = 'slow'  # All tests, including any UI-triggering ones.
    MEDIUM = 'medium'  # All but the slowest tests.
    FAST = 'fast'  # Only fast-running tests (TBD target runtime).

    def __str__(self):
        return self.value


def main():
    args = get_args()

    # Read arguments
    blender_execs = get_blender_binaries()
    if not len(blender_execs):
        print("ERROR : No Blender exe paths found!")
        return

    # Compile the addon
    res = subprocess.check_output(COMPILE_CMD)
    print(res.decode("utf-8"))

    reset_test_file()

    # Loop over all binaries and run tests.
    t0 = time.time()
    any_failures = False
    for ind, binary in enumerate(blender_execs):
        run_all = args.all_execs is True
        run_specific = args.version is not None
        if ind > 0 and not (run_all or run_specific):
            continue  # Only run the first test unless specified
        if not os.path.exists(binary):
            print(f"Blender EXE not found: {binary}")
            continue
        cmd = [binary,
               "--background",
               "--factory-startup",
               "-y",
               "--python",
               TEST_RUNNER,
               "--"]  # TODO: Option to specify specific test or test class
        if args.test_specific is not None:
            cmd.extend(["-t", args.test_specific])
        if args.version is not None:
            cmd.extend(["-v", args.version])
        # output = subprocess.check_output(cmd)
        child = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        output = child.communicate()[0]
        print(output.decode("utf-8"))

        # Detect if there was at least 1+ failure/error, to pass to exit code.
        if child.returncode != 0:
            any_failures = True

    t1 = time.time()

    # Especially ensure tracker files are removed after tests complete.
    remove_tracker_files()

    output_results()
    round_s = round(t1 - t0)
    exit_code = 1 if any_failures else 0
    print(f"tests took {round_s}s to run, ending with code {exit_code}")
    sys.exit(exit_code)


def get_args():
    """Sets up and returns argument parser for module functions."""
    parser = argparse.ArgumentParser(description="Run MCprep tests.")
    # Would use action=argparse.BooleanOptionalAction,
    # but that's python 3.9+ only; we need to support 3.7.0+ (Blender 2.80)
    parser.add_argument(
        "-a", "--all_execs", action="store_true",
        help="Run the test suite once per each executable in blender_execs.txt"
    )
    parser.set_defaults(all_execs=False)
    parser.add_argument(
        "-t", "--test_specific",
        help="Run only a specific test function or class matching this name")
    parser.add_argument(
        "-v", "--version",
        help="Specify the blender version(s) to test, in #.# or #.##,#.#")
    parser.add_argument(
        "-s", "--speed",
        type=TestSpeed,
        choices=list(TestSpeed),
        help="Which speed of tests to run")
    return parser.parse_args()


def get_blender_binaries() -> List:
    """Extracts a list of strings meant to be blender binary paths."""
    if not os.path.exists(DCC_EXES):
        print(f"ERROR : The {DCC_EXES} file is missing! Please create it!")
        return []

    with open(DCC_EXES, "r") as f:
        blender_execs = [ln.rstrip() for ln in f.readlines()]

    return blender_execs


def reset_test_file():
    """Removes and reinitializes the output csv test file."""
    try:
        os.remove(TEST_CSV_OUTPUTS)
    except Exception as e:
        print(e)

    with open(TEST_CSV_OUTPUTS, "w") as fopen:
        header = ["bversion", "ran_tests", "ran", "skips", "failed", "errors"]
        fopen.write(",".join(header) + "\n")


def output_results():
    """Reads in and prints out the csv of test results."""
    if not os.path.isfile(TEST_CSV_OUTPUTS):
        print("Could not find test results csv!")
        return
    print(SPACER)
    with open(TEST_CSV_OUTPUTS, "r") as fopen:
        lns = fopen.readlines()
        for idx, line in enumerate(lns):
            line = line.strip()
            cols = line.split(",")

            # Update the first column to be a nicer written format, add
            # spacing to help columns align.
            cols[0] = cols[0].replace(". ", ".") + "   "  #
            tabline = "\t".join(cols)
            print(tabline)
            if idx == 0:
                print(SPACER)


def remove_tracker_files():
    """Ensure local tracker files are NEVER left around after tests."""
    git_dir = os.path.dirname(__file__)
    jfile = "mcprep_addon_tracker.json"
    jpath = os.path.join(git_dir, "MCprep_addon", jfile)
    par_jfile = "mcprep_addon_trackerid.json"
    par_jpath = os.path.join(git_dir, par_jfile)

    has_jpath = os.path.isfile(jpath)
    has_par_jpath = os.path.isfile(par_jpath)

    if has_jpath:
        print("Removing: ", jpath)
        os.remove(jpath)
    if has_par_jpath:
        print("Removing: ", par_jpath)
        os.remove(par_jpath)


if __name__ == "__main__":
    main()
