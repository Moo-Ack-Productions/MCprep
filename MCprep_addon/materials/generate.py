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
import bpy

from .. import conf
from .. import util


# -----------------------------------------------------------------------------
# Material prep and generation functions (no registration)
# -----------------------------------------------------------------------------


def update_mcprep_texturepack_path(self, context):
	"""Triggered if the scene-level resource pack path is updated."""
	bpy.ops.mcprep.reload_items()


def get_mc_canonical_name(name):
	"""Convert a material name to standard MC name.

	Returns: canonical name, and form (mc, jmc, or mineways)
	"""
	general_name = util.nameGeneralize(name)
	if not conf.json_data:
		res = util.load_mcprep_json()
		if not res:
			return general_name, None
	if ("blocks" not in conf.json_data
			or "block_mapping_mc" not in conf.json_data["blocks"]
			or "block_mapping_jmc" not in conf.json_data["blocks"]
			or "block_mapping_mineways" not in conf.json_data["blocks"]):
		conf.log("Missing key values in json")
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
		conf.log("Canonical name not matched: "+general_name, True)
		canon = general_name
		form = None

	return canon, form


def find_from_texturepack(blockname, resource_folder=None):
	"""Given a blockname (and resource folder), find image filepath.

	Finds textures following any pack which should have this structure, and
	the input folder or default resource folder could target at any of the
	following sublevels above the <subfolder> level.
	//pack_name/assets/minecraft/textures/<subfolder>/<blockname.png>
	"""
	if not resource_folder:
		# default to internal pack
		resource_folder = bpy.context.scene.mcprep_texturepack_path

	if not os.path.isdir(resource_folder):
		conf.log("Error, resource folder does not exist")
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
					os.path.join(resource_folder,"block"),
					os.path.join(resource_folder,"items"),
					os.path.join(resource_folder,"item"),
					os.path.join(resource_folder,"entity"),
					os.path.join(resource_folder,"models"),
					os.path.join(resource_folder,"model"),
					]
	res = None

	# first see if subpath included is found, prioritize use of that
	extensions = [".png",".jpg",".jpeg"]
	if "/" in blockname:
		newpath = blockname.replace("/", os.path.sep)
		for ext in extensions:
			if os.path.isfile(os.path.join(resource_folder,newpath+ext)):
				res = os.path.join(resource_folder,newpath+ext)
				return res
		newpath = os.path.basename(blockname) # case where goes into other subpaths
		for ext in extensions:
			if os.path.isfile(os.path.join(resource_folder,newpath+ext)):
				res = os.path.join(resource_folder,newpath+ext)
				return res

	# fallback (more common case), wide-search for
	for path in search_paths:
		if not os.path.isdir(path):
			continue
		for ext in extensions:
			if os.path.isfile(os.path.join(path, blockname+ext)):
				res = os.path.join(path, blockname+ext)
				return res
	# Mineways fallback
	for suffix in ["-Alpha", "-RGB", "-RGBA"]:
		if blockname.endswith(suffix):
			res = os.path.join(resource_folder,"mineways_assets",
								"mineways"+suffix+".png")
			if os.path.isfile(res):
				return res

	return res


def detect_form(materials):
	"""Function which, given the input materials, guesses the exporter form.

	Useful for pre-determining elibibility of a function and also for tracking
	reporting to give sense of how common which exporter is used.
	"""
	jmc2obj = 0
	mc = 0
	mineways = 0
	for mat in materials:
		if not mat:
			continue
		name = util.nameGeneralize(mat.name)
		_, form = get_mc_canonical_name(name)
		if form == "jmc2obj":
			jmc2obj+=1
		elif form == "mineways":
			mineways+=1
		else:
			mc+=1

	only_mineways = False

	# more logic, e.g. count
	if mineways==0 and jmc2obj==0:
		res = None  # unknown
	elif mineways>0 and jmc2obj==0:
		res = "mineways"
	elif jmc2obj>0 and mineways==0:
		res = "jmc2obj"
	elif jmc2obj < mineways:
		res = "mineways"
	elif jmc2obj > mineways:
		res = "jmc2obj"
	else:
		res = None  # unknown

	return res  # one of jmc2obj, mineways, or None


