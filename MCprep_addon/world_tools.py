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
import math
from pathlib import Path
from typing import List, Optional
import shutil

import bpy
from bpy.types import Context, Camera
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .conf import env, VectorType
from . import util
from . import tracking
from .materials import generate


# -----------------------------------------------------------------------------
# supporting functions
# -----------------------------------------------------------------------------

BUILTIN_SPACES = (
	"Standard",
	"Filmic",
	"Filmic Log",
	"Raw",
	"False Color"
)


time_obj_cache = None


def get_time_object() -> None:
	"""Returns the time object if present in the file"""
	global time_obj_cache  # to avoid re parsing every time

	if time_obj_cache is not None:
		try:
			if "MCprepHour" not in time_obj_cache:
				time_obj_cache = None
		except ReferenceError:
			time_obj_cache = None  # e.g. if item was deleted

	cached = time_obj_cache is not None
	obj_gone = cached and time_obj_cache not in bpy.data.objects[:]
	key_missing = cached and "MCprepHour" not in time_obj_cache
	if obj_gone or key_missing:
		time_obj_cache = None

	if time_obj_cache is None:
		time_objs = [obj for obj in bpy.data.objects if "MCprepHour" in obj]
		if time_objs:
			# If multiple contain this key, fetch the most recent.
			time_objs.sort(key=lambda x: x.name)
			time_obj_cache = time_objs[-1]

	return time_obj_cache


class ObjHeaderOptions:
	"""Wrapper functions to avoid typos causing issues."""

	def __init__(self):
		self._exporter: Optional[str] = None
		self._file_type: Optional[str] = None
	
	"""
	Wrapper functions to avoid typos causing issues
	"""
	def set_mineways(self):
		self._exporter = "Mineways"

	def set_jmc2obj(self):
		self._exporter = "jmc2obj"

	def set_atlas(self):
		self._file_type = "ATLAS"

	def set_seperated(self):
		self._file_type = "INDIVIDUAL_TILES"

	"""
	Returns the exporter used
	"""
	def exporter(self):
		return self._exporter if self._exporter is not None else "(choose)"

	"""
	Returns the type of textures
	"""
	def texture_type(self):
		return self._file_type if self._file_type is not None else "NONE"


obj_header = ObjHeaderOptions()


def detect_world_exporter(filepath: Path) -> None:
	"""Detect whether Mineways or jmc2obj was used, based on prefix info.

	Primary heruistic: if detect Mineways header, assert Mineways, else
	assume jmc2obj. All Mineways exports for a long time have prefix info
	set in the obj file as comments.
	"""
	with open(filepath, 'r') as obj_fd:
		try:
			header = obj_fd.readline()
			if 'mineways' in header.lower():
				obj_header.set_mineways()
				# form of: # Wavefront OBJ file made by Mineways version 5.10...
				for line in obj_fd:
					if line.startswith("# File type:"):
						header = line.rstrip()  # Remove trailing newline

				# The issue here is that Mineways has changed how the header is generated.
				# As such, we're limited with only a couple of OBJs, some from
				# 2020 and some from 2023, so we'll assume people are using
				# an up to date version.
				atlas = (
					"# File type: Export all textures to three large images",
					"# File type: Export full color texture patterns"
				)
				tiles = (
					"# File type: Export tiles for textures to directory textures",
					"# File type: Export individual textures to directory tex"
				)
				print('"{}"'.format(header))
				if header in atlas:  # If a texture atlas is used
					obj_header.set_atlas()
				elif header in tiles:  # If the OBJ uses individual textures
					obj_header.set_seperated()
				return
		except UnicodeDecodeError:
			print(f"Failed to read first line of obj: {filepath}")
			return
		obj_header.set_jmc2obj()
		# Since this is the default for Jmc2Obj,
		# we'll assume this is what the OBJ is using
		obj_header.set_seperated()


def convert_mtl(filepath):
	"""Convert the MTL file if we're not using one of Blender's built in
	colorspaces

	Without this, Blender's OBJ importer will attempt to set non-color data to
	alpha maps and what not, which causes issues in ACES and whatnot where
	non-color data is not an option.

	This MTL conversion simply does the following:
	- Comment out lines that begin with map_d
	- Add a header at the end

	Returns:
		True if success or skipped, False if failed, or None if skipped
	"""
	# Check if the MTL exists. If not, then check if it
	# uses underscores. If still not, then return False
	mtl = Path(filepath.rsplit(".", 1)[0] + '.mtl')
	if not mtl.exists():
		mtl_underscores = Path(mtl.parent.absolute()) / mtl.name.replace(" ", "_")
		if mtl_underscores.exists():
			mtl = mtl_underscores
		else:
			return False

	lines = None
	copied_file = None

	try:
		with open(mtl, 'r') as mtl_file:
			lines = mtl_file.readlines()
	except Exception as e:
		print(e)
		return False
	
	# This checks to see if the user is using a built-in colorspace or if none of the lines have map_d. If so
	# then ignore this file and return None
	if bpy.context.scene.view_settings.view_transform in BUILTIN_SPACES or not any("map_d" in s for s in lines):
		return None

	# This represents a new folder that'll backup the MTL filepath
	original_mtl_path = Path(filepath).parent.absolute() / "ORIGINAL_MTLS"
	original_mtl_path.mkdir(parents=True, exist_ok=True)

	mcprep_header = (
		"# This section was created by MCprep's MTL conversion script\n",
		"# Please do not remove\n",
		"# Thanks c:\n"
	)

	try:
		header = tuple(lines[-3:])  # Get the last 3 lines
		# Check if MTL has already been converted. If so, return True
		if header != mcprep_header:
			# Copy the MTL with metadata
			print("Header " + str(header))
			copied_file = shutil.copy2(mtl, original_mtl_path.absolute())
		else:
			return True
	except Exception as e:
		print(e)
		return False

	# In this section, we go over each line
	# and check to see if it begins with map_d. If
	# it does, then we simply comment it out. Otherwise,
	# we can safely ignore it.
	try:
		with open(mtl, 'r') as mtl_file:
			for index, line in enumerate(lines):
				if line.startswith("map_d "):
					lines[index] = "# " + line
	except Exception as e:
		print(e)
		return False

	# This needs to be seperate since it involves writing
	try:
		with open(mtl, 'w') as mtl_file:
			mtl_file.writelines(lines)
			mtl_file.writelines(mcprep_header)

	# Recover the original file
	except Exception as e:
		print(e)
		shutil.copy2(copied_file, mtl)
		return False

	return True


