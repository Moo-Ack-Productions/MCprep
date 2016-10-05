# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2016 Patrick W. Crawford
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


# library imports
import bpy
import os
import math
from bpy_extras.io_utils import ImportHelper
import shutil
import urllib.request

# addon imports
from . import conf
from . import util
from . import tracking


# -----------------------------------------------------------------------------
# Material class functions
# -----------------------------------------------------------------------------



class MCPREP_materialChange(bpy.types.Operator):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "mcprep.mat_change" #"object.mc_mat_change"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

	useReflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropriate materials to be rendered reflective",
		default = True
		)

	consolidateMaterials = bpy.props.BoolProperty(
		name = "Consolidate materials",
		description = "Consolidate duplciate materials & textures",
		default = True
		)

	# prop: consolidate textures consolidateTextures
	
	def getListDataMats(self):

		reflective = [ 'glass', 'glass_pane_side','ice','ice_packed','iron_bars',
				'door_iron_top','door_iron_bottom','diamond_block','iron_block',
				'gold_block','emerald_block','iron_trapdoor','glass_*',
				'Iron_Door','Glass_Pane','Glass','Stained_Glass_Pane',
				'Iron_Trapdoor','Block_of_Iron','Block_of_Diamond',
				'Stained_Glass','Block_of_Gold','Block_of_Emerald',
				'Packed_Ice','Ice']
		water = ['water','water_flowing','Stationary_Water']
		# things are transparent by default to be safe, but if something is solid
		# it is better to make it solid (faster render and build times)
		solid = ['sand','dirt','dirt_grass_side','dirt_grass_top',
				'dispenser_front','furnace_top','redstone_block','gold_block',
				'stone','iron_ore','coal_ore','wool_*','stained_clay_*',
				'stone_brick','cobblestone','plank_*','log_*','farmland_wet',
				'farmland_dry','cobblestone_mossy','nether_brick','gravel',
				'*_ore','red_sand','dirt_podzol_top','stone_granite_smooth',
				'stone_granite','stone_diorite','stone_diorite_smooth',
				'stone_andesite','stone_andesite_smooth','brick','snow',
				'hardened_clay','sandstone_side','sandstone_side_carved',
				'sandstone_side_smooth','sandstone_top','red_sandstone_top',
				'red_sandstone_normal','bedrock','dirt_mycelium_top',
				'stone_brick_mossy','stone_brick_cracked','stone_brick_circle',
				'stone_slab_side','stone_slab_top','netherrack','soulsand',
				'*_block','endstone','Grass_Block','Dirt','Stone_Slab','Stone',
				'Oak_Wood_Planks','Wooden_Slab','Sand','Carpet','Wool',
				'Stained_Clay','Gravel','Sandstone','*_Fence','Wood',
				'Acacia/Dark_Oak_Wood','Farmland','Brick','Snow','Bedrock',
				'Netherrack','Soul_Sand','End_Stone']
		emit = ['redstone_block','redstone_lamp_on','glowstone','lava',
				'lava_flowing','fire','sea_lantern','Glowstone',
				'Redstone_Lamp_(on)','Stationary_Lava','Fire','Sea_Lantern',
				'Block_of_Redstone']

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

		# defines lists for materials with special default settings.
		listData = self.getListDataMats()
		try:
			newName = mat.name+'_tex' # add exception to skip? with warning?
			texList = mat.texture_slots.values()
		except:
			if conf.v:print('\tissue: '+obj.name+' has no active material')
			return
		### Check material texture exists and set name
		try:
			bpy.data.textures[texList[0].name].name = newName
		except:
			if conf.v:print('\twarning: material '
				+mat.name+' has no texture slot. skipping...')
			return

		# disable all but first slot, ensure first slot enabled
		mat.use_textures[0] = True
		for index in range(1,len(texList)):
			mat.use_textures[index] = False

		# strip out the .00#
		matGen = util.nameGeneralize(mat.name)
		mat.use_nodes = False

		mat.use_transparent_shadows = True #all materials receive trans
		mat.specular_intensity = 0
		mat.texture_slots[0].texture.use_interpolation = False
		mat.texture_slots[0].texture.filter_type = 'BOX'
		mat.texture_slots[0].texture.filter_size = 0
		mat.texture_slots[0].use_map_color_diffuse = True
		mat.texture_slots[0].diffuse_color_factor = 1
		mat.use_textures[1] = False

		if not self.checklist(matGen,listData['solid']): # alpha default on
			bpy.data.textures[newName].use_alpha = True
			mat.texture_slots[0].use_map_alpha = True
			mat.use_transparency = True
			mat.alpha = 0
			mat.texture_slots[0].alpha_factor = 1
		   
		if self.useReflections and self.checklist(matGen,listData['reflective']):
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
		return 0

	### Function for default cycles materials
	def materialsCycles(self, mat):
		# get the texture, but will fail if NoneType
		try:
			imageTex = mat.texture_slots[0].texture.image
		except:
			return
		matGen = util.nameGeneralize(mat.name)
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
		if self.useReflections and self.checklist(matGen,listData['reflective']):
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
			nodeMix1.inputs[0].default_value = 0 # no transparency
		try:
			if nodeTex.image.source =='SEQUENCE':
				nodeTex.image_user.use_cyclic = True
				nodeTex.image_user.use_auto_refresh = True
				intlength = mat.texture_slots[0].texture.image_user.frame_duration
				nodeTex.image_user.frame_duration = intlength
		except:
			pass
		return 0
	
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		col.prop(self, "useReflections")
		col.prop(self, "consolidateMaterials")
		# tick box to enable tracking
	
	def execute(self, context):

		# only sends tracking if opted in
		tracking.trackUsage("materials",bpy.context.scene.render.engine)

		#get list of selected objects
		objList = context.selected_objects
		if len(objList)==0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		matList = util.materialsFromObj(objList)
		if len(objList)==0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}
		
		#check if linked material exists
		render_engine = context.scene.render.engine
		count = 0

		for mat in matList:
			#if linked false:
			if (True):
				if (render_engine == 'BLENDER_RENDER'):
					#print('BI mat')
					if conf.vv:print("Blender internal material prep")
					res = self.materialsInternal(mat)
					if res==0: count+=1
				elif (render_engine == 'CYCLES'):
					#print('cycles mat')
					if conf.vv:print("Cycles material prep")
					res = self.materialsCycles(mat)
					if res==0: count+=1
			else:
				if conf.v:print('Get the linked material instead!')

		self.report({"INFO"},"Modified "+str(count)+" materials")
		return {'FINISHED'}



