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

from .. import conf
from .. import util

# -----------------------------------------------------------------------------
# Material prep and generation functions (no registration)
# -----------------------------------------------------------------------------


def get_mc_canonical_name(name):
	"""Convert a material name to standard MC name.

	Returns: canonical name, and form (mc, jmc, or mineways)
	"""

	general_name = util.nameGeneralize(name)
	if not conf.json_data:
		res = util.load_mcprep_json()
		if not res:
			return general_name, None
	if "blocks" not in conf.json_data \
			or "block_mapping_mc" not in conf.json_data["blocks"] \
			or "block_mapping_jmc" not in conf.json_data["blocks"] \
			or "block_mapping_mineways" not in conf.json_data["blocks"]:
		if conf.v: print("Missing key values in json")
		return general_name, None
	if general_name in conf.json_data["blocks"]["block_mapping_mc"]:
		canon = conf.json_data["blocks"]["block_mapping_mc"][general_name]
		form = "mc"
	elif general_name in conf.json_data["blocks"]["block_mapping_jmc"]:
		canon = conf.json_data["blocks"]["block_mapping_jmc"][general_name]
		form = "jmc2obj"
	elif general_name in conf.json_data["blocks"]["block_mapping_mineways"]:
		canon = conf.json_data["blocks"]["block_mapping_mineways"][general_name]
		form = "mineways"
	else:
		if conf.vv: print("Canonical name not matched: "+general_name)
		canon = general_name
		form = None

	return canon, form