def enble_obj_importer() -> Optional[bool]:
	"""Checks if obj import is avail and tries to activate if not.

	If we fail to enable obj importing, return false. True if enabled, and Non
	if nothing changed.
	"""
	enable_addon = None
	if util.min_bv((4, 0)):
		return None  # No longer an addon, native built in.
	else:
		in_import_scn = "obj_import" not in dir(bpy.ops.wm)
		in_wm = ""
		if not in_import_scn and not in_wm:
			enable_addon = "io_scene_obj"

	if enable_addon is None:
		return None

	try:
		bpy.ops.preferences.addon_enable(module=enable_addon)
		return True
	except RuntimeError:
		return False


# -----------------------------------------------------------------------------
# open mineways/jmc2obj related
# -----------------------------------------------------------------------------


class MCPREP_OT_open_jmc2obj(bpy.types.Operator):
	"""Open the jmc2obj executbale"""
	bl_idname = "mcprep.open_jmc2obj"
	bl_label = "Open jmc2obj"
	bl_description = "Open the jmc2obj executbale"

	# poll, and prompt to download if not present w/ tutorial link
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "open_program"
	track_param = "jmc2obj"
	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		res = util.open_program(addon_prefs.open_jmc2obj_path)

		if res == -1:
			bpy.ops.mcprep.install_jmc2obj('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif res != 0:
			self.report({'ERROR'}, str(res))
			return {'CANCELLED'}
		else:
			self.report({'INFO'}, "jmc2obj should open soon")
		return {'FINISHED'}


class MCPREP_OT_install_jmc2obj(bpy.types.Operator):
	"""Utility class to prompt jmc2obj installing"""
	bl_idname = "mcprep.install_jmc2obj"
	bl_label = "Install jmc2obj"
	bl_description = "Prompt to install the jmc2obj world exporter"

	# error message

	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400 * util.ui_scale())

	def draw(self, context):
		self.layout.label(text="Valid program path not found!")
		self.layout.separator()
		self.layout.label(text="Need to install jmc2obj?")
		self.layout.operator(
			"wm.url_open", text="Click to download"
		).url = "http://www.jmc2obj.net/"
		_ = self.layout.split()
		col = self.layout.column()
		col.scale_y = 0.7
		col.label(text="Then, go to MCprep's user preferences and set the jmc2obj")
		col.label(text=" path to jmc2obj_ver#.jar, for example")
		row = self.layout.row(align=True)

		if bpy.app.version < (2, 81):
			# Due to crash-prone bug in 2.81 through 2.83 (beta), if this
			# operator's draw popup is still present behind the newly opened
			# preferences window, and the user then opens a filebrowser e.g.
			# by pressing a folder icon, blender will instant-crash.
			# Thus, don't offer to open preferences for these blender versions
			row.operator(
				"mcprep.open_preferences",
				text="Open MCprep preferences",
				icon="PREFERENCES").tab = "settings"

		row.operator(
			"wm.url_open", text="Open tutorial"
		).url = "https://theduckcow.com/dev/blender/mcprep/setup-world-exporters/"
		return

	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)

		return {'FINISHED'}


class MCPREP_OT_open_mineways(bpy.types.Operator):
	"""Open the Mineways executbale"""
	bl_idname = "mcprep.open_mineways"
	bl_label = "Open Mineways"
	bl_description = "Open the Mineways executbale"

	# poll, and prompt to download if not present w/ tutorial link
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "open_program"
	track_param = "mineways"
	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		if os.path.isfile(addon_prefs.open_mineways_path):
			res = util.open_program(addon_prefs.open_mineways_path)
		else:
			res = -1

		if res == -1:
			bpy.ops.mcprep.install_mineways('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif res != 0:
			self.report({'ERROR'}, str(res))
			return {'CANCELLED'}
		else:
			self.report({'INFO'}, "Mineways should open soon")
		return {'FINISHED'}


class MCPREP_OT_install_mineways(bpy.types.Operator):
	"""Utility class to prompt Mineways installing"""
	bl_idname = "mcprep.install_mineways"
	bl_label = "Install Mineways"
	bl_description = "Prompt to install the Mineways world exporter"

	# error message

	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400 * util.ui_scale())

	def draw(self, context):
		self.layout.label(text="Valid program path not found!")
		self.layout.separator()
		self.layout.label(text="Need to install Mineways?")
		self.layout.operator(
			"wm.url_open", text="Click to download"
		).url = "http://www.realtimerendering.com/erich/minecraft/public/mineways/"
		_ = self.layout.split()
		col = self.layout.column()
		col.scale_y = 0.7
		col.label(text="Then, go to MCprep's user preferences and set the")
		col.label(text=" Mineways path to Mineways.exe or Mineways.app, for example")
		row = self.layout.row(align=True)
		if bpy.app.version < (2, 81):
			# Due to crash-prone bug in 2.81 through 2.83 (beta), if this
			# operator's draw popup is still present behind the newly opened
			# preferences window, and the user then opens a filebrowser e.g.
			# by pressing a folder icon, blender will instant-crash.
			# Thus, don't offer to open preferences for these blender versions
			row.operator(
				"mcprep.open_preferences",
				text="Open MCprep preferences",
				icon="PREFERENCES").tab = "settings"

		row.operator(
			"wm.url_open", text="Open tutorial"
		).url = "https://theduckcow.com/dev/blender/mcprep/setup-world-exporters/"
		return

	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Additional world tools
