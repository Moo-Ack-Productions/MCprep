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


import math
import os
import random
import time

import bpy
from bpy.types import (
  Context, Object, Collection
)
import mathutils

from typing import Dict, List, Union, Tuple
from . import spawn_util
from .. import conf
from ..conf import env, VectorType
from ..materials import generate
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# Mesh swap functions
# -----------------------------------------------------------------------------

meshswap_cache = {}
meshswap_cache_path = None


def get_meshswap_cache(context: Context, clear: bool=False) -> Dict[str, List[str]]:
	"""Load groups/objects from meshswap lib if not cached, return key vars."""
	global meshswap_cache
	global meshswap_cache_path  # used to auto-clear path if bpy prop changed

	meshswap_path = context.scene.meshswap_path
	if not meshswap_cache_path:
		meshswap_cache_path = meshswap_path
		clear = True
	if meshswap_cache_path != meshswap_path:
		clear = True

	if meshswap_cache and clear is not True:
		return meshswap_cache

	meshswap_cache = {"groups": [], "objects": []}
	if not os.path.isfile(meshswap_path):
		env.log("Meshswap path not found")
		return meshswap_cache
	if not meshswap_path.lower().endswith('.blend'):
		env.log("Meshswap path must be a .blend file")
		return meshswap_cache

	with bpy.data.libraries.load(meshswap_path) as (data_from, _):
		grp_list = spawn_util.filter_collections(data_from)

		meshswap_cache["groups"] = grp_list
		for obj in list(data_from.objects):
			if obj in meshswap_cache["groups"]:
				# env.log("Skipping meshwap obj already in cache: "+str(obj))
				continue
			# ignore list? e.g. Point.001,
			meshswap_cache["objects"].append(obj)
	return meshswap_cache


def getMeshswapList(context: Context) -> List[Tuple[str, str, str]]:
	"""Only used for UI drawing of enum menus, full list."""

	# may redraw too many times, perhaps have flag
	if not context.scene.mcprep_props.meshswap_list:
		updateMeshswapList(context)
	return [
		(itm.block, itm.name.title(), f"Place {itm.name}")
		for itm in context.scene.mcprep_props.meshswap_list]


def move_assets_to_excluded_layer(context: Context, collections: List[Collection]) -> None:
	"""Utility to move source collections to excluded layer to not be rendered"""
	initial_view_coll = context.view_layer.active_layer_collection

	# Then, setup the exclude view layer
	meshswap_exclude_vl = util.get_or_create_viewlayer(
		context, "Meshswap Exclude")
	meshswap_exclude_vl.collection.hide_viewport = True
	meshswap_exclude_vl.collection.hide_render = True

	for grp in collections:
		if grp.name not in initial_view_coll.collection.children:
			continue  # not linked, likely a sub-group not added to scn
		initial_view_coll.collection.children.unlink(grp)
		if grp.name not in meshswap_exclude_vl.collection.children:
			meshswap_exclude_vl.collection.children.link(grp)


def update_meshswap_path(self, context: Context) -> None:
	"""for UI list path callback"""
	env.log("Updating meshswap path", vv_only=True)
	if not context.scene.meshswap_path.lower().endswith('.blend'):
		print("Meshswap file is not a .blend, and should be")
	if not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
		print("Meshswap blend file does not exist")
	updateMeshswapList(context)


def updateMeshswapList(context: Context) -> None:
	"""Update the meshswap list"""
	meshswap_file = bpy.path.abspath(context.scene.meshswap_path)
	if not os.path.isfile(meshswap_file):
		print("Invalid meshswap blend file path")
		context.scene.mcprep_props.meshswap_list.clear()
		return

	temp_meshswap_list = []  # just to skip duplicates
	meshswap_list = []

	cache = get_meshswap_cache(context)
	method = "collection"

	for name in cache.get("groups"):
		if not name:
			continue
		if util.nameGeneralize(name).lower() in temp_meshswap_list:
			continue
		description = f"Place {name} block"
		meshswap_list.append((method, name, name.title(), description))
		temp_meshswap_list.append(util.nameGeneralize(name).lower())

	# sort the list alphabetically by name
	if meshswap_list:
		_, sorted_blocks = zip(*sorted(zip(
			[block[1].lower() for block in meshswap_list],
			meshswap_list)))
	else:
		sorted_blocks = []

	# now re-populate the UI list
	context.scene.mcprep_props.meshswap_list.clear()
	for itm in sorted_blocks:
		item = context.scene.mcprep_props.meshswap_list.add()
		item.method = itm[0]
		item.block = itm[1]
		item.name = itm[2]
		item.description = itm[3]


class face_struct():
	"""Structure class for preprocessed faces of a mesh"""
	def __init__(self, normal_coord: VectorType, global_coord: VectorType , local_coord: VectorType) -> None:
		self.n: VectorType = normal_coord
		self.g: VectorType = global_coord
		self.l: VectorType = local_coord


# -----------------------------------------------------------------------------
# Mesh swap functions
# -----------------------------------------------------------------------------


class MCPREP_OT_meshswap_path_reset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.meshswap_path_reset"
	bl_label = "Reset meshswap path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):

		addon_prefs = util.get_user_preferences(context)
		context.scene.meshswap_path = addon_prefs.meshswap_path
		updateMeshswapList(context)
		return {'FINISHED'}


