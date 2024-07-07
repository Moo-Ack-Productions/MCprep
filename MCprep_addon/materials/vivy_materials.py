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
from enum import Enum

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union, Optional
import json

from .. import tracking
from .. import util
from ..conf import env
from . import generate
from . import sync
from .generate import checklist, get_mc_canonical_name

class Fallback(Enum):
	FALLBACK_S = "fallback_s"
	FALLBACK_N = "fallback_n"
	FALLBACK = "fallback"

@dataclass
class VivyPasses:
	diffuse: str 
	specular: Optional[str]
	normal: Optional[str]

@dataclass
class VivyRefinements:
	emissive: Optional[str]
	reflective: Optional[str]
	metallic: Optional[str]
	glass: Optional[str]
	fallback_n: Optional[str]
	fallback_s: Optional[str]
	fallback: Optional[str]

@dataclass
class VivyMaterial:
	base_material: str 
	desc: str 
	passes: VivyPasses
	refinements: Optional[VivyRefinements]

@dataclass
class VivyOptions:
	source_mat: str
	material: VivyMaterial
	passes: Dict[str, str]
	fallback: Optional[Fallback]

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
	if isinstance(options.material.refinements, VivyRefinements):
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
			if options.fallback == Fallback.FALLBACK_S and ext.fallback_s is not None:
				options.material.base_material = ext.fallback_s
				options.material.passes.specular = None
			elif options.fallback == Fallback.FALLBACK_N and ext.fallback_n is not None:
				options.material.base_material = ext.fallback_n
				options.material.passes.normal = None
			elif options.fallback == Fallback.FALLBACK and ext.fallback is not None:
				options.material.base_material = ext.fallback
				options.material.passes.specular = None
				options.material.passes.normal = None

	import_name: Optional[str] = None
	if options.material.base_material in env.vivy_cache:
		import_name = options.material.base_material
	elif util.nameGeneralize(options.material.base_material) in env.vivy_cache:
		import_name = util.nameGeneralize(options.material.base_material)

	# If link is true, check library material not already linked.
	sync_file = get_vivy_blend()

	init_mats = list(bpy.data.materials)
	path = os.path.join(str(sync_file), "Material")

	if isinstance(import_name, str):
		util.bAppendLink(path, import_name, False)  # No linking.

	imported = set(list(bpy.data.materials)) - set(init_mats)
	if not imported:
		return f"Could not import {material.name}"
	selected_material = list(imported)[0]
	
	# Set the passes
	passes = [(options.material.passes.diffuse, "diffuse"), 
		   (options.material.passes.specular, "specular"), 
		   (options.material.passes.normal, "normal")]

	for p in passes:
		if p[0] is not None:
			new_material_nodes = selected_material.node_tree.nodes
			if not new_material_nodes.get(p[0]):
				return f"Material has no {p[1]} node"

			if not material.node_tree.nodes:
				return "Material has no nodes"

			nnodes = selected_material.node_tree.nodes
			material_nodes = material.node_tree.nodes

			if not material_nodes.get("Image Texture") and not material_nodes.get(options.material.passes.diffuse):
				return "Material has no Image Texture node"

			nnode_diffuse = nnodes.get(p[0])
			nnode_diffuse.image = options.passes[p[1]]

	material.user_remap(selected_material)

	m_name = material.name
	bpy.data.materials.remove(material)
	selected_material.name = m_name
	return None

def get_vivy_blend() -> Path:
	"""Return the path of the Vivy material library"""
	return Path(os.path.join(env.json_path.parent, "vivy_materials.blend"))

def get_vivy_json() -> Path:
	"""Return the path of the Vivy JSON file"""
	return Path(os.path.join(env.json_path.parent, "vivy_materials.json"))

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
		if "materials" in env.vivy_material_json:
			for m, d in env.vivy_material_json["materials"].items():
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

	md = env.vivy_material_json["materials"][self.materialName]
	row = self.layout.row()
	row.label(text=md["desc"])
	
	box = self.layout.box()
	box.label(text="Expects the following passes:")
	row = box.row()
	row.label(text="Diffuse", icon="MATERIAL")
	if "specular" in md["passes"]:
		row = box.row()
		row.label(text="Specular", icon="NODE_MATERIAL")
	if "normal" in md["passes"]:
		row = box.row()
		row.label(text="Normal", icon="ORIENTATION_NORMAL")
	
	if "refinements" in md:
		box = self.layout.box()
		box.label(text="Has refinements for the following:")
		if "emissive" in md["refinements"]:
			row = box.row()
			row.label(text="Emission", icon="OUTLINER_OB_LIGHT")
		if "reflective" in md["refinements"]:
			row = box.row()
			row.label(text="Glossy", icon="NODE_MATERIAL")
		if "metallic" in md["refinements"]:
			row = box.row()
			row.label(text="Metalic", icon="NODE_MATERIAL")
		if "glass" in md["refinements"]:
			row = box.row()
			row.label(text="Transmissive", icon="OUTLINER_OB_LIGHTPROBE")
		if "fallback_s" in md["refinements"]:
			row = box.row()
			row.label(text="Fallback for Missing Specular")
		if "fallback_n" in md["refinements"]:
			row = box.row()
			row.label(text="Fallback for Missing Normal")
		if "fallback" in md["refinements"]:
			row = box.row()
			row.label(text="Complete Fallback for No Extra Passes")

