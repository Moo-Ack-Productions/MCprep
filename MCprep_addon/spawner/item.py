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
from bpy_extras.io_utils import ImportHelper
import mathutils

from .. import util
from .. import tracking
from ..conf import env
from ..materials import generate 
try:
	import bpy.utils.previews
except ImportError:
	pass

# -----------------------------------------------------------------------------
# Support functions
# -----------------------------------------------------------------------------


def reload_items(context):
	"""Reload the items UI list for spawning"""

	mcprep_props = context.scene.mcprep_props
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	extensions = [".png", ".jpg", ".jpeg"]

	mcprep_props.item_list.clear()
	if env.use_icons and env.preview_collections["items"]:
		try:
			bpy.utils.previews.remove(env.preview_collections["items"])
		except Exception as e:
			print(e)
			env.log("MCPREP: Failed to remove icon set, items")

	# Check levels
	lvl_1 = os.path.join(resource_folder, "textures")
	lvl_2 = os.path.join(resource_folder, "minecraft", "textures")
	lvl_3 = os.path.join(resource_folder, "assets", "minecraft", "textures")

	if not os.path.isdir(resource_folder):
		env.log("Error, resource folder does not exist")
		return
	elif os.path.isdir(lvl_1):
		resource_folder = lvl_1
	elif os.path.isdir(lvl_2):
		resource_folder = lvl_2
	elif os.path.isdir(lvl_3):
		resource_folder = lvl_3

	search_paths = [
		resource_folder,
		os.path.join(resource_folder, "items"),
		os.path.join(resource_folder, "item")]
	files = []

	for path in search_paths:
		if not os.path.isdir(path):
			continue
		files += [
			os.path.join(path, item_file)
			for item_file in os.listdir(path)
			if os.path.isfile(os.path.join(path, item_file))
			and os.path.splitext(item_file.lower())[-1] in extensions]
	for i, item_file in enumerate(sorted(files)):
		basename = os.path.splitext(os.path.basename(item_file))[0]
		asset = mcprep_props.item_list.add()
		asset.name = basename.replace("_", " ")
		asset.description = "Spawn one " + basename
		asset.path = item_file
		asset.index = i

		# if available, load the custom icon too
		if not env.use_icons or env.preview_collections["items"] == "":
			continue
		env.preview_collections["items"].load(
			"item-{}".format(i), item_file, 'IMAGE')

	if mcprep_props.item_list_index >= len(mcprep_props.item_list):
		mcprep_props.item_list_index = len(mcprep_props.item_list) - 1


