# ##### MCprep #####
#
# Developed by Patrick W. Crawford, see more at
# http://theduckcow.com/dev/blender/MCprep
#
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


from contextlib import redirect_stdout
import filecmp
import importlib
import io
import os
import shutil
import sys
import tempfile
import time
import traceback

import bpy
from mathutils import Vector

TEST_FILE = "test_results.tsv"

# -----------------------------------------------------------------------------
# Primary test loop
# -----------------------------------------------------------------------------


class mcprep_testing():
	# {status}, func, prefunc caller (reference only)

	def __init__(self):
		self.suppress = True  # hold stdout
		self.test_status = {}  # {func.__name__: {"check":-1, "res":-1,0,1}}
		self.test_cases = [
			self.spawn_mob,
			self.spawn_mob_linked,
			self.check_blend_eligible,
			self.check_blend_eligible_middle,
			self.check_blend_eligible_real,
			self.change_skin,
			self.import_world_split,
			self.import_world_fail,
			self.import_jmc2obj,
			self.import_mineways_separated,
			self.import_mineways_combined,
			self.name_generalize,
			self.canonical_name_no_none,
			self.canonical_test_mappings,
			self.meshswap_spawner,
			self.meshswap_jmc2obj,
			self.meshswap_mineways_separated,
			self.meshswap_mineways_combined,
			self.detect_desaturated_images,
			self.detect_extra_passes,
			self.find_missing_images_cycles,
			self.qa_meshswap_file,
			self.item_spawner,
			self.item_spawner_resize,
			self.entity_spawner,
			self.model_spawner,
			self.geonode_effect_spawner,
			self.particle_area_effect_spawner,
			self.collection_effect_spawner,
			self.img_sequence_effect_spawner,
			self.particle_plane_effect_spawner,
			self.sync_materials,
			self.sync_materials_link,
			self.load_material,
			self.uv_transform_detection,
			self.uv_transform_no_alert,
			self.uv_transform_combined_alert,
			self.world_tools,
			self.test_enable_obj_importer,
			self.qa_effects,
			self.qa_rigs,
			self.convert_mtl_simple,
			self.convert_mtl_skip,
		]
		self.run_only = None  # Name to give to only run this test

		self.mcprep_json = {}

	def run_all_tests(self):
		"""For use in command line mode, run all tests and checks"""
		if self.run_only and self.run_only not in [tst.__name__ for tst in self.test_cases]:
			print("{}No tests ran!{} Test function not found: {}".format(
				COL.FAIL, COL.ENDC, self.run_only))

		for test in self.test_cases:
			if self.run_only and test.__name__ != self.run_only:
				continue
			self.mcrprep_run_test(test)

		failed_tests = [
			tst for tst in self.test_status
			if self.test_status[tst]["check"] < 0]
		passed_tests = [
			tst for tst in self.test_status
			if self.test_status[tst]["check"] > 0]

		print("\n{}COMPLETED, {} passed and {} failed{}".format(
			COL.HEADER,
			len(passed_tests), len(failed_tests),
			COL.ENDC))
		if passed_tests:
			print("{}Passed tests:{}".format(COL.OKGREEN, COL.ENDC))
			print("\t" + ", ".join(passed_tests))
		if failed_tests:
			print("{}Failed tests:{}".format(COL.FAIL, COL.ENDC))
			for tst in self.test_status:
				if self.test_status[tst]["check"] > 0:
					continue
				ert = suffix_chars(self.test_status[tst]["res"], 70)
				print("\t{}{}{}: {}".format(COL.UNDERLINE, tst, COL.ENDC, ert))

		# indicate if all tests passed for this blender version
		if not failed_tests:
			with open(TEST_FILE, 'a') as tsv:
				tsv.write("{}\t{}\t-\n".format(bpy.app.version, "ALL PASSED"))

	def write_placeholder(self, test_name):
		"""Append placeholder, presuming if not changed then blender crashed"""
		with open(TEST_FILE, 'a') as tsv:
			tsv.write("{}\t{}\t-\n".format(
				bpy.app.version, "CRASH during " + test_name))

	def update_placeholder(self, test_name, test_failure):
		"""Update text of (if error) or remove placeholder row of file"""
		with open(TEST_FILE, 'r') as tsv:
			contents = tsv.readlines()

		if not test_failure:  # None or ""
			contents = contents[:-1]
		else:
			this_failure = "{}\t{}\t{}\n".format(
				bpy.app.version, test_name, suffix_chars(test_failure, 20))
			contents[-1] = this_failure
		with open(TEST_FILE, 'w') as tsv:
			for row in contents:
				tsv.write(row)

	def mcrprep_run_test(self, test_func):
		"""Run a single MCprep test"""
		print("\n{}Testing {}{}".format(COL.HEADER, test_func.__name__, COL.ENDC))
		self.write_placeholder(test_func.__name__)
		self._clear_scene()
		try:
			if self.suppress:
				stdout = io.StringIO()
				with redirect_stdout(stdout):
					res = test_func()
			else:
				res = test_func()
			if not res:
				print("\t{}TEST PASSED{}".format(COL.OKGREEN, COL.ENDC))
				self.test_status[test_func.__name__] = {"check": 1, "res": res}
			else:
				print("\t{}TEST FAILED:{}".format(COL.FAIL, COL.ENDC))
				print("\t" + res)
				self.test_status[test_func.__name__] = {"check": -1, "res": res}
		except Exception:
			print("\t{}TEST FAILED{}".format(COL.FAIL, COL.ENDC))
			print(traceback.format_exc())  # other info, e.g. line number/file
			res = traceback.format_exc()
			self.test_status[test_func.__name__] = {"check": -1, "res": res}
		# print("\tFinished test {}".format(test_func.__name__))
		self.update_placeholder(test_func.__name__, res)

	def setup_env_paths(self):
		"""Adds the MCprep installed addon path to sys for easier importing."""
		to_add = None

		for base in bpy.utils.script_paths():
			init = os.path.join(base, "addons", "MCprep_addon", "__init__.py")
			if os.path.isfile(init):
				to_add = init
				break
		if not to_add:
			raise Exception("Could not add the environment path for direct importing")

		# add to path and bind so it can use relative improts (3.5 trick)
		spec = importlib.util.spec_from_file_location("MCprep", to_add)
		module = importlib.util.module_from_spec(spec)
		sys.modules[spec.name] = module
		spec.loader.exec_module(module)

		from MCprep import conf
		conf.env = conf.MCprepEnv()

	def get_mcprep_path(self):
		"""Returns the addon basepath installed in this blender instance"""
		for base in bpy.utils.script_paths():
			init = os.path.join(
				base, "addons", "MCprep_addon")  # __init__.py folder
			if os.path.isdir(init):
				return init
		return None

	# -----------------------------------------------------------------------------
	# Testing utilities, not tests themselves (ie assumed to work)
	# -----------------------------------------------------------------------------

	def _clear_scene(self):
		"""Clear scene and data without printouts"""
		# if not self.suppress:
		# stdout = io.StringIO()
		# with redirect_stdout(stdout):
		bpy.ops.wm.read_homefile(app_template="", use_empty=True)

	def _add_character(self):
		"""Add a rigged character to the scene, specifically Alex"""
		bpy.ops.mcprep.reload_mobs()
		# mcmob_type='player/Simple Rig - Boxscape-TheDuckCow.blend:/:Simple Player'
		# mcmob_type='player/Alex FancyFeet - TheDuckCow & VanguardEnni.blend:/:alex'
		# Formatting os.path.sep below required for windows support.
		mcmob_type = 'hostile{}mobs - Rymdnisse.blend:/:silverfish'.format(
			os.path.sep)
		bpy.ops.mcprep.mob_spawner(mcmob_type=mcmob_type)

	def _import_jmc2obj_full(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "jmc2obj", "jmc2obj_test_1_15_2.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _import_mineways_separated(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(
			testdir, "mineways", "separated_textures",
			"mineways_test_separated_1_15_2.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _import_mineways_combined(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(
			testdir, "mineways", "combined_textures",
			"mineways_test_combined_1_15_2.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _create_canon_mat(self, canon=None, test_pack=False):
		"""Creates a material that should be recognized"""
		name = canon if canon else "dirt"
		mat = bpy.data.materials.new(name)
		mat.use_nodes = True
		img_node = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
		if canon and not test_pack:
			base = self.get_mcprep_path()
			filepath = os.path.join(
				base, "MCprep_resources",
				"resourcepacks", "mcprep_default", "assets", "minecraft", "textures",
				"block", canon + ".png")
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

	def _set_test_mcprep_texturepack_path(self, reset=False):
		"""Assigns or resets the local texturepack path."""
		testdir = os.path.dirname(__file__)
		path = os.path.join(testdir, "test_resource_pack")
		if not os.path.isdir(path):
			raise Exception("Failed to set test texturepack path")
		bpy.context.scene.mcprep_texturepack_path = path

	# Seems that infolog doesn't update in background mode
	def _get_last_infolog(self):
		"""Return back the latest info window log"""
		for txt in bpy.data.texts:
			bpy.data.texts.remove(txt)
		_ = bpy.ops.ui.reports_to_textblock()
		print("DEVVVV get last infolog:")
		for ln in bpy.data.texts['Recent Reports'].lines:
			print(ln.body)
		print("END printlines")
		return bpy.data.texts['Recent Reports'].lines[-1].body

	def _set_exporter(self, name):
		"""Sets the exporter name"""
		# from MCprep.util import get_user_preferences
		if name not in ['(choose)', 'jmc2obj', 'Mineways']:
			raise Exception('Invalid exporter set tyep')
		context = bpy.context
		if hasattr(context, "preferences"):
			prefs = context.preferences.addons.get("MCprep_addon", None)
		prefs.preferences.MCprep_exporter_type = name

	# -----------------------------------------------------------------------------
	# Operator unit tests
	# -----------------------------------------------------------------------------

	def find_missing_images_cycles(self):
		"""Find missing images from selected materials, cycles.

		Scenarios in which we find new textures
		One: material is empty with no image block assigned at all, though has
			image node and material is a canonical name
		Two: material has image block but the filepath is missing, find it
		Three: image is there, or image is packed; ie assume is fine (don't change)
		"""

		# first, import a material that has no filepath
		self._clear_scene()
		mat, node = self._create_canon_mat("sugar_cane")
		bpy.ops.mesh.primitive_plane_add()
		bpy.context.object.active_material = mat

		pre_path = node.image.filepath
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = node.image.filepath
		if pre_path != post_path:
			return "Pre/post path differed, should be the same"

		# now save the texturefile somewhere
		tmp_dir = tempfile.gettempdir()
		tmp_image = os.path.join(tmp_dir, "sugar_cane.png")
		shutil.copyfile(node.image.filepath, tmp_image)  # leave original intact

		# Test that path is unchanged even when with a non canonical path
		node.image.filepath = tmp_image
		if node.image.filepath != tmp_image:
			os.remove(tmp_image)
			return "fialed to setup test, node path not = " + tmp_image
		pre_path = node.image.filepath
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = node.image.filepath
		if pre_path != post_path:
			os.remove(tmp_image)
			return (
				"Pre/post path differed in tmp dir when there should have "
				"been no change: pre {} vs post {}".format(pre_path, post_path))

		# test that an empty node within a canonically named material is fixed
		pre_path = node.image.filepath
		node.image = None  # remove the image from block
		if node.image:
			os.remove(tmp_image)
			return "failed to setup test, image block still assigned"
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = node.image.filepath
		if not post_path:
			os.remove(tmp_image)
			return "No post path found, should have loaded file"
		elif post_path == pre_path:
			os.remove(tmp_image)
			return "Should have loaded image as new datablock from canon location"
		elif not os.path.isfile(post_path):
			os.remove(tmp_image)
			return "New path file does not exist"

		# test an image with broken texturepath is fixed for cannon material name

		# node.image.filepath = tmp_image # assert it's not the canonical path
		# pre_path = node.image.filepath # the original path before renaming
		# os.rename(tmp_image, tmp_image+"x")
		# if os.path.isfile(bpy.path.abspath(node.image.filepath)) or pre_path != node.image.filepath:
		# 	os.remove(pre_path)
		# 	os.remove(tmp_image+"x")
		# 	return "Failed to setup test, original file exists/img path updated"
		# bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		# post_path = node.image.filepath
		# if pre_path == post_path:
		# 	os.remove(tmp_image+"x")
		# 	return "Should have updated missing image to canonical, still is "+post_path
		# elif post_path != canonical_path:
		# 	os.remove(tmp_image+"x")
		# 	return "New path not canonical: "+post_path
		# os.rename(tmp_image+"x", tmp_image)

		# Example where we save and close the blend file, move the file,
		# and re-open. First, load the scene
		self._clear_scene()
		mat, node = self._create_canon_mat("sugar_cane")
		bpy.ops.mesh.primitive_plane_add()
		bpy.context.object.active_material = mat
		# Then, create the textures locally
		bpy.ops.file.pack_all()
		bpy.ops.file.unpack_all(method='USE_LOCAL')
		unpacked_path = bpy.path.abspath(node.image.filepath)
		# close and open, moving the file in the meantime
		save_tmp_file = os.path.join(tmp_dir, "tmp_test.blend")
		os.rename(unpacked_path, unpacked_path + "x")
		bpy.ops.wm.save_mainfile(filepath=save_tmp_file)
		bpy.ops.wm.open_mainfile(filepath=save_tmp_file)
		# now run the operator
		img = bpy.data.images['sugar_cane.png']
		pre_path = img.filepath
		if os.path.isfile(pre_path):
			os.remove(unpacked_path + "x")
			return "Failed to setup test for save/reopn move"
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		post_path = img.filepath
		if post_path == pre_path:
			os.remove(unpacked_path + "x")
			return "Did not change path from " + pre_path
		elif not os.path.isfile(post_path):
			os.remove(unpacked_path + "x")
			return "File for blend reloaded image does not exist: {}".format(
				node.image.filepath)
		os.remove(unpacked_path + "x")

		# address the example of sugar_cane.png.001 not being detected as canonical
		# as a front-end name (not image file)
		self._clear_scene()
		mat, node = self._create_canon_mat("sugar_cane")
		bpy.ops.mesh.primitive_plane_add()
		bpy.context.object.active_material = mat

		pre_path = node.image.filepath
		node.image = None  # remove the image from block
		mat.name = "sugar_cane.png.001"
		if node.image:
			os.remove(tmp_image)
			return "failed to setup test, image block still assigned"
		bpy.ops.mcprep.replace_missing_textures(animateTextures=False)
		if not node.image:
			os.remove(tmp_image)
			return "Failed to load new image within mat named .png.001"
		post_path = node.image.filepath
		if not post_path:
			os.remove(tmp_image)
			return "No image loaded for " + mat.name
		elif not os.path.isfile(node.image.filepath):
			return "File for loaded image does not exist: " + node.image.filepath

		# Example running with animateTextures too

		# check on image that is packed or not, or packed but no data
		os.remove(tmp_image)

	def spawn_mob(self):
		"""Spawn mobs, reload mobs, etc"""
		self._clear_scene()
		self._add_character()  # run the utility as it's own sort of test

		self._clear_scene()
		bpy.ops.mcprep.reload_mobs()

		# sample don't specify mob, just load whatever is first
		bpy.ops.mcprep.mob_spawner()

		# spawn with linking
		# try changing the folder
		# try install mob and uninstall

	def spawn_mob_linked(self):
		self._clear_scene()
		bpy.ops.mcprep.reload_mobs()
		bpy.ops.mcprep.mob_spawner(toLink=True)

	def check_blend_eligible(self):
		from MCprep.spawner import spawn_util
		fake_base = "MyMob - by Person"

		suffix_new = " pre9.0.0"  # Force active blender instance as older
		suffix_old = " pre1.0.0"  # Force active blender instance as newer.

		p_none = fake_base + ".blend"
		p_new = fake_base + suffix_new + ".blend"
		p_old = fake_base + suffix_old + ".blend"
		rando = "rando_name" + suffix_old + ".blend"

		# Check where input file is the "non-versioned" one.

		res = spawn_util.check_blend_eligible(p_none, [p_none, rando])
		if res is not True:
			return "Should have been true even if rando has suffix"

		res = spawn_util.check_blend_eligible(p_none, [p_none, p_old])
		if res is not True:
			return "Should be true as curr blend eligible and checked latest"

		res = spawn_util.check_blend_eligible(p_none, [p_none, p_new])
		if res is not False:
			print(p_none, p_new, res)
			return "Should be false as curr blend not eligible and checked latest"

		# Now check if input is a versioned file.

		res = spawn_util.check_blend_eligible(p_new, [p_none, p_new])
		if res is not True:
			return "Should have been true since we are below min blender"

		res = spawn_util.check_blend_eligible(p_old, [p_none, p_old])
		if res is not False:
			return "Should have been false since we are above this min blender"

	def check_blend_eligible_middle(self):
		# Warden-like example, where we have equiv of pre2.80, pre3.0, and
		# live blender 3.0+ (presuming we want to test a 2.93-like user)
		from MCprep.spawner import spawn_util
		fake_base = "WardenExample"

		# Assume the "current" version of blender is like 9.1
		# To make test not be flakey, actual version of blender can be anything
		# in range of 2.7.0 upwards to 8.999.
		suffix_old = " pre2.7.0"  # Force active blender instance as older.
		suffix_mid = " pre9.0.0"  # Force active blender instance as older.
		suffix_new = ""  # presume "latest" version

		p_old = fake_base + suffix_old + ".blend"
		p_mid = fake_base + suffix_mid + ".blend"
		p_new = fake_base + suffix_new + ".blend"

		# Test in order
		filelist = [p_old, p_mid, p_new]

		res = spawn_util.check_blend_eligible(p_old, filelist)
		if res is True:
			return "Older file should not match (in order)"
		res = spawn_util.check_blend_eligible(p_mid, filelist)
		if res is not True:
			return "Mid file SHOULD match (in order)"
		res = spawn_util.check_blend_eligible(p_new, filelist)
		if res is True:
			return "Newer file should not match (in order)"

		# Test out of order
		filelist = [p_mid, p_new, p_old]

		res = spawn_util.check_blend_eligible(p_old, filelist)
		if res is True:
			return "Older file should not match (out of order)"
		res = spawn_util.check_blend_eligible(p_mid, filelist)
		if res is not True:
			return "Mid file SHOULD match (out of order)"
		res = spawn_util.check_blend_eligible(p_new, filelist)
		if res is True:
			return "Newer file should not match (out of order)"

	def check_blend_eligible_real(self):
		# This order below matches a user's who was encountering an error
		# (the actual in-memory python list order)
		riglist = [
			"bee - Boxscape.blend",
			"Blaze - Trainguy.blend",
			"Cave Spider - Austin Prescott.blend",
			"creeper - TheDuckCow.blend",
			"drowned - HissingCreeper-thefunnypie2.blend",
			"enderman - Trainguy.blend",
			"Ghast - Trainguy.blend",
			"guardian - Trainguy.blend",
			"hostile - boxscape.blend",
			"illagers - Boxscape.blend",
			"mobs - Rymdnisse.blend",
			"nether hostile - Boxscape.blend",
			"piglin zombified piglin - Boxscape.blend",
			"PolarBear - PixelFrosty.blend",
			"ravager - Boxscape.blend",
			"Shulker - trainguy.blend",
			"Skeleton - Trainguy.blend",
			"stray - thefunnypie2.blend",
			"Warden - DigDanAnimates pre2.80.0.blend",
			"Warden - DigDanAnimates pre3.0.0.blend",
			"Warden - DigDanAnimates.blend",
			"Zombie - Hissing Creeper.blend",
			"Zombie Villager - Hissing Creeper-thefunnypie2.blend"
		]
		target_list = [
			"Warden - DigDanAnimates pre2.80.0.blend",
			"Warden - DigDanAnimates pre3.0.0.blend",
			"Warden - DigDanAnimates.blend",
		]

		from MCprep.spawner import spawn_util
		if bpy.app.version < (2, 80):
			correct = "Warden - DigDanAnimates pre2.80.0.blend"
		elif bpy.app.version < (3, 0):
			correct = "Warden - DigDanAnimates pre3.0.0.blend"
		else:
			correct = "Warden - DigDanAnimates.blend"

		for rig in target_list:
			res = spawn_util.check_blend_eligible(rig, riglist)
			if rig == correct:
				if res is not True:
					return "Did not pick {} as correct rig".format(rig)
			else:
				if res is True:
					return "Should have said {} was correct - not {}".format(correct, rig)

	def change_skin(self):
		"""Test scenarios for changing skin after adding a character."""
		self._clear_scene()

		bpy.ops.mcprep.reload_skins()
		skin_ind = bpy.context.scene.mcprep_skins_list_index
		skin_item = bpy.context.scene.mcprep_skins_list[skin_ind]
		tex_name = skin_item['name']
		skin_path = os.path.join(bpy.context.scene.mcprep_skin_path, tex_name)

		status = 'fail'
		try:
			_ = bpy.ops.mcprep.applyskin(
				filepath=skin_path,
				new_material=False)
		except RuntimeError as e:
			if 'No materials found to update' in str(e):
				status = 'success'  # expect to fail when nothing selected
		if status == 'fail':
			return "Should have failed to skin swap with no objects selected"

		# now run on a real test character, with 1 material and 2 objects
		self._add_character()

		pre_mats = len(bpy.data.materials)
		bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=False)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats:  # should be unchanged
			return (
				"change_skin.mat counts diff despit no new mat request, "
				"{} before and {} after".format(pre_mats, post_mats))

		# do counts of materials before and after to ensure they match
		pre_mats = len(bpy.data.materials)
		bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=True)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats * 2:  # should exactly double since in new scene
			return (
				"change_skin.mat counts diff mat counts, "
				"{} before and {} after".format(pre_mats, post_mats))

		pre_mats = len(bpy.data.materials)

		# not diff operator name, this is popup browser
		bpy.ops.mcprep.skin_swapper(
			filepath=skin_path,
			new_material=False)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats:  # should be unchanged
			return (
				"change_skin.mat counts differ even though should be same, "
				"{} before and {} after".format(pre_mats, post_mats))

		# TODO: Add test for when there is a bogus filename, responds with
		# Image file not found in err

		# capture info or recent out?
		# check that username was there before or not
		bpy.ops.mcprep.applyusernameskin(
			username='TheDuckCow',
			skip_redownload=False,
			new_material=True)

		# check that timestamp of last edit of file was longer ago than above cmd

		bpy.ops.mcprep.applyusernameskin(
			username='TheDuckCow',
			skip_redownload=True,
			new_material=True)

		# test deleting username skin and that file is indeed deleted
		# and not in list anymore

		# bpy.ops.mcprep.applyusernameskin(
		# 	username='TheDuckCow',
		# 	skip_redownload=True,
		# 	new_material=True)

		# test that the file was added back

		bpy.ops.mcprep.spawn_with_skin()
		# test changing skin to file when no existing images/textres
		# test changing skin to file when existing material
		# test changing skin to file for both above, cycles and internal
		# test changing skin file for both above without, then with,
		#   then without again, normals + spec etc.
		return

	def import_world_split(self):
		"""Test that imported world has multiple objects"""
		self._clear_scene()

		pre_objects = len(bpy.data.objects)
		self._import_jmc2obj_full()
		post_objects = len(bpy.data.objects)
		if post_objects + 1 > pre_objects:
			print("Success, had {} objs, post import {}".format(
				pre_objects, post_objects))
			return
		elif post_objects + 1 == pre_objects:
			return "Only one new object imported"
		else:
			return "Nothing imported"

	def import_world_fail(self):
		"""Ensure loader fails if an invalid path is loaded"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "jmc2obj", "xx_jmc2obj_test_1_14_4.obj")
		try:
			bpy.ops.mcprep.import_world_split(filepath=obj_path)
		except Exception as e:
			print("Failed, as intended: " + str(e))
			return
		return "World import should have returned an error"

	def import_materials_util(self, mapping_set):
		"""Reusable function for testing on different obj setups"""
		from MCprep.materials.generate import get_mc_canonical_name
		from MCprep.materials.generate import find_from_texturepack
		from MCprep import util

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

		print("Mapped: {}, unmapped: {}, unleveraged: {}".format(
			len(mapped), len(unmapped), len(unleveraged)))

		if len(unmapped):
			err = "Textures not mapped to json file"
			print(err)
			print(sorted(unmapped))
			print("")
			# return err
		if len(unleveraged) > 20:
			err = "Json file materials not found in obj test file, may need to update world"
			print(err)
			print(sorted(unleveraged))
			# return err

		if len(mapped) == 0:
			return "No materials mapped"
		elif mapping_set == "block_mapping_mineways" and len(mapped) > 75:
			# Known that the "combined" atlas texture of Mineways imports
			# has low coverge, and we're not doing anything about it.
			# but will at least capture if coverage gets *worse*.
			pass
		elif len(mapped) < len(unmapped):  # too many esp. for Mineways
			# not a very optimistic threshold, but better than none
			return "More materials unmapped than mapped"
		print("")

		# each element is [cannon_name, form], form is none if not matched
		mapped = [get_mc_canonical_name(mat.name) for mat in bpy.data.materials]

		# no matching canon name (warn)
		mats_not_canon = [itm[0] for itm in mapped if itm[1] is None]
		if mats_not_canon and mapping_set != "block_mapping_mineways":
			print("Non-canon material names found: ({})".format(len(mats_not_canon)))
			print(mats_not_canon)
			if len(mats_not_canon) > 30:  # arbitrary threshold
				return "Too many materials found without canonical name ({})".format(
					len(mats_not_canon))
		else:
			print("Confirmed - no non-canon images found")

		# affirm the correct mappings
		mats_no_packimage = [
			find_from_texturepack(itm[0]) for itm in mapped
			if itm[1] is not None]
		mats_no_packimage = [path for path in mats_no_packimage if path]
		print("Mapped paths: " + str(len(mats_no_packimage)))

		# could not resolve image from resource pack (warn) even though in mapping
		mats_no_packimage = [
			itm[0] for itm in mapped
			if itm[1] is not None and not find_from_texturepack(itm[0])]
		print("No resource images found for mapped items: ({})".format(
			len(mats_no_packimage)))
		print("These would appear to have cannon mappings, but then fail on lookup")

		# known number up front, e.g. chests, stone_slab_side, stone_slab_top
		if len(mats_no_packimage) > 5:
			return "Missing images for blocks specified in mcprep_data.json: {}".format(
				",".join(mats_no_packimage))

		# also test that there are not raw image names not in mapping list
		# but that otherwise could be added to the mapping list as file exists

	def import_jmc2obj(self):
		"""Checks that material names in output obj match the mapping file"""
		self._clear_scene()
		self._import_jmc2obj_full()

		res = self.import_materials_util("block_mapping_jmc")
		return res

	def import_mineways_separated(self):
		"""Checks Mineways (single-image) material name mapping to mcprep_data"""
		self._clear_scene()
		self._import_mineways_separated()

		res = self.import_materials_util("block_mapping_mineways")
		return res

	def import_mineways_combined(self):
		"""Checks Mineways (multi-image) material name mapping to mcprep_data"""
		self._clear_scene()
		self._import_mineways_combined()

		res = self.import_materials_util("block_mapping_mineways")
		return res

	def name_generalize(self):
		"""Tests the outputs of the generalize function"""
		from MCprep.util import nameGeneralize
		test_sets = {
			"ab": "ab",
			"table.001": "table",
			"table.100": "table",
			"table001": "table001",
			"fire_0": "fire_0",
			# "fire_0_0001.png":"fire_0", not current behavior, but desired?
			"fire_0_0001": "fire_0",
			"fire_0_0001.001": "fire_0",
			"fire_layer_1": "fire_layer_1",
			"cartography_table_side1": "cartography_table_side1"
		}
		errors = []
		for key in list(test_sets):
			res = nameGeneralize(key)
			if res != test_sets[key]:
				errors.append("{} converts to {} and should be {}".format(
					key, res, test_sets[key]))
			else:
				print("{}:{} passed".format(key, res))

		if errors:
			return "Generalize failed: " + ", ".join(errors)

	def canonical_name_no_none(self):
		"""Ensure that MC canonical name never returns none"""
		from MCprep.materials.generate import get_mc_canonical_name
		from MCprep.util import materialsFromObj
		self._clear_scene()
		self._import_jmc2obj_full()
		self._import_mineways_separated()
		self._import_mineways_combined()

		bpy.ops.object.select_all(action='SELECT')
		mats = materialsFromObj(bpy.context.selected_objects)
		canons = [[get_mc_canonical_name(mat.name)][0] for mat in mats]

		if None in canons:  # detect None response to canon input
			return "Canon returned none value"
		if '' in canons:
			return "Canon returned empty str value"

		# Ensure it never returns None
		in_str, _ = get_mc_canonical_name('')
		if in_str != '':
			return "Empty str should return empty string, not" + str(in_str)

		did_raise = False
		try:
			get_mc_canonical_name(None)
		except Exception:
			did_raise = True
		if not did_raise:
			return "None input SHOULD raise error"

		# TODO: patch conf.env.json_data["blocks"] used by addon if possible,
		# if this is transformed into a true py unit test. This will help
		# check against report (-MNGGQfGGTJRqoizVCer)

	def canonical_test_mappings(self):
		"""Test some specific mappings to ensure they return correctly."""
		from MCprep.materials.generate import get_mc_canonical_name

		misc = {
			".emit": ".emit",
		}
		jmc_to_canon = {
			"grass": "grass",
			"mushroom_red": "red_mushroom",
			# "slime": "slime_block",  # KNOWN jmc, need to address
		}
		mineways_to_canon = {}

		for map_type in [misc, jmc_to_canon, mineways_to_canon]:
			for key, val in map_type.items():
				res, mapped = get_mc_canonical_name(key)
				if res == val:
					continue
				return "Wrong mapping: {} mapped to {} ({}), not {}".format(
					key, res, mapped, val)

	def meshswap_util(self, mat_name):
		"""Run meshswap on the first object with found mat_name"""
		from MCprep.util import select_set

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

		bpy.ops.object.select_all(action='DESELECT')
		select_set(obj, True)
		res = bpy.ops.mcprep.meshswap()
		if res != {'FINISHED'}:
			return "Meshswap returned cancelled for " + mat_name

	def meshswap_spawner(self):
		"""Tests direct meshswap spawning"""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props
		bpy.ops.mcprep.reload_meshswap()
		if not scn_props.meshswap_list:
			return "No meshswap assets loaded for spawning"
		elif len(scn_props.meshswap_list) < 15:
			return "Too few meshswap assets available"

		if bpy.app.version >= (2, 80):
			# Add with make real = False
			bpy.ops.mcprep.meshswap_spawner(
				block='banner', method="collection", make_real=False)

			# test doing two of the same one (first won't be cached, second will)
			# Add one with make real = True
			bpy.ops.mcprep.meshswap_spawner(
				block='fire', method="collection", make_real=True)
			if 'fire' not in bpy.data.collections:
				return "Fire not in collections"
			elif not bpy.context.selected_objects:
				return "Added made-real meshswap objects not selected"

			# Test that cache is properly used. Also test that the default
			# 'method=colleciton' is used, since that's the only mode of
			# support for meshswap spawner at the moment.
			bpy.ops.mcprep.meshswap_spawner(block='fire', make_real=False)
			if 'fire' not in bpy.data.collections:
				return "Fire not in collections"
			count = sum([1 for itm in bpy.data.collections if 'fire' in itm.name])
			if count != 1:
				return "Imported extra fire group, should have cached instead!"

			# test that added item ends up in location location=(1,2,3)
			loc = (1, 2, 3)
			bpy.ops.mcprep.meshswap_spawner(
				block='fire', method="collection", make_real=False, location=loc)
			if not bpy.context.object:
				return "Added meshswap object not added as active"
			elif not bpy.context.selected_objects:
				return "Added meshswap object not selected"
			if bpy.context.object.location != Vector(loc):
				return "Location not properly applied"
			count = sum([1 for itm in bpy.data.collections if 'fire' in itm.name])
			if count != 1:
				return "Should have 1 fire groups exactly, did not cache"
		else:
			# Add with make real = False
			bpy.ops.mcprep.meshswap_spawner(
				block='banner', method="collection", make_real=False)

			# test doing two of the same one (first won't be cached, second will)
			# Add one with make real = True
			bpy.ops.mcprep.meshswap_spawner(
				block='fire', method="collection", make_real=True)
			if 'fire' not in bpy.data.groups:
				return "Fire not in groups"
			elif not bpy.context.selected_objects:
				return "Added made-real meshswap objects not selected"

			bpy.ops.mcprep.meshswap_spawner(
				block='fire', method="collection", make_real=False)
			if 'fire' not in bpy.data.groups:
				return "Fire not in groups"
			count_torch = sum([1 for itm in bpy.data.groups if 'fire' in itm.name])
			if count_torch != 1:
				return "Imported extra fire group, should have cached instead!"

			# test that added item ends up in location location=(1,2,3)
			loc = (1, 2, 3)
			bpy.ops.mcprep.meshswap_spawner(
				block='fire', method="collection", make_real=False, location=loc)
			if not bpy.context.object:
				return "Added meshswap object not added as active"
			elif not bpy.context.selected_objects:
				return "Added meshswap object not selected"
			if bpy.context.object.location != Vector(loc):
				return "Location not properly applied"

	def meshswap_jmc2obj(self):
		"""Tests jmc2obj meshswapping"""
		self._clear_scene()
		self._import_jmc2obj_full()
		self._set_exporter('jmc2obj')

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

		errors = []
		for mat_name in test_materials:
			try:
				res = self.meshswap_util(mat_name)
			except Exception as err:
				err = str(err)
				if len(err) > 15:
					res = err[:15].replace("\n", "")
				else:
					res = err
			if res:
				errors.append(mat_name + ":" + res)
		if errors:
			return "Meshswap failed: " + ", ".join(errors)

	def meshswap_mineways_separated(self):
		"""Tests jmc2obj meshswapping"""
		self._clear_scene()
		self._import_mineways_separated()
		self._set_exporter('Mineways')

		# known Mineways (separated) material names expected for meshswap
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

		errors = []
		for mat_name in test_materials:
			try:
				res = self.meshswap_util(mat_name)
			except Exception as err:
				err = str(err)
				if len(err) > 15:
					res = err[:15].replace("\n", "")
				else:
					res = err
			if res:
				errors.append(mat_name + ":" + res)
		if errors:
			return "Meshswap failed: " + ", ".join(errors)

	def meshswap_mineways_combined(self):
		"""Tests jmc2obj meshswapping"""
		self._clear_scene()
		self._import_mineways_combined()
		self._set_exporter('Mineways')

		# known Mineways (separated) material names expected for meshswap
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

		errors = []
		for mat_name in test_materials:
			try:
				res = self.meshswap_util(mat_name)
			except Exception as err:
				err = str(err)
				if len(err) > 15:
					res = err[:15].replace("\n", "")
				else:
					res = err
			if res:
				errors.append(mat_name + ":" + res)
		if errors:
			return "Meshswap combined failed: " + ", ".join(errors)

	def detect_desaturated_images(self):
		"""Checks the desaturate images function works"""
		from MCprep.materials.generate import is_image_grayscale

		base = self.get_mcprep_path()
		print("Raw base", base)
		base = os.path.join(
			base, "MCprep_resources", "resourcepacks", "mcprep_default",
			"assets", "minecraft", "textures", "block")
		print("Remapped base: ", base)

		# known images that ARE desaturated:
		desaturated = [
			"grass_block_top.png"
		]
		saturated = [
			"grass_block_side.png",
			"glowstone.png"
		]

		for tex in saturated:
			img = bpy.data.images.load(os.path.join(base, tex))
			if not img:
				raise Exception('Failed to load img ' + str(tex))
			if is_image_grayscale(img) is True:
				raise Exception(
					'Image {} detected as grayscale, should be saturated'.format(tex))
		for tex in desaturated:
			img = bpy.data.images.load(os.path.join(base, tex))
			if not img:
				raise Exception('Failed to load img ' + str(tex))
			if is_image_grayscale(img) is False:
				raise Exception(
					'Image {} detected as saturated - should be grayscale'.format(tex))

		# test that it is caching as expected.. by setting a false
		# value for cache flag and seeing it's returning the property value

	def detect_extra_passes(self):
		"""Ensure only the correct pbr file matches are found for input file"""
		from MCprep.materials.generate import find_additional_passes

		tmp_dir = tempfile.gettempdir()

		# physically generate these empty files, then delete
		tmp_files = [
			"oak_log_top.png",
			"oak_log_top-s.png",
			"oak_log_top_n.png",
			"oak_log.jpg",
			"oak_log_s.jpg",
			"oak_log_n.jpeg",
			"oak_log_disp.jpeg",
			"stonecutter_saw.tiff",
			"stonecutter_saw n.tiff"
		]

		for tmp in tmp_files:
			fname = os.path.join(tmp_dir, tmp)
			with open(fname, 'a'):
				os.utime(fname)

		def cleanup():
			"""Failsafe delete files before raising error within test method"""
			for tmp in tmp_files:
				try:
					os.remove(os.path.join(tmp_dir, tmp))
				except Exception:
					pass

		# assert setup was successful
		for tmp in tmp_files:
			if os.path.isfile(os.path.join(tmp_dir, tmp)):
				continue
			cleanup()
			raise Exception("Failed to generate test empty files")

		# the test cases; input is diffuse, output is the whole dict
		cases = [
			{
				"diffuse": os.path.join(tmp_dir, "oak_log_top.png"),
				"specular": os.path.join(tmp_dir, "oak_log_top-s.png"),
				"normal": os.path.join(tmp_dir, "oak_log_top_n.png"),
			}, {
				"diffuse": os.path.join(tmp_dir, "oak_log.jpg"),
				"specular": os.path.join(tmp_dir, "oak_log_s.jpg"),
				"normal": os.path.join(tmp_dir, "oak_log_n.jpeg"),
				"displace": os.path.join(tmp_dir, "oak_log_disp.jpeg"),
			}, {
				"diffuse": os.path.join(tmp_dir, "stonecutter_saw.tiff"),
				"normal": os.path.join(tmp_dir, "stonecutter_saw n.tiff"),
			}
		]

		for test in cases:
			res = find_additional_passes(test["diffuse"])
			if res != test:
				cleanup()
				# for debug readability, basepath everything
				for itm in res:
					res[itm] = os.path.basename(res[itm])
				for itm in test:
					test[itm] = os.path.basename(test[itm])
				raise Exception("Mismatch for set {}: got {} but expected {}".format(
					test["diffuse"], res, test))

		# test other cases intended to fail
		res = find_additional_passes(os.path.join(tmp_dir, "not_a_file.png"))
		if res != {}:
			cleanup()
			raise Exception("Fake file should not have any return")

	def _qa_helper(self, basepath, allow_packed):
		"""File used to help QC an open blend file."""

		# bpy.ops.file.make_paths_relative() instead of this, do manually.
		different_base = []
		not_relative = []
		missing = []
		for img in bpy.data.images:
			if not img.filepath:
				continue
			abspath = os.path.abspath(bpy.path.abspath(img.filepath))
			if not abspath.startswith(basepath):
				if allow_packed is True and img.packed_file:
					pass
				else:
					different_base.append(os.path.basename(img.filepath))
			if img.filepath != bpy.path.relpath(img.filepath):
				not_relative.append(os.path.basename(img.filepath))
			if not os.path.isfile(abspath):
				if allow_packed is True and img.packed_file:
					pass
				else:
					missing.append(img.name)

		if len(different_base) > 50:
			return "Wrong basepath for image filepath comparison!"
		if different_base:
			return "Found {} images with different basepath from file: {}".format(
				len(different_base), ", ".join(different_base))
		if not_relative:
			return "Found {} non relative img files: {}".format(
				len(not_relative), ", ".join(not_relative))
		if missing:
			return "Found {} img with missing source files: {}".format(
				len(missing), ", ".join(missing))

	def qa_meshswap_file(self):
		"""Open the meshswap file, assert there are no relative paths"""
		basepath = os.path.join("MCprep_addon", "MCprep_resources")
		basepath = os.path.abspath(basepath)  # relative to the dev git folder
		blendfile = os.path.join(basepath, "mcprep_meshSwap.blend")
		if not os.path.isfile(blendfile):
			return blendfile + ": missing tests dir local meshswap file"
		bpy.ops.wm.open_mainfile(filepath=blendfile)
		# do NOT save this file!

		resp = self._qa_helper(basepath, allow_packed=False)
		if resp:
			return resp

		# detect any non canonical material names?? how to exclude?

		# Affirm that no materials have a principled node, should be basic only

	def item_spawner(self):
		"""Test item spawning and reloading"""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props

		pre_items = len(scn_props.item_list)
		bpy.ops.mcprep.reload_items()
		post_items = len(scn_props.item_list)

		if pre_items != 0:
			return "Should have opened new file with unloaded assets?"
		elif post_items == 0:
			return "No items loaded"
		elif post_items < 50:
			return "Too few items loaded, missing texturepack?"

		# spawn with whatever default index
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.spawn_item()
		post_objs = len(bpy.data.objects)

		if post_objs == pre_objs:
			return "No items spawned"
		elif post_objs > pre_objs + 1:
			return "More than one item spawned"

		# test core useage on a couple of out of the box textures

		# test once with custom block
		# bpy.ops.mcprep.spawn_item_file(filepath=)

		# test with different thicknesses
		# test after changing resource pack
		# test that with an image of more than 1k pixels, it's truncated as expected
		# test with different

	def item_spawner_resize(self):
		"""Test spawning an item that requires resizing."""
		self._clear_scene()
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

		if post_objs == pre_objs:
			return "No items spawned"
		elif post_objs > pre_objs + 1:
			return "More than one item spawned"

		# Now check that this item spawned has the expected face count.
		obj = bpy.context.object
		polys = len(obj.data.polygons)
		print("Poly's count: ", polys)
		if polys > 16:
			return "Didn't scale enough to fewer pixels, facecount: " + str(polys)
		elif polys < 16:
			return "Over-scaled down facecount: " + str(polys)

	def entity_spawner(self):
		"""Test entity spawning and reloading"""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props

		pre_count = len(scn_props.entity_list)
		bpy.ops.mcprep.reload_entities()
		post_count = len(scn_props.entity_list)

		if pre_count != 0:
			return "Should have opened new file with unloaded assets?"
		elif post_count == 0:
			return "No entities loaded"
		elif post_count < 5:
			return "Too few entities loaded ({}), missing texturepack?".format(
				post_count - pre_count)

		# spawn with whatever default index
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.entity_spawner()
		post_objs = len(bpy.data.objects)

		if post_objs == pre_objs:
			return "No entity spawned"

		# Test collection/group added
		# Test loading from file.

	def model_spawner(self):
		"""Test model spawning and reloading"""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props

		pre_count = len(scn_props.model_list)
		bpy.ops.mcprep.reload_models()
		post_count = len(scn_props.model_list)

		if pre_count != 0:
			return "Should have opened new file with unloaded assets?"
		elif post_count == 0:
			return "No models loaded"
		elif post_count < 50:
			return "Too few models loaded, missing texturepack?"

		# spawn with whatever default index
		pre_objs = list(bpy.data.objects)
		bpy.ops.mcprep.spawn_model(
			filepath=scn_props.model_list[scn_props.model_list_index].filepath)
		post_objs = bpy.data.objects

		if len(post_objs) == len(pre_objs):
			return "No models spawned"
		elif len(post_objs) > len(pre_objs) + 1:
			return "More than one model spawned"

		# Test that materials were properly added.
		new_objs = list(set(post_objs) - set(pre_objs))
		model = new_objs[0]
		if not model.active_material:
			return "No material on model"

		# TODO: fetch/check there being a texture.

		# Test collection/group added
		# Test loading from file.

	def geonode_effect_spawner(self):
		"""Test the geo node variant of effect spawning works."""
		if bpy.app.version < (3, 0):
			return  # Not supported before 3.0 anyways.
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props
		etype = "geo_area"

		pre_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])
		bpy.ops.mcprep.reload_effects()
		post_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])

		if pre_count != 0:
			return "Should start with no effects loaded"
		if post_count == 0:
			return "Should have more effects loaded after reload"

		effect = [x for x in scn_props.effects_list if x.effect_type == etype][0]
		res = bpy.ops.mcprep.spawn_global_effect(effect_id=str(effect.index))
		if res != {'FINISHED'}:
			return "Did not end with finished result"

		# TODO: Further checks it actually loaded the effect.
		# Check that the geonode inputs are updated.
		obj = bpy.context.object
		if not obj:
			return "Geo node added object not selected"

		geo_nodes = [mod for mod in obj.modifiers if mod.type == "NODES"]
		if not geo_nodes:
			return "No geonode modifier found"

		# Now validate that one of the settings was updated.
		# TODO: example where we assert the active effect `subpath` is non empty

	def particle_area_effect_spawner(self):
		"""Test the particle area variant of effect spawning works."""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props
		etype = "particle_area"

		pre_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])
		bpy.ops.mcprep.reload_effects()
		post_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])

		if pre_count != 0:
			return "Should start with no effects loaded"
		if post_count == 0:
			return "Should have more effects loaded after reload"

		effect = [x for x in scn_props.effects_list if x.effect_type == etype][0]
		res = bpy.ops.mcprep.spawn_global_effect(effect_id=str(effect.index))
		if res != {'FINISHED'}:
			return "Did not end with finished result"

		# TODO: Further checks it actually loaded the effect.

	def collection_effect_spawner(self):
		"""Test the collection variant of effect spawning works."""
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props
		etype = "collection"

		pre_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])
		bpy.ops.mcprep.reload_effects()
		post_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])

		if pre_count != 0:
			return "Should start with no effects loaded"
		if post_count == 0:
			return "Should have more effects loaded after reload"

		init_objs = list(bpy.data.objects)

		effect = [x for x in scn_props.effects_list if x.effect_type == etype][0]
		res = bpy.ops.mcprep.spawn_instant_effect(effect_id=str(effect.index), frame=2)
		if res != {'FINISHED'}:
			return "Did not end with finished result"

		final_objs = list(bpy.data.objects)
		new_objs = list(set(final_objs) - set(init_objs))
		if len(new_objs) == 0:
			return "didn't crate new objects"
		if bpy.context.object not in new_objs:
			return "Selected obj is not a new object"

		is_empty = bpy.context.object.type == 'EMPTY'
		is_coll_inst = bpy.context.object.instance_type == 'COLLECTION'
		if not is_empty or not is_coll_inst:
			return "Didn't end up with selected collection instance"

		# TODO: Further checks it actually loaded the effect.

	def img_sequence_effect_spawner(self):
		"""Test the image sequence variant of effect spawning works."""
		if bpy.app.version < (2, 81):
			return "Disabled due to consistent crashing"
		self._clear_scene()
		scn_props = bpy.context.scene.mcprep_props
		etype = "img_seq"

		pre_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])
		bpy.ops.mcprep.reload_effects()
		post_count = len([
			x for x in scn_props.effects_list if x.effect_type == etype])

		if pre_count != 0:
			return "Should start with no effects loaded"
		if post_count == 0:
			return "Should have more effects loaded after reload"

		# Find the one with at least 10 frames.
		effect_name = "Big smoke"
		effect = None
		for this_effect in scn_props.effects_list:
			if this_effect.effect_type != etype:
				continue
			if this_effect.name == effect_name:
				effect = this_effect

		if not effect:
			return "Failed to fetch {} target effect".format(effect_name)

		t0 = time.time()
		res = bpy.ops.mcprep.spawn_instant_effect(effect_id=str(effect.index))
		if res != {'FINISHED'}:
			return "Did not end with finished result"

		t1 = time.time()
		if t1 - t0 > 1.0:
			return "Spawning took over 1 second for sequence effect"

		# TODO: Further checks it actually loaded the effect.

	def particle_plane_effect_spawner(self):
		"""Test the particle plane variant of effect spawning works."""
		self._clear_scene()

		filepath = os.path.join(
			bpy.context.scene.mcprep_texturepack_path,
			"assets", "minecraft", "textures", "block", "dirt.png")
		res = bpy.ops.mcprep.spawn_particle_planes(filepath=filepath)

		if res != {'FINISHED'}:
			return "Did not end with finished result"

		# TODO: Further checks it actually loaded the effect.

	def world_tools(self):
		"""Test adding skies, prepping the world, etc"""
		from MCprep.world_tools import get_time_object

		# test with both engines (cycles+eevee, or cycles+internal)
		self._clear_scene()
		bpy.ops.mcprep.world()

		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_shader',
			# initial_time='8',
			add_clouds=True,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed partially to the side
		obj = get_time_object()
		if not obj:
			return "No detected MCprepHour controller (a)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_mesh',
			# initial_time='12',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down
		obj = get_time_object()
		if not obj:
			return "No detected MCprepHour controller (b)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_only',
			# initial_time='18',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down
		obj = get_time_object()
		if not obj:
			return "No detected MCprepHour controller (c)"

		self._clear_scene()
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_static_mesh',
			# initial_time='0',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# find the sun, ensure it's pointed straight down

		self._clear_scene()
		obj = get_time_object()
		if obj:
			return "Found MCprepHour controller, shouldn't be one (d)"
		pre_objs = len(bpy.data.objects)
		bpy.ops.mcprep.add_mc_sky(
			world_type='world_static_only',
			# initial_time='6',
			add_clouds=False,
			remove_existing_suns=True)
		post_objs = len(bpy.data.objects)
		if pre_objs >= post_objs:
			return "Nothing added"
		# test that it removes existing suns by first placing one, and then
		# affirming it's gone

	def sync_materials(self):
		"""Test syncing materials works"""
		self._clear_scene()

		# test empty case
		res = bpy.ops.mcprep.sync_materials(
			link=False,
			replace_materials=False,
			skipUsage=True)  # track here false to avoid error
		if res != {'CANCELLED'}:
			return "Should return cancel in empty scene"

		# test that the base test material is included as shipped
		bpy.ops.mesh.primitive_plane_add()
		obj = bpy.context.object
		if bpy.app.version >= (2, 80):
			obj.select_set(True)
		else:
			obj.select = True

		new_mat = bpy.data.materials.new("mcprep_test")
		obj.active_material = new_mat

		init_mats = bpy.data.materials[:]
		init_len = len(bpy.data.materials)
		res = bpy.ops.mcprep.sync_materials(
			link=False,
			replace_materials=False)
		if res != {'FINISHED'}:
			return "Should return finished with test file"

		# check there is another material now
		imported = set(bpy.data.materials[:]) - set(init_mats)
		post_len = len(bpy.data.materials)
		if not list(imported):
			return "No new materials found"
		elif len(list(imported)) > 1:
			return "More than one material generated"
		elif list(imported)[0].library:
			return "Material linked should not be a library"
		elif post_len - 1 != init_len:
			return "Should have imported specifically one material"

		new_mat.name = "mcprep_test"
		init_len = len(bpy.data.materials)
		res = bpy.ops.mcprep.sync_materials(
			link=False,
			replace_materials=True)
		if res != {'FINISHED'}:
			return "Should return finished with test file (replace)"
		if len(bpy.data.materials) != init_len:
			return "Number of materials should not have changed with replace"

		# Now test it works with name generalization, stripping .###
		new_mat.name = "mcprep_test.005"
		init_mats = bpy.data.materials[:]
		init_len = len(bpy.data.materials)
		res = bpy.ops.mcprep.sync_materials(
			link=False,
			replace_materials=False)
		if res != {'FINISHED'}:
			return "Should return finished with test file"

		# check there is another material now
		imported = set(bpy.data.materials[:]) - set(init_mats)
		post_len = len(bpy.data.materials)
		if not list(imported):
			return "No new materials found"
		elif len(list(imported)) > 1:
			return "More than one material generated"
		elif list(imported)[0].library:
			return "Material linked should not be a library"
		elif post_len - 1 != init_len:
			return "Should have imported specifically one material"

	def sync_materials_link(self):
		"""Test syncing materials works"""
		self._clear_scene()

		# test that the base test material is included as shipped
		bpy.ops.mesh.primitive_plane_add()
		obj = bpy.context.object
		if bpy.app.version >= (2, 80):
			obj.select_set(True)
		else:
			obj.select = True

		new_mat = bpy.data.materials.new("mcprep_test")
		obj.active_material = new_mat

		new_mat.name = "mcprep_test"
		init_mats = bpy.data.materials[:]
		res = bpy.ops.mcprep.sync_materials(
			link=True,
			replace_materials=False)
		if res != {'FINISHED'}:
			return "Should return finished with test file (link)"
		imported = set(bpy.data.materials[:]) - set(init_mats)
		imported = list(imported)
		if not imported:
			return "No new material found after linking"
		if not list(imported)[0].library:
			return "Material linked is not a library"

	def load_material(self):
		"""Test the load material operators and related resets"""
		self._clear_scene()
		bpy.ops.mcprep.reload_materials()

		# add object
		bpy.ops.mesh.primitive_cube_add()

		scn_props = bpy.context.scene.mcprep_props
		itm = scn_props.material_list[scn_props.material_list_index]
		path = itm.path
		bpy.ops.mcprep.load_material(filepath=path)

		# validate that the loaded material has a name matching current list
		mat = bpy.context.object.active_material
		scn_props = bpy.context.scene.mcprep_props
		mat_item = scn_props.material_list[scn_props.material_list_index]
		if mat_item.name not in mat.name:
			return "Material name not loaded " + mat.name

	def uv_transform_detection(self):
		"""Ensure proper detection and transforms for Mineways all-in-one images"""
		from MCprep.materials.uv_tools import get_uv_bounds_per_material
		self._clear_scene()

		bpy.ops.mesh.primitive_cube_add()
		bpy.ops.object.editmode_toggle()
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.uv.reset()
		bpy.ops.object.editmode_toggle()
		new_mat = bpy.data.materials.new(name="tmp")
		bpy.context.object.active_material = new_mat

		if not bpy.context.object or not bpy.context.object.active_material:
			return "Failed set up for uv_transform_detection"

		uv_bounds = get_uv_bounds_per_material(bpy.context.object)
		mname = bpy.context.object.active_material.name
		if uv_bounds != {mname: [0, 1, 0, 1]}:
			return "UV transform for default cube should have max bounds"

		bpy.ops.object.editmode_toggle()
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.uv.sphere_project()  # will ensure more irregular UV map, not bounded
		bpy.ops.object.editmode_toggle()
		uv_bounds = get_uv_bounds_per_material(bpy.context.object)
		if uv_bounds == {mname: [0, 1, 0, 1]}:
			return "UV mapping is irregular, should have different min/max"

	def uv_transform_no_alert(self):
		"""Ensure that uv transform alert does not go off unexpectedly"""
		from MCprep.materials.uv_tools import detect_invalid_uvs_from_objs
		self._clear_scene()

		self._import_mineways_separated()
		invalid, invalid_objs = detect_invalid_uvs_from_objs(
			bpy.context.selected_objects)
		prt = ",".join([obj.name for obj in invalid_objs])  # obj.name.split("_")[-1]
		if invalid is True:
			return "Mineways separated tiles export should not alert: " + prt

		self._clear_scene()
		self._import_jmc2obj_full()
		invalid, invalid_objs = detect_invalid_uvs_from_objs(
			bpy.context.selected_objects)
		prt = ",".join([obj.name.split("_")[-1] for obj in invalid_objs])
		if invalid is True:
			return "jmc2obj export should not alert: " + prt

	def uv_transform_combined_alert(self):
		"""Ensure that uv transform alert goes off for Mineways all-in-one"""
		from MCprep.materials.uv_tools import detect_invalid_uvs_from_objs
		self._clear_scene()

		self._import_mineways_combined()
		invalid, invalid_objs = detect_invalid_uvs_from_objs(
			bpy.context.selected_objects)
		if invalid is False:
			return "Combined image export should alert"
		if not invalid_objs:
			return "Correctly alerted combined image, but no obj's returned"

		# Do specific checks for water and lava, since they might be combined
		# and cover more than one uv position (and falsely pass the test)
		# in combined, water is called "Stationary_Wat" and "Stationary_Lav"
		# (yes, appears cutoff; and yes includes the flowing too)
		# NOTE! in 2.7x, will be named "Stationary_Water", but in 2.9 it is
		# "Test_MCprep_1.16.4__-145_4_1271_to_-118_255_1311_Stationary_Wat"
		water_obj = [
			obj for obj in bpy.data.objects if "Stationary_Wat" in obj.name][0]
		lava_obj = [
			obj for obj in bpy.data.objects if "Stationary_Lav" in obj.name][0]

		invalid, invalid_objs = detect_invalid_uvs_from_objs([lava_obj, water_obj])
		if invalid is False:
			return "Combined lava/water should still alert"

	def test_enable_obj_importer(self):
		"""Ensure module name is correct, since error won't be reported."""
		bpy.ops.preferences.addon_enable(module="io_scene_obj")

	def qa_effects(self):
		"""Ensures that effects files meet all QA needs"""

		basepath = os.path.join("MCprep_addon", "MCprep_resources", "effects")
		basepath = os.path.abspath(basepath)  # relative to the dev git folder

		bfiles = []
		for child in os.listdir(basepath):
			fullp = os.path.join(basepath, child)
			if os.path.isfile(fullp) and child.lower().endswith(".blend"):
				bfiles.append(fullp)
			elif not os.path.isdir(fullp):
				continue
			subblends = [
				os.path.join(basepath, child, blend)
				for blend in os.listdir(os.path.join(basepath, child))
				if os.path.isfile(os.path.join(basepath, child, blend))
				and blend.lower().endswith(".blend")
			]
			bfiles.extend(subblends)

		print("Checking blend files")
		if not bfiles:
			return "No files loaded for bfiles"

		issues = []
		checked = 0
		for blend in bfiles:
			print("QC'ing:", blend)
			if not os.path.isfile(blend):
				return "Did not exist: " + str(blend)
			bpy.ops.wm.open_mainfile(filepath=blend)

			resp = self._qa_helper(basepath, allow_packed=True)
			if resp:
				issues.append([blend, resp])
			checked += 1

		if issues:
			return issues

	def qa_rigs(self):
		"""Ensures that all rig files meet all QA needs.

		NOTE: This test is actually surpisingly fast given the number of files
		it needs to check against, but it's possible it can be unstable. Exit
		early to override if needed.
		"""

		basepath = os.path.join("MCprep_addon", "MCprep_resources", "rigs")
		basepath = os.path.abspath(basepath)  # relative to the dev git folder

		bfiles = []
		for child in os.listdir(basepath):
			fullp = os.path.join(basepath, child)
			if os.path.isfile(fullp) and child.lower().endswith(".blend"):
				bfiles.append(fullp)
			elif not os.path.isdir(fullp):
				continue
			subblends = [
				os.path.join(basepath, child, blend)
				for blend in os.listdir(os.path.join(basepath, child))
				if os.path.isfile(os.path.join(basepath, child, blend))
				and blend.lower().endswith(".blend")
			]
			bfiles.extend(subblends)

		print("Checking blend files")
		if not bfiles:
			return "No files loaded for bfiles"

		issues = []
		checked = 0
		for blend in bfiles:
			print("QC'ing:", blend)
			if not os.path.isfile(blend):
				return "Did not exist: " + str(blend)
			bpy.ops.wm.open_mainfile(filepath=blend)

			resp = self._qa_helper(basepath, allow_packed=True)
			if resp:
				issues.append([blend, resp])
			checked += 1

		if issues:
			return "Checked {} rigs, issues: {}".format(
				checked, issues)

	def convert_mtl_simple(self):
		"""Ensures that conversion of the mtl with other color space works."""
		from MCprep import world_tools

		src = "mtl_simple_original.mtl"
		end = "mtl_simple_modified.mtl"
		test_dir = os.path.dirname(__file__)
		simple_mtl = os.path.join(test_dir, src)
		modified_mtl = os.path.join(test_dir, end)

		# now save the texturefile somewhere
		tmp_dir = tempfile.gettempdir()
		tmp_mtl = os.path.join(tmp_dir, src)
		shutil.copyfile(simple_mtl, tmp_mtl)  # leave original intact

		if not os.path.isfile(tmp_mtl):
			return "Failed to create tmp tml at " + tmp_mtl

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

		if res is None:
			return "Failed to mock color space and thus could not test convert_mtl"

		if res is False:
			return "Convert mtl failed with false response"

		# Now check that the data is the same.
		res = filecmp.cmp(tmp_mtl, modified_mtl, shallow=False)
		if res is not True:
			# Not removing file, since we likely want to inspect it.
			return "Generated MTL is different: {} vs {}".format(
				tmp_mtl, modified_mtl)
		else:
			os.remove(tmp_mtl)

	def convert_mtl_skip(self):
		"""Ensures that we properly skip if a built in space active."""
		from MCprep import world_tools

		src = "mtl_simple_original.mtl"
		test_dir = os.path.dirname(__file__)
		simple_mtl = os.path.join(test_dir, src)

		# now save the texturefile somewhere
		tmp_dir = tempfile.gettempdir()
		tmp_mtl = os.path.join(tmp_dir, src)
		shutil.copyfile(simple_mtl, tmp_mtl)  # leave original intact

		if not os.path.isfile(tmp_mtl):
			return "Failed to create tmp tml at " + tmp_mtl

		# Need to mock:
		# bpy.context.scene.view_settings.view_transform
		# to be an invalid kind of attribute, to simulate an ACES or AgX space.
		# But we can't do that since we're not (yet) using the real unittest
		# framework, hence we'll just clear the  world_tool's vars.
		actual_space = str(bpy.context.scene.view_settings.view_transform)
		save_init = list(world_tools.BUILTIN_SPACES)
		world_tools.BUILTIN_SPACES = [actual_space]
		print("TEST: pre", world_tools.BUILTIN_SPACES)

		# Resultant file
		res = world_tools.convert_mtl(tmp_mtl)

		# Restore the property we unset.
		world_tools.BUILTIN_SPACES = save_init
		print("TEST: post", world_tools.BUILTIN_SPACES)

		if res is not None:
			os.remove(tmp_mtl)
			return "Should not have converter MTL for valid space"


