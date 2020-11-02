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


#import math
import os
#import random
#import time

import bpy
#import mathutils

# addon imports
from .. import conf
from ..materials import generate
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# Mesh swap functions
# -----------------------------------------------------------------------------

entity_cache = {}
entity_cache_path = None

def get_entity_cache(context, clear=False):
	"""Load groups/objects from entity spawning lib if not cached, return key vars."""
	global entity_cache
	global entity_cache_path # used to auto-clear path if bpy prop changed

	entity_path = context.scene.entity_path
	if not entity_cache_path:
		entity_cache_path = entity_path
		clear = True
	if entity_cache_path != entity_path:
		clear = True

	if entity_cache and clear is not True:
		return entity_cache

	entity_cache = {"groups":[], "objects":[]}
	if not os.path.isfile(entity_path):
		conf.log("Entity path not found")
		return entity_cache
	if not entity_path.lower().endswith('.blend'):
		conf.log("Entity path must be a .blend file")
		return entity_cache

	with bpy.data.libraries.load(entity_path) as (data_from, _):
		if hasattr(data_from, "groups"): # blender 2.7
			get_attr = "groups"
		else: # 2.8
			get_attr = "collections"
		grp_list = list(getattr(data_from, get_attr))
		entity_cache["groups"] = grp_list
		for obj in list(data_from.objects):
			if obj in entity_cache["groups"]:
				# conf.log("Skipping meshwap obj already in cache: "+str(obj))
				continue
			# ignore list? e.g. Point.001,
			entity_cache["objects"].append(obj)
	return entity_cache


def getEntityList(context):
	"""Only used for UI drawing of enum menus, full list."""

	# may redraw too many times, perhaps have flag
	if not context.scene.mcprep_props.entity_list:
		updateEntityList(context)
	return [(itm.block, itm.name.title(), "Place {}".format(itm.name))
			for itm in context.scene.mcprep_props.entity_list]


def update_entity_path(self, context):
	"""for UI list path callback"""
	conf.log("Updating entity path", vv_only=True)
	if not context.scene.entity_path.lower().endswith('.blend'):
		print("Entity file is not a .blend, and should be")
	if not os.path.isfile(bpy.path.abspath(context.scene.entity_path)):
		print("Entity blend file does not exist")
	updateEntityList(context)


def updateEntityList(context):
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
		if util.nameGeneralize(name).lower() == "Rigidbodyworld".lower():
			continue
		description = "Place {x} block".format(x=name)
		entity_list.append((prefix+name, name.title(), description))
		temp_entity_list.append(util.nameGeneralize(name).lower())

	# sort the list alphabetically by name
	if entity_list:
		_, sorted_blocks = zip(*sorted(zip([block[1].lower()
			for block in entity_list], entity_list)))
	else:
		sorted_blocks = []

	# now re-populate the UI list
	context.scene.mcprep_props.entity_list.clear()
	for itm in sorted_blocks:
		item = context.scene.mcprep_props.entity_list.add()
		item.block = itm[0]
		item.name = itm[1]
		item.description = itm[2]


class face_struct():
	"""Structure class for preprocessed faces of a mesh"""
	def __init__(self, normal_coord, global_coord, local_coord):
		self.n = normal_coord
		self.g = global_coord
		self.l = local_coord


