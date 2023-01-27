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

import bpy
import bmesh
from bpy_extras.io_utils import ImportHelper

from .. import conf
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# Core MC model functions and implementation
# -----------------------------------------------------------------------------

class ModelException(Exception):
	"""Custom exception type for model loading."""


def rotate_around(
	d, pos, origin, axis='z', offset=[8, 0, 8], scale=[0.063, 0.063, 0.063]):
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
	elm_from=[0, 0, 0],
	elm_to=[16, 16, 16],
	rot_origin=[8, 8, 8],
	rot_axis='y',
	rot_angle=0):
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
		[0, 1, 2, 3],
		[5, 4, 7, 6],
		[1, 0, 4, 5],
		[7, 6, 2, 3],
		[4, 0, 3, 7],
		[1, 5, 6, 2]]

	return [verts, edges, faces]


def add_material(name="material", path=""):
	"""Creates a simple material with an image texture from path."""
	conf.log(name + ": " + path, vv_only=True)
	mat = bpy.data.materials.new(name=name)
	mat.blend_method = 'CLIP'
	mat.shadow_method = 'CLIP'
	mat.use_nodes = True
	matnodes = mat.node_tree.nodes

	tex = matnodes.new('ShaderNodeTexImage')
	if os.path.isfile(path):
		img = bpy.data.images.load(path, check_existing=True)
		tex.image = img
	tex.interpolation = 'Closest'

	shader = matnodes['Principled BSDF']
	mat.node_tree.links.new(shader.inputs['Base Color'], tex.outputs['Color'])
	mat.node_tree.links.new(shader.inputs['Alpha'], tex.outputs['Alpha'])
	return mat


def locate_image(context, textures, img, model_filepath):
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
			if(len(local_path.split(":")) == 1):
				namespace = "minecraft"
			else:
				namespace = local_path.split(":")[0]
				local_path = local_path.split(":")[1]

			directory = os.path.join(
				resource_folder, "assets", namespace, "textures")
		return os.path.realpath(os.path.join(directory, local_path) + ".png")


def read_model(context, model_filepath):
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

	elements = None
	textures = None

	parent = obj_data.get("parent")
	if parent is not None:
		if parent == "builtin/generated" or parent == "item/generated":
			pass  # generates the model from the texture
		elif parent == "builtin/entity":
			# model from an entity file, only for chests, ender chests, mob
			# heads, shields, banners and tridents.
			pass
		else:
			if(len(parent.split(":")) == 1):
				namespace = "minecraft"
				parent_filepath = parent
			else:
				namespace = parent.split(":")[0]
				parent_filepath = parent.split(":")[1]

			# resource_folder
			models_dir = os.path.join(
				"assets", namespace, "models", parent_filepath + ".json")
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
				conf.log("Failed to find mcmodel file " + parent_filepath)

	current_elements = obj_data.get("elements")
	if current_elements is not None:
		elements = current_elements  # overwrites any elements from parents

	current_textures = obj_data.get("textures")
	if current_textures is not None:
		if textures is None:
			textures = current_textures
		else:
			for img in current_textures:
				textures[img] = current_textures[img]

	conf.log("\nfile:" + str(model_filepath), vv_only=True)
	# conf.log("parent:" + str(parent))
	# conf.log("elements:" + str(elements))
	# conf.log("textures:" + str(textures))

	return elements, textures