class MCPREP_combineMaterials(bpy.types.Operator):
	bl_idname = "mcprep.combine_materials"
	bl_label = "Combine materials"
	bl_description = "Consolidate the same materials together"

	# arg to auto-force remove old? versus just keep as 0-users

	def execute(self, context):

		# 2-level structure to hold base name and all
		# materials blocks with the same base
		nameCat = {}
		data = bpy.data.materials

		# get and categorize all materials names
		for mat in data:
			base = util.nameGeneralize(mat.name)
			if base not in nameCat:
				nameCat[base] = [mat.name]
			elif mat.name not in nameCat[base]:
				nameCat[base].append(mat.name)
			else:
				print("Skipping, already added material")

		# pre 2.78 solution, deep loop
		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl == None or sl.material == None:continue
					sl.material = bpy.data.materials[nameCat[ util.nameGeneralize(sl.material.name) ][0]]
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in nameCat:
			if len(base)<2: continue
			
			nameCat[base].sort() # in-place sorting
			baseMat = data[ nameCat[base][0] ]
			
			for matname in nameCat[base][1:]:

				# skip if fake user set
				if data[matname].use_fake_user == True: continue 
				# otherwise, remap
				res = util.remap_users(data[matname],baseMat)
				if res != 0:
					self.report({'ERROR'}, str(res))
					return {'CANCELLED'}
				old = data[matname]
				if removeold==True and old.users==0:
					data.remove( data[matname] )
			
			# Final step.. rename to not have .001 if it does
			genBase = util.nameGeneralize(baseMat.name)
			if baseMat.name != genBase:
				if genBase in data and data[genBase].users!=0:
					pass
				else:
					baseMat.name = genBase
			else:
				baseMat.name = genBase

		return {'FINISHED'}