def checklist(matName, listName):
	"""Helper function for expanding single wildcard within generalized
	material names."""

	if not conf.json_data:
		conf.log("No json_data for checklist to call from!")
	if not "blocks" in conf.json_data or not listName in conf.json_data["blocks"]:
		conf.log("conf.json_data is missing blocks or listName "+str(listName))
		return False
	alist = conf.json_data["blocks"][listName]
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


def matprep_internal(mat, passes, use_reflections, only_solid):
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
		conf.log('\twarning: material '
			+mat.name+' has no texture slot. skipping...')
		return

	# disable all but first slot, ensure first slot enabled
	mat.use_textures[0] = True
	diff_layer = 0
	spec_layer = None
	norm_layer = None
	disp_layer = None
	saturate_layer = None
	first_unused = None
	for index in range(1,len(texList)):
		if not mat.texture_slots[index] or not mat.texture_slots[index].texture:
			mat.use_textures[index] = False
			if not first_unused:
				first_unused = index
		elif "MCPREP_diffuse" in mat.texture_slots[index].texture:
			diff_layer = index
			mat.use_textures[index] = True
		elif "MCPREP_specular" in mat.texture_slots[index].texture:
			spec_layer = index
			mat.use_textures[index] = True
		elif "MCPREP_normal" in mat.texture_slots[index].texture:
			norm_layer = index
			mat.use_textures[index] = True
		elif "SATURATE" in mat.texture_slots[index].texture:
			saturate_layer = index
			mat.use_textures[index] = True
		else:
			mat.use_textures[index] = False

	if mat.texture_slots[diff_layer].texture.type != "IMAGE":
		conf.log("No diffuse-detected texture, skipping material: "+mat.name)
		return 1

	# strip out the .00#
	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)
	mat.use_nodes = False

	mat.use_transparent_shadows = True #all materials receive trans
	mat.specular_intensity = 0
	mat.texture_slots[diff_layer].texture.use_interpolation = False
	mat.texture_slots[diff_layer].texture.filter_type = 'BOX'
	mat.texture_slots[diff_layer].texture.filter_size = 0
	mat.texture_slots[diff_layer].use_map_color_diffuse = True
	mat.texture_slots[diff_layer].diffuse_color_factor = 1

	if only_solid is False and not checklist(canon, "solid"): # alpha default on
		bpy.data.textures[newName].use_alpha = True
		mat.texture_slots[diff_layer].use_map_alpha = True
		mat.use_transparency = True
		mat.alpha = 0
		mat.texture_slots[diff_layer].alpha_factor = 1
		for index in [spec_layer, norm_layer, disp_layer]:
			if index:
				mat.texture_slots[index].use_map_alpha = False

	if use_reflections and checklist(canon, "reflective"):
		mat.alpha = 0
		mat.raytrace_mirror.use = True
		mat.raytrace_mirror.reflect_factor = 0.15
	else:
		mat.raytrace_mirror.use = False
		mat.alpha = 0

	if checklist(canon, "emit"):
		mat.emit = 1
	else:
		mat.emit = 0

	if canon in conf.json_data['blocks']['desaturated']:
		# cycle through and see if the layer exists to enable/disable blend
		if "texture_swapped" in mat:
			if saturate_layer:
				pass  # should be good
			else:
				# set_internal_texture(True)

				# TODO: code is duplicative to below, consolidate later
				if mat.name+"_saturate" in bpy.data.textures:
					new_tex = bpy.data.textures[mat.name+"_saturate"]
				else:
					new_tex = bpy.data.textures.new(name=mat.name+"_saturate", type="BLEND")
				if not saturate_layer:
					if not first_unused:
						first_unused = len(mat.texture_slots)-1 # force reuse last at worst
					sl = mat.texture_slots.create(first_unused)
				else:
					sl = mat.texture_slots[saturate_layer]
				sl.texture = new_tex
				sl.texture["SATURATE"] = True
				sl.use_map_normal = False
				sl.use_map_color_diffuse = True
				sl.use_map_specular = False
				sl.use_map_alpha = False
				sl.blend_type = 'OVERLAY'
				sl.use = True
				new_tex.use_color_ramp = True
				for _ in range(len(new_tex.color_ramp.elements)-1):
					new_tex.color_ramp.elements.remove(new_tex.color_ramp.elements[0])
				desat_color = conf.json_data['blocks']['desaturated'][canon]
				if len(desat_color) < len(new_tex.color_ramp.elements[0].color):
					desat_color.append(1.0)
				new_tex.color_ramp.elements[0].color = desat_color

	return 0


