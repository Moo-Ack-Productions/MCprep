# ##### MCprep #####
#
# Developed by Patrick W. Crawford, see more at
# http://theduckcow.com/dev/blender/MCprep
# 
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
import os
import math
import mathutils
import random

# addon imports
from . import conf
from . import util
from . import tracking


# -----------------------------------------------------------------------------
# Mesh swap functions
# -----------------------------------------------------------------------------

# only used for UI drawing of enum menus, full list
def getMeshswapList(context):

	# test the link path first!
	# rigpath = bpy.path.abspath(context.scene.mcrig_path) #addon_prefs.mcrig_path
	# blendFiles = []
	# riglist = []

	if len(conf.rig_list)==0: # may redraw too many times, perhaps have flag
		return updateMeshswapList(context)

	else:
		return conf.meshswap_list


# for UI list path callback
def update_meshswap_path(self, context):
	if conf.vv:print("Updating meshswap path")
	updateMeshswapList(context)

# Update the meshswap list
def updateMeshswapList(context):
	# test the link path first!
	meshswap_file = bpy.path.abspath(context.scene.meshswap_path)
	if os.path.isfile(meshswap_file)==False:
		print("Invalid meshswap blend file path")
	temp_meshswap_list = []
	meshswap_list = []
	# conf.meshswap_list = []

	with bpy.data.libraries.load(meshswap_file) as (data_from, data_to):
		for name in data_from.groups:

			# special cases, skip some groups/repeats
			if util.nameGeneralize(name).lower() in temp_meshswap_list: continue
			if util.nameGeneralize(name).lower() == "Rigidbodyworld".lower():
				continue


			description = "Place {x} block".format(x=name)
			meshswap_list.append( ("Group/"+name,name.title(),description) )
			temp_meshswap_list.append(util.nameGeneralize(name).lower())
		# here do same for blocks, assuming no name clashes. 
		# way to 'ignore' blocks from source? ID prop?

		# for name in data_from.objects:
		# 	if util.nameGeneralize(name).lower() in temp_meshswap_list: continue
		# 	description = "Place {x} block".format(x=name)
		# 	meshswap_list.append( ("Object/"+name,name.title(),description) )
		# 	temp_meshswap_list.append(util.nameGeneralize(name).lower())

	# sort the list alphebtically by name
	temp, sorted_blocks = zip(*sorted(zip([block[1].lower() for block in meshswap_list], meshswap_list)))
	conf.meshswap_list = sorted_blocks

	# now re-populate the UI list
	context.scene.mcprep_meshswap_list.clear()
	for itm in conf.meshswap_list:
		item = context.scene.mcprep_meshswap_list.add()
		item.label = itm[2]
		item.description = itm[2]
		item.name = itm[1].title()

	return conf.meshswap_list


# -----------------------------------------------------------------------------
# Mesh swap functions
# -----------------------------------------------------------------------------


class MCPREP_spawnPathReset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.meshswap_pathreset"
	bl_label = "Reset meshswap path"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self,context):
		
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		context.scene.meshswap_path = addon_prefs.meshswap_path
		updateMeshswapList(context)
		return {'FINISHED'}