# -----------------------------------------------------------------------------
# Mesh swap functions
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
	"""Instantly spawn built-in entity blocks into a scene"""
	bl_idname = "mcprep.entity_spawner"
	bl_label = "Entity Spawner"
	bl_options = {'REGISTER', 'UNDO'}

	# properties, will appear in redo-last menu
	def swap_enum(self, context):
		return getEntityList(context)

	block = bpy.props.EnumProperty(items=swap_enum, name="Entity")
	location = bpy.props.FloatVectorProperty(
		default=(0,0,0),
		name = "Location")
	append_layer = bpy.props.IntProperty(
		name="Append layer",
		default=20,
		min=0,
		max=20,
		description="Set the layer for appending groups, 0 means same as active layers")
	prep_materials = bpy.props.BoolProperty(
		name="Prep materials",
		default=True,
		description="Run prep materials on objects after appending")
	snapping = bpy.props.EnumProperty(
		name="Snapping",
		items=[("none","No snap","Keep exact location"),
				("center","Snap center","Snap to block center"),
				("offset","Snap offset","Snap to block center with 0.5 offset")
			],
		description="Automatically snap to whole block locations")
	make_real = bpy.props.BoolProperty(
		name="Make real",
		default=True,
		description="Automatically make groups real after placement")

	# toLink = bpy.props.BoolProperty(
	#       name = "Library Link mob",
	#       description = "Library link instead of append the group",
	#       default = False
	#       )
	# option to force load from library instead of reuse local group?

	@classmethod
	def poll(self, context):
		return context.mode == 'OBJECT'

	track_function = "entitySpawner"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		pre_groups = list(util.collections())

		entityPath = bpy.path.abspath(context.scene.entity_path)
		method, block = self.block.split("/",1)
		toLink = False
		use_cache = False
		group = None

		if method in ('Collection', 'Group') and block in util.collections():
			group = util.collections()[block]
			# if blender 2.8, see if collection part of the MCprepLib coll.
			use_cache = True
		else:
			util.bAppendLink(os.path.join(entityPath,method), block, toLink)

		if method=="Object":
			for ob in bpy.context.selected_objects:
				if ob.type != 'MESH':
					util.select_set(ob, False)
			try:
				importedObj = bpy.context.selected_objects[0]
			except:
				print("selected object not found")
				self.report({'WARNING'}, "Imported object not found")
				return {'CANCELLED'}
			importedObj["MCprep_noSwap"] = 1
			importedObj.location = self.location
			if self.prep_materials is True:
				try:
					bpy.ops.mcprep.prep_materials(
						autoFindMissingTextures=False,
						improveUiSettings=False,
						skipUsage=True) # if cycles
				except:
					print("Could not prep materials")
					self.report({"WARNING"}, "Could not prep materials")
		else:
			if not use_cache:
				group = self.prep_collection(context, block, pre_groups)

			if not group:
				conf.log("No group identified, could not retrieve imported group")
				self.report({"ERROR"}, "Could not retrieve imported group")
				return {'CANCELLED'}

			# now finally add the group instance
			for obj in util.get_objects_conext(context):
				util.select_set(obj, False)
			ob = util.addGroupInstance(group.name, self.location)
			if self.snapping=="center":
				offset=0 # could be 0.5
				ob.location = [round(x+offset)-offset for x in self.location]
			elif self.snapping=="offset":
				offset=0.5 # could be 0.5
				ob.location = [round(x+offset)-offset for x in self.location]
			ob["MCprep_noSwap"] = 1

			if self.make_real:
				if util.bv28():
					# make real doesn't select resulting output now (true for
					# earlier versions of 2.8, not true in 2.82 at least where
					# selects everything BUT the source of original instance
					pre_objs = list(bpy.data.objects)
					bpy.ops.object.duplicates_make_real()
					post_objs = list(bpy.data.objects)
					new_objs = list(set(post_objs)-set(pre_objs))
					for obj in new_objs:
						util.select_set(obj, True)
				else:
					bpy.ops.object.duplicates_make_real()

				if group is not None:
					self.fix_armature_target(
						context, context.selected_objects, group)

				# remove the empty added by making duplicates real.
				if ob in bpy.data.objects[:] and ob.type == "EMPTY":
					util.obj_unlink_remove(ob, True, context)
				else:
					for ob in context.selected_objects:
						if ob.type != "EMPTY":
							continue
						elif ob.parent or ob.children:
							continue
						util.obj_unlink_remove(ob, True, context)
				# TODO: Consider actually keeping the empty, and parenting the
				# spawned items to this empty (not the defautl behavior)
			else:
				# change the draw size
				if hasattr(ob, "empty_draw_size"):
					ob.empty_draw_size = 0.25
				else:
					ob.empty_display_size = 0.25
				# mark as active object
				util.set_active_object(context, ob)

			# Move source of group instance into excluded view layer
			if util.bv28() and group:
				util.move_assets_to_excluded_layer(context, [group])

		self.track_param = self.block
		return {'FINISHED'}

	def fix_armature_target(self, context, new_objs, src_coll):
		"""To address 2.8 bug where group made real might not update armature source"""

		src_armas = [arma for arma in src_coll.objects
			if arma.type == 'ARMATURE']
		new_armas = [arma for arma in new_objs
			if arma.type == 'ARMATURE']
		src_armas_basnames = [util.nameGeneralize(obj.name) for obj in src_armas]
		new_armas_basnames = [util.nameGeneralize(obj.name) for obj in new_armas]
		if not new_armas:
			return # nothing we can do to fix if new arma not existing
		for obj in new_objs:
			for mod in obj.modifiers:
				# two scenarios:
				# if 2.7: armature modifier already changed, copy over anim data
				# if 2.8: swap modifier armature and also copy over anim data
				if mod.type != 'ARMATURE':
					continue
				# if not (mod.object in new_objs or mod.object in src_armas):
				#       continue # all good (from mod arma target perspective)
				if mod.object not in src_armas and mod.object not in new_armas:
					continue # unknown source, no way to know how to fix this
				target_base = util.nameGeneralize(mod.object.name)
				if target_base not in new_armas_basnames:
					continue # shouldn't occur, but skip if it does

				new_target = new_armas[new_armas_basnames.index(target_base)]
				old_target = src_armas[src_armas_basnames.index(target_base)]

				# for blender 2.8, bug is that target is still old_target
				# but for blender 2.7, the mod target will already have changed
				if old_target.animation_data:
					new_target.animation_data_create()
					new_target.animation_data.action = old_target.animation_data.action
					conf.log("Updated animation of armature for instance of "+src_coll.name)

				if mod.object in new_objs:
					continue # was already the new object target for modifier
				mod.object = new_target
				conf.log("Updated target of armature for instance of "+src_coll.name)

	def prep_collection(self, context, block, pre_groups):
		"""Prep the imported collection, ran only if newly imported (not cached)"""

		# Group method first, move append to according layer
		for ob in util.get_objects_conext(context):
			util.select_set(ob, False)

		layers = [False]*20
		if not hasattr(context.scene, "layers"):
			# TODO: here add all subcollections to an MCprepLib collection.
			pass
		elif self.append_layer==0:
			layers = context.scene.layers
		else:
			layers[self.append_layer-1] = True
		objlist = []
		group = None
		for coll in util.collections():
			if coll in pre_groups:
				continue
			for ob in coll.objects:
				if ob.name in context.scene.objects:
					#context.scene.objects.unlink(ob)
					objlist.append(ob)
			if util.nameGeneralize(coll.name) == util.nameGeneralize(block):
				group = coll

		if group is None:
			return None

		if self.prep_materials is True:
			for ob in objlist:
				util.select_set(ob, True)
			try:
				bpy.ops.mcprep.prep_materials(
					autoFindMissingTextures=False,
					improveUiSettings=False,
					skipUsage=True) # if cycles
			except:
				print("Could not prep materials")
			for ob in util.get_objects_conext(context):
				util.select_set(ob, False)

		if hasattr(context.scene, "layers"): # 2.7 only
			for obj in objlist:
				obj.layers = layers
		return group


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


class MCPREP_UL_entity_list(bpy.types.UIList):
	"""For asset listing UIList drawing"""
	# previously McprepEntity_UIList
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):

		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='QUESTION')








# -----------------------------------------------------------------------------
#       Register functions
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_entity_path_reset,
	MCPREP_OT_entity_spawner,
	MCPREP_OT_reload_entites,
	MCPREP_UL_entity_list,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
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
