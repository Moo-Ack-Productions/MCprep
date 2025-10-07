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
from bpy.types import Context, Material
from bpy_extras.io_utils import ImportHelper

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union, Optional
import json

from .. import tracking
from .. import util
from ..conf import MCprepError, env
from . import generate
from . import sync
from . import vivy_utils as vu
from .generate import checklist, get_mc_canonical_name

@dataclass
class VivyOptions:
	source_mat: str
	material: vu.VivyMaterial
	passes: Dict[str, str]
	fallback: Optional[vu.Fallback]

CACHED_MATERIALS: Dict[str, Material] = {}
MAT_TO_IMPORT: Dict[str, str] = {}

def reload_material_vivy_library(context: Context) -> None:
	"""Reloads the library and cache"""
	sync_file = get_vivy_blend()
	if not sync_file.exists():
		env.log("Vivy file not found", vv_only=True)
		env.vivy_cache = []
		return

	with bpy.data.libraries.load(str(sync_file)) as (data_from, _):
		env.vivy_cache = list(data_from.materials)
	env.log("Updated Vivy cache", vv_only=True)

def material_in_vivy_library(material: str, context: Context) -> bool:
	"""Returns true if the material is in the sync mat library blend file."""
	if env.vivy_cache is None:
		reload_material_vivy_library(context)
	if util.nameGeneralize(material) in env.vivy_cache:
		return True
	elif material in env.vivy_cache:
		return True
	return False

def set_material(context: Context, material: Material, options: VivyOptions) -> Optional[Union[Material, str]]:
	if isinstance(options.material.refinements, vu.VivyRefinements):
		ext = options.material.refinements
		if ext.emissive is not None:
			matGen = util.nameGeneralize(options.source_mat)
			canon, _ = get_mc_canonical_name(matGen)
			if checklist(canon, "emit"):
				options.material.base_material = ext.emissive
		if ext.reflective is not None:
			matGen = util.nameGeneralize(options.source_mat)
			canon, _ = get_mc_canonical_name(matGen)
			if checklist(canon, "reflective"):
				options.material.base_material = ext.reflective
		if ext.metallic is not None:
			matGen = util.nameGeneralize(options.source_mat)
			canon, _ = get_mc_canonical_name(matGen)
			if checklist(canon, "metallic"):
				options.material.base_material = ext.metallic
		if ext.glass is not None:
			matGen = util.nameGeneralize(options.source_mat)
			canon, _ = get_mc_canonical_name(matGen)
			if checklist(canon, "glass"):
				options.material.base_material = ext.glass

		# Fallbacks in case texture swap with PBR fails
		if options.fallback is not None:
			if options.fallback == vu.Fallback.FALLBACK_S and ext.fallback_s is not None:
				options.material.base_material = ext.fallback_s
				options.material.passes.specular = None
			elif options.fallback == vu.Fallback.FALLBACK_N and ext.fallback_n is not None:
				options.material.base_material = ext.fallback_n
				options.material.passes.normal = None
			elif options.fallback == vu.Fallback.FALLBACK and ext.fallback is not None:
				options.material.base_material = ext.fallback
				options.material.passes.specular = None
				options.material.passes.normal = None

	import_name: Optional[str] = None
	if options.material.base_material in env.vivy_cache:
		import_name = options.material.base_material
	elif util.nameGeneralize(options.material.base_material) in env.vivy_cache:
		import_name = util.nameGeneralize(options.material.base_material)

	if not import_name:
		return "Can't have None for import name"

	# If link is true, check library material not already linked.
	sync_file = get_vivy_blend()

	init_mats = list(bpy.data.materials)
	path = os.path.join(str(sync_file), "Material")

	if import_name not in CACHED_MATERIALS:
		util.bAppendLink(path, import_name, False)  # No linking.

		imported = set(list(bpy.data.materials)) - set(init_mats)
		if not imported:
			return f"Could not import {import_name}"
		CACHED_MATERIALS[import_name] = list(imported)[0]
	
	# Set the passes
	passes = [(options.material.passes.diffuse, "diffuse"), 
		   (options.material.passes.specular, "specular"), 
		   (options.material.passes.normal, "normal")]

	replacement_mat = CACHED_MATERIALS[import_name].copy()

	for p in passes:
		if p[0] is not None:
			new_material_nodes = replacement_mat.node_tree.nodes
			if not new_material_nodes.get(p[0]):
				return f"Material has no {p[1]} node"

			if not material.node_tree.nodes:
				return "Material has no nodes"

			nnodes = replacement_mat.node_tree.nodes
			material_nodes = material.node_tree.nodes

			if not material_nodes.get("Image Texture") and not material_nodes.get(options.material.passes.diffuse):
				return "Material has no Image Texture node"
			
			nnode_diffuse = nnodes.get(p[0])
			nnode_diffuse.image = options.passes[p[1]]

	material.user_remap(replacement_mat)
	m_name = material.name
	bpy.data.materials.remove(material)
	replacement_mat.name = m_name
	MAT_TO_IMPORT[m_name] = import_name
	return None

