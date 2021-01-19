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


class MCPREP_OT_reload_spawners(bpy.types.Operator):
	"""Relaod meshswapping and spawning lists"""
	bl_idname = "mcprep.reload_spawners"
	bl_label = "Reload meshswap and mob spawners"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		bpy.ops.mcprep.reload_meshswap()
		bpy.ops.mcprep.reload_mobs()
		bpy.ops.mcprep.reload_items()

		# to prevent re-drawing "load spawners!" if any one of the above
		# loaded nothing for any reason.
		conf.loaded_all_spawners = True
		return {'FINISHED'}


class MCPREP_OT_spawn_path_reset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.spawn_path_reset"
	bl_label = "Reset spawn path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self,context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_mob_path = addon_prefs.mob_path
		mobs.update_rig_list(context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	UI list related
# -----------------------------------------------------------------------------


class MCPREP_UL_mob(bpy.types.UIList):
	"""For mob asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "mob-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not conf.use_icons:
				layout.label(text=set.name)
			elif conf.use_icons and icon in conf.preview_collections["mobs"]:
				layout.label(text=set.name,
					icon_value=conf.preview_collections["mobs"][icon].icon_id)
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["mobs"]:
				layout.label(text="",
					icon_value=conf.preview_collections["mobs"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class MCPREP_UL_meshswap(bpy.types.UIList):
	"""For meshswap asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			layout.label(text=set.name)
			# col.prop(set, "name", text="", emboss=False)
		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='QUESTION')


class MCPREP_UL_item(bpy.types.UIList):
	"""For item asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "item-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not conf.use_icons:
				layout.label(text=set.name)
			elif conf.use_icons and icon in conf.preview_collections["items"]:
				layout.label(text=set.name,
					icon_value=conf.preview_collections["items"][icon].icon_id)
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["items"]:
				layout.label(text="",
					icon_value=conf.preview_collections["items"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class MCPREP_UL_material(bpy.types.UIList):
	"""For material library UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "material-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not conf.use_icons:
				layout.label(text=set.name)
			elif conf.use_icons and icon in conf.preview_collections["materials"]:
				layout.label(text=set.name,
					icon_value=conf.preview_collections["materials"][icon].icon_id)
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["materials"]:
				layout.label(text="",
					icon_value=conf.preview_collections["materials"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class ListMobAssetsAll(bpy.types.PropertyGroup):
	"""For listing hidden group of all mobs, regardless of category"""
	description = bpy.props.StringProperty()
	category = bpy.props.StringProperty()
	mcmob_type = bpy.props.StringProperty()
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


class ListMobAssets(bpy.types.PropertyGroup):
	"""For UI drawing of mob assets and holding data"""
	description = bpy.props.StringProperty()
	category = bpy.props.StringProperty()  # category it belongs to
	mcmob_type = bpy.props.StringProperty()
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


class ListMeshswapAssets(bpy.types.PropertyGroup):
	"""For UI drawing of meshswap assets and holding data"""
	block = bpy.props.StringProperty()  # virtual enum, Group/name
	description = bpy.props.StringProperty()


class ListItemAssets(bpy.types.PropertyGroup):
	"""For UI drawing of item assets and holding data"""
	# inherited: name
	description = bpy.props.StringProperty()
	path = bpy.props.StringProperty(subtype='FILE_PATH')
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


classes = (
	ListMobAssetsAll,
	ListMobAssets,
	ListMeshswapAssets,
	ListItemAssets,
	MCPREP_UL_material,
	MCPREP_UL_mob,
	MCPREP_UL_meshswap,
	MCPREP_UL_item,
	MCPREP_OT_reload_spawners,
	MCPREP_OT_spawn_path_reset,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
