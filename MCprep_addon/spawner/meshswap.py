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

import bpy
import mathutils

# addon imports
from .. import conf
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# Mesh swap functions
# -----------------------------------------------------------------------------

meshswap_cache = {}
meshswap_cache_path = None

def get_meshswap_cache(context, clear=False):
	"""Load groups/objects from meshswap lib if not cached, return key vars."""
	global meshswap_cache
	global meshswap_cache_path

	meshswap_path = context.scene.meshswap_path
	if not meshswap_cache_path:
		meshswap_cache_path = meshswap_path
		clear = True
	if meshswap_cache_path != meshswap_path:
		clear = True

	if not meshswap_cache or clear is True:
		meshswap_cache = {"groups":[], "objects":[]}
		with bpy.data.libraries.load(meshswap_path) as (data_from, data_to):
			if hasattr(data_from, "groups"): # blender 2.7
				get_attr = "groups"
				prefix = "Group/"
			else: # 2.8
				get_attr = "collections"
				prefix = "Collection/"
			meshswap_cache["groups"] = list(getattr(data_from, get_attr))
			for obj in list(data_from.objects):
				if obj in meshswap_cache["groups"]:
					# conf.log("Skipping meshwap obj already in cache: "+str(obj))
					continue
				meshswap_cache["objects"].append(obj)
		return meshswap_cache
	else:
		return meshswap_cache


def getMeshswapList(context):
	"""Only used for UI drawing of enum menus, full list."""

	# may redraw too many times, perhaps have flag
	if not context.scene.mcprep_props.meshswap_list:
		updateMeshswapList(context)
	return [(itm.block, itm.name.title(), "Place {}".format(itm.name))
			for itm in context.scene.mcprep_props.meshswap_list]


def update_meshswap_path(self, context):
	"""for UI list path callback"""
	conf.log("Updating meshswap path", vv_only=True)
	if not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
		print("Meshswap blend file does not exist")
	updateMeshswapList(context)


def updateMeshswapList(context):
	"""Update the meshswap list"""
	meshswap_file = bpy.path.abspath(context.scene.meshswap_path)
	if not os.path.isfile(meshswap_file):
		print("Invalid meshswap blend file path")
		context.scene.mcprep_props.meshswap_list.clear()
		return

	temp_meshswap_list = []  # just to skip duplicates
	meshswap_list = []

	cache = get_meshswap_cache(context)
	prefix = "Group/" if hasattr(bpy.data, "groups") else "Collection/"
	for name in cache.get("groups"):
		if util.nameGeneralize(name).lower() in temp_meshswap_list:
			continue
		if util.nameGeneralize(name).lower() == "Rigidbodyworld".lower():
			continue
		description = "Place {x} block".format(x=name)
		meshswap_list.append((prefix+name, name.title(), description))
		temp_meshswap_list.append(util.nameGeneralize(name).lower())

	# sort the list alphabetically by name
	_, sorted_blocks = zip(*sorted(zip([block[1].lower()
		for block in meshswap_list], meshswap_list)))

	# now re-populate the UI list
	context.scene.mcprep_props.meshswap_list.clear()
	for itm in sorted_blocks:
		item = context.scene.mcprep_props.meshswap_list.add()
		item.block = itm[0]
		item.name = itm[1]
		item.description = itm[2]


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

	block = bpy.props.EnumProperty(items=swap_enum, name="Meshswap block")
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
		method, block = self.block.split("/")
		toLink = False
		use_cache = False
		group = None

		if method in ('Collection', 'Group') and block in util.collections():
			group = util.collections()[block]
			# if blender 2.8, see if collection part of the MCprepLib coll.
			use_cache = True
			for obj in group.objects:
				util.select_set(obj, True)
		else:
			util.bAppendLink(os.path.join(meshSwapPath,method), block, toLink)

		if method=="Object":
			# Object-level disabled! Must have better
			# asset management for this to work
			for ob in bpy.context.selected_objects:
				if ob.type != 'MESH':
					util.select_set(ob, False)
			try:
				importedObj = bpy.context.selected_objects[0]
			except:
				print("selected object not found") #in case nothing selected.. which happens even during selection?
				self.report({'WARNING'}, "Imported object not found")
				return {'CANCELLED'}
			importedObj["MCprep_noSwap"] = "True"
			importedObj.location = self.location
			if self.prep_materials is True:
				bpy.ops.mcprep.prep_materials(skipUsage=True) # if cycles
		else:
			if not use_cache:
				group = self.prep_collection(context, block, pre_groups)

			if not group:
				conf.log("No group identified, could not retrieve imported group")
				self.report({"ERROR"}, "Could not retrieve imported group")
				return {'CANCELLED'}

			# now finally add the group instance
			for obj in context.scene.objects:
				util.select_set(obj, False)
			ob = util.addGroupInstance(group.name, self.location)
			if self.snapping=="center":
				offset=0 # could be 0.5
				ob.location = [round(x+offset)-offset for x in self.location]
			elif self.snapping=="offset":
				offset=0.5 # could be 0.5
				ob.location = [round(x+offset)-offset for x in self.location]
			ob["MCprep_noSwap"] = "True"

			# cleanup
			if self.make_real:
				bpy.ops.object.duplicates_make_real()
				# remove the empty added by making duplicates real.
				if group is not None:
					self.fix_armature_target(
						context, context.selected_objects, group)
				for ob in context.selected_objects:
					if ob.type != "EMPTY":
						continue
					elif ob.parent or ob.children:
						continue
					util.obj_unlink_remove(ob, True, context)

			# TODO: for 2.8, hide brought in asset collections without hiding
			#   them in the individual instances in the viewport/render.
			# Need alternative method. For now, MeshSwap will just pull in
			# groups and have them visible in the scene in default location.
			# if util.bv28() and group:
				# util.hide_viewport(group, True) # hide newly added source grps
				# group.hide_render = True # makes instances hidden on render

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
				# 	continue # all good (from mod arma target perspective)
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
					print(new_target)
					new_target.animation_data.action = old_target.animation_data.action

				if mod.object in new_objs:
					continue # was already the new object target for modifier
				mod.object = new_target
				conf.log("Updated target of armature for instance of "+src_coll.name)


	def prep_collection(self, context, block, pre_groups):
		"""Prep the imported collection, ran only if newly imported (not cached)"""

		# Group method first, move append to according layer
		for ob in context.scene.objects:
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
			bpy.ops.mcprep.prep_materials(skipUsage=True) # if cycles
			for ob in context.scene.objects:
				util.select_set(ob, False)

		if hasattr(context.scene, "layers"): # 2.7 only
			for obj in objlist:
				obj.layers = layers
		return group



