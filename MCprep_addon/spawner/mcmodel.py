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
import json
from mathutils import Vector
from math import sin, cos, radians
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, Sequence
import re

import bpy
import bmesh
from bpy.types import Context, Material
from bpy_extras.io_utils import ImportHelper

from ..conf import MCprepError, env, VectorType
from .. import util
from .. import tracking
from ..materials import generate  # TODO: Use this module for mat gen in future
from .spawner_gizmo import draw_callback

TexFace = Dict[str, Dict[str, str]]

Element = Sequence[Union[Dict[str, VectorType], TexFace]]
Texture = Dict[str, str]

try:
	from bpy.types import FileHandler
except ImportError:
	# This is wrapper type that we use for FileHandler, since it's
	# only availible in Blender 4.1 and above. In older versions of
	# Blender, we just set it to the generic object type
	FileHandler = object

# Constants for Directions and Faces
NORTH_DIR = "north"
SOUTH_DIR = "south"
UP_DIR = "up"
DOWN_DIR = "down"
WEST_DIR = "west"
EAST_DIR = "east"

FACE_DIRECTIONS = (NORTH_DIR, SOUTH_DIR, UP_DIR, DOWN_DIR, WEST_DIR, EAST_DIR)

# -----------------------------------------------------------------------------
# Core MC model functions and implementation
# -----------------------------------------------------------------------------


class ModelException(Exception):
	"""Custom exception type for model loading."""


def rotate_around(
	d: float,
	pos: VectorType,
	origin: VectorType,
	axis: str = 'z',
	offset: VectorType = [8, 0, 8],
	scale: VectorType = [0.0625, 0.0625, 0.0625]
) -> VectorType:
	r = -radians(d)
	axis_i = ord(axis) - 120  # 'x'=0, 'y'=1, 'z'=2
	a = pos[(1 + axis_i) % 3]
	b = pos[(2 + axis_i) % 3]
	c = pos[(3 + axis_i) % 3]
	m = origin[(1 + axis_i) % 3]
	n = origin[(2 + axis_i) % 3]
	# this equation rotates the verticies around the origin point
	new_pos = [0, 0, 0]
	new_pos[(1 + axis_i) % 3] = cos(r) * (a - m) + (b - n) * sin(r) + m
	new_pos[(2 + axis_i) % 3] = -sin(r) * (a - m) + cos(r) * (b - n) + n
	new_pos[(3 + axis_i) % 3] = c
	# offset and scale are applied to the vertices in the return
	# the default offset is what makes sure the block/item is centered
	# the default scale will match the block size of 1m/blender unit.
	return Vector((
		-(new_pos[0] - offset[0]) * scale[0],
		(new_pos[2] - offset[2]) * scale[2],
		(new_pos[1] - offset[1]) * scale[1]
	))