class MCPREP_meshswapSpawner(bpy.types.Operator):
	"""Instantly spawn built-in meshswap blocks into a scene"""
	bl_idname = "mcprep.meshswap_spawner"
	bl_label = "Meshswap Spawner"
	bl_options = {'REGISTER', 'UNDO'}

	# properties, will appear in redo-last menu
	def swap_enum(self, context):
		return getMeshswapList(context)

	meshswap_block = bpy.props.EnumProperty(items=swap_enum, name="Meshswap block")
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
	# instantiate if group?

	def execute(self, context):

		tracking.trackUsage("meshswapSpawner",self.meshswap_block)

		pre_groups = list(bpy.data.groups)

		meshSwapPath = bpy.path.abspath(context.scene.meshswap_path)
		method,block = self.meshswap_block.split("/")
		toLink = False

		util.bAppendLink(os.path.join(meshSwapPath,method), block, toLink)

		if method=="Object":
			# Object-level disabled! Must have better
			# asset management for this to work
			try:
				importedObj = bpy.context.selected_objects[0]
			except:
				print("selected obejct not found") #in case nothing selected.. which happens even during selection?
				return {'FINISHED'}
			importedObj["MCprep_noSwap"] = "True"
			importedObj.location = self.location
			if self.prep_materials==True:
				bpy.ops.mcprep.mat_change(skipUsage=True) # if cycles
		else:
			# Group method

			# first, move append to according layer
			bpy.ops.object.select_all(action='DESELECT')

			layers = [False]*20
			if self.append_layer==0:
				layers = context.scene.layers
			else:
				layers[self.append_layer-1] = True
			objlist = []
			groupname = None
			for g in bpy.data.groups:
				if g in pre_groups:continue

				for ob in g.objects:
					if ob.name in context.scene.objects:
						#context.scene.objects.unlink(ob)
						objlist.append(ob)
				if util.nameGeneralize(g.name) == util.nameGeneralize(block):
					groupname = g

			if groupname==None:
				self.report({"ERROR"},"Could not retreive imported group")
				return {'CANCELLED'}

			if self.prep_materials==True:
				for ob in objlist:
					ob.select=True
				bpy.ops.mcprep.mat_change(skipUsage=True) # if cycles
				bpy.ops.object.select_all(action='DESELECT')

			for ob in objlist:
				ob.layers = layers

			# now finally add the group instance
			bpy.ops.object.select_all(action='DESELECT')
			ob = util.addGroupInstance(groupname.name,self.location)
			if self.snapping=="center":
				offset=0 # could be 0.5
				ob.location = [round(x+offset)-offset for x in self.location]
			elif self.snapping=="offset":
				offset=0.5 # could be 0.5
				ob.location = [round(x+offset)-offset for x in self.location]
			ob["MCprep_noSwap"] = "True"
			if self.make_real:bpy.ops.object.duplicates_make_real()


		return {'FINISHED'}


class MCPREP_reloadMeshswap(bpy.types.Operator):
	"""Force reload the mob spawner rigs, use after manually adding rigs to folders"""
	bl_idname = "mcprep.reload_meshswap"
	bl_label = "Reload the meshswap and cache"

	def execute(self,context):
		updateMeshswapList(context)
		return {'FINISHED'}


# for asset listing UIList drawing
class MCPREP_meshswap_UIList(bpy.types.UIList):
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
			# row.scale_x = 0.25
			# row.operator('mcprep.spawner_set_active_mob', emboss=False, text='',
			#               icon=ic).index = index
			# row.operator('mcprep.mob_spawner_direct',emboss=False, text='',
			# 			icon='FORWARD').mcmob_index = index

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