class MCPREP_OT_reload_meshswap(bpy.types.Operator):
	"""Force reload the MeshSwap objects and cache."""
	bl_idname = "mcprep.reload_meshswap"
	bl_label = "Reload MeshSwap"

	@tracking.report_error
	def execute(self, context):
		if not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
			self.report({'WARNING'}, "Meshswap blend file does not exist")
		get_meshswap_cache(context, clear=True)
		updateMeshswapList(context)
		return {'FINISHED'}


class MCPREP_UL_meshswap_list(bpy.types.UIList):
	"""For asset listing UIList drawing"""
	# previously McprepMeshswap_UIList
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):

		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='QUESTION')


class MCPREP_OT_meshswap(bpy.types.Operator):
	"""Swap minecraft objects from world imports for custom 3D models in the according meshSwap blend file"""
	bl_idname = "mcprep.meshswap"
	bl_label = "Mesh Swap"
	bl_options = {'REGISTER', 'UNDO'}

	#used for only occasionally refreshing the 3D scene while mesh swapping
	counterObject = 0  # used in count
	countMax = 5  # count compared to this, frequency of refresh (number of objs)

	# properties for draw
	meshswap_join = bpy.props.BoolProperty(
		name="Join same blocks",
		default=True,
		description="Join together swapped blocks of the same type (unless swapped with a group)")
	use_dupliverts = bpy.props.BoolProperty(
		name="Use dupliverts (faster)",
		default=True,
		description="Use dupliverts to add meshes")
	link_groups = bpy.props.BoolProperty(
		name="Link groups",
		default=False,
		description="Link groups instead of appending")
	prep_materials = bpy.props.BoolProperty(
		name="Prep materials",
		default=False,
		description="Automatically apply prep materials (with default settings) to blocks added in")
	append_layer = bpy.props.IntProperty(
		name="Append layer",
		default=20,
		min=0,
		max=20,
		description="When groups are appended instead of linked, "+\
				"the objects part of the group will be placed in this "+\
				"layer, 0 means same as active layers")

	meshswap_lamps = bpy.props.EnumProperty(
		name="Lamps",
		items= [('group', 'With groups', 'Repalce light emitting blocks group instances, containing 3D blocks and lamps'),
				('material', 'By material', "Add lamps above light emitting blocks, withotu modifying original light-emitting blocks"),
				('none', 'Skip lights', "Don't add any lights, skip meshswapping for light-emitting blocks")],
		description="Set how lights are added (if any, based on selected materials)"
		)

	filmic_values = bpy.props.BoolProperty(
		name="Use filmic lamp values",
		default=False,
		description="Set added lamp values with appropriate filmic rendering values")


	@classmethod
	def poll(cls, context):
		addon_prefs = util.get_user_preferences(context)
		return addon_prefs.MCprep_exporter_type != "(choose)"

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400*util.ui_scale())

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
		row.prop(self,"meshswap_join")
		row = layout.row()
		row.prop(self,"link_groups")
		row.prop(self,"prep_materials")
		row = layout.row()
		if not util.bv28():
			row.prop(self,"append_layer")

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
			col.label(text="WARNING: May take a long time to process!!", icon="ERROR")
			col.label(text="If you selected a large number of blocks to meshswap,", icon="BLANK1")
			col.label(text="consider using a smaller area closer to the camera", icon="BLANK1")

	def checkExternal(self, context, name):
		"""Called for each object in the loop as soon as possible."""

		groupSwap = False
		meshSwap = False # if object  is in both group and mesh swap, group will be used
		edgeFlush = False # blocks perfectly on edges, require rotation
		edgeFloat = False # floating off edge into air, require rotation ['vines','ladder','lilypad']
		torchlike = False # ['torch','redstone_torch_on','redstone_torch_off']
		removable = False # to be removed, hard coded.
		doorlike = False # appears like a door.
		# for varied positions from exactly center on the block, 1 for Z random too
		# 1= x,y,z random; 0= only x,y random; 2=rotation random only (vertical)
		#variance = [ ['tall_grass',1], ['double_plant_grass_bottom',1],
		#			['flower_yellow',0], ['flower_red',0] ]
		variance = [False,0] # needs to be in this structure
		new_groups = [] # list of newly added groups in this process

		addon_prefs = util.get_user_preferences(context)
		meshSwapPath = context.scene.meshswap_path
		rmable = []
		if addon_prefs.MCprep_exporter_type == "jmc2obj":
			rmable = ['double_plant_grass_top','torch_flame','cactus_side','cactus_bottom','book',
						'enchant_table_side','enchant_table_bottom','door_iron_top','door_wood_top',
						'brewing_stand','door_dark_oak_upper','door_acacia_upper','door_jungle_upper',
						'door_birch_upper','door_spruce_upper','tnt_top','tnt_bottom']
		elif addon_prefs.MCprep_exporter_type == "Mineways":
			rmable = [] # Mineways removable objs
		else:
			# need to select one of the exporters!
			return False # {'CANCELLED'}
		# delete unnecessary ones first
		if name in rmable:
			removable = True
			conf.log("Removable!")
			return {'removable':removable}

		# check the actual name against the library
		cache = get_meshswap_cache(context)
		if name in cache["groups"] or name in util.collections():
			groupSwap = True
		elif name in cache["objects"]:
			meshSwap = True
		else:
			return False # if not present, continue

		# now import
		conf.log("about to link, group {} / mesh {}?".format(
			groupSwap, meshSwap))
		toLink = self.link_groups
		for ob in context.selected_objects:
			util.select_set(ob, False)
		#import: guaranteed to have same name as "appendObj" for the first instant afterwards
		grouped = False # used to check if to join or not
		importedObj = None		# need to initialize to something, though this obj not used
		groupAppendLayer = self.append_layer

		# for blender 2.8 compatibility
		if hasattr(bpy.data, "groups"):
			g_or_c = 'Group'
		elif hasattr(bpy.data, "collections"):
			g_or_c = 'Collection'

		if groupSwap:
			if name not in util.collections():
				# if group not linked, put appended group data onto the GUI field layer
				if hasattr(context.scene, "layers"):
					activeLayers = list(context.scene.layers)
				else:
					activeLayers = None
				if (not toLink) and (groupAppendLayer!=0):
					x = [False]*20
					x[groupAppendLayer-1] = True
					if hasattr(context.scene, "layers"):
						context.scene.layers = x

				# Get prelist of groups/collections to check against afterwards
				pre_colls = list(util.collections())

				# special cases, make another list for this? number of variants can vary..
				if name == "torch" or name == "Torch":
					if name+".1" not in pre_colls:
						util.bAppendLink(os.path.join(meshSwapPath, g_or_c), name+".1", toLink)
					# bpy.ops.object.delete()
					if name+".2" not in pre_colls:
						util.bAppendLink(os.path.join(meshSwapPath, g_or_c), name+".2", toLink)
					# bpy.ops.object.delete()
				util.bAppendLink(os.path.join(meshSwapPath, g_or_c), name, toLink)

				if util.bv28():
					post_colls = list(util.collections())
					new_groups += list(set(post_colls)-set(pre_colls))

				grouped = True
				# if activated a different layer, go back to the original ones
				if hasattr(context.scene, "layers") and activeLayers:
					context.scene.layers = activeLayers
				else:
					conf.log("TODO: assign meshswap 2.8 collections", vv_only=True)
			grouped = True
			# set properties
			for item in util.collections()[name].items():
				conf.log("GROUP PROPS:" + str(item))
				try:
					x = item[1].name #will NOT work if property UI
				except:
					x = item[0] # the name of the property, [1] is the value
					if x=='variance':
						variance = [True, item[1]]
					elif x=='edgeFloat':
						edgeFloat = True
					elif x=='doorlike':
						doorlike = True
					elif x=='edgeFlush':
						edgeFlush = True
					elif x=='torchlike':
						torchlike = True
					elif x=='removable':
						removable = True
		else:
			util.bAppendLink(os.path.join(meshSwapPath, 'Object'), name, False)
			### NOTICE: IF THERE IS A DISCREPENCY BETWEEN ASSETS FILE AND WHAT IT SAYS SHOULD
			### BE IN FILE, EG NAME OF MESH TO SWAP CHANGED,  INDEX ERROR IS THROWN HERE
			### >> MAKE a more graceful error indication.
			# filter out non-meshes in case of parent grouping or other pull-ins
			# conf.log("DEBUG - post importing {}, selected objects: {}".format(
			# 	name, list(bpy.context.selected_objects)), vv_only=True)

			for ob in bpy.context.selected_objects:
				# 2.79b specific hack to clear brought in empties with the mesh
				# e.g. in case of animated deformation modifiers via object
				if ob.type != 'MESH':
					util.select_set(ob, False)
			try:
				importedObj = bpy.context.selected_objects[0]
			except:
				return False #in case nothing selected.. which happens even during selection?
			importedObj["MCprep_noSwap"] = "True"
			# now check properties
			for item in importedObj.items():
				try:
					x = item[1].name #will NOT work if property UI
				except:
					x = item[0] # the name of the property, [1] is the value
					if x=='variance':
						variance = [True, item[1]]
					elif x=='edgeFloat':
						edgeFloat = True
					elif x=='doorlike':
						doorlike = True
					elif x=='edgeFlush':
						edgeFlush = True
					elif x=='torchlike':
						torchlike = True
					elif x=='removable':
						removable = True
			for ob in context.selected_objects:
				util.select_set(ob, False)
		##### HERE set the other properties, e.g. variance and edgefloat, now that the obj exists
		conf.log("groupSwap: {}, meshSwap: {}".format(groupSwap, meshSwap))
		conf.log("edgeFloat: {}, variance: {}, torchlike: {}".format(
			edgeFloat, variance, torchlike))
		return {'meshSwap':meshSwap, 'groupSwap':groupSwap,'variance':variance,
				'edgeFlush':edgeFlush,'edgeFloat':edgeFloat,'torchlike':torchlike,
				'removable':removable,'object':importedObj,'doorlike':doorlike,
				'new_groups':new_groups}

	def offsetByHalf(self, obj):
		if obj.type != 'MESH':
			return
		# bpy.ops.object.mode_set(mode='OBJECT')
		conf.log("doing offset")
		# bpy.ops.mesh.select_all(action='DESELECT')
		active = bpy.context.object #preserve current active
		util.set_active_object(bpy.context, obj)
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.transform.translate(value=(0.5, 0.5, 0.5))
		bpy.ops.object.mode_set(mode='OBJECT')
		obj.location[0] -= .5
		obj.location[1] -= .5
		obj.location[2] -= .5
		util.set_active_object(bpy.context, active)

	track_function = "meshswap"
	@tracking.report_error
	def execute(self, context):
		runcount = 0 # counter.. if zero by end, raise error that no selected objects matched
		## debug, restart check
		addon_prefs = util.get_user_preferences(context)
		direc = context.scene.meshswap_path

		# check library file exists
		if not os.path.isfile(direc):
			#extract actual path from the relative one if relative, e.g. //file.blend
			direc = bpy.path.abspath(direc)
			#bpy.ops.object.dialogue('INVOKE_DEFAULT') # DOES work! but less streamlined
			if not os.path.isfile(direc):
				self.report({'ERROR'}, "Mesh swap blend file not found!") # better, actual "error"
				return {'CANCELLED'}

		# get some scene information
		doOffset = (addon_prefs.MCprep_exporter_type == "Mineways")
		# separate each material into a separate object
		# could also recombine similar materials here, so happens just once.
		selList = context.selected_objects
		new_groups = [] # for later hiding of all source new groups
		for obj in selList:
			try:
				bpy.ops.object.convert(target='MESH')
			except:
				pass
			bpy.ops.mesh.separate(type='MATERIAL')
		# now do type checking and fix any name discrepancies
		selList = context.selected_objects # re-grab having made new objects
		objList = []
		removeList = []  # list of objects to remove at end
		for obj in selList:
			#ignore non mesh selected objects or objs labeled to not double swap
			if obj.type != 'MESH' or ("MCprep_noSwap" in obj):
				continue
			if not obj.active_material:
				continue
			obj.data.name = obj.active_material.name
			obj.name = obj.active_material.name
			objList.append(obj)

		# global scale, WIP
		gScale = 1
		conf.log("Using scale: {}".format(gScale))
		conf.log(objList)

		#primary loop, for each OBJECT needing swapping
		for swap in objList:
			swapGen = util.nameGeneralize(swap.name)
			conf.log("Simplified name: {x}".format(x=swapGen))
			swapProps = self.checkExternal(context, swapGen) # IMPORTS, gets lists properties, etc
			if swapProps == False: # issue in swapProps, e.g. not a mesh or not in lib or some error
				continue

			if swapProps.get('new_groups'):
				new_groups += swapProps['new_groups']
			#special cases, for "extra" mesh pieces we don't want around afterwards
			if swapProps['removable']:
				removeList.append(swap)
				continue
			# just selecting mesh with same name and if in objList
			if not (swapProps['meshSwap'] or swapProps['groupSwap']):
				continue
			conf.log("Swapping '{x}', simplified name '{y}".format(
					x=swap.name, y=swapGen))
			# if mineways/necessary, offset mesh by a half. Do it on a per object basis.
			if doOffset:
				self.offsetByHalf(swap)

			for poly in swap.data.polygons:
				poly.select = False

			#loop through each face or "polygon" of mesh
			facebook = [] # store the information of the obj's faces..
			for poly in swap.data.polygons:  #range(0,len(polyList)):
				gtmp = util.matmul(
					swap.matrix_world, mathutils.Vector(poly.center))
				g = [gtmp[0],gtmp[1],gtmp[2]]
				n = poly.normal
				tmp2 = poly.center
				l = [tmp2[0],tmp2[1],tmp2[2]] #to make value unlinked to mesh
				if 0.015 < poly.area and poly.area < 0.016:
					continue # hack for not having too many torches show up, both jmc2obj and Mineways
				facebook.append([n,g,l]) # g is global, l is local

			for ob in context.selected_objects:
				if util.bv28():
					continue
				util.select_set(ob, False)

			# removing duplicates and checking orientation
			dupList = []	#where actual blocks are to be added
			rotList = []	#rotation of blocks
			for setNum in range(0,len(facebook)):
				# LOCAL coordinates!!!
				x = round(facebook[setNum][2][0]) #since center's are half ints..
				y = round(facebook[setNum][2][1]) #don't need (+0.5) -.5 structure
				z = round(facebook[setNum][2][2])

				outsideBool = -1
				if (swapProps['edgeFloat']): outsideBool = 1

				if util.onEdge(facebook[setNum][2]): #check if face is on unit block boundary (local coord!)
					a = facebook[setNum][0][0] * 0.4 * outsideBool #x normal
					b = facebook[setNum][0][1] * 0.4 * outsideBool #y normal
					c = facebook[setNum][0][2] * 0.4 * outsideBool #z normal
					x = round(facebook[setNum][2][0]+a)
					y = round(facebook[setNum][2][1]+b)
					z = round(facebook[setNum][2][2]+c)
					#print("ON EDGE, BRO! line, "+str(x) +","+str(y)+","+str(z))
					#print([facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])

				#### TORCHES, hack removes duplicates while not removing "edge" floats
				# if facebook[setNum][2][1]+0.5 - math.floor(facebook[setNum][2][1]+0.5) < 0.3:
				# 	#continue if coord. is < 1/3 of block height, to do with torch's base in wrong cube.
				# 	if not swapProps['edgeFloat']:
				# 		#continue
				# 		print("do nothing, this is for jmc2obj")
				conf.log(" DUPLIST: ")
				conf.log(
					str([[x,y,z], [facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]]]),
				True)

				### START HACK PATCH, FOR MINEWAYS double-tall adding
				# prevent double high grass... which mineways names sunflowers.
				overwrite = 0 # 0 means normal, -1 means skip, 1 means overwrite the one below
				if ([x,y-1,z] in dupList) and swapGen in ["Sunflower","Iron_Door","Wooden_Door"]:
					overwrite = -1
				elif ([x,y+1,z] in dupList) and swapGen in ["Sunflower","Iron_Door","Wooden_Door"]:
					dupList[dupList.index([x,y+1,z])] = [x,y,z]
					overwrite = -1
				### END HACK PATCH

				# rotation value (second append value: 0 means nothing, rest 1-4.
				if ((not [x,y,z] in dupList) or (swapProps['edgeFloat'])) and overwrite >=0:
					# append location
					dupList.append([x,y,z])
					# check difference from rounding, this gets us the rotation!
					x_diff = x-facebook[setNum][2][0]
					#print(facebook[setNum][2][0],x,x_diff)
					z_diff = z-facebook[setNum][2][2]
					#print(facebook[setNum][2][2],z,z_diff)

					# append rotation, exporter dependent
					if addon_prefs.MCprep_exporter_type == "jmc2obj":
						if swapProps['torchlike']: # needs fixing
							if (x_diff>.1 and x_diff < 0.4):
								rotList.append(1)
							elif (z_diff>.1 and z_diff < 0.4):
								rotList.append(2)
							elif (x_diff<-.1 and x_diff > -0.4):
								rotList.append(3)
							elif (z_diff<-.1 and z_diff > -0.4):
								rotList.append(4)
							else:
								rotList.append(0)
						elif swapProps['edgeFloat']:
							if (y-facebook[setNum][2][1] < 0):
								rotList.append(8)
							elif (x_diff > 0.3):
								rotList.append(7)
							elif (z_diff > 0.3):
								rotList.append(0)
							elif (z_diff < -0.3):
								rotList.append(6)
							else:
								rotList.append(5)
						elif swapProps['edgeFlush']:
							# actually 6 cases here, can need rotation below...
							# currently not necessary/used, so not programmed..
							rotList.append(0)
						elif swapProps['doorlike']:
							if (y-facebook[setNum][2][1] < 0):
								rotList.append(8)
							elif (x_diff > 0.3):
								rotList.append(7)
							elif (z_diff > 0.3):
								rotList.append(0)
							elif (z_diff < -0.3):
								rotList.append(6)
							else:
								rotList.append(5)
						else:
							rotList.append(0)
					elif addon_prefs.MCprep_exporter_type == "Mineways":
						conf.log("checking: {} {}".format(x_diff,z_diff))
						if swapProps['torchlike']: # needs fixing
							conf.log("recognized it's a torchlike obj..")
							if (x_diff>.1 and x_diff < 0.6):
								rotList.append(1)
								#print("rot 1?")
							elif (z_diff>.1 and z_diff < 0.6):
								rotList.append(2)
								#print("rot 2?")
							elif (x_diff<-.1 and x_diff > -0.6):
								#print("rot 3?")
								rotList.append(3)
							elif (z_diff<-.1 and z_diff > -0.6):
								rotList.append(4)
								#print("rot 4?")
							else:
								rotList.append(0)
								#print("rot 0?")
						elif swapProps['edgeFloat']:
							if (y-facebook[setNum][2][1] < 0):
								rotList.append(8)
							elif (x_diff > 0.3):
								rotList.append(7)
							elif (z_diff > 0.3):
								rotList.append(0)
							elif (z_diff < -0.3):
								rotList.append(6)
							else:
								rotList.append(5)
						elif swapProps['edgeFlush']:
							# actually 6 cases here, can need rotation below...
							# currently not necessary/used, so not programmed..
							rotList.append(0)
						elif swapProps['doorlike']:
							if (y-facebook[setNum][2][1] < 0):
								rotList.append(8)
							elif (x_diff > 0.3):
								rotList.append(7)
							elif (z_diff > 0.3):
								rotList.append(0)
							elif (z_diff < -0.3):
								rotList.append(6)
							else:
								rotList.append(5)
						else:
							rotList.append(0)
					else:
						rotList.append(0)

			##### OPTION HERE TO SEGMENT INTO NEW FUNCTION
			conf.log("### > trans")
			for ob in context.selected_objects:
				if util.bv28():
					continue
				util.select_set(ob, False)
			base = swapProps["object"]
			grouped = swapProps["groupSwap"]
			#self.counterObject = 0
			# duplicating, rotating and moving
			dupedObj = []

			for (set,rot) in zip(dupList,rotList):
				### HIGH COMPUTATION/CRITICAL SECTION
				#refresh the scene every once in awhile
				self.counterObject+=1
				runcount +=1
				if (self.counterObject > self.countMax):
					self.counterObject = 0
					#below technically a "hack", should use: bpy.data.scenes[0].update()
					if not util.bv28():
						bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

				loc = util.matmul(swap.matrix_world, mathutils.Vector(set))

				# loc = swap.matrix_world*mathutils.Vector(set) #local to global
				if grouped:
					# definition for randimization, defined at top!
					randGroup = util.randomizeMeshSawp(swapGen,3)
					conf.log("Rand group: {}".format(randGroup))

					# The built in method fails, bpy.ops.object.group_instance_add(...)
					#UPDATE: I reported the bug, and they fixed it nearly instantly =D
					# but it was recommended to do the below anyways.
					new_ob = util.addGroupInstance(randGroup,loc)

				else:
					new_ob = util.obj_copy(base, context)
					new_ob.location = mathutils.Vector(loc)
					util.select_set(new_ob, True)  # needed?
					dupedObj.append(new_ob)

				obj = new_ob # bpy.context.selected_objects[-1]
				# do extra transformations now as necessary
				obj.rotation_euler = swap.rotation_euler
				# special case of un-applied, 90(+/- 0.01)-0-0 rotation on source (y-up conversion)
				if (swap.rotation_euler[0]>= math.pi/2-.01 and swap.rotation_euler[0]<= math.pi/2+.01
					and swap.rotation_euler[1]==0 and swap.rotation_euler[2]==0):
					obj.rotation_euler[0] -= math.pi/2
				obj.scale = swap.scale

				#rotation/translation for walls, assumes last added object still selected
				x,y,offset,rotValue,z = 0,0,0.28,0.436332,0.12

				if rot == 1:
					# torch rotation 1
					x = -offset
					obj.location += mathutils.Vector((x, y, z))
					obj.rotation_euler[1]+=rotValue
				elif rot == 2:
					# torch rotation 2
					y = offset
					obj.location += mathutils.Vector((x, y, z))
					obj.rotation_euler[0]+=rotValue
				elif rot == 3:
					# torch rotation 3
					x = offset
					obj.location += mathutils.Vector((x, y, z))
					obj.rotation_euler[1]-=rotValue
				elif rot == 4:
					# torch rotation 4
					y = -offset
					obj.location += mathutils.Vector((x, y, z))
					obj.rotation_euler[0]-=rotValue
				elif rot == 5:
					# edge block rotation 1
					obj.rotation_euler[2]+= -math.pi/2
				elif rot == 6:
					# edge block rotation 2
					obj.rotation_euler[2]+= math.pi
				elif rot == 7:
					# edge block rotation 3
					obj.rotation_euler[2]+= math.pi/2
				elif rot==8:
					# edge block rotation 4 (ceiling, not 'keep same')
					obj.rotation_euler[0]+= math.pi/2

				# extra variance to break up regularity, e.g. for tall grass
				# first, xy and z variance
				if [True,1] == swapProps['variance']:
					x = (random.random()-0.5)*0.5
					y = (random.random()-0.5)*0.5
					z = (random.random()/2-0.5)*0.6
					obj.location += mathutils.Vector((x, y, z))
				# now for just xy variance, base stays the same
				elif [True,0] == swapProps['variance']: # for non-z variance
					x = (random.random()-0.5)*0.5	 # values LOWER than *1.0 make it less variable
					y = (random.random()-0.5)*0.5
					obj.location += mathutils.Vector((x, y, 0))
				for ob in context.selected_objects:
					if util.bv28():
						continue
					util.select_set(ob, False)

			### END CRITICAL SECTION

			if not grouped:
				if base in dupedObj:
					dupedObj.pop(dupedObj.index(base))
				util.obj_unlink_remove(base, True, context)

			#join meshes together
			if not grouped and dupedObj and self.meshswap_join:
				# ERROR HERE if don't do the len(dupedObj) thing.
				util.set_active_object(context, dupedObj[0])
				for d in dupedObj:
					if d.type != 'MESH':
						print("Skipping non-mesh:", d)
						continue
					util.select_set(d, True)
				if context.mode != "OBJECT":
					bpy.ops.object.mode_set(mode='OBJECT')

				# to avoid reselection later objects that were joined
				for obtemp in context.selected_objects:
					if obtemp in selList:
						selList.pop(selList.index(obtemp))
				bpy.ops.object.join()
				selList.append(context.selected_objects[0])

			removeList.append(swap)

			# Setup for later re-selection
			for d in dupedObj:
				if d in removeList:
					continue
				# Setup below is for cross compatibility, in 2.8 & 2.7
				# where accessing a field on deleted object will raise error
				try:
					if not hasattr(d, "users"):
						continue
				except ReferenceError:
					continue
				selList.append(d)

		# final re-selection and deletion
		if runcount > 0:
			for rm in removeList:
				if rm in selList:
					selList.pop(selList.index(rm)) # to be safe, pop from list before removal
				try:
					util.obj_unlink_remove(rm, True, context)
				except:
					print("Failed to clear user/remove object")

		for d in selList:
			# Risk if object was joined against another object that its data
			# no longer exists, which can result in a failure e.g. for 2.72
			# However, pre-work should have prevented interacting with already
			# deleted object here, so the try/except is more for later blender
			# versions to fail gracefully just in case
			try:
				if not hasattr(d, "users"): # can be crashing point pre 2.79(?)
					continue
			except ReferenceError:
					continue
			util.select_set(d, True)

		if util.bv28():
			for grp in new_groups:
				util.hide_viewport(grp, True)
				# grp.hide_render = True

		if runcount==0:
			self.report({'ERROR'}, "Nothing swapped, likely no materials of selected objects match the meshswap file objects/groups")
			return {'CANCELLED'}
		elif runcount==1:
			self.report({'INFO'}, "Swapped 1 object")
			return {'FINISHED'}
		else:
			self.report({'INFO'}, "Swapped {x} objects".format(x=runcount))
			return {'FINISHED'}


class MCPREP_OT_fix_mineways_scale(bpy.types.Operator):
	"""Quick upscaling of Mineways import by 10 for meshswapping"""
	bl_idname = "object.fixmeshswapsize"
	bl_label = "Mineways quick upscale"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		conf.log("Attempting to fix Mineways scaling for meshswap")
		# get cursor loc first? shouldn't matter which mode/location though
		tmp = bpy.context.space_data.pivot_point
		tmpLoc = util.get_cuser_location(context)
		bpy.context.space_data.pivot_point = 'CURSOR'
		util.set_cuser_location((0,0,0), context)

		bpy.ops.transform.resize(value=(10, 10, 10))
		bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
		# bpy.ops.transform.resize(value=(.1, .1, .1))
		bpy.context.space_data.pivot_point = tmp
		util.set_cuser_location((0,0,0), tmpLoc)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Register functions
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_meshswap_path_reset,
	MCPREP_OT_meshswap_spawner,
	MCPREP_OT_reload_meshswap,
	MCPREP_UL_meshswap_list,
	MCPREP_OT_meshswap,
	MCPREP_OT_fix_mineways_scale,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
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
