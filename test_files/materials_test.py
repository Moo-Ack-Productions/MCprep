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
import datetime
import os
import shutil
import unittest

import bpy
from bpy.types import Material

from MCprep_addon.materials import sequences
from MCprep_addon.materials import generate


class MaterialsTest(unittest.TestCase):
    """Materials-related tests."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def setUp(self):
        """Clears scene and data between each test"""
        bpy.ops.wm.read_homefile(app_template="", use_empty=True)

    def _debug_save_file_state(self):
        """Saves the current scene state to a test file for inspection."""
        testdir = os.path.dirname(__file__)
        path = os.path.join(testdir, "debug_save_state.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print(f"Saved to debug file: {path}")

    def _get_mcprep_path(self):
        """Returns the addon basepath installed in this blender instance"""
        for base in bpy.utils.script_paths():
            init = os.path.join(
                base, "addons", "MCprep_addon")  # __init__.py folder
            if os.path.isdir(init):
                return init
        self.fail("Failed to get MCprep path")

    def _get_canon_texture_image(self, name: str, test_pack=False):
        if test_pack:
            testdir = os.path.dirname(__file__)
            filepath = os.path.join(
                testdir, "test_resource_pack", "textures", name + ".png")
            return filepath
        else:
            base = self._get_mcprep_path()
            filepath = os.path.join(
                base, "MCprep_resources",
                "resourcepacks", "mcprep_default", "assets", "minecraft",
                "textures", "block", name + ".png")
            return filepath

    def _create_canon_mat(self, canon: str = None, test_pack=False):
        # ) -> Tuple(bpy.types.Material, bpy.types.ShaderNode):
        """Creates a material that should be recognized."""
        name = canon if canon else "dirt"
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        img_node = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        if canon:
            filepath = self._get_canon_texture_image(canon, test_pack)
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

    def test_generate_material_sequence(self):
        """Validates generating an image sequence works ok."""
        self._material_sequnece_subtest(operator=False)

    def test_prep_material_animated(self):
        """Validates loading an animated material works ok."""
        self._material_sequnece_subtest(operator=True)

    def _has_animated_tex_node(self, mat) -> bool:
        any_animated = False
        for nd in mat.node_tree.nodes:
            if nd.type != "TEX_IMAGE":
                continue
            if nd.image.source == "SEQUENCE":
                any_animated = True
                break
        return any_animated

    def _material_sequnece_subtest(self, operator: bool):
        """Validates generating an image sequence works ok."""

        tiled_img = os.path.join(
            os.path.dirname(__file__),
            "test_resource_pack", "textures", "campfire_fire.png")
        fake_orig_img = tiled_img
        result_dir = os.path.splitext(tiled_img)[0]

        try:
            shutil.rmtree(result_dir)
        except Exception:
            pass  # Ok, generally should be cleaned up anyways.

        # Ensure that the folder does not initially exist
        self.assertFalse(os.path.isdir(result_dir),
                         "Folder pre-exists, should be removed before test")

        res, err = None, None
        if operator is True:
            # Add a mesh to operate on
            bpy.ops.mesh.primitive_plane_add()

            res = bpy.ops.mcprep.load_material(
                filepath=tiled_img, animateTextures=False)
            self.assertEqual(res, {'FINISHED'})

            any_animated = self._has_animated_tex_node(
                bpy.context.object.active_material)
            self.assertFalse(any_animated, "Should not be initially animated")

            res = bpy.ops.mcprep.load_material(
                filepath=tiled_img, animateTextures=True)
            self.assertEqual(res, {'FINISHED'})
            any_animated = self._has_animated_tex_node(
                bpy.context.object.active_material)
            self._debug_save_file_state()
            self.assertTrue(any_animated, "Affirm animated material applied")

        else:
            res, err = sequences.generate_material_sequence(
                source_path=fake_orig_img,
                image_path=tiled_img,
                form=None,
                export_location="original",
                clear_cache=True)

            gen_files = [img for img in os.listdir(result_dir)
                         if img.endswith(".png")]
            self.assertTrue(os.path.isdir(result_dir),
                            "Output directory does not exist")
            shutil.rmtree(result_dir)
            self.assertTrue(gen_files, "No images generated")
            self.assertIsNone(err, "Generate materials had an error")
            self.assertTrue(
                res,
                "Failed to get success resposne from generate img sequence")

    def test_detect_desaturated_images(self):
        """Checks the desaturate images are recognized as such."""
        should_saturate = {
            # Sample of canonically grayscale textures.
            "grass_block_top": True,
            "acacia_leaves": True,
            "redstone_dust_line0": True,
            "water_flow": True,

            # Sample of textures already saturated
            "grass_block_side": False,
            "glowstone": False
        }

        for tex in list(should_saturate):
            do_sat = should_saturate[tex]
            with self.subTest(f"Assert {tex} saturate is {do_sat}"):
                img_file = self._get_canon_texture_image(tex, test_pack=False)
                self.assertTrue(
                    os.path.isfile(img_file),
                    f"Failed to get test file {img_file}")
                img = bpy.data.images.load(img_file)
                self.assertTrue(img, 'Failed to load img')
                res = generate.is_image_grayscale(img)
                if do_sat:
                    self.assertTrue(
                        res, f"Should detect {tex} as grayscale")
                else:
                    self.assertFalse(
                        res, f"Should not detect {tex} as grayscale")

        # TODO: test that it is caching as expected.. by setting a false
        # value for cache flag and seeing it's returning the property value

    def test_matprep_cycles(self):
        """Tests the generation function used within an operator."""
        canon = "grass_block_top"
        mat, img_node = self._create_canon_mat(canon, test_pack=False)
        passes = {"diffuse": img_node.image}
        options = generate.PrepOptions(
            passes=passes,
            use_reflections=False,
            use_principled=True,
            only_solid=False,
            pack_format="simple",
            use_emission_nodes=False,
            use_emission=False
        )

        generate.matprep_cycles(mat, options)
        self.assertEqual(1, len(bpy.data.materials))
        self.assertEqual(1, len(bpy.data.images), list(bpy.data.images))

    def test_skin_swap_local(self):
        bpy.ops.mcprep.reload_skins()
        skin_ind = bpy.context.scene.mcprep_skins_list_index
        skin_item = bpy.context.scene.mcprep_skins_list[skin_ind]
        tex_name = skin_item["name"]
        skin_path = os.path.join(bpy.context.scene.mcprep_skin_path, tex_name)

        self.assertIsNone(bpy.context.object, "Should have no initial object")

        with self.assertRaises(RuntimeError) as raised:
            res = bpy.ops.mcprep.applyskin(
                filepath=skin_path,
                new_material=False)
            self.assertEqual(res, {'CANCELLED'})

        self.assertEqual('Error: No materials found to update\n',
                         str(raised.exception),
                         "Should fail when no existing materials exist")

        # now run on a real test character, with 1 material and 2 objects
        # self._add_character()
        # Using a simple material now, to make things fast.
        mat, _ = self._create_canon_mat()
        bpy.ops.mesh.primitive_plane_add()
        self.assertIsNotNone(bpy.context.object, "Object should be selected")
        bpy.context.object.active_material = mat

        # Perform the main action
        pre_mats = len(bpy.data.materials)
        res = bpy.ops.mcprep.applyskin(filepath=skin_path,
                                       new_material=False)
        post_mats = len(bpy.data.materials)
        self.assertEqual(pre_mats, post_mats, "Should not create a new mat")

        # do counts of materials before and after to ensure they match
        pre_mats = len(bpy.data.materials)
        bpy.ops.mcprep.applyskin(
            filepath=skin_path,
            new_material=True)
        post_mats = len(bpy.data.materials)
        self.assertEqual(pre_mats * 2, post_mats,
                         "Should have 2x as many mats after new mats created")

    def test_skin_swap_username(self):
        bpy.ops.mcprep.reload_skins()

        mat, _ = self._create_canon_mat()
        bpy.ops.mesh.primitive_plane_add()
        self.assertIsNotNone(bpy.context.object, "Object should be selected")
        bpy.context.object.active_material = mat

        username = "theduckcow"

        # Be sure to delete the skin first, otherwise just testing locality.
        target_index = None
        for ind, itm in enumerate(bpy.context.scene.mcprep_skins_list):
            if itm["name"].lower() == username.lower() + ".png":
                target_index = ind
                break

        if target_index is not None:
            bpy.context.scene.mcprep_skins_list_index = target_index
            res = bpy.ops.mcprep.remove_skin()
            self.assertEqual(res, {'FINISHED'})

        # Triple verify the file is now gone.
        skin_path = os.path.join(bpy.context.scene.mcprep_skin_path,
                                 username + ".png")
        self.assertFalse(os.path.isfile(skin_path),
                         "Skin should initially be removed")

        res = bpy.ops.mcprep.applyusernameskin(
            username='TheDuckCow',
            skip_redownload=False,
            new_material=True)

        self.assertEqual(res, {'FINISHED'})
        self.assertTrue(os.path.isfile(skin_path),
                        "Skin should have downloaded")

        initial_mod_stat = os.path.getmtime(skin_path)
        initial_mod = datetime.datetime.fromtimestamp(initial_mod_stat)

        # import time
        # time.sleep(1)
        res = bpy.ops.mcprep.applyusernameskin(
            username='TheDuckCow',
            skip_redownload=True,
            new_material=True)
        self.assertEqual(res, {'FINISHED'})

        new_mod_stat = os.path.getmtime(skin_path)
        new_mod = datetime.datetime.fromtimestamp(new_mod_stat)

        # TODO: Verify if this is truly cross platform for last time modified.
        self.assertEqual(initial_mod, new_mod, "Should not have redownloaded")

    def test_download_username_list(self):
        usernames = ["theduckcow", "thekindkitten"]
        skin_path = bpy.context.scene.mcprep_skin_path

        for _user in usernames:
            _user_file = os.path.join(skin_path, f"{_user}.png")
            if os.path.isfile(_user_file):
                os.remove(_user_file)

        res = bpy.ops.mcprep.download_username_list(
            username_list=','.join(usernames),
            skip_redownload=True,
            convert_layout=True)
        self.assertEqual(res, {'FINISHED'})
        for _user in usernames:
            with self.subTest(_user):
                _user_file = os.path.join(skin_path, f"{_user}.png")
                self.assertTrue(os.path.isfile(_user_file),
                                f"{_user} file should have downloaded")

    def test_spawn_with_skin(self):
        bpy.ops.mcprep.reload_mobs()
        bpy.ops.mcprep.reload_skins()

        res = bpy.ops.mcprep.spawn_with_skin()
        self.assertEqual(res, {'FINISHED'})

        # test changing skin to file when no existing images/textres
        # test changing skin to file when existing material
        # test changing skin to file for both above, cycles and internal
        # test changing skin file for both above without, then with,
        #   then without again, normals + spec etc.


if __name__ == '__main__':
    unittest.main(exit=False)