def get_vivy_blend() -> Path:
	"""Return the path of the Vivy material library"""
	try:
		return Path(os.path.join(bpy.path.abspath(bpy.context.scene.vivy_file_path), "vivy_materials.blend"))
	except Exception:
		return Path("")

def get_vivy_json() -> Path:
	"""Return the path of the Vivy JSON file"""
	return Path(os.path.join(bpy.context.scene.vivy_file_path, "vivy_materials.json"))

def generate_vivy_materials(self, context, options: VivyOptions):
	# Sync file stuff.
	sync_file = get_vivy_blend()
	if not os.path.isfile(sync_file):
		self.report({'ERROR'}, f"Sync file not found: {sync_file}")
		return {'CANCELLED'}

	if sync_file == bpy.data.filepath:
		return {'CANCELLED'}

	# Find the material
	if not material_in_vivy_library(options.material.base_material, context):
		self.report({'ERROR'}, f"Material not found: {options.material.base_material}")
		return {'CANCELLED'}

	mat_list = list(bpy.data.materials)
	mat = [m for m in mat_list if m.name == options.source_mat]
	if len(mat) != 1:
		self.report({'ERROR'}, f"Could not get {options.source_mat}")
	try:
		err = set_material(context, mat[0], options) # no linking
		if err:
			env.log(err)
	except Exception as e:
		print(e)

"""
Panel related parts below
"""
class VivyMaterialProps():
	def get_materials(self, context):
		if env.vivy_material_json is None:
			with open(get_vivy_json(), 'r') as f:
				env.vivy_material_json = json.load(f)
		itms = []
		if vu.VIVY_MATERIALS in env.vivy_material_json:
			for m, d in env.vivy_material_json[vu.VIVY_MATERIALS].items():
				itms.append((m, m, d["desc"]))
		return itms

	materialName: bpy.props.EnumProperty(
		name="Material",
		description="Material to use for prepping",
		items=get_materials
	)

def draw_mats_common(self, context: Context) -> None:
	row = self.layout.row()
	row.prop(self, "materialName")

	md = vu.data_vivy_material(self.materialName)
	row = self.layout.row()
	row.label(text=md.desc)
	
	box = self.layout.box()
	box.label(text="Expects the following passes:")
	row = box.row()
	row.label(text="Diffuse", icon="MATERIAL")
	if md.passes.specular:
		row = box.row()
		row.label(text="Specular", icon="NODE_MATERIAL")
	if md.passes.normal:
		row = box.row()
		row.label(text="Normal", icon="ORIENTATION_NORMAL")
	
	if md.refinements:
		box = self.layout.box()
		box.label(text="Has refinements for the following:")
		if md.refinements.emissive:
			row = box.row()
			row.label(text="Emission", icon="OUTLINER_OB_LIGHT")
		if md.refinements.reflective:
			row = box.row()
			row.label(text="Glossy", icon="NODE_MATERIAL")
		if md.refinements.metallic:
			row = box.row()
			row.label(text="Metalic", icon="NODE_MATERIAL")
		if md.refinements.glass:
			row = box.row()
			row.label(text="Transmissive", icon="OUTLINER_OB_LIGHTPROBE")
		if md.refinements.fallback_s:
			row = box.row()
			row.label(text="Fallback for Missing Specular")
		if md.refinements.fallback_n:
			row = box.row()
			row.label(text="Fallback for Missing Normal")
		if md.refinements.fallback:
			row = box.row()
			row.label(text="Complete Fallback for No Extra Passes")

