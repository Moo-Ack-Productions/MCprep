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

from .. import conf
from .. import util
from .. import tracking

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
	resource_folder = context.scene.mcprep_texturepack_path
	extensions = [".png",".jpg",".jpeg"]

	mcprep_props.item_list.clear()
	if conf.use_icons and conf.preview_collections["items"]:
		try:
			bpy.utils.previews.remove(conf.preview_collections["items"])
		except:
			conf.log("MCPREP: Failed to remove icon set, items")

	if not os.path.isdir(resource_folder):
		conf.log("Error, resource folder does not exist")
		return
	elif os.path.isdir(os.path.join(resource_folder,"textures")):
		resource_folder = os.path.join(resource_folder,"textures")
	elif os.path.isdir(os.path.join(resource_folder,"minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"minecraft","textures")
	elif os.path.isdir(os.path.join(resource_folder,"assets","minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"assets","minecraft","textures")

	search_paths = [
		resource_folder,
		os.path.join(resource_folder,"items"),
		os.path.join(resource_folder,"item")]
	files = []

	for path in search_paths:
		if not os.path.isdir(path):
			continue
		files += [os.path.join(path, item_file)
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
		if not conf.use_icons or conf.preview_collections["items"] == "":
			continue
		conf.preview_collections["items"].load(
			"item-{}".format(i), item_file, 'IMAGE')

	if mcprep_props.item_list_index >= len(mcprep_props.item_list):
		mcprep_props.item_list_index = len(mcprep_props.item_list) - 1


def spawn_item_from_filepath(context, path, max_pixels, thickness, threshold,
	transparency):
	"""Reusable function for generating an item from an image filepath

	Arguments
		context
		path: full path to image file
		max_pixels: int, maximum number of output faces, will scale down
		thickness: Thickness of the solidfy modifier, minimum 0
		threshold: float, alpha value below which faces will be removed
		transparency: bool, remove faces below threshold
	"""

	# load image and initialize objects
	image = None  # image datablock
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
	pix = len(image.pixels)/4
	if pix > max_pixels:
		# TODO: remove loop and do more direct resizing
		while pix > max_pixels:
			width = image.size[0]
			height = image.size[1]
			image.scale(width/1.5,height/1.5)
			pix = len(image.pixels)/4
	width = image.size[0] # ie columns
	height = image.size[1] # ie rows

	w_even_add = (-0.5 if width%2==0 else 0) + width
	h_even_add = (-0.5 if height%2==0 else 0) + height

	# new method, start with a UV grid and delete faces from there
	if util.bv28():
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height+1, # outter edges count as a subdiv
			y_subdivisions=width+1, # outter edges count as a subdiv
			size=2,
			calc_uvs=True,
			location=(0,0,0))
	elif bpy.app.version < (2, 77): # could be 2, 76 even
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height+1, # outter edges count as a subdiv
			y_subdivisions=width+1, # outter edges count as a subdiv
			radius=1,
			location=(0,0,0))
		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.uv.unwrap()
		bpy.ops.object.mode_set(mode='OBJECT')
	else:
		bpy.ops.mesh.primitive_grid_add(
			x_subdivisions=height+1, # outter edges count as a subdiv
			y_subdivisions=width+1, # outter edges count as a subdiv
			radius=1,
			calc_uvs=True,
			location=(0,0,0))
	itm_obj = context.object

	# scale the object to match ratio, keeping max dimension as set above
	if width < height:
		itm_obj.scale[0] = width/height
	elif height < width:
		itm_obj.scale[1] = height/width
	bpy.ops.object.transform_apply(scale=True)

	# Deselect faces now, as seetting face.select = False doens't work even
	# though using face.select = True does work
	bpy.ops.object.mode_set(mode='EDIT')
	bpy.ops.mesh.select_mode(type='FACE')  # ideally capture initial state
	bpy.ops.mesh.select_all(action='DESELECT')
	bpy.ops.object.mode_set(mode='OBJECT')

	if transparency is True:
		# lazy load alpha part of image to memory, hold for whole operator
		alpha_faces = list(image.pixels)[3::4]
		uv = itm_obj.data.uv_layers.active
		for face in itm_obj.data.polygons:
			if len(face.loop_indices) < 3:
				continue

			# since we just generated UVs and the mesh, safe to get img
			# coords from face cetner, offset from obj center
			img_x = int((face.center[0]*width + w_even_add)/2)
			img_y = int((face.center[1]*height + h_even_add)/2)

			# now verify this index of image is below alpha threshold
			alpha = alpha_faces[img_y*height + img_x]
			if alpha < threshold:
				face.select = True

		bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.delete(type='FACE')
		bpy.ops.object.mode_set(mode='OBJECT')

	itm_obj.location = util.get_cuser_location(context)

	# Material and Textures
	# TODO: use the generate functions here instead
	mat = bpy.data.materials.new(name)
	mat.name = name

	# replace this with generate materials?
	engine = bpy.context.scene.render.engine
	if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
		tex = bpy.data.textures.new(name, type = 'IMAGE')
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
	elif engine=='CYCLES' or engine=='BLENDER_EEVEE':
		mat.use_nodes = True
		nodes = mat.node_tree.nodes
		links = mat.node_tree.links
		for node in nodes:
			nodes.remove(node)

		diffuse_node = nodes.new(type="ShaderNodeBsdfDiffuse")
		tex_node = nodes.new(type='ShaderNodeTexImage')
		output_node = nodes.new(type='ShaderNodeOutputMaterial')
		tex_node.image = image
		tex_node.interpolation = 'Closest'

		if transparency == 0:
			links.new(tex_node.outputs[0], diffuse_node.inputs[0])
			links.new(diffuse_node.outputs[0], output_node.inputs[0])

			diffuse_node.location[0] -= 200
			diffuse_node.location[1] -= 100
			tex_node.location[0] -= 400
			output_node.location[0] += 200
		else:
			transp_node = nodes.new(type='ShaderNodeBsdfTransparent')
			mix_node = nodes.new(type='ShaderNodeMixShader')
			links.new(tex_node.outputs[0], diffuse_node.inputs[0])
			links.new(diffuse_node.outputs[0], mix_node.inputs[2])
			links.new(transp_node.outputs[0], mix_node.inputs[1])
			links.new(tex_node.outputs[1], mix_node.inputs[0])
			links.new(mix_node.outputs[0], output_node.inputs[0])

			transp_node.location[0] -= 200
			transp_node.location[1] += 100
			diffuse_node.location[0] -= 200
			diffuse_node.location[1] -= 100
			tex_node.location[0] -= 400
			output_node.location[0] += 200

	# Final object updated
	if thickness > 0:
		mod = itm_obj.modifiers.new(type='SOLIDIFY', name='Solidify')
		mod.thickness = thickness/max([width, height])
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


class MCPREP_OT_spawn_item(bpy.types.Operator):
	"""Spawn in an item as a mesh from selected list item"""
	bl_idname = "mcprep.spawn_item"
	bl_label = "Spawn selected item"
	bl_options = {'REGISTER', 'UNDO'}

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
		description="The thickness of the item (this can later be changed in modifiers)")
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
		description="If needed, scale down image to generate less than this maximum pixel count")
	scale_uvs = bpy.props.FloatProperty(
		name="Scale UVs",
		default=0.75,
		description="Scale individual UV faces of the generated item")
	filepath = bpy.props.StringProperty(
		default="",
		options={'HIDDEN', 'SKIP_SAVE'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	track_function = "item"
	track_param = "list"
	@tracking.report_error
	def execute(self, context):
		"""Execute either taking image from UIList or from active UV image"""
		sima = context.space_data
		if not self.filepath:
			scn_props = context.scene.mcprep_props
			self.filepath = scn_props.item_list[scn_props.item_list_index].path
			self.track_param = "list"
		elif sima.type == 'IMAGE_EDITOR' and sima.image:
			self.track_param = "uvimage"
		else:
			self.track_param = "shiftA"

		obj, status = spawn_item_from_filepath(
			context, self.filepath, self.max_pixels,
			self.thickness*self.size, self.threshold, self.transparency)

		# apply additional settings
		# generate materials via prep, without re-loading image datablock
		if status and not obj:
			self.report({'ERROR'}, status)
			return {'CANCELLED'}
		elif status:
			self.report({'INFO'}, status)

		# apply other settings such as overall object scale and uv face scale
		for i in range(3):
			obj.scale[i] *= 0.5 * self.size
		bpy.ops.object.transform_apply(scale=True, location=False)
		bpy.ops.mcprep.scale_uv(
			scale=self.scale_uvs, selected_only=False, skipUsage=True)
		#bpy.ops.object.mode_set(mode='OBJECT')
		return {'FINISHED'}


class MCPREP_OT_spawn_item_from_file(bpy.types.Operator, ImportHelper):
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

	size = bpy.props.FloatProperty(
		name="Size",
		default=1.0,
		min=0.001,
		description="Size in blender units of the item")
	thickness = bpy.props.FloatProperty(
		name="Thickness",
		default=1.0,
		min=0.0,
		description="The thickness of the item (this can later be changed in modifiers)")
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
	scale_uvs = bpy.props.FloatProperty(
		name="Scale UVs",
		default=0.75,
		description="Scale individual UV faces of the generated item")
	max_pixels = bpy.props.IntProperty(
		name="Max pixels",
		default=50000,
		min=1,
		description="If the image selected contains more pixels than given number the image will be scaled down")

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	track_function = "item"
	track_param = "from file"
	@tracking.report_error
	def execute(self, context):
		if not self.filepath:
			self.report({"WARNING"}, "No image selected, canceling")
			return {'CANCELLED'}

		obj, status = spawn_item_from_filepath(context, self.filepath,
			self.max_pixels, self.thickness, self.threshold, self.transparency)

		if status and not obj:
			self.report({'ERROR'}, status)
			return {'CANCELLED'}
		elif status:
			self.report({'INFO'}, status)

		# apply other settings such as overall object scale and uv face scale
		for i in range(3):
			obj.scale[i] *= 0.5 * self.size
		bpy.ops.object.transform_apply(scale=True, location=False)
		bpy.ops.mcprep.scale_uv(scale=self.scale_uvs, selected_only=False)
		return {"FINISHED"}


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
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
