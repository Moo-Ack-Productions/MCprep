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
					and os.path.splitext(item_file)[-1] in extensions]
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
	"""Reusable function for generating an item from an image filepath"""

	# TODO: Update approach to start with subdivided image plane, scaled such
	# that image pixels will be square, and then delete faces accordingly,
	# and apply scaling operator

	obj = None  # object datablock
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

	# Variables
	x = 0
	y = 0
	n = 3
	a = 0
	first = True
	area = None
	pix = len(image.pixels)/4

	# Scale image
	if pix > max_pixels:
		while pix > max_pixels:
			width = image.size[0]
			height = image.size[1]
			image.scale(width/1.5,height/1.5)
			pix = len(image.pixels)/4
	width = image.size[0]
	height = image.size[1]
	uv_width = 0.5 - 1/(width*2)
	uv_height = 0.5 - 1/(width*2)

	# Creating the mesh
	while a < pix:
		if image.pixels[n] >= threshold:
			if util.bv28():
				bpy.ops.mesh.primitive_plane_add(
					location=(x,y,0), size=.5, enter_editmode=1)
			else:
				bpy.ops.mesh.primitive_plane_add(
					location=(x,y,0), radius=.5, enter_editmode=1)
			bpy.ops.uv.unwrap()
			if util.bv28():
				bpy.context.area.type = 'UV_EDITOR'
			else:
				bpy.context.area.type = 'IMAGE_EDITOR'
			if first is True:
				bpy.context.space_data.mode = 'VIEW'
				bpy.ops.uv.select_all(action='TOGGLE')
				first = False
				bpy.ops.uv.reset()
			bpy.ops.uv.select_all(action='TOGGLE')
			bpy.ops.transform.resize(value=(0,0,0))
			tx = uv_width - x/width
			ty = uv_height - y/height
			bpy.ops.transform.translate(value=(-tx,-ty,0))
			bpy.context.area.type = 'VIEW_3D'
			x = x+1
		else:
			x = x+1
		if x>=width:
			x = 0
			y = y+1
		n = n+4
		a = a+1

	# Fix final mesh
	# TODO: avoid all ops code here.
	# bpy.ops.mesh.select_all() # action='SELECT'?
	# bpy.ops.mesh.select_all()
	bpy.ops.mesh.select_all(action='SELECT')
	bpy.ops.mesh.remove_doubles()
	bpy.ops.object.editmode_toggle()
	if thickness > 0:
		bpy.ops.object.modifier_add(type='SOLIDIFY')

	# Material and Textures
	# TODO: use the generate functions here instead
	mat = bpy.data.materials.new(name)
	mat.name = name

	# Internal
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
		# TODO: re-use material generator here
		mat.use_nodes = True
		nodes = mat.node_tree.nodes
		links = mat.node_tree.links
		if transparency == 0:
			tex_node = nodes.new(type='ShaderNodeTexImage')
			tex_node.image = image
			diffuse_node = nodes.get("Diffuse BSDF")
			links.new(tex_node.outputs[0], diffuse_node.inputs[0])
		else:
			for node in nodes:
				nodes.remove(node)
			transp_node = nodes.new(type='ShaderNodeBsdfTransparent')
			mix_node = nodes.new(type='ShaderNodeMixShader')
			tex_node = nodes.new(type='ShaderNodeTexImage')
			output_node = nodes.new(type='ShaderNodeOutputMaterial')
			tex_node.image = image
			diffuse_node = nodes.new(type="ShaderNodeBsdfDiffuse")
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

	# Final fixes to the object
	for obj in bpy.context.selected_objects:
		if thickness > 0:
			obj.modifiers['Solidify'].thickness = thickness*0.0625
			obj.modifiers['Solidify'].offset = 0.1
		obj.data.name = name
		bpy.context.object.data.materials.append(mat)
		obj.name = name
	bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
	bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN')
	bpy.ops.transform.resize(value=(0.0625,0.0625,0.0625))
	bpy.ops.object.transform_apply(scale=True)

	# set the image, mostly relevant to blender internal
	for uv_face in obj.data.uv_textures.active.data:
		uv_face.image = image

	return obj, None


# -----------------------------------------------------------------------------
# Operator classes
# -----------------------------------------------------------------------------


class MCPREP_OT_spawn_item(bpy.types.Operator):
	"""Spawn in an item as a mesh from selected list item"""
	bl_idname = "mcprep.spawn_item"
	bl_label = "Spawn selected item"
	bl_options = {'REGISTER', 'UNDO'}

	# TODO: add options like spawning attached to rig hand or other,
	max_pixels = bpy.props.IntProperty(
		name="Maximum Number of Pixels:",
		default=50000,
		min=1,
		description="If the image selected contains more pixels than given number the image will be scaled down")
	thickness = bpy.props.FloatProperty(
		name="Thickness:",
		default=1.0,
		min=0.0,
		description="The thickness of the item (this can later be changed in modifiers)")
	threshold = bpy.props.FloatProperty(
		name="Alpha Threshold:",
		description="1.0 = zero tolerance, no transparent pixels will be generated",
		default=0.5,
		min=0.0)
	transparency = bpy.props.BoolProperty(
		name="Use Transparent Pixels",
		description="Transparent pixels will be transparent once rendered",
		default=True)
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
		# 	conf.log('Reading image from image editor')
		# 	if not sima.image.filepath:
		# 		self.report({'ERROR'}, "Image must be saved to file first.")
		# 		return {'CANCELLED'}
		# 	filepath = sima.image.filepath
		# else:
		# 	scn_props = context.scene.mcprep_props
		# 	filepath = scn_props.item_list[scn_props.item_list_index].path

		obj, status = spawn_item_from_filepath(context, self.filepath,
			self.max_pixels, self.thickness, self.threshold, self.transparency)
		# apply additional settings
		# generate materials via prep, without re-loading image datablock
		if status and not obj:
			self.report({'ERROR'}, status)
			return {'CANCELLED'}
		elif status:
			self.report({'INFO'}, status)
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

	max_pixels = bpy.props.IntProperty(
		name="Maximum Number of Pixels:",
		default=50000,
		min=1,
		description="If the image selected contains more pixels than given number the image will be scaled down")
	thickness = bpy.props.FloatProperty(
		name="Thickness:",
		default=1.0,
		min=0.0,
		description="The thickness of the item (this can later be changed in modifiers)")
	threshold = bpy.props.FloatProperty(
		name="Alpha Threshold:",
		description="1.0 = zero tolerance, no transparent pixels will be generated",
		default=0.5,
		min=0.0)
	transparency = bpy.props.BoolProperty(
		name="Use Transparent Pixels",
		description="Transparent pixels will be transparent once rendered",
		default=True)

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