class MCPREP_OT_meshswap_spawner(bpy.types.Operator):
	"""Instantly spawn built-in meshswap blocks into a scene"""
	bl_idname = "mcprep.meshswap_spawner"
	bl_label = "Meshswap Spawner"
	bl_options = {'REGISTER', 'UNDO'}

	# properties, will appear in redo-last menu
	def swap_enum(self, context):
		return getMeshswapList(context)

	block: bpy.props.EnumProperty(items=swap_enum, name="Meshswap block")
	method: bpy.props.EnumProperty(
		name="Import method",
		items=[
			# Making collection first to be effective default.
			("collection", "Collection/group asset", "Collection/group asset"),
			("object", "Object asset", "Object asset"),
		],
		options={'HIDDEN'})
	location: bpy.props.FloatVectorProperty(
		default=(0, 0, 0),
		name="Location")
	append_layer: bpy.props.IntProperty(
		name="Append layer",
		default=20,
		min=0,
		max=20,
		description="Set the layer for appending groups, 0 means same as active layers")
	prep_materials: bpy.props.BoolProperty(
		name="Prep materials",
		default=True,
		description="Run prep materials on objects after appending")
	snapping: bpy.props.EnumProperty(
		name="Snapping",
		items=[
			("none", "No snap", "Keep exact location"),
			("center", "Snap center", "Snap to block center"),
			("offset", "Snap offset", "Snap to block center with 0.5 offset")],
		description="Automatically snap to whole block locations")
	make_real: bpy.props.BoolProperty(
		name="Make real",
		default=False,  # TODO: make True once able to retain animations like fire
		description="Automatically make groups real after placement")

	# toLink: bpy.props.BoolProperty(
	# 	name = "Library Link mob",
	# 	description = "Library link instead of append the group",
	# 	default = False
	# 	)
	# option to force load from library instead of reuse local group?

	@classmethod
	def poll(self, context):
		return context.mode == 'OBJECT'

	track_function = "meshswapSpawner"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		pre_groups = list(util.collections())

		meshSwapPath = bpy.path.abspath(context.scene.meshswap_path)
		block = self.block
		method = self.method
		if method == "collection":
			is_object = False
			method = "Group" if hasattr(bpy.data, "groups") else "Collection"
		elif method == "object":
			is_object = True
			method = "Object"
		link = False
		use_cache = False
		group = None

		if not is_object and block in util.collections():
			group = util.collections()[block]
			# if blender 2.8, see if collection part of the MCprepLib coll.
			use_cache = True
		else:
			util.bAppendLink(os.path.join(meshSwapPath, method), block, link)

		if is_object:
			# Object-level disabled! Must have better
			# asset management for this to work
			for ob in bpy.context.selected_objects:
				if ob.type != 'MESH':
					util.select_set(ob, False)
			try:
				importedObj = bpy.context.selected_objects[0]
			except:
				# in case nothing selected.. which happens even during selection?
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
						skipUsage=True)  # if cycles
				except:
					print("Could not prep materials")
					self.report({"WARNING"}, "Could not prep materials")
		else:
			if not use_cache:
				group = spawn_util.prep_collection(
					self, context, block, pre_groups)

			if not group:
				env.log("No group identified, could not retrieve imported group")
				self.report({"ERROR"}, "Could not retrieve imported group")
				return {'CANCELLED'}

			# now finally add the group instance
			for obj in util.get_objects_conext(context):
				util.select_set(obj, False)
			ob = util.addGroupInstance(group.name, self.location)
			if util.bv28():
				util.move_to_collection(ob, context.collection)
			if self.snapping == "center":
				offset = 0  # could be 0.5
				ob.location = [round(x + offset) - offset for x in self.location]
			elif self.snapping == "offset":
				offset = 0.5  # could be 0.5
				ob.location = [round(x + offset) - offset for x in self.location]
			ob["MCprep_noSwap"] = 1

			if self.make_real:
				if util.bv28():
					# make real doesn't select resulting output now (true for
					# earlier versions of 2.8, not true in 2.82 at least where
					# selects everything BUT the source of original instance

					pre_objs = list(bpy.data.objects)
					bpy.ops.object.duplicates_make_real()
					post_objs = list(bpy.data.objects)
					new_objs = list(set(post_objs) - set(pre_objs))
					for obj in new_objs:
						util.select_set(obj, True)

						# Re-apply animation if any
						# TODO: Causes an issue for any animation that depends
						# on direct xyz placement (noting that parents are
						# cleared on Make Real). Could try adding a parent to
						# any given object's current location and give the
						# equivalent xyz offset at some point in time.
						"""
						orig_objs = [obo for obo in group.objects
							if util.nameGeneralize(obj.name) == util.nameGeneralize(obo.name)]
						if not orig_objs:
							continue
						obo = orig_objs[0]
						if not obo or not obo.animation_data:
							continue
						if not obj.animation_data:
							obj.animation_data_create()
						obj.animation_data.action = obo.animation_data.action
						"""
				else:
					bpy.ops.object.duplicates_make_real()

				if group is not None:
					spawn_util.fix_armature_target(
						self, context, context.selected_objects, group)

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

		self.track_param = f"{self.method}/{self.block}"
		return {'FINISHED'}

	def prep_collection(self, context: Context, block: str, pre_groups: List[Collection]) -> Collection:
		"""Prep the imported collection, ran only if newly imported (not cached)"""

		# Group method first, move append to according layer
		for ob in util.get_objects_conext(context):
			util.select_set(ob, False)

		layers = [False] * 20
		if not hasattr(context.scene, "layers"):
			# TODO: here add all subcollections to an MCprepLib collection.
			pass
		elif self.append_layer == 0:
			layers = context.scene.layers
		else:
			layers[self.append_layer - 1] = True
		objlist = []
		group = None
		for coll in util.collections():
			if coll in pre_groups:
				continue
			if coll.name.lower().startswith("collection"):
				continue  # Will drop e.g. "Collection 1" from blender 2.7x.
			for ob in coll.objects:
				if ob.name in context.scene.objects:
					# context.scene.objects.unlink(ob)
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
					skipUsage=True)  # If cycles.
			except:
				print("Could not prep materials")
			for ob in util.get_objects_conext(context):
				util.select_set(ob, False)

		if hasattr(context.scene, "layers"):  # 2.7 only
			for obj in objlist:
				obj.layers = layers
		return group


