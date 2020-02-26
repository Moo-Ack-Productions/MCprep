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


import bpy
import traceback

import os
import json
import sys
import io
from contextlib import redirect_stdout
import importlib


# -----------------------------------------------------------------------------
# Primary test loop
# -----------------------------------------------------------------------------


class mcprep_testing():
	# {status}, func, prefunc caller (reference only)

	def __init__(self):
		self.suppress = True # hold stdout
		self.test_status = {} # {func.__name__: {"check":-1, "res":-1,0,1}}
		self.test_cases = [
			self.enable_mcprep,
			self.prep_materials,
			self.openfolder,
			self.spawn_mob,
			self.change_skin,
			self.import_world_split,
			self.import_world_fail,
			self.import_jmc2obj,
			self.import_mineways_separated,
			self.import_mineways_combined
			]
		self.run_only = None # name to give to only run this test

		self.mcprep_json = {}
		# 	0:["prep_materials", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	1:["combine_materials", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	2:["combine_images", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	3:["scale_uv", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	4:["isolate_alpha_uvs", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	5:["improve_ui", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	6:["skin_swapper", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	7:["applyskin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	8:["applyusernameskin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	9:["fix_skin_eyes", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	10:["add_skin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	11:["remove_skin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	12:["reload_skins", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	13:["spawn_with_skin", {"type":"material","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	14:["handler_skins_enablehack", {"type":"material","check":0,"res":""}, ""],
		# 	15:["open_preferences", {"type":"mcprep_ui","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["openfolder", {"type":"mcprep_ui","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["meshswap_pathreset", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["meshswap_spawner", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["reload_meshswap", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["meshswap", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["meshswap", {"type":"meshswap","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["fixmeshswapsize", {"type":"meshswap","check":0,"res":""}, "bpy.ops.object"],
		# 	16:["reload_spawners", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["reload_mobs", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["mob_spawner_direct", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["mob_spawner", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# 	16:["mob_install_menu", {"type":"spawner","check":0,"res":""}, "bpy.ops.mcprep"],
		# }

	def run_all_tests(self):
		"""For use in command line mode, run all tests and checks"""
		if self.run_only and self.run_only not in [tst.__name__ for tst in self.test_cases]:
			print("{}No tests ran!{} Test function not found: {}".format(
				COL.FAIL, COL.ENDC, self.run_only))

		for test in self.test_cases:
			if self.run_only and test.__name__ != self.run_only:
				continue
			self.mcrprep_run_test(test)

		failed_tests = [tst for tst in self.test_status
			if self.test_status[tst]["check"] < 0]
		passed_tests = [tst for tst in self.test_status
			if self.test_status[tst]["check"] > 0]

		print("\n{}COMPLETED, {} passed and {} failed{}".format(
			COL.HEADER,
			len(passed_tests), len(failed_tests),
			COL.ENDC))
		if passed_tests:
			print("{}Passed tests:{}".format(COL.OKGREEN, COL.ENDC))
			print("\t"+", ".join(passed_tests))
		if failed_tests:
			print("{}Failed tests:{}".format(COL.FAIL, COL.ENDC))
			for tst in self.test_status:
				if self.test_status[tst]["check"] > 0:
					continue
				ert = self.test_status[tst]["res"]
				ert.replace('\n', '\\n ')
				if len(ert)>70:
					ert = ert[-70:]
				print("\t{}{}{}: {}".format(COL.UNDERLINE, tst, COL.ENDC, ert))

	def mcrprep_run_test(self, test_func):
		"""Run a single MCprep test"""
		print("\n{}Testing {}{}".format(COL.HEADER, test_func.__name__, COL.ENDC))

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
				self.test_status[test_func.__name__] = {"check":1, "res": res}
			else:
				print("\t{}TEST FAILED:{}".format(COL.FAIL, COL.ENDC))
				print("\t"+res)
				self.test_status[test_func.__name__] = {"check":-1, "res": res}
		except Exception as e:
			print("\t{}TEST FAILED{}".format(COL.FAIL, COL.ENDC))
			print(traceback.format_exc()) # plus other info, e.g. line number/file?
			self.test_status[test_func.__name__] = {"check":-1, "res": traceback.format_exc()}
		# print("\tFinished test {}".format(test_func.__name__))

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
		conf.init()

	# -----------------------------------------------------------------------------
	# Testing utilities, not tests themselves (ie assumed to work)
	# -----------------------------------------------------------------------------

	def _clear_scene(self):
		"""Clear scene and data without printouts"""
		# if not self.suppress:
		# stdout = io.StringIO()
		# with redirect_stdout(stdout):
		bpy.ops.wm.read_homefile(app_template="")
		for obj in bpy.data.objects:
			bpy.data.objects.remove(obj) # wait, that's illegal?
		for mat in bpy.data.materials:
			bpy.data.materials.remove(mat)
			# for txt in bpy.data.texts:
			# 	bpy.data.texts.remove(txt)

	def _add_character(self):
		"""Add a rigged character to the scene, specifically Alex"""
		bpy.ops.mcprep.reload_mobs()
		# mcmob_type='player/Simple Rig - Boxscape-TheDuckCow.blend:/:Simple Player'
		# mcmob_type='player/Alex FancyFeet - TheDuckCow & VanguardEnni.blend:/:alex'
		mcmob_type='hostile/mobs - Rymdnisse.blend:/:silverfish'
		bpy.ops.mcprep.mob_spawner(mcmob_type=mcmob_type, skipUsage=True)

	def _import_jmc2obj_full(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "jmc2obj", "jmc2obj_test_1_14_4.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _import_mineways_separated(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "mineways", "separated_textures",
			"mineways_test_texs_1_14_4.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _import_mineways_combined(self):
		"""Import the full jmc2obj test set"""
		testdir = os.path.dirname(__file__)
		obj_path = os.path.join(testdir, "mineways", "combined_textures",
			"mineways_test_single_1_14_4.obj")
		bpy.ops.mcprep.import_world_split(filepath=obj_path)

	def _create_canon_mat(self):
		"""Creates a material that should be recognized"""
		mat = bpy.data.materials.new("dirt")
		mat.use_nodes = True
		img_node = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
		img = bpy.data.images.new("dirt", 16, 16)
		img_node.image = img
		return mat

	# Seems that infolog doesn't update in background mode
	def _get_last_infolog(self):
		"""Return back the latest info window log"""
		for txt in bpy.data.texts:
			bpy.data.texts.remove(txt)
		res = bpy.ops.ui.reports_to_textblock()
		print("DEVVVV get last infolog:")
		for ln in bpy.data.texts['Recent Reports'].lines:
			print(ln.body)
		print("END printlines")
		return bpy.data.texts['Recent Reports'].lines[-1].body

	# def _get_mcprep_data(self):
	# 	"""Return the contents of the mcprep_data.json file"""
	# 	if self.mcprep_json:
	# 		return self.mcprep_json
	# 	base = os.path.dirname(os.path.dirname(__file__))
	# 	json_path = os.path.join(base, "MCprep_addon", "MCprep_resources", "mcprep_data_update.json")

	# 	with open(json_path) as jpth:
	# 		self.mcprep_json = json.load(jpth)

	# 	if not self.mcprep_json:
	# 		raise Exception("Could not load json resource")
	# 	return self.mcprep_json


	# -----------------------------------------------------------------------------
	# Operator unit tests
	# -----------------------------------------------------------------------------

	def enable_mcprep(self):
		"""Ensure we can both enable and disable MCprep"""

		# brute force enable
		# stdout = io.StringIO()
		# with redirect_stdout(stdout):
		try:
			bpy.ops.preferences.addon_enable(module="MCprep_addon")
		except:
			pass

		# see if we can safely toggle off and back on
		print("Try disable:")
		bpy.ops.preferences.addon_disable(module="MCprep_addon")
		print("Try re-enable:")
		bpy.ops.preferences.addon_enable(module="MCprep_addon")
		return

	def prep_materials(self):
		# run once when nothing is selected, no active object
		self._clear_scene()


		# res = bpy.ops.mcprep.prep_materials(
		# 	animateTextures=False,
		# 	autoFindMissingTextures=False,
		# 	improveUiSettings=False,
		# 	skipUsage=True)
		# if res != {'CANCELLED'}:
		# 	return "Should have returned cancelled as no objects selected"
		# elif "No objects selected" != self._get_last_infolog():
		# 	return "Did not get the right info log back"

		status = 'fail'
		print("Checking blank usage")
		try:
			bpy.ops.mcprep.prep_materials(
				animateTextures=False,
				autoFindMissingTextures=False,
				improveUiSettings=False,
				#skipUsage=True
				)
		except RuntimeError as e:
			if "Error: No objects selected" in str(e):
				status = 'success'
			else:
				return "prep_materials other err: "+str(e)
		if status=='fail':
			return "Prep should have failed with error on no objects"

		# add object, no material. Should still fail as no materials
		bpy.ops.mesh.primitive_plane_add()
		obj = bpy.context.object
		status = 'fail'
		try:
			res = bpy.ops.mcprep.prep_materials(
				animateTextures=False,
				autoFindMissingTextures=False,
				improveUiSettings=False)
		except RuntimeError as e:
			if 'No materials found' in str(e):
				status = 'success' # expect to fail when nothing selected
		if status=='fail':
			return "mcprep.prep_materials-02 failure"

		# TODO: Add test where material is added but without an image/nodes

		# add object with canonical material name. Assume cycles
		new_mat = self._create_canon_mat()
		obj.active_material = new_mat
		status = 'fail'
		try:
			res = bpy.ops.mcprep.prep_materials(
				animateTextures=False,
				autoFindMissingTextures=False,
				improveUiSettings=False)
		except Exception as e:
			return "Unexpected error: "+str(e)
		# how to tell if prepping actually occured? Should say 1 material prepped
		print(self._get_last_infolog())

	def prep_materials_cycles(self):
		"""Cycles-specific tests"""

	def find_missing(self):
		"""Find missing materials"""

	def openfolder(self):
		if bpy.app.background is True:
			return "" # can't test this in background mode

		folder = bpy.utils.script_path_user()
		if not os.path.isdir(folder):
			return "Sample folder doesn't exist, couldn't test"
		res = bpy.ops.mcprep.openfolder(folder)
		if res=={"FINISHED"}:
			return ""
		else:
			return "Failed, returned cancelled"

	def spawn_mob(self):
		"""Spawn mobs, reload mobs, etc"""
		self._clear_scene()
		self._add_character() # run the utility as it's own sort of test

		self._clear_scene()
		bpy.ops.mcprep.reload_mobs()

		# sample don't specify mob, just load whatever is first
		bpy.ops.mcprep.mob_spawner()

		# spawn an alex

		# try changing the folder

		# try install mob and uninstall

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
			res = bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=False)
		except RuntimeError as e:
			if 'No materials found to update' in str(e):
				status = 'success' # expect to fail when nothing selected
		if status=='fail':
			return "Should have failed to skin swap with no objects selected"

		# now run on a real test character, with 1 material and 2 objects
		self._add_character()

		pre_mats = len(bpy.data.materials)
		bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=False)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats: # should be unchanged
			return "change_skin.mat counts diff despit no new mat request, {} before and {} after".format(
				pre_mats, post_mats)

		# do counts of materials before and after to ensure they match
		pre_mats = len(bpy.data.materials)
		bpy.ops.mcprep.applyskin(
			filepath=skin_path,
			new_material=True)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats*2: # should exactly double since in new scene
			return "change_skin.mat counts diff mat counts, {} before and {} after".format(
				pre_mats, post_mats)

		pre_mats = len(bpy.data.materials)

		bpy.ops.mcprep.skin_swapper( # not diff operator name, this is popup browser
			filepath=skin_path,
			new_material=False)
		post_mats = len(bpy.data.materials)
		if post_mats != pre_mats: # should be unchanged
			return "change_skin.mat counts differ even though should be same, {} before and {} after".format(
				pre_mats, post_mats)

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



		bpy.ops.mcprep.spawn_with_skin(skipUsage=True)
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
		if post_objects+1 > pre_objects:
			print("Success, had {} objs, post import {}".format(
				pre_objects, post_objects))
			return ""
		elif post_objects+1 == pre_objects:
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
			print("Failed, as intended: "+str(e))
			return ""
		return "World import should have returned an error"

	def import_materials_util(self, mapping_set):
		"""Reusable function for testing on different obj setups"""
		from MCprep.materials.generate import get_mc_canonical_name
		from MCprep.materials.generate import find_from_texturepack
		from MCprep import util
		from MCprep import conf

		util.load_mcprep_json() # force load json cache
		mcprep_data = conf.json_data["blocks"][mapping_set]

		# first detect alignment to the raw underlining mappings, nothing to
		# do with canonical yet
		mapped = [mat.name for mat in bpy.data.materials
			if mat.name in mcprep_data] # ok!
		unmapped = [mat.name for mat in bpy.data.materials
			if mat.name not in mcprep_data] # not ok
		fullset = mapped+unmapped # ie all materials
		unleveraged = [mat for mat in mcprep_data
			if mat not in fullset] # not ideal, means maybe missed check

		print("Mapped: {}, unmapped: {}, unleveraged: {}".format(
			len(mapped), len(unmapped), len(unleveraged)))

		if len(unmapped):
			err = "Textures not mapped to json file"
			print(err)
			print(sorted(unmapped))
			print("")
			#return err
		if len(unleveraged) > 20:
			err = "Json file materials not found in obj test file, may need to update world"
			print(err)
			print(sorted(unleveraged))
			# return err

		if len(mapped) == 0:
			return "No materials mapped"
		elif len(mapped) < len(unmapped)+len(unleveraged):
			# not a very optimistic threshold, but better than none
			return "More materials unmapped than mapped"
		print("")

		mc_count=0
		jmc_count=0
		mineways_count=0

		# each element is [cannon_name, form], form is none if not matched
		mapped = [get_mc_canonical_name(mat.name) for mat in bpy.data.materials]

		# no matching canon name (warn)
		mats_not_canon = [itm[0] for itm in mapped if itm[1] is None]
		if mats_not_canon:
			print("Non-canon material names found: ({})".format(len(mats_not_canon)))
			print(mats_not_canon)
			if len(mats_not_canon)>30: # arbitrary threshold
				return "Too many materials found without canonical name ({})".format(
					len(mats_not_canon))
		else:
			print("Confirmed - no non-canon images found")

		# affirm the correct mappings
		mats_no_packimage = [find_from_texturepack(itm[0]) for itm in mapped
			if itm[1] is not None]
		mats_no_packimage = [path for path in mats_no_packimage if path]
		print("Mapped paths: "+str(len(mats_no_packimage)))

		# could not resolve image from resource pack (warn) even though in mapping
		mats_no_packimage = [itm[0] for itm in mapped
			if itm[1] is not None and not find_from_texturepack(itm[0])]
		print("No resource images found for mapped items: ({})".format(
			len(mats_no_packimage)))
		print("These would appear to have cannon mappings, but then fail on lookup")
		for itm in mats_no_packimage:
			print("\t"+itm)
		if len(mats_no_packimage)>5: # known number up front, e.g. chests, stone_slab_side, stone_slab_top
			return "Missing images for blocks specified in mcprep_data.json"

		# also test that there are not raw image names not in mapping list
		# but that otherwise could be added to the mapping list as file exists

	def import_jmc2obj(self):
		"""Checks that material names in output obj match the mapping file"""
		self._clear_scene()
		self._import_jmc2obj_full()

		res = self.import_materials_util("block_mapping_jmc")
		return res

	def import_mineways_separated(self):
		"""Checks Mineways (multi-image) material name mapping to mcprep_data"""
		self._clear_scene()
		self._import_mineways_separated()

		#mcprep_data = self._get_mcprep_data()
		res = self.import_materials_util("block_mapping_jmc")
		return res

	def import_mineways_combined(self):
		"""Checks Mineways (multi-image) material name mapping to mcprep_data"""
		self._clear_scene()
		self._import_mineways_combined()

		#mcprep_data = self._get_mcprep_data()
		res = self.import_materials_util("block_mapping_jmc")
		return res


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


