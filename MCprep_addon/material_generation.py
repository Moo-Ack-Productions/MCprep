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

import bpy
import os

from . import conf
from . import util

# -----------------------------------------------------------------------------
# Material prep and generation functions (no registration)
# -----------------------------------------------------------------------------

# Convert a material name (e.g. from jmc2obj or Mineways) to standard MC name
def get_mc_canonical_name(name):

	general_name = util.nameGeneralize(name)
	return general_name

def find_from_texturepack(blockname, resource_folder):
	# resource packs have this structure, this function should work with
	# any level within this structure as the resource_folder:
	# //pack_name/assets/minecraft/textures/<subfolder>/<blockname.png>

	if not os.path.isdir(resource_folder):
		if conf.v: print("Error, resource folder does not exist")
		return
	elif os.path.isdir(os.path.join(resource_folder,"textures")):
		resource_folder = os.path.join(resource_folder,"textures")
	elif os.path.isdir(os.path.join(resource_folder,"minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"minecraft","textures")
	elif os.path.isdir(os.path.join(resource_folder,"assets","minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"assets","minecraft","textures")

	if conf.v:print("Final resource folder/subfolder checking:",resource_folder)
	# paths within to search
	search_paths = [resource_folder,
					os.path.join(resource_folder,"blocks"),
					os.path.join(resource_folder,"items")
					#os.path.join(resource_folder,"entity")
					]
	if conf.v:print(search_paths)
	res = None
	for path in search_paths:
		if not os.path.isdir(path): continue
		elif os.path.isfile(os.path.join(path, blockname+".png")):
			res = os.path.join(path, blockname+".png")
		elif os.path.isfile(os.path.join(path, blockname+".jpg")):
			res = os.path.join(path, blockname+".jpg")
		elif os.path.isfile(os.path.join(path, blockname+".jpeg")):
			res = os.path.join(path, blockname+".jpeg")
		if res is not None: break

	return res


# Get mapping of material names to associated material settings
# Depreciate this in favor of get_mc_canonical_name
def getListDataMats():
	# List of materials for special settings
	# TODO: Convert to equivalent json file and use that instead

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
			'Block_of_Redstone','torch_flame_noimport','Sea-Lantern']

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
def checklist(matName,alist):
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


def matprep_internal(mat, use_reflections):
	# Updated existing internal materials with improved settings.
	# Will not necessarily properly convert cycles materials into internal

	# defines lists for materials with special default settings.
	listData = getListDataMats()
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

	if not checklist(matGen,listData['solid']): # alpha default on
		bpy.data.textures[newName].use_alpha = True
		mat.texture_slots[0].use_map_alpha = True
		mat.use_transparency = True
		mat.alpha = 0
		mat.texture_slots[0].alpha_factor = 1

	if use_reflections and checklist(matGen,listData['reflective']):
		mat.alpha=0.15
		mat.raytrace_mirror.use = True
		mat.raytrace_mirror.reflect_factor = 0.3
	else:
		mat.raytrace_mirror.use = False
		mat.alpha=0

	if checklist(matGen,listData['emit']):
		mat.emit = 1
	else:
		mat.emit = 0
	return 0


def matprep_cycles(mat, use_reflections, use_principled):
	# Determine how to prep or generate the cycles materials
	# TODO: Detect if there are normal or spec maps

	if False: #use_principled:
		res = matgen_cycles_principled(mat,use_reflections)
	else:
		res = matgen_cycles_original(mat,use_reflections)

	return res


def set_texture_pack(material, folder, use_extra_passes):
	# get listing of all images of selected materials
	# run through and check for each if counterpart material exists
	# run the swap (and auto load e.g. normals and specs if avail.)
	mc_name = get_mc_canonical_name(material.name)
	if conf.v:print("got name:",mc_name)
	image = find_from_texturepack(mc_name, folder)
	if conf.v:print("got texture:",image)
	if image==None:
		return 0

	# TODO: relate image to existing image datablock, or load it in
	# default for now, just always create new data block
	image_data = util.loadTexture(image)

	# assert_textures_on_materials(image_data, [material])

	# want to change both internal and cycles, if available.
	status = set_internal_texture(image_data, material)
	if (bpy.context.scene.render.engine == 'CYCLES'):
		status = set_cycles_texture(image_data, material)

	return 1


# called for any texture changing
# input a list of material & an already loaded image datablock
# TODO: Add option to search for or ignore/remove extra maps (normal, etc)
def assert_textures_on_materials(image, materials):
	render_engine = bpy.context.scene.render.engine
	count = 0

	if (render_engine == 'BLENDER_RENDER'):
		for mat in materials:
			status = set_internal_texture(image, mat)
			if status: count+=1
	elif (render_engine == 'CYCLES'):
		for mat in materials:
			status = set_cycles_texture(image, mat)
			if status: count+=1
	return count


# input is image datablock
# Used by skin swap and change texture pack
# TODO: Check if node type is input to normal pass or spec or other
# TODO: when going through image texture nodes, see if has attr applied for being
# specific pass; should ALWAYS be applied; and if none are applied, intelligently
# apply attribtues (e.g. if not square.. then likely not an MC material)
# IGNORE THAT< see plan below in comments for intenral.. do more "blind"
# search for each image found and if counterpart exists in new fodler;
# if it doesn't, leave it alone!
# (WAAIIIT.. remember this is SET, ie we WILL apply an image, it's for
# skin swapping by default.. but shoudl be usable by swap texturepack too)
def set_cycles_texture(image, material, extra_passes=False):
	if material.node_tree == None: return False
	# extra_passes:
	# check if there is more data to see pass types
	img_sets = {}
	if extra_passes:
		img_sets = findPassesFromImagepath(image.filepath)

	changed=False

	for node in material.node_tree.nodes:
		if node.type != "TEX_IMAGE": continue
		# TODO: see if there are other texture nodes for normal/etc,
		# check via prop saved to node object
		# if extra_passes: {extra checking}

		# check to see nodes and their respective pre-named field,
		# saved as an attribute on the node
		if "MCPREP_diffuse" in node:
			node.image = image
			node.mute = False
			node.hide = False
		elif "MCPREP_normal" in node:
			if "normal" in img_sets:
				node.image = img_sets["normal"]
			else:
				node.mute = True
				node.hide = True
		elif "MCPREP_specular" in node:
			if "specular" in img_sets:
				node.image = img_sets["specular"]
			else:
				node.mute = True
				node.hide = True
		else:
			# assume all unlabeled texture nodes should be the diffuse
			node["MCPREP_diffuse"] = True # annotate node
			node.image = image
			node.mute = False
			node.hide = False

		changed = True

	return changed


# input is image datablock,
# TODO: when going through layers, see if enabled already for normal / spec or not
# and enabled/disable accordingly (e.g. if was resource with normal, now is not)
def set_internal_texture(image, material, extra_passes=False):
	# check if there is more data to see pass types
	img_sets = {}
	if extra_passes:
		img_sets = findPassesFromImagepath(image.filepath)

	base = None
	tex = None

	# set primary diffuse color as the first image found
	for i,sl in enumerate(material.texture_slots):
		if sl==None or sl.texture==None or sl.texture.type!='IMAGE': continue
		sl.texture.image = image
		sl.use = True
		tex = sl.texture
		base=i
		sl.use_map_normal = False
		sl.use_map_color_diffuse = True
		sl.use_map_specular = False

	# if no textures found, assert adding this one as the first
	if tex==None:
		if conf.v: print("Found no textures, asserting texture onto material")
		name = material.name+"_tex"
		if name not in bpy.data.textures:
			tex = bpy.data.textures.new(name=name,type="IMAGE")
		else:
			tex = bpy.data.textures[name]
		tex.image = image
		if material.texture_slots[0] == None:
			material.texture_slots.create(0)
		material.texture_slots[0].texture = tex
		material.texture_slots[0].use = True

	# go through and turn off any previous passes not in img_sets
	for i,sl in enumerate(material.texture_slots):

		if i==base:continue # skip primary texture set
		if "normal" in img_sets: # pop item each time
			if tex and tex.name+"_n" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_n"]
			else:
				new_tex = bpy.data.textures.new(name=tex.name+"_n",type="IMAGE")
			f = img_sets.pop("normal")
			new_img = util.loadTexture(f)
			new_tex.image = new_img
			sl.texture = new_tex
			sl.use_map_normal = True
			sl.use_map_color_diffuse = False
			sl.use_map_specular = False
			sl.use = True
		elif "spec" in img_sets:
			if tex and tex.name+"_s" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_s"]
			f = img_sets.pop("normal")
			new_img = util.loadTexture(f)
			new_tex.image = new_img
			sl.texture = new_tex
			sl.use_map_normal = False
			sl.use_map_color_diffuse = False
			sl.use_map_specular = True
			sl.use = True

	return True


# Find relevant passes like normal and spec in same folder as provided image
def findPassesFromImagepath(image_file):
	abs_img_file = bpy.path.abspath(image_file)
	if not os.path.isfile(abs_img_file): return []

	img_dir = os.path.dirname(abs_img_file)
	img_base = os.path.basename(abs_img_file)
	base_name = os.path.splitext(img_base)[0] # remove extension

	# valid extentsions and ending names for pass types
	exts = [".png",".jpg",".jpeg",".tiff"]
	normal = [" n","_n","-n","normal","norm","nrm","normals"]
	spec = [" s","_s","-s","specular","spec","nrm","normals"]
	res = {}

	# find lowercase base name matching with valid extentions
	filtered_files = [f for f in os.listdir(img_dir)
					if os.path.isfile(os.path.join(img_dir,f)) and \
					f.lower().startswith(img_base.lower()) and \
					os.path.splitext(f)[-1].lower() in exts
					]
	for f in filtered_files:
		for npass in normal:
			if f.lower().endswith(npass):
				res["normal"]=os.path.join(img_dir,f)
		for spass in spec:
			if f.lower().endswith(npass):
				res["spec"]=os.path.join(img_dir,f)
	return res


# -----------------------------------------------------------------------------
# Generating node groups
# -----------------------------------------------------------------------------



def matgen_cycles_principled(mat, use_reflections):
	return 1 # return 0 once implemented


def matgen_cycles_original(mat, use_reflections):
	# Original material generator for cycles, not using principled shader
	# and defaults to assuming all blocks have transparency, and leaves
	# reflection node in even if not using

	# get the texture, but will fail if NoneType
	image_diff = None
	image_norm = None
	image_spec = None
	image_disp = None # not used
	for sl in mat.texture_slots:
		if not (sl and sl.use and sl.texture!=None and hasattr(sl.texture, "image")\
				and sl.texture.image!=None): continue
		if sl.use_map_color_diffuse and image_diff is None:
			image_diff = sl.texture.image
		elif sl.use_map_normal and image_norm is None:
			image_norm = sl.texture.image
		elif sl.use_map_specular and image_spec is None:
			image_spec = sl.texture.image
		elif sl.use_map_displacement and image_disp is None:
			image_disp = sl.texture.image

	if image_diff==None:
		print("Could not find diffuse image, halting generation")
		return

	# try:
	# 	imageTex = mat.texture_slots[0].texture.image
	# 	# check whether other maps also exist
	# except:
	# 	return

	matGen = util.nameGeneralize(mat.name)
	listData = getListDataMats()

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
	nodeTexNorm = nodes.new('ShaderNodeTexImage')
	nodeTexSpec = nodes.new('ShaderNodeTexImage')
	nodeNormal = nodes.new('ShaderNodeNormalMap')
	nodeOut = nodes.new('ShaderNodeOutputMaterial')

	# set location and connect
	nodeTex.location = (-400,0)
	nodeTexNorm.location = (-600,-275)
	nodeTexSpec.location = (-600,275)
	nodeNormal.location = (-400,-275)
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
	links.new(nodeTexNorm.outputs["Color"],nodeNormal.inputs[0])
	links.new(nodeNormal.outputs["Normal"],nodeDiff.inputs[2])
	links.new(nodeNormal.outputs["Normal"],nodeGloss.inputs[2])

	# annotate texture nodes, and load images if available
	nodeTex["MCPREP_diffuse"] = True
	nodeTexSpec["MCPREP_specular"] = True
	nodeTexNorm["MCPREP_normal"] = True
	# nodeTexDisp["MCPREP_disp"] = True
	nodeTex.image = image_diff
	if image_spec:
		nodeTexSpec.image = image_spec
	else:
		nodeTexSpec.mute = True
	if image_norm:
		nodeTexNorm.image = image_norm
	else:
		nodeTexNorm.mute = True
		nodeNormal.mute = True
	# nodeTexDisp.image = image_disp

	nodeTex.interpolation = 'Closest'
	nodeTexSpec.interpolation = 'Closest'
	# don't treat normal as closest?

	#set other default values, e.g. the mixes
	nodeMix2.inputs[0].default_value = 0 # factor mix with glossy
	nodeGloss.inputs[1].default_value = 0.1 # roughness

	# the above are all default nodes. Now see if in specific lists
	if use_reflections and checklist(matGen,listData['reflective']):
		nodeMix2.inputs[0].default_value = 0.3  # mix factor
		nodeGloss.inputs[1].default_value = 0.005 # roughness
	else:
		nodeMix2.mute = True
		nodeMix2.hide = True
		nodeGloss.mute = True
		nodeGloss.hide = True

	if checklist(matGen,listData['emit']):
		# TODO: add falloff node, colormixRGB node, LightPass node;
		# change the input to colormix RGB for 2 to be 2.5,2.5,2.5
		# and pass isCamerRay into 0 of colormix (factor), and pass
		# in light pass into 1 of colormix ; this goes into strength
		# then, disable or replace the diffuse node entirely, and
		# glossy too (ovveride?)?
		# rather, REPLACE the diffuse node with the emit, instead of joinging
		# via another mix shader and nodeDiff

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

		nodeMixEmitDiff.inputs[0].default_value = 1
		nodeEmit.inputs[1].default_value = 2.5
		# emit value
		# sample as a light
		mat.cycles.sample_as_light = True
	else:
		mat.cycles.sample_as_light = False

	if checklist(matGen,listData['water']):
		# setup the animation??
		nodeMix2.inputs[0].default_value = 0.2
		nodeGloss.inputs[1].default_value = 0.01 # copy of reflective for now
	if checklist(matGen,listData['solid']):
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
