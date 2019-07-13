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


class MCPREP_OT_improve_ui(bpy.types.Operator):
	"""Improve UI for minecraft textures: disable mipmaps, set texture solid
	in viewport, and set rendermode to at least solid view"""
	bl_idname = "mcprep.improve_ui"
	bl_label = "Improve UI"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		# Disable mipmaps (not saved, but avoids on screen blurry textures)
		prefs = util.get_preferences(context)
		if hasattr(prefs.system, "use_mipmaps"):
			prefs.system.use_mipmaps = False

		# show textures in solid mode
		view = context.space_data
		if hasattr(view, "show_textured_solid"): # 2.7
			context.space_data.show_textured_solid = True
		elif view.type == 'VIEW_3D' and hasattr(context.scene, "display"):
			try: # can fail e.g. in workbench view
				view.shading.color_type = "TEXTURE"
				view.shading.background_type = "WORLD"
			except:
				pass
		elif hasattr(context.screen, "shading"): # 2.8 non shaded view
			try: # can fail e.g. in workbench view
				context.scene.display.shading.color_type = "TEXTURE"
				context.scene.display.shading.background_type = "WORLD"
			except:
				pass

		# now change the active drawing level to a minimum of solid mode
		view27 = ['TEXTURED','MATEIRAL','RENDERED']
		view28 = ['SOLID', 'MATERIAL', 'RENDERED']
		engine = bpy.context.scene.render.engine
		if not util.bv28() and context.space_data.viewport_shade not in view27:
			if engine == 'CYCLES': # or engine == 'BLENDER_EEVEE':
				context.space_data.viewport_shade = 'TEXTURED'
			else:
				context.space_data.viewport_shade = 'SOLID'
		elif util.bv28() and context.scene.display.shading.type not in view28:
			# must go through all spaces to find the match screen[].layout.space...
			# and then apply, e.g.

			# make it solid mode, regardless of cycles or eevee
			context.scene.display.shading.type = 'SOLID'
		return {'FINISHED'}


class MCPREP_OT_show_preferences(bpy.types.Operator):
	"""Open user preferences and display MCprep settings"""
	bl_idname = "mcprep.open_preferences"
	bl_label = "Show MCprep preferences"

	tab = bpy.props.EnumProperty(
		items = [('settings', 'Open settings', 'Open MCprep preferences settings'),
				('tutorials', 'Open tutorials', 'View MCprep tutorials'),
				('tracker_updater', 'Open tracker/updater settings',
					'Open user tracking & addon updating settings')],
		name = "Section")

	@tracking.report_error
	def execute(self, context):
		bpy.ops.screen.userpref_show('INVOKE_AREA')
		util.get_preferences(context).active_section = "ADDONS"
		bpy.data.window_managers["WinMan"].addon_search = "MCprep"

		addons_ids = [mod for mod in addon_utils.modules(refresh=False)
						if mod.__name__ == __package__]
		addon_blinfo = addon_utils.module_bl_info(addons_ids[0])
		if not addon_blinfo["show_expanded"]:
			if hasattr(bpy.ops, "preferences") and hasattr(bpy.ops.preferences, "addon_expand") and util.bv28(): # later 2.8 buids
				bpy.ops.preferences.addon_expand(module=__package__)
			elif hasattr(bpy.ops, "wm") and hasattr(bpy.ops.wm, "addon_expand"): # old 2.8 and 2.7
				bpy.ops.wm.addon_expand(module=__package__)
			else:
				self.report({"INFO"}, "Search for and expand the MCprep addon in preferences")

		addon_prefs = util.get_user_preferences(context)
		addon_prefs.preferences_tab = self.tab
		return {'FINISHED'}


class MCPREP_OT_open_folder(bpy.types.Operator):
	"""Open a folder in the host operating system"""
	bl_idname = "mcprep.openfolder"
	bl_label = "Open folder"

	folder = bpy.props.StringProperty(
		name="Folderpath",
		default="//")

	@tracking.report_error
	def execute(self,context):
		if os.path.isdir(bpy.path.abspath(self.folder))==False:
			self.report({'ERROR'},
				"Invalid folder path: {x}".format(x=self.folder))
			return {'CANCELLED'}

		res = util.open_folder_crossplatform(self.folder)
		if res is False:
			msg = "Didn't open folder, navigate to it manually: {x}".format(
				x=self.folder)
			print(msg)
			self.report({'ERROR'},msg)
			return {'CANCELLED'}
		return {'FINISHED'}


class MCPREP_OT_open_help(bpy.types.Operator):
	"""Support operator for opening url in UI, but indicating through popup
	text that it is a supporting/help button"""
	bl_idname = "mcprep.open_help"
	bl_label = "Open folder"
	bl_description = "Need help? Click to open reference page"

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


class MCPREP_OT_prep_material_legacy(bpy.types.Operator):
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
		print("Using legacy operator call for MCprep materials, move to use bpy.ops.mcprep.prep_materials")
		bpy.ops.mcprep.prep_materials(
			useReflections = self.useReflections,
			combineMaterials = self.combineMaterials
		)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_improve_ui,
	MCPREP_OT_show_preferences,
	MCPREP_OT_open_folder,
	MCPREP_OT_open_help,
	MCPREP_OT_prep_material_legacy
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