class MCPREP_OT_vivy_materials(bpy.types.Operator, VivyMaterialProps):
	"""
	Vivy's custom material generator that 
	derives much of its code from MCprep's 
	Prep materials operator
	"""
	bl_idname = "vivy.prep_materials"
	bl_label = "Vivy Materials"
	bl_options = {'REGISTER', 'UNDO'}


	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=300 * util.ui_scale())

	def draw(self, context):
		draw_mats_common(self, context)

	track_function = "vivy_materials"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
		# get list of selected objects
		obj_list = context.selected_objects
		if not obj_list:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if not mat_list:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		# check if linked material exists
		engine = context.scene.render.engine
		count = 0
		count_lib_skipped = 0

		for mat in mat_list:
			if not mat:
				env.log(
					"During prep, found null material:" + str(mat), vv_only=True)
				continue

			elif mat.library:
				count_lib_skipped += 1
				continue

			passes = generate.get_textures(mat)
			if passes.get("diffuse"):
				# Otherwise, attempt to get or load extra passes. Needed if
				# swap texturepack hasn't been used yet, otherwise would need
				# to prep twice (even if the base diff texture was already
				# loaded from that pack).
				diff_filepath = passes["diffuse"].filepath
				# bpy. makes rel to file, os. resolves any os.pardir refs.
				abspath = os.path.abspath(bpy.path.abspath(diff_filepath))
				other_passes = generate.find_additional_passes(abspath)
				for pass_name in other_passes:
					if pass_name not in passes or not passes.get(pass_name):
						# Need to update the according tagged node with tex.
						passes[pass_name] = bpy.data.images.load(
							other_passes[pass_name],
							check_existing=True)

			if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
				# Make sure Vivy has loaded the JSON
				if not isinstance(env.vivy_material_json, Dict):
					if env.vivy_material_json is None:
						with open(get_vivy_json(), 'r') as f:
							env.vivy_material_json = json.load(f)

				# Set all options and go!
				md = vu.data_vivy_material(self.materialName)
				options = VivyOptions(
					source_mat=mat.name,
					material=md,
					passes=passes,
					fallback=None
				)
				generate_vivy_materials(self, context, options)
				count += 1
			else:
				self.report(
					{'ERROR'},
					"Only Cycles and Eevee are supported")
				return {'CANCELLED'}

		if count_lib_skipped > 0:
			self.report(
				{"INFO"},
				f"Modified {count} materials, skipped {count_lib_skipped} linked ones.")
		elif count > 0:
			self.report({"INFO"}, f"Modified  {count} materials")
		else:
			self.report(
				{"ERROR"},
				"Nothing modified, be sure you selected objects with existing materials!"
			)
		
		for obj in obj_list:
			obj["VIVY_PREPPED"] = True
			obj["VIVY_MATERIAL_SET"] = json.dumps(MAT_TO_IMPORT)
			obj["VIVY_MATERIAL_BASE"] = self.materialName

		addon_prefs = util.get_user_preferences(context)
		self.track_param = context.scene.render.engine
		self.track_exporter = addon_prefs.MCprep_exporter_type
		return {'FINISHED'}

