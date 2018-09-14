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
import os
import addon_utils

from . import conf
from . import util
from . import tracking


# -----------------------------------------------------------------------------
# General utility operator classes
# -----------------------------------------------------------------------------


class McprepImproveUi(bpy.types.Operator):
	"""Improve UI for minecraft textures: disable mipmaps, set texture solid
	in viewport, and set rendermode to at least solid view"""
	bl_idname = "mcprep.improve_ui"
	bl_label = "Improve UI"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		context.space_data.show_textured_solid = True
		context.user_preferences.system.use_mipmaps = False

		texviewable = ['TEXTURED','MATEIRAL','RENDERED']
		engine = bpy.context.scene.render.engine
		if context.space_data.viewport_shade not in texviewable:
			if engine == 'CYCLES':  # or engine == 'BLENDER_EEVEE'
				context.space_data.viewport_shade = 'TEXTURED'
			else:
				context.space_data.viewport_shade = 'SOLID'
		return {'FINISHED'}


class McprepShowPreferences(bpy.types.Operator):
	"""Open user preferences and display the MCprep settings."""
	bl_idname = "mcprep.open_preferences"
	bl_label = "Show MCprep preferences"

	tab = bpy.props.EnumProperty(
		items = [('settings', 'Open settings', 'Open MCprep preferences settings'),
				('tutorials', 'Open tutorials', 'View MCprep tutorials'),
				('tracker_updater', 'Open tracker/updater settings',
					'Open user tracking & addon updating settings')],
		name = "Exporter")

	@tracking.report_error
	def execute(self, context):
		bpy.ops.screen.userpref_show('INVOKE_AREA')
		context.user_preferences.active_section = "ADDONS"
		bpy.data.window_managers["WinMan"].addon_search = "MCprep"

		addons_ids = [mod for mod in addon_utils.modules(refresh=False)
						if mod.__name__ == __package__]
		addon_blinfo = addon_utils.module_bl_info(addons_ids[0])
		if not addon_blinfo["show_expanded"]:
			bpy.ops.wm.addon_expand(module=__package__)

		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		addon_prefs.preferences_tab = self.tab
		return {'FINISHED'}


class McprepOpenFolder(bpy.types.Operator):
	"""Open a folder in the host operating system"""
	bl_idname = "mcprep.openfolder"
	bl_label = "Open folder"

	folder = bpy.props.StringProperty(
		name="Folderpath",
		default="//")

	@tracking.report_error
	def execute(self,context):
		if os.path.isdir(bpy.path.abspath(self.folder))==False:
			self.report({'ERROR'}, "Invalid folder path: {x}".format(x=self.folder))
			return {'CANCELLED'}

		res = util.open_folder_crossplatform(self.folder)
		if res==False:
			msg = "Didn't open folder, navigate to it manually: {x}".format(x=self.folder)
			print(msg)
			self.report({'ERROR'},msg)
			return {'CANCELLED'}
		return {'FINISHED'}


class McprepOpenHelp(bpy.types.Operator):
	"""Support operator for opening url in UI, but indicating through popup
	text that it is a supporting/help button."""
	bl_idname = "mcprep.open_help"
	bl_label = "Open folder"
	bl_description = "Need help? Click to open."

	url = bpy.props.StringProperty(
		name="Url",
		default="")

	@tracking.report_error
	def execute(self,context):
		if self.url == "":
			return {'CANCELLED'}
		else:
			bpy.ops.wm.url_open(url=self.url)
		return {'FINISHED'}


class McprepPrepMaterialLegacy(bpy.types.Operator):
	"""Legacy operator which calls new operator, use mcprep.prep_material"""
	bl_idname = "mcprep.mat_change"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

	useReflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropriate materials to be rendered reflective",
		default = True
		)
	combineMaterials = bpy.props.BoolProperty(
		name = "Combine materials",
		description = "Consolidate duplciate materials & textures",
		default = False
		)

	track_function = "materials_legacy"

	@tracking.report_error
	def execute(self, context):
		print("Using legacy operator call for MCprep materials")
		bpy.ops.mcprep.prep_materials(
			useReflections = self.useReflections,
			combineMaterials = self.combineMaterials
		)
		return {'FINISHED'}

# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register():
	pass

def unregister():
	pass