class OCOL:
	"""override class for colors, for terminals not supporting color-out"""
	HEADER = ''
	OKBLUE = ''
	OKGREEN = ''
	WARNING = '[WARN]'
	FAIL = '[ERR]'
	ENDC = ''
	BOLD = ''
	UNDERLINE = ''


class COL:
	"""native_colors to use, if terminal supports color out"""
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'


def suffix_chars(string, max_char):
	"""Returns passed string or the last max_char characters if longer"""
	string = string.replace('\n', '\\n ')
	string = string.replace(',', ' ')
	if len(string) > max_char:
		return string[-max_char:]
	return string

# -----------------------------------------------------------------------------
# Testing file, to semi-auto check addon functionality is working
# Run this as a script, which creates a temp MCprep - test panel
# and cycle through all tests.
# -----------------------------------------------------------------------------


class MCPTEST_OT_test_run(bpy.types.Operator):
	bl_label = "MCprep run test"
	bl_idname = "mcpreptest.run_test"
	bl_description = "Run specified test index"

	index: bpy.props.IntProperty(default=0)

	def execute(self, context):
		# ind = context.window_manager.mcprep_test_index
		test_class.mcrprep_run_test(self.index)
		return {'FINISHED'}


class MCPTEST_OT_test_selfdestruct(bpy.types.Operator):
	bl_label = "MCprep test self-destruct (dereg)"
	bl_idname = "mcpreptest.self_destruct"
	bl_description = "Deregister the MCprep test script, panel, and operators"

	def execute(self, context):
		print("De-registering MCprep test")
		unregister()
		return {'FINISHED'}


