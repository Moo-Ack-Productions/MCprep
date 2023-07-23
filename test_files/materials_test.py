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

from typing import Tuple
import os
import unittest

import bpy
from bpy.types import Material


class MaterialsTest(unittest.TestCase):
    """Materials-related tests."""

    def setUp(self):
        """Clears scene and data between each test"""
        bpy.ops.wm.read_homefile(app_template="", use_empty=True)

    def _debug_save_file_state(self):
        """Saves the current scene state to a test file for inspection."""
        testdir = os.path.dirname(__file__)
        path = os.path.join(testdir, "debug_save_state.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print(f"Saved to debug file: {path}")

    def _create_canon_mat(self, canon=None, test_pack=False):
        """Creates a material that should be recognized."""
        name = canon if canon else "dirt"
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        img_node = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        if canon and not test_pack:
            base = self.get_mcprep_path()
            filepath = os.path.join(
                base, "MCprep_resources",
                "resourcepacks", "mcprep_default", "assets", "minecraft",
                "textures", "block", canon + ".png")
            img = bpy.data.images.load(filepath)
        elif canon and test_pack:
            testdir = os.path.dirname(__file__)
            filepath = os.path.join(
                testdir, "test_resource_pack", "textures", canon + ".png")
            img = bpy.data.images.load(filepath)
        else:
            img = bpy.data.images.new(name, 16, 16)
        img_node.image = img
        return mat, img_node

    def _set_test_mcprep_texturepack_path(self, reset: bool = False):
        """Assigns or resets the local texturepack path."""
        testdir = os.path.dirname(__file__)
        path = os.path.join(testdir, "test_resource_pack")
        if not os.path.isdir(path):
            raise Exception("Failed to set test texturepack path")
        bpy.context.scene.mcprep_texturepack_path = path

    def test_prep_materials_no_selection(self):
        """Ensures prepping with no selection fails."""
        with self.assertRaises(RuntimeError) as rte:
            res = bpy.ops.mcprep.prep_materials(
                animateTextures=False,
                packFormat="simple",
                autoFindMissingTextures=False,
                improveUiSettings=False)
            self.assertEqual(res, {'CANCELLED'})
        self.assertIn(
            "Error: No objects selected",
            str(rte.exception),
            "Wrong error raised")

    def test_prep_materials_sel_no_mat(self):
        """Ensures prepping an obj without materials fails."""
        bpy.ops.mesh.primitive_plane_add()
        self.assertIsNotNone(bpy.context.object, "Object should be selected")
        with self.assertRaises(RuntimeError) as rte:
            res = bpy.ops.mcprep.prep_materials(
                animateTextures=False,
                packFormat="simple",
                autoFindMissingTextures=False,
                improveUiSettings=False)
            self.assertEqual(res, {'CANCELLED'})
        self.assertIn(
            "No materials found",
            str(rte.exception),
            "Wrong error raised")

        # TODO: Add test where material is added but without an image/nodes

    def _prep_material_test_constructor(self, pack_format: str) -> Material:
        """Ensures prepping with the expected parameters succeeds."""
        bpy.ops.mesh.primitive_plane_add()
        obj = bpy.context.object

        # add object with canonical material name. Assume cycles
        new_mat, _ = self._create_canon_mat()
        obj.active_material = new_mat
        self.assertIsNotNone(obj.active_material, "Material should be applied")

        res = bpy.ops.mcprep.prep_materials(
            animateTextures=False,
            packFormat=pack_format,
            autoFindMissingTextures=False,
            improveUiSettings=False)

        self.assertEqual(res, {'FINISHED'}, "Did not return finished")
        return new_mat

    def _get_imgnode_stats(self, mat: Material) -> Tuple[int, int]:
        count_images = 0
        missing_images = 0
        for node in mat.node_tree.nodes:
            if node.type != "TEX_IMAGE":
                continue
            elif node.image:
                count_images += 1
            else:
                missing_images += 1
        return (count_images, missing_images)

    def test_prep_simple(self):
        new_mat = self._prep_material_test_constructor("simple")
        count_images, missing_images = self._get_imgnode_stats(new_mat)
        self.assertEqual(
            count_images, 1, "Should have only 1 pass after simple load")
        self.assertEqual(
            missing_images, 0, "Should have 0 unloaded passes")

    def test_prep_pbr_specular(self):
        new_mat = self._prep_material_test_constructor("specular")
        count_images, missing_images = self._get_imgnode_stats(new_mat)
        self.assertGreaterEqual(
            count_images, 1, "Should have 1+ pass after pbr load")
        self.assertEqual(
            missing_images, 2, "Other passes should remain empty")

    def test_prep_pbr_seus(self):
        new_mat = self._prep_material_test_constructor("seus")
        count_images, missing_images = self._get_imgnode_stats(new_mat)
        self.assertGreaterEqual(
            count_images, 1, "Should have 1+ pass after seus load")
        self.assertEqual(
            missing_images, 2, "Other passes should remain empty")

    def test_prep_missing_pbr_passes(self):
        """Ensures norm/spec passes loaded after simple prepping."""
        self._set_test_mcprep_texturepack_path()
        new_mat, _ = self._create_canon_mat("diamond_ore", test_pack=True)

        bpy.ops.mesh.primitive_plane_add()
        obj = bpy.context.object
        obj.active_material = new_mat
        self.assertIsNotNone(obj.active_material, "Material should be applied")

        # Start with simple material loaded, non pbr/no extra passes
        res = bpy.ops.mcprep.prep_materials(
            animateTextures=False,
            autoFindMissingTextures=False,
            packFormat="simple",
            useExtraMaps=False,  # Set to false
            syncMaterials=False,
            improveUiSettings=False)
        self.assertEqual(res, {'FINISHED'})
        count_images, missing_images = self._get_imgnode_stats(new_mat)
        self.assertEqual(
            count_images, 1, "Should have only 1 pass after simple load")
        self.assertEqual(
            missing_images, 0, "Should have 0 unloaded passes")

        # Now try pbr load, should auto-load in adjacent _n and _s passes.
        self._set_test_mcprep_texturepack_path()
        res = bpy.ops.mcprep.prep_materials(
            animateTextures=False,
            autoFindMissingTextures=False,
            packFormat="specular",
            useExtraMaps=True,  # Set to True
            syncMaterials=False,
            improveUiSettings=False)
        self.assertEqual(res, {'FINISHED'})
        self.assertSequenceEqual(
            bpy.data.materials, [new_mat],
            "We should have only modified the one pre-existing material")

        count_images, missing_images = self._get_imgnode_stats(new_mat)
        # self._debug_save_file_state()
        self.assertEqual(
            count_images, 3, "Should have 3 pass after pbr load")
        self.assertEqual(
            missing_images, 0, "Should have 0 unloaded passes")


if __name__ == '__main__':
    unittest.main(exit=False)
