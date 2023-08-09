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

import os
import unittest

import bpy

from MCprep_addon import world_tools
from MCprep_addon import util


class WorldToolsTest(unittest.TestCase):
    """World tools related tests."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def setUp(self):
        """Clears scene and data between each test"""
        bpy.ops.wm.read_homefile(app_template="", use_empty=True)
        self.addon_prefs = util.get_user_preferences(bpy.context)

    def _import_world_with_settings(self, file: str):
        testdir = os.path.dirname(__file__)
        obj_path = os.path.join(testdir, file)

        self.assertEqual(len(bpy.data.objects), 0, "Should start with no objs")
        self.assertTrue(os.path.isfile(obj_path),
                        f"Obj file missing: {obj_path}, {file}")
        res = bpy.ops.mcprep.import_world_split(filepath=obj_path)
        self.assertEqual(res, {'FINISHED'})
        self.assertGreater(len(bpy.data.objects), 50, "Should have many objs")
        self.assertGreater(
            len(bpy.data.materials), 50, "Should have many mats")

    def test_world_import_jmc_full(self):
        test_subpath = os.path.join(
            "test_data", "jmc2obj_test_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "jmc2obj")

    def test_world_import_mineways_separated(self):
        test_subpath = os.path.join(
            "test_data", "mineways_test_separated_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "Mineways")

    def test_world_import_mineways_combined(self):
        test_subpath = os.path.join(
            "test_data", "mineways_test_combined_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "Mineways")


if __name__ == '__main__':
    unittest.main(exit=False)