class MCPTEST_PT_test_panel(bpy.types.Panel):
	"""MCprep test panel"""
	bl_label = "MCprep Test Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if bpy.app.version < (2, 80) else 'UI'
	bl_category = "MCprep"

	def draw_header(self, context):
		col = self.layout.column()
		col.label("", icon="ERROR")

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.label(text="Select test case:")
		col.prop(context.window_manager, "mcprep_test_index")
		ops = col.operator("mcpreptest.run_test")
		ops.index = context.window_manager.mcprep_test_index
		col.prop(context.window_manager, "mcprep_test_autorun")
		col.label(text="")

		r = col.row()
		subc = r.column()
		subc.scale_y = 0.8
		# draw test results thus far:
		for i, itm in enumerate(test_class.test_cases):
			row = subc.row(align=True)

			if test_class.test_cases[i][1]["check"] == 1:
				icn = "COLOR_GREEN"
			elif test_class.test_cases[i][1]["check"] == -1:
				icn = "COLOR_GREEN"
			elif test_class.test_cases[i][1]["check"] == -2:
				icn = "QUESTION"
			else:
				icn = "MESH_CIRCLE"
			row.operator("mcpreptest.run_test", icon=icn, text="").index = i
			row.label("{}-{} | {}".format(
				test_class.test_cases[i][1]["type"],
				test_class.test_cases[i][0],
				test_class.test_cases[i][1]["res"]
			))
		col.label(text="")
		col.operator("mcpreptest.self_destruct")


