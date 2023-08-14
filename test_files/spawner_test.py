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


class BaseSpawnerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def setUp(self):
        """Clears scene and data between each test"""
        bpy.ops.wm.read_homefile(app_template="", use_empty=True)


class MobSpawnerTest(BaseSpawnerTest):
    """Mob spawning related tests."""

    fast_mcmob_type: str = 'hostile/mobs - Rymdnisse.blend:/:endermite'

    def test_mob_spawner_append(self):
        """Spawn mobs, reload mobs, etc"""
        res = bpy.ops.mcprep.reload_mobs()
        self.assertEqual(res, {'FINISHED'})

        # sample don't specify mob, just load whatever is first
        res = bpy.ops.mcprep.mob_spawner(
            mcmob_type=self.fast_mcmob_type,
            toLink=False,  # By design for this subtest
            clearPose=False,
            prep_materials=False
        )
        self.assertEqual(res, {'FINISHED'})

        # spawn with linking
        # try changing the folder
        # try install mob and uninstall

    def test_mob_spawner_linked(self):
        res = bpy.ops.mcprep.reload_mobs()
        self.assertEqual(res, {'FINISHED'})
        res = bpy.ops.mcprep.mob_spawner(
            mcmob_type=self.fast_mcmob_type,
            toLink=True,  # By design for this subtest
            clearPose=False,
            prep_materials=False)
        self.assertEqual(res, {'FINISHED'})

    def test_mob_spawner_relocate(self):
        res = bpy.ops.mcprep.reload_mobs()
        # Set cursor location.
        for method in ["Clear", "Offset"]:  # Cursor tested above
            res = bpy.ops.mcprep.mob_spawner(
                mcmob_type=self.fast_mcmob_type,
                relocation=method,
                toLink=False,
                clearPose=True,
                prep_materials=False)
            self.assertEqual(res, {'FINISHED'})

    def test_bogus_mob_spawn(self):
        """Spawn mobs, reload mobs, etc"""
        res = bpy.ops.mcprep.reload_mobs()
        self.assertEqual(res, {'FINISHED'})

        # sample don't specify mob, just load whatever is first
        with self.assertRaises(TypeError):
            res = bpy.ops.mcprep.mob_spawner(
                mcmob_type="bogus"
            )

    # TODO: changing the folder, install / uninstall mob


class ItemSpawnerTest(BaseSpawnerTest):
    """Item spawning related tests."""

    def test_item_spawner(self):
        """Test item spawning and reloading"""
        scn_props = bpy.context.scene.mcprep_props

        pre_items = len(scn_props.item_list)
        bpy.ops.mcprep.reload_items()
        post_items = len(scn_props.item_list)

        self.assertEqual(pre_items, 0)
        self.assertGreater(post_items, 0, "No items loaded")
        self.assertGreater(post_items, 50,
                           "Too few items loaded, missing texturepack?")

        # spawn with whatever default index
        pre_objs = len(bpy.data.objects)
        bpy.ops.mcprep.spawn_item()
        post_objs = len(bpy.data.objects)

        self.assertGreater(post_objs, pre_objs, "No items spawned")
        self.assertEqual(post_objs, pre_objs + 1, "More than one item spawned")

        # test core useage on a couple of out of the box textures

        # test once with custom block
        # bpy.ops.mcprep.spawn_item_file(filepath=)

        # test with different thicknesses
        # test after changing resource pack
        # test that with an image of more than 1k pixels, it's truncated as expected
        # test with different

    def test_item_spawner_resize(self):
        """Test spawning an item that requires resizing."""
        bpy.ops.mcprep.reload_items()

        # Create a tmp file
        tmp_img = bpy.data.images.new("tmp_item_spawn", 32, 32, alpha=True)
        tmp_img.filepath = os.path.join(bpy.app.tempdir, "tmp_item.png")
        tmp_img.save()

        # spawn with whatever default index
        pre_objs = len(bpy.data.objects)
        bpy.ops.mcprep.spawn_item_file(
            max_pixels=16,
            filepath=tmp_img.filepath
        )
        post_objs = len(bpy.data.objects)

        self.assertGreater(post_objs, pre_objs, "No items spawned")
        self.assertEqual(post_objs, pre_objs + 1, "More than one item spawned")

        # Now check that this item spawned has the expected face count.
        obj = bpy.context.object
        polys = len(obj.data.polygons)
        self.assertEqual(16, polys, "Wrong pixel scaling applied")


class EffectsSpawnerTest(BaseSpawnerTest):
    """EffectsSpawning-related tests."""

    def test_particle_plane_effect_spawner(self):
        """Test the particle plane variant of effect spawning works."""
        filepath = os.path.join(
            bpy.context.scene.mcprep_texturepack_path,
            "assets", "minecraft", "textures", "block", "dirt.png")
        res = bpy.ops.mcprep.spawn_particle_planes(filepath=filepath)

        self.assertEqual(res, {'FINISHED'})

    def test_img_sequence_effect_spawner(self):
        """Ensures the image sequence variant of effect spawning works."""
        if bpy.app.version < (2, 81):
            self.skipTest("Disabled due to consistent crashing")

        scn_props = bpy.context.scene.mcprep_props
        etype = "img_seq"

        pre_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])
        bpy.ops.mcprep.reload_effects()
        post_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])

        self.assertEqual(pre_count, 0, "Should start with no effects loaded")
        self.assertGreater(post_count, 0,
                           "Should have more effects loaded after reload")

        # Find the one with at least 10 frames.
        effect_name = "Big smoke"
        effect = None
        for this_effect in scn_props.effects_list:
            if this_effect.effect_type != etype:
                continue
            if this_effect.name == effect_name:
                effect = this_effect

        self.assertTrue(
            effect, "Failed to fetch {} target effect".format(effect_name))

        res = bpy.ops.mcprep.spawn_instant_effect(effect_id=str(effect.index))
        self.assertEqual(res, {'FINISHED'})

        # TODO: Further checks it actually loaded the effect.


class ModelSpawnerTest(BaseSpawnerTest):
    """ModelSpawning-related tests."""

    def model_spawner(self):
        """Test model spawning and reloading"""
        scn_props = bpy.context.scene.mcprep_props

        pre_count = len(scn_props.model_list)
        res = bpy.ops.mcprep.reload_models()
        self.assertEqual(res, {'FINISHED'})
        post_count = len(scn_props.model_list)

        self.assertEqual(pre_count, 0,
                         "Should have opened new file with unloaded assets")
        self.assertGreater(post_count, 0, "No models loaded")
        self.assertGreater(post_count, 50,
                           "Too few models loaded, missing texturepack?")

        # spawn with whatever default index
        pre_objs = list(bpy.data.objects)
        res = bpy.ops.mcprep.spawn_model(
            filepath=scn_props.model_list[scn_props.model_list_index].filepath)
        self.assertEqual(res, {'FINISHED'})
        post_objs = bpy.data.objects

        self.assertGreater(post_objs, pre_objs, "No models spawned")
        self.assertEqual(len(post_objs), len(pre_objs) + 1,
                         "More than one model spawned")

        # Test that materials were properly added.
        new_objs = list(set(post_objs) - set(pre_objs))
        model = new_objs[0]
        self.assertTrue(model.active_material, "No material on model")


if __name__ == '__main__':
    unittest.main(exit=False)