def matprep_cycles(mat, passes, use_reflections, use_principled, only_solid):
	"""Determine how to prep or generate the cycles materials.

	Args:
		mat: the existing material
		passes: dictionary struc of all found pass names
		use_reflections: whether to turn reflections on
		use_principled: if available and cycles, use principled node
		saturate: if a desaturated texture (by canonical resource), add color
	"""
	if util.bv28():
		# ensure nodes are enabled esp. after importing from BI scenes
		mat.use_nodes = True

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)
	if checklist(canon, "emit"):
		res = matgen_cycles_emit(mat, passes)
	elif use_principled and hasattr(bpy.types, 'ShaderNodeBsdfPrincipled'):
		res = matgen_cycles_principled(mat, passes, use_reflections, only_solid)
	else:
		res = matgen_cycles_original(mat, passes, use_reflections, only_solid)
	return res


def set_texture_pack(material, folder, use_extra_passes):
	"""Replace existing material's image with texture pack's."""
	# run through and check for each if counterpart material exists
	# run the swap (and auto load e.g. normals and specs if avail.)
	mc_name, form = get_mc_canonical_name(material.name)
	image = find_from_texturepack(mc_name, folder)
	if image==None:
		return 0

	image_data = util.loadTexture(image)
	engine = bpy.context.scene.render.engine
	saturate = mc_name in conf.json_data['blocks']['desaturated']
	material["texture_swapped"] = True  # used to apply saturation

	if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		status = set_cycles_texture(image_data, material, True)
	elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		status = set_internal_texture(image_data, material, use_extra_passes)
	return 1


def assert_textures_on_materials(image, materials):
	"""Called for any texture changing, e.g. skin, input a list of material and
	an already loaded image datablock."""
	# TODO: Add option to search for or ignore/remove extra maps (normal, etc)
	engine = bpy.context.scene.render.engine
	count = 0

	if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		for mat in materials:
			status = set_internal_texture(image, mat)
			if status: count+=1
	elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		for mat in materials:
			status = set_cycles_texture(image, mat)
			if status: count+=1
	return count


def set_cycles_texture(image, material, extra_passes=False):
	"""
	Used by skin swap and assiging missing textures or tex swapping.
	Args:
		image: image datablock
	"""
	if material.node_tree == None:
		return False
	# check if there is more data to see pass types
	img_sets = {}
	if extra_passes:
		img_sets = find_additional_passes(image.filepath)
	changed=False

	for node in material.node_tree.nodes:
		if "texture_swapped" in material and node.type == "MIX_RGB" and "SATURATE" in node:
			node.mute = False
			node.hide = False
			conf.log("Unmuting mix_rgb to saturate texture")

		# if node.type != "TEX_IMAGE": continue

		# check to see nodes and their respective pre-named field,
		# saved as an attribute on the node
		if "MCPREP_diffuse" in node:
			node.image = image
			node.mute = False
			node.hide = False
		elif "MCPREP_normal" in node:
			if "normal" in img_sets:
				if node.type == 'TEX_IMAGE':
					new_img = util.loadTexture(img_sets["normal"])
					node.image = new_img
				node.mute = False
				node.hide = False
			else:
				node.mute = True
				node.hide = True

				# remove the link between normal map and principled shader
				# normal_map = node.outputs[0].links[0].to_node
				# principled = ...

		elif "MCPREP_specular" in node:
			if "specular" in img_sets:
				new_img = util.loadTexture(img_sets["specular"])
				node.image = new_img
				node.mute = False
				node.hide = False
			else:
				node.mute = True
				node.hide = True

		elif node.type == "TEX_IMAGE":
			# assume all unlabeled texture nodes should be the diffuse
			node["MCPREP_diffuse"] = True  # annotate node for future reference
			node.image = image
			node.mute = False
			node.hide = False
		else:
			continue

		changed = True

	return changed


