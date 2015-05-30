# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2014 Mikhail Rachinskiy
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

"""
This code is open source under the MIT license.
Its purpose is to increase the workflow of creating Minecraft
related renders and animations, by automating certain tasks.

Developed and tested for blender 2.72 up to the indicated bledner version below

The addon must be installed as a ZIP folder, not an individual python script.

Source code available on github as well as more information:
https://github.com/TheDuckCow/MCprep.git

"""

########
bl_info = {
	"name": "MCprep",
	"category": "Object",
	"version": (2, 0, 0),
	"blender": (2, 74, 0),
	"location": "3D window toolshelf > Tools tab",
	"description": "Speeds up the workflow of minecraft animations and imported minecraft worlds",
	"warning": "",
	"wiki_url": "https://github.com/TheDuckCow/MCprep",
	"author": "Patrick W. Crawford <theduckcow@live.com>",
	"tracker_url":"https://github.com/TheDuckCow/MCprep/issues"
}

import bpy,os,mathutils,random,math
from bpy.types import AddonPreferences

#verbose
v = True 
#v = False
importedMats = False

########################################################################################
#	Below for precursor functions
#	Thereafter for the class functions
########################################################################################

########
# check if a face is on the boundary between two blocks (local coordinates)
def onEdge(faceLoc):
	strLoc = [ str(faceLoc[0]).split('.')[1][0],
				str(faceLoc[1]).split('.')[1][0],
				str(faceLoc[2]).split('.')[1][0] ]
	if (strLoc[0] == '5' or strLoc[1] == '5' or strLoc[2] == '5'):
		return True
	else:
		return False


########
# randomization for model imports, add extra statements for exta cases
def randomizeMeshSawp(swap,variations):
	randi=''
	if swap == 'torch':
		randomized = random.randint(0,variations-1)
		#print("## "+str(randomized))
		if randomized != 0: randi = ".{x}".format(x=randomized)
	return swap+randi


########
# strips out duplication naming ".001", ".002" from a name
def nameGeneralize(name):
	nameList = name.split(".")
	#check last item in list, to see if numeric type e.g. from .001
	try:
		x = int(nameList[-1])
		name = nameList[0]
		for a in nameList[1:-1]: name+='.'+a
	except:
		pass
	return name


########
# gets all materials on input list of objects
def getObjectMaterials(objList):
	matList = []
	#loop over every object, adding each material if not alraedy added
	for obj in objList:
		#must be a mesh, e.g. lamps or cameras don't have 'materials'
		if obj.type != 'MESH': continue
		objectsMaterials = obj.material_slots
		for materialID in objectsMaterials:
			if materialID.material not in matList:
				matList.append(materialID.material)
	return matList


########
# gets all textures on input list of materials
# currently not used, some issue in getting NoneTypes (line if textureID.texture in..)
def getMaterialTextures(matList):
	if len(matList)==0: return []
	texList = []
	# loop over every material, adding each texture slot
	for mat in matList:
		materialTextures = mat.texture_slots
		#print("###",materialTextures)
		if len(materialTextures)==0: return []
		for textureID in materialTextures:
			if textureID.texture not in texList:
				texList.append(textureID.texture)
	return texList


########
# For multiple version compatibility,
# this function generalized appending/linking
def bAppendLink(directory,name, toLink):
	# blender post 2.71 changed to new append/link methods
	post272 = False
	try:
		version = bpy.data.version
		post272 = True
	except:
		pass #  "version" didn't exist before 72!
	#if (version[0] >= 2 and version[1] >= 72):
	if post272:
		# NEW method of importing
		if (toLink):
			bpy.ops.wm.link(directory=directory, filename=name)
		else:
			bpy.ops.wm.append(directory=directory, filename=name)
	else:
		# OLD method of importing
		bpy.ops.wm.link_append(directory=directory, filename=name, link=toLink)
	

########
# If scale isn't set, try to guess the scale of the world
# being meshswapped. Default is 1x1x1 m blocks, as in meshwap files.
def estimateScale(faces):
	global v

	scale = 1
	# Consider only sending a subset of all the faces, not many should be needed
	# hash count, make a list where each entry is [ area count, number matched ]
	guessList = []
	countList = []
	# iterate over all faces
	for face in faces:
		n = face.normal
		if not (abs(n[0]) == 0 or abs(n[0]) == 1):
			continue #catches any faces not flat or angled slightly

		# ideally throw out/cancel also if the face isn't square.
		a = face.area 	# shouldn't do area, but do height of a single face....
		if a not in guessList:
			guessList.append(a)
			countList.append(1)
		else:
			countList[guessList.index(a)] += 1
	if v:
		for a in range(len(guessList)): print(guessList[a], countList[a])
	return guessList[ countList.index(max(countList)) ]


