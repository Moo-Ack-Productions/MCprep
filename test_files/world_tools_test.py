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

import filecmp
import os
import shutil
import tempfile
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

    def test_enable_obj_importer(self):
        """Ensure module name is correct, since error won't be reported."""
        bpy.ops.preferences.addon_enable(module="io_scene_obj")

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

    def test_world_import_fails_expected(self):
        testdir = os.path.dirname(__file__)
        obj_path = os.path.join(testdir, "fake_world.obj")
        with self.assertRaises(RuntimeError):
            res = bpy.ops.mcprep.import_world_split(filepath=obj_path)
            self.assertEqual(res, {'CANCELLED'})

    def test_add_mc_sky(self):
        subtests = [
            # name / enum option, add_clouds, remove_existing_suns
            ["world_shader", True, True],
            ["world_mesh", True, False],
            ["world_only", False, True],
            ["world_static_mesh", False, False],
            ["world_static_only", True, True]
        ]

        for sub in subtests:
            with self.subTest(sub[0]):
                # Reset the scene
                bpy.ops.wm.read_homefile(app_template="", use_empty=True)

                pre_objs = len(bpy.data.objects)
                res = bpy.ops.mcprep.add_mc_sky(
                    world_type=sub[0],
                    add_clouds=sub[1],
                    remove_existing_suns=sub[2]
                )
                post_objs = len(bpy.data.objects)
                self.assertEqual(res, {'FINISHED'})
                self.assertGreater(
                    post_objs, pre_objs, "No timeobject imported")
                obj = world_tools.get_time_object()
                if "static" in sub[0]:
                    self.assertFalse(obj, "Static scn should have no timeobj")
                else:
                    self.assertTrue(obj, "Dynamic scn should have timeobj")

    def test_convert_mtl_simple(self):
        """Ensures that conversion of the mtl with other color space works."""

        src = "mtl_simple_original.mtl"
        end = "mtl_simple_modified.mtl"
        test_dir = os.path.dirname(__file__)
        simple_mtl = os.path.join(test_dir, "test_data", src)
        modified_mtl = os.path.join(test_dir, "test_data", end)

        # now save the texturefile somewhere
        tmp_dir = tempfile.gettempdir()
        tmp_mtl = os.path.join(tmp_dir, src)
        shutil.copyfile(simple_mtl, tmp_mtl)  # leave original intact

        self.assertTrue(
            os.path.isfile(tmp_mtl),
            f"Failed to create tmp tml at {tmp_mtl}")

        # Need to mock:
        # bpy.context.scene.view_settings.view_transform
        # to be an invalid kind of attribute, to simulate an ACES or AgX space.
        # But we can't do that since we're not (yet) using the real unittest
        # framework, hence we'll just clear the  world_tool's vars.
        save_init = list(world_tools.BUILTIN_SPACES)
        world_tools.BUILTIN_SPACES = ["NotRealSpace"]
        print("TEST: pre", world_tools.BUILTIN_SPACES)

        # Resultant file
        res = world_tools.convert_mtl(tmp_mtl)

        # Restore the property we unset.
        world_tools.BUILTIN_SPACES = save_init
        print("TEST: post", world_tools.BUILTIN_SPACES)

        self.assertIsNotNone(
            res,
            "Failed to mock color space and thus could not test convert_mtl")

        self.assertTrue(res, "Convert mtl failed with false response")

        # Now check that the data is the same.
        res = filecmp.cmp(tmp_mtl, modified_mtl, shallow=False)
        self.assertTrue(
            res, f"Generated MTL is different: {tmp_mtl} vs {modified_mtl}")
        # Not removing file, since we likely want to inspect it.
        os.remove(tmp_mtl)

    def test_convert_mtl_skip(self):
        """Ensures that we properly skip if a built in space active."""

        src = "mtl_simple_original.mtl"
        test_dir = os.path.dirname(__file__)
        simple_mtl = os.path.join(test_dir, "test_data", src)

        # now save the texturefile somewhere
        tmp_dir = tempfile.gettempdir()
        tmp_mtl = os.path.join(tmp_dir, src)
        shutil.copyfile(simple_mtl, tmp_mtl)  # leave original intact

        self.assertTrue(
            os.path.isfile(tmp_mtl), f"Failed to create tmp tml at {tmp_mtl}")

        # Need to mock:
        # bpy.context.scene.view_settings.view_transform
        # to be an invalid kind of attribute, to simulate an ACES or AgX space.
        # But we can't do that since we're not (yet) using the real unittest
        # framework, hence we'll just clear the  world_tool's vars.
        actual_space = str(bpy.context.scene.view_settings.view_transform)
        save_init = list(world_tools.BUILTIN_SPACES)
        world_tools.BUILTIN_SPACES = [actual_space]
        # print("TEST: pre", world_tools.BUILTIN_SPACES)

        # Resultant file
        res = world_tools.convert_mtl(tmp_mtl)

        # Restore the property we unset.
        world_tools.BUILTIN_SPACES = save_init
        # print("TEST: post", world_tools.BUILTIN_SPACES)

        if res is not None:
            os.remove(tmp_mtl)
        self.assertIsNone(res, "Should not have converter MTL for valid space")


if __name__ == '__main__':
    unittest.main(exit=False)