def add_element(
	elm_from: VectorType = [0, 0, 0],
	elm_to: VectorType = [16, 16, 16],
	rot_origin: VectorType = [8, 8, 8],
	rot_axis: str = 'y',
	rot_angle: float = 0
) -> list:
	"""Calculates and defines the verts, edge, and faces that to create."""
	verts = [
		rotate_around(
			rot_angle, [elm_from[0], elm_to[1], elm_from[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_to[0], elm_to[1], elm_from[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_to[0], elm_from[1], elm_from[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_from[0], elm_from[1], elm_from[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_from[0], elm_to[1], elm_to[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_to[0], elm_to[1], elm_to[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_to[0], elm_from[1], elm_to[2]], rot_origin, rot_axis),
		rotate_around(
			rot_angle, [elm_from[0], elm_from[1], elm_to[2]], rot_origin, rot_axis),
	]

	edges = []
	faces = [
		[0, 1, 2, 3],  # north
		[5, 4, 7, 6],  # south
		[1, 0, 4, 5],  # up
		[7, 6, 2, 3],  # down
		[4, 0, 3, 7],  # west
		[1, 5, 6, 2]]  # east

	return verts, edges, faces


def add_get_material(
	name: str = "material", path: str = "", use_name: bool = False
) -> Optional[Material]:
	"""Creates or get an existing created simple material with an image texture from path."""
	engine = bpy.context.scene.render.engine
	mat = bpy.data.materials.get(name)
	if mat:
		return mat

	# Create the base material node tree setup
	mat, err = generate.generate_base_material(bpy.context, name, path, False)
	if mat is None and err:
		env.log("Failed to fetch any generated material")
		return None

	passes = generate.get_textures(mat)
	# In most case Minecraft JSON material
	# do not use PBR passes, so set it to None
	for pass_name in passes:
		if pass_name != "diffuse":
			passes[pass_name] = None
	# Prep material
	# Halt if no diffuse image found
	if engine == 'CYCLES' or engine == 'BLENDER_EEVEE' or engine == 'BLENDER_EEVEE_NEXT':
		options = generate.PrepOptions(
			passes=passes,
			use_reflections=False,
			use_principled=True,
			only_solid=False,
			pack_format=generate.PackFormat.SIMPLE,
			use_emission_nodes=False,
			use_emission=False  # This is for an option set in matprep_cycles
		)
		_ = generate.matprep_cycles(
			mat=mat,
			options=options
		)

	if use_name:
		mat.name = name

	return mat


def locate_image(
	context: Context, textures: Dict[str, str], img: str, model_filepath: Path
) -> Path:
	"""Finds and returns the filepath of the image texture."""
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)

	local_path = textures[img]  # Can fail lookup.
	if local_path[0] == '#':  # reference to another texture
		return locate_image(context, textures, local_path[1:], model_filepath)
		# note this will result in multiple materials that use the same texture
		# considering reworking this function to also create the material so
		# these can point towards the same material.
	else:
		if local_path[0] == '.':  # path is local to the model file
			directory = os.path.dirname(model_filepath)
		else:
			if len(local_path.split(":")) == 1:
				namespace = "minecraft"
			else:
				namespace = local_path.split(":")[0]
				local_path = local_path.split(":")[1]

			directory = os.path.join(
				resource_folder, "assets", namespace, "textures")
		return os.path.realpath(os.path.join(directory, local_path) + ".png")


def read_model(
	context: Context, model_filepath: Path) -> Tuple[Element, Texture]:
	"""Reads json file to get textures and elements needed for model.

	This function is recursively called to also get the elements and textures
	from the parent models the elements from the child will always overwrite
	the parent's elements individual textures from the child will overwrite the
	same texture from the parent.
	"""
	try:
		with open(model_filepath, 'r') as f:
			obj_data = json.load(f)
	except PermissionError as e:
		print(e)
		raise ModelException("Permission error, try running as admin") from e
	except UnicodeDecodeError as e:
		print(e)
		raise ModelException("Could not read file, select valid json file") from e

	addon_prefs = util.get_user_preferences(context)

	# Go from:      pack/assets/minecraft/models/block/block.json
	# to 5 dirs up: pack/
	targets_folder = bpy.path.abspath(
		os.path.dirname(
			os.path.dirname(
				os.path.dirname(
					os.path.dirname(
						os.path.dirname(model_filepath))))))
	# Fallback directories, which should already be resource pack paths.
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	fallback_folder = bpy.path.abspath(addon_prefs.custom_texturepack_path)

	elements: Optional[Element] = None
	textures: Optional[Texture] = None

	parent = obj_data.get("parent")
	if parent is not None:
		if parent == "builtin/generated" or parent == "item/generated":
			pass  # generates the model from the texture
		elif parent == "builtin/entity":
			# model from an entity file, only for chests, ender chests, mob
			# heads, shields, banners and tridents.
			pass
		else:
			if len(parent.split(":")) == 1:
				namespace = "minecraft"
				parent_filepath = parent
			else:
				namespace = parent.split(":")[0]
				parent_filepath = parent.split(":")[1]

			# resource_folder
			models_dir = os.path.join(
				"assets", namespace, "models", f"{parent_filepath}.json")
			target_path = os.path.join(targets_folder, models_dir)
			active_path = os.path.join(resource_folder, models_dir)
			base_path = os.path.join(fallback_folder, models_dir)

			if os.path.isfile(target_path):
				elements, textures = read_model(context, target_path)
			if os.path.isfile(active_path):
				elements, textures = read_model(context, active_path)
			elif os.path.isfile(base_path):
				elements, textures = read_model(context, base_path)
			else:
				env.log(f"Failed to find mcmodel file {parent_filepath}")

	current_elements: Element = obj_data.get("elements")
	if current_elements is not None:
		elements = current_elements  # overwrites any elements from parents

	current_textures: Texture = obj_data.get("textures")
	if current_textures is not None:
		if textures is None:
			textures = current_textures
		else:
			for img in current_textures:
				textures[img] = current_textures[img]

	env.log(f"\nfile: {model_filepath}", vv_only=True)
	# env.log("parent:" + str(parent))
	# env.log("elements:" + str(elements))
	# env.log("textures:" + str(textures))

	return elements, textures


def add_model(
	model_filepath: Path, obj_name: str = "MinecraftModel"
) -> Tuple[int, bpy.types.Object]:
	"""Primary function for generating a model from json file."""
	collection = bpy.context.collection
	view_layer = bpy.context.view_layer

	# Called recursively!
	# Can raise ModelException due to permission or corrupted file data.
	elements, textures = read_model(bpy.context, model_filepath)

	if elements is None:
		return 1, None

	mesh = bpy.data.meshes.new(obj_name)  # add a new mesh
	obj = bpy.data.objects.new(obj_name, mesh)  # add a new object using the mesh
	collection.objects.link(obj)  # put the object into the scene (link)
	view_layer.objects.active = obj  # set as the active object in the scene
	obj.select_set(True)  # select object
	obj_mats = obj.data.materials

	bm = bmesh.new()

	mesh.uv_layers.new()
	uv_layer = bm.loops.layers.uv.verify()

	materials = []
	materials_remap = {}
	if textures:
		for img in textures:
			if img != "particle":
				tex_pth = locate_image(bpy.context, textures, img, model_filepath)
				# Ensure the material name json file only use 1 material or having "all" texture
				if (len(textures) < 3 or textures.get("all")):
					name = f"{obj_name}"
				else:
					name = f"{obj_name}_{img}"
					materials_remap[f"#{img}"] = textures[img]
				mat = None
				if "#" not in textures[img]:
					mat = add_get_material(name, tex_pth, use_name=False)
				# Map the "#" reference texture for later use in the assign material
				# Make sure the same material doesn't get append and ignore reference texture like "#all"
				if f"#{img}" not in materials and name not in obj_mats and mat is not None:
					obj_mats.append(mat)
					materials.append(f"#{img}")

	for e in elements:
		# Check if 'from' and 'to' bounds are present
		if 'from' not in e or 'to' not in e:
			raise ModelException(f"Element is missing required 'from' or 'to' bounds: {e}")

		f_bounds = e['from']  # [x1, y1, z1]
		t_bounds = e['to']	  # [x2, y2, z2]

		# Check if bounds are lists of 3 points
		if not isinstance(f_bounds, list) or len(f_bounds) != 3:
			raise ModelException(f"Invalid 'from' bounds format: {f_bounds}")
		if not isinstance(t_bounds, list) or len(t_bounds) != 3:
			raise ModelException(f"Invalid 'to' bounds format: {t_bounds}")

		rotation = e.get("rotation")
		if rotation is None:
			# rotation default
			rotation = {"angle": 0, "axis": "y", "origin": [8, 8, 8]}
		element = add_element(
			f_bounds, t_bounds, rotation['origin'], rotation['axis'], rotation['angle'])
		verts = [bm.verts.new(v) for v in element[0]]  # add a new vert

		faces = e.get("faces")
		for i in range(len(element[2])):
			f = element[2][i]

			if not faces:
				continue

			face_name = FACE_DIRECTIONS[i]
			d_face = faces.get(face_name)
			if not d_face:
				continue

			face_mat = d_face.get("texture")
			# uv can be rotated 0, 90, 180, or 270 degrees
			uv_rot = d_face.get("rotation")
			if uv_rot is None:
				uv_rot = 0

			# the index of the first uv cord,
			# the rotation is achieved by shifting the order of the uv coords
			uv_idx = int(uv_rot / 90)

			uv_coords = d_face.get("uv")  # in the format [x1, y1, x2, y2]

			# --- UV Calculation Algorithm Overview ---
			# Minecraft UVs use a 0-16 scale, where V=0 is the top edge (Y-max).
			# 1. Auto-UV: Calculates UV [u_min, v_min, u_max, v_max] based on the
			#    element's bounding box ('from'/'to' vectors).
			# 2. Conversion: Converts Minecraft's 0-16 UV scale to Blender's 0-1 UV
			#    scale. Note that the V-axis is flipped (1 - MC_V ÷ 16) to match Blender's
			#    convention (V=1 at the top).
			# 3. Corner Definition: Defines the four corners (TL, TR, BR, BL) in 0-1 Blender
			#    UV space.
			# 4. Base Ordering: Defines the initial ordering of these corners (uvs_base) for
			#    the specific face direction, accounting for MC's default face-to-UV mapping
			#    conventions.
			# 5. Rotation: Applies the `uv_rot` (0, 90, 180, 270) by cyclically shifting the
			#    corner order (uvs_rot).
			# 6. Mirroring/Flipping: Applies face-specific mirroring (X and/or Y axes) to correct
			#    orientation between MC model format and Blender's mesh structure.
			# ---------------------------------------

			if uv_coords is None:
				# Auto-calculate proportional UVs (0-16 scale) based on element bounds
				# MC UV convention: (u_min, v_min, u_max, v_max). V is measured from 0 at the top.
				if face_name in (NORTH_DIR, SOUTH_DIR):
					# U maps to X, V maps to Y (height). V is 16-Y (flipped V for MC texture coords).
					uv_coords = [f_bounds[0], 16 - t_bounds[1], t_bounds[0], 16 - f_bounds[1]]
				elif face_name in (WEST_DIR, EAST_DIR):
					# U maps to Z, V maps to Y (height). V is 16-Y (flipped V for MC texture coords).
					uv_coords = [f_bounds[2], 16 - t_bounds[1], t_bounds[2], 16 - f_bounds[1]]
				elif face_name in (UP_DIR, DOWN_DIR):
					# U maps to X, V maps to Z (depth).
					uv_coords = [f_bounds[0], f_bounds[2], t_bounds[0], t_bounds[2]]
				else:
					env.log(f"Unknown face direction '{face_name}'. Defaulting UV mapping")
					uv_coords = [0, 0, 16, 16]

			# = UV Corner Definition =
			# Convert MC UV (0-16) to Blender UV (0-1) and flip V accordingly.
			u_min = uv_coords[0] / 16
			u_max = uv_coords[2] / 16
			v_max = 1 - (uv_coords[1] / 16)  # Blender Top V
			v_min = 1 - (uv_coords[3] / 16)  # Blender Bottom V

			# Define the four corners
			p_TL = (u_min, v_max)  # Top Left
			p_TR = (u_max, v_max)  # Top Right
			p_BR = (u_max, v_min)  # Bottom Right
			p_BL = (u_min, v_min)  # Bottom Left

			# Face-specific base ordering (maps Tex-corners -> face loop positions)
			if face_name == UP_DIR:  # Y+ (V-flip and U-flip)
				uvs_base = [p_TR, p_TL, p_BL, p_BR]
			elif face_name == DOWN_DIR:  # Y- (V-flip and U-flip)
				uvs_base = [p_BL, p_BR, p_TR, p_TL]
			elif face_name == NORTH_DIR:  # Z- (V-flip)
				uvs_base = [p_TL, p_TR, p_BR, p_BL]
			elif face_name == SOUTH_DIR:  # Z+ (V-flip and U-flip)
				uvs_base = [p_BR, p_BL, p_TL, p_TR]
			elif face_name == EAST_DIR:  # X+ (V-flip and U-flip)
				uvs_base = [p_BR, p_BL, p_TL, p_TR]
			elif face_name == WEST_DIR:  # X- (V-flip)
				uvs_base = [p_TL, p_TR, p_BR, p_BL]
			else:
				# Default fallback (should not happen, just in case though)
				env.log(f"Used default fallback for UV base on {obj_name}")
				uvs_base = [p_TL, p_TR, p_BR, p_BL]

			# Reverse vertex order for downward faces before creation — keeps UVs intact
			f_for_face = list(f)
			if face_name == DOWN_DIR:
				f_for_face = list(reversed(f_for_face))

			if len(f_for_face) != 4:
				env.log(f"Face vertex index list expected 4 elements, but got {len(f_for_face)}. Skipping face.")
				continue

			face_verts = []
			out_of_bounds = False
			for vert_idx in f_for_face:
				if 0 <= vert_idx < len(verts):
					face_verts.append(verts[vert_idx])
				else:
					env.log(f"Vertex index {vert_idx} is out of bounds (0 to {len(verts) - 1}). Skipping face.")
					out_of_bounds = True
					break  # No need to keep checking this face
			if out_of_bounds:
				continue
			try:
				face = bm.faces.new(tuple(face_verts))
			except ValueError as e:
				env.log(f"Failed to create BMesh face: {e}. Skipping.")
				continue

			face.normal_update()

			# Give slight offset by normal for overlay geometry
			if face_mat == "#overlay":
				bmesh.ops.translate(bm, verts=face.verts, vec=0.0025 * face.normal)

			# Apply rotation shift (uv_idx) with bounds check
			uvs_rot = []
			if uvs_base and len(uvs_base) > 0:
				uvs_rot = [uvs_base[(k + uv_idx) % len(uvs_base)] for k in range(len(uvs_base))]
			else:
				env.log("Warning: Empty uvs_base, skipping UV rotation.")

			# Mirror axis per-face (to fix convention mismatches)
			mirror_axis = None
			if face_name == NORTH_DIR:
				mirror_axis = "Y"
			elif face_name == EAST_DIR:
				mirror_axis = "X"
			elif face_name == SOUTH_DIR:
				mirror_axis = "X"
			elif face_name == WEST_DIR:
				mirror_axis = "Y"
			elif face_name == DOWN_DIR:
				mirror_axis = "Y"
			# up -> no mirroring

			# If mirroring, get UV island median and mirror around point.
			if mirror_axis is not None:
				mx = sum(p[0] for p in uvs_rot) / len(uvs_rot)
				my = sum(p[1] for p in uvs_rot) / len(uvs_rot)
				uvs_final = []
				for (x, y) in uvs_rot:
					if mirror_axis == "X":
						nx = 2 * mx - x		# mirror horizontally
						ny = y
					else:
						nx = x
						ny = 2 * my - y		  # mirror vertically
					uvs_final.append((nx, ny))
			else:
				uvs_final = uvs_rot

			# For cardinal faces (north/south/east/west) mirror over both axes
			if face_name in (NORTH_DIR, SOUTH_DIR, EAST_DIR, WEST_DIR):
				mx = sum(p[0] for p in uvs_final) / len(uvs_final)
				my = sum(p[1] for p in uvs_final) / len(uvs_final)
				uvs_final = [(2 * mx - x, 2 * my - y) for x, y in uvs_final]

			# Flip UV for 'down' face (V-axis flip)
			if face_name == DOWN_DIR:
				mx = sum(p[0] for p in uvs_final) / len(uvs_final)
				my = sum(p[1] for p in uvs_final) / len(uvs_final)
				uvs_final = [(x, 2 * my - y) for (x, y) in uvs_final]

			# Assign the final computed UVs to the face loops
			if not uvs_final:
				env.log("Warning: Empty uvs_final, skipping UV assignment for this face.")
			else:
				for j, loop in enumerate(face.loops):
					# Bounds check before assignment
					if j >= len(uvs_final):
						env.log(f"UV index {j} out of bounds for computed UVs (size: {len(uvs_final)}). Skipping assignment.")
						break

					try:
						_ = loop[uv_layer]
					except KeyError:
						env.log("Warning: UV layer not found on loop; skipping UV assignment.")
						continue

					if (j % len(uvs_final)) < 0 or (j % len(uvs_final)) >= len(uvs_final):
						env.log(f"Error assigning UV to loop {j}: Out of Bounds")
						continue
					loop[uv_layer].uv = uvs_final[j % len(uvs_final)]

			# Using materials_remap to remap the index, used for the block with remapping "#side"
			# Stored material index for getting the texture
			material_index = 0
			if face_mat and (face_mat in materials or face_mat in materials_remap):
				face_mat_ref = materials_remap.get(face_mat)
				if face_mat_ref and "#" in face_mat_ref:
					face_mat = face_mat_ref
				material_index = materials.index(face_mat)

			# Assign the material on face
			face.material_index = material_index

			# Adjusting the uv scaling
			if len(obj_mats) > 0:
				node = obj_mats[material_index].node_tree.nodes.get('Diffuse Texture')
				if node:
					img_size = node.image.size
					scale = 1
					if img_size[1] != img_size[0]:
						scale = (img_size[0] / img_size[1])
					face_pivot = (0, 1)  # OpenGL UV
					scale_factor_uv = (1, scale)

					# Starts doing uv scaling from a pivot location
					for loop in face.loops:
						uv = loop[uv_layer].uv
						u, v = uv

						# Translate to pivot
						translated_u = u - face_pivot[0]
						translated_v = v - face_pivot[1]

						# Scale
						scaled_u = translated_u * scale_factor_uv[0]
						scaled_v = translated_v * scale_factor_uv[1]

						# Translate back
						loop[uv_layer].uv = (scaled_u + face_pivot[0], scaled_v + face_pivot[1])

	# Quick way to clean the model, hopefully it doesn't cause any UV issues
	# Ignore model has overlay geometry, causing issue
	if not textures.get("overlay"):
		bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)

	# make the bmesh the object's mesh
	bm.to_mesh(mesh)
	bm.free()
	return 0, obj

# -----------------------------------------------------------------------------
# UI and resource pack management.
# -----------------------------------------------------------------------------


def update_model_list(context: Context):
	"""Update the model list.

	Prefer loading model names from the active resource pack, but fall back
	to the default user preferences pack. This ensures that fallback names
	like "block", which resource packs often don't define themselves, is
	available.
	"""
	scn_props = context.scene.mcprep_props
	sorted_models = []  # Struc of model, name, description
	addon_prefs = util.get_user_preferences()

	active_pack = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	active_pack = os.path.join(
		active_pack, "assets", "minecraft", "models", "block")

	base_pack = bpy.path.abspath(addon_prefs.custom_texturepack_path)
	base_pack = os.path.join(
		base_pack, "assets", "minecraft", "models", "block")

	if not os.path.isdir(active_pack):
		scn_props.model_list.clear()
		scn_props.model_list_index = 0
		env.log(f"No models found for active path {active_pack}")
		return
	base_has_models = os.path.isdir(base_pack)

	active_models = [
		model for model in os.listdir(active_pack)
		if os.path.isfile(os.path.join(active_pack, model))
		and model.lower().endswith(".json")]

	if base_has_models:
		base_models = [
			model for model in os.listdir(active_pack)
			if os.path.isfile(os.path.join(active_pack, model))
			and model.lower().endswith(".json")]
	else:
		env.log(f"Base resource pack has no models folder: {base_pack}")
		base_models = []

	sorted_models = [
		os.path.join(active_pack, model) for model in active_models]
	# Add the fallback models not defined by active pack.
	sorted_models += [
		os.path.join(base_pack, model) for model in base_models
		if model not in active_models]

	sorted_models = sorted(sorted_models)

	# now re-populate the UI list
	scn_props.model_list.clear()
	for model in sorted_models:
		name = os.path.splitext(os.path.basename(model))[0]

		# Filter out models that can't spawn. Typically those that reference
		# #fire or the likes in the file.
		# These blocks just don't make sense to put in the for "unspawnable_for_now"
		# - Template base of that block for example candle, cake with candles, fence
		# - Orient blocks base, cube same as orientable (no texture)
		# - Light blocks are just special no geometry block with 15 states of light levels
		# - Shulkers, hanging signs, signs are entities, put it here for now since they have a lot of variants
		# - "pitcher_crop_top_stage_" is a top part of a double plant. I have no idea why it has no geometry.
		# - custom_fence_ not sure what even used for
		# - stem_growth and stem_fruit are used for pumpkin and melon stem models
		# - block is a base for every block in the game. Same for the slab bases
		# - Air, barrier, structure void, skull have no geometry
		is_contains = re.search(
			r"template_|orientable|cube_|\
			_shulker_box|_sign|\
			light_0|light_1|\
			pitcher_crop_top_stage_|custom_fence_|\
			stem_growth|^stem_fruit$|\
			^block$|^air$|^barrier$|^structure_void$|^thin_block$|\
			^slab$|^slab_top$|^skull$",
			name
		)
		if is_contains:
			continue

		# Filter the "unspawnable_for_now"
		# Either entity block or block that doesn't good for json
		blocks = env.json_data.get(
			"unspawnable_for_now",
			["bed", "chest", "banner", "campfire"])
		if name in blocks:
			continue

		item = scn_props.model_list.add()
		item.filepath = model
		item.name = name
		item.description = "Spawn a {} model from active resource pack".format(
			name)

	if scn_props.model_list_index >= len(scn_props.model_list):
		scn_props.model_list_index = len(scn_props.model_list) - 1


def draw_import_mcmodel(self, context: Context):
	"""Import bar layout definition."""
	layout = self.layout
	layout.operator("mcprep.import_model_file", text="Minecraft Model (.json)")


class ModelSpawnBase():
	"""Class to inheret reused MCprep item spawning settings and functions."""
	location: bpy.props.FloatVectorProperty(
		default=(0, 0, 0),
		name="Location")
	rotation: bpy.props.FloatVectorProperty(
		default=(0, 0, 0),
		name="Rotation")
	snapping: bpy.props.EnumProperty(
		name="Snapping",
		items=[
			("none", "No snap", "Keep exact location"),
			("center", "Snap center", "Snap to block center"),
			("offset", "Snap offset", "Snap to block center with 0.5 offset")],
		description="Automatically snap to whole block locations")
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	def place_model(self, obj):
		if self.snapping == "center":
			offset = 0
			obj.location = [round(x + offset) - offset for x in self.location]
			obj.location.z -= 0.5
		elif self.snapping == "offset":
			offset = 0.5
			obj.location = [round(x + offset) - offset for x in self.location]
			obj.location.z -= 0.5
		else:
			obj.location = self.location

		obj.rotation_euler = self.rotation

	def post_spawn(self, context, new_obj):
		"""Do final consistent cleanup after model is spawned."""
		for ob in util.get_objects_conext(context):
			util.select_set(ob, False)
		util.select_set(new_obj, True)

	def create_and_place_json_model(self, context, filepath: Path) -> Optional[MCprepError]:
		"""Function that does the entire model creation and placing"""
		filename = filepath.stem
		if not filepath or not filepath.exists():
			line, file = env.current_line_and_file()
			return MCprepError(FileNotFoundError(), line, file, "File not found")
		if filepath.suffix != ".json":
			line, file = env.current_line_and_file()
			return MCprepError(Exception(), line, file, f"File is not JSON: {filepath}")

		try:
			r, obj = add_model(filepath, filename)
			if r:
				line, file = env.current_line_and_file()
				return MCprepError(Exception(), line, file, "JSON model does not contain any actual geometry")
		except ModelException as e:
			line, file = env.current_line_and_file()
			return MCprepError(ModelException(), line, file, f"Encountered error: {e}")

		self.place_model(obj)
		self.post_spawn(context, obj)


class MCPREP_OT_spawn_minecraft_model(bpy.types.Operator, ModelSpawnBase):
	"""Import in an MC model from a json file."""
	bl_idname = "mcprep.spawn_model"
	bl_label = "Place model"
	bl_options = {'REGISTER', 'UNDO'}

	filepath: bpy.props.StringProperty(
		default="",
		subtype="FILE_PATH",
		options={'HIDDEN', 'SKIP_SAVE'})

	track_function = "model"
	track_param = "list"
	@tracking.report_error
	def execute(self, context):
		res = self.create_and_place_json_model(context, Path(self.filepath))
		if res:
			self.report({'ERROR'}, res.msg)
			return {'CANCELLED'}
		return {'FINISHED'}


class MCPREP_OT_import_minecraft_model_file(
	bpy.types.Operator, ImportHelper, ModelSpawnBase):
	"""Import an MC model from a json file."""
	bl_idname = "mcprep.import_model_file"
	bl_label = "Import model (.json)"
	bl_options = {'REGISTER', 'UNDO'}

	filename_ext = ".json"
	filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
	filter_glob: bpy.props.StringProperty(
		default="*.json",
		options={'HIDDEN'},
		maxlen=255  # Max internal buffer length, longer would be clamped.
	)

	track_function = "model"
	track_param = "file"
	@tracking.report_error
	def execute(self, context):
		res = self.create_and_place_json_model(context, Path(self.filepath))
		if res:
			self.report({'ERROR'}, res.msg)
			return {'CANCELLED'}
		return {'FINISHED'}

	def invoke(self, context, event):
		if self.filepath:
			return self.execute(context)
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}


class MCPREP_FH_import_minecraft_model_file(FileHandler):
	bl_idname = "MCPREP_FH_import_minecraft_model_file"
	bl_label = "File handler for JSON import"
	bl_import_operator = "mcprep.place_json_model_with_gizmo"
	bl_file_extensions = ".json"

	@classmethod
	def poll_drop(cls, context) -> bool:
		return (context.area and context.area.type == 'VIEW_3D')


class MCPREP_OT_reload_models(bpy.types.Operator):
	"""Reload model spawner, use after adding/removing/renaming files in the resource pack folder"""
	bl_idname = "mcprep.reload_models"
	bl_label = "Reload models"

	@tracking.report_error
	def execute(self, context):
		update_model_list(context)
		return {'FINISHED'}


class MCPREP_OT_place_json_model_with_gizmo(bpy.types.Operator, ModelSpawnBase):
	bl_idname = "mcprep.place_json_model_with_gizmo"
	bl_label = "Import Minecraft JSON model and Place"
	bl_description = "Imports a Minecraft JSON model with location selection"
	bl_options = {'REGISTER', 'UNDO'}

	filename_ext = ".json"
	filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})

	def invoke(self, context, event):
		from .spawner_gizmo import HitVector

		self.hit_vector: Optional[HitVector] = None

		self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(
			self.draw_callback, (context,), 'WINDOW', 'POST_VIEW'
		)
		context.window_manager.modal_handler_add(self)
		return {'RUNNING_MODAL'}

	def execute(self, context):
		if self.hit_vector:
			self.location = self.hit_vector.location
			self.rotation = self.hit_vector.rotation.to_euler()
			res = self.create_and_place_json_model(context, Path(self.filepath))
			if res:
				self.report({'ERROR'}, res.msg)
				return {'CANCELLED'}
		else:
			return {'CANCELLED'}
		return {'FINISHED'}

	def modal(self, context, event):
		context.area.tag_redraw()
		if event.type == 'MOUSEMOVE':
			from .spawner_gizmo import update_raycast
			self.hit_vector = update_raycast(context, event)
		elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
			res = self.execute(context)
			self.finish(context)
			return res
		elif event.type in {'RIGHTMOUSE', 'ESC'}:
			self.finish(context)
			return {'CANCELLED'}
		return {'RUNNING_MODAL'}

	def finish(self, context):
		bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, 'WINDOW')
		context.area.tag_redraw()

	def draw_callback(self, context) -> None:
		if not self.hit_vector:
			return

		draw_callback(self.hit_vector)


classes = (
	MCPREP_OT_spawn_minecraft_model,
	MCPREP_OT_import_minecraft_model_file,
	MCPREP_OT_reload_models,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	if util.min_bv((4, 1)):
		bpy.utils.register_class(MCPREP_FH_import_minecraft_model_file)
		bpy.utils.register_class(MCPREP_OT_place_json_model_with_gizmo)

	bpy.types.TOPBAR_MT_file_import.append(draw_import_mcmodel)


def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(draw_import_mcmodel)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	if util.min_bv((4, 1)):
		bpy.utils.unregister_class(MCPREP_FH_import_minecraft_model_file)
		bpy.utils.unregister_class(MCPREP_OT_place_json_model_with_gizmo)
