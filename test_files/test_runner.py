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

import argparse
import os
import sys
import unittest

import bpy

# Commandline script passed to Blender, directory should be //test/
MODULE_DIR = os.path.dirname(__file__)
sys.path.append(MODULE_DIR)

SPACER = "-" * 79


def get_args():
    """Sets up and returns argument parser for module functions."""
    # Override the args available to arg parser, to ignore blender ones.
    if "--" in sys.argv:
        test_args = sys.argv[sys.argv.index("--") + 1:]
    else:
        test_args = []
    sys.argv = [os.path.basename(__file__)] + test_args

    parser = argparse.ArgumentParser(description="Run MCprep tests.")
    parser.add_argument(
        "-t", "--test_specific",
        help="Run only a specific test function or class matching this name")
    parser.add_argument(
        "-v", "--version",
        help="Specify the blender version(s) to test, in #.# or #.##,#.#")
    return parser.parse_args()


def setup_env_paths(self):
    """Adds the MCprep installed addon path to sys for easier importing."""
    to_add = None

    for base in bpy.utils.script_paths():
        init = os.path.join(base, "addons", "MCprep_addon", "__init__.py")
        if os.path.isfile(init):
            to_add = init
            break
    if not to_add:
        raise Exception("Could not add MCprep addon path for importing")

    sys.path.insert(0, to_add)


def main():
    args = get_args()
    suite = unittest.TestSuite()

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    if args.version is not None:
        # A concatenated list like 3.5,2.80
        bvers = args.version.split(",")
        # Get the tuple version to compare to current version.
        valid_bver = False
        for this_bv in bvers:
            this_bv_tuple = tuple(int(i) for i in this_bv.split("."))

            # Get the current version of blender, truncating to the same number
            # of digits (so input: #.# -> current bv 2.80.1 gets cut to 2.80)
            open_blender = bpy.app.version[:len(this_bv_tuple)]
            if open_blender == this_bv_tuple:
                valid_bver = True
                break

        if not valid_bver:
            print(f"Skipping: Blender {bpy.app.version} does not match {args.version}")
            sys.exit()

    print("")
    print(SPACER)
    print(f"Running tests for {bpy.app.version}...")

    # Run tests in the addon tests directory matching rule.
    suite.addTest(unittest.TestLoader().discover(MODULE_DIR, "*_test.py"))

    # Check if there's another input for a single test to run,
    # rebuild the test suite with only that flagged test.
    if args.test_specific:
        new_suite = unittest.TestSuite()
        for test_file in suite._tests:
            for test_cls in test_file._tests:
                for test_function_suite in test_cls:
                    for this_test in test_function_suite._tests:
                        # str in format of:
                        # file_name.ClassName.test_case_name
                        tst_name_id = this_test.id()
                        tst_names = tst_name_id.split(".")
                        if args.test_specific in tst_names:
                            new_suite.addTest(this_test)
                            print("Run only: ", this_test._testMethodName)
        suite = new_suite

    results = unittest.TextTestRunner(verbosity=2).run(suite)
    print(SPACER)
    print(results)

    # Append outputs to csv file, so that we can easily see multiple
    # runs across different versions of blender to verify successes.
    errs = [res[0].id().split(".")[-1] for res in results.errors]
    fails = [res[0].id().split(".")[-1] for res in results.failures]
    skipped = [res[0].id().split(".")[-1] for res in results.skipped]

    errors = ";".join(errs + fails).replace(",", " ")
    with open("test_results.csv", 'a') as csv:
        err_txt = "No errors" if errors == "" else errors
        csv.write("{},{},{},{},{},{}\r\n".format(
            str(bpy.app.version).replace(",", "."),
            "all_tests" if not args.test_specific else args.test_specific,
            results.testsRun - len(skipped),
            len(skipped),
            len(results.errors) + len(results.failures),
            err_txt,
        ))
    print("Wrote out test results.")
    if errors:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