########################################################################################
#	Above for precursor functions
#	Below for the class functions
########################################################################################

########
# Operator, sets up the materials for better Blender Internal rendering
class materialChange(bpy.types.Operator):
	"""Preps selected minecraft materials"""
	bl_idname = "object.mc_mat_change"
	bl_label = "MCprep mats"
	bl_options = {'REGISTER', 'UNDO'}
	

	def getListDataMats(self):
		global importedMats

		reflective = [ 'glass', 'glass_pane_side','ice','ice_packed','iron_bars']
		water = ['water','water_flowing']
		# things are transparent by default to be safe, but if something is solid it is much
		# better to make it solid (faster render and build times)
		solid = ['sand','dirt','dirt_grass_side','dirt_grass_top','dispenser_front','furnace_top',
				'redstone_block','gold_block','yourFace','stone','iron_ore','coal_ore',
				'stone_brick']
		emit= ['redstone_block','redstone_lamp_on','glowstone','lava','lava_flowing','fire']

		######## CHANGE TO MATERIALS LIBRARY
		# if v and not importedMats:print("Parsing library file for materials")
		# #attempt to LOAD information from an asset file...
		# matLibPath = bpy.context.scene.MCprep_material_path
		# if not(os.path.isfile(matLibPath)):
		# 	#extract actual path from the relative one
		# 	matLibPath = bpy.path.abspath(matLibPath)

		# WHAT IT SHOULD DO: check the NAME of the current material,
		# and ONLY import that one if it's there. maybe split this into another function
		# imported mats is a bool so we only attempt to load one time instead of like fifty.
		
		"""
		# commeting this out beacuse of excessive imports
		if (os.path.isfile(matLibPath)) and not importedMats:
			importedMats = True
			if v:print("Material library found, reading in")
			with bpy.data.libraries.load(matLibPath) as (data_from, data_to):
				data_to.materials = data_from.materials
		"""
			# now go through the new materials and change them for the old...?


		return {'reflective':reflective, 'water':water, 'solid':solid,
				'emit':emit}
	
	## HERE functions for GENERAL material setup (cycles and BI)
	def materialsInternal(self, mat):
		global v

		# defines lists for materials with special default settings.
		listData = self.getListDataMats()
		
		try:
			newName = mat.name+'_tex' # add exception to skip? with warning?
			texList = mat.texture_slots.values()
		except:
			if v:print('\tissue: '+obj.name+' has no active material')
			return
	   
		### Check material texture exists and set name
		try:
			bpy.data.textures[texList[0].name].name = newName
		except:
			if v:print('\tiwarning: material '+mat.name+' has no texture slot. skipping...')
			return

		# disable all but first slot, ensure first slot enabled
		mat.use_textures[0] = True
		for index in range(1,len(texList)):
			mat.use_textures[index] = False
	   
		#generalizing the name, so that lava.001 material is recognized and given emit
		matGen = nameGeneralize(mat.name)
		mat.use_nodes = False
	   
		mat.use_transparent_shadows = True #all materials receive trans
		mat.specular_intensity = 0
		mat.texture_slots[0].texture.use_interpolation = False
		mat.texture_slots[0].texture.filter_type = 'BOX'
		mat.texture_slots[0].texture.filter_size = 0
		mat.texture_slots[0].use_map_color_diffuse = True
		mat.texture_slots[0].diffuse_color_factor = 1
		mat.use_textures[1] = False

		if not matGen in listData['solid']: #ie alpha is on unless turned off
			bpy.data.textures[newName].use_alpha = True
			mat.texture_slots[0].use_map_alpha = True
			mat.use_transparency = True
			mat.alpha = 0
			mat.texture_slots[0].alpha_factor = 1
		   
		if matGen in listData['reflective']:
			mat.alpha=0.3
			mat.raytrace_mirror.use = True
			mat.raytrace_mirror.reflect_factor = 0.3
	   
		if matGen in listData['emit']:
			mat.emit = 1
		else:
			mat.emit = 0

	### Function for default cycles materials
	def materialsCycles(self, mat):

		# get the texture, but will fail if NoneType
		try:
			imageTex = mat.texture_slots[0].texture.image
		except:
			return
		matGen = nameGeneralize(mat.name)
		listData = self.getListDataMats()

		#enable nodes
		mat.use_nodes = True
		nodes = mat.node_tree.nodes
		links = mat.node_tree.links
		nodes.clear()
		nodeDiff = nodes.new('ShaderNodeBsdfDiffuse')
		nodeGloss = nodes.new('ShaderNodeBsdfGlossy')
		nodeTrans = nodes.new('ShaderNodeBsdfTransparent')
		nodeMix1 = nodes.new('ShaderNodeMixShader')
		nodeMix2 = nodes.new('ShaderNodeMixShader')
		nodeTex = nodes.new('ShaderNodeTexImage')
		nodeOut = nodes.new('ShaderNodeOutputMaterial')
		
		# set location and connect
		nodeTex.location = (-400,0)
		nodeGloss.location = (0,-150)
		nodeDiff.location = (-200,-150)
		nodeTrans.location = (-200,0)
		nodeMix1.location = (0,0)
		nodeMix2.location = (200,0)
		nodeOut.location = (400,0)
		links.new(nodeTex.outputs["Color"],nodeDiff.inputs[0])
		links.new(nodeDiff.outputs["BSDF"],nodeMix1.inputs[2])
		links.new(nodeTex.outputs["Alpha"],nodeMix1.inputs[0])
		links.new(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
		links.new(nodeGloss.outputs["BSDF"],nodeMix2.inputs[2])
		links.new(nodeMix1.outputs["Shader"],nodeMix2.inputs[1])
		links.new(nodeMix2.outputs["Shader"],nodeOut.inputs[0])
		nodeTex.image = imageTex
		nodeTex.interpolation = 'Closest'

		#set other default values, e.g. the mixes
		nodeMix2.inputs[0].default_value = 0 # factor mix with glossy
		nodeGloss.inputs[1].default_value = 0.1 # roughness

		# the above are all default nodes. Now see if in specific lists
		if matGen in listData['reflective']:
			nodeMix2.inputs[0].default_value = 0.2  # mix factor
			nodeGloss.inputs[1].default_value = 0.01 # roughness
		if matGen in listData['emit']:
			# add an emit node, insert it before the first mix node
			nodeMixEmitDiff = nodes.new('ShaderNodeMixShader')
			nodeEmit = nodes.new('ShaderNodeEmission')
			nodeEmit.location = (-400,-150)
			nodeMixEmitDiff.location = (-200,-150)
			nodeDiff.location = (-400,0)
			nodeTex.location = (-600,0)

			links.new(nodeTex.outputs["Color"],nodeEmit.inputs[0])
			links.new(nodeDiff.outputs["BSDF"],nodeMixEmitDiff.inputs[1])
			links.new(nodeEmit.outputs["Emission"],nodeMixEmitDiff.inputs[2])
			links.new(nodeMixEmitDiff.outputs["Shader"],nodeMix1.inputs[2])

			nodeMixEmitDiff.inputs[0].default_value = 0.9
			nodeEmit.inputs[1].default_value = 2.5
			# emit value
		if matGen in listData['water']:
			# setup the animation??
			nodeMix2.inputs[0].default_value = 0.2
			nodeGloss.inputs[1].default_value = 0.01 # copy of reflective for now
		if matGen in listData['solid']:
			#links.remove(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
			## ^ need to get right format to remove link, need link object, not endpoints
			nodeMix1.inputs[0].default_value = 0 # no transparency
	
	
	def execute(self, context):
		global importedMats
		#get list of selected objects
		objList = context.selected_objects
		# gets the list of materials (without repetition) in the selected object list
		matList = getObjectMaterials(objList)
		# set to false so it will import
		importedMats = False
		#check if linked material exists
		render_engine = bpy.context.scene.render.engine

		for mat in matList:
			#if linked false:
			if (True):
				if (render_engine == 'BLENDER_RENDER'):
					#print('BI mat')
					self.materialsInternal(mat)
				elif (render_engine == 'CYCLES'):
					#print('cycles mat')
					self.materialsCycles(mat)
			else:
				if v:print('Get the linked material instead!')
		# reset it so it can check for reimport again if necessary
		importedMats = False
		return {'FINISHED'}


########
# Operator, funtion swaps meshes/groups from library file
class meshSwap(bpy.types.Operator):
	"""Swap minecraft imports for custom 3D models in the meshSwap blend file"""
	bl_idname = "object.mc_meshswap"
	bl_label = "MCprep meshSwap"
	bl_options = {'REGISTER', 'UNDO'}
	
	#used for only occasionally refreshing the 3D scene while mesh swapping
	counterObject = 0	# used in count
	countMax = 5		# count compared to this, frequency of refresh (number of objs)

	def getListData(self):
		global v

		##### lists for meshSwap
		added = [] # list for checking if item added to lists yet or not
		groupSwapList = []
		## if same object type is in both group and mesh swap list, group will be used
		meshSwapList = []
		edgeFlush = [] # blocks perfectly on edges, require rotation	
		edgeFloat = [] # floating off edge into air, require rotation ['vines','ladder','lilypad']
		torchlike = [] # ['torch','redstone_torch_on','redstone_torch_off']
		#remove meshes not used for processing, for objects imported with extra meshes
		# below is still hardcoded!
		removable = ['double_plant_grass_top','torch_flame']
		# for varied positions from exactly center on the block, 1 for Z random too
		# 1= x,y,z random; 0= only x,y random; 2=rotation random only (vertical)
		#variance = [ ['tall_grass',1], ['double_plant_grass_bottom',1],
		#			['flower_yellow',0], ['flower_red',0] ]
		variance = []
		
		########
		if v:print("Parsing library files")
		
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		meshSwapPath = addon_prefs.jmc2obj_swap
		if bpy.context.scene.MCprep_exporter_type == "Mineways":
			meshSwapPath = addon_prefs.mineways_swap
		if not os.path.isfile(meshSwapPath):
			#extract actual path from the relative one if relative, e.g. //file.blend
			meshSwapPath = bpy.path.abspath(meshSwapPath)

		# this auto links every group, not just the ones we need!!!
		with bpy.data.libraries.load(meshSwapPath) as (data_from, data_to):
			data_to.objects = data_from.objects
			data_to.groups = data_from.groups
			
		# now operate directly on the loaded data
		# start with groups
		for group in data_from.groups:
			if group is not None:

				# check if the group already exists here!
				groupSwapList.append(group.name)
				added.append(group.name)	
				
				# here check properties for which additional category to put it in
				for item in group.items():
					try:
						x = item[1].name #will NOT work if property UI
						#continue
					except:
						tmpName = group.name
						x = item[0] # the name of the property, [1] is the value
						if x=='variance':
							variance.append([tmpName,item[1]])
						elif x=='edgeFloat':
							edgeFloat.append(tmpName)
						elif x=='edgeFlush':
							edgeFlush.append(tmpName)
						elif x=='torchlike':
							torchlike.append(tmpName)
						elif x=='removable':
							removable.append(tmpName)
		
		# now add the objects
		for object in data_from.objects:
			if object is not None and len(object.users_group) ==0 and object.type == "MESH":
				tmpName = nameGeneralize(object.name) #not ideal! but the name instance meshes..
				meshSwapList.append(tmpName)
				added.append(tmpName)
				
				# here check properties for which additional category to put it in
				for item in object.items():
					try:
						x = item[1].name #will NOT work if property UI
						#continue
					except:
						x = item[0] # the name of the property, [1] is the value
						if x=='variance':
							variance.append([tmpName,item[1]])
						elif x=='edgeFloat':
							edgeFloat.append(tmpName)
						elif x=='edgeFlush':
							edgeFlush.append(tmpName)
						elif x=='torchlike':
							torchlike.append(tmpName)
						elif x=='removable':
							removable.append(tmpName)
		
		#print("#: ",meshSwapPath)
		if v:print("groupSwapList: ",groupSwapList)
		if v:print("meshSwapList: ",meshSwapList)
		if v:print("edgeFloat: ",edgeFloat,", variance: ",variance,", torchlike: ",torchlike)
		
		return {'meshSwapList':meshSwapList, 'groupSwapList':groupSwapList,
				'variance':variance, 'edgeFlush':edgeFlush,
				'edgeFloat':edgeFloat,'torchlike':torchlike,'removable':removable}


	########
	# add object instance not working, so workaround function:
	def addGroupInstance(self,groupName,loc):
		scene = bpy.context.scene
		ob = bpy.data.objects.new(groupName, None)
		ob.dupli_type = 'GROUP'
		ob.dupli_group = bpy.data.groups.get(groupName)
		ob.location = loc
		scene.objects.link(ob)
		ob.select = True


	def offsetByHalf(self,obj):
		if obj.type != 'MESH': return
		bpy.ops.object.mode_set(mode='OBJECT')
		active = bpy.context.active_object
		bpy.context.scene.objects.active  = obj
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.transform.translate(value=(0.5, 0.5, 0.5))
		bpy.ops.object.mode_set(mode='OBJECT')
		obj.location[0] -= .5
		obj.location[1] -= .5
		obj.location[2] -= .5
		bpy.context.scene.objects.active  = active


	def execute(self, context):
		global v
		## debug, restart check
		if v:print('###################################')
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

		direc = addon_prefs.jmc2obj_swap
		if bpy.context.scene.MCprep_exporter_type == "Mineways":
			direc = addon_prefs.mineways_swap
		
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
		groupAppendLayer = context.scene.MCprep_groupAppendLayer
		activeLayers = list(context.scene.layers)
		doOffset = (bpy.context.scene.MCprep_exporter_type == "Mineways")
		
		#separate each material into a separate object
		#is this good practice? not sure what's better though
		# could also recombine similar materials here, so happens just once.
		selList = context.selected_objects
		for obj in selList:
			try: bpy.ops.object.convert(target='MESH')
			except: pass
			bpy.ops.mesh.separate(type='MATERIAL')
		
		# now do type checking and fix any name discrepencies
		objList = context.selected_objects
		objList = []
		for obj in selList:
			#ignore non mesh selected objects or objs labeled to not double swap
			if obj.type != 'MESH' or ("MCprep_noSwap" in obj): continue
			if obj.active_material == None: continue
			obj.data.name = obj.active_material.name
			obj.name = obj.active_material.name
			objList.append(obj) # redundant, should just make it the same list as before

		# Now get a list of all objects in this blend file, and all groups
		listData = self.getListData()

		# global scale, WIP
		gScale = 1
		# faces = []
		# for ob in objList:
		# 	for poly in ob.data.polygons.values():
		# 		faces.append(poly)

		# # gScale = estimateScale(objList[0].data.polygons.values())
		# gScale = estimateScale(faces)
		if v: print("Using scale: ", gScale)
		print(objList)

		#primary loop, for each OBJECT needing swapping
		for swap in objList:
			
			#first check if swap has already happened: // not doing that yet
			# generalize name to do work on duplicated meshes, but keep original
			swapGen = nameGeneralize(swap.name)
			
			#special cases, for "extra" mesh pieces we don't want around afterwards
			if swapGen in listData['removable']:
				bpy.ops.object.select_all(action='DESELECT')
				swap.select = True
				bpy.ops.object.delete()
				continue
			
			#just selecting mesh with same name accordinly.. ALSO only if in objList
			if not (swapGen in listData['meshSwapList'] or swapGen in listData['groupSwapList']): continue
			if v: print("Swapping '{x}', simplified name '{y}".format(x=swap.name, y=swapGen))
			
			# if mineways/necessary, offset mesh by a half. Do it on a per object basis.
			if doOffset:
				try:offsetByHalf(swap)
				except: print("ERROR in offsetByHalf, verify swapped meshes for ",swap.name)


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
				n = swap.data.polygons[polyIndex].normal #currently not used!
				tmp2 = swap.data.polygons[polyIndex].center
				l = [tmp2[0],tmp2[1],tmp2[2]] #to make value unlinked to mesh
				facebook.append([n,g,l]) # g is global, l is local
			bpy.ops.object.select_all(action='DESELECT')

			"""
			August 4, 2014 - 1:51 am
			R.I.P. the bug that plagued my aniamtions since the dawn of this addon.
			
			This bug lived a long life, it went many places - and saw many imported worlds.
			And while it may have seemed to exist soley for the purpose of my demise, it was
			a test of my character, and through it I have grown stronger and wiser.
			
			The original line, which caused this issue that needed only commenting out to fix:
				
				bpy.ops.object.delete() #Hey! The values of facebook are unchanged, so it's NOT linked..?
			
			Note how I had even questioned the deletion of this object when first written, but found it
			strange that the values linked to it remained unchanged given the objects absence.
			
			As I now understand, blender has an internal memory garbage collector, and sometimes it
			takes shorter or longer for deleted obejct data to be removed from the gargage. And hence,
			the variance in being how long it took before the meshSwap object ob.worldMatrix many
			lines hereafter would go awry, for at the point where meshes began to transoform in odd
			ways, the original object had finally, and truly, been removed.
			
			Also, note to self: this function is still a hell of a mess. Do something about it.
			"""
			
			# removing duplicates and checking orientation
			dupList = []	#where actual blocks are to be added
			rotList = []	#rotation of blocks

			for setNum in range(0,len(facebook)):
				# LOCAL coordinates!!!
				x = round(facebook[setNum][2][0]) #since center's are half ints.. 
				y = round(facebook[setNum][2][1]) #don't need (+0.5) -.5 structure
				z = round(facebook[setNum][2][2])
				
				outsideBool = -1
				if (swapGen in listData['edgeFloat']): outsideBool = 1
				
				if onEdge(facebook[setNum][2]): #check if face is on unit block boundary (local coord!)
					a = facebook[setNum][0][0] * 0.4 * outsideBool #x normal
					b = facebook[setNum][0][1] * 0.4 * outsideBool #y normal
					c = facebook[setNum][0][2] * 0.4 * outsideBool #z normal
					x = round(facebook[setNum][2][0]+a) 
					y = round(facebook[setNum][2][1]+b)
					z = round(facebook[setNum][2][2]+c)
					#print("ON EDGE, BRO! line ~468, "+str(x) +","+str(y)+","+str(z)+", ")
					#print([facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])	
				
				#### TORCHES, hack removes duplicates while not removing "edge" floats
				if facebook[setNum][2][1]+0.5 - math.floor(facebook[setNum][2][1]+0.5) < 0.3:
					#continue if coord. is < 1/3 of block height, to do with torch's base in wrong cube.
					if swapGen not in listData['edgeFloat']:
						#continue
						print("do nothing, this is for jmc2obj")	
				if v:print(" DUPLIST: ")
				if v:print([x,y,z], [facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])
				
				# rotation value (second append value: 0 means nothing, rest 1-4.
				if (not [x,y,z] in dupList) or (swapGen in listData['edgeFloat']):
					# append location
					dupList.append([x,y,z])
					
					# check differece from rounding, this gets us the rotation!
					x_diff = x-facebook[setNum][2][0]
					#print(facebook[setNum][2][0],x,x_diff)
					z_diff = z-facebook[setNum][2][2]
					#print(facebook[setNum][2][2],z,z_diff)
					
					# append rotation
					if swapGen in listData['torchlike']: # needs fixing
						if (x_diff>.2 and x_diff < 0.3):
							rotList.append(1)
						elif (z_diff>.2 and z_diff < 0.3):	
							rotList.append(2)
						elif (x_diff<-.2 and x_diff > -0.3):	
							rotList.append(3)
						elif (z_diff<-.2 and z_diff > -0.3):
							rotList.append(4)
						else:
							rotList.append(0)
					elif swapGen in listData['edgeFloat']:
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
					elif swapGen in listData['edgeFlush']:
						# actually 6 cases here, can need rotation below...
						# currently not necessary/used, so not programmed..	 
						rotList.append(0)
					else:
						# no rotation from source file, must always append something
						rotList.append(0)
			
			#import: guaranteed to have same name as "appendObj" for the first instant afterwards
			grouped = False # used to check if to join or not
			base = None		# need to initialize to something, though this obj no used
			if swapGen in listData['groupSwapList']:
				
				if v:print(">> link group?",toLink,groupAppendLayer,swapGen)
				
				# GROUP LAYER APPENDING DOESN'T WORK CURRENTLY
				# if group not linked, put appended group data onto the GUI field layer
				if (not toLink) and (groupAppendLayer!=0):
					x = [False]*20
					x[groupAppendLayer-1] = True
					context.scene.layers = x
				
				#special cases, make another list for this? number of variants can vary..
				if swapGen == "torch":
					bAppendLink(direc+'/Group/', swapGen+".1", toLink)
					bpy.ops.object.delete()
					bAppendLink(direc+'/Group/', swapGen+".2", toLink)
					bpy.ops.object.delete()
				
				bAppendLink(direc+'/Group/', swapGen, toLink)
				
				bpy.ops.object.delete()
				grouped = True
				
				# if activated a different layer, go back to the original ones
				context.scene.layers = activeLayers
				
			else:
				
				bAppendLink(direc+'/Object/',swapGen, False)
				
				### NOTICE: IF THERE IS A DISCREPENCY BETWEEN ASSETS FILE AND WHAT IT SAYS SHOULD BE IN FILE
				### EG NAME OF MESH TO SWAP CHANGED,  INDEX ERROR IS THROWN HERE
				### >> MAKE a more graceful error indication.
				
				try:
					base = bpy.context.selected_objects[0]
				except:
					continue #in case nothing selected.. which happens even during selection?
				"""
				try:
					base = bpy.context.selected_objects[0]
					if base["MCprep_noSwap"] == "True":
						print("DID WE MAKE IT HERE")
						continue
				except:
					base["MCprep_noSwap"] = "True"
				"""
				base["MCprep_noSwap"] = "True"
				bpy.ops.object.select_all(action='DESELECT')

			
			##### OPTION HERE TO SEGMENT INTO NEW FUNCTION
			if v:print("### > trans")
			#self.counterObject = 0
			# duplicating, rotating and moving
			dupedObj = []
			for (set,rot) in zip(dupList,rotList):
				
				### HIGH COMPUTATION/CRITICAL SECTION
				#refresh the scene every once in awhile
				self.counterObject+=1
				if (self.counterObject > self.countMax):
					self.counterObject = 0
					#below technically a "hack", should use: bpy.data.scenes[0].update()
					bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

				
				loc = swap.matrix_world*mathutils.Vector(set) #local to global
				if grouped:
					# definition for randimization, defined at top!
					randGroup = randomizeMeshSawp(swapGen,3)
					
					# The built in method fails, bpy.ops.object.group_instance_add(...)
					#UPDATE: I reported the bug, and they fixed it nearly instantly =D
					# but it was recommended to do the below anyways.
					self.addGroupInstance(randGroup,loc)
					
				else:
					#sets location of current selection, imported object or group from above
					base.select = True		# select the base object
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
				if [swapGen,1] in listData['variance']:
					x = (random.random()-0.5)*0.5
					y = (random.random()-0.5)*0.5
					z = (random.random()/2-0.5)*0.6
					obj.location += mathutils.Vector((x, y, z))
				# now for just xy variance, base stays the same
				elif [swapGen,0] in listData['variance']: # for non-z variance
					x = (random.random()-0.5)*0.5	 # values LOWER than *1.0 make it less variable
					y = (random.random()-0.5)*0.5
					obj.location += mathutils.Vector((x, y, 0))
				bpy.ops.object.select_all(action='DESELECT')
			
			
			### END CRITICAL SECTION
				
			if not grouped:
				base.select = True
				bpy.ops.object.delete() # the original copy used for duplication
			
			
			#join meshes together
			if not grouped and (len(dupedObj) >0):
				#print(len(dupedObj))
				# ERROR HERE if don't do the len(dupedObj) thing.
				bpy.context.scene.objects.active = dupedObj[0]
				for d in dupedObj:
					d.select = True
				
				bpy.ops.object.join()
			
			bpy.ops.object.select_all(action='DESELECT')
			swap.select = True
			bpy.ops.object.delete()
			
			#deselect? or try to reselect everything that was selected previoulsy
			bpy.ops.object.select_all(action='DESELECT')
		
		return {'FINISHED'}


#######
# Class for spawning/proxying a new asset for animation
class solidifyPixels(bpy.types.Operator):
	"""Turns each pixel of active UV map/texture into a face -- WIP"""
	bl_idname = "object.solidify_pixels"
	bl_label = "Solidify Pixels"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		if v:print("hello world, solidify those pixels!")
		self.report({'ERROR'}, "Feature not implemented yet")
		return {'FINISHED'}


########################################################################################
#	Above for class functions/operators
#	Below for UI
########################################################################################



#######
# pop-up declaring some button is WIP still =D
class WIP(bpy.types.Menu):
	bl_label = "wip_warning"
	bl_idname = "view3D.wip_warning"

	# Set the menu operators and draw functions
	def draw(self, context):
		layout = self.layout
		row1 = layout.row()
		row1.label(text="This addon is a work in progress, this function is not yet implemented")  


#######
# preferences UI
class RenderMusicProperties(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	jmc2obj_swap = bpy.props.StringProperty(
		name = "jmc2obj_swap",
		description = "Asset file for jmc2obj imported worlds",
		subtype = 'FILE_PATH',
		default = scriptdir + "/mcprep_meshSwap_jmc2obj.blend")

	mineways_swap = bpy.props.StringProperty(
		name = "mineways_swap",
		description = "Asset file for Mineways imported worlds",
		subtype = 'FILE_PATH',
		default = scriptdir + "/mcprep_meshSwap_mineways.blend")

	mcprep_use_lib = bpy.props.BoolProperty(
		name = "Link meshswapped groups & materials",
		description = "Use library linking when meshswapping or material matching",
		default = False)

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.label("Meshswapping source asset files:")
		layout = layout.box()
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("jmc2obj assets")
		col.label("Mineways assets")
		col = split.column()
		col.prop(self, "jmc2obj_swap", text="")
		col.prop(self, "mineways_swap", text="")

		layout = self.layout
		split = layout.split()
		# col = split.column()
		# col.label(text="Link groups & materials")
		col = split.column()
		col.prop(self, "mcprep_use_lib")


#######
# MCprep panel for these declared tools
class MCpanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "MCprep Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = 'Tools'

	def draw(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		
		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		
		row = col.row(align=True)
		row.prop(context.scene,"MCprep_exporter_type", expand=True)

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		if context.scene.MCprep_exporter_type == "jmc2obj":
			row.label(text="Meshswap source:")
			row.prop(addon_prefs,"jmc2obj_swap",text="")
		elif context.scene.MCprep_exporter_type == "Mineways":
			row.label(text="Meshswap source:")
			row.prop(addon_prefs,"mineways_swap",text="")
		
		row = col.row(align=True)
		row.label(text="Materials blend")
		row.prop(addon_prefs,"MCprep_material_path",text="")
		#does nothing yet (correctly)
		#col.prop(context.scene,"MCprep_groupAppendLayer",text="")
		
		split = layout.split()
		col = split.column(align=True)
		#for setting MC materials and looking in library
		col.operator("object.mc_mat_change", text="Prep Materials", icon='MATERIAL')
		#below should actually just call a popup window
		col.operator("object.mc_meshswap", text="Mesh Swap", icon='LINK_BLEND')
		#col.prop(context.scene,"MCprep_export_type", expand=True)
		

		#the UV's pixels into actual 3D geometry (but same material, or modified to fit)
		#col.operator("object.solidify_pixels", text="Solidify Pixels", icon='MOD_SOLIDIFY')
		
		split = layout.split()
		col = split.column(align=True)
		# doesn't properly work yet
		#col.label(text="Link groups")
		#col.prop(context.scene,"MCprep_linkGroup")
		
		#user prefs quick access
		#col.operator("object.showprefs", text="User prefs", icon='PREFERENCES')


#######
# WIP OK button general purpose
class dialogue(bpy.types.Operator):
	bl_idname = "object.dialogue"
	bl_label = "dialogue"
	message = "Library error, check path to assets has the meshSwap blend"
	
	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)
		return {'FINISHED'}
	
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400, height=200)
		#return wm.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.label(self.message)


########################################################################################
#	Above for UI
#	Below for registration stuff
########################################################################################


def register():

	bpy.types.Scene.MCprep_groupAppendLayer = bpy.props.IntProperty(
		name="Group Append Layer",
		description="When groups are appended instead of linked, the objects part of the group will be palced in this layer, 0 means same as active layer, otherwise sets the the given layer number",
		min=0,
		max=20,
		default=20)
	bpy.types.Scene.MCprep_exporter_type = bpy.props.EnumProperty(
		items = [('jmc2obj', 'jmc2obj', 'Select if exporter used was jmc2obj'),
				('Mineways', 'Mineways', 'Select if exporter used was Mineways')],
		name = "Exporter")

	# classes
	bpy.utils.register_class(materialChange)
	bpy.utils.register_class(meshSwap)
	bpy.utils.register_class(solidifyPixels)
	
	
	bpy.utils.register_class(dialogue)
	bpy.utils.register_class(WIP)
	bpy.utils.register_class(MCpanel)
	bpy.utils.register_class(RenderMusicProperties)

	import urllib.request
	n = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html")
	print("register complete")


def unregister():
	bpy.utils.unregister_class(materialChange)
	bpy.utils.unregister_class(meshSwap)
	bpy.utils.unregister_class(solidifyPixels)
	
	bpy.utils.unregister_class(dialogue)
	bpy.utils.unregister_class(WIP)
	bpy.utils.unregister_class(MCpanel)
	bpy.utils.unregister_class(RenderMusicProperties)
	
	#properties
	del bpy.types.Scene.MCprep_meshswap_path
	del bpy.types.Scene.MCprep_material_path
	del bpy.types.Scene.MCprep_linkGroup
	del bpy.types.Scene.MCprep_groupAppendLayer
	del bpy.types.Scene.MCprep_export_type


if __name__ == "__main__":
	register()