def find_from_texturepack(blockname, resource_folder=None):
	"""Given a blockname (and resource fodler), find image filepath.

	Finds textures following any pack which should have this structure, and
	the input folder or default resource folder could target at any of the
	following sublevels above the <subfolder> level.
	//pack_name/assets/minecraft/textures/<subfolder>/<blockname.png>
	"""
	if not resource_folder:
		# default to internal pack
		resource_folder = bpy.context.scene.mcprep_custom_texturepack_path

	if not os.path.isdir(resource_folder):
		if conf.v: print("Error, resource folder does not exist")
		return
	elif os.path.isdir(os.path.join(resource_folder,"textures")):
		resource_folder = os.path.join(resource_folder,"textures")
	elif os.path.isdir(os.path.join(resource_folder,"minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"minecraft","textures")
	elif os.path.isdir(os.path.join(resource_folder,"assets","minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"assets","minecraft","textures")

	# if conf.vv:print("\tFinal resource folder/subfolder checking:",resource_folder)

	search_paths = [resource_folder,
					os.path.join(resource_folder,"blocks"),
					os.path.join(resource_folder,"items"),
					os.path.join(resource_folder,"entity"),
					os.path.join(resource_folder,"models"),
					]
	res = None

	# first see if subpath included is found, prioritize use of that
	extensions = [".png",".jpg",".jpeg"]
	if "/" in blockname:
		newpath = blockname.replace("/", os.path.sep)
		for ext in extensions:
			if os.path.isfile(os.path.join(resource_folder,newpath+ext)):
				res = os.path.join(resource_folder,newpath+ext)
				# if conf.v: print("\tFound resource file via subpath: "+res)
				return res
		blockname = os.path.basename(blockname)

	# fallback (more common case), wide-search for
	for path in search_paths:
		if not os.path.isdir(path): continue
		for ext in extensions:
			if os.path.isfile(os.path.join(path, blockname+ext)):
				res = os.path.join(path, blockname+ext)
				# if conf.v: print("\tFound resource file: "+res)
				return res
	# Mineways fallback
	for suffix in ["-Alpha", "-RGB", "-RGBA"]:
		if blockname.endswith(suffix):
			res = os.path.join(resource_folder,"mineways_assets",
								"mineways"+suffix+".png")
			if os.path.isfile(res):
				return res
	return res


# def getListDataMats():
# 	"""Get mapping of material names to associated material settings.

# 	List of materials for special settings
# 	"""
# 	# TODO: already depreciated, fully delete once reference no longer needed

# 	reflective = [ 'glass', 'glass_pane_side','ice','ice_packed','iron_bars',
# 			'door_iron_top','door_iron_bottom','diamond_block','iron_block',
# 			'gold_block','emerald_block','iron_trapdoor','glass_*',
# 			'Iron_Door','Glass_Pane','Glass','Stained_Glass_Pane',
# 			'Iron_Trapdoor','Block_of_Iron','Block_of_Diamond',
# 			'Stained_Glass','Block_of_Gold','Block_of_Emerald',
# 			'Packed_Ice','Ice']
# 	water = ['water','water_flowing','Stationary_Water']
# 	solid = ['sand','dirt','dirt_grass_side','dirt_grass_top',
# 			'dispenser_front','furnace_top','redstone_block','gold_block',
# 			'stone','iron_ore','coal_ore','wool_*','stained_clay_*',
# 			'stone_brick','cobblestone','plank_*','log_*','farmland_wet',
# 			'farmland_dry','cobblestone_mossy','nether_brick','gravel',
# 			'*_ore','red_sand','dirt_podzol_top','stone_granite_smooth',
# 			'stone_granite','stone_diorite','stone_diorite_smooth',
# 			'stone_andesite','stone_andesite_smooth','brick','snow',
# 			'hardened_clay','sandstone_side','sandstone_side_carved',
# 			'sandstone_side_smooth','sandstone_top','red_sandstone_top',
# 			'red_sandstone_normal','bedrock','dirt_mycelium_top',
# 			'stone_brick_mossy','stone_brick_cracked','stone_brick_circle',
# 			'stone_slab_side','stone_slab_top','netherrack','soulsand',
# 			'*_block','endstone','Grass_Block','Dirt','Stone_Slab','Stone',
# 			'Oak_Wood_Planks','Wooden_Slab','Sand','Carpet','Wool',
# 			'Stained_Clay','Gravel','Sandstone','*_Fence','Wood',
# 			'Acacia/Dark_Oak_Wood','Farmland','Brick','Snow','Bedrock',
# 			'Netherrack','Soul_Sand','End_Stone']
# 	emit = ['redstone_block','redstone_lamp_on','glowstone','lava',
# 			'lava_flowing','fire','sea_lantern','Glowstone',
# 			'Redstone_Lamp_(on)','Stationary_Lava','Fire','Sea_Lantern',
# 			'Block_of_Redstone','torch_flame_noimport','Sea-Lantern']

# 	return {'reflective':reflective, 'water':water, 'solid':solid,
# 			'emit':emit}


def checklist(matName, alist):
	"""Helper function for expanding single wildcard within generalized
	material names."""
	if matName in alist:
		return True
	else:
		for name in alist:
			if not '*' in name:
				continue
			x = name.split('*')
			if x[0] != '' and x[0] in matName:
				return True
			elif x[1] != '' and x[1] in matName:
				return True
		return False


def matprep_internal(mat, passes, use_reflections):
	"""Update existing internal materials with improved settings.
	Will not necessarily properly convert cycles materials into internal."""

	if not conf.json_data:
		res = util.load_mcprep_json()

	image_diff = passes["diffuse"]
	image_norm = passes["diffuse"]
	image_spec = passes["diffuse"]
	image_disp = None  # not used

	newName = mat.name+'_tex'
	texList = mat.texture_slots.values()
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

	# TODO: selectively add additional passes beyond diffuse

	# strip out the .00#
	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)
	mat.use_nodes = False

	mat.use_transparent_shadows = True #all materials receive trans
	mat.specular_intensity = 0
	mat.texture_slots[0].texture.use_interpolation = False
	mat.texture_slots[0].texture.filter_type = 'BOX'
	mat.texture_slots[0].texture.filter_size = 0
	mat.texture_slots[0].use_map_color_diffuse = True
	mat.texture_slots[0].diffuse_color_factor = 1
	mat.use_textures[1] = False

	if not checklist(canon,conf.json_data['blocks']['solid']): # alpha default on
		bpy.data.textures[newName].use_alpha = True
		mat.texture_slots[0].use_map_alpha = True
		mat.use_transparency = True
		mat.alpha = 0
		mat.texture_slots[0].alpha_factor = 1

	if use_reflections and checklist(canon,conf.json_data['blocks']['reflective']):
		mat.alpha=0.15
		mat.raytrace_mirror.use = True
		mat.raytrace_mirror.reflect_factor = 0.3
	else:
		mat.raytrace_mirror.use = False
		mat.alpha=0

	if checklist(canon,conf.json_data['blocks']['emit']):
		mat.emit = 1
	else:
		mat.emit = 0
	return 0


def matprep_cycles(mat, passes, use_reflections, use_principled, saturate=False):
	"""Determine how to prep or generate the cycles materials.

	Args:
		mat: the existing material
		passes: dictionary struc of all found pass names
		use_reflections: whether to turn reflections on
		use_principled: if available and cycles, use principled node
		saturate: if a desaturated texture (by canonical resource), add color
	"""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)
	if checklist(canon,conf.json_data['blocks']['emit']):
		res = matgen_cycles_emit(mat, passes)
	elif use_principled and hasattr(bpy.types, 'ShaderNodeBsdfPrincipled'):
		res = matgen_cycles_principled(mat, passes, use_reflections, saturate)
	else:
		res = matgen_cycles_original(mat, passes, use_reflections, saturate)
	return res


def set_texture_pack(material, folder, use_extra_passes):
	"""Replace existing material's image with texture pack's."""
	# run through and check for each if counterpart material exists
	# run the swap (and auto load e.g. normals and specs if avail.)
	mc_name, form = get_mc_canonical_name(material.name)
	if conf.v:print("got name:",mc_name)
	image = find_from_texturepack(mc_name, folder)
	if image==None:
		return 0

	# TODO: relate image to existing image datablock, or load it in
	# default for now, just always create new data block
	image_data = util.loadTexture(image)
	engine = bpy.context.scene.render.engine
	saturate = mc_name in conf.json_data['blocks']['desaturated']

	if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		status = set_cycles_texture(image_data, material, True, saturate)
	elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		status = set_internal_texture(image_data, material, True, saturate)
	return 1


def assert_textures_on_materials(image, materials):
	"""Called for any texture changing, e.g. skin, input a list of material and
	an already loaded image datablock."""
	# TODO: Add option to search for or ignore/remove extra maps (normal, etc)
	engine = bpy.context.scene.render.engine
	count = 0

	if 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		for mat in materials:
			status = set_internal_texture(image, mat)
			if status: count+=1
	elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
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
def set_cycles_texture(image, material, extra_passes=False, saturate=False):
	if material.node_tree == None: return False
	# extra_passes:
	# check if there is more data to see pass types
	img_sets = {}
	if extra_passes:
		img_sets = find_additional_passes(image.filepath)
	# if conf.vv:
	# 	print("Extra passes for cycles set: "+str(img_sets))

	changed=False

	for node in material.node_tree.nodes:
		if saturate and node.type == "MIX_RGB" and "SATURATE" in node:
			node.mute = False
			node.hide = False
			if conf.v: print("Unmuting mix_rgb to saturate texture")

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
				new_img = bpy.data.images.load(img_sets["normal"])
				node.image = new_img
				node.mute = False
				node.hide = False
			else:
				node.mute = True
				node.hide = True
		elif "MCPREP_specular" in node:
			if "specular" in img_sets:
				new_img = bpy.data.images.load(img_sets["specular"])
				node.image = new_img
				node.mute = False
				node.hide = False
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


def set_internal_texture(image, material, extra_passes=False, saturate=False):
	"""Set texture for internal engine. Input is image datablock."""
	# TODO: when going through layers, see if enabled already for normal /
	# spec or not and enabled/disable accordingly (e.g. if was resource
	# with normal, now is not)

	# check if there is more data to see pass types
	matGen = util.nameGeneralize(material.name)
	canon, form = get_mc_canonical_name(matGen)
	img_sets = {}
	if extra_passes:
		img_sets = find_additional_passes(image.filepath)
	if saturate:
		img_sets["saturate"] = True

	base = None
	tex = None

	# set primary diffuse color as the first image found
	for i,sl in enumerate(material.texture_slots):
		if sl==None or sl.texture==None or sl.texture.type!='IMAGE':
			continue
		sl.texture.image = image
		sl.use = True
		tex = sl.texture
		base=i
		sl.use_map_normal = False
		sl.use_map_color_diffuse = True
		sl.use_map_specular = False
		sl.blend_type = 'MIX'
		break

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

		if i==base:
			continue # skip primary texture set
		if "normal" in img_sets and img_sets["normal"]: # pop item each time
			if tex and tex.name+"_n" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_n"]
			else:
				new_tex = bpy.data.textures.new(name=tex.name+"_n",type="IMAGE")
			print(sl)
			if not sl:
				sl = material.texture_slots.create(i)
				# scene refresh required here, as create delays
				# bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
			f = img_sets.pop("normal")
			new_img = util.loadTexture(f)
			new_tex.image = new_img
			sl.texture = new_tex
			sl.use_map_normal = True
			sl.normal_factor = 0.1
			sl.use_map_color_diffuse = False
			sl.use_map_specular = False
			sl.blend_type = 'MIX'
			sl.use = True
		elif "spec" in img_sets and img_sets["spec"]:
			if tex and tex.name+"_s" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_s"]
			else:
				new_tex = bpy.data.textures.new(name=tex.name+"_n",type="IMAGE")
			if not sl:
				sl = material.texture_slots.create(i)
			f = img_sets.pop("normal")
			new_img = util.loadTexture(f)
			new_tex.image = new_img
			sl.texture = new_tex
			sl.use_map_normal = False
			sl.use_map_color_diffuse = False
			sl.use_map_specular = True
			sl.blend_type = 'MIX'
			sl.use = True
		elif "saturate" in img_sets:
			img_sets.pop("saturate")
			if canon not in conf.json_data['blocks']['desaturated']:
				continue
			if tex and tex.name+"_saturate" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_saturate"]
			else:
				new_tex = bpy.data.textures.new(name=tex.name+"_saturate", type="BLEND")
			if not sl:
				sl = material.texture_slots.create(i)
			new_tex.use_color_ramp = True
			for _ in range(len(new_tex.color_ramp.elements)-1):
				new_tex.color_ramp.elements.remove(new_tex.color_ramp.elements[0])

			desat_color = conf.json_data['blocks']['desaturated'][canon]
			if len(desat_color) < len(new_tex.color_ramp.elements):
				desat_color.append(1.0)
			new_tex.color_ramp.elements[0].color = desat_color
			sl.texture = new_tex
			sl.use_map_normal = False
			sl.use_map_color_diffuse = True
			sl.use_map_specular = False
			sl.blend_type = 'OVERLAY'
			sl.use = True

	return True


def get_node_for_pass(material, pass_name):
	"""Assumes cycles material, returns texture node for given pass in mat."""
	if pass_name not in ["diffuse", "specular", "normal", "displace"]:
		return None
	if not material.node_tree:
		return None
	return_node = None
	for node in material.node_tree.nodes:
		if node.type != "TEX_IMAGE":
			continue
		elif "MCPREP_diffuse" in node and pass_name == "diffuse":
			return_node = node
		elif "MCPREP_normal" in node and pass_name == "normal":
			return_node = node
		elif "MCPREP_specular" in node and pass_name == "specular":
			return_node = node
		elif "MCPREP_specular" in node and pass_name == "displace":
			return_node = node
		else:
			if not return_node:
				return_node = node
	print("RETURNING NODE: "+str(return_node))
	return return_node


def get_texlayer_for_pass(material, pass_name):
	"""Assumes BI material, returns texture layer for given pass in mat."""
	if pass_name not in ["diffuse", "specular", "normal", "displace"]:
		return None

	if not hasattr(material, "texture_slots"):
		return None

	for sl in material.texture_slots:
		if not (sl and sl.use and sl.texture!=None
				and hasattr(sl.texture, "image")
				and sl.texture.image!=None): continue
		if sl.use_map_color_diffuse and pass_name == "diffuse":
			return sl.texture
		elif sl.use_map_normal and pass_name == "normal":
			return sl.texture
		elif sl.use_map_specular and pass_name == "specular":
			return sl.texture
		elif sl.use_map_displacement and pass_name == "displace":
			return sl.texture


def get_textures(material):
	"""Extract the image datablocks for a given material.

	Returns {"diffuse":texture, "normal":None, ...}
	"""
	image_block = None
	passes = {"diffuse":None, "specular":None, "normal":None,
				"displace":None}

	# first try cycles materials, fall back to internal if not present
	if material.use_nodes == True:
		for node in material.node_tree.nodes:
			if node.type != "TEX_IMAGE":
				continue
			elif "MCPREP_diffuse" in node:
				passes["diffuse"] = node.image
			elif "MCPREP_normal" in node:
				passes["normal"] = node.image
			elif "MCPREP_specular" in node:
				passes["specular"] = node.image
			else:
				if not passes["diffuse"]:
					passes["diffuse"] = node.image

	# look through internal, unless already found main diffuse pass
	# TODO: Consider checking more explicitly checking based on selected engine
	if hasattr(material, "texture_slots") and not passes["diffuse"]:
		for sl in material.texture_slots:
			if not (sl and sl.use and sl.texture!=None
					and hasattr(sl.texture, "image")
					and sl.texture.image!=None): continue
			if sl.use_map_color_diffuse and passes["diffuse"] is None:
				passes["diffuse"] = sl.texture.image
			elif sl.use_map_normal and passes["normal"] is None:
				passes["normal"] = sl.texture.image
			elif sl.use_map_specular and passes["specular"] is None:
				passes["specular"] = sl.texture.image
			elif sl.use_map_displacement and passes["displace"] is None:
				passes["displace"] = sl.texture.image

	return passes


def find_additional_passes(image_file):
	"""Find relevant passes like normal and spec in same folder as image."""
	abs_img_file = bpy.path.abspath(image_file)
	if conf.vv:
		print("\tFind additional passes for: "+image_file)
	if not os.path.isfile(abs_img_file):
		return {}

	img_dir = os.path.dirname(abs_img_file)
	img_base = os.path.basename(abs_img_file)
	base_name = os.path.splitext(img_base)[0] # remove extension

	# valid extentsions and ending names for pass types
	exts = [".png",".jpg",".jpeg",".tiff"]
	normal = [" n","_n","-n","normal","norm","nrm","normals"]
	spec = [" s","_s","-s","specular","spec"]
	disp = [" d","_d","-d","displace","disp","bump"," b","_b","-b"]
	res = {"diffuse":image_file}

	# find lowercase base name matching with valid extentions
	filtered_files = [f for f in os.listdir(img_dir)
					if os.path.isfile(os.path.join(img_dir,f)) and
					f.lower().startswith(base_name.lower()) and
					os.path.splitext(f)[-1].lower() in exts
					]
	for filtered in filtered_files:
		for npass in normal:
			if os.path.splitext(filtered)[0].lower().endswith(npass):
				res["normal"]=os.path.join(img_dir,filtered)
		for spass in spec:
			if os.path.splitext(filtered)[0].lower().endswith(spass):
				res["specular"]=os.path.join(img_dir,filtered)
		for dpass in disp:
			if os.path.splitext(filtered)[0].lower().endswith(dpass):
				res["displace"]=os.path.join(img_dir,filtered)
	return res


def replace_missing_texture(image):
	"""If image missing from image datablock, replace from texture pack.

	Image block name could be the diffuse or any other pass of material, and
	should handle accordingly
	"""

	if image == None:
		# if conf.vv: print("\tImage block is none:" + str(image))
		return 0
	if image.size[0] != 0 and image.size[1] != 0:
		return 0
	if conf.v: print("Missing datablock detected: "+image.name)

	name = image.name
	if len(name)>4 and name[-4] == ".":
		name = name[:-4]  # cuts off e.g. .png
	elif len(name)>5 and name[-5] == ".":
		name = name[:-5]  # cuts off e.g. .jpeg
	matGen = util.nameGeneralize(name)
	canon, form = get_mc_canonical_name(matGen)
	# TODO: detect for pass structure like normal and still look for right pass
	image_path = find_from_texturepack(canon)
	if not image_path:
		return -1
	image.filepath = image_path
	# image.reload() # not needed?
	# pack?

	return 1  # updated image block



# -----------------------------------------------------------------------------
# Generating node groups
# -----------------------------------------------------------------------------


def matgen_cycles_principled(mat, passes, use_reflections, saturate=False):
	"""Generate principled cycles material, defaults to using transparency."""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	# get the texture, but will fail if NoneType
	image_diff = passes["diffuse"]
	image_norm = passes["normal"]
	image_spec = passes["specular"]
	image_disp = None # not used

	if not image_diff:
		print("Could not find diffuse image, halting generation: "+mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		print("Source image missing for material: " + mat.name)
		# TODO: find replacement texture here, if enabled
		return

	#enable nodes
	mat.use_nodes = True
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	principled = nodes.new('ShaderNodeBsdfPrincipled')
	nodeTrans = nodes.new('ShaderNodeBsdfTransparent')
	nodeMix1 = nodes.new('ShaderNodeMixShader')
	nodeTexDiff = nodes.new('ShaderNodeTexImage')
	nodeTexNorm = nodes.new('ShaderNodeTexImage')
	nodeTexSpec = nodes.new('ShaderNodeTexImage')
	nodeSaturateMix = nodes.new('ShaderNodeMixRGB')
	nodeNormal = nodes.new('ShaderNodeNormalMap')
	nodeOut = nodes.new('ShaderNodeOutputMaterial')

	# set names
	nodeTexDiff.name = "Diffuse Tex"
	nodeTexDiff.label = "Diffuse Tex"
	nodeTexNorm.name = "Normal Tex"
	nodeTexNorm.label = "Normal Tex"
	nodeTexSpec.name = "Specular Tex"
	nodeTexSpec.label = "Specular Tex"
	nodeSaturateMix.name = "Add Color"
	nodeSaturateMix.label = "Add Color"

	# set location and connect
	nodeTexDiff.location = (-400,0)
	nodeTexNorm.location = (-600,-275)
	nodeSaturateMix.location = (-200,0)
	nodeTexSpec.location = (-600,0)
	nodeNormal.location = (-400,-275)
	principled.location = (0,0)
	nodeTrans.location = (-400,100)
	nodeMix1.location = (200,0)
	nodeOut.location = (400,0)

	# default links
	links.new(nodeTexDiff.outputs["Color"],nodeSaturateMix.inputs[1])
	links.new(nodeSaturateMix.outputs["Color"],principled.inputs[0])
	links.new(nodeTexSpec.outputs["Color"],principled.inputs[5])
	links.new(nodeTexNorm.outputs["Color"],nodeNormal.inputs[1])
	links.new(nodeNormal.outputs["Normal"],principled.inputs[17])

	links.new(nodeTexDiff.outputs["Alpha"],nodeMix1.inputs[0])
	links.new(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
	links.new(principled.outputs["BSDF"],nodeMix1.inputs[2])

	links.new(nodeMix1.outputs["Shader"],nodeOut.inputs[0])

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexSpec["MCPREP_specular"] = True
	nodeTexNorm["MCPREP_normal"] = True
	nodeSaturateMix["SATURATE"] = True
	# nodeTexDisp["MCPREP_disp"] = True
	nodeTexDiff.image = image_diff
	if image_spec:
		nodeTexSpec.image = image_spec
	else:
		nodeTexSpec.mute = True
	if image_norm:
		nodeTexNorm.image = image_norm
	else:
		nodeTexNorm.mute = True
		# nodeNormal.mute = True

	nodeTexDiff.interpolation = 'Closest'
	nodeTexSpec.interpolation = 'Closest'

	# apply additional settings
	mat.cycles.sample_as_light = False
	if use_reflections and checklist(canon,conf.json_data['blocks']['reflective']):
		principled.inputs[5].default_value = 0.5
		principled.inputs[7].default_value = 0.1
	else:
		principled.inputs[4].default_value = 0  # unset metallic (dielectric)
		principled.inputs[5].default_value = 0  # set specular
		principled.inputs[7].default_value = 0.1  # set roughness

	if checklist(canon,conf.json_data['blocks']['solid']):
		# nodeMix1.inputs[0].default_value = 1 # no transparency
		nodes.remove(nodeTrans)
		nodes.remove(nodeMix1)
		# nodeDiff.location[1] += 150
		links.new(principled.outputs["BSDF"],nodeOut.inputs[0])

	nodeSaturateMix.inputs[0].default_value = 1.0
	nodeSaturateMix.blend_type = 'OVERLAY'
	nodeSaturateMix.mute = True
	nodeSaturateMix.hide = True
	if canon in conf.json_data['blocks']['desaturated']:
		# Could potentially process image and determine if grayscale (mostly),
		# but would be slow. For now, explicitly pass in if saturated or not
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		if len(desat_color) < len(nodeSaturateMix.inputs[2].default_value):
			desat_color.append(1.0)
		nodeSaturateMix.inputs[2].default_value = desat_color
		if saturate:
			nodeSaturateMix.mute = False
			nodeSaturateMix.hide = False

	return 0 # return 0 once implemented


def matgen_cycles_original(mat, passes, use_reflections, saturate=False):
	"""Generate basic cycles material, defaults to using transparency node."""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	image_diff = passes["diffuse"]
	image_norm = passes["normal"]
	image_spec = passes["specular"]
	image_disp = None # not used

	if image_diff==None:
		print("Could not find diffuse image, halting generation: "+mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		print("Source image missing for material: " + mat.name)
		# TODO: find replacement texture here, if enabled
		return

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
	nodeTexDiff = nodes.new('ShaderNodeTexImage')
	nodeTexNorm = nodes.new('ShaderNodeTexImage')
	nodeTexSpec = nodes.new('ShaderNodeTexImage')
	nodeNormal = nodes.new('ShaderNodeNormalMap')
	nodeSaturateMix = nodes.new('ShaderNodeMixRGB')
	nodeOut = nodes.new('ShaderNodeOutputMaterial')

	# node names
	nodeTexDiff.name = "Diffuse Tex"
	nodeTexDiff.label = "Diffuse Tex"
	nodeTexNorm.name = "Normal Tex"
	nodeTexNorm.label = "Normal Tex"
	nodeTexSpec.name = "Specular Tex"
	nodeTexSpec.label = "Specular Tex"
	nodeSaturateMix.name = "Add Color"
	nodeSaturateMix.label = "Add Color"

	# set location and connect
	nodeTexDiff.location = (-400,0)
	nodeTexNorm.location = (-600,-275)
	nodeTexSpec.location = (-600,275)
	nodeNormal.location = (-400,-275)
	nodeGloss.location = (0,-150)
	nodeSaturateMix.location = (-200,0)
	nodeDiff.location = (-200,-150)
	nodeTrans.location = (-200,0)
	nodeMix1.location = (0,0)
	nodeMix2.location = (200,0)
	nodeOut.location = (400,0)

	links.new(nodeTexDiff.outputs["Color"],nodeSaturateMix.inputs[1])
	links.new(nodeSaturateMix.outputs["Color"],nodeDiff.inputs[0])
	links.new(nodeDiff.outputs["BSDF"],nodeMix1.inputs[2])
	links.new(nodeTexDiff.outputs["Alpha"],nodeMix1.inputs[0])
	links.new(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
	links.new(nodeGloss.outputs["BSDF"],nodeMix2.inputs[2])
	links.new(nodeMix1.outputs["Shader"],nodeMix2.inputs[1])
	links.new(nodeMix2.outputs["Shader"],nodeOut.inputs[0])
	links.new(nodeTexNorm.outputs["Color"],nodeNormal.inputs[0])
	links.new(nodeNormal.outputs["Normal"],nodeDiff.inputs[2])
	links.new(nodeNormal.outputs["Normal"],nodeGloss.inputs[2])

	# annotate texture nodes, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexSpec["MCPREP_specular"] = True
	nodeTexNorm["MCPREP_normal"] = True
	nodeSaturateMix["SATURATE"] = True
	# nodeTexDisp["MCPREP_disp"] = True
	nodeTexDiff.image = image_diff
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

	nodeTexDiff.interpolation = 'Closest'
	nodeTexSpec.interpolation = 'Closest'
	# don't treat normal as closest?

	#set other default values, e.g. the mixes
	nodeMix2.inputs[0].default_value = 0 # factor mix with glossy
	nodeGloss.inputs[1].default_value = 0.1 # roughness
	nodeNormal.inputs[0].default_value = 0.1 # tone down normal maps

	# the above are all default nodes. Now see if in specific lists
	mat.cycles.sample_as_light = False
	if use_reflections and checklist(canon,conf.json_data['blocks']['reflective']):
		nodeMix2.inputs[0].default_value = 0.3  # mix factor
		nodeGloss.inputs[1].default_value = 0.005 # roughness
	else:
		nodeMix2.mute = True
		nodeMix2.hide = True
		nodeGloss.mute = True
		nodeGloss.hide = True

	if checklist(canon,conf.json_data['blocks']['water']):
		# setup the animation??
		nodeMix2.inputs[0].default_value = 0.2
		nodeGloss.inputs[1].default_value = 0.01 # copy of reflective for now
	if checklist(canon,conf.json_data['blocks']['solid']):
		# nodeMix1.inputs[0].default_value = 1 # no transparency
		nodes.remove(nodeTrans)
		nodes.remove(nodeMix1)
		nodeDiff.location[1] += 150
		links.new(nodeDiff.outputs["BSDF"],nodeMix2.inputs[1])
	else:
		nodeMix1.mute = False
	try:
		if nodeTexDiff.image.source =='SEQUENCE':
			nodeTexDiff.image_user.use_cyclic = True
			nodeTexDiff.image_user.use_auto_refresh = True
			intlength = mat.texture_slots[0].texture.image_user.frame_duration
			nodeTexDiff.image_user.frame_duration = intlength
	except:
		pass

	nodeSaturateMix.inputs[0].default_value = 1.0
	nodeSaturateMix.blend_type = 'OVERLAY'
	nodeSaturateMix.mute = True
	nodeSaturateMix.hide = True
	if canon in conf.json_data['blocks']['desaturated']:
		# Could potentially process image and determine if grayscale (mostly),
		# but would be slow. For now, explicitly pass in if saturated or not
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		if len(desat_color) < len(nodeSaturateMix.inputs[2].default_value):
			desat_color.append(1.0)
		nodeSaturateMix.inputs[2].default_value = desat_color
		if saturate:
			nodeSaturateMix.mute = False
			nodeSaturateMix.hide = False

	return 0


def matgen_cycles_emit(mat, passes):
	"""Generates light emiting cycles material, with transaprency."""

	image_diff = passes["diffuse"]
	# image_norm = passes["normal"]
	# image_spec = passes["specular"]
	# image_disp = None # not used
	if image_diff==None:
		print("Could not find diffuse image, halting generation: "+mat.name)
		return

	mat.use_nodes = True
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	# if not checklist(canon,conf.json_data['blocks']['emit']):
	# if calling this method, don't even check type - just assume emit

	# TODO: add falloff node, colormixRGB node, LightPass node;
	# change the input to colormix RGB for 2 to be 2.5,2.5,2.5
	# and pass isCamerRay into 0 of colormix (factor), and pass
	# in light pass into 1 of colormix ; this goes into strength

	# add an emit node, insert it before the first mix node
	nodeLightPath = nodes.new('ShaderNodeLightPath')
	nodeTexDiff = nodes.new('ShaderNodeTexImage')
	nodeTrans = nodes.new('ShaderNodeBsdfTransparent')
	nodeEmit = nodes.new('ShaderNodeEmission')
	nodeEmitVisible = nodes.new('ShaderNodeEmission')
	nodeMixEmits = nodes.new('ShaderNodeMixShader')
	nodeMix = nodes.new('ShaderNodeMixShader')
	nodeFalloff = nodes.new('ShaderNodeLightFalloff')
	nodeOut = nodes.new('ShaderNodeOutputMaterial')

	nodeLightPath.location = (-600, 0)
	nodeTexDiff.location = (-400, -150)
	nodeTrans.location = (-200, 0)
	nodeEmit.location = (-200, -100)
	nodeEmitVisible.location = (-200, -220)
	nodeMixEmits.location = (0, 0)
	nodeMix.location = (200, 0)
	nodeFalloff.location = (-400, 0)
	nodeOut.location = (400, 0)

	# links.new(nodeMixEmitDiff.outputs["Color"], nodeEmit.inputs[0])
	links.new(nodeTexDiff.outputs["Color"], nodeEmit.inputs[0])
	links.new(nodeTexDiff.outputs["Color"], nodeEmitVisible.inputs[0])
	links.new(nodeTexDiff.outputs["Alpha"], nodeMix.inputs[0])
	links.new(nodeFalloff.outputs["Quadratic"], nodeEmit.inputs[1])
	links.new(nodeLightPath.outputs["Is Camera Ray"], nodeMixEmits.inputs[0])
	links.new(nodeEmit.outputs["Emission"], nodeMixEmits.inputs[1])
	links.new(nodeEmitVisible.outputs["Emission"], nodeMixEmits.inputs[2])
	links.new(nodeTrans.outputs["BSDF"], nodeMix.inputs[1])
	links.new(nodeMixEmits.outputs["Shader"], nodeMix.inputs[2])
	links.new(nodeMix.outputs["Shader"], nodeOut.inputs[0])

	nodeTexDiff.interpolation = 'Closest'
	nodeTexDiff.image = image_diff
	nodeTexDiff["MCPREP_diffuse"] = True  # or call it emit?
	nodeEmitVisible.inputs[1].default_value = 1.0
	nodeFalloff.inputs[0].default_value = 30  # controls actual light emitted
	nodeFalloff.inputs[1].default_value = 0.03

	mat.cycles.sample_as_light = True

	return 0