def add_model(model_filepath, obj_name="MinecraftModel"):
	"""Primary function for generating a model from json file."""
	mesh = bpy.data.meshes.new(obj_name)  # add a new mesh
	obj = bpy.data.objects.new(obj_name, mesh)  # add a new object using the mesh

	collection = bpy.context.collection
	view_layer = bpy.context.view_layer
	collection.objects.link(obj)  # put the object into the scene (link)
	view_layer.objects.active = obj  # set as the active object in the scene
	obj.select_set(True)  # select object

	bm = bmesh.new()

	mesh.uv_layers.new()
	uv_layer = bm.loops.layers.uv.verify()

	# Called recursively!
	# Can raise ModelException due to permission or corrupted file data.
	elements, textures = read_model(bpy.context, model_filepath)

	materials = []
	if textures:
		for img in textures:
			if img != "particle":
				tex_pth = locate_image(bpy.context, textures, img, model_filepath)
				mat = add_material(obj_name + "_" + img, tex_pth)
				obj.data.materials.append(mat)
				materials.append("#" + img)

	if elements is None:
		elements = [
			{'from': [0, 0, 0], 'to':[0, 0, 0]}]  # temp default elements

	for e in elements:
		rotation = e.get("rotation")
		if rotation is None:
			# rotation default
			rotation = {"angle": 0, "axis": "y", "origin": [8, 8, 8]}

		element = add_element(
			e['from'], e['to'], rotation['origin'], rotation['axis'], rotation['angle'])
		verts = [bm.verts.new(v) for v in element[0]]  # add a new vert
		uvs = [[1, 1], [0, 1], [0, 0], [1, 0]]
		# face directions defaults
		face_dir = ["north", "south", "up", "down", "west", "east"]
		faces = e.get("faces")
		for i in range(len(element[2])):
			f = element[2][i]

			if not faces:
				continue

			d_face = faces.get(face_dir[i])
			if not d_face:
				continue

			face = bm.faces.new(
				(verts[f[0]], verts[f[1]], verts[f[2]], verts[f[3]])
			)
			face.normal_update()

			# uv can be rotated 0, 90, 180, or 270 degrees
			uv_rot = d_face.get("rotation")
			if uv_rot is None:
				uv_rot = 0

			# the index of the first uv cord,
			# the rotation is achieved by shifting the order of the uv coords
			uv_idx = int(uv_rot / 90)

			uv_coords = d_face.get("uv")  # in the format [x1, y1, x2, y2]
			if uv_coords is None:
				uv_coords = [0, 0, 16, 16]

			# uv in the model is between 0 to 16 regardless of resolution,
			# in blender its 0 to 1 the y-axis is inverted when compared to
			# blender uvs, which is why it is subtracted from 1, essentially
			# this converts the json uv points to the blender equivelent.
			uvs = [
				[uv_coords[2] / 16, 1 - (uv_coords[1] / 16)],  # [x2, y1]
				[uv_coords[0] / 16, 1 - (uv_coords[1] / 16)],  # [x1, y1]
				[uv_coords[0] / 16, 1 - (uv_coords[3] / 16)],  # [x1, y2]
				[uv_coords[2] / 16, 1 - (uv_coords[3] / 16)]   # [x2, y2]
			]

			for j in range(len(face.loops)):
				# uv coords order is determened by the rotation of the uv,
				# e.g. if the uv is rotated by 180 degrees, the first index
				# will be 2 then 3, 0, 1.
				face.loops[j][uv_layer].uv = uvs[(j + uv_idx) % len(uvs)]

			face_mat = d_face.get("texture")
			if face_mat is not None and face_mat in materials:
				face.material_index = materials.index(face_mat)

	# make the bmesh the object's mesh
	bm.to_mesh(mesh)
	bm.free()
	return obj


# -----------------------------------------------------------------------------
# UI and resource pack management.
# -----------------------------------------------------------------------------


def update_model_list(context):
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
		conf.log("No models found for active path " + active_pack)
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
		conf.log("Base resource pack has no models folder: " + base_pack)
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
		if "template" in name:
			continue
		item = scn_props.model_list.add()
		item.filepath = model
		item.name = name
		item.description = "Spawn a {} model from active resource pack".format(
			name)

	if scn_props.model_list_index >= len(scn_props.model_list):
		scn_props.model_list_index = len(scn_props.model_list) - 1


def draw_import_mcmodel(self, context):
	"""Import bar layout definition."""
	layout = self.layout
	layout.operator("mcprep.import_model_file", text="Minecraft Model (.json)")