class VIVY_OT_materials(bpy.types.Operator, VivyMaterialProps):
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
				md = env.vivy_material_json["materials"][self.materialName]
				options = VivyOptions(
					source_mat=mat.name,
					material=VivyMaterial(
						base_material=md["base_material"],
						desc=md["desc"],
						passes=VivyPasses(
							diffuse=md["passes"]["diffuse"],
							specular=md["passes"]["specular"] if "specular" in md["passes"] else None,
							normal=md["passes"]["normal"] if "normal" in md["passes"] else None
						),
						refinements=None if "refinements" not in md else VivyRefinements(
							emissive=md["refinements"]["emissive"] if "emissive" in md["refinements"] else None,
							reflective=md["refinements"]["reflective"] if "reflecive" in md["refinements"] else None,
							metallic=md["refinements"]["metallic"] if "metallic" in md["refinements"] else None,
							glass=md["refinements"]["glass"] if "glass" in md["refinements"] else None,
							fallback_s=md["refinements"]["fallback_s"] if "fallback_s" in md["refinements"] else None,
							fallback_n=md["refinements"]["fallback_n"] if "fallback_n" in md["refinements"] else None,
							fallback=md["refinements"]["fallback"] if "fallback" in md["refinements"] else None
						)
					),
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
			obj["VIVY_MATERIAL_NAME"] = self.materialName

		addon_prefs = util.get_user_preferences(context)
		self.track_param = context.scene.render.engine
		self.track_exporter = addon_prefs.MCprep_exporter_type
		return {'FINISHED'}

class VIVY_OT_swap_texture_pack(
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
		
		mtype = None
		for obj in obj_list:
			if "VIVY_PREPPED" not in obj:
				self.report({'ERROR'}, "OBJ needs to be prepped first!")
				return {'CANCELLED'}
			
			material_types = {}
			if obj["VIVY_MATERIAL_NAME"] not in material_types:
				material_types[obj["VIVY_MATERIAL_NAME"]] = 0
			else:
				material_types[obj["VIVY_MATERIAL_NAME"]] += 1
			
			if len(material_types) > 1:
				self.report({'ERROR'}, "Multiple material types at once for texture swap not supported yet!")
				return {'CANCELED'}

			mtype = obj["VIVY_MATERIAL_NAME"]

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
			self.preprocess_material(mat)
			res += self.set_texture_pack(context, mat, folder, mtype)
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
	
	def set_texture_pack(self, context, material: Material, folder: Path, material_type: str) -> bool:
		"""Replace existing material's image with texture pack's.

		Run through and check for each if counterpart material exists, then
		run the swap (and auto load e.g. normals and specs if avail.)
		"""
		mc_name, _ = get_mc_canonical_name(material.name)
		image = generate.find_from_texturepack(mc_name, folder)
		if image is None:
			obj = bpy.context.view_layer.objects.active
			md = env.vivy_material_json["materials"][obj["VIVY_MATERIAL_NAME"]]
			options = VivyOptions(
				source_mat=material.name,
				material=VivyMaterial(
					base_material=md["base_material"],
					desc=md["desc"],
					passes=VivyPasses(
						diffuse=md["passes"]["diffuse"],
						specular=md["passes"]["specular"] if "specular" in md["passes"] else None,
						normal=md["passes"]["normal"] if "normal" in md["passes"] else None
					),
					refinements=None if "refinements" not in md else VivyRefinements(
						emissive=md["refinements"]["emissive"] if "emissive" in md["refinements"] else None,
						reflective=md["refinements"]["reflective"] if "reflecive" in md["refinements"] else None,
						metallic=md["refinements"]["metallic"] if "metallic" in md["refinements"] else None,
						glass=md["refinements"]["glass"] if "glass" in md["refinements"] else None,
						fallback_s=md["refinements"]["fallback_s"] if "fallback_s" in md["refinements"] else None,
						fallback_n=md["refinements"]["fallback_n"] if "fallback_n" in md["refinements"] else None,
						fallback=md["refinements"]["fallback"] if "fallback" in md["refinements"] else None
					)
				),
				passes=generate.get_textures(material),
				fallback=Fallback.FALLBACK
			)
			generate_vivy_materials(self, context, options)
			return False

		image_data = util.loadTexture(image)
		_ = self.set_cycles_texture(context, image_data, material, material_type, True)
		return True

	def set_cycles_texture(self, context, image: generate.Image, material: Material, type: str, extra_passes: bool=False) -> bool:
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
		
		p = env.vivy_material_json["materials"][type]["passes"]
		print(p)
		diffuse = p["diffuse"] if "diffuse" in p else None
		specular = p["specular"] if "specular" in p else None
		normal = p["normal"] if "normal" in p else None

		nodes = material.node_tree.nodes
		fallback = None
		passes = {}
		if diffuse is not None:
			d = nodes.get(diffuse)
			d.image = image
			passes["diffuse"] = image
		if specular is not None:
			s = nodes.get(specular)
			if "specular" in img_sets:
				new_img = util.loadTexture(img_sets["specular"])
				s.image = new_img
				util.apply_colorspace(s, 'Non-Color')
				passes["specular"] = new_img
			else:
				fallback = Fallback.FALLBACK_S
		if normal is not None:
			n = nodes.get(normal)
			if "normal" in img_sets:
				new_img = util.loadTexture(img_sets["normal"])
				n.image = new_img
				util.apply_colorspace(n, 'Non-Color')
				passes["normal"] = new_img 
			else:
				fallback = Fallback.FALLBACK_N
		
		# use fallback material if needed
		if fallback is not None:
			obj = bpy.context.view_layer.objects.active
			md = env.vivy_material_json["materials"][obj["VIVY_MATERIAL_NAME"]]
			options = VivyOptions(
				source_mat=material.name,
				material=VivyMaterial(
					base_material=md["base_material"],
					desc=md["desc"],
					passes=VivyPasses(
						diffuse=md["passes"]["diffuse"],
						specular=md["passes"]["specular"] if "specular" in md["passes"] else None,
						normal=md["passes"]["normal"] if "normal" in md["passes"] else None
					),
					refinements=None if "refinements" not in md else VivyRefinements(
						emissive=md["refinements"]["emissive"] if "emissive" in md["refinements"] else None,
						reflective=md["refinements"]["reflective"] if "reflecive" in md["refinements"] else None,
						metallic=md["refinements"]["metallic"] if "metallic" in md["refinements"] else None,
						glass=md["refinements"]["glass"] if "glass" in md["refinements"] else None,
						fallback_s=md["refinements"]["fallback_s"] if "fallback_s" in md["refinements"] else None,
						fallback_n=md["refinements"]["fallback_n"] if "fallback_n" in md["refinements"] else None,
						fallback=md["refinements"]["fallback"] if "fallback" in md["refinements"] else None
					)
				),
				passes=passes,
				fallback=fallback
			)
			generate_vivy_materials(self, context, options)
			set_material(context, material, options)
			

		changed = True
		nodes.active = nodes.get(diffuse)
		return changed

class VIVY_OT_material_export(bpy.types.Operator, VivyMaterialProps):
	"""
	Export operator for Vivy's material library
	"""
	bl_idname = "vivy.export_library"
	bl_label = "Export Vivy's Material Library"
	bl_options = {'REGISTER'}
	
	directory: bpy.props.StringProperty(
        name="Folder to Export To",
        description="",
        subtype='DIR_PATH'
        )

	filter_folder: bpy.props.BoolProperty(
        default=True,
        options={"HIDDEN"}
        )
	
	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}

	track_function = "vivy_material_export"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
		import zipfile
		from datetime import date
		zip_file_name = f"vivy_export-{date.today()}" + '.zip'
		zip_file_path = Path(self.directory) / Path(zip_file_name)
		with zipfile.ZipFile(zip_file_path, mode='w') as zf:
			blend_path, json_path = (get_vivy_blend(), get_vivy_json())
			if not blend_path.exists() or not json_path.exists():
				self.report({'ERROR'}, "Missing library files to export!")
				return {'CANCELLED'}
			zf.write(blend_path, arcname=blend_path.name)
			zf.write(json_path, arcname=json_path.name)
		return {'FINISHED'}

class VIVY_OT_material_import(bpy.types.Operator, ImportHelper):
	bl_label = "Import Vivy Library"
	bl_idname = "vivy.import_library"

	filter_glob: bpy.props.StringProperty(
		default='*.zip',
		options={'HIDDEN'}
	)
	
	track_function = "vivy_material_import"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
		import zipfile
		path = Path(self.filepath)
		with zipfile.ZipFile(path, mode="r") as zf:
			files = zf.namelist()
			if "vivy_materials.blend" not in files or "vivy_materials.json" not in files:
				self.report({'ERROR'}, "Zip archive is missing files!")
				return {'CANCELLED'}
			zf.extract("vivy_materials.blend", path=get_vivy_blend().parent)
			zf.extract("vivy_materials.json", path=get_vivy_json().parent)

		# Reload the JSON to get
		# updated information
		env.reload_vivy_json()
		return {'FINISHED'}

classes = [
	VIVY_OT_materials,
	VIVY_OT_swap_texture_pack,
	VIVY_OT_material_export,
	VIVY_OT_material_import
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