class MCPREP_OT_reload_meshswap(bpy.types.Operator):
	"""Force reload the MeshSwap objects and cache."""
	bl_idname = "mcprep.reload_meshswap"
	bl_label = "Reload MeshSwap"

	@tracking.report_error
	def execute(self, context):
		if not context.scene.meshswap_path.lower().endswith('.blend'):
			self.report({'WARNING'}, "Meshswap file must be a .blend, try resetting")
		elif not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
			self.report({'WARNING'}, "Meshswap blend file does not exist")

		# still reload even with above issues, cache/UI should be cleared
		get_meshswap_cache(context, clear=True)
		updateMeshswapList(context)
		return {'FINISHED'}


class MCPREP_OT_meshswap(bpy.types.Operator):
	"""Swap minecraft objects from world imports for custom 3D models in the according meshSwap blend file"""
	bl_idname = "mcprep.meshswap"
	bl_label = "Mesh Swap"
	bl_options = {'REGISTER', 'UNDO'}

	# used for only occasionally refreshing the 3D scene while mesh swapping
	counterObject = 0  # used in count
	countMax = 5  # count compared to this, frequency of refresh (number of objs)
	runcount = 0  # current counter status of swapped meshes

	# properties for draw
	meshswap_join: bpy.props.BoolProperty(
		name="Join same blocks",
		default=True,
		description=(
			"Join together swapped blocks of the same type "
			"(unless swapped with a group)"))
	use_dupliverts: bpy.props.BoolProperty(
		name="Use dupliverts (faster)",
		default=True,
		description="Use dupliverts to add meshes")
	link_groups: bpy.props.BoolProperty(
		name="Link groups",
		default=False,
		description="Link groups instead of appending")
	prep_materials: bpy.props.BoolProperty(
		name="Prep materials",
		default=False,
		description=(
			"Automatically apply prep materials (with default settings) "
			"to blocks added in"))
	append_layer: bpy.props.IntProperty(
		name="Append layer",
		default=20,
		min=0,
		max=20,
		description=(
			"When groups are appended instead of linked, "
			"the objects part of the group will be placed in this "
			"layer, 0 means same as active layers"))

	@classmethod
	def poll(cls, context):
		addon_prefs = util.get_user_preferences(context)
		return addon_prefs.MCprep_exporter_type != "(choose)" and context.mode == 'OBJECT'

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

	def draw(self, context):
		layout = self.layout

		# please save the file first. Not implemented
		if False:
			layout.label(
				text="You must save your blend file before meshswapping",
				icon="ERROR")
			return

		layout.label(text="GENERAL SETTINGS")
		row = layout.row()
		# row.prop(self,"use_dupliverts") # coming soon
		row.prop(self, "meshswap_join")
		row = layout.row()
		row.prop(self, "link_groups")
		row.prop(self, "prep_materials")
		row = layout.row()
		if not util.bv28():
			row.prop(self, "append_layer")

		# multi settings, to come
		# layout.split()
		# layout.label(text="HOW TO ADD LIGHTS")
		# row = layout.row()
		# row.prop(self,"meshswap_lamps", expand=True)
		# row = layout.row()
		# row.prop(self,"filmic_values")

		if True:
			layout.split()
			col = layout.column()
			col.scale_y = 0.7
			col.label(
				text="WARNING: May take a long time to process!!", icon="ERROR")
			col.label(
				text="If you selected a large number of blocks to meshswap,",
				icon="BLANK1")
			col.label(
				text="consider using a smaller area closer to the camera",
				icon="BLANK1")

	track_function = "meshswap"
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
		tprep = time.time()
		addon_prefs = util.get_user_preferences(context)
		self.track_exporter = addon_prefs.MCprep_exporter_type

		direc = context.scene.meshswap_path
		if not direc.lower().endswith('.blend'):
			self.report({'WARNING'}, "Meshswap file must be a .blend!")
			bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
			return {'CANCELLED'}

		if not os.path.isfile(direc):
			direc = bpy.path.abspath(direc)
			if not os.path.isfile(direc):
				# better, actual "error" popup.
				self.report({'WARNING'}, "Meshswap blend file not found!")
				bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
				return {'CANCELLED'}

		# Assign vars used across operator
		self.runcount = 0  # counter; if zero by end, raise error nothing matched
		objList: List[Object] = self.prep_obj_list(context)
		selList: List[Object] = context.selected_objects  # re-grab having made new objects
		new_groups = []  # for new imported groups
		removeList = []  # for objects that should be removed
		new_objects = []  # all the newly added objects

		# setup the progress bar
		denom = len(objList)
		env.log(f"Meshswap to check over {denom} objects")
		bpy.context.window_manager.progress_begin(0, 100)

		tprep = time.time() - tprep
		t0s = []  # start of loop
		t1s = []  # between prep and face process
		t2s = []  # between face process and
		t3s = []  # end of loop

		# primary loop, for each OBJECT needing swapping
		for iter_index, swap in enumerate(objList):
			t0s.append(time.time())
			t1s.append(t0s[-1])
			t2s.append(t0s[-1])
			t3s.append(t0s[-1])
			bpy.context.window_manager.progress_update(iter_index / denom)
			swapGen: str = util.nameGeneralize(swap.name)
			# swapGen = generate.get_mc_canonical_name(swap.name)
			env.log(f"Simplified name: {swapGen}")
			# IMPORTS, gets lists properties, etc
			swapProps: dict = self.checkExternal(context, swapGen)

			# issue in swapProps, e.g. not a mesh or not in lib or some error
			if swapProps is False:
				continue

			if swapProps.get('new_groups'):
				new_groups += swapProps['new_groups']
			# special cases, for "extra" mesh pieces we don't want around afterwards
			if swapProps['removable']:
				removeList.append(swap)
				continue
			# just selecting mesh with same name and if in objList
			if not (swapProps['meshSwap'] or swapProps['groupSwap']):
				continue

			env.log(
				f"Swapping '{swap.name}', simplified name '{swapGen}")

			# loop through each face or "polygon" of mesh, throw out invalids
			t1s[-1] = time.time()
			offset = 0.5 if self.track_exporter == 'Mineways' else 0
			facebook = self.get_face_list(swap, offset)

			if not util.bv28():
				for obj in context.selected_objects:
					util.select_set(obj, False)

			# removing duplicates and checking orientation
			# structure of: "x-y-z":[[x,y,z], [xr, yr, zr]]
			instance_configs = {}
			for face in facebook:
				# updates instance_configs
				self.proccess_poly_orientations(face, swapProps, swapGen, instance_configs)

			# Primary function for adding the actual instances
			# Critical path process section!
			t2s[-1] = time.time()
			grouped, dupedObj = self.add_instances_with_transforms(
				context, swap, swapProps, instance_configs)
			base = swapProps["object"]

			# Having completed adding instances, remove the 'base copy'
			if not grouped:
				if base in dupedObj:
					dupedObj.pop(dupedObj.index(base))
				if base in selList:  # gaurd for stability, but shouldn't happen
					selList.pop(selList.index(base))
				util.obj_unlink_remove(base, True, context)

			if grouped:
				new_objects += dupedObj  # list
			elif dupedObj and self.meshswap_join:
				# join meshes together, carefully removing old selected objects
				# from selection lists
				util.set_active_object(context, dupedObj[0])
				for d in dupedObj:
					if d.type != 'MESH':
						continue
					util.select_set(d, True)
				if context.mode != "OBJECT":
					bpy.ops.object.mode_set(mode='OBJECT')

				# to avoid reselection later objects that were joined
				for obtemp in context.selected_objects:
					if obtemp in selList:
						selList.pop(selList.index(obtemp))
					if obtemp in dupedObj:
						dupedObj.pop(dupedObj.index(obtemp))
				bpy.ops.object.join()
				if context.selected_objects:
					new_objects.append(context.selected_objects[0])
				else:
					env.log("No selected objects after join")
			else:
				# no joining, so just directly append to new_objects
				new_objects += dupedObj  # a list

			removeList.append(swap)

			# Setup for later re-selection and applying no-re-meshswap property
			for obj in new_objects:
				if obj in removeList:
					continue
				# Setup below is for cross compatibility, in 2.8 & 2.7
				# where accessing a field on deleted object will raise error
				# (but, we should have already excluded deleted objects anyways)
				try:
					if not hasattr(obj, "users"):
						continue
					if not obj.name:  # accessing name itself could cause crash/error
						continue
				except ReferenceError:
					continue
				selList.append(obj)
				obj['MCprep_noSwap'] = 1  # property to avoid duplicate future swap
			t3s[-1] = time.time()

		t4 = time.time()
		# final re-selection and deletion
		if self.runcount > 0:
			for rm in removeList:
				if rm in selList:
					# prevent later operations on deleted object
					selList.pop(selList.index(rm))
				if rm in new_objects:
					# prevent later operations on deleted object
					new_objects.pop(new_objects.index(rm))
				try:
					util.obj_unlink_remove(rm, True, context)
				except:
					print(f"Failed to clear user/remove object: {rm.name}")

		for obj in selList:
			# Risk if object was joined against another object that its data
			# no longer exists, which can result in a failure e.g. for 2.72
			# However, pre-work should have prevented interacting with already
			# deleted object here, so the try/except is more for later blender
			# versions to fail gracefully just in case
			try:
				if not hasattr(obj, "users"):  # can be crashing point pre 2.79(?)
					continue
			except ReferenceError:
				continue
			util.select_set(obj, True)

		# Create nicer nested organization of meshswapped assets, and excluding
		# this meshswap group to avoid showing in render. Also move newly
		# spawned instances into a collection of its own (2.8 only)
		if util.bv28():
			swaped_vl = util.get_or_create_viewlayer(context, "Meshswap Render")
			for obj in new_objects:
				util.move_to_collection(obj, swaped_vl.collection)

			util.move_assets_to_excluded_layer(context, new_groups)

		# end progress bar, end of primary section
		bpy.context.window_manager.progress_end()
		t5 = time.time()

		# run timing calculations
		if env.very_verbose:
			loop_prep = sum(t1s) - sum(t0s)
			face_process = sum(t2s) - sum(t1s)
			instancing = sum(t3s) - sum(t2s)
			cleanup = t5 - t4
			total = tprep + loop_prep + face_process + instancing + cleanup
			env.log(f"Total time: {round(total, 1)}s, init: {round(tprep, 1)}, prep: {round(loop_prep, 1)}, poly process: {round(face_process, 1)}, instance:{round(instancing, 1)}, cleanup: {round(cleanup, 1)}")

		if self.runcount == 0:
			self.report({'ERROR'}, (
				"Nothing swapped, likely no materials of "
				"selected objects match the meshswap file objects/groups"))
			return {'CANCELLED'}
		elif self.runcount == 1:
			self.report({'INFO'}, "Swapped 1 object")
			return {'FINISHED'}
		self.report({'INFO'}, f"Swapped {self.runcount} objects")
		return {'FINISHED'}

	def prep_obj_list(self, context: Context) -> List[Object]:
		"""Initial operator prep to get list of objects to check over"""
		try:
			bpy.ops.object.convert(target='MESH')
		except:
			pass
		bpy.ops.mesh.separate(type='MATERIAL')

		# now do type checking and fix any name discrepancies
		objList = []
		for obj in context.selected_objects:
			# ignore non mesh selected objects or objs labeled to not double swap
			if obj.type != 'MESH' or ("MCprep_noSwap" in obj):
				continue
			if not obj.active_material:
				continue
			objList.append(obj)
			# obj.data.name = obj.active_material.name
			# obj.name = obj.active_material.name
			if obj.active_material:
				obj.name = util.nameGeneralize(obj.active_material.name)
		return objList

	def get_face_list(self, swap, offset: float) -> List[VectorType]:
		"""Returns list of relevant faces and mapped coordinates.

		Offset is for Mineways to virtually shift all block centers to half ints

		Returns list with each item: n (normal), g (global pos), l (local pos)
		"""
		facebook = []
		for poly in swap.data.polygons:
			gtmp = util.matmul(
				swap.matrix_world, mathutils.Vector(poly.center))
			# even without offset, list this to make values unlinked to mesh
			g = [gtmp[0] + offset, gtmp[1] + offset, gtmp[2] + offset]
			n = poly.normal  # in local coordinates
			tmp2 = poly.center
			# even without offset, list this
			l = [tmp2[0] + offset, tmp2[1] + offset, tmp2[2] + offset]
			if 0.015 < poly.area and poly.area < 0.016:
				# hack to avoid too many torches show up, both jmc2obj and Mineways
				continue
			facebook.append(face_struct(n, g, l))  # g is global, l is local
		return facebook

	def checkExternal(self, context: Context, name: str) -> Union[bool, Dict[str, str]]:
		"""Called for each object in the loop as soon as possible."""

		groupSwap = False
		meshSwap = False  # if object in both group and mesh swap, group will be used
		edgeFlush = False  # blocks perfectly on edges, require rotation
		edgeFloat = False  # floating off edge into air, require rotation ['vines','ladder','lilypad']
		torchlike = False  # ['torch','redstone_torch_on','redstone_torch_off']
		removable = False  # to be removed, hard coded.
		doorlike = False  # appears like a door.

		front_face_rotate = False
		# rotate mesh with this material's face forward (+y local=default)
		# for varied positions from exactly center on the block, 1 for Z random too
		# 1= x,y,z random; 0= only x,y random; 2=rotation random only (vertical)
		# variance = [ ['tall_grass',1], ['double_plant_grass_bottom',1],
		# ['flower_yellow',0], ['flower_red',0] ]
		variance = [False, 0]  # needs to be in this structure
		new_groups = []  # list of newly added groups in this process

		meshSwapPath = context.scene.meshswap_path
		rmable = []
		if self.track_exporter == "jmc2obj":
			rmable = [
				'book', 'brewing_stand', 'cactus_bottom', 'cactus_top', 'campfire_fire',
				'campfire_log_lit', 'door_acacia_upper', 'door_birch_upper',
				'door_dark_oak_upper', 'door_iron_top', 'door_jungle_upper',
				'door_spruce_upper', 'door_wood_top', 'double_plant_grass_top',
				'enchant_table_bottom', 'enchant_table_side', 'furnace_side',
				'furnace_top', 'pumpkin_side_lit', 'pumpkin_top_lit', 'sunflower_back',
				'sunflower_front', 'sunflower_top', 'tnt_bottom', 'tnt_side',
				'torch_flame', 'workbench_back', 'workbench_front'
			]
		elif self.track_exporter == "Mineways":
			rmable = [
				'acacia_door_top', 'birch_door_top', 'cactus_top', 'campfire_fire',
				'campfire_log_lit', 'dark_oak_door_top', 'enchanting_table_side',
				'iron_door_top', 'jungle_door_top', 'oak_door_top',
				'spruce_door_top', 'sunflower_back', 'sunflower_front',
				'sunflower_top', 'tall_grass_top', 'tnt_bottom' 'tnt_side'
			]
		else:
			# need to select one of the exporters!
			return False  # {'CANCELLED'}
		# delete unnecessary ones first
		if name in rmable:
			removable = True
			env.log("Removable!")
			return {'removable': removable}

		# check the actual name against the library
		name = generate.get_mc_canonical_name(name)[0]
		cache = get_meshswap_cache(context)
		if name in env.json_data["blocks"]["canon_mapping_block"]:
			# e.g. remaps entity/chest/normal back to chest
			name_remap = env.json_data["blocks"]["canon_mapping_block"][name]
		else:
			name_remap = None

		if name in cache["groups"] or name in util.collections():
			groupSwap = True
		elif name in cache["objects"]:
			meshSwap = True
		elif not name_remap:
			return False
		elif name_remap in cache["groups"] or name_remap in util.collections():
			groupSwap = True
			name = name_remap
		elif name_remap in cache["objects"]:
			meshSwap = True
			name = name_remap
		else:
			return False  # if not present, continue

		# now import
		env.log(f"About to link, group {groupSwap} / mesh {meshSwap}?")
		toLink = self.link_groups
		for ob in context.selected_objects:
			util.select_set(ob, False)

		# import: guaranteed to have same name as "appendObj" for the first
		# instant afterwards.

		# Used to check if to join or not.
		grouped = False
		# Need to initialize to something, though this obj not used.
		importedObj = None
		groupAppendLayer = self.append_layer

		# for blender 2.8 compatibility
		if hasattr(bpy.data, "groups"):
			g_or_c = 'Group'
		elif hasattr(bpy.data, "collections"):
			g_or_c = 'Collection'

		if groupSwap:
			if name not in util.collections():
				# if group not linked, put appended group data onto the GUI field layer
				if hasattr(context.scene, "layers"):  # blender 2.7x
					activeLayers = list(context.scene.layers)
				else:
					activeLayers = None
				if (not toLink) and (groupAppendLayer != 0):
					x = [False] * 20
					x[groupAppendLayer - 1] = True
					if hasattr(context.scene, "layers"):
						context.scene.layers = x

				# Get prelist of groups/collections to check against afterwards
				pre_colls = list(util.collections())

				# special cases, make another list for this? number of variants can vary..
				if name == "torch" or name == "Torch":
					if f"{name}.1" not in pre_colls:
						util.bAppendLink(os.path.join(meshSwapPath, g_or_c), f"{name}.1", toLink)
					if f"{name}.2" not in pre_colls:
						util.bAppendLink(os.path.join(meshSwapPath, g_or_c), f"{name}.2", toLink)
				util.bAppendLink(os.path.join(meshSwapPath, g_or_c), name, toLink)

				if util.bv28():
					post_colls = list(util.collections())
					new_groups += list(set(post_colls) - set(pre_colls))

				grouped = True
				# if activated a different layer, go back to the original ones
				if hasattr(context.scene, "layers") and activeLayers:
					context.scene.layers = activeLayers
				# 2.8 handled later with everything at once
			grouped = True
			# set properties
			for item in util.collections()[name].items():
				env.log(f"GROUP PROPS:{item}")
				try:
					x = item[1].name  # will NOT work if property UI
				except:
					x = item[0]  # the name of the property, [1] is the value
					if x == 'variance':
						variance = [True, item[1]]
					elif x == 'edgeFloat':
						edgeFloat = True
					elif x == 'doorlike':
						doorlike = True
					elif x == 'edgeFlush':
						edgeFlush = True
					elif x == 'torchlike':
						torchlike = True
					elif x == 'removable':
						removable = True
					elif x == 'frontFaceRotate':
						front_face_rotate = True
		else:
			util.bAppendLink(os.path.join(meshSwapPath, 'Object'), name, False)
			# ## NOTICE: IF THERE IS A DISCREPENCY BETWEEN ASSETS FILE AND WHAT IT SAYS SHOULD
			# ## BE IN FILE, EG NAME OF MESH TO SWAP CHANGED, INDEX ERROR IS THROWN HERE
			# ## >> MAKE a more graceful error indication.
			# filter out non-meshes in case of parent grouping or other pull-ins
			# env.log("DEBUG - post importing {}, selected objects: {}".format(
			# 	name, list(bpy.context.selected_objects)), vv_only=True)

			for ob in bpy.context.selected_objects:
				# 2.79b specific hack to clear brought in empties with the mesh
				# e.g. in case of animated deformation modifiers via object
				if ob.type != 'MESH':
					util.select_set(ob, False)
			try:
				importedObj = bpy.context.selected_objects[0]
			except:
				# in case nothing selected.. which happens even during selection?
				return False
			importedObj["MCprep_noSwap"] = 1
			# now check properties
			for item in importedObj.items():
				try:
					x = item[1].name  # will NOT work if property UI
				except:
					x = item[0]  # the name of the property, [1] is the value
					if x == 'variance':
						variance = [True, item[1]]
					elif x == 'edgeFloat':
						edgeFloat = True
					elif x == 'doorlike':
						doorlike = True
					elif x == 'edgeFlush':
						edgeFlush = True
					elif x == 'torchlike':
						torchlike = True
					elif x == 'removable':
						removable = True
			for ob in context.selected_objects:
				util.select_set(ob, False)
		# #### HERE set the other properties, e.g. variance and edgefloat, now that the obj exists
		env.log(f"groupSwap: {groupSwap}, meshSwap: {meshSwap}")
		env.log(f"edgeFloat: {edgeFloat}, variance: {variance}, torchlike: {torchlike}")
		return {
			'importName': name, 'object': importedObj, 'meshSwap': meshSwap,
			'groupSwap': groupSwap, 'variance': variance, 'edgeFlush': edgeFlush,
			'edgeFloat': edgeFloat, 'torchlike': torchlike, 'removable': removable,
			'doorlike': doorlike, 'new_groups': new_groups}

	def proccess_poly_orientations(self, face: face_struct, swapProps: Dict[str, str], swapGen: str, instance_configs: Dict[str, Tuple[VectorType, int]]) -> None:
		"""Iterate over individual face, updating instance loc/rotation

		Arguments:
			face: face struct with n (normal), g (global coord), l (local coord)
			instance_configs: pass by ref dict of instances to make, with rot and loc info
		"""

		offset = 0.5 if self.track_exporter == 'Mineways' else 0

		# Transform so centers are half ints (jmc2obj default), from local coords
		x = round(face.l[0])
		y = round(face.l[1])
		z = round(face.l[2])

		# Reverses which block to count 'on edge' for so that the instances
		# are placed in "front" of where it hangs, as this is how the meshswap
		# assets are setup (object origin will be in front of the hanging item)
		outside_hanging = 1 if swapProps['edgeFloat'] else -1
		# check if face is on unit block boundary (local coord!)
		if util.face_on_edge(face.l):
			a = face.n[0] * 0.1 * outside_hanging
			b = face.n[1] * 0.1 * outside_hanging
			c = face.n[2] * 0.1 * outside_hanging
			x = round(face.l[0] + a)
			y = round(face.l[1] + b)
			z = round(face.l[2] + c)
			# print("ON EDGE, BRO! line, "+str(x) +","+str(y)+","+str(z))
			# print([facebook[ind].l[0], facebook[ind].l[1], facebook[ind].l[2]])
		else:
			a, b, c = 0, 0, 0

		instance_key = f"{x}-{y}-{z}"
		loc = [x, y, z]

		# ### TORCHES, hack removes duplicates while not removing "edge" floats
		# if facebook[ind].l[1]+0.5 - math.floor(facebook[ind].l[1]+0.5) < 0.3:
		# 	#continue if coord. is < 1/3 of block height, to do with torch's base
		#   #in wrong cube.
		# 	if not swapProps['edgeFloat']:
		# 		#continue
		# 		print("do nothing, this is for jmc2obj")
		env.log(
			"Instance:  loc, face.local, face.nrm, hanging offset, if_edgeFloat:",
			vv_only=True)
		env.log(
			str([loc, face.l, face.n, [a, b, c], outside_hanging]),
			vv_only=True)

		# ## START HACK PATCH, FOR MINEWAYS (single-tex export) double-tall blocks
		# prevent double high grass... which mineways names sunflowers.
		hack_check = ["Sunflower", "Iron_Door", "Wooden_Door"]
		if swapGen in hack_check and f"{x}-{y - 2}-{z}" in instance_configs:
			overwrite = -1
		elif swapGen in hack_check and f"{x}-{y + 1}-{z}" in instance_configs:
			# dupList[dupList.index([x,y+1,z])] = [x,y,z]
			instance_configs[f"{x}-{y + 1}-{z}"][0] = loc  # update loc only
			overwrite = -1
		else:
			overwrite = 0  # 0 = normal, -1 = skip, 1 = overwrite the block below
		# ## END HACK PATCH

		# rotation value (second append value: 0 means no rotation, rest is 1-4)
		if overwrite < 0:
			return

		if instance_key in instance_configs and not swapProps['edgeFloat']:
			return  # no need to overwrite

		# dupList.append([x,y,z])
		# check difference from rounding, this gets us the rotation!
		x_diff = x - face.l[0]
		z_diff = z - face.l[2]

		# append rotation, exporter dependent
		if self.track_exporter == "jmc2obj":
			if swapProps['torchlike']:  # needs fixing
				if (x_diff > .1 and x_diff < 0.4):
					rot_type = 1
				elif (z_diff > .1 and z_diff < 0.4):
					rot_type = 2
				elif (x_diff < -.1 and x_diff > -0.4):
					rot_type = 3
				elif (z_diff < -.1 and z_diff > -0.4):
					rot_type = 4
				else:
					rot_type = 0
			elif swapProps['edgeFloat']:
				env.log("Edge float!", vv_only=True)
				if (y - face.l[1] < 0):
					rot_type = 8
				elif (x_diff > 0.3):
					rot_type = 7
				elif (z_diff > 0.3):
					rot_type = 0
				elif (z_diff < -0.3):
					rot_type = 6
				else:
					rot_type = 5
			elif swapProps['edgeFlush']:
				# actually 6 cases here, can need rotation below...
				# currently not necessary/used, so not programmed..
				rot_type = 0
			elif swapProps['doorlike']:
				if (y - face.l[1] < 0):
					rot_type = 8
				elif (x_diff > 0.3):
					rot_type = 7
				elif (z_diff > 0.3):
					rot_type = 0
				elif (z_diff < -0.3):
					rot_type = 6
				else:
					rot_type = 5
			else:
				rot_type = 0
		elif self.track_exporter == "Mineways":
			env.log(f"checking: {x_diff} {z_diff}")
			if swapProps['torchlike']:  # needs fixing
				env.log("recognized it's a torchlike obj..")
				if (x_diff > .1 and x_diff < 0.6):
					rot_type = 1
				elif (z_diff > .1 and z_diff < 0.6):
					rot_type = 2
				elif (x_diff < -.1 and x_diff > -0.6):
					rot_type = 3
				elif (z_diff < -.1 and z_diff > -0.6):
					rot_type = 4
				else:
					rot_type = 0
			elif swapProps['edgeFloat']:
				if (y - face.l[1] < 0):
					rot_type = 8
				elif (x_diff > 0.3):
					rot_type = 7
				elif (z_diff > 0.3):
					rot_type = 0
				elif (z_diff < -0.3):
					rot_type = 6
				else:
					rot_type = 5
			elif swapProps['edgeFlush']:
				# actually 6 cases here, can need rotation below...
				# currently not necessary/used, so not programmed..
				rot_type = 0
			elif swapProps['doorlike']:
				if (y - face.l[1] < 0):
					rot_type = 8
				elif (x_diff > 0.3):
					rot_type = 7
				elif (z_diff > 0.3):
					rot_type = 0
				elif (z_diff < -0.3):
					rot_type = 6
				else:
					rot_type = 5
			else:
				rot_type = 0
		else:
			rot_type = 0

		# update the instance ref for this face
		offset = -0.5 if self.track_exporter == 'Mineways' else 0
		loc_unoffset = [pos + offset for pos in loc]
		instance_configs[instance_key] = [loc_unoffset, rot_type]

	def add_instances_with_transforms(self, context: Context, swap, swapProps: Dict[str, str], instance_configs: Dict[str, Tuple[VectorType, int]]) -> Tuple[bool, List[Object]]:
		"""Creates all block instances for a single object.

		Will add and apply rotations, add loc variances, and run random group
		imports if any relevant.
		"""

		base = swapProps["object"]
		grouped = swapProps["groupSwap"]
		dupedObj = []  # duplicating, rotating and moving

		for instance_key in list(instance_configs):
			loc_local, rot = instance_configs[instance_key]

			# ## HIGH COMPUTATION/CRITICAL SECTION
			# refresh the scene every once in awhile
			self.counterObject += 1
			self.runcount += 1
			if (self.counterObject > self.countMax):
				self.counterObject = 0
				if not util.bv28():
					pass
					# bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
				elif hasattr(context, "view_layer"):
					context.view_layer.update()  # but does not redraw ui

			loc = util.matmul(swap.matrix_world, mathutils.Vector(loc_local))

			# loc = swap.matrix_world*mathutils.Vector(set) #local to global
			if grouped:
				# definition for randimization, defined at top!
				randGroup = util.randomizeMeshSwap(swapProps['importName'], 3)
				env.log(f"Rand group: {randGroup}")
				new_ob = util.addGroupInstance(randGroup, loc)
				if hasattr(new_ob, "empty_draw_size"):
					new_ob.empty_draw_size = 0.25
				else:
					new_ob.empty_display_size = 0.25
				dupedObj.append(new_ob)
			else:
				# TODO: Change to adding a single vertex, dupliverts
				new_ob = util.obj_copy(base, context)
				new_ob.location = mathutils.Vector(loc)
				util.select_set(new_ob, True)  # needed?
				dupedObj.append(new_ob)

			# obj = new_ob # bpy.context.selected_objects[-1]
			# do extra transformations now as necessary
			new_ob.rotation_euler = swap.rotation_euler

			# special case of un-applied,
			# 90(+/- 0.01)-0-0 rotation on source (y-up conversion)
			checkcon = swap.rotation_euler[0] >= math.pi / 2 - .01
			checkcon &= swap.rotation_euler[0] <= math.pi / 2 + .01
			checkcon &= swap.rotation_euler[1] == 0
			checkcon &= swap.rotation_euler[2] == 0
			if checkcon:
				new_ob.rotation_euler[0] -= math.pi / 2
			new_ob.scale = swap.scale

			# rotation/translation for walls, assumes last added object still selected
			x, y, offset, rotValue, z = 0, 0, 0.28, 0.436332, 0.12

			if rot == 1:
				# torch rotation 1
				x = -offset
				new_ob.location += mathutils.Vector((x, y, z))
				new_ob.rotation_euler[1] += rotValue
			elif rot == 2:
				# torch rotation 2
				y = offset
				new_ob.location += mathutils.Vector((x, y, z))
				new_ob.rotation_euler[0] += rotValue
			elif rot == 3:
				# torch rotation 3
				x = offset
				new_ob.location += mathutils.Vector((x, y, z))
				new_ob.rotation_euler[1] -= rotValue
			elif rot == 4:
				# torch rotation 4
				y = -offset
				new_ob.location += mathutils.Vector((x, y, z))
				new_ob.rotation_euler[0] -= rotValue
			elif rot == 5:
				# edge block rotation 1
				new_ob.rotation_euler[2] += -math.pi / 2
			elif rot == 6:
				# edge block rotation 2
				new_ob.rotation_euler[2] += math.pi
			elif rot == 7:
				# edge block rotation 3
				new_ob.rotation_euler[2] += math.pi / 2
			elif rot == 8:
				# edge block rotation 4 (ceiling, not 'keep same')
				new_ob.rotation_euler[0] += math.pi / 2

			# extra variance to break up regularity, e.g. for tall grass
			# first, xy and z variance
			if [True, 1] == swapProps['variance']:
				x = (random.random() - 0.5) * 0.5
				y = (random.random() - 0.5) * 0.5
				z = (random.random() / 2 - 0.5) * 0.6
				new_ob.location += mathutils.Vector((x, y, z))
			# now for just xy variance, base stays the same
			elif [True, 0] == swapProps['variance']:  # for non-z variance
				# values LOWER than *1.0 make it less variable
				x = (random.random() - 0.5) * 0.5
				y = (random.random() - 0.5) * 0.5
				new_ob.location += mathutils.Vector((x, y, 0))

			# Clear selection before moving on with next iteration
			for ob in context.selected_objects:
				if util.bv28():
					continue
				util.select_set(ob, False)
		return grouped, dupedObj

	def offsetByHalf(self, obj: Object) -> None:
		if obj.type != 'MESH':
			return
		env.log("doing offset")
		active = bpy.context.object  # preserve current active
		util.set_active_object(bpy.context, obj)
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.transform.translate(value=(0.5, 0.5, 0.5))
		bpy.ops.object.mode_set(mode='OBJECT')
		obj.location[0] -= .5
		obj.location[1] -= .5
		obj.location[2] -= .5
		util.set_active_object(bpy.context, active)