def set_internal_texture(image, material, extra_passes=False):
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
	if "texture_swapped" in material:
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
		conf.log("Found no textures, asserting texture onto material")
		name = material.name+"_tex"
		if name not in bpy.data.textures:
			tex = bpy.data.textures.new(name=name,type="IMAGE")
		else:
			tex = bpy.data.textures[name]
		tex.image = image
		if material.texture_slots[0] == None:
			material.texture_slots.create(0)
		material.texture_slots[0].texture = tex
		material.texture_slots[0].texture["MCPREP_diffuse"] = True
		material.texture_slots[0].use = True
		base = 0

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
			f = img_sets.pop("normal")
			new_img = util.loadTexture(f)
			new_tex.image = new_img
			sl.texture = new_tex
			sl.texture["MCPREP_normal"] = True
			sl.use_map_normal = True
			sl.normal_factor = 0.1
			sl.use_map_color_diffuse = False
			sl.use_map_specular = False
			sl.use_map_alpha = False
			sl.blend_type = 'MIX'
			sl.use = True
		elif "spec" in img_sets and img_sets["spec"]:
			if tex and tex.name+"_s" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_s"]
			else:
				new_tex = bpy.data.textures.new(name=tex.name+"_s",type="IMAGE")
			if not sl:
				sl = material.texture_slots.create(i)
			f = img_sets.pop("specular")
			new_img = util.loadTexture(f)
			new_img.use_alpha = False  # would mess up material
			new_tex.image = new_img
			sl.texture = new_tex
			sl.texture["MCPREP_specular"] = True
			sl.use_map_normal = False
			sl.use_map_color_diffuse = False
			sl.use_map_specular = True
			sl.use_map_alpha = False
			sl.blend_type = 'MIX'
			sl.use = True
		elif "saturate" in img_sets:
			img_sets.pop("saturate")
			print("Running saturate")
			if canon not in conf.json_data['blocks']['desaturated']:
				continue
			if tex and tex.name+"_saturate" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name+"_saturate"]
			else:
				new_tex = bpy.data.textures.new(name=tex.name+"_saturate", type="BLEND")
			if not sl:
				sl = material.texture_slots.create(i)
			sl.texture = new_tex
			sl.texture["SATURATE"] = True
			sl.use_map_normal = False
			sl.use_map_color_diffuse = True
			sl.use_map_specular = False
			sl.use_map_alpha = False
			sl.blend_type = 'OVERLAY'
			sl.use = True
			new_tex.use_color_ramp = True
			for _ in range(len(new_tex.color_ramp.elements)-1):
				new_tex.color_ramp.elements.remove(new_tex.color_ramp.elements[0])
			desat_color = conf.json_data['blocks']['desaturated'][canon]
			if len(desat_color) < len(new_tex.color_ramp.elements[0].color):
				desat_color.append(1.0)
			new_tex.color_ramp.elements[0].color = desat_color

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
		elif "MCPREP_displace" in node and pass_name == "displace":
			return_node = node
		else:
			if not return_node:
				return_node = node
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
	"""Extract the image datablocks for a given material (prefer cycles).

	Returns {"diffuse":texture, "normal":None, ...}
	"""
	image_block = None
	passes = {"diffuse":None, "specular":None, "normal":None,
				"displace":None}

	if not material:
		return passes

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
	conf.log("Missing datablock detected: "+image.name)

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

def copy_texture_animation_pass_settings(mat):
	"""Get any animation settings for passes."""
	# Pre-copy any animated node settings before clearing nodes
	animated_data = {}
	if not mat.use_nodes:
		return {}
	for node in mat.node_tree.nodes:
		if node.type != "TEX_IMAGE":
			continue
		if not node.image:
			continue
		if not node.image.source == 'SEQUENCE':
			continue
		if "MCPREP_diffuse" in node:
			passname = "diffuse"
		elif "MCPREP_normal" in node:
			passname = "normal"
		elif "MCPREP_specular" in node:
			passname = "specular"
		elif "MCPREP_displace" in node:
			passname = "displace"
		else:
			if not animated_data.get("diffuse"):
				passname = "diffuse"
		animated_data[passname] = {
			"frame_duration": node.image_user.frame_duration,
			"frame_start": node.image_user.frame_start,
			"frame_offset": node.image_user.frame_offset
		}
	return animated_data


