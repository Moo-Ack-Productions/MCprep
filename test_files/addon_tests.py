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


"""
DEPRECATED
"""


from contextlib import redirect_stdout
import importlib
import io
import os
import shutil
import sys
import tempfile
import traceback

import bpy

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
			self.name_generalize,
			self.canonical_name_no_none,
			self.canonical_test_mappings,
			self.detect_extra_passes,
			self.find_missing_images_cycles,
			self.sync_materials,
			self.sync_materials_link,
			self.uv_transform_detection,
			self.uv_transform_no_alert,
			self.uv_transform_combined_alert,
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
