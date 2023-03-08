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
	bpy.ops.mcprep.reload_materials()
	bpy.ops.mcprep.reload_models()
	conf.material_sync_cache = None


def get_mc_canonical_name(name):
	"""Convert a material name to standard MC name.

	Returns:
		canonical name, or fallback to generalized name (never returns None)
		form (mc, jmc, or mineways)
	"""
	general_name = util.nameGeneralize(name)
	if not conf.json_data:
		res = util.load_mcprep_json()
		if not res:
			return general_name, None

	# Special case to allow material names, e.g. in meshswap, to end in .emit
	# while still mapping to canonical names, to pick up features like animated
	# textures. Cross check that name isn't exactly .emit to avoid None return.
	if ".emit" in general_name and general_name != ".emit":
		general_name = general_name.replace(".emit", "")

	no_missing = "blocks" in conf.json_data
	no_missing &= "block_mapping_mc" in conf.json_data["blocks"]
	no_missing &= "block_mapping_jmc" in conf.json_data["blocks"]
	no_missing &= "block_mapping_mineways" in conf.json_data["blocks"]

	if no_missing is False:
		conf.log("Missing key values in json")
		return general_name, None

	# The below workaround is to account for the jmc2obj v113+ which changes
	# how mappings and assignments work.
	if general_name.startswith("minecraft_block-"):
		# minecraft_block-name maps to textures/block/name.png,
		# other options over block are: entity, models, etc.
		jmc_prefix = True
		general_name = name[len("minecraft_block-"):]
	else:
		jmc_prefix = False

	if general_name in conf.json_data["blocks"]["block_mapping_mc"]:
		canon = conf.json_data["blocks"]["block_mapping_mc"][general_name]
		form = "mc" if not jmc_prefix else "jmc2obj"
	elif general_name in conf.json_data["blocks"]["block_mapping_jmc"]:
		canon = conf.json_data["blocks"]["block_mapping_jmc"][general_name]
		form = "jmc2obj"
	elif general_name in conf.json_data["blocks"]["block_mapping_mineways"]:
		canon = conf.json_data["blocks"]["block_mapping_mineways"][general_name]
		form = "mineways"
	elif general_name.lower() in conf.json_data["blocks"]["block_mapping_jmc"]:
		canon = conf.json_data["blocks"]["block_mapping_jmc"][
			general_name.lower()]
		form = "jmc2obj"
	elif general_name.lower() in conf.json_data["blocks"]["block_mapping_mineways"]:
		canon = conf.json_data["blocks"]["block_mapping_mineways"][
			general_name.lower()]
		form = "mineways"
	else:
		conf.log("Canonical name not matched: " + general_name, vv_only=True)
		canon = general_name
		form = None

	if canon is None or canon == '':
		conf.log("Error: Encountered None canon value with " + str(general_name))
		canon = general_name

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
		resource_folder = bpy.path.abspath(bpy.context.scene.mcprep_texturepack_path)

	if not os.path.isdir(resource_folder):
		conf.log("Error, resource folder does not exist")
		return

	# Check multiple paths, picking the first match (order is important),
	# goal of picking out the /textures folder.
	check_dirs = [
		os.path.join(resource_folder, "textures"),
		os.path.join(resource_folder, "minecraft", "textures"),
		os.path.join(resource_folder, "assets", "minecraft", "textures")]
	for path in check_dirs:
		if os.path.isdir(path):
			resource_folder = path
			break

	search_paths = [
		resource_folder,
		# Both singular and plural shown below as it has varied historically.
		os.path.join(resource_folder, "blocks"),
		os.path.join(resource_folder, "block"),
		os.path.join(resource_folder, "items"),
		os.path.join(resource_folder, "item"),
		os.path.join(resource_folder, "entity"),
		os.path.join(resource_folder, "models"),
		os.path.join(resource_folder, "model"),
	]
	res = None

	# first see if subpath included is found, prioritize use of that
	extensions = [".png", ".jpg", ".jpeg"]
	if "/" in blockname:
		newpath = blockname.replace("/", os.path.sep)
		for ext in extensions:
			if os.path.isfile(os.path.join(resource_folder, newpath + ext)):
				res = os.path.join(resource_folder, newpath + ext)
				return res
		newpath = os.path.basename(blockname)  # case where goes into other subpaths
		for ext in extensions:
			if os.path.isfile(os.path.join(resource_folder, newpath + ext)):
				res = os.path.join(resource_folder, newpath + ext)
				return res

	# fallback (more common case), wide-search for
	for path in search_paths:
		if not os.path.isdir(path):
			continue
		for ext in extensions:
			check_path = os.path.join(path, blockname + ext)
			if os.path.isfile(check_path):
				res = os.path.join(path, blockname + ext)
				return res
	# Mineways fallback
	for suffix in ["-Alpha", "-RGB", "-RGBA"]:
		if blockname.endswith(suffix):
			res = os.path.join(
				resource_folder, "mineways_assets", "mineways" + suffix + ".png")
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
			jmc2obj += 1
		elif form == "mineways":
			mineways += 1
		else:
			mc += 1

	# more logic, e.g. count
	if mineways == 0 and jmc2obj == 0:
		res = None  # unknown
	elif mineways > 0 and jmc2obj == 0:
		res = "mineways"
	elif jmc2obj > 0 and mineways == 0:
		res = "jmc2obj"
	elif jmc2obj < mineways:
		res = "mineways"
	elif jmc2obj > mineways:
		res = "jmc2obj"
	else:
		res = None  # unknown

	return res  # one of jmc2obj, mineways, or None


def checklist(matName, listName):
	"""Helper to expand single wildcard within generalized material names"""
	if not conf.json_data:
		conf.log("No json_data for checklist to call from!")
	if "blocks" not in conf.json_data or listName not in conf.json_data["blocks"]:
		conf.log(
			"conf.json_data is missing blocks or listName " + str(listName))
		return False
	if matName in conf.json_data["blocks"][listName]:
		return True
	for name in conf.json_data["blocks"][listName]:
		if '*' not in name:
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
		_ = util.load_mcprep_json()

	newName = mat.name + '_tex'
	texList = mat.texture_slots.values()
	try:
		bpy.data.textures[texList[0].name].name = newName
	except:
		conf.log(
			'\twarning: material ' + mat.name + ' has no texture slot. skipping...')
		return

	# disable all but first slot, ensure first slot enabled
	mat.use_textures[0] = True
	diff_layer = 0
	spec_layer = None
	norm_layer = None
	disp_layer = None
	saturate_layer = None
	first_unused = None
	for index in range(1, len(texList)):
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
		conf.log("No diffuse-detected texture, skipping material: " + mat.name)
		return 1

	# strip out the .00#
	canon, _ = get_mc_canonical_name(util.nameGeneralize(mat.name))
	mat.use_nodes = False

	mat.use_transparent_shadows = True  # all materials receive trans
	mat.specular_intensity = 0
	mat.texture_slots[diff_layer].texture.use_interpolation = False
	mat.texture_slots[diff_layer].texture.filter_type = 'BOX'
	mat.texture_slots[diff_layer].texture.filter_size = 0
	mat.texture_slots[diff_layer].use_map_color_diffuse = True
	mat.texture_slots[diff_layer].diffuse_color_factor = 1

	if only_solid is False and not checklist(canon, "solid"):  # alpha default on
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

	if checklist(canon, "emit") or "emit" in mat.name.lower():
		mat.emit = 1
	else:
		mat.emit = 0

	# cycle through and see if the layer exists to enable/disable blend
	if not checklist(canon, "desaturated"):
		pass
	else:
		diff_img = mat.texture_slots[diff_layer].texture.image
		is_grayscale = is_image_grayscale(diff_img)

		# TODO: code is duplicative to below, consolidate later
		if mat.name + "_saturate" in bpy.data.textures:
			new_tex = bpy.data.textures[mat.name + "_saturate"]
		else:
			new_tex = bpy.data.textures.new(name=mat.name + "_saturate", type="BLEND")
		if not saturate_layer:
			if not first_unused:
				first_unused = len(mat.texture_slots) - 1  # force reuse last at worst
			sl = mat.texture_slots.create(first_unused)
		else:
			sl = mat.texture_slots[saturate_layer]
		sl.texture = new_tex
		sl.texture["SATURATE"] = True
		sl.use_map_normal = False
		sl.use_map_color_diffuse = True
		sl.use_map_specular = False
		sl.use_map_alpha = False
		sl.blend_type = 'MULTIPLY'  # changed from OVERLAY
		sl.use = bool(is_grayscale)  # turns off if not grayscale (or None)
		new_tex.use_color_ramp = True
		for _ in range(len(new_tex.color_ramp.elements) - 1):
			new_tex.color_ramp.elements.remove(new_tex.color_ramp.elements[0])
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		if len(desat_color) < len(new_tex.color_ramp.elements[0].color):
			desat_color.append(1.0)
		new_tex.color_ramp.elements[0].color = desat_color

	return 0