def apply_texture_animation_pass_settings(mat, animated_data):
	"""Apply animated texture settings for all given passes of dict."""

	if not mat.use_nodes:
		return {}

	node_diff = get_node_for_pass(mat, "diffuse")
	node_normal = get_node_for_pass(mat, "normal")
	node_specular = get_node_for_pass(mat, "specular")
	node_displace = get_node_for_pass(mat, "displace")

	for itm in animated_data:
		if itm == "diffuse" and node_diff:
			anim_node = node_diff
		elif itm == "normal" and node_normal:
			anim_node = node_normal
		elif itm == "specular" and node_specular:
			anim_node = node_specular
		elif itm == "displace" and node_displace:
			anim_node = node_displace
		else:
			continue

		anim_node.image_user.frame_duration = animated_data[itm]["frame_duration"]
		anim_node.image_user.frame_start = animated_data[itm]["frame_start"]
		anim_node.image_user.frame_offset = animated_data[itm]["frame_offset"]
		anim_node.image_user.use_auto_refresh = True
		anim_node.image_user.use_cyclic = True


def matgen_cycles_principled(mat, passes, use_reflections, only_solid):
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
		# Would have already checked for replacement textures by now, so skip
		return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	principled = nodes.new('ShaderNodeBsdfPrincipled')
	nodeTrans = nodes.new('ShaderNodeBsdfTransparent')
	nodeMix1 = nodes.new('ShaderNodeMixShader')
	nodeTexDiff = nodes.new('ShaderNodeTexImage')
	nodeTexNorm = nodes.new('ShaderNodeTexImage')
	nodeTexSpec = nodes.new('ShaderNodeTexImage')
	nodeSpecInv = nodes.new('ShaderNodeInvert')
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
	nodeSpecInv.label = "Spec Inverse"

	# set location and connect
	nodeTexDiff.location = (-400,0)
	nodeTexNorm.location = (-600,-275)
	nodeSaturateMix.location = (-200,0)
	nodeTexSpec.location = (-600,0)
	nodeSpecInv.location = (-400,-275)
	nodeNormal.location = (-400,-425)
	principled.location = (0,0)
	nodeTrans.location = (0,100)
	nodeMix1.location = (300,0)
	nodeOut.location = (500,0)
	if util.bv28():
		nodeTexDiff.location[0] -= 100
		nodeTexNorm.location[0] -= 200
		nodeTexSpec.location[0] -= 200

	# default links
	links.new(nodeTexDiff.outputs["Color"],nodeSaturateMix.inputs[1])
	links.new(nodeSaturateMix.outputs["Color"],principled.inputs[0])
	# links.new(nodeTexSpec.outputs["Color"],principled.inputs[5]) # Works better w/ packs
	links.new(nodeTexSpec.outputs["Color"],nodeSpecInv.inputs[1]) # "proper" way
	links.new(nodeSpecInv.outputs["Color"],principled.inputs[7]) # "proper" way
	links.new(nodeTexNorm.outputs["Color"],nodeNormal.inputs[1])
	links.new(nodeNormal.outputs["Normal"], principled.inputs["Normal"])

	# TODO: Use alpha socket of princpled node for newer blender versions
	links.new(nodeTexDiff.outputs["Alpha"],nodeMix1.inputs[0])
	links.new(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
	links.new(principled.outputs["BSDF"],nodeMix1.inputs[2])

	links.new(nodeMix1.outputs["Shader"],nodeOut.inputs[0])

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexSpec["MCPREP_specular"] = True
	nodeTexNorm["MCPREP_normal"] = True
	nodeNormal["MCPREP_normal"] = True # to also be also muted if no normal tex
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

	if hasattr(nodeTexDiff, "interpolation"): # 2.72+
		nodeTexDiff.interpolation = 'Closest'
		nodeTexSpec.interpolation = 'Closest'
	if hasattr(nodeTexSpec, "color_space"): # 2.7 and earlier 2.8 versions
		nodeTexSpec.color_space = 'NONE'  # for better interpretation of specmaps
		nodeTexNorm.color_space = 'NONE'  # for better interpretation of normals
	elif nodeTexSpec.image and hasattr(nodeTexSpec.image, "colorspace_settings"): # later 2.8 versions
		nodeTexSpec.image.colorspace_settings.name = 'Non-Color'
		if nodeTexNorm.image:
			nodeTexNorm.image.colorspace_settings.name = 'Non-Color'

	# apply additional settings
	if hasattr(mat, "cycles"):
		mat.cycles.sample_as_light = False
	addToAlpha = None
	if use_reflections and checklist(canon, "reflective"):
		principled.inputs[5].default_value = 0.5  # spec
		principled.inputs[7].default_value = 0.0  # roughness, used to be 0.05

		# Add to alpha math channel here to increase reflections even in
		# pure alpha-transparent spots, e.g. for glass
		addToAlpha = nodes.new('ShaderNodeMath')
		addToAlpha.location = (0, 200)
		# nodeSaturateMix.location = (-200,-200)
		addToAlpha.use_clamp = True
		addToAlpha.operation = 'ADD'
		addToAlpha.inputs[1].default_value = 0.2
		links.new(nodeTexDiff.outputs["Alpha"],addToAlpha.inputs[0])
		links.new(addToAlpha.outputs["Value"],nodeMix1.inputs[0])
	else:
		principled.inputs[5].default_value = 0.5  # set specular
		principled.inputs[7].default_value = 0.7  # set roughness

	waterHSV = None
	if checklist(canon, "water"):
		# principled.inputs[5].default_value = 1.0  # spec
		principled.inputs[7].default_value = 0.0  # roughness

		# addToAlpha.inputs[1].default_value = -0.1 # increase transparency

		# add HSV node for more user control
		waterHSV = nodes.new('ShaderNodeHueSaturation')
		waterHSV.location = (-200, -150)
		links.new(nodeSaturateMix.outputs["Color"], waterHSV.inputs[4])
		links.new(waterHSV.outputs["Color"], principled.inputs[0])

	if use_reflections and checklist(canon, "metallic"):
		principled.inputs[4].default_value = 1  # set metallic
		if principled.inputs[7].default_value < 0.2:  # roughness
			principled.inputs[7].default_value = 0.2
	else:
		principled.inputs[4].default_value = 0  # set dielectric


	if only_solid is True or checklist(canon, "solid"):
		# nodeMix1.inputs[0].default_value = 1 # no transparency
		nodes.remove(nodeTrans)
		nodes.remove(nodeMix1)
		if addToAlpha:
			nodes.remove(addToAlpha)
		# nodeDiff.location[1] += 150
		links.new(principled.outputs["BSDF"],nodeOut.inputs[0])

		# faster, and appropriate for non-transparent (and refelctive?) materials
		principled.distribution = 'GGX'
		if hasattr(mat, "blend_method"):
			mat.blend_method = 'OPAQUE' # eevee setting
	else:
		# non-solid (potentially, not necessarily though)
		if hasattr(mat, "blend_method"):  # 2.8 eevee settings
			# TODO: Work on finding the optimal decision here
			# clip could be better in cases of true/false transparency
			# could do work to detect this from the image directly..
			# though would be slower

			# noisy, but workable for partial trans; bad for materials with
			# no partial trans (makes view-through all somewhat noisy)
			# Note: placed with hasattr to reduce bugs, seemingly only on old
			# 2.80 build
			if hasattr(mat, "blend_method"):
				mat.blend_method = 'HASHED'
			if hasattr(mat, "shadow_method"):
				mat.shadow_method = 'HASHED'

			# best if there is no partial transparency
			# material.blend_method = 'CLIP' for no partial transparency
			# both work fine with depth of field.

			# but, BLEND does NOT work well with Depth of Field or layering

	nodeSaturateMix.inputs[0].default_value = 1.0
	nodeSaturateMix.blend_type = 'OVERLAY'
	nodeSaturateMix.mute = True
	nodeSaturateMix.hide = True
	if checklist(canon, "desaturated"):
		# Could potentially process image and determine if grayscale (mostly),
		# but would be slow. For now, explicitly pass in if saturated or not
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		if len(desat_color) < len(nodeSaturateMix.inputs[2].default_value):
			desat_color.append(1.0)
		nodeSaturateMix.inputs[2].default_value = desat_color
		if "texture_swapped" in mat:
			nodeSaturateMix.mute = False
			nodeSaturateMix.hide = False

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	return 0 # return 0 once implemented


def matgen_cycles_original(mat, passes, use_reflections, only_solid):
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
	animated_data = copy_texture_animation_pass_settings(mat)
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
	nodeTexDiff.location = (-600,0)
	nodeTexNorm.location = (-600,-275)
	nodeTexSpec.location = (-600,275)
	nodeNormal.location = (-400,-425)
	nodeGloss.location = (0,-150)
	nodeSaturateMix.location = (-400,0)
	nodeDiff.location = (-200,-150)
	nodeTrans.location = (-200,0)
	nodeMix1.location = (0,0)
	nodeMix2.location = (200,0)
	nodeOut.location = (400,0)
	if util.bv28():
		nodeTexDiff.location[0] -= 100
		nodeTexNorm.location[0] -= 200
		nodeTexSpec.location[0] -= 200

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

	if hasattr(nodeTexDiff, "interpolation"): # only avail 2.72+
		nodeTexDiff.interpolation = 'Closest'
		nodeTexSpec.interpolation = 'Closest' # should this be closest or not?
	if hasattr(nodeTexSpec, "color_space"): # 2.7 and earlier 2.8 versions
		nodeTexSpec.color_space = 'NONE'  # for better interpretation of specmaps
		nodeTexNorm.color_space = 'NONE'  # for better interpretation of normals
	elif nodeTexSpec.image and hasattr(nodeTexSpec.image, "colorspace_settings"): # 2.7 and earlier 2.8 versions
		nodeTexSpec.image.colorspace_settings.name = 'Non-Color'
		if nodeTexNorm.iamge:
			nodeTexNorm.iamge.colorspace_settings.name = 'Non-Color'

	#set other default values, e.g. the mixes
	nodeMix2.inputs[0].default_value = 0 # factor mix with glossy
	nodeGloss.inputs[1].default_value = 0.1 # roughness
	nodeNormal.inputs[0].default_value = 0.1 # tone down normal maps

	# the above are all default nodes. Now see if in specific lists
	if hasattr(mat, "cycles"):
		mat.cycles.sample_as_light = False
	if use_reflections and checklist(canon, "reflective"):
		nodeMix2.inputs[0].default_value = 0.3  # mix factor
		nodeGloss.inputs[1].default_value = 0.0 # roughness, used to be 0.05
	else:
		nodeMix2.mute = True
		nodeMix2.hide = True
		nodeGloss.mute = True
		nodeGloss.hide = True

	if checklist(canon, "water"):
		# setup the animation??
		nodeMix2.inputs[0].default_value = 0.2
		nodeGloss.inputs[1].default_value = 0.0
	if only_solid is True or checklist(canon, "solid"):
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
		if "texture_swapped" in mat:
			nodeSaturateMix.mute = False
			nodeSaturateMix.hide = False

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	return 0


def matgen_cycles_emit(mat, passes):
	"""Generates light emiting cycles material, with transaprency."""

	mat_gen = util.nameGeneralize(mat.name)
	canon, _ = get_mc_canonical_name(mat_gen)

	image_diff = passes["diffuse"]
	# image_norm = passes["normal"]
	# image_spec = passes["specular"]
	# image_disp = None # not used
	if image_diff==None:
		print("Could not find diffuse image, halting generation: "+mat.name)
		return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
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
	if util.bv28():
		nodeLightPath.location[0] -= 100
		nodeTexDiff.location[0] -= 100

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

	if hasattr(nodeTexDiff, "interpolation"): # 2.72+
		nodeTexDiff.interpolation = 'Closest'
	nodeTexDiff.image = image_diff
	nodeTexDiff["MCPREP_diffuse"] = True  # or call it emit?
	nodeEmitVisible.inputs[1].default_value = 1.0
	nodeFalloff.inputs[0].default_value = 30  # controls actual light emitted
	nodeFalloff.inputs[1].default_value = 0.03

	if hasattr(mat, "cycles"):
		mat.cycles.sample_as_light = True

	# 2.8 eevee settings
	if not checklist(canon, "solid") and hasattr(mat, "blend_method"):
		# TODO: Work on finding the optimal decision here
		# clip could be better in cases of true/false transparency
		# could do work to detect this from the image directly..
		# though would be slower

		# noisy, but workable for partial trans; bad for materials with
		# no partial trans (makes view-through all somewhat noisy)
		# Note: placed with hasattr to reduce bugs, seemingly only on old
		# 2.80 build
		if hasattr(mat, "blend_method"):
			mat.blend_method = 'HASHED'
		if hasattr(mat, "shadow_method"):
			mat.shadow_method = 'HASHED'

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	return 0