def mcprep_test_index_update(self, context):
	if context.window_manager.mcprep_test_autorun:
		print("Auto-run MCprep test")
		bpy.ops.mcpreptest.run_test(index=self.mcprep_test_index)


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPTEST_OT_test_run,
	MCPTEST_OT_test_selfdestruct,
	MCPTEST_PT_test_panel
)


def register():
	print("REGISTER MCPREP TEST")
	maxlen = len(test_class.test_cases)

	bpy.types.WindowManager.mcprep_test_index = bpy.props.IntProperty(
		name="MCprep test index",
		default=-1,
		min=-1,
		max=maxlen,
		update=mcprep_test_index_update)
	bpy.types.WindowManager.mcprep_test_autorun = bpy.props.BoolProperty(
		name="Autorun test",
		default=True)

	# context.window_manager.mcprep_test_index = -1 put into handler to reset?
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	print("DEREGISTER MCPREP TEST")
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.WindowManager.mcprep_test_index
	del bpy.types.WindowManager.mcprep_test_autorun


if __name__ == "__main__":
	global test_class
	test_class = mcprep_testing()

	register()

	# setup paths to the target
	test_class.setup_env_paths()

	# check for additional args, e.g. if running from console beyond blender
	if "--" in sys.argv:
		argind = sys.argv.index("--")
		args = sys.argv[argind + 1:]
	else:
		args = []

	if "-v" in args:
		test_class.suppress = False
	else:
		test_class.suppress = True

	if "-run" in args:
		ind = args.index("-run")
		if len(args) > ind:
			test_class.run_only = args[ind + 1]

	if "--auto_run" in args:
		test_class.run_all_tests()
