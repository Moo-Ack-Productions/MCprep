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
from .. import tracking
from .. import util
from . import sync


def default_material_in_sync_library(default_material, context):
	"""Returns true if the material is in the sync mat library blend file"""
	if conf.material_sync_cache is None:
		sync.reload_material_sync_library(context)
	if util.nameGeneralize(default_material) in conf.material_sync_cache:
		return True
	elif default_material in conf.material_sync_cache:
		return True
	return False


def sync_default_material(context, material, default_material, engine):
	"""
	This is ideitical to the normal sync materials function but it also copies
	the material and changes the name
	"""
	if default_material in conf.material_sync_cache:
		import_name = default_material
	elif util.nameGeneralize(default_material) in conf.material_sync_cache:
		import_name = util.nameGeneralize(default_material)

	# if link is true, check library material not already linked
	sync_file = sync.get_sync_blend(context)

	# I'm no Python expert (I prefer C++) but Google tells me that this means to copy all the elements 
	# -StandingPad
	init_mats = bpy.data.materials[:]
	util.bAppendLink(os.path.join(sync_file, "Material"), import_name, False) # no linking

	imported = set(bpy.data.materials[:]) - set(init_mats)
	if not imported:
		return "Could not import " + str(material.name)
	new_material = list(imported)[0]

	# checking if there's a node with the label Texture
	new_material_nodes = new_material.node_tree.nodes
	if not new_material_nodes.get("MCPREP_diffuse"):
		return "Material has no MCPREP_diffuse node"

	# Copy the material and change the name
	new_default_material = new_material.copy()

	if not material.node_tree.nodes:
		return "Material has no nodes"

	# Change the texture
	new_default_material_nodes = new_default_material.node_tree.nodes
	material_nodes = material.node_tree.nodes

	if not material_nodes.get("Image Texture"):
		return "Material has no Image Texture node"

	default_texture_node = new_default_material_nodes.get("MCPREP_diffuse")
	ImageTexture = material_nodes.get("Image Texture").image.name
	TextureFile = bpy.data.images.get(ImageTexture)
	default_texture_node.image = TextureFile

	if engine == "cycles" or engine == "blender_eevee":
		default_texture_node.interpolation = 'Closest'

	# 2.78+ only, else silent failure
	res = util.remap_users(material, new_default_material)
	if res != 0:
		# try a fallback where we at least go over the selected objects
		return res

	# remove the old material since we're changing the default and we don't
	# want to overwhelm users
	bpy.data.materials.remove(material)
	new_default_material.name = material.name
	return None


class MCPREP_OT_default_material(bpy.types.Operator):
	bl_idname = "mcprep.sync_default_materials"
	bl_label = "Sync Default Materials"
	bl_options = {'REGISTER', 'UNDO'}

	use_pbr = bpy.props.BoolProperty(
		name="Use PBR",
		description="Use PBR or not",
		default=False)

	engine = bpy.props.StringProperty(
		name="engine To Use",
		description="Defines the engine to use",
		default="cycles")

	SIMPLE = "simple"
	PBR = "pbr"

	track_function = "sync_default_materials"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		# Sync file stuff.
		sync_file = sync.get_sync_blend(context)
		if not os.path.isfile(sync_file):
			self.report({'ERROR'}, "Sync file not found: " + sync_file)
			return {'CANCELLED'}

		if sync_file == bpy.data.filepath:
			return {'CANCELLED'}

		# Find the default material.
		material_name = material_name = f"default_{self.SIMPLE if not self.use_pbr else self.PBR}_{self.engine}"
		if not default_material_in_sync_library(material_name, context):
			self.report({'ERROR'}, "No default material found")
			return {'CANCELLED'}

		# Sync materials.
		mat_list = list(bpy.data.materials)
		for mat in mat_list:
			try:
				err = sync_default_material(context, mat, material_name, self.engine) # no linking
				if err:
					conf.log(err)
			except Exception as e:
				print(e)

		return {'FINISHED'}


class MCPREP_OT_create_default_material(bpy.types.Operator):
	bl_idname = "mcprep.create_default_material"
	bl_label = "Create Default Material"
	bl_options = {'REGISTER', 'UNDO'}

	SIMPLE = "simple"
	PBR = "pbr"

	def execute(self, context):
		engine = context.scene.render.engine
		self.create_default_material(context, engine.lower(), "simple")
		return {'FINISHED'}

	def create_default_material(self, context, engine, type):
		"""
		create_default_material: takes 3 arguments and returns nothing
		context: Blender Context
		engine: the render engine in lowercase
		type: the type of texture that's being dealed with
		"""
		if not len(bpy.context.selected_objects):
			"""
			If there's no selected objects
			"""
			self.report({'ERROR'}, "Select an object to create the material")
			return

		material_name = "default_{type}_{engine}".format(
			type=type,
			engine=engine
		)
		default_material = bpy.data.materials.new(name=material_name)
		default_material.use_nodes = True
		nodes = default_material.node_tree.nodes
		links = default_material.node_tree.links
		nodes.clear()

		default_texture_node = nodes.new(type="ShaderNodeTexImage")
		principled = nodes.new("ShaderNodeBsdfPrincipled")
		nodeOut = nodes.new("ShaderNodeOutputMaterial")

		default_texture_node.name = "MCPREP_diffuse"
		default_texture_node.label = "Diffuse Texture"
		default_texture_node.location = (120, 0)

		principled.inputs["Specular"].default_value = 0
		principled.location = (600, 0)

		nodeOut.location = (820, 0)

		links.new(default_texture_node.outputs[0], principled.inputs[0])
		links.new(principled.outputs["BSDF"], nodeOut.inputs[0])

		if engine is "eevee":
			if hasattr(default_material, "blend_method"):
				default_material.blend_method = 'HASHED'
			if hasattr(default_material, "shadow_method"):
				default_material.shadow_method = 'HASHED'


classes = (
	MCPREP_OT_default_material,
	MCPREP_OT_create_default_material,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)
	bpy.app.handlers.load_post.append(sync.clear_sync_cache)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	try:
		bpy.app.handlers.load_post.remove(sync.clear_sync_cache)
	except:
		pass