class ModelSpawnBase():
	"""Class to inheret reused MCprep item spawning settings and functions."""
	location = bpy.props.FloatVectorProperty(
		default=(0, 0, 0),
		name="Location")
	snapping = bpy.props.EnumProperty(
		name="Snapping",
		items=[
			("none", "No snap", "Keep exact location"),
			("center", "Snap center", "Snap to block center"),
			("offset", "Snap offset", "Snap to block center with 0.5 offset")],
		description="Automatically snap to whole block locations")
	skipUsage = bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT' and util.bv28()

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

	def post_spawn(self, context, new_obj):
		"""Do final consistent cleanup after model is spawned."""
		for ob in util.get_objects_conext(context):
			util.select_set(ob, False)
		util.select_set(new_obj, True)


class MCPREP_OT_spawn_minecraft_model(bpy.types.Operator, ModelSpawnBase):
	"""Import in an MC model from a json file."""
	bl_idname = "mcprep.spawn_model"
	bl_label = "Place model"
	bl_options = {'REGISTER', 'UNDO'}

	filepath = bpy.props.StringProperty(
		default="",
		subtype="FILE_PATH",
		options={'HIDDEN', 'SKIP_SAVE'})

	track_function = "model"
	track_param = "list"
	@tracking.report_error
	def execute(self, context):
		name = os.path.basename(os.path.splitext(self.filepath)[0])
		if not self.filepath or not os.path.isfile(self.filepath):
			self.report({"WARNING"}, "Filepath not found")
			bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
			return {'CANCELLED'}
		if not self.filepath.lower().endswith(".json"):
			self.report(
				{"ERROR"}, "File is not json: " + self.filepath)
			return {'CANCELLED'}

		try:
			obj = add_model(os.path.normpath(self.filepath), name)
		except ModelException as e:
			self.report({"ERROR"}, "Encountered error: " + str(e))
			return {'CANCELLED'}

		self.place_model(obj)
		self.post_spawn(context, obj)
		return {'FINISHED'}


class MCPREP_OT_import_minecraft_model_file(
	bpy.types.Operator, ImportHelper, ModelSpawnBase):
	"""Import an MC model from a json file."""
	bl_idname = "mcprep.import_model_file"
	bl_label = "Import model (.json)"
	bl_options = {'REGISTER', 'UNDO'}

	filename_ext = ".json"
	filter_glob = bpy.props.StringProperty(
		default="*.json",
		options={'HIDDEN'},
		maxlen=255  # Max internal buffer length, longer would be clamped.
	)

	track_function = "model"
	track_param = "file"
	@tracking.report_error
	def execute(self, context):
		filename = os.path.splitext(os.path.basename(self.filepath))[0]
		if not self.filepath or not os.path.isfile(self.filepath):
			self.report({"ERROR"}, "Filepath not found")
			return {'CANCELLED'}
		if not self.filepath.lower().endswith(".json"):
			self.report(
				{"ERROR"}, "File is not json: " + self.filepath)
			return {'CANCELLED'}

		try:
			obj = add_model(os.path.normpath(self.filepath), filename)
		except ModelException as e:
			self.report({"ERROR"}, "Encountered error: " + str(e))
			return {'CANCELLED'}

		self.place_model(obj)
		self.post_spawn(context, obj)
		return {'FINISHED'}


class MCPREP_OT_reload_models(bpy.types.Operator):
	"""Reload model spawner, use after adding/removing/renaming files in the resource pack folder"""
	bl_idname = "mcprep.reload_models"
	bl_label = "Reload models"

	@tracking.report_error
	def execute(self, context):
		update_model_list(context)
		return {'FINISHED'}


classes = (
	MCPREP_OT_spawn_minecraft_model,
	MCPREP_OT_import_minecraft_model_file,
	MCPREP_OT_reload_models,
)


def register():
	util.make_annotations(ModelSpawnBase)  # Don't register, only annotate.
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)

	if util.bv28():
		bpy.types.TOPBAR_MT_file_import.append(draw_import_mcmodel)


def unregister():
	if util.bv28():
		bpy.types.TOPBAR_MT_file_import.remove(draw_import_mcmodel)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
