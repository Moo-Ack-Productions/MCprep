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

class MCPREP_improveUI(bpy.types.Operator):
	"""Improve the UI with specific view settings"""
	bl_idname = "mcprep.improve_ui"
	bl_label = "Improve UI"
	bl_description = "Improve UI for minecraft textures: disable mipmaps,"+\
						"set texture solid in viewport, and set rendermode"+\
						"to at least solid view"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		context.space_data.show_textured_solid = True
		context.user_preferences.system.use_mipmaps = False

		texviewable = ['SOLID','TEXTURED','MATEIRAL','RENDERED']
		if context.space_data.viewport_shade not in texviewable:
			context.space_data.viewport_shade = 'SOLID'

		return {'FINISHED'}


class MCPREP_showPrefs(bpy.types.Operator):
	"""Show MCprep preferences"""
	bl_idname = "mcprep.open_preferences"
	bl_label = "Show MCprep preferences"
	bl_description = "Open user preferences and display the MCprep settings. "+\
					"Note, you may need to press the triangle icon to expand"

	tab = bpy.props.EnumProperty(
		items = [('settings', 'Open settings', 'Open MCprep preferences settings'),
				('tutorials', 'Open tutorials', 'View tutorials'),
				('tracker_updater', 'Open tracker/updater settings',
					'Open user tracking & addon updating settings')],
		name = "Exporter")

	@tracking.report_error
	def execute(self,context):
		bpy.ops.screen.userpref_show('INVOKE_AREA')
		context.user_preferences.active_section = "ADDONS"
		bpy.data.window_managers["WinMan"].addon_search = "MCprep"
		try:
			#  if info["show_expanded"] != True:
			#
			#, where info comes from for mod, info in addons:
			# and addons is:
			# import addon_utils
			# addons = [(mod, addon_utils.module_bl_info(mod)) for mod in addon_utils.modules(refresh=False)]
			#
			# ie, get MCprep from mod in addon_utils.modules(refresh=False)
			# and then just 	grab
			# [addon_utils.module_bl_info(mod)]

			# less ideal way but works
			# for mod in
			# addon = addon_utils.module_bl_info(mode)
			addon = addon_utils.module_bl_info(__package__)
			if addon["show_expanded"] != True:
				bpy.ops.wm.addon_expand(module=__package__)
		except:
			if conf.v: print("Couldn't toggle MCprep preferences being expended")

		preferences_tab = self.tab
		# # just toggles not sets it, not helpful. need to SET it to expanded
		return {'FINISHED'}


class MCPREP_openFolder(bpy.types.Operator):
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


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register():
	pass

def unregister():
	pass