# -----------------------------------------------------------------------------

class MCPREP_OT_import_world_split(bpy.types.Operator, ImportHelper):
	"""Imports an obj file, and auto splits it by material"""
	bl_idname = "mcprep.import_world_split"
	bl_label = "Import World"
	bl_options = {'REGISTER', 'UNDO'}

	filter_glob: bpy.props.StringProperty(
		default="*.obj;*.mtl",
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "import_split"
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
		# for consistency with the built in one, only import the active path
		if self.filepath.lower().endswith(".mtl"):
			filename = Path(self.filepath)
			new_filename = filename.with_suffix(".obj")
			# Auto change from MTL to OBJ, latet if's will check if existing.
			self.filepath = str(new_filename)
		if not self.filepath:
			self.report({"ERROR"}, "File not found, could not import obj")
			return {'CANCELLED'}
		if not os.path.isfile(self.filepath):
			self.report({"ERROR"}, "File not found, could not import obj")
			return {'CANCELLED'}
		if not self.filepath.lower().endswith(".obj"):
			self.report({"ERROR"}, "You must select a .obj file to import")
			return {'CANCELLED'}

		res = enble_obj_importer()
		if res is None:
			pass
		elif res is True:
			self.report(
				{"INFO"},
				"FYI: had to enable OBJ imports in user preferences")
		elif res is False:
			self.report({"ERROR"}, "Built-in OBJ importer could not be enabled")
			return {'CANCELLED'}

		# There are a number of bug reports that come from the generic call
		# of obj importing. If this fails, should notify the user to try again
		# or try exporting again.
		#
		# In order to not overly supress error messages, below we only capture
		# very tight specific errors possible, so that other errors still get
		# reported so it may be passed off to blender devs. It is understood the
		# below errors are not internationalized, so someone with another lang
		# set will get the raw bubbled up traceback.
		obj_import_err_msg = (
			"Blender's OBJ importer error, try re-exporting your world and "
			"import again.")
		obj_import_mem_msg = (
			"Memory error during OBJ import, try exporting a smaller world")

		# First let's convert the MTL if needed
		conv_res = convert_mtl(self.filepath)
		try:
			if conv_res is None:
				pass  # skipped, no issue anyways.
			elif conv_res is False:
				self.report({"WARNING"}, "MTL conversion failed!")

			res = None
			if util.min_bv((3, 5)):
				res = bpy.ops.wm.obj_import(
					filepath=self.filepath, use_split_groups=True)
			else:
				res = bpy.ops.import_scene.obj(
					filepath=self.filepath, use_split_groups=True)

		except MemoryError as err:
			print("Memory error during import OBJ:")
			print(err)
			self.report({"ERROR"}, obj_import_mem_msg)
			return {'CANCELLED'}
		except ValueError as err:
			if "could not convert string" in str(err):
				# Error such as:
				#   vec[:] = [float_func(v) for v in line_split[1:]]
				#   ValueError: could not convert string to float: b'6848/28'
				print(err)
				self.report({"ERROR"}, obj_import_err_msg)
				return {'CANCELLED'}
			elif "invalid literal for int() with base" in str(err):
				# Error such as:
				#   idx = int(obj_vert[0])
				#   ValueError: invalid literal for int() with base 10: b'4semtl'
				print(err)
				self.report({"ERROR"}, obj_import_err_msg)
				return {'CANCELLED'}
			else:
				raise err
		except IndexError as err:
			if "list index out of range" in str(err):
				# Error such as:
				#   verts_split.append(verts_loc[vert_idx])
				#   IndexError: list index out of range
				print(err)
				self.report({"ERROR"}, obj_import_err_msg)
				return {'CANCELLED'}
			else:
				raise err
		except UnicodeDecodeError as err:
			if "codec can't decode byte" in str(err):
				# Error such as:
				#   keywords["relpath"] = os.path.dirname(bpy.data.filepath)
				#   UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc4 in
				#     position 24: invalid continuation byte
				print(err)
				self.report({"ERROR"}, obj_import_err_msg)
				return {'CANCELLED'}
			else:
				raise err
		except TypeError as err:
			if "enum" in str(err) and "not found in" in str(err):
				# Error such as:
				#   enum "Non-Color" not found in ('AppleP3 Filmic Log Encoding',
				#  'AppleP3 sRGB OETF', ...
				print(err)
				self.report({"ERROR"}, obj_import_err_msg)
				return {'CANCELLED'}
			else:
				raise err
		except AttributeError as err:
			if "object has no attribute 'image'" in str(err):
				# Error such as:
				#   nodetex.image = image
				#   AttributeError: 'NoneType' object has no attribute 'image'
				print(err)
				self.report({"ERROR"}, obj_import_err_msg)
				return {'CANCELLED'}
			else:
				raise err
		except RuntimeError as err:
			# Possible this is the more broad error that even the abvoe
			# items are wrapped under. Generally just prompt user to re-export.
			print(err)
			self.report({"ERROR"}, obj_import_err_msg)
			return {'CANCELLED'}

		if res != {'FINISHED'}:
			self.report({"ERROR"}, "Issue encountered while importing world")
			return {'CANCELLED'}

		prefs = util.get_user_preferences(context)
		detect_world_exporter(self.filepath)
		prefs.MCprep_exporter_type = obj_header.exporter()

		for obj in context.selected_objects:
			obj["MCPREP_OBJ_HEADER"] = True
			obj["MCPREP_OBJ_FILE_TYPE"] = obj_header.texture_type()

		self.split_world_by_material(context)

		addon_prefs = util.get_user_preferences(context)
		self.track_exporter = addon_prefs.MCprep_exporter_type  # Soft detect.
		return {'FINISHED'}

	def obj_name_to_material(self, obj):
		"""Update an objects name based on its first material"""
		if not obj:
			return
		mat = obj.active_material
		if not mat and not obj.material_slots:
			return
		else:
			mat = obj.material_slots[0].material
		if not mat:
			return
		obj.name = util.nameGeneralize(mat.name)

	def split_world_by_material(self, context: Context) -> None:
		"""2.8-only function, split combined object into parts by material"""
		world_name = os.path.basename(self.filepath)
		world_name = os.path.splitext(world_name)[0]

		# Create the new world collection
		prefs = util.get_user_preferences(context)
		if prefs is not None and prefs.MCprep_exporter_type != '(choose)':
			name = f"{prefs.MCprep_exporter_type} world: {world_name}"
		else:
			name = f"minecraft_world: {world_name}"
		worldg = util.collections().new(name=name)
		context.scene.collection.children.link(worldg)  # Add to outliner.

		for obj in context.selected_objects:
			util.move_to_collection(obj, worldg)

		# Force renames based on material, as default names are not useful.
		for obj in worldg.objects:
			self.obj_name_to_material(obj)


class MCPREP_OT_prep_world(bpy.types.Operator):
	"""Class to prep world settings to appropriate default"""
	bl_idname = "mcprep.world"
	bl_label = "Prep World"
	bl_description = "Prep world render settings to something generally useful"
	bl_options = {'REGISTER', 'UNDO'}

	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "prep_world"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		engine = bpy.context.scene.render.engine
		self.track_param = engine
		if not context.scene.world:
			context.scene.world = bpy.data.worlds.new("MCprep world")
		if engine == 'CYCLES':
			self.prep_world_cycles(context)
		elif engine == 'BLENDER_EEVEE':
			self.prep_world_eevee(context)
		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			self.prep_world_internal(context)
		else:
			self.report({'ERROR'}, "Must be cycles, eevee, or blender internal")
		return {'FINISHED'}

	def prep_world_cycles(self, context: Context) -> None:
		if not context.scene.world or not context.scene.world.use_nodes:
			context.scene.world.use_nodes = True

		world_nodes = context.scene.world.node_tree.nodes
		world_links = context.scene.world.node_tree.links

		if "mcprep_world" not in context.scene.world:
			world_nodes.clear()
			skynode = generate.create_node(
				world_nodes, "ShaderNodeTexSky", location=(-280, 300))
			background = generate.create_node(
				world_nodes, "ShaderNodeBackground", location=(10, 300))
			output = generate.create_node(
				world_nodes, "ShaderNodeOutputWorld", location=(300, 300))
			world_links.new(skynode.outputs["Color"], background.inputs[0])
			world_links.new(background.outputs["Background"], output.inputs[0])

		if hasattr(context.scene.world.light_settings, "use_ambient_occlusion"):
			# pre 4.0
			context.scene.world.light_settings.use_ambient_occlusion = False
		else:
			print("Unable to disbale use_ambient_occlusion")

		if hasattr(context.scene, "cycles"):
			context.scene.cycles.caustics_reflective = False
			context.scene.cycles.caustics_refractive = False

			# higher = faster, though potentially noisier; this is a good balance
			context.scene.cycles.light_sampling_threshold = 0.1
			context.scene.cycles.max_bounces = 8

			# Renders faster at a (minor?) cost of the image output
			# TODO: given the output change, consider adding a bool toggle
			context.scene.render.use_simplify = True
			context.scene.cycles.ao_bounces = 2
			context.scene.cycles.ao_bounces_render = 2

	def prep_world_eevee(self, context: Context) -> None:
		"""Default world settings for Eevee rendering"""
		if not context.scene.world or not context.scene.world.use_nodes:
			context.scene.world.use_nodes = True

		world_nodes = context.scene.world.node_tree.nodes
		world_links = context.scene.world.node_tree.links

		if "mcprep_world" not in context.scene.world:
			world_nodes.clear()
			light_paths = generate.create_node(
				world_nodes, "ShaderNodeLightPath", location=(-150, 400))
			background_camera = generate.create_node(
				world_nodes, "ShaderNodeBackground", location=(10, 150))
			background_others = generate.create_node(
				world_nodes, "ShaderNodeBackground", location=(10, 300))
			mix_shader = generate.create_node(
				world_nodes, "ShaderNodeMixShader", location=(300, 300))
			output = generate.create_node(
				world_nodes, "ShaderNodeOutputWorld", location=(500, 300))
			background_others.inputs["Color"].default_value = (0.14965, 0.425823, 1, 1)
			background_others.inputs["Strength"].default_value = 0.1
			background_camera.inputs["Color"].default_value = (0.14965, 0.425823, 1, 1)
			background_camera.inputs["Strength"].default_value = 1
			world_links.new(light_paths.outputs[0], mix_shader.inputs[0])
			world_links.new(
				background_others.outputs["Background"], mix_shader.inputs[1])
			world_links.new(
				background_camera.outputs["Background"], mix_shader.inputs[2])
			world_links.new(mix_shader.outputs["Shader"], output.inputs[0])

		# Increase render speeds by disabling ambienet occlusion.
		if hasattr(context.scene.world.light_settings, "use_ambient_occlusion"):
			# pre 4.0
			context.scene.world.light_settings.use_ambient_occlusion = False
		else:
			print("Unable to disbale use_ambient_occlusion")

		if hasattr(context.scene, "cycles"):
			context.scene.cycles.caustics_reflective = False
			context.scene.cycles.caustics_refractive = False

			# higher = faster, though potentially noisier; this is a good balance
			context.scene.cycles.light_sampling_threshold = 0.1
			context.scene.cycles.max_bounces = 8
			context.scene.cycles.ao_bounces = 2
			context.scene.cycles.ao_bounces_render = 2

		# Renders faster at a (minor?) cost of the image output
		# TODO: given the output change, consider make a bool toggle for this
		bpy.context.scene.render.use_simplify = True

	def prep_world_internal(self, context):
		# check for any suns with the sky setting on;
		if not context.scene.world:
			return
		context.scene.world.use_nodes = False
		context.scene.world.horizon_color = (0.00938029, 0.0125943, 0.0140572)
		context.scene.world.light_settings.use_ambient_occlusion = True
		context.scene.world.light_settings.ao_blend_type = 'MULTIPLY'
		context.scene.world.light_settings.ao_factor = 0.1
		context.scene.world.light_settings.use_environment_light = True
		context.scene.world.light_settings.environment_energy = 0.05
		context.scene.render.use_shadows = True
		context.scene.render.use_raytrace = True
		context.scene.render.use_textures = True

		# check for any sunlamps with sky setting
		sky_used = False
		for lamp in context.scene.objects:
			if lamp.type not in ("LAMP", "LIGHT") or lamp.data.type != "SUN":
				continue
			if lamp.data.sky.use_sky:
				sky_used = True
				break
		if sky_used:
			env.log("MCprep sky being used with atmosphere")
			context.scene.world.use_sky_blend = False
			context.scene.world.horizon_color = (0.00938029, 0.0125943, 0.0140572)
		else:
			env.log("No MCprep sky with atmosphere")
			context.scene.world.use_sky_blend = True
			context.scene.world.horizon_color = (0.647705, 0.859927, 0.940392)
			context.scene.world.zenith_color = (0.0954261, 0.546859, 1)


class MCPREP_OT_add_mc_sky(bpy.types.Operator):
	"""Add sun lamp and time of day (dynamic) driver, setup sky with sun and moon"""
	bl_idname = "mcprep.add_mc_sky"
	bl_label = "Create MC Sky"
	bl_options = {'REGISTER', 'UNDO'}

	def enum_options(self, context: Context) -> List[tuple]:
		"""Dynamic set of enums to show based on engine"""
		engine = bpy.context.scene.render.engine
		enums = []
		if bpy.app.version >= (2, 77) and engine in ("CYCLES", "BLENDER_EEVEE"):
			enums.append((
				"world_shader",
				"Dynamic sky + shader sun/moon",
				"Import dynamic sky and shader-based sun and moon"))
		enums.append((
			"world_mesh",
			"Dynamic sky + mesh sun/moon",
			"Import dynamic sky and mesh sun and moon"))
		enums.append((
			"world_only",
			"Dynamic sky only",
			"Import dynamic sky, with no sun or moon"))
		enums.append((
			"world_static_mesh",
			"Static sky + mesh sun/moon",
			"Create static sky with mesh sun and moon"))
		enums.append((
			"world_static_only",
			"Static sky only",
			"Create static sky, with no sun or moon"))
		return enums

	world_type: bpy.props.EnumProperty(
		name="Sky type",
		description=(
			"Decide to improt dynamic (time/hour-controlled) vs static sky "
			"(daytime only), and the type of sun/moon (if any) to use"),
		items=enum_options)
	initial_time: bpy.props.EnumProperty(
		name="Set time (dynamic only)",
		description="Set initial time of day, only supported for dynamic sky types",
		items=(
			("8", "Morning", "Set initial time to 9am"),
			("12", "Noon", "Set initial time to 12pm"),
			("18", "Sunset", "Set initial time to 6pm"),
			("0", "Midnight", "Set initial time to 12am"),
			("6", "Sunrise", "Set initial time to 6am"))
	)
	add_clouds: bpy.props.BoolProperty(
		name="Add clouds",
		description="Add in a cloud mesh",
		default=True)
	remove_existing_suns: bpy.props.BoolProperty(
		name="Remove initial suns",
		description="Remove any existing sunlamps",
		default=True)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

	def draw(self, context):
		self.layout.prop(self, "world_type")
		# self.layout.prop(self, "initial_time")
		# issue updating driver when set this way
		row = self.layout.row()
		row.prop(self, "add_clouds")
		row.prop(self, "remove_existing_suns")
		row = self.layout.row()
		row.label(
			text="Note: Dynamic skies use drivers, enable auto-run python scripts")

	track_function = "world_time"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		# must be in object mode
		if context.mode != "OBJECT":
			bpy.ops.object.mode_set(mode="OBJECT")

		new_objs = []
		if self.remove_existing_suns:
			for lamp in context.scene.objects:
				if lamp.type not in ("LAMP", "LIGHT") or lamp.data.type != "SUN":
					continue
				util.obj_unlink_remove(lamp, True)

		engine = context.scene.render.engine
		wname = None
		if engine == "BLENDER_EEVEE":
			blend = "clouds_moon_sun_eevee.blend"
			wname = "MCprepWorldEevee"
		else:
			blend = "clouds_moon_sun.blend"
			wname = "MCprepWorldCycles"

		blendfile = os.path.join(
			os.path.dirname(__file__), "MCprep_resources", blend)

		prev_world = None
		if self.world_type in ("world_static_mesh", "world_static_only"):
			# Create world dynamically (previous, simpler implementation)
			new_sun = self.create_sunlamp(context)
			new_objs.append(new_sun)

			if engine in ('BLENDER_RENDER', 'BLENDER_GAME'):
				world = context.scene.world
				if not world:
					world = bpy.data.worlds.new("MCprep World")
					context.scene.world = world
				new_sun.data.shadow_method = 'RAY_SHADOW'
				new_sun.data.shadow_soft_size = 0.5
				world.use_sky_blend = False
				world.horizon_color = (0.00938029, 0.0125943, 0.0140572)
			bpy.ops.mcprep.world(skipUsage=True)  # do rest of sky setup

		elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
			if not os.path.isfile(blendfile):
				self.report(
					{'ERROR'},
					f"Source MCprep world blend file does not exist: {blendfile}")
				env.log(
					f"Source MCprep world blend file does not exist: {blendfile}")
				return {'CANCELLED'}
			if wname in bpy.data.worlds:
				prev_world = bpy.data.worlds[wname]
				prev_world.name = "-old"
			new_objs += self.create_dynamic_world(context, blendfile, wname)

		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			# dynamic world using built-in sun sky and atmosphere
			new_sun = self.create_sunlamp(context)
			new_objs.append(new_sun)
			new_sun.data.shadow_method = 'RAY_SHADOW'
			new_sun.data.shadow_soft_size = 0.5

			world = context.scene.world
			if not world:
				world = bpy.data.worlds.new("MCprep World")
				context.scene.world = world
			world.use_sky_blend = False
			world.horizon_color = (0.00938029, 0.0125943, 0.0140572)

			# be sure to turn off all other sun lamps with atmosphere set
			new_sun.data.sky.use_sky = True  # use sun orientation settings if BI
			for lamp in context.scene.objects:
				if lamp.type not in ("LAMP", "LIGHT") or lamp.data.type != "SUN":
					continue
				if lamp == new_sun:
					continue
				lamp.data.sky.use_sky = False

			time_obj = get_time_object()
			if not time_obj:
				env.log(
					"TODO: implement create time_obj, parent sun to it & driver setup")

		if self.world_type in ("world_static_mesh", "world_mesh"):
			if not os.path.isfile(blendfile):
				self.report(
					{'ERROR'},
					f"Source MCprep world blend file does not exist: {blendfile}")
				env.log(
					f"Source MCprep world blend file does not exist: {blendfile}")
				return {'CANCELLED'}
			resource = f"{blendfile}/bpy.types.Object"

			util.bAppendLink(resource, "MoonMesh", False)
			non_empties = [
				ob for ob in context.selected_objects if ob.type != 'EMPTY']
			if non_empties:
				moonmesh = non_empties[0]
				tobj = get_time_object()
				if tobj != moonmesh:
					# Sometimes would error, see report -MfO6dDjpxFF4lfqqYGM
					moonmesh.parent = tobj
				new_objs.append(moonmesh)
			else:
				self.report({'WARNING'}, "Could not add moon")

			util.bAppendLink(resource, "SunMesh", False)
			non_empties = [
				ob for ob in context.selected_objects if ob.type != 'EMPTY']
			if non_empties:
				sunmesh = non_empties[0]
				tobj = get_time_object()
				if tobj != moonmesh:
					sunmesh.parent = tobj
				new_objs.append(sunmesh)
			else:
				self.report({'WARNING'}, "Could not add sun")

		if prev_world:
			bpy.data.worlds.remove(prev_world)

		if self.add_clouds:
			resource = blendfile + "/Object"
			util.bAppendLink(resource, "clouds", False)
			new_objs += list(context.selected_objects)
			if engine in ('BLENDER_RENDER', 'BLENDER_GAME'):
				materials = util.materialsFromObj(context.selected_objects)
				for mat in materials:
					mat.use_nodes = False
					mat.use_shadeless = False
					mat.translucency = 1

			# Now also increase camera render distance to see clouds
			cams = [obj for obj in bpy.data.objects if obj.type == "CAMERA"]
			for cam in cams:
				cam.data.clip_end = 1000  # 1000 matches explicitly to shader

		# ensure all new objects (lights, meshes, control objs) in same group
		if "mcprep_world" in util.collections():
			util.collections()["mcprep_world"].name = "mcprep_world_old"
		time_group = util.collections().new("mcprep_world")
		for obj in new_objs:
			time_group.objects.link(obj)

		self.track_param = self.world_type
		self.track_param = engine
		return {'FINISHED'}

	def create_sunlamp(self, context: Context) -> bpy.types.Object:
		"""Create new sun lamp from primitives"""
		if hasattr(bpy.data, "lamps"):  # 2.7
			newlamp = bpy.data.lamps.new("Sun", "SUN")
		else:  # 2.8
			newlamp = bpy.data.lights.new("Sun", "SUN")
		obj = bpy.data.objects.new("Sunlamp", newlamp)
		obj.location = (0, 0, 20)
		obj.rotation_euler[0] = 0.481711
		obj.rotation_euler[1] = 0.303687
		obj.rotation_euler[1] = 0.527089
		obj.data.energy = 1.0
		# obj.data.color
		util.obj_link_scene(obj, context)
		util.scene_update(context)
		if hasattr(obj, "use_contact_shadow"):
			obj.use_contact_shadow = True
		return obj

	def create_dynamic_world(self, context: Context, blendfile: Path, wname: str) -> List[bpy.types.Object]:
		"""Setup fpr creating a dynamic world and setting up driver targets"""
		resource = blendfile + "/World"
		obj_list = []

		global time_obj_cache
		if time_obj_cache:
			try:
				util.obj_unlink_remove(time_obj_cache, True, context)
			except Exception as e:
				print(f"Error, could not unlink time_obj_cache {time_obj_cache}")
				print(e)

		time_obj_cache = None  # force reset to use newer cache object

		# Append the world (and time control elements)
		util.bAppendLink(resource, wname, False)
		obj_list += list(context.selected_objects)

		if wname in bpy.data.worlds:
			context.scene.world = bpy.data.worlds[wname]
			context.scene.world["mcprep_world"] = True
		else:
			self.report({'ERROR'}, "Failed to import new world")
			env.log("Failed to import new world")

		# assign sun/moon shader accordingly
		use_shader = 1 if self.world_type == "world_shader" else 0
		for node in context.scene.world.node_tree.nodes:
			if node.type != "GROUP":
				continue
			node.inputs[3].default_value = use_shader

		# set initial times of day, if dynamic
		# time_obj = get_time_object()
		# time_obj["MCprepHour"] = float(self.initial_time)

		# # update drivers, needed if time has changed vs import source
		# if context.scene.world.node_tree.animation_data:
		#	# context.scene.world.node_tree.animation_data.drivers[0].update()
		#	drivers = context.scene.world.node_tree.animation_data.drivers[0]
		#	drivers.driver.variables[0].targets[0].id = time_obj
		#	# nope, still doesn't work.

		# if needed: create time object and setup drivers
		# if not time_obj:
		# 	env.log("Creating time_obj")
		# 	time_obj = bpy.data.objects.new('MCprep Time Control', None)
		# 	util.obj_link_scene(time_obj, context)
		# 	global time_obj_cache
		# 	time_obj_cache = time_obj
		# 	if hasattr(time_obj, "empty_draw_type"):  # 2.7
		# 		time_obj.empty_draw_type = 'SPHERE'
		# 	else:  # 2.8
		# 		time_obj.empty_display_type = 'SPHERE'
		# first, get the driver
		# if (not world.node_tree.animation_data
		# 		or not world.node_tree.animation_data.drivers
		# 		or not world.node_tree.animation_data.drivers[0].driver):
		# 	env.log("Could not get driver from imported dynamic world")
		# 	self.report({'WARNING'}, "Could not update driver for dynamic world")
		# 	driver = None
		# else:
		#	driver = world.node_tree.animation_data.drivers[0].driver
		# if driver and driver.variables[0].targets[0].id_type == 'OBJECT':
		#	driver.variables[0].targets[0].id = time_obj
		# add driver to control obj's x rotation

		return obj_list


class MCPREP_OT_time_set(bpy.types.Operator):
	"""Set the time affecting light, sun and moon position, similar to in-game commands"""
	bl_idname = "mcprep.time_set"
	bl_label = "Set time of day"
	bl_options = {'REGISTER', 'UNDO'}

	# subject center to place lighting around
	time_enum: bpy.props.EnumProperty(
		name="Time selection",
		description="Select between the different reflections",
		items=[
			("1000", "Day", "Time (day)=1,000, morning time"),
			("6000", "Noon", "Time=6,000, sun is at zenith"),
			# Approx matching resource:
			("12000", "Sunset", "Time=12,000, sun starts setting"),
			# matches command:
			("13000", "Night", "Time (night)=13,000"),
			# matches reference:
			("18000", "Midnight", "Time=18,000, moon at zenish"),
			("23000", "Sunrise", "Time set day=23,000, sun first visible")
		])
	day_offset: bpy.props.IntProperty(
		name="Day offset",
		description="Offset by number of days (ie +/- 24000*n)",
		default=0)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

	def draw(self, context):
		self.layout.prop(self, "time_enum")
		self.layout.prop(self, "day_offset")
		self.layout.prop(self, "keyframe")

	@tracking.report_error
	def execute(self, context):
		new_time = 24 * self.day_offset
		new_time += int(self.time_enum)
		context.scene.mcprep_props.world_time = new_time
		if bpy.context.scene.tool_settings.use_keyframe_insert_auto:
			if not context.scene.animation_data:
				context.scene.animation_data_create()
			anim_data = context.scene.animation_data
			if not anim_data.action:
				ac = bpy.data.actions.new("SceneAnimation")
				anim_data.action = ac
			context.scene.mcprep_props.keyframe_insert(
				"world_time")

		return {'FINISHED'}


class MCPREP_OT_render_helper():
	render_queue = []
	render_queue_cleanup = []

	old_res_x = None
	old_res_y = None
	original_cam = None

	filepath = None

	rendered_count = 0
	rendering = False
	current_render = {}
	prior_frame = {}
	previews = []
	open_folder = False

	def cleanup_scene(self):
		# Clean up
		env.log("Cleanup pano rendering")
		for i in range(len(self.render_queue_cleanup)):
			util.obj_unlink_remove(self.render_queue_cleanup[i]["camera"], True)

		bpy.context.scene.render.resolution_x = self.old_res_x
		bpy.context.scene.render.resolution_y = self.old_res_y
		bpy.context.scene.camera = self.original_cam

		self.rendered_count = 0

		# Attempt to remove self from handlers.
		try:
			bpy.app.handlers.render_cancel.remove(self.cancel_render)
			bpy.app.handlers.render_complete.remove(self.render_next_in_queue)
		except ValueError as e:
			print("Failed to remove handler:", e)

		self.rendering = False
		self.render_queue_cleanup = []

		self.display_current(use_rendered=True)
		for img in self.previews:
			bpy.data.images.remove(img)

		if self.open_folder:
			bpy.ops.mcprep.openfolder(folder=self.filepath)

	def create_panorama_cam(self, name: str, camera_data: Camera, rot: VectorType, loc: VectorType) -> bpy.types.Object:
		"""Create a camera"""

		camera = bpy.data.objects.new(name, camera_data)
		camera.rotation_euler = rot
		camera.location = loc
		util.obj_link_scene(camera)
		return camera

	def cancel_render(self, scene) -> None:
		env.log("Cancelling pano render queue")
		self.render_queue = []
		self.cleanup_scene()

	def display_current(self, use_rendered: bool=False) -> None:
		"""Display the most recent image in a window."""
		if self.rendered_count == 0:
			bpy.ops.render.view_show("INVOKE_DEFAULT")

		# Set up the window as needed.
		area = None
		for window in reversed(bpy.context.window_manager.windows):
			this_area = window.screen.areas[0]
			if this_area.type == "IMAGE_EDITOR":
				area = this_area
				break
		if not area:
			print("Could not fetch area tod isplay interim pano render")
			return

		if self.rendering:
			header_text = f"Pano render in progress: {self.rendered_count}/6 done"
		else:
			header_text = "Pano render finished"

		env.log(header_text)
		area.header_text_set(header_text)
		area.show_menus = False

		if use_rendered:
			img = bpy.data.images.get("Render Result")
			if img:
				area.spaces[0].image = img
		elif self.rendered_count > 0 and self.prior_frame:
			path = os.path.join(self.filepath, self.prior_frame["filename"])
			print(path)
			if not os.path.isfile(path):
				print("Failed to find pano frame to load preview")
			elif area:
				img = bpy.data.images.load(path)  # DO cleanup.
				area.spaces[0].image = img
				self.previews.append(img)

		for region in area.regions:
			region.tag_redraw()

	def render_next_in_queue(self, scene, dummy):
		"""Render the next image in the queue"""
		if not self.rendering:
			self.rendering = True  # The initial call.
		else:
			self.rendered_count += 1
			self.prior_frame = self.current_render

		if not self.render_queue:
			env.log("Finished pano render queue")
			self.cleanup_scene()
			return

		self.current_render = self.render_queue.pop()
		file_name = self.current_render["filename"]

		bpy.context.scene.camera = self.current_render["camera"]

		bpy.context.scene.render.filepath = os.path.join(
			self.filepath, file_name)

		env.log(f"Starting pano render {file_name}")
		self.display_current()

		bpy.app.timers.register(
			render_pano_frame_timer, first_interval=0.05, persistent=False)


render_helper = MCPREP_OT_render_helper()


def init_render_timer() -> None:
	"""Helper for pano renders to offset the start of the queue from op run."""
	env.log("Initial render timer started pano queue")
	render_helper.render_next_in_queue(None, None)


def render_pano_frame_timer() -> None:
	"""Pano render timer callback, giving a chance to refresh display."""
	bpy.ops.render.render(
		'EXEC_DEFAULT', write_still=True, use_viewport=False)


class MCPREP_OT_render_panorama(bpy.types.Operator, ExportHelper):
	"""Render the Panorama images for a texture Pack"""
	bl_idname = "mcprep.render_panorama"
	bl_label = "Render Panorama"
	bl_description = "Render Panorama for texture Pack"
	bl_options = {'REGISTER', 'UNDO'}

	panorama_resolution: bpy.props.IntProperty(
		name="Render resolution",
		description="The resolution of the output images",
		default=1024
	)
	open_folder: bpy.props.BoolProperty(
		name="Open folder when done",
		description="Open the output folder when render completes",
		default=False)

	filepath: bpy.props.StringProperty(subtype='DIR_PATH')
	filename_ext = ""  # Not used, but required by ExportHelper.

	def draw(self, context):
		col = self.layout.column()
		col.scale_y = 0.8
		col.label(text="Pick the output folder")
		col.label(text="to place pano images.")
		self.layout.prop(self, "panorama_resolution")
		self.layout.prop(self, "open_folder")

	def execute(self, context):
		# Save old Values
		render_helper.original_cam = bpy.context.scene.camera
		render_helper.old_res_x = bpy.context.scene.render.resolution_x
		render_helper.old_res_y = bpy.context.scene.render.resolution_y
		render_helper.filepath = self.filepath
		render_helper.open_folder = self.open_folder

		camera_data = bpy.data.cameras.new(name="panorama_cam")
		camera_data.angle = math.pi / 2

		pi_half = math.pi / 2
		orig_pos = render_helper.original_cam.location
		render_helper.render_queue.append({
			"camera": render_helper.create_panorama_cam(
				"panorama_0", camera_data, (pi_half, 0.0, 0.0), orig_pos),
			"filename": "panorama_0.png"
		})
		render_helper.render_queue.append({
			"camera": render_helper.create_panorama_cam(
				"panorama_1", camera_data, (pi_half, 0.0, math.pi + pi_half), orig_pos),
			"filename": "panorama_1.png"
		})
		render_helper.render_queue.append({
			"camera": render_helper.create_panorama_cam(
				"panorama_2", camera_data, (pi_half, 0.0, math.pi), orig_pos),
			"filename": "panorama_2.png"
		})
		render_helper.render_queue.append({
			"camera": render_helper.create_panorama_cam(
				"panorama_3", camera_data, (pi_half, 0.0, pi_half), orig_pos),
			"filename": "panorama_3.png"
		})
		render_helper.render_queue.append({
			"camera": render_helper.create_panorama_cam(
				"panorama_4", camera_data, (math.pi, 0.0, 0.0), orig_pos),
			"filename": "panorama_4.png"
		})
		render_helper.render_queue.append({
			"camera": render_helper.create_panorama_cam(
				"panorama_5", camera_data, (0.0, 0.0, 0.0), orig_pos),
			"filename": "panorama_5.png"
		})

		render_helper.render_queue_cleanup = render_helper.render_queue.copy()

		# Do the renderage
		bpy.context.scene.render.resolution_x = self.panorama_resolution
		bpy.context.scene.render.resolution_y = self.panorama_resolution
		bpy.app.handlers.render_cancel.append(render_helper.cancel_render)
		bpy.app.handlers.render_complete.append(render_helper.render_next_in_queue)

		render_helper.display_current()

		bpy.app.timers.register(
			init_render_timer, first_interval=0.05, persistent=False)

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Above for UI
# Below for register
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_open_jmc2obj,
	MCPREP_OT_install_jmc2obj,
	MCPREP_OT_open_mineways,
	MCPREP_OT_install_mineways,
	MCPREP_OT_prep_world,
	MCPREP_OT_add_mc_sky,
	MCPREP_OT_time_set,
	MCPREP_OT_import_world_split,
	MCPREP_OT_render_panorama,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
