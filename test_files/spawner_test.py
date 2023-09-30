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
from mathutils import Vector

from MCprep_addon import util


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

    @unittest.skipIf(bpy.app.version < (3, 0),
                     "Geonodes not supported pre 3.0")
    def test_geonode_effect_spawner(self):
        scn_props = bpy.context.scene.mcprep_props
        etype = "geo_area"

        pre_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])
        bpy.ops.mcprep.reload_effects()
        post_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])

        self.assertEqual(pre_count, 0, "Should start with no effects loaded")
        self.assertGreater(
            post_count, 0, "Should have more effects loaded after reload")

        effect = [x for x in scn_props.effects_list if x.effect_type == etype][0]
        res = bpy.ops.mcprep.spawn_global_effect(effect_id=str(effect.index))
        self.assertEqual(res, {'FINISHED'}, "Did not end with finished result")

        # TODO: Further checks it actually loaded the effect.
        # Check that the geonode inputs are updated.
        obj = bpy.context.object
        self.assertTrue(obj, "Geo node added object not selected")

        geo_nodes = [mod for mod in obj.modifiers if mod.type == "NODES"]
        self.assertTrue(geo_nodes, "No geonode modifier found")

        # Now validate that one of the settings was updated.
        # TODO: example where we assert the active effect `subpath` is non empty

    def test_particle_area_effect_spawner(self):
        """Test the particle area variant of effect spawning works."""
        scn_props = bpy.context.scene.mcprep_props
        etype = "particle_area"

        pre_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])
        bpy.ops.mcprep.reload_effects()
        post_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])

        self.assertEqual(pre_count, 0, "Should start with no effects loaded")
        self.assertGreater(
            post_count, 0, "Should have more effects loaded after reload")

        effect = [x for x in scn_props.effects_list if x.effect_type == etype][0]
        res = bpy.ops.mcprep.spawn_global_effect(effect_id=str(effect.index))
        self.assertEqual(res, {'FINISHED'}, "Did not end with finished result")

        # TODO: Further checks it actually loaded the effect.

    def test_collection_effect_spawner(self):
        """Test the collection variant of effect spawning works."""
        scn_props = bpy.context.scene.mcprep_props
        etype = "collection"

        pre_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])
        bpy.ops.mcprep.reload_effects()
        post_count = len([
            x for x in scn_props.effects_list if x.effect_type == etype])

        self.assertEqual(pre_count, 0, "Should start with no effects loaded")
        self.assertGreater(
            post_count, 0, "Should have more effects loaded after reload")

        init_objs = list(bpy.data.objects)

        effect = [x for x in scn_props.effects_list if x.effect_type == etype][0]
        res = bpy.ops.mcprep.spawn_instant_effect(
            effect_id=str(effect.index), frame=2)
        self.assertEqual(res, {'FINISHED'}, "Did not end with finished result")

        final_objs = list(bpy.data.objects)
        new_objs = list(set(final_objs) - set(init_objs))
        self.assertGreater(len(new_objs), 0, "didn't crate new objects")
        self.assertTrue(
            bpy.context.object in new_objs, "Selected obj is not a new object")

        is_empty = bpy.context.object.type == 'EMPTY'
        is_coll_inst = bpy.context.object.instance_type == 'COLLECTION'
        self.assertFalse(
            not is_empty or not is_coll_inst,
            "Didn't end up with selected collection instance")
        # TODO: Further checks it actually loaded the effect.


class ModelSpawnerTest(BaseSpawnerTest):
    """ModelSpawning-related tests."""

    def test_model_spawner(self):
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
        post_objs = list(bpy.data.objects)

        self.assertGreater(len(post_objs), len(pre_objs), "No models spawned")
        self.assertEqual(len(post_objs), len(pre_objs) + 1,
                         "More than one model spawned")

        # Test that materials were properly added.
        new_objs = list(set(post_objs) - set(pre_objs))
        model = new_objs[0]
        self.assertTrue(model.active_material, "No material on model")


class EntitySpawnerTest(BaseSpawnerTest):
    """EntitySpawning-related tests."""

    def test_entity_spawner(self):
        scn_props = bpy.context.scene.mcprep_props

        pre_count = len(scn_props.entity_list)
        self.assertEqual(pre_count, 0,
                         "Should have opened new file with unloaded assets")
        bpy.ops.mcprep.reload_entities()
        post_count = len(scn_props.entity_list)

        self.assertGreater(post_count, 5, "Too few entities loaded")

        # spawn with whatever default index
        pre_objs = len(bpy.data.objects)
        bpy.ops.mcprep.entity_spawner()
        post_objs = len(bpy.data.objects)

        self.assertGreater(post_objs, pre_objs, "No entity spawned")
        # Test collection/group added
        # Test loading from file.