# class MCPREP_scaleUV(bpy.types.Operator):
# 	bl_idname = "mcprep.scaleUV"
# 	bl_label = "Scale all faces in UV editor"
# 	bl_description = "Scale all faces in the UV editor"

# 	def execute(self, context):
		
# 		# WIP
# 		ob = context.active_object

# 		# copied from elsewhere
# 		uvs = ob.data.uv_layers[0].data
# 		matchingVertIndex = list(chain.from_iterable(polyIndices))

# 		# example, matching list of uv coord and 3dVert coord:
# 		uvs_XY = [i.uv for i in Object.data.uv_layers[0].data]
# 		vertXYZ= [v.co for v in Object.data.vertices]

# 		matchingVertIndex = list(chain.from_iterable([p.vertices for p in Object.data.polygons]))
# 		# and now, the coord to pair with uv coord:
# 		matchingVertsCoord = [vertsXYZ[i] for i in matchingVertIndex]

# 		return {'FINISHED'}


class MCPREP_improveUI(bpy.types.Operator):
	"""Improve the UI with specific view settings"""
	bl_idname = "mcprep.improve_ui"
	bl_label = "Prep UI"
	bl_description = "Improve UI for minecraft by disabling mipmaps & setting texture solid"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		context.space_data.show_textured_solid = True # need to make it 3d space
		context.user_preferences.system.use_mipmaps = True

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Skin swapping lists
# -----------------------------------------------------------------------------


# for asset listing UIList drawing
class MCPREP_skin_UIList(bpy.types.UIList):
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		layout.prop(set, "name", text="", emboss=False)


# for asset listing
class ListColl(bpy.types.PropertyGroup):
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()


# reload the skins in the directory for UI list
def reloadSkinList(context):

	skinfolder = context.scene.mcskin_path
	files = [ f for f in os.listdir(skinfolder) if\
					os.path.isfile(os.path.join(skinfolder,f)) ]

	skinlist = []
	for path in files:
		if path.split(".")[-1].lower() not in ["png","jpg","jpeg","tiff"]: continue
		skinlist.append( (path, "{x} skin".format(x=path)) )

	# clear lists
	context.scene.mcprep_skins_list.clear()
	conf.skin_list = []

	# recreate
	for i, (skin, description) in enumerate(skinlist, 1):
		item = context.scene.mcprep_skins_list.add()
		conf.skin_list.append(  (skin,os.path.join(skinfolder,skin))  )
		item.label = description
		item.description = description
		item.name = skin


# for UI list path callback
def update_skin_path(self, context):
	if conf.vv:print("Updating skin path")
	reloadSkinList(context)


def getMatsFromSelected(selected):
	# pre-expand
	obj_list = []
	
	for ob in selected:
		if ob.type == 'MESH':
			obj_list.append(ob)
		elif ob.type == 'ARMATURE':
			for ch in ob.children:
				if ch.type == 'MESH': obj_list.append(ch)
		else:
			continue
	
	mat_list = []
	for ob in obj_list:
		# get all materials
		
		for slot in ob.material_slots:
			if slot.material not in mat_list:mat_list.append(slot.material)
	return mat_list


# called for any texture changing
# input a list of material & an already loaded image datablock
def changeTexture(image, materials):
	render_engine = bpy.context.scene.render.engine
	if (render_engine == 'BLENDER_RENDER'):
		if conf.vv:print("Blender internal skin swapping")
		status = swapInternal(image, materials)
	elif (render_engine == 'CYCLES'):
		if conf.vv:print("Cycles skin swapping")
		status =swapCycles(image, materials)
	return status


# scene update to auto load skins on load
def collhack_skins(scene):
	bpy.app.handlers.scene_update_pre.remove(collhack_skins)
	if conf.vv:print("Reloading skins")

	try:
		reloadSkinList(bpy.context)
	except:
		if conf.v:print("Didn't run callback")
		pass


# input is either UV image itself or filepath
def swapCycles(image, mats):
	if conf.vv:print("Texture swapping cycles")
	changed = 0
	for mat in mats:
		if mat.node_tree == None:continue
		for node in mat.node_tree.nodes:
			if node.type != "TEX_IMAGE": continue
			node.image = image
			changed+=1

	if changed == 0:
		return False # nothing updated
	else:
		return True # updated at least one texture (the first)


