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


# library imports
import bpy
from bpy_extras.io_utils import ImportHelper
import os
import math
import shutil
from mathutils import Vector

# addon imports
from .. import conf
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------


class McprepReloadSpawners(bpy.types.Operator):
	"""Relaod meshswapping and spawning lists"""
	bl_idname = "mcprep.reload_spawners"
	bl_label = "Reload meshswap and mob spawners"

	@tracking.report_error
	def execute(self, context):

		bpy.ops.mcprep.reload_meshswap()
		bpy.ops.mcprep.reload_mobs()

		return {'FINISHED'}


class McprepSpawnPathReset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.spawnpathreset"
	bl_label = "Reset spawn path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self,context):

		addon_prefs = util.get_prefs()
		context.scene.mcprep_mob_path = addon_prefs.mob_path
		updateRigList(context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	UI list related
# -----------------------------------------------------------------------------


class McprepMobUiList(bpy.types.UIList):
	"""For mob asset listing UIList drawing."""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):

		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)
			#layout.label(text='', icon='TIME')
			# if conf.active_mob_subind == index:
			# 	ic = "RADIOBUT_ON"
			# 	layout.label("Skin swap")
			# else:
			# 	ic = "RADIOBUT_OFF"
			# col = layout.column()
			# row = col.row()
			# row.scale_x = 0.2
			# row.operator('mcprep.mob_spawner_direct',emboss=False, text='',
			# 			icon='FORWARD').mcmob_index = index

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


class McprepMeshswapUiList(bpy.types.UIList):
	"""For meshswap asset listing UIList drawing."""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):

		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


# for asset listing
class ListColl(bpy.types.PropertyGroup):
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	bpy.types.Scene.mcprep_mob_list = \
			bpy.props.CollectionProperty(type=ListColl)
	bpy.types.Scene.mcprep_mob_list_index = bpy.props.IntProperty(default=0)


def unregister():
	del bpy.types.Scene.mcprep_mob_list
	del bpy.types.Scene.mcprep_mob_list_index
