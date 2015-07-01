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
	"version": (2, 1, 0),
	"blender": (2, 74, 0),
	"location": "3D window toolshelf > Tools tab",
	"description": "Speeds up the workflow of minecraft animations and imported minecraft worlds",
	"warning": "",
	"wiki_url": "https://github.com/TheDuckCow/MCprep",
	"author": "Patrick W. Crawford <support@theduckcow.com>",
	"tracker_url":"https://github.com/TheDuckCow/MCprep/issues"
}

import bpy,os,mathutils,random,math
from bpy.types import AddonPreferences

#verbose
v = False
ver = 'v(2, 1, 0)'

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
	elif swap == 'Torch':
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



########
# Analytics functions
def install():
	vr = ver
	try:
		pydir = bpy.path.abspath(os.path.dirname(__file__))
		if os.path.isfile(pydir+"/optin") or os.path.isfile(pydir+"/optout"):
			# this means it has already installed once, don't count as another
			return
		else:
			f = open(pydir+"/optout", 'w') # make new file, empty
			f.close()
		import urllib.request
		d = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html",timeout=10).read().decode('utf-8')
		ks = d.split("<br>")
		ak = ks[1]
		rk = ks[2]
		import json,http.client
		connection = http.client.HTTPSConnection('api.parse.com', 443)
		connection.connect()
		d = ''
		if v:d="_dev"
		if v:vr+=' dev'
		connection.request('POST', '/1/classes/install'+d, json.dumps({
			   "version": vr,
			 }), {
				"X-Parse-Application-Id": ak,
				"X-Parse-REST-API-Key": rk,
				"Content-Type": "application/json"
			 })
		result = json.loads(   (connection.getresponse().read()).decode())
	except:
		# if v:print("Register connection failed/timed out")
		return

def usageStat(function):
	vr = ver
	if v:vr+=' dev'
	if v:print("Running USAGE STATS for: {x}".format(x=function))
	
	try:
		count = -1
		# first grab/increment the text file's count
		pydir = bpy.path.abspath(os.path.dirname(__file__))
		if os.path.isfile(pydir+"/optin"):
			f = open(pydir+"/optin", 'r')
			ln = f.read()
			f.close()
			# fcns = ln.split('\n')
			# for entry in fcns:
			if function in ln:
				if v:print("found function, checking num")
				i0 = ln.index(function)
				i = i0+len(function)+1
				start = ln[:i]
				if '\n' in ln[i:]:
					if v:print("not end of file")
					i2 = ln[i:].index('\n') # -1 or not?
					print("pre count++:"+ln[i:][:i2]+",{a} {b}".format(a=i,b=i2))
					count = int(ln[i:][:i2])+1
					if v:print("fnct count: "+str(count))
					ln = start+str(count)+ln[i:][i2:]
				else:
					if v:print("end of file adding")
					count = int(ln[i:])+1
					if v:print("fnt count: "+str(count))
					ln = start+str(count)+'\n'
				f = open(pydir+"/optin", 'w')
				f.write(ln)
				f.close()
			else:
				if v:print("adding function")
				count = 1
				ln+="{x}:1\n".format(x=function)
				f = open(pydir+"/optin", 'w')
				f.write(ln)
				f.close()


		import urllib.request

		d = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html",timeout=10).read().decode('utf-8')
		ks = d.split("<br>")
		ak = ks[1]
		rk = ks[2]
		import json,http.client
		connection = http.client.HTTPSConnection('api.parse.com', 443)
		connection.connect()
		d = ''
		if v:d="_dev"
		connection.request('POST', '/1/classes/usage'+d, json.dumps({
			   "function": function,
			   "version":vr,
			   "count": count, # -1 for not implemented yet/error
			 }), {
				"X-Parse-Application-Id": ak,
				"X-Parse-REST-API-Key": rk,
				"Content-Type": "application/json"
			 })
		result = json.loads(   (connection.getresponse().read()).decode())
		if v:print("Sent usage stat, returned: {x}".format(x=result))
	except:
		if v:print("Failed to send stat")
		return

def checkOptin():
	pydir = bpy.path.abspath(os.path.dirname(__file__))
	if os.path.isfile(pydir+"/optin"):
		return True
	else:
		return False

def tracking(set='disable'):
	if v:print("Setting the tracking file:")
	try:
		pydir = bpy.path.abspath(os.path.dirname(__file__))
		# print("pydir: {x}".format(x = pydir))

		if set=='disable' or set==False:
			if os.path.isfile(pydir+"/optout"):
				# print("already optout")
				return # already disabled
			elif os.path.isfile(pydir+"/optin"):
				os.rename(pydir+"/optin",pydir+"/optout")
				# print("renamed optin to optout")
			else:
				# f = open(pydir+"/optout.txt", 'w') # make new file, empty
				# f.close()
				# print("Created new optout file")
				# DON'T create a file.. only do this in the install script so it
				# knows if this has been enabeld before or not
				return
		elif set=='enable' or set==True:
			if os.path.isfile(pydir+"/optin"):
				# technically should check the sanity of this file
				# print("File already there, tracking enabled")
				return
			elif os.path.isfile(pydir+"/optout"):
				# check if ID has already been created. if note, do that
				# print("rename file if it exists")
				os.rename(pydir+"/optout",pydir+"/optin")
			else:
				# create the file and ID
				# print("Create new optin file")
				f = open(pydir+"/optin", 'w') # make new file, empty
				f.close()
	except:
		pass