def matprep_cycles(
	mat, passes, use_reflections, use_principled, only_solid, pack_format, use_emission_nodes):
	"""Determine how to prep or generate the cycles materials.

	Args:
		mat: the existing material
		passes: dictionary struc of all found pass names
		use_reflections: whether to turn reflections on
		use_principled: if available and cycles, use principled node
		saturate: if a desaturated texture (by canonical resource), add color
		pack_format: which format of PBR, string ("Simple", Specular", "SEUS")

	Returns:
		int: 0 only if successful, otherwise None or other
	"""
	if util.bv28():
		# ensure nodes are enabled esp. after importing from BI scenes
		mat.use_nodes = True

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)
	use_emission = checklist(canon, "emit") or "emit" in mat.name.lower()

	# TODO: Update different options for water before enabling this
	# if use_reflections and checklist(canon, "water"):
	#	res = matgen_special_water(mat, passes)
	# if use_reflections and checklist(canon, "glass"):
	#	res = matgen_special_glass(mat, passes)
	if pack_format == "simple" and util.bv28():
		res = matgen_cycles_simple(
			mat, passes, use_reflections, use_emission, only_solid, use_principled, use_emission_nodes)
	elif use_principled and hasattr(bpy.types, 'ShaderNodeBsdfPrincipled'):
		res = matgen_cycles_principled(
			mat, passes, use_reflections, use_emission, only_solid, pack_format, use_emission_nodes)
	else:
		res = matgen_cycles_original(
			mat, passes, use_reflections, use_emission, only_solid, pack_format, use_emission_nodes)
	return res


def set_texture_pack(material, folder, use_extra_passes):
	"""Replace existing material's image with texture pack's.

	Run through and check for each if counterpart material exists, then
	run the swap (and auto load e.g. normals and specs if avail.)
	"""
	mc_name, _ = get_mc_canonical_name(material.name)
	image = find_from_texturepack(mc_name, folder)
	if image is None:
		return 0

	image_data = util.loadTexture(image)
	engine = bpy.context.scene.render.engine

	if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		_ = set_cycles_texture(image_data, material, True)
	elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		_ = set_internal_texture(image_data, material, use_extra_passes)
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
			if status:
				count += 1
	elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		for mat in materials:
			status = set_cycles_texture(image, mat)
			if status:
				count += 1
	return count


