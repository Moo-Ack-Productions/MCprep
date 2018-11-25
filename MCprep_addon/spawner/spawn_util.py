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
from . import mobs
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
		bpy.ops.mcprep.reload_items()

		return {'FINISHED'}


class McprepSpawnPathReset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.spawn_path_reset"
	bl_label = "Reset spawn path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self,context):

		addon_prefs = util.get_prefs()
		context.scene.mcprep_mob_path = addon_prefs.mob_path
		mobs.updateRigList(context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	UI list related
# -----------------------------------------------------------------------------


class McprepMobUiList(bpy.types.UIList):
	"""For mob asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


class McprepMeshswapUiList(bpy.types.UIList):
	"""For meshswap asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


class McprepItemUiList(bpy.types.UIList):
	"""For meshswap asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			icon = "item-{}".format(set.index)
			if not conf.use_icons:
				col.label(set.name)
			elif conf.use_icons and icon in conf.preview_collections["items"]:
				col.label(set.name,
					icon_value=conf.preview_collections["items"][icon].icon_id)
			else:
				col.label(set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


class ListMobAssets(bpy.types.PropertyGroup):
	"""For UI drawing of mob assets and holding data"""
	label = bpy.props.StringProperty()  # depreciate
	description = bpy.props.StringProperty()

	# TODO: add in fields here to avoid having data in conf
	# local = bpy.props.StringProperty()  # is this the path?
	category = bpy.props.StringProperty()  # category it belongs to
	path = bpy.props.StringProperty()  # blend file path
	group = bpy.props.StringProperty()  # group/collection name to append
	# name = bpy.props.StringProperty() # label is Title'd


class ListMeshswapAssets(bpy.types.PropertyGroup):
	"""For UI drawing of meshswap assets and holding data"""
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()

	# TODO: use this over that in the meshswap file


class ListItemAssets(bpy.types.PropertyGroup):
	"""For UI drawing of item assets and holding data"""
	# inherited: name
	description = bpy.props.StringProperty()
	path = bpy.props.StringProperty(subtype='FILE_PATH')
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	pass


def unregister():
	pass