class meshSwap(bpy.types.Operator):
	"""Swap minecraft objects from world imports for custom 3D models in the according meshSwap blend file"""
	bl_idname = "mcprep.meshswap"
	bl_label = "MCprep meshSwap"
	bl_options = {'REGISTER', 'UNDO'}
	
	#used for only occasionally refreshing the 3D scene while mesh swapping
	counterObject = 0	# used in count
	countMax = 5		# count compared to this, frequency of refresh (number of objs)

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
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		return addon_prefs.MCprep_exporter_type != "(choose)"

	# force use UI
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400)

	def draw(self, context):
		layout = self.layout

		# please save the file first
		if False:
			layout.label("You must save your blend file before meshswapping", icon="ERROR")
			return

		layout.label("GENERAL SETTINGS")
		row = layout.row()
		# row.prop(self,"use_dupliverts") # coming soon
		row.prop(self,"meshswap_join")
		row = layout.row()
		row.prop(self,"link_groups")
		row.prop(self,"prep_materials")
		row = layout.row()
		row.prop(self,"append_layer")
		
		# multi settings, to come
		# layout.split()
		# layout.label("HOW TO ADD LIGHTS")
		# row = layout.row()
		# row.prop(self,"meshswap_lamps",expand=True)
		# row = layout.row()
		# row.prop(self,"filmic_values")
		
		if True:
			layout.split()
			col = layout.column()
			col.scale_y = 0.7
			col.label("WARNING: May take a long time to process!!", icon="ERROR")
			col.label("If you selected a large number of blocks to meshswap,", icon="BLANK1")
			col.label("consider using a smaller area closer to the camera", icon="BLANK1")


	# called for each object in the loop as soon as possible
	def checkExternal(self, context, name):
		if conf.v:print("Checking external library")
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		
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
			return {'CANCELLED'}
		# delete unnecessary ones first
		if name in rmable:
			removable = True
			if conf.v:print("Removable!")
			return {'removable':removable}
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

		#check the actual name against the library
		with bpy.data.libraries.load(meshSwapPath) as (data_from, data_to):
			if name in data_from.groups or name in bpy.data.groups:
				groupSwap = True
			elif name in data_from.objects:
				meshSwap = True

		# now import
		if conf.v:print("about to link, group/mesh?",groupSwap,meshSwap)
		toLink = self.link_groups # should read from addon prefs, false by default
		bpy.ops.object.select_all(action='DESELECT') # context...? ensure in 3d view..
		#import: guaranteed to have same name as "appendObj" for the first instant afterwards
		grouped = False # used to check if to join or not
		importedObj = None		# need to initialize to something, though this obj no used
		groupAppendLayer = self.append_layer
		if groupSwap and name not in bpy.data.groups:
			# if group not linked, put appended group data onto the GUI field layer
			activeLayers = list(context.scene.layers)
			if (not toLink) and (groupAppendLayer!=0):
				x = [False]*20
				x[groupAppendLayer-1] = True
				context.scene.layers = x
			
			#special cases, make another list for this? number of variants can vary..
			if name == "torch" or name == "Torch":
				util.bAppendLink(os.path.join(meshSwapPath,'Group'), name+".1", toLink)
				bpy.ops.object.delete()
				util.bAppendLink(os.path.join(meshSwapPath,'Group'), name+".2", toLink)
				bpy.ops.object.delete()
			util.bAppendLink(os.path.join(meshSwapPath,'Group'), name, toLink)
			bpy.ops.object.delete()
			grouped = True
			# if activated a different layer, go back to the original ones
			context.scene.layers = activeLayers
			grouped = True
			# set properties
			for item in bpy.data.groups[name].items():
				if conf.v:print("GROUP PROPS:",item)
				try:
					x = item[1].name #will NOT work if property UI
				except:
					x = item[0] # the name of the property, [1] is the value
					if x=='variance':
						variance = [tmpName,item[1]]
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
		elif groupSwap:
			# ie already have a local group, so continue but don't import anything
			grouped = True
			#set properties
			for item in bpy.data.groups[name].items():
				try:
					x = item[1].name #will NOT work if property UI
				except:
					x = item[0] # the name of the property, [1] is the value
					if x=='variance':
						variance = [tmpName,item[1]]
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
			util.bAppendLink(os.path.join(meshSwapPath,'Object'),name, False)
			### NOTICE: IF THERE IS A DISCREPENCY BETWEEN ASSETS FILE AND WHAT IT SAYS SHOULD
			### BE IN FILE, EG NAME OF MESH TO SWAP CHANGED,  INDEX ERROR IS THROWN HERE
			### >> MAKE a more graceful error indication.
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
						variance = [True,item[1]]
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
			bpy.ops.object.select_all(action='DESELECT')
		##### HERE set the other properties, e.g. variance and edgefloat, now that the obj exists
		if conf.v:print("groupSwap: ",groupSwap,"meshSwap: ",meshSwap)
		if conf.v:print("edgeFloat: ",edgeFloat,", variance: ",variance,", torchlike: ",torchlike)
		return {'meshSwap':meshSwap, 'groupSwap':groupSwap,'variance':variance,
				'edgeFlush':edgeFlush,'edgeFloat':edgeFloat,'torchlike':torchlike,
				'removable':removable,'object':importedObj,'doorlike':doorlike}

	def offsetByHalf(self,obj):
		if obj.type != 'MESH': return
		# bpy.ops.object.mode_set(mode='OBJECT')
		if conf.v:print("doing offset")
		# bpy.ops.mesh.select_all(action='DESELECT')
		active = bpy.context.active_object #preserve current active
		bpy.context.scene.objects.active  = obj
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.transform.translate(value=(0.5, 0.5, 0.5))
		bpy.ops.object.mode_set(mode='OBJECT')
		obj.location[0] -= .5
		obj.location[1] -= .5
		obj.location[2] -= .5
		bpy.context.scene.objects.active = active


	def execute(self, context):

		# 
		tracking.trackUsage("meshswap",None)

		runcount = 0 # counter.. if zero by end, raise error that no selected objects matched
		## debug, restart check
		if conf.v:print('###################################')
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		# if checkOptin():usageStat('meshSwap'+':'+addon_prefs.MCprep_exporter_type)
		direc = context.scene.meshswap_path
		
		#check library file exists
		if not os.path.isfile(direc):
			#extract actual path from the relative one if relative, e.g. //file.blend
			direc = bpy.path.abspath(direc)
			#bpy.ops.object.dialogue('INVOKE_DEFAULT') # DOES work! but less streamlined
			if not os.path.isfile(direc):
				self.report({'ERROR'}, "Mesh swap blend file not found!") # better, actual "error"
				return {'CANCELLED'}
		
		# get some scene information
		toLink = False #context.scene.MCprep_linkGroup
		groupAppendLayer = self.append_layer
		activeLayers = list(context.scene.layers) ## NEED TO BE PASSED INTO the thing.
		# along with the scene name
		doOffset = (addon_prefs.MCprep_exporter_type == "Mineways")
		#separate each material into a separate object
		#is this good practice? not sure what's better though
		# could also recombine similar materials here, so happens just once.
		selList = context.selected_objects
		for obj in selList:
			try: bpy.ops.object.convert(target='MESH')
			except: pass
			bpy.ops.mesh.separate(type='MATERIAL')
		# now do type checking and fix any name discrepencies
		objList = []
		for obj in selList:
			#ignore non mesh selected objects or objs labeled to not double swap
			if obj.type != 'MESH' or ("MCprep_noSwap" in obj): continue
			if obj.active_material == None: continue
			obj.data.name = obj.active_material.name
			obj.name = obj.active_material.name
			objList.append(obj) 

		#listData = self.getListData() # legacy, no longer doing this
		# global scale, WIP
		gScale = 1
		# faces = []
		# for ob in objList:
		# 	for poly in ob.data.polygons.values():
		# 		faces.append(poly)
		# # gScale = estimateScale(objList[0].data.polygons.values())
		# gScale = estimateScale(faces)
		if conf.v: print("Using scale: ", gScale)
		if conf.v:print(objList)

		#primary loop, for each OBJECT needing swapping
		for swap in objList:
			swapGen = util.nameGeneralize(swap.name)
			if conf.v:print("Simplified name: {x}".format(x=swapGen))
			swapProps = self.checkExternal(context,swapGen) # IMPORTS, gets lists properties, etc
			if swapProps == False: # error happened in swapProps, e.g. not a mesh or something
				continue
			#special cases, for "extra" mesh pieces we don't want around afterwards
			if swapProps['removable']:
				bpy.ops.object.select_all(action='DESELECT')
				swap.select = True
				bpy.ops.object.delete()
				continue
			#just selecting mesh with same name accordinly.. ALSO only if in objList
			if not (swapProps['meshSwap'] or swapProps['groupSwap']): continue
			if conf.v: print("Swapping '{x}', simplified name '{y}".format(x=swap.name, y=swapGen))
			# if mineways/necessary, offset mesh by a half. Do it on a per object basis.
			if doOffset:
				self.offsetByHalf(swap)
				# try:offsetByHalf(swap)
				# except: print("ERROR in offsetByHalf, verify swapped meshes for ",swap.name)

			worldMatrix = swap.matrix_world.copy() #set once per object
			polyList = swap.data.polygons.values() #returns LIST of faces.
			#print(len(polyList)) # DON'T USE POLYLIST AFTER AFFECTING THE MESH
			for poly in range(len(polyList)):
				swap.data.polygons[poly].select = False
			#loop through each face or "polygon" of mesh
			facebook = [] #what? it's where I store the information of the obj's faces..
			for polyIndex in range(0,len(polyList)):
				gtmp = swap.matrix_world*mathutils.Vector(swap.data.polygons[polyIndex].center)
				g = [gtmp[0],gtmp[1],gtmp[2]]
				n = swap.data.polygons[polyIndex].normal
				tmp2 = swap.data.polygons[polyIndex].center
				l = [tmp2[0],tmp2[1],tmp2[2]] #to make value unlinked to mesh
				if swap.data.polygons[polyIndex].area < 0.016 and swap.data.polygons[polyIndex].area > 0.015:
					continue # hack for not having too many torches show up, both jmc2obj and Mineways
				facebook.append([n,g,l]) # g is global, l is local
			bpy.ops.object.select_all(action='DESELECT')
			
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
				if conf.v:print(" DUPLIST: ")
				if conf.v:print([x,y,z], [facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])
				
				### START HACK PATCH, FOR MINEWAYS double-tall adding
				# prevent double high grass... which mineways names sunflowers.
				overwrite = 0 # 0 means normal, -1 means skip, 1 means overwrite the one below
				if ([x,y-1,z] in dupList) and swapGen in ["Sunflower","Iron_Door","Wooden_Door"]:
					overwrite = -1
				elif ([x,y+1,z] in dupList) and swapGen in ["Sunflower","Iron_Door","Wooden_Door"]:
					dupList[ dupList.index([x,y+1,z]) ] = [x,y,z]
					overwrite = -1
				### END HACK PATCH

				# rotation value (second append value: 0 means nothing, rest 1-4.
				if ((not [x,y,z] in dupList) or (swapProps['edgeFloat'])) and overwrite >=0:
					# append location
					dupList.append([x,y,z])
					# check differece from rounding, this gets us the rotation!
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
						if conf.v:print("checking:",x_diff,z_diff)
						if swapProps['torchlike']: # needs fixing
							if conf.v:print("recognized it's a torchlike obj..")
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
			if conf.v:print("### > trans")
			bpy.ops.object.select_all(action='DESELECT')
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
					bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

				
				loc = swap.matrix_world*mathutils.Vector(set) #local to global
				if grouped:
					# definition for randimization, defined at top!
					randGroup = util.randomizeMeshSawp(swapGen,3)
					
					# The built in method fails, bpy.ops.object.group_instance_add(...)
					#UPDATE: I reported the bug, and they fixed it nearly instantly =D
					# but it was recommended to do the below anyways.
					util.addGroupInstance(randGroup,loc)
					
				else:
					#sets location of current selection, imported object or group from above
					base.select = True		# select the base object # UPDATE: THIS IS THE swapProps.object
					bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
					bpy.context.selected_objects[-1].location = mathutils.Vector(loc)
					# next line hackish....
					dupedObj.append(bpy.context.selected_objects[-1])
					base.select = False
				
				#still hackish
				obj = bpy.context.selected_objects[-1]	
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
				bpy.ops.object.select_all(action='DESELECT')
			
			### END CRITICAL SECTION
				
			if not grouped:
				base.select = True
				bpy.ops.object.delete() # the original copy used for duplication
			
			#join meshes together
			if not grouped and (len(dupedObj) >0) and self.meshswap_join:
				#print(len(dupedObj))
				# ERROR HERE if don't do the len(dupedObj) thing.
				bpy.context.scene.objects.active = dupedObj[0]
				for d in dupedObj:
					d.select = True
				
				bpy.ops.object.join()
			
			bpy.ops.object.select_all(action='DESELECT')
			swap.select = True
			bpy.ops.object.delete()
			
			#Try to reselect everything that was selected previoulsy + new objects
			for d in dupedObj:
				try:
					d.select = True # if this works, then..
					selList.append(d)
				except:
					pass
			bpy.ops.object.select_all(action='DESELECT')

		# final reselection
		for d in selList:
			try:
				d.select = True
			except:
				pass
		
		if runcount==0:
			self.report({'ERROR'}, "Nothing swapped, likely no materials of selected objects match the meshswap file objects/groups")
		elif runcount==1:
			self.report({'INFO'}, "Swapped 1 object")
		else:
			self.report({'INFO'}, "Swapped {x} objects".format(x=runcount))

		return {'FINISHED'}