# input is either UV image itself or filepath
def swapInternal(image, mats):
	if conf.vv:print("Texture swapping internal")
	changed = 0
	for mat in mats:
		for sl in mat.texture_slots:
			if sl==None or sl.texture == None or sl.texture.type != 'IMAGE': continue
			print("Found  a good texture slot! orig image: "+str(sl.texture.image.name))
			sl.texture.image = image
			changed += 1
			break
	if changed == 0:
		return False # nothing updated
	else:
		return True # updated at least one texture (the first)


def loadSkinFile(self, context):

	if os.path.isfile(self.filepath)==False:
		self.report({'ERROR'}, "No materials found to update")
		# special message for library linking?

	image = util.loadTexture(self.filepath)
	mats = getMatsFromSelected(context.selected_objects)
	if len(mats)==0:
		self.report({'ERROR'}, "No materials found to update")
		# special message for library linking?
		return 1

	# do th change, will update according to render engine
	status = changeTexture(image, mats)
	if status == False:
		self.report({'ERROR'}, "No image textures found to update")
		return 1
	else:
		pass 

	# and fix eyes if appropriate
	if image.size[1]/image.size[0] != 1:
		# self.report({'ERROR'}, "")
		self.report({'INFO'}, "No image textures found to update")
		return 0
	return 0


# -----------------------------------------------------------------------------
# Skin swapping classes
# -----------------------------------------------------------------------------


