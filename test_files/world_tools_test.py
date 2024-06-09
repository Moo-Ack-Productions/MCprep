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

from MCprep_addon import util
from MCprep_addon import world_tools
from MCprep_addon.materials.generate import find_from_texturepack
from MCprep_addon.materials.generate import get_mc_canonical_name
from MCprep_addon.materials.uv_tools import detect_invalid_uvs_from_objs
from MCprep_addon.util import materialsFromObj


class WorldToolsTest(unittest.TestCase):
    """World tools related tests."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def setUp(self):
        """Clears scene and data between each test"""
        bpy.ops.wm.read_homefile(app_template="", use_empty=True)
        self.addon_prefs = util.get_user_preferences(bpy.context)

    # -------------------------------------------------------------------------
    # Sub-test utilities
    # -------------------------------------------------------------------------

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

    def _canonical_name_no_none(self):
        """Ensure that MC canonical name never returns none"""

        mats = materialsFromObj(bpy.context.scene.objects)
        canons = [[get_mc_canonical_name(mat.name)][0] for mat in mats]
        self.assertGreater(len(canons), 10, "Materials not selected")
        self.assertNotIn(None, canons, "Canon returned none value")
        self.assertNotIn("", canons, "Canon returned empty str value")

        # Ensure it never returns None
        in_str, _ = get_mc_canonical_name('')
        self.assertEqual(in_str, '', "Empty str should return empty string")

        with self.assertRaises(TypeError):
            get_mc_canonical_name(None)  # "None input SHOULD raise error"

    def _import_materials_util(self, mapping_set):
        """Reusable function for testing on different obj setups"""

        util.load_mcprep_json()  # force load json cache
        # Must use the reference of env associated with util,
        # can't import conf separately.
        mcprep_data = util.env.json_data["blocks"][mapping_set]

        # first detect alignment to the raw underlining mappings, nothing to
        # do with canonical yet
        mapped = [
            mat.name for mat in bpy.data.materials
            if mat.name in mcprep_data]  # ok!
        unmapped = [
            mat.name for mat in bpy.data.materials
            if mat.name not in mcprep_data]  # not ok
        fullset = mapped + unmapped  # ie all materials
        unleveraged = [
            mat for mat in mcprep_data
            if mat not in fullset]  # not ideal, means maybe missed check

        # print("Mapped: {}, unmapped: {}, unleveraged: {}".format(
        #     len(mapped), len(unmapped), len(unleveraged)))

        # if len(unmapped):
        #     err = "Textures not mapped to json file"
        #     print(err)
        #     print(sorted(unmapped))
        #     print("")
        #     # return err
        # if len(unleveraged) > 20:
        #     err = "Json file materials not found, need to update world?"
        #     print(err)
        #     print(sorted(unleveraged))
        #     # return err

        self.assertGreater(len(mapped), 0, "No materials mapped")
        if mapping_set == "block_mapping_mineways" and len(mapped) > 75:
            # Known that the "combined" atlas texture of Mineways imports
            # has low coverge, and we're not doing anything about it.
            # but will at least capture if coverage gets *worse*.
            pass
        elif len(mapped) < len(unmapped):  # too many esp. for Mineways
            # not a very optimistic threshold, but better than none
            self.fail("More materials unmapped than mapped")

        # each element is [cannon_name, form], form is none if not matched
        mapped = [get_mc_canonical_name(mat.name)
                  for mat in bpy.data.materials]

        # no matching canon name (warn)
        mats_not_canon = [itm[0] for itm in mapped if itm[1] is None]
        if mats_not_canon and mapping_set != "block_mapping_mineways":
            # print("Non-canon material names found: ({})".format(len(mats_not_canon)))
            # print(mats_not_canon)
            if len(mats_not_canon) > 30:  # arbitrary threshold
                self.fail("Too many materials found without canonical name")

        # affirm the correct mappings
        mats_no_packimage = [
            find_from_texturepack(itm[0]) for itm in mapped
            if itm[1] is not None]
        mats_no_packimage = [path for path in mats_no_packimage if path]

        # could not resolve image from resource pack (warn) even though in mapping
        mats_no_packimage = [
            itm[0] for itm in mapped
            if itm[1] is not None and not find_from_texturepack(itm[0])]

        # known number up front, e.g. chests, stone_slab_side, stone_slab_top
        if len(mats_no_packimage) > 6:
            miss_blocks = " | ".join(mats_no_packimage)
            self.fail("Missing images for mcprep_data.json blocks: {}".format(
                miss_blocks))

        # also test that there are not raw image names not in mapping list
        # but that otherwise could be added to the mapping list as file exists

    # -------------------------------------------------------------------------
    # Top-level tests
    # -------------------------------------------------------------------------

    def test_enable_obj_importer(self):
        """Ensure module name is correct, since error won't be reported."""
        if bpy.app.version < (4, 0):
            res = bpy.ops.preferences.addon_enable(module="io_scene_obj")
            self.assertEqual(res, {'FINISHED'})
        else:
            in_import_scn = "obj_import" in dir(bpy.ops.wm)
            self.assertTrue(in_import_scn, "obj_import operator not found")


    def test_world_import_jmc_full(self):
        test_subpath = os.path.join(
            "test_data", "jmc2obj_test_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "jmc2obj")

        # UV tool test. Would be in its own test, but then we would be doing
        # multiple unnecessary imports of the same world. So make it a subtest.
        with self.subTest("test_uv_transform_no_alert_jmc2obj"):
            invalid, invalid_objs = detect_invalid_uvs_from_objs(
                bpy.context.selected_objects)
            prt = ",".join([obj.name.split("_")[-1] for obj in invalid_objs])
            self.assertFalse(
                invalid, f"jmc2obj export should not alert: {prt}")

        with self.subTest("canon_name_validation"):
            self._canonical_name_no_none()

        with self.subTest("test_mappings"):
            self._import_materials_util("block_mapping_jmc")

    def test_world_import_mineways_separated(self):
        test_subpath = os.path.join(
            "test_data", "mineways_test_separated_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "Mineways")

        # UV tool test. Would be in its own test, but then we would be doing
        # multiple unnecessary imports of the same world. So make it a subtest.
        with self.subTest("test_uv_transform_no_alert_mineways"):
            invalid, invalid_objs = detect_invalid_uvs_from_objs(
                bpy.context.selected_objects)
            prt = ",".join([obj.name for obj in invalid_objs])
            self.assertFalse(
                invalid,
                f"Mineways separated tiles export should not alert: {prt}")

        with self.subTest("canon_name_validation"):
            self._canonical_name_no_none()

        with self.subTest("test_mappings"):
            self._import_materials_util("block_mapping_mineways")

    def test_world_import_mineways_combined(self):
        test_subpath = os.path.join(
            "test_data", "mineways_test_combined_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "Mineways")

        with self.subTest("test_uv_transform_combined_alert"):
            invalid, invalid_objs = detect_invalid_uvs_from_objs(
                bpy.context.selected_objects)
            self.assertTrue(invalid, "Combined image export should alert")
            if not invalid_objs:
                self.fail(
                    "Correctly alerted combined image, but no obj's returned")

            # Do specific checks for water and lava, could be combined and
            # cover more than one uv position (and falsely pass the test) in
            # combined, water is called "Stationary_Wat" and "Stationary_Lav"
            # (yes, appears cutoff; and yes includes the flowing too)
            # NOTE! in 2.7x, will be named "Stationary_Water", but in 2.9 it is
            # "Test_MCprep_1.16.4__-145_4_1271_to_-118_255_1311_Stationary_Wat"
            water_obj = [obj for obj in bpy.data.objects
                         if "Stationary_Wat" in obj.name][0]
            lava_obj = [obj for obj in bpy.data.objects
                        if "Stationary_Lav" in obj.name][0]

            invalid, invalid_objs = detect_invalid_uvs_from_objs(
                [lava_obj, water_obj])
            self.assertTrue(invalid, "Combined lava/water should still alert")

        with self.subTest("canon_name_validation"):
            self._canonical_name_no_none()

        with self.subTest("test_mappings"):
            self._import_materials_util("block_mapping_mineways")

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