class fixMinewaysScale(bpy.types.Operator):
	"""Quick upscaling of Mineways import by 10 for meshswapping"""
	bl_idname = "object.fixmeshswapsize"
	bl_label = "Mineways quick upscale"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		if conf.v:print("Attempting to fix Mineways scaling for meshswap")
		# get cursor loc first? shouldn't matter which mode/location though
		tmp = bpy.context.space_data.pivot_point
		tmpLoc = bpy.context.space_data.cursor_location
		bpy.context.space_data.pivot_point = 'CURSOR'
		bpy.context.space_data.cursor_location[0] = 0
		bpy.context.space_data.cursor_location[1] = 0
		bpy.context.space_data.cursor_location[2] = 0

		# do estimates, default / preference to 10/.1 should be made though!
		#estimateScale(faces):

		bpy.ops.transform.resize(value=(10, 10, 10))
		bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
		# bpy.ops.transform.resize(value=(.1, .1, .1))
		#bpy.ops.object.select_all(action='DESELECT')
		bpy.context.space_data.pivot_point = tmp
		bpy.context.space_data.cursor_location = tmpLoc
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Above for class functions/operators
#	Below for UI/register
# -----------------------------------------------------------------------------


# for asset listing
class ListColl(bpy.types.PropertyGroup):
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()


def register():
	bpy.types.Scene.mcprep_meshswap_list = \
			bpy.props.CollectionProperty(type=ListColl)
	bpy.types.Scene.mcprep_meshswap_list_index = bpy.props.IntProperty(default=0)


def unregister():
	del bpy.types.Scene.mcprep_meshswap_list
	del bpy.types.Scene.mcprep_meshswap_list_index