def set_cycles_texture(image, material, extra_passes=False):
	"""
	Used by skin swap and assiging missing textures or tex swapping.
	Args:
		image: already loaded image datablock
		material: existing material datablock
		extra_passes: whether to include or hard exclude non diffuse passes
	"""
	conf.log("Setting cycles texture for img: {} mat: {}".format(
		image.name, material.name))
	if material.node_tree is None:
		return False
	# check if there is more data to see pass types
	img_sets = {}
	if extra_passes:
		img_sets = find_additional_passes(image.filepath)
	changed = False

	is_grayscale = False

	canon, _ = get_mc_canonical_name(util.nameGeneralize(material.name))
	if checklist(canon, "desaturated"):
		is_grayscale = is_image_grayscale(image)

	for node in material.node_tree.nodes:
		if node.type == "MIX_RGB" and "SATURATE" in node:
			node.mute = not is_grayscale
			node.hide = not is_grayscale
			conf.log(" mix_rgb to saturate texture")

		# if node.type != "TEX_IMAGE": continue

		# check to see nodes and their respective pre-named field,
		# saved as an attribute on the node
		if "MCPREP_diffuse" in node:
			node.image = image
			node.mute = False
			node.hide = False
		elif "MCPREP_normal" in node and node.type == 'TEX_IMAGE':
			if "normal" in img_sets:
				new_img = util.loadTexture(img_sets["normal"])
				node.image = new_img
				util.apply_colorspace(node, 'Non-Color')
				node.mute = False
				node.hide = False
			else:
				node.mute = True
				node.hide = True

				# remove the link between normal map and principled shader
				# normal_map = node.outputs[0].links[0].to_node
				# principled = ...

		elif "MCPREP_specular" in node and node.type == 'TEX_IMAGE':
			if "specular" in img_sets:
				new_img = util.loadTexture(img_sets["specular"])
				node.image = new_img
				node.mute = False
				node.hide = False
				util.apply_colorspace(node, 'Non-Color')
			else:
				node.mute = True
				node.hide = True

		elif node.type == "TEX_IMAGE":
			# assume all unlabeled texture nodes should be the diffuse pass
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
	canon, _ = get_mc_canonical_name(util.nameGeneralize(material.name))

	is_grayscale = False
	if checklist(canon, "desaturated"):
		is_grayscale = is_image_grayscale(image)

	img_sets = {}
	if extra_passes:
		img_sets = find_additional_passes(image.filepath)
	if is_grayscale is True:
		img_sets["saturate"] = True

	base = None
	tex = None

	# set primary diffuse color as the first image found
	for i, sl in enumerate(material.texture_slots):
		if sl is None or sl.texture is None or sl.texture.type != 'IMAGE':
			continue
		sl.texture.image = image
		sl.use = True
		tex = sl.texture
		base = i
		sl.use_map_normal = False
		sl.use_map_color_diffuse = True
		sl.use_map_specular = False
		sl.blend_type = 'MIX'
		break

	# if no textures found, assert adding this one as the first
	if tex is None:
		conf.log("Found no textures, asserting texture onto material")
		name = material.name + "_tex"
		if name not in bpy.data.textures:
			tex = bpy.data.textures.new(name=name, type="IMAGE")
		else:
			tex = bpy.data.textures[name]
		tex.image = image
		if material.texture_slots[0] is None:
			material.texture_slots.create(0)
		material.texture_slots[0].texture = tex
		material.texture_slots[0].texture["MCPREP_diffuse"] = True
		material.texture_slots[0].use = True
		base = 0

	# go through and turn off any previous passes not in img_sets
	for i, sl in enumerate(material.texture_slots):
		if i == base:
			continue  # skip primary texture set
		if "normal" in img_sets and img_sets["normal"]:  # pop item each time
			if tex and tex.name + "_n" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name + "_n"]
			else:
				new_tex = bpy.data.textures.new(
					name=tex.name + "_n", type="IMAGE")
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
			if tex and tex.name + "_s" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name + "_s"]
			else:
				new_tex = bpy.data.textures.new(
					name=tex.name + "_s", type="IMAGE")
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
			if not checklist(canon, "desaturated"):
				continue
			if tex and tex.name + "_saturate" in bpy.data.textures:
				new_tex = bpy.data.textures[tex.name + "_saturate"]
			else:
				new_tex = bpy.data.textures.new(
					name=tex.name + "_saturate", type="BLEND")
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
			for _ in range(len(new_tex.color_ramp.elements) - 1):
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
		if not (sl and sl.use and sl.texture is not None
				and hasattr(sl.texture, "image")
				and sl.texture.image is not None):
			continue
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

	Returns {"diffuse":texture.image, "normal":node.image "spec":None, ...}
	"""
	passes = {
		"diffuse": None, "specular": None, "normal": None, "displace": None}

	if not material:
		return passes

	# first try cycles materials, fall back to internal if not present
	if material.use_nodes is True:
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
			if not (sl and sl.use and sl.texture is not None
					and hasattr(sl.texture, "image")
					and sl.texture.image is not None):
				continue
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
	conf.log("\tFind additional passes for: " + image_file, vv_only=True)
	if not os.path.isfile(abs_img_file):
		return {}

	img_dir = os.path.dirname(abs_img_file)
	img_base = os.path.basename(abs_img_file)
	base_name = os.path.splitext(img_base)[0]  # remove extension

	# valid extentsions and ending names for pass types
	exts = [".png", ".jpg", ".jpeg", ".tiff"]
	normal = [" n", "_n", "-n", " normal", "_norm", "_nrm", " normals"]
	spec = [" s", "_s", "-s", " specular", "_spec"]
	disp = [" d", "_d", "-d", " displace", "_disp", " bump", " b", "_b", "-b"]
	res = {"diffuse": image_file}

	# find lowercase base name matching with valid extentions
	filtered_files = []
	for f in os.listdir(img_dir):
		if not f.lower().startswith(base_name.lower()):
			continue
		if not os.path.isfile(os.path.join(img_dir, f)):
			continue
		if os.path.splitext(f)[-1].lower() not in exts:
			continue
		filtered_files.append(f)

	# now do narrow matching based on each extention name type
	for filtered in filtered_files:
		this_base = os.path.splitext(filtered)[0]
		for npass in normal:
			if this_base.lower() == (base_name + npass).lower():
				res["normal"] = os.path.join(img_dir, filtered)
		for spass in spec:
			if this_base.lower() == (base_name + spass).lower():
				res["specular"] = os.path.join(img_dir, filtered)
		for dpass in disp:
			if this_base.lower() == (base_name + dpass).lower():
				res["displace"] = os.path.join(img_dir, filtered)

	return res


def replace_missing_texture(image):
	"""If image missing from image datablock, replace from texture pack.

	Image block name could be the diffuse or any other pass of material, and
	should handle accordingly
	"""

	if image is None:
		return False
	if image.source == 'SEQUENCE' and os.path.isfile(bpy.path.abspath(image.filepath)):
		# technically the next statement should prevail, but this filecheck
		# addresses animated textures who show up without any size/pixel data
		# just after a reload (even though functional)
		return False
	if image.size[0] != 0 and image.size[1] != 0:
		# Non zero means currently loaded, but could be lost on reload
		if image.packed_file:
			# only assume safe if packed...
			return False
		elif os.path.isfile(bpy.path.abspath(image.filepath)):
			# ... or the filepath is present.
			return False
	conf.log("Missing datablock detected: " + image.name)

	name = image.name
	if len(name) > 4 and name[-4] == ".":
		name = name[:-4]  # cuts off e.g. .png
	elif len(name) > 5 and name[-5] == ".":
		name = name[:-5]  # cuts off e.g. .jpeg
	canon, _ = get_mc_canonical_name(name)
	# TODO: detect for pass structure like normal and still look for right pass
	image_path = find_from_texturepack(canon)
	if not image_path:
		return False
	image.filepath = image_path
	# image.reload() # not needed?
	# pack?

	return True  # updated image block


def is_image_grayscale(image):
	"""Returns true if image data is all grayscale, false otherwise"""

	def rgb_to_saturation(r, g, b):
		"""Converter 0-1 rgb values back to 0-1 saturation value"""
		mx = max(r, g, b)
		if mx == 0:
			return 0
		mn = min(r, g, b)
		df = mx - mn
		return (df / mx)

	if not image:
		return None
	conf.log("Checking image for grayscale " + image.name, vv_only=True)
	if 'grayscale' in image:  # cache
		return image['grayscale']
	if not image.pixels:
		conf.log("Not an image / no pixels", vv_only=True)
		return None

	# setup sampling to limit number of processed pixels
	max_samples = 1024  # A 32 by 32 image. May be higher with rounding.
	pxl_count = len(image.pixels) / image.channels
	aspect = image.size[0] / image.size[1]
	datablock_copied = False

	if pxl_count > max_samples:
		imgcp = image.copy()  # Duplicate the datablock

		# Find new pixel sizes keeping aspect ratio, equation of:
		# 1024 = nwith * nheight
		# 1024 = (nheight * aspect) * nheight
		# nheight = sqrtoot(1024 / aspect)
		nheight = (1024 / aspect)**0.5
		imgcp.scale(int(nheight * aspect), int(nheight))
		pxl_count = imgcp.size[0] * imgcp.size[1]
		datablock_copied = True
	else:
		imgcp = image

	# Pixel by pixel saturation checks, with some wiggle room thresholds
	thresh = 0.1  # treat saturated if any more than 10%

	# max pixels above thresh to return as saturated,
	# 15% is chosen as ~double the % of "yellow" pixels in vanilla jungle leaves
	max_thresh = 0.15 * pxl_count

	# running count to check against
	pixels_saturated = 0

	is_grayscale = True  # True until proven false.

	# check all pixels until exceeded threshold.
	for ind in range(int(pxl_count))[::]:
		ind = ind * imgcp.channels  # could be rgb or rgba
		if imgcp.channels > 3 and imgcp.pixels[ind + 3] == 0:
			continue  # skip alpha pixels during check
		this_saturated = rgb_to_saturation(
			imgcp.pixels[ind],
			imgcp.pixels[ind + 1],
			imgcp.pixels[ind + 2])
		if this_saturated > thresh:
			pixels_saturated += 1
		if pixels_saturated >= max_thresh:
			is_grayscale = False
			conf.log("Image not grayscale: " + image.name, vv_only=True)
			break

	if datablock_copied:  # Cleanup if image was copied to scale down size.
		bpy.data.images.remove(imgcp)

	image['grayscale'] = is_grayscale  # set cache
	conf.log("Image is grayscale: " + image.name, vv_only=True)
	return is_grayscale


def set_saturation_material(mat):
	"""Update material to be saturated or not"""
	if not mat:
		return

	canon, _ = get_mc_canonical_name(mat.name)
	if not checklist(canon, "desaturated"):
		conf.log("debug: not eligible for saturation", vv_only=True)
		return

	conf.log("Running set_saturation on " + mat.name, vv_only=True)
	diff_pass = get_node_for_pass(mat, "diffuse")
	if not diff_pass:
		return
	diff_img = diff_pass.image

	if not diff_img:
		conf.log("debug: No diffuse", vv_only=True)
		return

	saturate = is_image_grayscale(diff_img)

	desat_color = conf.json_data['blocks']['desaturated'][canon]
	engine = bpy.context.scene.render.engine

	if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		# get the saturation textureslot, or create
		sat_slot_ind = None
		first_unused = None
		for index in range(len(mat.texture_slots)):
			slot = mat.texture_slots[index]
			if not slot or not slot.texture:
				if not first_unused:
					first_unused = index
				continue
			elif "SATURATE" not in slot.texture:
				continue
			sat_slot_ind = index
			break
		if not sat_slot_ind:
			return
		mat.use_textures[sat_slot_ind] = bool(saturate)

	elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		sat_node = None
		for node in mat.node_tree.nodes:
			if "SATURATE" not in node:
				continue
			sat_node = node
			break

		if not sat_node:
			return  # requires regenerating material to add back
		if len(desat_color) == 3:
			desat_color += [1]  # add in alpha

		sat_node_in = get_node_socket(node, is_input=True) # Get the node sockets in a version agnostic way	
		sat_node.inputs[sat_node_in[2]].default_value = desat_color
		sat_node.mute = not bool(saturate)
		sat_node.hide = not bool(saturate)


def create_node(tree_nodes, node_type, **attrs):
	"""Create node with default attributes

	Args:
		tree_nodes: the material node tree's nodes
		node_type: the type of the node
		**attrs: set attributes if that node type has
			(eg: location, name, blend_type...)
			"node_tree" can be referencing nodegroup or name of that nodegroup
			"hide_sockets" to hide the sockets only display linked when need
	"""
	if node_type == 'ShaderNodeMixRGB':  # MixRGB in 3.4
		if util.min_bv((3, 4, 0)):
			node = tree_nodes.new('ShaderNodeMix')
			node.data_type = 'RGBA'
		else:
			node = tree_nodes.new('ShaderNodeMixRGB')
	else:
		node = tree_nodes.new(node_type)
	for attr, value in attrs.items():
		if hasattr(node, attr) and attr != 'node_tree':
			setattr(node, attr, value)
		elif attr == 'node_tree':  # node group
			assign = bpy.data.node_groups[value] if type(value) is str else value
			setattr(node, attr, assign)
		elif attr == 'hide_sockets':  # option to hide socket for big node
			node.inputs.foreach_set('hide', [value] * len(node.inputs))
			node.outputs.foreach_set('hide', [value] * len(node.outputs))
	return node


def get_node_socket(node, is_input=True):
	"""Gets the input or output sockets indicies for node"""
	n_type = node.bl_idname
	if n_type == 'ShaderNodeMix' or n_type == 'ShaderNodeMixRGB':
		# Mix Color in 3.4 use socket indicies 0, 6, 7 for Factor, Color inputs
		# and output with 2.
		# MixRGB uses 0, 1, 2 and 0
		if util.min_bv((3, 4, 0)):
			if node.data_type == 'RGBA':
				inputs, outputs = [0, 6, 7], [2]
		else:
			inputs, outputs = [0, 1, 2], [0]
	else:
		inputs = [i for i in range(len(node.inputs))]
		outputs = [i for i in range(len(node.outputs))]
	return inputs if is_input else outputs

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


def texgen_specular(mat, passes, nodeInputs, use_reflections):

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	# Define links and nodes
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links

	# Define the diffuse, normal, and specular nodes
	image_diff = passes["diffuse"]
	image_norm = passes["normal"]
	image_spec = passes["specular"]

	# Creates the necessary nodes
	nodeTexDiff = create_node(
		nodes, "ShaderNodeTexImage",
		name="Diffuse Texture",
		label="Diffuse Texture",
		location=(-380, 140),
		interpolation='Closest')
	nodeTexNorm = create_node(
		nodes, "ShaderNodeTexImage",
		name="Normal Texture",
		label="Normal Texture",
		location=(-680, -500))
	nodeTexSpec = create_node(
		nodes, "ShaderNodeTexImage",
		name="Specular Texture",
		label="Specular Texture",
		location=(-380, -180),
		interpolation='Closest')
	nodeSaturateMix = create_node(
		nodes, "ShaderNodeMixRGB",
		name="Add Color",
		label="Add Color",
		location=(-80, 140),
		blend_type='MULTIPLY',
		mute=True,
		hide=True)

	nodeSpecInv = create_node(
		nodes, "ShaderNodeInvert",
		name="Specular Inverse",
		label="Specular Inverse",
		location=(-80, -280))
	nodeNormalInv = create_node(
		nodes, "ShaderNodeRGBCurve",
		name="Normal Inverse",
		label="Normal Inverse",
		location=(-380, -500))
	nodeNormal = create_node(
		nodes, "ShaderNodeNormalMap",
		location=(-80, -500))

	# Sets values
	nodeSaturateMix.inputs[0].default_value = 1.0  # Graystyle Blending
	nodeNormalInv.mapping.curves[1].points[0].location = (0, 1)
	nodeNormalInv.mapping.curves[1].points[1].location = (1, 0)

	# Get MixRGB sockets
	saturateMixIn = get_node_socket(nodeSaturateMix)
	saturateMixOut = get_node_socket(nodeSaturateMix, is_input=False)

	# Links the nodes to the reroute nodes.
	links.new(nodeTexDiff.outputs["Color"], nodeSaturateMix.inputs[saturateMixIn[1]])
	links.new(nodeTexNorm.outputs["Color"], nodeNormalInv.inputs["Color"])
	links.new(nodeNormalInv.outputs["Color"], nodeNormal.inputs["Color"])
	links.new(nodeTexSpec.outputs["Color"], nodeSpecInv.inputs["Color"])

	for i in nodeInputs[0]:
		links.new(nodeSaturateMix.outputs[saturateMixOut[0]], i)
	for i in nodeInputs[1]:
		links.new(nodeTexDiff.outputs["Alpha"], i)
	if image_spec and use_reflections:
		for i in nodeInputs[3]:
			links.new(nodeSpecInv.outputs["Color"], i)
		for i in nodeInputs[5]:
			links.new(nodeTexSpec.outputs["Color"], i)
	for i in nodeInputs[6]:
		links.new(nodeNormal.outputs["Normal"], i)

	# Mutes necessary nodes if no specular map
	if image_spec:
		nodeTexSpec.image = image_spec
	else:
		nodeTexSpec.mute = True

	# Mutes necessary nodes if no normal map
	if image_norm:
		nodeTexNorm.image = image_norm
	else:
		nodeTexNorm.mute = True
		nodeNormalInv.mute = True
		nodeNormal.mute = True

	# Update to use non-color data for spec and normal
	util.apply_colorspace(nodeTexSpec, 'Non-Color')
	util.apply_colorspace(nodeTexNorm, 'Non-Color')

	# Graystyle Blending
	if not checklist(canon, "desaturated"):
		pass
	elif not is_image_grayscale(image_diff):
		pass
	else:
		conf.log("Texture desaturated: " + canon, vv_only=True)
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		if len(desat_color) < len(nodeSaturateMix.inputs[saturateMixIn[2]].default_value):
			desat_color.append(1.0)
		nodeSaturateMix.inputs[saturateMixIn[2]].default_value = desat_color
		nodeSaturateMix.mute = False
		nodeSaturateMix.hide = False

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexSpec["MCPREP_specular"] = True
	nodeTexNorm["MCPREP_normal"] = True
	# to also be also muted if no normal tex
	nodeNormal["MCPREP_normal"] = True
	nodeSaturateMix["SATURATE"] = True
	# nodeTexDisp["MCPREP_disp"] = True
	nodeTexDiff.image = image_diff


def texgen_seus(mat, passes, nodeInputs, use_reflections, use_emission):

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	# Define links and nodes
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links

	# Define the diffuse, normal, and specular nodes
	image_diff = passes["diffuse"]
	image_norm = passes["normal"]
	image_spec = passes["specular"]

	# Creates the necessary nodes
	nodeTexDiff = create_node(
		nodes, "ShaderNodeTexImage",
		name="Diffuse Texture",
		label="Diffuse Texture",
		location=(-380, 140),
		interpolation='Closest')
	nodeTexNorm = create_node(
		nodes, "ShaderNodeTexImage",
		name="Normal Texture",
		label="Normal Texture",
		location=(-680, -500))
	nodeTexSpec = create_node(
		nodes, "ShaderNodeTexImage",
		name="Specular Texture",
		label="Specular Texture",
		location=(-580, -180),
		interpolation='Closest')
	nodeSaturateMix = create_node(
		nodes, "ShaderNodeMixRGB",
		name="Add Color",
		label="Add Color",
		location=(-80, 140),
		blend_type='MULTIPLY',
		mute=True,
		hide=True)

	nodeSpecInv = create_node(
		nodes, "ShaderNodeInvert",
		name="Smooth Inverse",
		label="Smooth Inverse",
		location=(-80, -280))
	nodeSeperate = create_node(
		nodes, "ShaderNodeSeparateRGB",
		name="RGB Seperation",
		label="RGB Seperation",
		location=(-280, -280))
	nodeNormal = create_node(
		nodes, "ShaderNodeNormalMap",
		location=(-80, -500))
	nodeNormalInv = create_node(
		nodes, "ShaderNodeRGBCurve",
		name="Normal Inverse",
		label="Normal Inverse",
		location=(-380, -500))

	# Sets values
	nodeSaturateMix.inputs[0].default_value = 1.0  # Graystyle Blending
	nodeNormalInv.mapping.curves[1].points[0].location = (0, 1)
	nodeNormalInv.mapping.curves[1].points[1].location = (1, 0)

	# Get MixRGB sockets
	saturateMixIn = get_node_socket(nodeSaturateMix)
	saturateMixOut = get_node_socket(nodeSaturateMix, is_input=False)

	# Links the nodes to the reroute nodes.
	links.new(nodeTexDiff.outputs["Color"], nodeSaturateMix.inputs[saturateMixIn[1]])
	links.new(nodeTexNorm.outputs["Color"], nodeNormalInv.inputs["Color"])
	links.new(nodeNormalInv.outputs["Color"], nodeNormal.inputs["Color"])
	links.new(nodeTexSpec.outputs["Color"], nodeSeperate.inputs["Image"])
	links.new(nodeSeperate.outputs["R"], nodeSpecInv.inputs["Color"])

	for i in nodeInputs[0]:
		if i == nodeSaturateMix.outputs[saturateMixOut[0]]:
			continue
		links.new(nodeSaturateMix.outputs[saturateMixOut[0]], i)
	for i in nodeInputs[1]:
		links.new(nodeTexDiff.outputs["Alpha"], i)
	if image_spec and use_reflections:
		if use_emission:
			for i in nodeInputs[2]:
				links.new(nodeSeperate.outputs["B"], i)
		for i in nodeInputs[4]:
			links.new(nodeSeperate.outputs["G"], i)
		for i in nodeInputs[3]:
			links.new(nodeSpecInv.outputs["Color"], i)
	for i in nodeInputs[6]:
		links.new(nodeNormal.outputs["Normal"], i)

	# Mutes necessary nodes if no specular map
	if image_spec:
		nodeTexSpec.image = image_spec
		nodeTexSpec.mute = False
		nodeSeperate.mute = False
	else:
		nodeTexSpec.mute = True
		nodeSeperate.mute = True

	# Mutes necessary nodes if no normal map
	if image_norm:
		nodeTexNorm.image = image_norm
		nodeTexNorm.mute = False
		nodeNormalInv.mute = False
		nodeNormal.mute = False
	else:
		nodeTexNorm.mute = True
		nodeNormalInv.mute = True
		nodeNormal.mute = True

	# Update to use non-color data for spec and normal
	util.apply_colorspace(nodeTexSpec, 'Non-Color')
	util.apply_colorspace(nodeTexNorm, 'Non-Color')

	# Graystyle Blending
	if not checklist(canon, "desaturated"):
		pass
	elif not is_image_grayscale(image_diff):
		pass
	else:
		conf.log("Texture desaturated: " + canon, vv_only=True)
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		desat_cmpr = len(nodeSaturateMix.inputs[saturateMixIn[2]].default_value)
		if len(desat_color) < desat_cmpr:
			desat_color.append(1.0)
		nodeSaturateMix.inputs[saturateMixIn[2]].default_value = desat_color
		nodeSaturateMix.mute = False
		nodeSaturateMix.hide = False

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexSpec["MCPREP_specular"] = True
	nodeTexNorm["MCPREP_normal"] = True
	# to also be also muted if no normal tex
	nodeNormal["MCPREP_normal"] = True
	nodeSaturateMix["SATURATE"] = True
	# nodeTexDisp["MCPREP_disp"] = True
	nodeTexDiff.image = image_diff


def matgen_cycles_simple(
	mat, passes, use_reflections, use_emission, only_solid, use_principled, use_emission_nodes):
	"""Generate principled cycles material."""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	image_diff = passes["diffuse"]

	if not image_diff:
		print("Could not find diffuse image, halting generation: " + mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		if image_diff.source != 'SEQUENCE':
			# Common non animated case; this means the image is missing and would
			# have already checked for replacement textures by now, so skip.
			return
		if not os.path.isfile(bpy.path.abspath(image_diff.filepath)):
			# can't check size or pixels as it often is not immediately avaialble
			# so instead, check against firs frame of sequence to verify load
			return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	nodeTexDiff = create_node(
		nodes, "ShaderNodeTexImage",
		name="Diffuse Texture",
		label="Diffuse Texture",
		location=(0, 0),
		interpolation='Closest',
		image=image_diff)
	nodeSaturateMix = create_node(
		nodes, "ShaderNodeMixRGB",
		name="Add Color",
		label="Add Color",
		location=(300, 0),
		blend_type='MULTIPLY',
		mute=True,
		hide=True)

	principled = create_node(nodes, "ShaderNodeBsdfPrincipled", location=(600, 0))
	node_out = create_node(nodes, "ShaderNodeOutputMaterial", location=(900, 0))

	# Sets default reflective values
	if use_reflections and checklist(canon, "reflective"):
		principled.inputs["Roughness"].default_value = 0
	else:
		principled.inputs["Roughness"].default_value = 0.7

	# Sets default metallic values
	if use_reflections and checklist(canon, "metallic"):
		principled.inputs["Metallic"].default_value = 1
		if principled.inputs["Roughness"].default_value < 0.2:
			principled.inputs["Roughness"].default_value = 0.2
	else:
		principled.inputs["Metallic"].default_value = 0

	# Get MixRGB sockets
	saturateMixIn = get_node_socket(nodeSaturateMix)
	saturateMixOut = get_node_socket(nodeSaturateMix, is_input=False)

	# Set values.
	# Specular causes issues with how blocks look, so let's disable it.
	nodeSaturateMix.inputs[saturateMixIn[0]].default_value = 1.0
	principled.inputs["Specular"].default_value = 0

	# Connect nodes.
	links.new(nodeTexDiff.outputs[0], nodeSaturateMix.inputs[saturateMixIn[1]])
	links.new(nodeSaturateMix.outputs[saturateMixOut[0]], principled.inputs[0])
	links.new(principled.outputs["BSDF"], node_out.inputs[0])

	if only_solid is True or checklist(canon, "solid"):
		# faster, and appropriate for non-transparent (and refelctive?) materials
		principled.distribution = 'GGX'
		if hasattr(mat, "blend_method"):
			mat.blend_method = 'OPAQUE'  # eevee setting
	else:
		# non-solid (potentially, not necessarily though)
		links.new(nodeTexDiff.outputs[1], principled.inputs["Alpha"])
		if hasattr(mat, "blend_method"):  # 2.8 eevee settings
			if hasattr(mat, "blend_method"):
				mat.blend_method = 'HASHED'
			if hasattr(mat, "shadow_method"):
				mat.shadow_method = 'HASHED'
	
	if use_emission_nodes and use_emission:
		inputs = [inp.name for inp in principled.inputs]
		if 'Emission Strength' in inputs:  # Later 2.9 versions only.
			principled.inputs['Emission Strength'].default_value = 1
		links.new(
			nodeSaturateMix.outputs[saturateMixOut[0]],
			principled.inputs["Emission"])

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	# Graystyle Blending
	if not checklist(canon, "desaturated"):
		pass
	elif not is_image_grayscale(image_diff):
		pass
	else:
		conf.log("Texture desaturated: " + canon, vv_only=True)
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		desat_cmpr = len(nodeSaturateMix.inputs[saturateMixIn[2]].default_value)
		if len(desat_color) < desat_cmpr:
			desat_color.append(1.0)
		nodeSaturateMix.inputs[saturateMixIn[2]].default_value = desat_color
		nodeSaturateMix.mute = False
		nodeSaturateMix.hide = False

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeSaturateMix["SATURATE"] = True

	return 0


def matgen_cycles_principled(
	mat, passes, use_reflections, use_emission, only_solid, pack_format, use_emission_nodes):
	"""Generate principled cycles material"""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	image_diff = passes["diffuse"]

	if not image_diff:
		print("Could not find diffuse image, halting generation: " + mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		if image_diff.source != 'SEQUENCE':
			# Common non animated case; this means the image is missing and would
			# have already checked for replacement textures by now, so skip
			return
		if not os.path.isfile(bpy.path.abspath(image_diff.filepath)):
			# can't check size or pixels as it often is not immediately avaialble
			# so instead, check against first frame of sequence to verify load
			return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	principled = create_node(
		nodes, "ShaderNodeBsdfPrincipled", location=(120, 0))
	nodeTrans = create_node(
		nodes, "ShaderNodeBsdfTransparent", location=(420, 140))
	nodeMixTrans = create_node(
		nodes, "ShaderNodeMixShader", location=(620, 0))
	nodeOut = create_node(
		nodes, "ShaderNodeOutputMaterial", location=(820, 0))

	# Sets default transparency value
	nodeMixTrans.inputs[0].default_value = 1
	
	# Sets default reflective values
	if use_reflections and checklist(canon, "reflective"):
		principled.inputs["Roughness"].default_value = 0
	else:
		principled.inputs["Roughness"].default_value = 0.7

	# Sets default metallic values
	if use_reflections and checklist(canon, "metallic"):
		principled.inputs["Metallic"].default_value = 1
		if principled.inputs["Roughness"].default_value < 0.2:
			principled.inputs["Roughness"].default_value = 0.2
	else:
		principled.inputs["Metallic"].default_value = 0

	# Connect nodes
	links.new(nodeTrans.outputs["BSDF"], nodeMixTrans.inputs[1])
	links.new(nodeMixTrans.outputs["Shader"], nodeOut.inputs[0])

	nodeEmit = create_node(
			nodes, "ShaderNodeEmission", location=(120, 140))
	nodeEmitCam = create_node(
			nodes, "ShaderNodeEmission", location=(120, 260))
	nodeMixEmit = create_node(
			nodes, "ShaderNodeMixShader", location=(420, 0))
	if use_emission_nodes:
		# Create emission nodes
		nodeMixCam = create_node(
			nodes, "ShaderNodeMixShader", location=(320, 260))
		nodeFalloff = create_node(
			nodes, "ShaderNodeLightFalloff", location=(-80, 320))
		nodeLightPath = create_node(
			nodes, "ShaderNodeLightPath", location=(-320, 520))
				
		# Set values
		nodeFalloff.inputs["Strength"].default_value = 32
		nodeEmitCam.inputs["Strength"].default_value = 4

		# Create the links
		links.new(principled.outputs["BSDF"], nodeMixEmit.inputs[1])
		links.new(nodeLightPath.outputs["Is Camera Ray"], nodeMixCam.inputs["Fac"])
		links.new(nodeFalloff.outputs["Linear"], nodeEmit.inputs["Strength"])
		links.new(nodeEmit.outputs["Emission"], nodeMixCam.inputs[1])
		links.new(nodeEmitCam.outputs["Emission"], nodeMixCam.inputs[2])
		links.new(nodeMixCam.outputs["Shader"], nodeMixEmit.inputs[2])
		links.new(nodeMixEmit.outputs["Shader"], nodeMixTrans.inputs[2])

		if use_emission:
			nodeMixEmit.inputs[0].default_value = 1
		else:
			nodeMixEmit.inputs[0].default_value = 0
	else:
		links.new(principled.outputs[0], nodeMixTrans.inputs[2])


	nodeInputs = [
		[
			principled.inputs["Base Color"],
			nodeEmit.inputs["Color"],
			nodeEmitCam.inputs["Color"]],
		[nodeMixTrans.inputs["Fac"]],
		[nodeMixEmit.inputs[0]],
		[principled.inputs["Roughness"]],
		[principled.inputs["Metallic"]],
		[principled.inputs["Specular"]],
		[principled.inputs["Normal"]]]
	
	if not use_emission_nodes:
		nodes.remove(nodeEmit)
		nodes.remove(nodeEmitCam)
		nodes.remove(nodeMixEmit)
	# generate texture format and connect
	if pack_format == "specular":
		texgen_specular(mat, passes, nodeInputs, use_reflections)
	elif pack_format == "seus":
		texgen_seus(mat, passes, nodeInputs, use_reflections, use_emission_nodes)

	if only_solid is True or checklist(canon, "solid"):
		nodes.remove(nodeTrans)
		nodes.remove(nodeMixTrans)
		nodeOut.location = (620, 0)

		if use_emission_nodes:
			links.new(nodeMixEmit.outputs[0], nodeOut.inputs[0])

		# faster, and appropriate for non-transparent (and refelctive?) materials
		principled.distribution = 'GGX'
		if hasattr(mat, "blend_method"):
			mat.blend_method = 'OPAQUE'  # eevee setting
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
	
	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	return 0


def matgen_cycles_original(
	mat, passes, use_reflections, use_emission, only_solid, pack_format, use_emission_nodes):
	"""Generate principled cycles material"""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	image_diff = passes["diffuse"]

	if not image_diff:
		print("Could not find diffuse image, halting generation: " + mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		if image_diff.source != 'SEQUENCE':
			# Common non animated case; this means the image is missing and would
			# have already checked for replacement textures by now, so skip
			return
		if not os.path.isfile(bpy.path.abspath(image_diff.filepath)):
			# can't check size or pixels as it often is not immediately avaialble
			# so instea, check against firs frame of sequence to verify load
			return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	# Shader
	nodeDiff = create_node(nodes, "ShaderNodeBsdfDiffuse", location=(940, 200))
	nodeGlossDiff = create_node(nodes, "ShaderNodeBsdfGlossy", location=(940, 60))
	nodeGlossMetallic = create_node(
		nodes, "ShaderNodeBsdfGlossy", location=(1140, -120))
	nodeTrans = create_node(
		nodes, "ShaderNodeBsdfTransparent", location=(1740, 120))
	nodeEmit = create_node(nodes, "ShaderNodeEmission", location=(1340, 120))
	nodeEmitCam = create_node(nodes, "ShaderNodeEmission", location=(1340, 240))
	# Mix Shader
	nodeMixDiff = create_node(nodes, "ShaderNodeMixShader", location=(1140, 40))
	nodeMixMetallic = create_node(
		nodes, "ShaderNodeMixShader", location=(1340, 0))
	nodeMixTrans = create_node(nodes, "ShaderNodeMixShader", location=(1940, 0))
	nodeMixEmit = create_node(nodes, "ShaderNodeMixShader", location=(1740, 0))
	nodeMixCam = create_node(nodes, "ShaderNodeMixShader", location=(1540, 240))
	# Mix
	nodeMixRGBDiff = create_node(nodes, "ShaderNodeMixRGB", location=(560, 200))
	nodeMixRGB = create_node(nodes, "ShaderNodeMixRGB", location=(180, 360))
	nodeMixRGBMetallic = create_node(
		nodes, "ShaderNodeMixRGB", location=(940, -120))
	# Input
	nodeFresnel = create_node(nodes, "ShaderNodeFresnel", location=(360, 160))
	nodeFresnelMetallic = create_node(
		nodes, "ShaderNodeFresnel", location=(740, -120))
	nodeLightPath = create_node(
		nodes, "ShaderNodeLightPath", location=(1340, 600))
	nodeGeometry = create_node(nodes, "ShaderNodeNewGeometry", location=(0, 600))
	# Math
	nodeMathPower = create_node(
		nodes, "ShaderNodeMath",
		location=(0, 360),
		operation="POWER")
	nodeMathPowerDiff = create_node(
		nodes, "ShaderNodeMath",
		location=(360, 360),
		operation="POWER")
	nodeMathMultiplyDiff = create_node(
		nodes, "ShaderNodeMath",
		location=(740, 200),
		operation="MULTIPLY")
	nodeMathMetallic = create_node(
		nodes, "ShaderNodeMath",
		location=(740, -280),
		operation="MULTIPLY")
	# Etc
	nodeBump = create_node(
		nodes, "ShaderNodeBump", location=(-200, 600))
	nodeFalloff = create_node(
		nodes, "ShaderNodeLightFalloff", location=(1140, 240))
	nodeOut = create_node(
		nodes, "ShaderNodeOutputMaterial", location=(2140, 0))

	# Get MixRGB sockets
	mixDiffIn = get_node_socket(nodeMixRGBDiff)
	mixIn = get_node_socket(nodeMixRGB)
	mixMetallicIn = get_node_socket(nodeMixRGBMetallic)
	mixOut = get_node_socket(nodeMixRGB, is_input=False)
	mixDiffOut = get_node_socket(nodeMixRGBDiff, is_input=False)
	mixMetallicOut = get_node_socket(nodeMixRGBMetallic, is_input=False)

	# Sets default transparency value
	nodeMixTrans.inputs["Fac"].default_value = 1
	nodeMathMultiplyDiff.inputs[1].default_value = 0.1
	nodeFalloff.inputs["Strength"].default_value = 32
	nodeEmitCam.inputs["Strength"].default_value = 4
	nodeMathPowerDiff.inputs[0].default_value = 0
	nodeMathPowerDiff.inputs[1].default_value = 2
	nodeMathPower.inputs[1].default_value = 2
	nodeMathMetallic.inputs[1].default_value = 4
	nodeMixRGBDiff.inputs[mixDiffIn[2]].default_value = [1, 1, 1, 1]

	# Sets default reflective values
	if use_reflections and checklist(canon, "reflective"):
		nodeGlossMetallic.inputs["Roughness"].default_value = 0
		nodeMathPower.inputs[0].default_value = 0
		nodeGlossDiff.inputs["Roughness"].default_value = 0
	else:
		nodeGlossMetallic.inputs["Roughness"].default_value = 0.7
		nodeMathPower.inputs[0].default_value = 0.7
		nodeGlossDiff.inputs["Roughness"].default_value = 0.7

	# Sets default metallic values
	if use_reflections and checklist(canon, "metallic"):
		nodeMixMetallic.inputs["Fac"].default_value = 1

		if nodeGlossMetallic.inputs["Roughness"].default_value < 0.2:
			nodeGlossMetallic.inputs["Roughness"].default_value = 0.2
		if nodeMathPower.inputs[0].default_value < 0.2:
			nodeMathPower.inputs[0].default_value = 0.2
		if nodeGlossDiff.inputs["Roughness"].default_value < 0.2:
			nodeGlossDiff.inputs["Roughness"].default_value = 0.2

	else:
		nodeMixMetallic.inputs["Fac"].default_value = 0

	# Connect nodes
	links.new(nodeMixDiff.outputs["Shader"], nodeMixMetallic.inputs[1])
	links.new(nodeMathPower.outputs[0], nodeMixRGB.inputs[mixIn[0]])
	links.new(nodeMathPower.outputs[0], nodeDiff.inputs["Roughness"])
	links.new(nodeMixRGB.outputs[mixOut[0]], nodeFresnel.inputs["Normal"])
	links.new(nodeFresnel.outputs[0], nodeMixRGBDiff.inputs[mixDiffIn[0]])
	links.new(nodeGeometry.outputs["Incoming"], nodeMixRGB.inputs[mixIn[2]])
	links.new(nodeBump.outputs["Normal"], nodeMixRGB.inputs[mixIn[1]])
	links.new(
		nodeMathPowerDiff.outputs["Value"],
		nodeMixRGBDiff.inputs[mixDiffIn[1]])
	links.new(
		nodeMixRGBDiff.outputs[mixDiffOut[0]],
		nodeMathMultiplyDiff.inputs[0])
	links.new(nodeMathMultiplyDiff.outputs["Value"], nodeMixDiff.inputs["Fac"])
	links.new(nodeDiff.outputs["BSDF"], nodeMixDiff.inputs[1])
	links.new(nodeGlossDiff.outputs["BSDF"], nodeMixDiff.inputs[2])
	links.new(
		nodeFresnelMetallic.outputs["Fac"],
		nodeMixRGBMetallic.inputs[mixMetallicIn[0]])
	links.new(
		nodeMathMetallic.outputs["Value"],
		nodeMixRGBMetallic.inputs[mixMetallicIn[2]])
	links.new(
		nodeMixRGBMetallic.outputs[mixMetallicOut[0]],
		nodeGlossMetallic.inputs["Color"])
	links.new(nodeGlossMetallic.outputs["BSDF"], nodeMixMetallic.inputs[2])
	links.new(nodeMixMetallic.outputs["Shader"], nodeMixEmit.inputs[1])
	links.new(nodeMixCam.outputs["Shader"], nodeMixEmit.inputs[2])
	links.new(nodeTrans.outputs["BSDF"], nodeMixTrans.inputs[1])
	links.new(nodeFalloff.outputs["Linear"], nodeEmit.inputs["Strength"])
	links.new(nodeLightPath.outputs["Is Camera Ray"], nodeMixCam.inputs["Fac"])
	links.new(nodeEmit.outputs["Emission"], nodeMixCam.inputs[1])
	links.new(nodeEmitCam.outputs["Emission"], nodeMixCam.inputs[2])
	links.new(nodeMixEmit.outputs["Shader"], nodeMixTrans.inputs[2])
	links.new(nodeMixTrans.outputs["Shader"], nodeOut.inputs["Surface"])

	nodeInputs = [
		[
			nodeMixRGBMetallic.inputs[mixMetallicIn[1]],
			nodeMathMetallic.inputs[0],
			nodeDiff.inputs["Color"],
			nodeEmit.inputs["Color"],
			nodeEmitCam.inputs["Color"]],
		[nodeMixTrans.inputs["Fac"]],
		[nodeMixEmit.inputs[0]],
		[
			nodeGlossDiff.inputs["Roughness"],
			nodeGlossMetallic.inputs["Roughness"],
			nodeMathPower.inputs[0]],
		[nodeMixMetallic.inputs["Fac"]],
		[nodeMathPowerDiff.inputs[0]],
		[
			nodeDiff.inputs["Normal"],
			nodeGlossMetallic.inputs["Normal"],
			nodeFresnelMetallic.inputs["Normal"],
			nodeGlossDiff.inputs["Normal"],
			nodeBump.inputs["Normal"]]]

	# generate texture format and connect
	if pack_format == "specular":
		texgen_specular(mat, passes, nodeInputs, use_reflections)
	elif pack_format == "seus":
		texgen_seus(mat, passes, nodeInputs, use_reflections, use_emission_nodes)

	if only_solid is True or checklist(canon, "solid"):
		nodes.remove(nodeTrans)
		nodes.remove(nodeMixTrans)
		nodeOut.location = (1540, 0)
		links.new(nodeMixEmit.outputs[0], nodeOut.inputs[0])

		if hasattr(mat, "blend_method"):
			mat.blend_method = 'OPAQUE'  # eevee setting
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

	if use_emission:
		nodeMixEmit.inputs[0].default_value = 1
	else:
		nodeMixEmit.inputs[0].default_value = 0

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	return 0


def matgen_special_water(mat, passes):
	"""Generate special water material"""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	# get the texture, but will fail if NoneType
	image_diff = passes["diffuse"]
	image_norm = passes["normal"]

	if not image_diff:
		print("Could not find diffuse image, halting generation: " + mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		if image_diff.source != 'SEQUENCE':
			# Common non animated case; this means the image is missing and would
			# have already checked for replacement textures by now, so skip
			return
		if not os.path.isfile(bpy.path.abspath(image_diff.filepath)):
			# can't check size or pixels as it often is not immediately avaialble
			# so instea, check against firs frame of sequence to verify load
			return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	nodeTexDiff = create_node(
		nodes, 'ShaderNodeTexImage',
		name="Diffuse Texure",
		label="Diffuse Texure",
		location=(-180, 140),
		interpolation='Closest',
		image=image_diff)
	nodeTexNorm = create_node(
		nodes, 'ShaderNodeTexImage',
		name="Normal Texure",
		label="Normal Texure",
		location=(-290, -180),
		interpolation='Closest')
	nodeSaturateMix = create_node(
		nodes, 'ShaderNodeMixRGB',
		name="Add Color",
		label="Add Color",
		location=(320, 140),
		blend_type='MULTIPLY',
		mute=True,
		hide=True)
	nodeNormalInv = create_node(
		nodes, 'ShaderNodeRGBCurve',
		name="Normal Inverse",
		label="Normal Inverse",
		location=(10, -180))
	nodeNormal = create_node(
		nodes, 'ShaderNodeNormalMap', location=(310, -180))
	nodeBrightContrast = create_node(
		nodes, 'ShaderNodeBrightContrast', location=(120, 140))

	nodeGlass = create_node(
		nodes, 'ShaderNodeBsdfGlass', location=(520, 140))
	nodeTrans = create_node(
		nodes, 'ShaderNodeBsdfTransparent', location=(520, 340))
	nodeMixTrans = create_node(
		nodes, 'ShaderNodeMixShader', location=(720, 140))
	nodeOut = create_node(
		nodes, 'ShaderNodeOutputMaterial', location=(920, 140))

	# Mix RGB sockets for 3.4
	saturateMixIn = get_node_socket(nodeSaturateMix)
	saturateMixOut = get_node_socket(nodeSaturateMix, is_input=False)

	# Sets default values
	nodeSaturateMix.inputs[0].default_value = 1.0	# Graystyle Blending
	nodeNormalInv.mapping.curves[1].points[0].location = (0, 1)
	nodeNormalInv.mapping.curves[1].points[1].location = (1, 0)
	nodeMixTrans.inputs[0].default_value = 0.8
	nodeBrightContrast.inputs[1].default_value = 12
	nodeBrightContrast.inputs[2].default_value = 24
	nodeGlass.inputs[1].default_value = 0.1
	nodeGlass.inputs[2].default_value = 1.333

	# Connect nodes
	links.new(nodeTexDiff.outputs[0], nodeBrightContrast.inputs[0])
	links.new(nodeBrightContrast.outputs[0], nodeSaturateMix.inputs[1])
	links.new(nodeSaturateMix.outputs[saturateMixOut[0]], nodeGlass.inputs[0])
	links.new(nodeGlass.outputs[0], nodeMixTrans.inputs[2])
	links.new(nodeTrans.outputs[0], nodeMixTrans.inputs[1])
	links.new(nodeMixTrans.outputs[0], nodeOut.inputs[0])
	links.new(nodeTexNorm.outputs[0], nodeNormalInv.inputs[0])
	links.new(nodeNormalInv.outputs[0], nodeNormal.inputs[0])
	links.new(nodeNormal.outputs[0], nodeGlass.inputs[3])

	# Normal update
	util.apply_colorspace(nodeTexNorm, 'Non-Color')
	if image_norm:
		nodeTexNorm.image = image_norm
		nodeTexNorm.mute = False
		nodeNormalInv.mute = False
		nodeNormal.mute = False
	else:
		nodeTexNorm.mute = True
		nodeNormalInv.mute = True
		nodeNormal.mute = True

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

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	# Graystyle Blending
	if not checklist(canon, "desaturated"):
		pass
	elif not is_image_grayscale(image_diff):
		pass
	else:
		conf.log("Texture desaturated: " + canon, vv_only=True)
		desat_color = conf.json_data['blocks']['desaturated'][canon]
		if len(desat_color) < len(nodeSaturateMix.inputs[saturateMixIn[2]].default_value):
			desat_color.append(1.0)
		nodeSaturateMix.inputs[saturateMixIn[2]].default_value = desat_color
		nodeSaturateMix.mute = False
		nodeSaturateMix.hide = False

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexNorm["MCPREP_normal"] = True
	nodeNormal["MCPREP_normal"] = True  # to also be also muted if no normal tex
	# nodeTexDisp["MCPREP_disp"] = True

	return 0


def matgen_special_glass(mat, passes):
	"""Generate special glass material"""

	matGen = util.nameGeneralize(mat.name)
	canon, form = get_mc_canonical_name(matGen)

	# get the texture, but will fail if NoneType
	image_diff = passes["diffuse"]
	image_norm = passes["normal"]

	if not image_diff:
		print("Could not find diffuse image, halting generation: " + mat.name)
		return
	elif image_diff.size[0] == 0 or image_diff.size[1] == 0:
		if image_diff.source != 'SEQUENCE':
			# Common non animated case; this means the image is missing and would
			# have already checked for replacement textures by now, so skip
			return
		if not os.path.isfile(bpy.path.abspath(image_diff.filepath)):
			# can't check size or pixels as it often is not immediately avaialble
			# so instea, check against firs frame of sequence to verify load
			return

	mat.use_nodes = True
	animated_data = copy_texture_animation_pass_settings(mat)
	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	nodeTexDiff = create_node(
		nodes, 'ShaderNodeTexImage',
		name="Diffuse Texture",
		label="Diffuse Texture", 
		location=(-380, 140),
		interpolation='Closest',
		image=image_diff)
	nodeTexNorm = create_node(
		nodes, 'ShaderNodeTexImage',
		name="Normal Texture",
		label="Normal Texture",
		location=(-680, -180))
	nodeNormalInv = create_node(
		nodes, 'ShaderNodeRGBCurve',
		name="Normal Inverse",
		label="Normal Inverse",
		location=(-380, -180))
	nodeNormal = create_node(nodes, 'ShaderNodeNormalMap', location=(-80, -180))
	nodeDiff = create_node(nodes, 'ShaderNodeBsdfDiffuse', location=(120, 0))
	nodeMixTrans = create_node(nodes, 'ShaderNodeMixShader', location=(620, 0))
	nodeGlass = create_node(nodes, 'ShaderNodeBsdfGlass', location=(120, 240))
	nodeBrightContrast = create_node(
		nodes, 'ShaderNodeBrightContrast', location=(420, 0))
	nodeOut = create_node(nodes, 'ShaderNodeOutputMaterial', location=(820, 0))

	# Sets default transparency value
	nodeMixTrans.inputs[0].default_value = 1
	nodeGlass.inputs[1].default_value = 0
	nodeGlass.inputs[2].default_value = 1.5
	nodeBrightContrast.inputs[1].default_value = 0
	nodeBrightContrast.inputs[2].default_value = 1

	# Connect nodes
	links.new(nodeGlass.outputs["BSDF"], nodeMixTrans.inputs[1])
	links.new(nodeDiff.outputs["BSDF"], nodeMixTrans.inputs[2])
	links.new(nodeTexDiff.outputs["Alpha"], nodeBrightContrast.inputs["Color"])
	links.new(nodeBrightContrast.outputs[0], nodeMixTrans.inputs[0])

	links.new(nodeDiff.outputs[0], nodeMixTrans.inputs[2])
	links.new(nodeMixTrans.outputs[0], nodeOut.inputs[0])
	links.new(nodeTexDiff.outputs["Color"], nodeDiff.inputs[0])
	links.new(nodeTexNorm.outputs["Color"], nodeNormalInv.inputs["Color"])
	links.new(nodeNormalInv.outputs["Color"], nodeNormal.inputs["Color"])
	links.new(nodeNormal.outputs[0], nodeDiff.inputs[2])

	# Normal update
	util.apply_colorspace(nodeTexNorm, 'Non-Color')
	if image_norm:
		nodeTexNorm.image = image_norm
		nodeTexNorm.mute = False
		nodeNormalInv.mute = False
		nodeNormal.mute = False
	else:
		nodeTexNorm.mute = True
		nodeNormalInv.mute = True
		nodeNormal.mute = True

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

	# reapply animation data if any to generated nodes
	apply_texture_animation_pass_settings(mat, animated_data)

	# annotate special nodes for finding later, and load images if available
	nodeTexDiff["MCPREP_diffuse"] = True
	nodeTexNorm["MCPREP_normal"] = True
	nodeNormal["MCPREP_normal"] = True  # to also be also muted if no normal tex
	# nodeTexDisp["MCPREP_disp"] = True

	return 0  # return 0 once implemented