class MCPREP_skinSwapper(bpy.types.Operator, ImportHelper):
	"""Swap the skin of a (character) with another file"""
	bl_idname = "mcprep.skin_swapper"
	bl_label = "Swap skin"
	bl_description = "Swap the skin of a rig with another file"
	bl_options = {'REGISTER', 'UNDO'}

	# filename_ext = ".zip"
	filter_glob = bpy.props.StringProperty(
			default="*",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

	def execute(self,context):
		tracking.trackUsage("skin","file import")
		res = loadSkinFile(self, context)
		if res!=0:
			return {'CANCELLED'}

		return {'FINISHED'}



class MCPREP_applySkin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyskin"
	bl_label = "Apply skin"
	bl_description = "Apply the active UV image to selected character materials"
	bl_options = {'REGISTER', 'UNDO'}

	filepath = bpy.props.StringProperty(
		name="Skin",
		description="selected")

	def execute(self,context):
		tracking.trackUsage("skin","ui list")
		res = loadSkinFile(self, context)
		if res!=0:
			return {'CANCELLED'}

		return {'FINISHED'}


class MCPREP_applyUsernameSkin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyusernameskin"
	bl_label = "Skin from user"
	bl_description = "Download and apply skin from specific username"
	bl_options = {'REGISTER', 'UNDO'}

	username = bpy.props.StringProperty(
		name="Username",
		description="Exact name of user to get texture from",
		default="")

	redownload = bpy.props.BoolProperty(
		name="Re-download",
		description="Re-download if already locally found",
		default=False)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		self.layout.label("Enter exact username below")
		self.layout.prop(self,"username",text="")
		self.layout.label(
			"and then press OK; blender may pause briefly to download")

	def execute(self,context):
		if self.username == "":
			self.report({"ERROR","Invalid username"})
			return {'CANCELLED'}
		tracking.trackUsage("skin","username")

		skins = [ str(skin[0]).lower() for skin in conf.skin_list ]
		paths = [ skin[1] for skin in conf.skin_list ]
		if self.username.lower() not in skins or self.redownload==True:
			self.downloadUser(context)
		else:
			if conf.v:print("Reusing downloaded skin")
			ind = skins.index(self.username.lower())
			bpy.ops.mcprep.applyskin(filepath=paths[ind][1])

		return {'FINISHED'}


	def downloadUser(self, context):

		#http://minotar.net/skin/theduckcow
		src_link = "http://minotar.net/skin/"
		saveloc = os.path.join(bpy.path.abspath(context.scene.mcskin_path),
								self.username.lower()+".png")
		
		#urllib.request.urlretrieve(src_link+self.username.lower(), saveloc)
		try:
			urllib.request.urlretrieve(src_link+self.username.lower(), saveloc)
		except urllib.error.HTTPError as e:
			self.report({"ERROR"},"Could not find username")
			return {'CANCELLED'}
		except urllib.error.URLError as e:
			self.report({"ERROR"},"URL error, check internet connection")
			return {'CANCELLED'}
		# else:
		# 	self.report({"ERROR"},"Error occurred trying to download skin")
		# 	return {'CANCELLED'}

		bpy.ops.mcprep.applyskin(filepath = saveloc)
		bpy.ops.mcprep.reload_skins()



class MCPREP_skinFixEyes(bpy.types.Operator):
	"""AFix the eyes of a rig to fit a rig"""
	bl_idname = "mcprep.fix_skin_eyes"
	bl_label = "Fix eyes"
	bl_description = "Fix the eyes of a rig to fit a rig"
	bl_options = {'REGISTER', 'UNDO'}

	# initial_eye_type: unknown (default), 2x2 square, 1x2 wide.

	def execute(self,context):
		
		# take the active texture input (based on selection)
		print("fix eyes")
		self.report({'ERROR'}, "Work in progress operator")
		return {'CANCELLED'}

		return {'FINISHED'}



class MCPREP_addSkin(bpy.types.Operator, ImportHelper):
	bl_idname = "mcprep.add_skin"
	bl_label = "Add skin"
	bl_description = "Add a new skin to the active folder"
	bl_options = {'REGISTER', 'UNDO'}

	# filename_ext = ".zip" # needs to be only tinder
	filter_glob = bpy.props.StringProperty(
			default="*",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

	def execute(self,context):

		new_skin = bpy.path.abspath(self.filepath)
		if os.path.isfile(new_skin) == False:
			self.report({"ERROR"},"Not a image file path")
			return {'CANCELLED'}

		# copy the skin file
		base = bpy.path.basename(new_skin)
		shutil.copy2(new_skin, os.path.join(context.scene.mcskin_path,base))

		# in future, select multiple
		bpy.ops.mcprep.reload_skins()
		self.report({"INFO"},"Added 1 skin") # more in the future

		return {'FINISHED'}


class MCPREP_removeSkin(bpy.types.Operator):
	bl_idname = "mcprep.remove_skin"
	bl_label = "Remove skin"
	bl_description = "Remove a skin from the active folder"
	bl_options = {'REGISTER', 'UNDO'}

	index = bpy.props.IntProperty(
			default=0)

	def execute(self,context):

		if self.index >= len(conf.skin_list):
			self.report({"ERROR"},"Indexing error")
			return {'CANCELLED'}

		file = conf.skin_list[self.index][-1]

		if os.path.isfile(file) == False:
			self.report({"ERROR"},"Skin not found to delete")
			return {'CANCELLED'}

		os.remove(file)

		# refresh the folder
		bpy.ops.mcprep.reload_skins()
		if context.scene.mcprep_skins_list_index >= len(conf.skin_list):
			context.scene.mcprep_skins_list_index = len(conf.skin_list)-1

		# in future, select multiple
		self.report({"INFO"},"Removed "+bpy.path.basename(file))

		
		return {'FINISHED'}



class MCPREP_reloadSkins(bpy.types.Operator):
	bl_idname = "mcprep.reload_skins"
	bl_label = "Reload skin"
	bl_description = "Reload the skins folder"

	def execute(self, context):
		reloadSkinList(context)
		return {'FINISHED'}



# -----------------------------------------------------------------------------
#	Above for UI
#	Below for register
# -----------------------------------------------------------------------------



def register():
	bpy.types.Scene.mcprep_skins_list = \
			bpy.props.CollectionProperty(type=ListColl)
	bpy.types.Scene.mcprep_skins_list_index = bpy.props.IntProperty(default=0)

	# to auto-load the skins
	bpy.app.handlers.scene_update_pre.append(collhack_skins)

def unregister():
	del bpy.types.Scene.mcprep_skins_list
	del bpy.types.Scene.mcprep_skins_list_index

