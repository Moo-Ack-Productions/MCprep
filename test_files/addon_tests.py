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
			self.find_missing_images_cycles
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
