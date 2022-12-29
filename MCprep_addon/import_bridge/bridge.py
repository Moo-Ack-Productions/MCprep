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
import time

import bpy
from bpy_extras.io_utils import ImportHelper

from .mineways_connector import MinewaysConnector
from .jmc_connector import JmcConnector
from ..conf import env
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
#	General functions
# -----------------------------------------------------------------------------

connector = None  # global reference to persistent connector obj
world_saves = [] # save enum UI list to memory
exec_exists_cache = None # cache OS filecheck


def initialize_connector(context):
	"""Setup the global connector and load some initial values"""
	global connector

	prefs = util.get_user_preferences(context)
	#if prefs.MCprep_exporter_type ==

	if connector:
		return
	addon_prefs = util.get_user_preferences(context)
	mineways_exec = addon_prefs.open_mineways_path
	saves = context.scene.mcprep_props.save_folder
	connector = MinewaysConnector(mineways_exec, saves)
	if context.scene.mcprep_props.bridge_world:
		connector.set_world(context.scene.mcprep_props.bridge_world)


def world_saves_enum(self, context):
	"""Generate and cache enum list of world saves"""
	global world_saves
	if world_saves:
		return world_saves

	world_saves = [("", "(Select world)", "Select a world save file to bridge")]
	saves = context.scene.mcprep_props.save_folder
	saves_folders = [world for world in os.listdir(saves)
		if os.path.isdir(os.path.join(saves, world))]
	for world in sorted(saves_folders):
		world_saves.append((
			world,
			world,
			"Set active world to save folder "+world
			))
	return world_saves


# def world_save_update(self, context):
# 	"""Update after changing the world save file"""
# 	initialize_connector(context)
# 	connector.set_world(context.scene.mcprep_props.bridge_world)


def exec_exists(exec_path):
	"""Check path and cache to limit recalls"""
	global exec_exists_cache
	exec_exists_cache = os.path.isfile(exec_path)
	return exec_exists_cache


# -----------------------------------------------------------------------------
#	Operators and panels
# -----------------------------------------------------------------------------


def panel_draw(self, context):
	"""Panel draw function for UI"""
	layout = self.layout

	addon_prefs = util.get_user_preferences(context)
	mineways_exec = addon_prefs.open_mineways_path
	if not exec_exists(mineways_exec):
		box = layout.box()
		col = box.column(align=True)
		col.scale_y = 0.8
		col.label(text="Mineways executable not set!")
		col.label(text="Install and set path in preferences to use bridge.")
		box.operator("mcprep.install_mineways")

	# preview image
	layout.label(text="Select world")
	layout.prop(context.scene.mcprep_props, "bridge_world", text="")
	layout.label(text="")
	col = layout.column(align=True)
	col.operator("mcprep.bridge_world_import_reference")
	col.operator("mcprep.bridge_world_import")
	col.operator("mcprep.bridge_world_refresh")
	col.operator("mcprep.bridge_world_extend")
	# preferences to change world path etc


class MCPREP_OT_preview_import(bpy.types.Operator):
	"""Load and place a preview image of the world to be imported."""
	bl_idname = "mcprep.bridge_world_preview"
	bl_label = "Preview World Import"
	bl_options = {'REGISTER', 'UNDO'}