class MCPREP_OT_vivy_swap_texture_pack(
	bpy.types.Operator, ImportHelper, VivyMaterialProps):
	"""Swap current textures for that of a texture pack folder"""
	bl_idname = "vivy.swap_texture_pack"
	bl_label = "Swap Texture Pack"
	bl_description = (
		"Change the texture pack for all materials of selected objects, "
		"select a folder path for an unzipped resource pack or texture folder")
	bl_options = {'REGISTER', 'UNDO'}

	filter_glob: bpy.props.StringProperty(
		default="",
		options={"HIDDEN"})
	use_filter_folder = True
	fileselectparams = "use_filter_blender"
	filepath: bpy.props.StringProperty(subtype="DIR_PATH")
	filter_image: bpy.props.BoolProperty(
		default=True,
		options={"HIDDEN", "SKIP_SAVE"})
	filter_folder: bpy.props.BoolProperty(
		default=True,
		options={"HIDDEN", "SKIP_SAVE"})

	@classmethod
	def poll(cls, context):
		addon_prefs = util.get_user_preferences(context)
		if addon_prefs.MCprep_exporter_type != "(choose)":
			return util.is_atlas_export(context)
		return False

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		subcol = col.column()
		subcol.scale_y = 0.7
		subcol.label(text="Select any subfolder of an")
		subcol.label(text="unzipped texture pack, then")
		subcol.label(text="press 'Swap Texture Pack'")
		subcol.label(text="after confirming these")

	track_function = "vivy_texture_pack"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)

		# check folder exist, but keep relative if relevant
		folder = self.filepath
		if os.path.isfile(bpy.path.abspath(folder)):
			folder = os.path.dirname(folder)
		env.log(f"Folder: {folder}")

		if not os.path.isdir(bpy.path.abspath(folder)):
			self.report({'ERROR'}, "Selected folder does not exist")
			return {'CANCELLED'}

		# get list of selected objects
		obj_list = context.selected_objects
		if len(obj_list) == 0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}
		
		mtype_set = None
		for obj in obj_list:
			if "VIVY_PREPPED" not in obj:
				self.report({'ERROR'}, "OBJ needs to be prepped first!")
				return {'CANCELLED'}
			mtype_set = json.loads(obj["VIVY_MATERIAL_SET"])
			mbase = obj["VIVY_MATERIAL_BASE"]

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if len(obj_list) == 0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}
		_ = generate.detect_form(mat_list)

		self.track_exporter = addon_prefs.MCprep_exporter_type

		# set the scene's folder for the texturepack being swapped
		context.scene.mcprep_texturepack_path = folder

		env.log(f"Materials detected: {len(mat_list)}")
		res = 0
		for mat in mat_list:
			if mat.name not in mtype_set:
				continue
			self.preprocess_material(mat)
			res += self.set_texture_pack(context, mat, folder, mtype_set[mat.name], mbase)
			self.report({'INFO'}, f"{res} materials affected")
		self.track_param = context.scene.render.engine
		return {'FINISHED'}
	
	def preprocess_material(self, material):
		"""Preprocess materials for special edge cases"""

		# in texture packs, this is actually just a transparent overaly -
		# but in Mineways export, this is the flattened grass/drit block side
		if material.name == "grass_block_side_overlay":
			material.name = "grass_block_side"
			env.log("Renamed material: grass_block_side_overlay to grass_block_side")
	
	def set_texture_pack(self, context, material: Material, folder: Path, mtype: str, mbase: str) -> bool:
		"""Replace existing material's image with texture pack's.

		Run through and check for each if counterpart material exists, then
		run the swap (and auto load e.g. normals and specs if avail.)
		"""
		mc_name, _ = get_mc_canonical_name(material.name)
		image = generate.find_from_texturepack(mc_name, Path(folder) if not isinstance(folder, Path) else folder)

		if isinstance(image, MCprepError):
			if image.msg:
				env.log(image.msg)
			obj = bpy.context.view_layer.objects.active
			md = vu.data_vivy_material(mbase)
			options = VivyOptions(
				source_mat=material.name,
				material=md,
				passes=generate.get_textures(material),
				fallback=vu.Fallback.FALLBACK
			)
			generate_vivy_materials(self, context, options)
			return False
		
		image_data = util.loadTexture(str(image))
		_ = self.set_cycles_texture(context, image_data, material, mtype, mbase, True)
		return True

	def set_cycles_texture(self, context, image: generate.Image, material: Material, mtype: str, mbase: str, extra_passes: bool=False) -> bool:
		"""
		Used by skin swap and assiging missing textures or tex swapping.
		Args:
			image: already loaded image datablock
			material: existing material datablock
			extra_passes: whether to include or hard exclude non diffuse passes
		"""
		env.log(f"Setting cycles texture for img: {image.name} mat: {material.name}")
		if material.node_tree is None:
			return False
		# check if there is more data to see pass types
		img_sets = {}
		if extra_passes:
			img_sets = generate.find_additional_passes(image.filepath)
		changed = False

		mat_passes = None
		for mapping in vu.data_vivy_mappings(mtype):
			if mapping.material.base_material == mbase:
				continue
			
			mat_passes = mapping.material.passes
			if mapping.refinement is None:
				continue
			if mapping.refinement == vu.Fallback.FALLBACK_S or mapping.refinement == vu.Fallback.FALLBACK:
				mat_passes.specular = None
			if mapping.refinement == vu.Fallback.FALLBACK_N or mapping.refinement == vu.Fallback.FALLBACK:
				mat_passes.normal = None

		if not mat_passes:
			return False

		diffuse = mat_passes.diffuse
		specular = mat_passes.specular
		normal = mat_passes.normal

		nodes = material.node_tree.nodes
		fallback = None
		passes = {}
		if diffuse is not None:
			d = nodes.get(diffuse)
			d.image = image
			passes["diffuse"] = image
		if specular is not None:
			s = nodes.get(specular)
			if "specular" in img_sets and s is not None:
				new_img = util.loadTexture(img_sets["specular"])
				s.image = new_img
				util.apply_noncolor_data(s)
				passes["specular"] = new_img
			else:
				fallback = vu.Fallback.FALLBACK_S
		if normal is not None:
			n = nodes.get(normal)
			if "normal" in img_sets and n is not None:
				new_img = util.loadTexture(img_sets["normal"])
				n.image = new_img
				util.apply_noncolor_data(n)
				passes["normal"] = new_img 
			else:
				if fallback == vu.Fallback.FALLBACK_S:
					fallback = vu.Fallback.FALLBACK
				else:
					fallback = vu.Fallback.FALLBACK_N
		
		# use fallback material if needed
		if fallback is not None:
			obj = bpy.context.view_layer.objects.active
			md = vu.data_vivy_material(mbase)
			options = VivyOptions(
				source_mat=material.name,
				material=md,
				passes=passes,
				fallback=fallback
			)
			generate_vivy_materials(self, context, options)
			

		changed = True
		nodes.active = nodes.get(diffuse)
		return changed

classes = [
	MCPREP_OT_vivy_materials,
	MCPREP_OT_vivy_swap_texture_pack,
]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.app.handlers.load_post.append(sync.clear_sync_cache)

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	try:
		bpy.app.handlers.load_post.remove(sync.clear_sync_cache)
	except:
		pass
