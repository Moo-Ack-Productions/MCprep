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
from typing import Dict, List, Tuple
from dataclasses import dataclass

import bpy

from bpy.types import Context
from .. import conf
from ..conf import env, VectorType, Entity
from .. import util
from .. import tracking

from . import spawn_util


# -----------------------------------------------------------------------------
# Entity spawn functions
# -----------------------------------------------------------------------------

entity_cache = {}
entity_cache_path = None


def get_entity_cache(context: Context, clear: bool=False) -> Dict[str, List[str]]:
	"""Load collections from entity spawning lib if not cached, return key vars."""
	global entity_cache
	global entity_cache_path  # Used to auto-clear path if bpy prop changed.

	entity_path = context.scene.entity_path
	if not entity_cache_path:
		entity_cache_path = entity_path
		clear = True
	if entity_cache_path != entity_path:
		clear = True

	if entity_cache and clear is not True:
		return entity_cache

	# Note: Only using groups, not objects, for entities.
	entity_cache = {"groups": [], "objects": []}
	if not os.path.isfile(entity_path):
		env.log("Entity path not found")
		return entity_cache
	if not entity_path.lower().endswith('.blend'):
		env.log("Entity path must be a .blend file")
		return entity_cache

	with bpy.data.libraries.load(entity_path) as (data_from, _):
		grp_list = spawn_util.filter_collections(data_from)
		entity_cache["groups"] = grp_list
	return entity_cache


def getEntityList(context: Context) -> List[Entity]:
	"""Only used for UI drawing of enum menus, full list."""

	# may redraw too many times, perhaps have flag
	if not context.scene.mcprep_props.entity_list:
		updateEntityList(context)
	return [
		(itm.entity, itm.name.title(), f"Place {itm.name}")
		for itm in context.scene.mcprep_props.entity_list]


def update_entity_path(self, context: Context) -> None:
	"""for UI list path callback"""
	env.log("Updating entity path", vv_only=True)
	if not context.scene.entity_path.lower().endswith('.blend'):
		print("Entity file is not a .blend, and should be")
	if not os.path.isfile(bpy.path.abspath(context.scene.entity_path)):
		print("Entity blend file does not exist")
	updateEntityList(context)


def updateEntityList(context: Context) -> None:
	"""Update the entity list"""
	entity_file = bpy.path.abspath(context.scene.entity_path)
	if not os.path.isfile(entity_file):
		print("Invalid entity blend file path")
		context.scene.mcprep_props.entity_list.clear()
		return

	temp_entity_list = []  # just to skip duplicates
	entity_list = []

	cache = get_entity_cache(context)
	prefix = "Group/" if hasattr(bpy.data, "groups") else "Collection/"
	for name in cache.get("groups"):
		if not name:
			continue
		if util.nameGeneralize(name).lower() in temp_entity_list:
			continue
		description = f"Place {name} entity"
		entity_list.append((f"{prefix}{name}", name.title(), description))
		temp_entity_list.append(util.nameGeneralize(name).lower())

	# sort the list alphabetically by name
	if entity_list:
		_, sorted_entities = zip(*sorted(zip(
			[entity[1].lower() for entity in entity_list], entity_list)))
	else:
		sorted_entities = []

	# now re-populate the UI list
	context.scene.mcprep_props.entity_list.clear()
	for itm in sorted_entities:
		item = context.scene.mcprep_props.entity_list.add()
		item.entity = itm[0]
		item.name = itm[1]
		item.description = itm[2]


# -----------------------------------------------------------------------------
# Entity spawn operators
# -----------------------------------------------------------------------------


class MCPREP_OT_entity_path_reset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.entity_path_reset"
	bl_label = "Reset entity path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):

		addon_prefs = util.get_user_preferences(context)
		context.scene.entity_path = addon_prefs.entity_path
		updateEntityList(context)
		return {'FINISHED'}


class MCPREP_OT_entity_spawner(bpy.types.Operator):
	"""Instantly spawn built-in entities into a scene"""
	bl_idname = "mcprep.entity_spawner"
	bl_label = "Entity Spawner"
	bl_options = {'REGISTER', 'UNDO'}

	# properties, will appear in redo-last menu
	def swap_enum(self, context: Context) -> List[tuple]:
		return getEntityList(context)

	entity: bpy.props.EnumProperty(items=swap_enum, name="Entity")
	append_layer: bpy.props.IntProperty(
		name="Append layer",
		default=20,
		min=0,
		max=20,
		description="Set the layer for appending groups, 0 means same as active layers")
	relocation: bpy.props.EnumProperty(
		items=[
			('Cursor', 'Cursor', 'Move the rig to the cursor'),
			('Clear', 'Origin', 'Move the rig to the origin'),
			('Offset', 'Offset root', (
				'Offset the root bone to cursor while leaving the rest pose '
				'at the origin'))],
		name="Relocation")
	clearPose: bpy.props.BoolProperty(
		name="Clear Pose",
		description="Clear the pose to rest position",
		default=True)
	prep_materials: bpy.props.BoolProperty(
		name="Prep materials (will reset nodes)",
		description=(
			"Prep materials of the added rig, will replace cycles node groups "
			"with default"),
		default=True)

	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	@classmethod
	def poll(self, context):
		return context.mode == 'OBJECT'

	track_function = "entitySpawner"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		entity_path = bpy.path.abspath(context.scene.entity_path)
		method, name = self.entity.split("/", 1)

		try:
			# must be in object mode, this make similar behavior to other objs
			bpy.ops.object.mode_set(mode='OBJECT')
		except:
			pass  # Can fail to this e.g. if no objects are selected.

		# if there is a script with this entity rig, attempt to run it
		spawn_util.attemptScriptLoad(entity_path)

		if self.prep_materials and context.selected_objects:
			try:
				bpy.ops.mcprep.prep_materials(
					improveUiSettings=False, skipUsage=True)
			except:
				self.report({"WARNING"}, "Failed to prep materials on entity load")

		spawn_util.load_append(self, context, entity_path, name)
		self.track_param = self.entity
		return {'FINISHED'}


class MCPREP_OT_reload_entites(bpy.types.Operator):
	"""Force reload the Entity objects and cache."""
	bl_idname = "mcprep.reload_entities"
	bl_label = "Reload Entities"

	@tracking.report_error
	def execute(self, context):
		if not context.scene.entity_path.lower().endswith('.blend'):
			self.report({'WARNING'}, "Entity file must be a .blend, try resetting")
		elif not os.path.isfile(bpy.path.abspath(context.scene.entity_path)):
			self.report({'WARNING'}, "Entity blend file does not exist")

		# still reload even with above issues, cache/UI should be cleared
		get_entity_cache(context, clear=True)
		updateEntityList(context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#       Register functions
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_entity_path_reset,
	MCPREP_OT_entity_spawner,
	MCPREP_OT_reload_entites,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	global entity_cache
	global entity_cache_path
	entity_cache = {}
	entity_cache_path = None


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	global entity_cache
	global entity_cache_path
	entity_cache = {}
	entity_cache_path = None