def spawn_item_from_filepath(
	context, path, max_pixels, thickness, threshold, transparency):
	"""Reusable function for generating an item from an image filepath

	Arguments
		context
		path: Full path to image file
		max_pixels: int, maximum number of output faces, will scale down
		thickness: Thickness of the solidfy modifier, minimum 0
		threshold: float, alpha value below which faces will be removed
		transparency: bool, remove faces below threshold
	"""

	# Load image and initialize objects.
	image = None  # Image datablock.
	img_str = os.path.basename(path)
	name = os.path.splitext(img_str)[0]
	abspath = bpy.path.abspath(path)

	if img_str in bpy.data.images and bpy.path.abspath(
			bpy.data.images[img_str].filepath) == abspath:
		image = bpy.data.images[img_str]
	elif not path or not os.path.isfile(abspath):
		return None, "File not found"
	else:
		image = bpy.data.images.load(abspath)

	# Scale image
	pix = len(image.pixels) / 4
	if pix > max_pixels:
		# Find new pixel sizes keeping aspect ratio, equation of:
		# max_pixels = nwith * nheight
		# max_pixels = (nheight * aspect) * nheight
		# nheight = sqrtoot(max_pixels / aspect)
		aspect = image.size[0] / image.size[1]
		nheight = (max_pixels / aspect)**0.5
		image.scale(int(nheight * aspect), int(nheight))
		pix = len(image.pixels)

	width = image.size[0]  # ie columns.
	height = image.size[1]  # ie rows.

	if width == 0 or height == 0:
		return None, "Image has invalid 0-size dimension"

	w_even_add = (-0.5 if width % 2 == 0 else 0) + width
	h_even_add = (-0.5 if height % 2 == 0 else 0) + height

	# new method, start with a UV grid and delete faces from there
	if bpy.app.version >= (2, 93):  # Index changed
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height,  # Outter edges count as a subdiv.
			y_subdivisions=width,  # Outter edges count as a subdiv.
			size=2,
			calc_uvs=True,
			location=(0, 0, 0))
	elif util.bv28():
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height + 1,  # Outter edges count as a subdiv.
			y_subdivisions=width + 1,  # Outter edges count as a subdiv.
			size=2,
			calc_uvs=True,
			location=(0, 0, 0))
	elif bpy.app.version < (2, 77):  # Could be 2.76 even.
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height + 1,  # Outter edges count as a subdiv.
			y_subdivisions=width + 1,  # Outter edges count as a subdiv.
			radius=1,
			location=(0, 0, 0))
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.uv.unwrap()
		bpy.ops.object.mode_set(mode='OBJECT')
	else:
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height + 1,  # Outter edges count as a subdiv.
			y_subdivisions=width + 1,  # Outter edges count as a subdiv.
			radius=1,
			calc_uvs=True,
			location=(0, 0, 0))
	itm_obj = context.object

	if not itm_obj:
		print("Error, could not create the item primitive object")
		return None, "Could not create the item primitive object"

	# Scale the object to match ratio, keeping max dimension as set above.
	if width < height:
		itm_obj.scale[0] = width / height
	elif height < width:
		itm_obj.scale[1] = height / width

	# Apply scale transform (funcitonally, applies ALL loc, rot, scale).
	itm_obj.data.transform(itm_obj.matrix_world)
	itm_obj.matrix_world = mathutils.Matrix()

	# Deselect faces now, as setting face.select = False doens't work even
	# though using face.select = True does work.
	bpy.ops.object.mode_set(mode='EDIT')
	bpy.ops.mesh.select_mode(type='FACE')  # Ideally capture initial state.
	bpy.ops.mesh.select_all(action='DESELECT')
	bpy.ops.object.mode_set(mode='OBJECT')

	if transparency is True:
		# Lazy load alpha part of image to memory, hold for whole operator.
		alpha_faces = list(image.pixels)[3::4]
		# uv = itm_obj.data.uv_layers.active
		for face in itm_obj.data.polygons:
			if len(face.loop_indices) < 3:
				continue

			# Since we just generated UVs and the mesh, safe to get img
			# coords from face cetner, offset from obj center.
			img_x = int((face.center[0] * width + w_even_add) / 2)
			img_y = int((face.center[1] * height + h_even_add) / 2)

			# Now verify this index of image is below alpha threshold.
			if len(alpha_faces) > img_y * height + img_x:
				alpha = alpha_faces[img_y * height + img_x]
			else:  # This shouldn't occur, but reports were filed.
				continue
			if alpha < threshold:
				face.select = True

		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.delete(type='FACE')
		bpy.ops.object.mode_set(mode='OBJECT')

	itm_obj.location = util.get_cuser_location(context)

	# Material and Textures.
	# TODO: use the generate functions here instead
	mat = bpy.data.materials.new(name)
	mat.name = name

	# Replace this with generate materials?
	engine = bpy.context.scene.render.engine
	if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		tex = bpy.data.textures.new(name, type='IMAGE')
		tex.image = image
		mat.specular_intensity = 0
		mtex = mat.texture_slots.add()
		mtex.texture = tex
		tex.name = name
		tex.use_interpolation = 0
		tex.use_mipmap = 0
		tex.filter_type = 'BOX'
		tex.filter_size = 0.1
		if transparency is True:
			mat.use_transparency = 1
			mat.alpha = 0
			mat.texture_slots[0].use_map_alpha = 1
	elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
		mat.use_nodes = True
		nodes = mat.node_tree.nodes
		links = mat.node_tree.links
		for node in nodes:
			nodes.remove(node)

		tex_node = generate.create_node(nodes, 'ShaderNodeTexImage', image = image, interpolation = 'Closest', location = (-400,0))
		diffuse_node = generate.create_node(nodes, "ShaderNodeBsdfDiffuse", location = (-200,-100))
		output_node = generate.create_node(nodes, 'ShaderNodeOutputMaterial', location = (200,0))

		if transparency == 0:
			links.new(tex_node.outputs[0], diffuse_node.inputs[0])
			links.new(diffuse_node.outputs[0], output_node.inputs[0])
		else:
			transp_node = generate.create_node(nodes, 'ShaderNodeBsdfTransparent', location = (-200,100))
			mix_node = generate.create_node(nodes, 'ShaderNodeMixShader')
			links.new(tex_node.outputs[0], diffuse_node.inputs[0])
			links.new(diffuse_node.outputs[0], mix_node.inputs[2])
			links.new(transp_node.outputs[0], mix_node.inputs[1])
			links.new(tex_node.outputs[1], mix_node.inputs[0])
			links.new(mix_node.outputs[0], output_node.inputs[0])

	# Final object updated
	if thickness > 0:
		mod = itm_obj.modifiers.new(type='SOLIDIFY', name='Solidify')
		mod.thickness = thickness / max([width, height])
		mod.offset = 0
	itm_obj.data.name = name
	bpy.context.object.data.materials.append(mat)
	itm_obj.name = name

	# set the image, mostly just relevant to blender internal
	if hasattr(itm_obj.data, "uv_textures"):
		for uv_face in itm_obj.data.uv_textures.active.data:
			uv_face.image = image
	return itm_obj, None


# -----------------------------------------------------------------------------
# Operator classes
# -----------------------------------------------------------------------------