class MCPREP_OT_import_world_from_objmeta(bpy.types.Operator, ImportHelper):
	"""Loads a Minecraft world into Blender using same settings as referenced OBJ file exported from Mineways"""
	bl_idname = "mcprep.bridge_world_import_reference"
	bl_label = "Import World from Reference"
	bl_options = {'REGISTER', 'UNDO'}

	filter_glob = bpy.props.StringProperty(
		default=".obj",  # verify this works
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(
		type=bpy.types.PropertyGroup,
		options={'HIDDEN', 'SKIP_SAVE'})
	# filter_image = bpy.props.BoolProperty(
	# 	default=True,
	# 	options={'HIDDEN', 'SKIP_SAVE'})

	track_function = "bridge_import_ref"
	# track_param = ""
	@tracking.report_error
	def execute(self, context):

		if not self.filepath:
			raise Exception

		# read obj file, extract the settings
		# save settings to [empty object? Collection itself?]


		bpy.ops.mcprep.bridge_world_import('INVOKE_DEFAULT') # and add the props as just-read
		return {'FINISHED'}



class MCPREP_OT_import_new_world(bpy.types.Operator):
	"""Loads a Minecraft world into Blender from a save file (via a Mineways bridge)"""
	bl_idname = "mcprep.bridge_world_import"
	bl_label = "Import World"
	bl_options = {'REGISTER', 'UNDO'}

	world_center = bpy.props.IntVectorProperty(
		name = "World center",
		description = "Select the X-Z center of import from the Minecraft save",
		default = (0, 0),
		subtype = 'XZ',
		size = 2,
		)
	import_center = bpy.props.IntVectorProperty(
		name = "Import location",
		description = "Move the center of the imported world to this location",
		default = (0, 0, 0),
		subtype = 'XYZ',
		size = 3,
		)
	import_height_offset = bpy.props.IntProperty(
		name = "Height offset",
		description = "Lower or raise the imported world by this amount",
		default = 0,
		)
	block_radius = bpy.props.IntProperty(
		name = "Block radius",
		description = "Radius of export, from World Center to all directions around",
		default = 100,
		min = 1
		)
	ceiling = bpy.props.IntProperty(
		name = "Height/ceiling",
		description = "The top level of the world to import",
		default = 256,
		min = 1,
		max = 512
		)
	floor = bpy.props.IntProperty(
		name = "Depth/floor",
		description = "The bottom level of the world to import",
		default = 0,
		min = 1,
		max = 512
		)
	use_chunks = bpy.props.BoolProperty(
		name = "Use chunks",
		description = "Export the world with separate sections per chunk. In the background, each chunk is one export from Mineways",
		default = True
		)
	chunk_size = bpy.props.IntProperty(
		name = "Chunk size",
		description = "Custom size of chunks to import",
		default = 16,
		min = 8
		)
	separate_blocks = bpy.props.BoolProperty(
		name = "Object per block",
		description = "Create one object per each block in the world (warning: will be slow, make exports larger, and make Blender slower!!)",
		default = False
		)
	prep_materials = bpy.props.BoolProperty(
		name = "Prep materials",
		default = True
		)
	animate_textures = bpy.props.BoolProperty(
		name = "Animate textures",
		default = False
		)
	single_texture = bpy.props.BoolProperty(
		name = "Single texture file",
		description = "Export the world with a single texture. Cannot use with animate textures",
		default = False
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=300*util.ui_scale())

	def draw(self, context):
		self.layout.prop(self, "first_corner")  # maybe use height max and min separately?
		self.layout.prop(self, "second_corner")
		row = self.layout.row()
		row.prop(self, "use_chunks")
		subcol = row.column()
		# subcol.enabled = self.use_chunks # use if can redraw tag
		subcol.prop(self, "chunk_size")

		col = self.layout.column(align=True)
		col.scale_y = 0.8
		col.label(text="Press OK to import/bridge world.", icon='TRIA_DOWN')
		col.label(text="This will launch Mineways in background.")
		col.label(text="The program may pop up or show dialogs,")
		col.label(text="Blender will hang until Mineways closes or is closed.")

	track_function = "bridge_import"
	track_param = ""
	@tracking.report_error
	def execute(self, context):
		initialize_connector(context)

		if not bpy.data.filepath:
			self.report({"ERROR"},
				"Must save blend file before bridging world save")
			return {'CANCELLED'}
		if not connector.world:
			self.report({"ERROR"},
				"No world set/found")
			return {'CANCELLED'}

		# take coordinates and convert to batch list; for now, single export
		t0 = time.time()

		# create world bridge path
		obj_path = os.path.join(
			os.path.dirname(bpy.data.filepath),
			"_" + connector.world + "_exp.obj"
			)
		mat_path = os.path.join(
			os.path.dirname(bpy.data.filepath),
			"_" + connector.world + "_exp.mtl"
			)

		env.log("Running Mineways bridge to import world "+ connector.world)
		connector.run_export_single(
			obj_path,
			list(self.first_corner),
			list(self.second_corner)
			)
		t1 = time.time()

		# TODO: Implement check/connector class check for success, not just file existing
		if not os.path.isfile(obj_path):
			self.report({"ERROR"}, "OBJ file not exported, try using Mineways on its own to export OBJ")
			env.log("OBJ file not found to import: "+obj_path)
			return {"CANCELLED"}
		env.log("Now importing the exported obj into blender")
		bpy.ops.import_scene.obj(filepath=obj_path)
		# consider removing old world obj's?

		t2 = time.time()
		env.log("Mineways bridge completed in: {}s (Mineways: {}s, obj import: {}s".format(
			int(t2-t0), int(t1-t0), int(t2-t1)))

		self.report({'INFO'}, "Bridge completed finished")
		return {'FINISHED'}


class MCPREP_OT_refresh_world(bpy.types.Operator):
	"""Refresh an already loaded Minecraft world from latest save file"""
	bl_idname = "mcprep.bridge_world_refresh"
	bl_label = "Refresh World"
	bl_options = {'REGISTER', 'UNDO'}

	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	track_function = "bridge_refresh"
	@tracking.report_error
	def execute(self, context):
		self.report({'ERROR'}, "Not yet implemented")
		return {'CANCELLED'}


class MCPREP_OT_extend_world(bpy.types.Operator):
	"""Extend the size of the world by adding more world chunk handlers"""
	bl_idname = "mcprep.bridge_world_extend"
	bl_label = "Extend World"

	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	track_function = "bridge_refresh"
	@tracking.report_error
	def execute(self, context):
		self.report({'ERROR'}, "Not yet implemented")
		return {'CANCELLED'}


# -----------------------------------------------------------------------------
#	Register
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_import_world_from_objmeta,
	MCPREP_OT_import_new_world,
	MCPREP_OT_refresh_world,
	MCPREP_OT_extend_world
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