class MCPREP_OT_fix_mineways_scale(bpy.types.Operator):
	"""Quick upscaling of Mineways import by 10 for meshswapping"""
	bl_idname = "object.fixmeshswapsize"
	bl_label = "Mineways quick upscale"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		env.log("Attempting to fix Mineways scaling for meshswap")

		# get cursor loc first? shouldn't matter which mode/location though
		tmp_loc = util.get_cursor_location(context)
		if hasattr(context.space_data, "pivot_point"):
			tmp = context.space_data.pivot_point
			bpy.context.space_data.pivot_point = 'CURSOR'
		else:
			tmp = context.scene.tool_settings.transform_pivot_point
			context.scene.tool_settings.transform_pivot_point = 'CURSOR'
		util.set_cursor_location((0, 0, 0), context)

		bpy.ops.transform.resize(value=(10, 10, 10))
		bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

		if hasattr(context.space_data, "pivot_point"):
			bpy.context.space_data.pivot_point = tmp
		else:
			context.scene.tool_settings.transform_pivot_point = tmp
		util.set_cursor_location(tmp_loc, context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Register functions
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_meshswap_path_reset,
	MCPREP_OT_meshswap_spawner,
	MCPREP_OT_reload_meshswap,
	MCPREP_OT_meshswap,
	MCPREP_OT_fix_mineways_scale,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	global meshswap_cache
	global meshswap_cache_path
	meshswap_cache = {}
	meshswap_cache_path = None


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	global meshswap_cache
	global meshswap_cache_path
	meshswap_cache = {}
	meshswap_cache_path = None