# -----------------------------------------------------------------------------
# Testing file, to semi-auto check addon functionality is working
# Run this as a script, which creates a temp MCprep - test panel
# and cycle through all tests.
# -----------------------------------------------------------------------------


class MCPTEST_OT_test_run(bpy.types.Operator):
	bl_label = "MCprep run test"
	bl_idname = "mcpreptest.run_test"
	bl_description = "Run specified test index"

	index = bpy.props.IntProperty(default=0)

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
		return{'FINISHED'}


class MCPTEST_PT_test_panel(bpy.types.Panel):
	"""MCprep test panel"""
	bl_label = "MCprep Test Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if bpy.app.version < (2,80) else 'UI'
	bl_category = "MCprep"

	def draw_header(self, context):
		col = self.layout.column()
		col.label("",icon="ERROR")

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		col.label(text="Select test case:")
		col.prop(context.window_manager, "mcprep_test_index")
		col.operator("mcpreptest.run_test").index = context.window_manager.mcprep_test_index
		col.prop(context.window_manager, "mcprep_test_autorun")
		col.label(text="")

		r = col.row()
		subc = r.column()
		subc.scale_y = 0.8
		# draw test results thus far:
		for i, itm in enumerate(test_class.test_cases):
			row = subc.row(align=True)

			if test_class.test_cases[i][1]["check"]==1:
				icn = "COLOR_GREEN"
			elif test_class.test_cases[i][1]["check"]==-1:
				icn = "COLOR_GREEN"
			elif test_class.test_cases[i][1]["check"]==-2:
				icn = "QUESTION"
			else:
				icn = "MESH_CIRCLE"
			row.operator("mcpreptest.run_test", icon=icn, text="").index=i
			row.label("{}-{} | {}".format(
				test_class.test_cases[i][1]["type"],
				test_class.test_cases[i][0],
				test_class.test_cases[i][1]["res"]
				)
			)
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
		default=True
		)

	# context.window_manager.mcprep_test_index = -1 put into handler to reset?
	for cls in classes:
		# util.make_annotations(cls)
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
			test_class.run_only = args[ind+1]

	if "--auto_run" in args:
		test_class.run_all_tests()