class MeshswapTest(BaseSpawnerTest):
    """Meshswap-related tests."""

    def _import_world_with_settings(self, file: str):
        testdir = os.path.dirname(__file__)
        obj_path = os.path.join(testdir, file)

        self.assertTrue(os.path.isfile(obj_path),
                        f"Obj file missing: {obj_path}, {file}")
        res = bpy.ops.mcprep.import_world_split(filepath=obj_path)
        self.assertEqual(res, {'FINISHED'})
        self.assertGreater(len(bpy.data.objects), 50, "Should have many objs")
        self.assertGreater(
            len(bpy.data.materials), 50, "Should have many mats")

    def _meshswap_util(self, mat_name: str) -> str:
        """Run meshswap on the first object with found mat_name"""
        if mat_name not in bpy.data.materials:
            return "Not a material: " + mat_name
        print("\nAttempt meshswap of " + mat_name)
        mat = bpy.data.materials[mat_name]

        obj = None
        for ob in bpy.data.objects:
            for slot in ob.material_slots:
                if slot and slot.material == mat:
                    obj = ob
                    break
            if obj:
                break
        if not obj:
            return "Failed to find obj for " + mat_name
        print("Found the object - " + obj.name)

        # Select only the object in question
        for ob in bpy.context.scene.objects:
            try:
                ob.select_set(False)
            except Exception:
                pass
        obj.select_set(True)
        res = bpy.ops.mcprep.meshswap()
        if res != {'FINISHED'}:
            return "Meshswap returned cancelled for " + mat_name
        return ""

    def test_meshswap_world_jmc(self):
        test_subpath = os.path.join("test_data", "jmc2obj_test_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.addon_prefs = util.get_user_preferences(bpy.context)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "jmc2obj")

        # known jmc2obj material names which we expect to be able to meshswap
        test_materials = [
            "torch",
            "fire",
            "lantern",
            "cactus_side",
            "vines",  # plural
            "enchant_table_top",
            "redstone_torch_on",
            "glowstone",
            "redstone_lamp_on",
            "pumpkin_front_lit",
            "sugarcane",
            "chest",
            "largechest",
            "sunflower_bottom",
            "sapling_birch",
            "white_tulip",
            "sapling_oak",
            "sapling_acacia",
            "sapling_jungle",
            "blue_orchid",
            "allium",
        ]

        for mat_name in test_materials:
            with self.subTest(mat_name):
                res = self._meshswap_util(mat_name)
                self.assertEqual("", res)

    def test_meshswap_world_mineways_separated(self):
        test_subpath = os.path.join(
            "test_data", "mineways_test_separated_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.addon_prefs = util.get_user_preferences(bpy.context)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "Mineways")

        # known mineways material names which we expect to be able to meshswap
        test_materials = [
            "grass",
            "torch",
            "fire_0",
            "MWO_chest_top",
            "MWO_double_chest_top_left",
            # "lantern", not in test object
            "cactus_side",
            "vine",  # singular
            "enchanting_table_top",
            # "redstone_torch_on", no separate "on" for Mineways separated exports
            "glowstone",
            "redstone_torch",
            "jack_o_lantern",
            "sugar_cane",
            "jungle_sapling",
            "dark_oak_sapling",
            "oak_sapling",
            "campfire_log",
            "white_tulip",
            "blue_orchid",
            "allium",
        ]

        for mat_name in test_materials:
            with self.subTest(mat_name):
                res = self._meshswap_util(mat_name)
                self.assertEqual("", res)

    def test_meshswap_world_mineways_combined(self):
        test_subpath = os.path.join(
            "test_data", "mineways_test_combined_1_15_2.obj")
        self._import_world_with_settings(file=test_subpath)
        self.addon_prefs = util.get_user_preferences(bpy.context)
        self.assertEqual(self.addon_prefs.MCprep_exporter_type, "Mineways")

        # known mineways material names which we expect to be able to meshswap
        test_materials = [
            "Sunflower",
            "Torch",
            "Redstone_Torch_(active)",
            "Lantern",
            "Dark_Oak_Sapling",
            "Sapling",  # should map to oak sapling
            "Birch_Sapling",
            "Cactus",
            "White_Tulip",
            "Vines",
            "Ladder",
            "Enchanting_Table",
            "Campfire",
            "Jungle_Sapling",
            "Red_Tulip",
            "Blue_Orchid",
            "Allium",
        ]

        for mat_name in test_materials:
            with self.subTest(mat_name):
                res = self._meshswap_util(mat_name)
                self.assertEqual("", res)

    def test_meshswap_spawner(self):
        scn_props = bpy.context.scene.mcprep_props
        bpy.ops.mcprep.reload_meshswap()
        self.assertGreater(len(scn_props.meshswap_list), 15,
                           "Too few meshswap assets available")

        # Add with make real = False
        res = bpy.ops.mcprep.meshswap_spawner(
            block='banner', method="collection", make_real=False)
        self.assertEqual(res, {'FINISHED'})

        # test doing two of the same one (first won't be cached, second will)
        # Add one with make real = True
        res = bpy.ops.mcprep.meshswap_spawner(
            block='fire', method="collection", make_real=True)
        self.assertEqual(res, {'FINISHED'})
        self.assertTrue('fire' in bpy.data.collections,
                        "Fire not in collections")
        self.assertTrue(len(bpy.context.selected_objects) > 0,
                        "Added made-real meshswap objects not selected")

        # Test that cache is properly used. Also test that the default
        # 'method=colleciton' is used.
        res = bpy.ops.mcprep.meshswap_spawner(block='fire', make_real=False)
        count = sum([1 for itm in bpy.data.collections if 'fire' in itm.name])
        self.assertEqual(
            count, 1, "Imported extra fire group, should have cached instead!")

        # test that added item ends up in location location=(1,2,3)
        loc = (1, 2, 3)
        bpy.ops.mcprep.meshswap_spawner(
            block='fire', method="collection", make_real=False, location=loc)
        self.assertTrue(
            bpy.context.object, "Added meshswap object not added as active")
        self.assertTrue(
            bpy.context.selected_objects, "Added meshswap object not selected")
        self.assertEqual(bpy.context.object.location,
                         Vector(loc),
                         "Location not properly applied")
        count = sum([1 for itm in bpy.data.collections if 'fire' in itm.name])
        self.assertEqual(
            count, 1, "Should have 1 fire groups exactly, did not cache")


if __name__ == '__main__':
    unittest.main(exit=False)