def checkForUpdate():
	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
	try:
		if addon_prefs.checked_update:
			return addon_prefs.update_avaialble
		else:
			addon_prefs.checked_update = True
			import urllib.request
			d = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html",timeout=10).read().decode('utf-8')
			vtmp1 = d.split('(')
			vtmp1 = vtmp1[1].split(')')[0]
			vtmp2 = ver.split('(')
			vtmp2 = vtmp2[1].split(')')[0]
			if vtmp1 != vtmp2:
				if v:print("MCprep not outdated")
				# create the text file etc.
				addon_prefs.update_avaialble = True
				return True
			else:
				if v:print("MCprep is outdated")
				addon_prefs.update_avaialble = False
				return False
	except:
		pass

########
# Toggle optin/optout for analytics
class toggleOptin(bpy.types.Operator):
	"""Toggle anonymous usage tracking to help the developers, disabled by default. The only data tracked is what functions are used, and the timestamp of the addon installation"""
	bl_idname = "object.mc_toggleoptin"
	bl_label = "Toggle opt-in for analytics tracking"

	def execute(self, context):
		if checkOptin():
			tracking(set='disable')
			usageStat('opt-out')
		else:
			tracking(set='enable')
			usageStat('opt-in')
		return {'FINISHED'}



########
# quickly open release webpage for update
class openreleasepage(bpy.types.Operator):
	"""Go to the MCprep page to get the most recent release and instructions"""
	bl_idname = "object.mcprep_openreleasepage"
	bl_label = "Open the MCprep release page"

	def execute(self, context):
		try:
			import webbrowser
			webbrowser.open("https://github.com/TheDuckCow/MCprep/releases")
		except:
			pass
		return {'FINISHED'}

########################################################################################
#	Above for precursor functions
#	Below for the class functions
########################################################################################


########
# Operator, sets up the materials for better Blender Internal rendering
class materialChange(bpy.types.Operator):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "object.mc_mat_change"
	bl_label = "MCprep mats"
	bl_options = {'REGISTER', 'UNDO'}
	

	def getListDataMats(self):

		reflective = [ 'glass', 'glass_pane_side','ice','ice_packed','iron_bars','door_iron_top','door_iron_bottom',
						'diamond_block','iron_block','gold_block','emerald_block','iron_trapdoor','glass_*',
						'Iron_Door','Glass_Pane','Glass','Stained_Glass_Pane','Iron_Trapdoor','Block_of_Iron',
						'Block_of_Diamond','Stained_Glass','Block_of_Gold','Block_of_Emerald','Packed_Ice',
						'Ice']
		water = ['water','water_flowing','Stationary_Water']
		# things are transparent by default to be safe, but if something is solid it is much
		# better to make it solid (faster render and build times)
		solid = ['sand','dirt','dirt_grass_side','dirt_grass_top','dispenser_front','furnace_top',
				'redstone_block','gold_block','stone','iron_ore','coal_ore','wool_*','stained_clay_*',
				'stone_brick','cobblestone','plank_*','log_*','farmland_wet','farmland_dry',
				'cobblestone_mossy','nether_brick','gravel','*_ore','red_sand','dirt_podzol_top',
				'stone_granite_smooth','stone_granite','stone_diorite','stone_diorite_smooth','stone_andesite',
				'stone_andesite_smooth','brick','snow','hardened_clay','sandstone_side','sandstone_side_carved',
				'sandstone_side_smooth','sandstone_top','red_sandstone_top','red_sandstone_normal','bedrock',
				'dirt_mycelium_top','stone_brick_mossy','stone_brick_cracked','stone_brick_circle',
				'stone_slab_side','stone_slab_top','netherrack','soulsand','*_block','endstone',
				'Grass_Block','Dirt','Stone_Slab','Stone','Oak_Wood_Planks','Wooden_Slab','Sand','Carpet',
				'Wool','Stained_Clay','Gravel','Sandstone','*_Fence','Wood','Acacia/Dark_Oak_Wood','Farmland',
				'Brick','Snow','Bedrock','Netherrack','Soul_Sand','End_Stone']
		emit = ['redstone_block','redstone_lamp_on','glowstone','lava','lava_flowing','fire',
				'sea_lantern',
				'Glowstone','Redstone_Lamp_(on)','Stationary_Lava','Fire','Sea_Lantern','Block_of_Redstone']

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
		# now go through the new materials and change them for the old...?

		return {'reflective':reflective, 'water':water, 'solid':solid,
				'emit':emit}
	
	# helper function for expanding wildcard naming for generalized materials
	# maximum 1 wildcard *
	def checklist(self,matName,alist):
		if matName in alist:
			return True
		else:
			for name in alist:
				if '*' in name:
					x = name.split('*')
					if x[0] != '' and x[0] in matName:
						return True
					elif x[1] != '' and x[1] in matName:
						return True
			return False

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

		if not self.checklist(matGen,listData['solid']): #ie alpha is on unless turned off
			bpy.data.textures[newName].use_alpha = True
			mat.texture_slots[0].use_map_alpha = True
			mat.use_transparency = True
			mat.alpha = 0
			mat.texture_slots[0].alpha_factor = 1
		   
		if self.checklist(matGen,listData['reflective']):
			mat.alpha=0.15
			mat.raytrace_mirror.use = True
			mat.raytrace_mirror.reflect_factor = 0.3
		else:
			mat.raytrace_mirror.use = False
			mat.alpha=0
	   
		if self.checklist(matGen,listData['emit']):
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
		if self.checklist(matGen,listData['reflective']):
			nodeMix2.inputs[0].default_value = 0.3  # mix factor
			nodeGloss.inputs[1].default_value = 0.005 # roughness
		if self.checklist(matGen,listData['emit']):
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
		if self.checklist(matGen,listData['water']):
			# setup the animation??
			nodeMix2.inputs[0].default_value = 0.2
			nodeGloss.inputs[1].default_value = 0.01 # copy of reflective for now
		if self.checklist(matGen,listData['solid']):
			#links.remove(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
			## ^ need to get right format to remove link, need link object, not endpoints
			nodeMix1.inputs[0].default_value = 0 # no transparency
		try:
			if nodeTex.image.source =='SEQUENCE':
				nodeTex.image_user.use_cyclic = True
				nodeTex.image_user.use_auto_refresh = True
				intlength = mat.texture_slots[0].texture.image_user.frame_duration
				nodeTex.image_user.frame_duration = intlength
		except:
			pass
	
	
	def execute(self, context):
		#get list of selected objects
		objList = context.selected_objects
		# gets the list of materials (without repetition) in the selected object list
		matList = getObjectMaterials(objList)
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
		if checkOptin():usageStat('materialChange')
		return {'FINISHED'}