class ItemSpawnBase():
	"""Class to inheret reused MCprep item spawning settings and functions."""

	# TODO: add options like spawning attached to rig hand or other,
	size = bpy.props.FloatProperty(
		name="Size",
		default=1.0,
		min=0.001,
		description="Size in blender units of the item")
	thickness = bpy.props.FloatProperty(
		name="Thickness",
		default=1.0,
		min=0.0,
		description=(
			"The thickness of the item (this can later be changed in "
			"modifiers)"))
	transparency = bpy.props.BoolProperty(
		name="Remove transparent faces",
		description="Transparent pixels will be transparent once rendered",
		default=True)
	threshold = bpy.props.FloatProperty(
		name="Transparent threshold",
		description="1.0 = zero tolerance, no transparent pixels will be generated",
		default=0.5,
		min=0.0,
		max=1.0)
	max_pixels = bpy.props.IntProperty(
		name="Max pixels",
		default=50000,
		min=1,
		description=(
			"If needed, scale down image to generate less than this maximum "
			"pixel count"))
	scale_uvs = bpy.props.FloatProperty(
		name="Scale UVs",
		default=0.75,
		description="Scale individual UV faces of the generated item")
	filepath = bpy.props.StringProperty(
		default="",
		subtype="FILE_PATH",
		options={'HIDDEN', 'SKIP_SAVE'})
	skipUsage = bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		pose_active = context.mode == 'POSE' and context.active_bone
		return context.mode == 'OBJECT' or pose_active

	def spawn_item_execution(self, context):
		"""Common execution for both spawn item from filepath and list."""
		if context.mode == 'POSE' and context.active_bone:
			spawn_in_pose = True
			# If in pose mode, assume that we are going to add the item
			# parented to the active bone, but still switch to object mode.
			arma_bone = context.active_bone
			arma_obj = context.object
			bpy.ops.object.mode_set(mode='OBJECT')
		else:
			spawn_in_pose = False

		obj, status = spawn_item_from_filepath(
			context, self.filepath, self.max_pixels,
			self.thickness * self.size, self.threshold, self.transparency)

		# apply additional settings
		# generate materials via prep, without re-loading image datablock
		if status == "File not found" and not obj:
			self.report({'WARNING'}, status)
			bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif status and not obj:
			self.report({'ERROR'}, status)
			return {'CANCELLED'}
		elif status:
			self.report({'INFO'}, status)

		# Apply other settings such as overall object scale and uv face scale.
		for i in range(3):
			obj.scale[i] *= 0.5 * self.size
		bpy.ops.object.transform_apply(scale=True, location=False)
		bpy.ops.mcprep.scale_uv(
			scale=self.scale_uvs, selected_only=False, skipUsage=True)

		# If originally in pose mode, do any further movement and parenting.
		if spawn_in_pose:
			# bpy.ops.object.parent_set(type='BONE')
			obj.parent = arma_obj
			obj.parent_type = 'BONE'
			obj.parent_bone = arma_bone.name
			obj.location = (0, 0, 0)
		return {'FINISHED'}


class MCPREP_OT_spawn_item(bpy.types.Operator, ItemSpawnBase):
	"""Spawn in an item as a mesh from selected list item"""
	bl_idname = "mcprep.spawn_item"
	bl_label = "Spawn selected item"
	bl_options = {'REGISTER', 'UNDO'}

	track_function = "item"
	track_param = "list"
	@tracking.report_error
	def execute(self, context):
		"""Execute either taking image from UIList or from active UV image"""
		sima = context.space_data
		if not self.filepath:
			scn_props = context.scene.mcprep_props
			if not scn_props.item_list:
				self.report(
					{'ERROR'}, "No filepath input, and no items in list loaded")
				return {'CANCELLED'}
			self.filepath = scn_props.item_list[scn_props.item_list_index].path
			self.track_param = "list"
		elif sima.type == 'IMAGE_EDITOR' and sima.image:
			self.track_param = "uvimage"
		else:
			self.track_param = "shiftA"

		return self.spawn_item_execution(context)


class MCPREP_OT_spawn_item_from_file(bpy.types.Operator, ImportHelper, ItemSpawnBase):
	"""Spawn in an item as a mesh from an image file"""
	bl_idname = "mcprep.spawn_item_file"
	bl_label = "Item from file"

	filter_glob = bpy.props.StringProperty(
		default="",
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(
		type=bpy.types.PropertyGroup,
		options={'HIDDEN', 'SKIP_SAVE'})
	filter_image = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'})

	track_function = "item"
	track_param = "from file"
	@tracking.report_error
	def execute(self, context):
		if not self.filepath:
			self.report({"WARNING"}, "No image selected, cancelling")
			return {'CANCELLED'}
		return self.spawn_item_execution(context)


class MCPREP_OT_reload_items(bpy.types.Operator):
	"""Reload item spawner, use after adding/removing/renaming files in the resource pack folder"""
	bl_idname = "mcprep.reload_items"
	bl_label = "Reload items"

	@tracking.report_error
	def execute(self, context):
		reload_items(context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_spawn_item,
	MCPREP_OT_spawn_item_from_file,
	MCPREP_OT_reload_items,
)


def register():
	util.make_annotations(ItemSpawnBase)  # Don't register, only annotate.
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
