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

import unittest

import bpy
import os

# TODO: restructure tests to be inside MCprep_addon to support rel imports.
# from . import test_runner
RUN_SLOW_TESTS = False

# Tests which cause some UI changes, such as opening webpages or folder opens.
RUN_UI_TESTS = False


class UtilOperatorsTest(unittest.TestCase):
    """Create tests for the util_operators.py file."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def test_improve_ui(self):
        res = bpy.ops.mcprep.improve_ui()
        self.assertEqual(res, {"CANCELLED"})  # Always returns this in bg mode

    # Cannot have the right context for this to run.
    # def test_open_preferences(self):
    #    res = bpy.ops.mcprep.open_preferences()
    #    self.assertEqual(res, {"FINISHED"})

    @unittest.skipUnless(RUN_UI_TESTS, "Skip UI: test_open_folder")
    def test_open_folder(self):
        folder = bpy.utils.script_path_user()
        self.assertTrue(os.path.isdir(folder), "Invalid target folder")
        res = bpy.ops.mcprep.openfolder(folder=folder)
        self.assertEqual(res, {"FINISHED"})

        with self.assertRaises(RuntimeError):
            res = bpy.ops.mcprep.openfolder(folder="/fake/folder")
            self.assertEqual(res, {"CANCELLED"})

    @unittest.skipUnless(RUN_UI_TESTS, "Skip UI: test_open_folder")
    def test_open_help(self):
        # Mocking not working this way when used on operators.
        # with mock.patch("bpy.ops.wm.url_open") as mock_open:
        res = bpy.ops.mcprep.open_help(url="https://theduckcow.com")
        self.assertEqual(res, {"FINISHED"})


if __name__ == '__main__':
    # TODO: restructure tests to be inside MCprep_addon to support rel imports.
    # args = test_runner.get_args()
    # RUN_SLOW_TESTS = args.speed == "slow"
    unittest.main(exit=False)