########
# Operator, funtion swaps meshes/groups from library file
class meshSwap(bpy.types.Operator):
	"""Swap minecraft objects from world imports for custom 3D models in the according meshSwap blend file"""
	bl_idname = "object.mc_meshswap"
	bl_label = "MCprep meshSwap"
	bl_options = {'REGISTER', 'UNDO'}
	
	#used for only occasionally refreshing the 3D scene while mesh swapping
	counterObject = 0	# used in count
	countMax = 5		# count compared to this, frequency of refresh (number of objs)
	

	@classmethod
	def poll(cls, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		return addon_prefs.MCprep_exporter_type != "(choose)"


	# called for each object in the loop as soon as possible
	def checkExternal(self, context, name):
		if v:print("Checking external library")
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		
		meshSwapPath = addon_prefs.meshswap_path
		rmable = []
		if addon_prefs.MCprep_exporter_type == "jmc2obj":
			rmable = ['double_plant_grass_top','torch_flame','cactus_side','cactus_bottom','book',
						'enchant_table_side','enchant_table_bottom','door_iron_top','door_wood_top']
		elif addon_prefs.MCprep_exporter_type == "Mineways":
			rmable = [] # Mineways removable objs
		else:
			# need to select one of the exporters!
			return {'CANCELLED'}
		# delete unnecessary ones first
		if name in rmable:
			removable = True
			if v:print("Removable!")
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
		if v:print("about to link, group/mesh?",groupSwap,meshSwap)
		toLink = addon_prefs.mcprep_use_lib # should read from addon prefs, false by default
		bpy.ops.object.select_all(action='DESELECT') # context...? ensure in 3d view..
		#import: guaranteed to have same name as "appendObj" for the first instant afterwards
		grouped = False # used to check if to join or not
		importedObj = None		# need to initialize to something, though this obj no used
		groupAppendLayer = addon_prefs.MCprep_groupAppendLayer
		if groupSwap and name not in bpy.data.groups:
			# if group not linked, put appended group data onto the GUI field layer
			activeLayers = list(context.scene.layers)
			if (not toLink) and (groupAppendLayer!=0):
				x = [False]*20
				x[groupAppendLayer-1] = True
				context.scene.layers = x
			
			#special cases, make another list for this? number of variants can vary..
			if name == "torch" or name == "Torch":
				bAppendLink(meshSwapPath+'/Group/', name+".1", toLink)
				bpy.ops.object.delete()
				bAppendLink(meshSwapPath+'/Group/', name+".2", toLink)
				bpy.ops.object.delete()
			bAppendLink(meshSwapPath+'/Group/', name, toLink)
			bpy.ops.object.delete()
			grouped = True
			# if activated a different layer, go back to the original ones
			context.scene.layers = activeLayers
			grouped = True
			# set properties
			for item in bpy.data.groups[name].items():
				if v:print("GROUP PROPS:",item)
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
			bAppendLink(meshSwapPath+'/Object/',name, False)
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
		if v:print("groupSwap: ",groupSwap,"meshSwap: ",meshSwap)
		if v:print("edgeFloat: ",edgeFloat,", variance: ",variance,", torchlike: ",torchlike)
		return {'meshSwap':meshSwap, 'groupSwap':groupSwap,'variance':variance,
				'edgeFlush':edgeFlush,'edgeFloat':edgeFloat,'torchlike':torchlike,
				'removable':removable,'object':importedObj,'doorlike':doorlike}


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
		# bpy.ops.object.mode_set(mode='OBJECT')
		if v:print("doing offset")
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
		global v
		## debug, restart check
		if v:print('###################################')
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		if checkOptin():usageStat('meshSwap'+':'+addon_prefs.MCprep_exporter_type)
		direc = addon_prefs.meshswap_path
		
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
		groupAppendLayer = addon_prefs.MCprep_groupAppendLayer
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
		if v: print("Using scale: ", gScale)
		if v:print(objList)

		#primary loop, for each OBJECT needing swapping
		for swap in objList:
			swapGen = nameGeneralize(swap.name)
			if v:print("Simplified name: {x}".format(x=swapGen))
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
			if v: print("Swapping '{x}', simplified name '{y}".format(x=swap.name, y=swapGen))
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
				
				if onEdge(facebook[setNum][2]): #check if face is on unit block boundary (local coord!)
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
				if v:print(" DUPLIST: ")
				if v:print([x,y,z], [facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])
				
				# rotation value (second append value: 0 means nothing, rest 1-4.
				if (not [x,y,z] in dupList) or (swapProps['edgeFloat']):
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
						if v:print("checking:",x_diff,z_diff)
						if swapProps['torchlike']: # needs fixing
							if v:print("recognized it's a torchlike obj..")
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
			if v:print("### > trans")
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
			if not grouped and (len(dupedObj) >0) and addon_prefs.mcprep_meshswapjoin:
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
		
		return {'FINISHED'}


#######
# Class for spawning/proxying a new asset for animation
class solidifyPixels(bpy.types.Operator):
	"""Turns each pixel of active UV map/texture into a face -- WIP"""
	bl_idname = "object.solidify_pixels"
	bl_label = "Solidify Pixels"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		if checkOptin():usageStat('solidifyPixels')
		if v:print("hello world, solidify those pixels!")
		self.report({'ERROR'}, "Feature not implemented yet")
		return {'FINISHED'}



class fixMinewaysScale(bpy.types.Operator):
	"""Quick upscaling of Mineways import by 10 for meshswapping"""
	bl_idname = "object.fixmeshswapsize"
	bl_label = "Mineways quick upscale"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		if v:print("Attempting to fix Mineways scaling for meshswap")
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

########
# For proxy spawner, getting list of usable rigs
def getRigList(): #consider passing in rigpath... but 
	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
	# test the link path first!
	rigpath = addon_prefs.mcrig_path
	blendFiles = []
	pathlist = []
	riglist = []

	#from os import listdir
	#from os.path import isfile, join
	onlyfiles = [ f for f in os.listdir(rigpath) if os.path.isfile(os.path.join(rigpath,f)) ]
	for f in onlyfiles:
		# only get listing of .blend files
		if f.split('.')[-1] == 'blend':
			pathlist.append(rigpath+f)
	for rigPath in pathlist:
		with bpy.data.libraries.load(rigPath) as (data_from, data_to):
			for name in data_from.groups:
				if name in bpy.data.groups:
					if v:print("Already grouped in this one. maybe should append the same way/rename?")
					riglist.append( ('//'+':/:'+name,name,"Spawn a {x} rig (local)".format(x=name)) ) # still append the group name, more of an fyi
				else:
					riglist.append( (rigPath+':/:'+name,name,"Spawn a {x} rig".format(x=name)) )

	# setup template
	rigListExample = [('blend/creeper', '#Creeper', '#Description'),
				('blend/steve', '#Steve', '#Description'),
				('blend/dawg', '#Dawg', '#Description')]

	return riglist # for debugging, return rigListExample

#######
# Class for spawning/proxying a new asset for animation
class mobSpawner(bpy.types.Operator):
	"""Instantly spawn any group rig found in the rigs folder. Check the addon preferences to change the path or add new rigs."""
	bl_idname = "object.mcprep_mobspawner"
	bl_label = "Mob Spawner"
	bl_options = {'REGISTER', 'UNDO'}

	# side ntoe, make function for trying to reconnect groups to the primary folder?
	# issue is that if we move the blend file elsewhere and have library linking, even
	# though paths passed in are absolute, it turns it into relative and messes up
	# as soon as it's moved - but we still know where the directory SHOULD be
	# (and maybe have it auto-duphack the model copies if there aren't enough, etc)

	# properties, will appear in redo-last menu
	

	def riglist_enum(self, context):
		return getRigList()

	mcmob_type = bpy.props.EnumProperty(items=riglist_enum) # needs to be defined after riglist_enum
	
	relocation = bpy.props.EnumProperty(
		items = [('None', 'Cursor', 'No relocation'),
				('Clear', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root', 'Offset the root bone to curse while moving the rest pose to the origin')],
		name = "relocation")
	toLink = bpy.props.BoolProperty(
		name = "Library Link mob",
		description = "Library link instead of append the group",
		default = False #change back to false later
		)
	clearPose = bpy.props.BoolProperty(
		name = "Clear Pose",
		description = "Clear the pose to rest position",
		default = True 
		)
	# clear location
		# offset "main" bone from world (only I would use this, really. include it, off by default)
	# link or append
		# >> use same append layer if any!
	# >> shift-d related, make new proxy/make new animation layer/link animation/copy only current pose etc 
	
	if v:print("mcmob_type: ",mcmob_type)

	# def draw(self):
	# we CAN format the redo-last panel, e.g. the bolt addon has done it for sure.
	# need to figure out that / find an rigListExample

	def proxySpawn(self):
		if v:print("Attempting to do proxySpawn")
		if v:print("Mob to spawn: ",self.mcmob_type)

	def execute(self, context):
		
		[path,name] = self.mcmob_type.split(':/:')
		if checkOptin():usageStat('mobSpawner'+':'+name) # want to also pass in the kind!
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

		try:
			bpy.ops.object.mode_set(mode='OBJECT') # must be in object mode, this make similar behavior to other objs
		except:
			pass # can fail to this e.g. if no objects are selected
		#self.proxySpawn()
		 # assumes : is never in filename.. which should be true
		 # NOOO! not for windows!!
		if self.toLink:
			if path != '//':
				bAppendLink(path+'/Group/',name, True)
				# proxy any and all armatures
				# here should do all that jazz with hacking by copying files, checking nth number
				#probably consists of checking currently linked libraries, checking if which
				#have already been linked into existing rigs


				try:
					bpy.ops.object.proxy_make(object=name+'.arma') # this brings up a menu, should do automatically.
					# this would be "good convention", but don't force it - let it also search through
					# and proxy every arma, regardless of name
				except:
					print("Spawner works better if the armature's name is {x}.arma".format(x=name))
					# self report?
					pass

			else:
				# .... need to do the hack with multiple mobs!!!
				if v:print("THIS IS THE LOCAL FILE... not sure what that means here.")
		else:
			# append the rig, the whole group.. though honestly ideally not, and just append the right objs
			#idea: link in group, inevtiably need to make into this blend file but then get the remote's
			# all object names, then unlink/remove group (and object it creates) and directly append all those objects
			# OOORR do append the group, then remove the group but keep the individual objects
			# that way we know we don't append in too many objects (e.g. parents pulling in children/vice versa)

			# also issue of "undo/redo"... groups stay linked/ as groups even if this happens!


			# not doing append layers anymore!
			#groupAppendLayer = addon_prefs.MCprep_groupAppendLayer
			#if groupSwap and name not in bpy.data.groups:
			# if group not linked, put appended group data onto the GUI field layer
			# activeLayers = list(context.scene.layers)
			# if (groupAppendLayer!=0):
			# 	x = [False]*20
			# 	x[groupAppendLayer-1] = True
			# 	context.scene.layers = x				


			if path != '//': #ie not yet linked in.
				sel = bpy.context.selected_objects # capture state before, technically also copy
				bpy.ops.object.select_all(action='DESELECT')
				bAppendLink(path+'/Group/',name, False)
				grp_added = context.selected_objects[0].users_group[0] # to be safe, grab the group from one of the objects
				gl = grp_added.dupli_offset # if rig not centered in original file, assume its group is
				cl = bpy.context.space_data.cursor_location

				#addedObjs = grp_added.objects
				addedObjs = context.selected_objects # why doesn't group added objects work?
				for a in addedObjs:
					a.select = True
					if a.hide:
						a.hide = False
						bpy.ops.group.objects_remove()
						a.hide = True
					else:
						bpy.ops.group.objects_remove()
				for a in grp_added.objects: # but this for selecte dobjects doesn't work below.
					a.select = True
					if a.hide:
						a.hide = False
						bpy.ops.group.objects_remove()
						a.hide = True
					else:
						bpy.ops.group.objects_remove()

				grp_added.name = "reaload-blend-to-remove-this-empty-group"
				bpy.ops.group.objects_remove_all() # just in case
				grp_added.user_clear() # next time blend file reloads, this group will be gone

				if self.clearPose or self.relocation=="Offset":
					#bpy.ops.object.select_all(action='DESELECT') # too soon?
					for ob in addedObjs:
						if ob.type == "ARMATURE" and nameGeneralize(ob.name)==name+'.arma':

							if v:print("This is the one, ",ob.name)

							if self.relocation == "Offset":
								# do the offset stuff, set active etc
								#bpy.ops.object.mode_set(mode='OBJECT')
								bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
							
							#bpy.ops.object.select_all(action='DESELECT')
							act = context.active_object
							bpy.context.scene.objects.active = ob
							if v:print("ACTIVE obj = {x}".format(x=ob.name))
							bpy.ops.object.mode_set(mode='POSE')
							if self.clearPose:
								if v:print("clear the stuff!")
								bpy.ops.pose.select_all(action='SELECT')
								bpy.ops.pose.rot_clear()
								bpy.ops.pose.scale_clear()
								bpy.ops.pose.loc_clear()
								# preserve original selection? keep all selected
							if self.relocation == "Offset":
								tmp=0
								#bpy.ops.pose.select_all(action='DESELECT')
								for nam in ["MAIN","root","base"]:
									if v:print("We are here right?")
									if nam in ob.pose.bones and tmp==0:

										# this method doesn't work because, even though we are in POSE
										# mode, the context for the operator is defined at the start,
										# so acts as if in object mode.. which isn't helpful at all.
										# ob.pose.bones[nam].bone.select = True
										# bpy.ops.view3d.snap_selected_to_cursor(use_offset=True)
										# #ob.pose.bones[nam].bone.select = False
										# tmp=1 # to end loop early


										# these transforms.. are so weird. what. but it works..
										# but not for all, some rigs are different. need some kind
										# of transform to consider in, global vs local etc.
										ob.pose.bones[nam].location[0] = cl[0]
										ob.pose.bones[nam].location[1] = cl[1]
										ob.pose.bones[nam].location[2] = -cl[2]
										tmp=1
								if tmp==0:
									print("This addon works better when the root bone's name is 'MAIN'")

							bpy.ops.object.mode_set(mode='OBJECT')
							bpy.context.scene.objects.active = act
							# for a in addedObjs:
							# 	a.select=True
							break #end the for loop, only one thing to offset!

				# now do the extra options, e.g. the offsets
				if self.relocation == "Clear":
					bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
				elif self.relocation=="None":
					bpy.ops.transform.translate(value=(cl[0]-gl[0],cl[1]-gl[1],cl[2]-gl[2]))

				# add the original selection back
				for ob in sel:
					ob.select = True

			else:
				# here this means the group HAS already been appended.. recopy thsoe elements, or try re-appending?
				# (yes, should try re-appending. may need to rename group)
				self.report({'ERROR'}, "Group name already exists in local file")
				if v:print("Group already appended/is here") #... so hack 'at it and rename it, append, and rename it back?

		return {'FINISHED'}



#######
# Install mob window (popup)
class installMob(bpy.types.Operator):
	"""Install custom rigs for the mob spawner, all groups in selected blend file will become individually spawnable"""
	bl_idname = "object.mcmob_install_menu"
	bl_label = "Install new mob"

	mcmob_install_new_path = bpy.props.StringProperty(
		name = "mcmob_install_new_path",
		description = "Select blend file to install for mob spawning",
		subtype = 'FILE_PATH',
		default = "//")

	# def invoke(self, context, event):
	#     return context.window_manager.invoke_props_dialog(self)

	# well, this would have been useful if it showed the filebrowser when clicking the icon, but it doesn't.
	# hence, we need to show a path in the filebrowser. clear it after.
	# def draw(self, context):
	#     layout = self.layout
	#     row = layout.row()
	#     row.label("Select blend file to install")
	#     row = layout.row()
	#     row.prop(self, "mcmob_install_new_path")
	#     row = layout.row()
		#col.operator(// install new mob).path_install = self.mcmob_install_new_path

	def execute(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		if v:print("attempting to install {x}".format(x=self.mcmob_install_new_path))

		#check blend input file exists
		newrig = self.mcmob_install_new_path
		drpath = addon_prefs.mcrig_path
		if not os.path.isfile(newrig):
			newrig = bpy.path.abspath(newrig)
			if not os.path.isfile(newrig):
				self.report({'ERROR'}, "Rig blend file not found!")
				return {'CANCELLED'}

		# now check the rigs folder indeed exists
		if not os.path.isdir(drpath):
			drpath = bpy.path.abspath(drpath)
			if not os.path.isdir(drpath):
				self.report({'ERROR'}, "Rig directory is not valid!")
				return {'CANCELLED'}
		
		# copy this file to the rig folder
		import shutil
		filename = (newrig).split('/')[-1]
		shutil.copyfile(newrig, drpath+filename)
		self.report({'INFO'}, "Mob-file Installed") #Successfully, do checking of the file!

		addon_prefs.mcmob_install_new_path = "//" # clear the path after install, to show it's not like a saved thing.

		return {'FINISHED'}


#######
# Show MCprep preferences
class showMCprefs(bpy.types.Operator):
	"""Show MCprep preferences"""
	bl_idname = "object.mcprep_preferences"
	bl_label = "Show MCprep preferences"

	def execute(self,context):
		bpy.ops.screen.userpref_show # doesn't work unless is set as an operator button directly!!! sigh
		bpy.data.window_managers["WinMan"].addon_search = "MCprep"
		#bpy.ops.wm.addon_expand(module="MCprep_addon") # just toggles not sets it, not helpful. need to SET it to expanded
		return {'FINISHED'}



########################################################################################
#	Above for class functions/operators
#	Below for UI
########################################################################################



#######
# Panel for placing in the shift-A add object menu
class mobSpawnerMenu(bpy.types.Menu):
	bl_label = "Mob Spawner"
	bl_idname = "mcmob_spawn_menu"

	def draw(self, context):
		#addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		bpy.context.scene.mcRigListGlobal
		layout = self.layout
		rigitems = getRigList()
		if v:print("RIG ITEMS length:"+str(len(rigitems)))
		for n in range(len(rigitems)):
			# do some kind of check for if no rigs found
			if False:
				layout.label(text="No rigs found", icon='ERROR')
			layout.operator("object.mcprep_mobspawner", text=rigitems[n][1]).mcmob_type = rigitems[n][0]



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
class MCprepPreference(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	meshswap_path = bpy.props.StringProperty(
		name = "meshswap_path",
		description = "Asset file for meshswapable objects and groups",
		subtype = 'FILE_PATH',
		default = scriptdir + "/mcprep_meshSwap.blend")
	mcrig_path = bpy.props.StringProperty(
		name = "mcrig_path",
		description = "Folder for rigs to spawn in",
		subtype = 'DIR_PATH',
		default = scriptdir + "/rigs/")
	mcprep_use_lib = bpy.props.BoolProperty(
		name = "Link meshswapped groups & materials",
		description = "Use library linking when meshswapping or material matching",
		default = False)
	MCprep_groupAppendLayer = bpy.props.IntProperty(
		name="Group Append Layer",
		description="When groups are appended instead of linked, the objects part of the group will be placed in this layer, 0 means same as active layer",
		min=0,
		max=20,
		default=20)
	MCprep_exporter_type = bpy.props.EnumProperty(
		items = [('(choose)', '(choose)', 'Select your exporter'),
				('jmc2obj', 'jmc2obj', 'Select if exporter used was jmc2obj'),
				('Mineways', 'Mineways', 'Select if exporter used was Mineways')],
		name = "Exporter")
	checked_update = bpy.props.BoolProperty(
		name = "mcprep_updatecheckbool",
		description = "Has an update for MCprep been checked for already",
		default = False)
	update_avaialble = bpy.props.BoolProperty(
		name = "mcprep_update",
		description = "True if an update is available",
		default = False)
	mcprep_meshswapjoin = bpy.props.BoolProperty(
		name = "mcprep_meshswapjoin",
		description = "Join individuals objects together during meshswapping",
		default = True)
	mcprep_riglink = bpy.props.BoolProperty( # is this actually being used over the other liblink option?
		name = "mcprep_riglink",
		description = "Link and proxy rigs as opposed to directly appending from rig library",
		default = False)
	mcmob_install_new_path = bpy.props.StringProperty(
		name = "mcmob_install_new_path",
		description = "Select blend file to install for mob spawning",
		subtype = 'FILE_PATH',
		default = "//")
		# TRY to make it so only blend files and folders are displayed in file-browser!

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.label("Meshswap")
		layout = layout.box()
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Default Exporter:")
		col = split.column()
		col.prop(self, "MCprep_exporter_type", text="")
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Meshwap assets")
		col = split.column()
		col.prop(self, "meshswap_path", text="")

		layout = self.layout
		row = layout.row()
		row.label("Mob spawning")
		layout = layout.box()
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Rig Folder")
		col = split.column()
		col.prop(self, "mcrig_path", text="")
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Select/install mobs")
		col = split.column()
		col.prop(self, "mcmob_install_new_path", text="")
		col = split.column()
		col.operator("object.mcmob_install_menu", text="Install file for mob spawning").mcmob_install_new_path = self.mcmob_install_new_path
		
		# misc settings
		layout = self.layout
		row = layout.row()
		row.prop(self, "mcprep_use_lib")
		row = layout.row()

		# another row for 
		layout = self.layout
		split = layout.split(percentage=0.5)
		col = split.column()
		row = layout.row()
		if checkOptin():
			col.operator("object.mc_toggleoptin", text="Opt OUT of anonymous usage tracking", icon='CANCEL')
		else:
			col.operator("object.mc_toggleoptin", text="Opt into of anonymous usage tracking", icon='HAND')
		#row = layout.row()
		col = split.column()
		col.operator("object.mcprep_openreleasepage", text="MCprep page for instructions and updates", icon="WORLD")
		row = layout.row()
		row.label("Don't forget to save user preferences!")


#######
# MCprep panel for these declared tools
class MCpanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "MCprep"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_context = "objectmode"
	bl_category = 'Tools'

	def draw(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		
		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		col.label("World exporter:")
		split = layout.split()
		col = split.row(align=True)
		row = col.row(align=True)
		row.prop(addon_prefs,"MCprep_exporter_type", expand=True)

		
		split = layout.split()
		col = split.column(align=True)

		col.label("MCprep tools")
		col.operator("object.mc_mat_change", text="Prep Materials", icon='MATERIAL')
		col.operator("object.mc_meshswap", text="Mesh Swap", icon='LINK_BLEND')
		col.operator("object.mcprep_mobspawner", text="Mob Spawner", icon='POSE_HLT')
		#the UV's pixels into actual 3D geometry (but same material, or modified to fit)
		#col.operator("object.solidify_pixels", text="Solidify Pixels", icon='MOD_SOLIDIFY')
		split = layout.split()
		row = split.row(align=True)
		if addon_prefs.MCprep_exporter_type == "(choose)":
			row.label(text="Select exporter!",icon='ERROR')
		elif addon_prefs.MCprep_exporter_type == "Mineways":
			# split = layout.split(percentage=1)
			# col = split.column(align=True)
			col.label (text="Check block size is")
			col.label (text="1x1x1, not .1x.1.x.1")
			# Attempt AutoFix, another button
			col.operator("object.fixmeshswapsize", text="Quick upscale from 0.1")
		else:
			row.label('jmc2obj works best :)')

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)

		if not context.scene.mcprep_showsettings:
			row.prop(context.scene,"mcprep_showsettings", text="settings", icon="TRIA_RIGHT")
			#row.operator("object.mcprep_preferences",icon="PREFERENCES",text='')
			row.operator("screen.userpref_show",icon="PREFERENCES",text='')

		else:
			row.prop(context.scene,"mcprep_showsettings", text="settings", icon="TRIA_DOWN")
			row.operator("screen.userpref_show",icon="PREFERENCES",text='')
			layout = layout.box()

			split = layout.split(percentage=1)
			col = split.column(align=True)
			col.prop(addon_prefs,"mcprep_meshswapjoin",text="Join same blocks together")
			col.prop(addon_prefs,"mcprep_use_lib",text="Link groups")
			col.label("Append layer")
			col.prop(addon_prefs,"MCprep_groupAppendLayer",text="")
			if addon_prefs.mcprep_use_lib == True:
				col.enabled = False
			col.label(text="Meshswap source:")
			col.prop(addon_prefs,"meshswap_path",text="")
			col.label(text="Mobs folder:")
			col.prop(addon_prefs,"mcrig_path",text="")

		
		layout = self.layout # clear out the box formatting
		split = layout.split()
		row = split.row(align=True)
		if checkForUpdate():
			row.label (text="Update ready!", icon='ERROR')
			split = layout.split()
			row = split.row(align=True)
			row.operator("object.mcprep_openreleasepage", text="Get it now", icon="HAND")



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

#######
# This allows you to right click on a button and link to the manual
def ops_manual_map():
	url_manual_prefix = "https://github.com/TheDuckCow/MCprep"
	url_manual_mapping = (
		("bpy.ops.mesh.add_object", "Modeling/Objects"),
		)
	return url_manual_prefix, url_manual_mapping


########################################################################################
#	Above for UI
#	Below for registration stuff
########################################################################################


# for custom menu registration.. not sure why
def draw_mobspawner(self, context):
	layout = self.layout
	layout.menu(mobSpawnerMenu.bl_idname)



def addon_filter_items(self, context):
	import addon_utils

	items = [('All', "All", "All Add-ons"),
			 ('User', "User", "All Add-ons Installed by User"),
			 ('Enabled', "Enabled", "All Enabled Add-ons"),
			 ('Disabled', "Disabled", "All Disabled Add-ons"),
			 ]

	items_unique = set()

	for mod in addon_utils.modules(refresh=False):
		info = addon_utils.module_bl_info(mod)
		items_unique.add(info["category"])

	items.extend([(cat, cat, "") for cat in sorted(items_unique)])
	return items

def register():


	bpy.types.Scene.mcRigListGlobal = bpy.props.EnumProperty(
		items = [('', '', 'Load rigs in the MCprep panel')],
		name = "Global mob rig list")

	bpy.types.Scene.mcprep_showsettings = bpy.props.BoolProperty(
		name = "mcprep_showsettings",
		description = "Show extra settings in the MCprep panel",
		default = False)

	bpy.utils.register_class(materialChange)
	bpy.utils.register_class(meshSwap)
	bpy.utils.register_class(mobSpawner)
	bpy.utils.register_class(solidifyPixels)
	bpy.utils.register_class(fixMinewaysScale)
	bpy.utils.register_class(installMob)
	
	bpy.utils.register_class(dialogue)
	bpy.utils.register_class(WIP)
	
	bpy.utils.register_class(showMCprefs)
	bpy.utils.register_class(mobSpawnerMenu)
	bpy.types.INFO_MT_armature_add.append(draw_mobspawner)

	bpy.utils.register_class(MCpanel)
	bpy.utils.register_class(MCprepPreference)
	#bpy.utils.register_manual_map(ops_manual_map)
	

	bpy.utils.register_class(toggleOptin)
	bpy.utils.register_class(openreleasepage)
	install()
	if v:print("MCprep register complete")

def unregister():
	bpy.utils.unregister_class(materialChange)
	bpy.utils.unregister_class(meshSwap)
	bpy.utils.unregister_class(mobSpawner)
	bpy.utils.unregister_class(solidifyPixels)
	bpy.utils.unregister_class(fixMinewaysScale)
	bpy.utils.unregister_class(installMob)
	
	bpy.utils.unregister_class(dialogue)
	bpy.utils.unregister_class(WIP)
	bpy.utils.unregister_class(MCprepPreference)
	bpy.utils.unregister_class(MCpanel)
	bpy.utils.unregister_class(mobSpawnerMenu)
	bpy.types.INFO_MT_armature_add.remove(draw_mobspawner)
	bpy.utils.unregister_class(showMCprefs)
	#bpy.utils.unregister_manual_map(ops_manual_map)

	bpy.utils.unregister_class(toggleOptin)
	bpy.utils.unregister_class(openreleasepage)

	del bpy.types.Scene.mcRigListGlobal
	del bpy.types.Scene.mcprep_showsettings

if __name__ == "__main__":
	register()
