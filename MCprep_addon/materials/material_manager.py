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
from collections import deque
import time

from typing import Dict, List, Optional, Set, Tuple, Union
from numpy.typing import NDArray

import numpy as np

from . import generate
from . import sequences
from .. import tracking
from .. import util

from ..conf import MCprepError, env

# 4096 * 4, used to cap the amount of
# pixels summed when not using the fast
# prefilter with the Combine Images operator
#
# 4096 is the amount of pixels capped to,
# and 4 is the RGBA channels
RGBA_PIXELS_4096_MAX = 16384

# --- CONFIG: PROPERTIES TO IGNORE ---
IGNORE_PROPS = (
	'bl_description', 'bl_width_default', 'bl_width_min', 'bl_width_max', 'bl_height_default', 'bl_height_min',
	'bl_height_max', 'bl_icon', 'bl_static_type', 'bl_label', 'name', 'label',
	'location', 'width', 'height', 'dimensions', 'hide', 'select',
	'show_options', 'show_texture', 'show_preview', 'use_custom_color',
	'color', 'parent', 'internal_links', 'texture_mapping', 'color_mapping', 'node_tree'
)

IGNORE_MAT_SETTINGS = (
	'name', 'use_fake_user', 'is_runtime_data', 'tag', 'asset_data',
	'preview_render_type', 'use_preview_world', 'use_nodes', 'node_tree',
	'diffuse_color', 'specular_color', 'roughness', 'specular_intensity',
	'metallic', 'line_color', 'animation_data'
)

# -----------------------------------------------------------------------------
# UI and utility functions
# -----------------------------------------------------------------------------


def reload_materials(context):
	"""Reload the material UI list"""
	mcprep_props = context.scene.mcprep_props
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	extensions = [".png", ".jpg", ".jpeg"]

	mcprep_props.material_list.clear()
	if env.use_icons and env.preview_collections["materials"]:
		try:
			bpy.utils.previews.remove(env.preview_collections["materials"])
		except:
			env.log("Failed to remove icon set, materials")

	if not os.path.isdir(resource_folder):
		env.log("Error, resource folder does not exist")
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
		os.path.join(resource_folder, "blocks"),
		os.path.join(resource_folder, "block")]
	files = []

	for path in search_paths:
		if not os.path.isdir(path):
			continue
		files += [
			os.path.join(path, image_file)
			for image_file in os.listdir(path)
			if os.path.isfile(os.path.join(path, image_file))
			and os.path.splitext(image_file.lower())[-1] in extensions]
	for i, image_file in enumerate(sorted(files)):
		basename = os.path.splitext(os.path.basename(image_file))[0]
		if basename.endswith("_s") or basename.endswith("_n"):
			continue  # ignore the pbr passes

		canon, _ = generate.get_mc_canonical_name(basename)
		asset = mcprep_props.material_list.add()
		asset.name = canon
		asset.description = f"Generate {canon} ({basename})"
		asset.path = image_file
		asset.index = i

		# if available, load the custom icon too
		if not env.use_icons or env.preview_collections["materials"] == "":
			continue
		env.preview_collections["materials"].load(
			f"material-{i}", image_file, 'IMAGE')

	if mcprep_props.material_list_index >= len(mcprep_props.material_list):
		mcprep_props.material_list_index = len(mcprep_props.material_list) - 1


class ListMaterials(bpy.types.PropertyGroup):
	"""For UI drawing of item assets and holding data"""
	# inherited: name
	description: bpy.props.StringProperty()
	path: bpy.props.StringProperty(subtype='FILE_PATH')
	index: bpy.props.IntProperty(min=0, default=0)  # for icon drawing


# -----------------------------------------------------------------------------
# Dataclasses for material comparison 
# -----------------------------------------------------------------------------

Primitive = Union[int, float, str, bool, list, None]

@dataclass
class KeyframeData:
	co: Tuple[float, float]
	handles: Tuple[float, float, float, float] # left_x, left_y, right_x, right_y
	types: Tuple[str, str, str, str]		   # handle_l, handle_r, interp, easing
	dynamics: Tuple[float, float, float]	   # back, amplitude, period

@dataclass
class FCurveData:
	array_index: int
	extrapolation: str
	auto_smoothing: bool
	mute: bool
	keyframes: List[KeyframeData]

@dataclass
class DriverVariableTarget:
	id_name: str
	data_path: str = ""
	bone_target: str = ""
	id_type: str = ""
	transform_type: str = ""
	transform_space: str = ""
	rotation_mode: str = ""
	context_property: str = ""

@dataclass
class DriverVariableData:
	name: str
	var_type: str
	targets: List[DriverVariableTarget]

@dataclass
class DriverModifierData:
	mod_type: str
	settings: Dict[str, Primitive]

@dataclass
class DriverFingerprint:
	drv_type: str
	expression: Optional[str]
	variables: List[DriverVariableData]
	fcurve: FCurveData
	modifiers: List[DriverModifierData]

@dataclass
class PropertyEntry:
	val: Primitive
	driver: Optional[DriverFingerprint] = None
	animation: Optional[List[FCurveData]] = None

class NodeLinkData:
	from_socket: str
	from_node: str
	to_socket: str
	to_node: str

@dataclass
class NodeFingerprint:
	node_type: str
	muted: bool
	properties: Dict[str, PropertyEntry]
	inputs: List[PropertyEntry]
	group_content: Optional['NodeTreeFingerprint'] = None

@dataclass
class NodeTreeFingerprint:
	nodes: List[NodeFingerprint]
	links: List[NodeLinkData]

@dataclass
class MaterialFingerprint:
	mat_type: str = ""
	diffuse: Optional[List[float]] = None
	roughness: Optional[float] = None
	metallic: Optional[float] = None
	node_tree_data: Optional[NodeTreeFingerprint] = None
	mat_action_name: str = 'None'
	node_tree_action_name: str = 'None'
	animation: Optional[Dict[str, List[FCurveData]]] = None
	render_settings: Optional[Dict[str, PropertyEntry]] = None
	line_art_settings: Optional[Dict[str, PropertyEntry]] = None


# -----------------------------------------------------------------------------
# Material structural comparison helpers
# -----------------------------------------------------------------------------

# --- SERIALIZATION HELPERS ---

def serialize_fcurve(precision: int, fcurve: bpy.types.FCurve) -> FCurveData:
	"""
	Converts an F-Curve data-block into a dictionary of primitive values for structural comparison.
	"""
	fcurve.keyframe_points.sort()

	return FCurveData(
		array_index=fcurve.array_index,
		extrapolation=fcurve.extrapolation,
		auto_smoothing=fcurve.auto_smoothing,
		mute=fcurve.mute,
		keyframes=[serialize_keyframe(precision, kp) for kp in fcurve.keyframe_points]
	)

def serialize_keyframe(precision: int, kp: bpy.types.Keyframe) -> KeyframeData:
	"""
	Serializes individual keyframe points, rounding float values to ensure consistent hashing.
	"""
	return KeyframeData(
		co=(round(kp.co[0], precision), round(kp.co[1], precision)),
		handles=(
			round(kp.handle_left[0], precision), round(kp.handle_left[1], precision),
			round(kp.handle_right[0], precision), round(kp.handle_right[1], precision)
		),
		types=(kp.handle_left_type, kp.handle_right_type, kp.interpolation, kp.easing),
		dynamics=(round(kp.back, precision), round(kp.amplitude, precision), round(kp.period, precision))
	)

# --- ANIMATION & DRIVER LOGIC ---
def get_animation_fingerprint(precision: int, id_data: bpy.types.ID, data_path: Optional[str] = None, array_index: Optional[int] = -1) -> Optional[List[FCurveData]]:
	"""
	Retrieves the animation data for a specific property or data-block as a serializable fingerprint.
	"""
	if not id_data.animation_data or not id_data.animation_data.action:
		return None

	action = id_data.animation_data.action
	fcurve = None
	
	if data_path:
		found = action.fcurves.find(data_path, index=array_index)
		fcurve = [found] if found else None 
	else:
		fcurve = sorted(action.fcurves, key=lambda f: (f.data_path, f.array_index))

	if not fcurve:
		return None
	return [serialize_fcurve(precision, f) for f in fcurve]

def get_driver_fingerprint(precision: int, id_data: bpy.types.ID, data_path: str, array_index: Optional[int] = -1) -> Optional[DriverFingerprint]:
	"""
	Captures driver expressions, variables, and modifier stacks into a serializable structure.
	"""
	if not id_data.animation_data or not id_data.animation_data.drivers:
		return None
		
	fcurve = id_data.animation_data.drivers.find(data_path, index=array_index)
	
	if fcurve is None:
		return None

	drv = fcurve.driver

	variables: List[DriverVariableData] = []
	for var in drv.variables:
		targets: List[DriverVariableTarget] = []
		
		for tar in var.targets:
			# 1. Basic Driver Settings
			tar_info: Dict[str, str] = {"id_name": getattr(tar.id, "name_full", tar.id.name) if tar.id else ""}

			# 2. Variable Logic (Only properties that affect driver result)
			if tar.bone_target:
				tar_info["bone_target"] = tar.bone_target

			if var.type == 'CONTEXT_PROP':
				tar_info["context_property"] = tar.context_property
				tar_info["data_path"] = tar.data_path

			elif var.type == 'SINGLE_PROP':
				tar_info["id_type"] = tar.id_type
				tar_info["data_path"] = tar.data_path

			elif var.type == 'TRANSFORMS':
				tar_info["transform_type"] = tar.transform_type
				tar_info["transform_space"] = tar.transform_space
				if tar.transform_type.startswith("ROT"):
					tar_info["rotation_mode"] = tar.rotation_mode

			elif var.type == 'LOC_DIFF':
				tar_info["transform_space"] = tar.transform_space

			targets.append(DriverVariableTarget(**tar_info))
		variables.append(DriverVariableData(name=var.name, var_type=var.type, targets=targets))

	# 3. F-Curve
	driver_fcurve = serialize_fcurve(precision, fcurve)
	
	# 4. F-Curve Modifiers (Skip if muted or influence is 0)
	modifiers: List[DriverModifierData] = []
	for mod in fcurve.modifiers:
		if mod.mute or getattr(mod, "influence", 1.0) <= 0.0:
			continue

		m_data: Dict[str, Primitive] = {}
		for prop in mod.bl_rna.properties:
			if not prop.is_readonly and prop.identifier not in {'name', 'type', 'is_active'}:
				m_data[prop.identifier] = to_primitive(getattr(mod, prop.identifier), precision)
		
		modifiers.append(DriverModifierData(mod_type=mod.type, settings=m_data))

	return DriverFingerprint(
		drv_type=drv.type,
		expression=drv.expression if drv.type == 'SCRIPTED' else None,
		variables=variables,
		fcurve=driver_fcurve,
		modifiers=modifiers
	)

# --- NODE TREE ANALYSIS ---

def get_material_fingerprint(material: bpy.types.Material, exclude_settings: bool, use_action_names: bool,	precision: int) -> MaterialFingerprint:
	"""
	Generates a unique signature of a material's node tree and render settings to identify duplicates.
	"""
	mat_type = "FIXED_MAT"
	diffuse = None
	roughness = None
	metallic = None
	node_tree_data = None
	mat_action_name = 'None'
	node_tree_action_name = 'None'
	anim = None
	render_settings = None
	line_art_settings = None

	if not material.node_tree:
		mat_type = "FIXED_MAT"
		diffuse = to_primitive(material.diffuse_color, precision)
		roughness = to_primitive(material.roughness, precision)
		metallic = to_primitive(material.metallic, precision)
	else:
		mat_type = "NODE_TREE"
		node_tree_data = get_node_group_fingerprint(material.node_tree, precision)

	# Gather Animation
	if use_action_names:
		# Material level action
		mat_action_name = material.animation_data.action.name if (material.animation_data and material.animation_data.action) else 'None'

		# Node Tree level action
		if material.node_tree and material.node_tree.animation_data and material.node_tree.animation_data.action:
			node_tree_action_name = material.node_tree.animation_data.action.name
		else:
			node_tree_action_name = 'None'

	anim = get_animation_fingerprint(precision, material)

	# Gather Material / Render Settings
	if not exclude_settings:
		render_settings = {}
		for prop in material.bl_rna.properties:
			if prop.is_readonly or prop.identifier in IGNORE_MAT_SETTINGS:
				continue

			val_data = PropertyEntry(val=to_primitive(getattr(material, prop.identifier), precision))

			# Check for driver
			driver = get_driver_fingerprint(precision, material, prop.identifier)
			if driver is not None:
				val_data.driver = driver

			render_settings[prop.identifier] = val_data

		# Gather Line Art Settings
		line_art_settings = {}
		if hasattr(material, "lineart"):
			la = material.lineart
			for prop in la.bl_rna.properties:
				if prop.is_readonly or prop.identifier in IGNORE_MAT_SETTINGS:
					continue

				value = getattr(la, prop.identifier)
				if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
					value = [to_primitive(v, precision) for v in value]
				else:
					value = to_primitive(value, precision)

				val_data = PropertyEntry(val=value)

				# Check for driver
				driver = get_driver_fingerprint(precision, material, f"line_art.{prop.identifier}")
				if driver is not None:
					val_data.driver = driver

				line_art_settings[prop.identifier] = val_data

	return MaterialFingerprint(
		mat_type=mat_type,
		diffuse=diffuse,
		roughness=roughness,
		metallic=metallic,
		node_tree_data=node_tree_data,
		mat_action_name=mat_action_name,
		node_tree_action_name=node_tree_action_name,
		animation=anim,
		render_settings=render_settings,
		line_art_settings=line_art_settings
	)

def get_node_group_fingerprint(node_tree: bpy.types.NodeTree, precision: int) -> Optional[NodeTreeFingerprint]:
	"""
	Recursively maps the connected node network, properties, and internal group contents.
	"""
	if not node_tree: return None
	active_nodes = get_connected_nodes(node_tree)
	nodes_data = []

	for node in sorted(list(active_nodes), key=lambda n: (n.bl_idname, n.name)):
		if node.bl_idname in {'NodeFrame', 'NodeReroute'}: continue

		node_data = {"type": node.bl_idname, "muted": node.mute, "properties": {}, "inputs": []}

		# Properties + Drivers + Anim
		for prop in node.bl_rna.properties:
			if prop.identifier in IGNORE_PROPS or prop.is_readonly: continue
			data_path = f'nodes["{node.name}"].{prop.identifier}'

			prop_entry = {"val": to_primitive(getattr(node, prop.identifier), precision)}

			# Check Driver & Anim
			driver = get_driver_fingerprint(precision, node_tree, data_path)
			anim = get_animation_fingerprint(precision, node_tree, data_path)
			if driver: prop_entry["driver"] = driver
			if anim: prop_entry["animation"] = anim

			node_data["properties"][prop.identifier] = prop_entry

		# Inputs
		for socket_idx, socket in enumerate(node.inputs):
			if socket.is_linked or not hasattr(socket, "default_value"):
				continue

			default_val = socket.default_value
			data_path = f'nodes["{node.name}"].inputs[{socket_idx}].default_value'

			# Scalar
			if isinstance(default_val, (int, float)):
				input_data = {"idx": socket_idx, "val": to_primitive(default_val, precision)}

				# Check Driver & Anim
				driver = get_driver_fingerprint(precision, node_tree, data_path)
				anim = get_animation_fingerprint(precision, node_tree, data_path)
				if driver: input_data["driver"] = driver
				if anim: input_data["animation"] = anim

				node_data["inputs"].append(input_data)

			# Array (RGBA / Vector)
			else:
				for array_idx, value in enumerate(default_val):

					input_data = {
						"idx": socket_idx,
						"array_index": array_idx,
						"val": value if isinstance(value, str) else round(value, 6)}

					# Check Driver & Anim
					driver = get_driver_fingerprint(precision, node_tree, data_path, array_idx)
					anim = get_animation_fingerprint(precision, node_tree, data_path, array_idx)
					if driver: input_data["driver"] = driver
					if anim: input_data["animation"] = anim

					node_data["inputs"].append(input_data)


		if node.bl_idname in ('ShaderNodeGroup', 'GeometryNodeGroup') and node.node_tree: # 'GeometryNodeGroup' included for future merge geoNode operator
			node_data["group_content"] = get_node_group_fingerprint(node.node_tree, precision)
		nodes_data.append(node_data)

	links_data = []
	for node in active_nodes:
		if node.bl_idname in {'NodeFrame', 'NodeReroute'}: continue
		for socket in node.inputs:
			if socket.is_linked:
				src = trace_socket(socket)
				if src.node in active_nodes:
					links_data.append({"from_socket": src.name, "from_node": src.node.bl_idname, "to_socket": socket.name, "to_node": node.bl_idname})

	return NodeTreeFingerprint(
		nodes=nodes_data,
		links=sorted(links_data, key=lambda x: str(x)))

def count_total_nodes(material: bpy.types.Material) -> int:
	"""
	Performs a recursive count of all functional nodes within a material and its nested node groups.
	"""
	if not material.node_tree:
		return 0

	def _recursive_count(node_tree):
		count = 0
		for node in node_tree.nodes:
			if node.bl_idname in {'NodeFrame', 'NodeReroute'}:
				continue
			count += 1
			# If it's a group, count its internal nodes too
			if node.bl_idname in ('ShaderNodeGroup', 'GeometryNodeGroup') and node.node_tree:
				count += _recursive_count(node.node_tree)
		return count

	return _recursive_count(material.node_tree)

def to_primitive(val, decimals: int = 4) -> Primitive:
	"""
	Converts Blender-specific data types into standard Python primitives for serialization.
	"""
	if isinstance(val, (int, float)):
		return round(val, decimals)
	elif isinstance(val, (str, bool, type(None))):
		return val
	elif hasattr(val, "to_list"):
		return [round(x, decimals) for x in val.to_list()]
	elif hasattr(val, "__iter__"):
		return [to_primitive(x, decimals) for x in val]
	return str(val)

def trace_socket(socket: bpy.types.NodeSocket) -> bpy.types.NodeSocket:
	"""
	Follows a node socket link back to its source, traversing reroute nodes.
	"""
	if not socket or not socket.is_linked:
		return socket
	current_link = socket.links[0]
	source_node = current_link.from_node
	while source_node and source_node.bl_idname == 'NodeReroute':
		if source_node.inputs[0].is_linked:
			current_link = source_node.inputs[0].links[0]
			source_node = current_link.from_node
		else:
			return source_node.inputs[0]
	return current_link.from_socket

def get_connected_nodes(node_tree: bpy.types.NodeTree) -> Set[bpy.types.Node]:
	"""
	Identifies all nodes that are functionally connected to a material or group output.
	"""
	if not node_tree:
		return set()
	outputNodes = [n for n in node_tree.nodes if n.bl_idname in ('ShaderNodeOutputMaterial', 'NodeGroupOutput')]
	connected = set()
	queue = deque(outputNodes)
	while queue:
		node = queue.popleft()
		if node in connected: continue
		connected.add(node)
		for input_socket in node.inputs:
			for link in input_socket.links:
				from_node = link.from_node
				if from_node not in connected:
					queue.append(from_node)
	return connected

# -----------------------------------------------------------------------------
# Material data management operators
# -----------------------------------------------------------------------------


class MCPREP_OT_reset_texturepack_path(bpy.types.Operator):
	bl_idname = "mcprep.reset_texture_path"
	bl_label = "Reset texture pack path"
	bl_description = (
		"Resets the texture pack folder to the MCprep default saved in preferences")
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_texturepack_path = addon_prefs.custom_texturepack_path
		return {'FINISHED'}


class MCPREP_OT_reload_materials(bpy.types.Operator):
	bl_idname = "mcprep.reload_materials"
	bl_label = "Reload materials"
	bl_description = "Reload the material library"

	@tracking.report_error
	def execute(self, context):
		reload_materials(context)
		return {'FINISHED'}


class MCPREP_OT_combine_materials(bpy.types.Operator):
	bl_idname = "mcprep.combine_materials"
	bl_label = "Combine materials"
	bl_description = "Consolidate duplicate materials based on nodes or name"
	bl_options = {'REGISTER', 'UNDO'}

	group_by_name: bpy.props.BoolProperty(
		name="Group Method: Material Name",
		description="Finds materials with the same name (ignoring extensions like .001)",
		default=False)

	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description="Build materials to consolidate based on selected objects only",
		default=False)

	exclude_mat_settings: bpy.props.BoolProperty(
		name="Exclude Material Settings",
		description="Do not compare materials settings, only nodes",
		default=False)

	use_action_names: bpy.props.BoolProperty(
		name="Differentiate by Action Name",
		description="If true, materials with identical animation but different Action names will be kept separate",
		default=False)

	precision: bpy.props.IntProperty(
		name="Matching Precision",
		description="Number of decimal places to round values to when comparing. Higher = stricter",
		min=0, max=6,
		default=4)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	track_function = "combine_materials"
	@tracking.report_error
	def execute(self, context):
		if self.selection_only and not context.selected_objects:
			self.report({'ERROR'}, "Select objects with materials first")
			return {'CANCELLED'}

		# 1. Gather materials
		if self.selection_only:
			materials_to_check = set()
			for obj in context.selected_objects:
				if hasattr(obj.data, "materials"):
					for mat in obj.data.materials:
						if mat and not mat.library and not mat.is_library_indirect:
							materials_to_check.add(mat)
			materials_to_check = list(materials_to_check)
		else:
			materials_to_check = [m for m in bpy.data.materials if not m.library and not m.is_library_indirect]

		if not materials_to_check:
			self.report({'INFO'}, "No materials found to process")
			return {'FINISHED'}

		precount = len(bpy.data.materials)

		# 2. Grouping by Fingerprint
		# Structure: { group_key: [ {fingerprint: dict, materials: [mat1, mat2]} ] }
		fingerprint_groups = {}

		for mat in materials_to_check:
			group_key = util.nameGeneralize(mat.name) if self.group_by_name else "GLOBAL"
			fp = get_material_fingerprint(mat, self.exclude_mat_settings, self.use_action_names, self.precision)

			if group_key not in fingerprint_groups:
				fingerprint_groups[group_key] = []

			# Check if fingerprint exists in the current group
			match_found = False
			for entry in fingerprint_groups[group_key]:
				if entry['fingerprint'] == fp:
					entry['materials'].append(mat)
					match_found = True
					break

			if not match_found:
				fingerprint_groups[group_key].append({'fingerprint': fp, 'materials': [mat]})

		# 3. Determine Masters and Build Merge Map
		merge_map = {}
		for group_key, entries in fingerprint_groups.items():
			for entry in entries:
				mats = entry['materials']
				if len(mats) <= 1:
					continue

				# Sort materials by total node count (add option for user to decide, least or greatest node count. What about number of users?), then by name length as a tie-breaker
				mats.sort(key=lambda m: (count_total_nodes(m), len(m.name)))

				master_mat = mats[0] # The one with the least nodes
				for i in range(1, len(mats)):
					merge_map[mats[i]] = master_mat

		# 4. Remap & Cleanup
		if not merge_map:
			self.report({'INFO'}, "No duplicates found")
			return {'FINISHED'}

		renamed_masters = set()
		for old_mat, master_mat in merge_map.items():
			if master_mat not in renamed_masters:
				new_name = util.nameGeneralize(master_mat.name)
				if new_name != master_mat.name and new_name not in bpy.data.materials:
					master_mat.name = new_name
				renamed_masters.add(master_mat)
			env.log(f"Replaced '{old_mat.name}' with '{master_mat.name}'")
			old_mat.user_remap(master_mat)

		to_delete = [m for m in merge_map.keys() if m.users == 0 and not m.use_fake_user]
		if to_delete:
			bpy.data.batch_remove(ids=to_delete)

		postcount = len(bpy.data.materials)
		consolidated_count = precount - postcount

		if consolidated_count > 0:
			self.report({"INFO"}, f"Consolidated {consolidated_count} material{'s' if consolidated_count > 1 else ''} (Total: {precount} -> {postcount})")
		else:
			self.report({"INFO"}, "No duplicates found")
		return {'FINISHED'}



class MCPREP_OT_combine_images(bpy.types.Operator):
	bl_idname = "mcprep.combine_images"
	bl_label = "Combine images"
	bl_description = "Find and merge duplicate images, remapping users to a single image"
	bl_options = {'REGISTER', 'UNDO'}

	group_by_name: bpy.props.BoolProperty(
		name="Group by Name",
		description="Compare duplicates using base names (e.g., 'Texture.001' matches 'Texture')",
		default=True)

	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description="Only check images used by materials on selected objects",
		default=False)

	strict_comparison: bpy.props.BoolProperty(
		name="Strict Comparison",
		description="Compare full image content instead of samples. More accurate, but slower for large images",
		default=False)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	track_function = "combine_images"
	@tracking.report_error
	def execute(self, context):
		# Setup image list
		if self.selection_only:
			if not context.selected_objects:
				self.report({'ERROR'}, "No objects selected")
				return {'CANCELLED'}

			target_images = set()
			processed_materials = set()

			for obj in context.selected_objects:
				if not hasattr(obj.data, "materials"):
					continue

				for mat in obj.data.materials:
					if not mat or mat in processed_materials:
						continue

					processed_materials.add(mat)
					if mat.use_nodes and mat.node_tree:
						for node in mat.node_tree.nodes:
							if node.type != 'TEX_IMAGE' or not node.image:
								continue
							target_images.add(node.image)

			if not target_images:
				self.report({'INFO'}, "No images found in selection")
				return {'FINISHED'}

			images_to_check = list(target_images)
		else:
			images_to_check = list(bpy.data.images)

		precount = len(bpy.data.images)

		# Group images
		#
		# Here we use a list, since we're just trying to get the
		# raw images at this point for comparison
		groups: List[Tuple[str, int, int, bpy.types.Image]] = []
		for img in images_to_check:
			if img.type in ('RENDER_RESULT', 'COMPOSITING') or img.use_fake_user:
				continue
			w, h = img.size
			# No data or empty image, nothing to compare, skip
			if w == 0 or h == 0 or not img.has_data:
				continue

			base_name = util.nameGeneralize(img.name) if self.group_by_name else "GLOBAL"
			groups.append((base_name, w, h, img))

		# Comparison and Remapping
		# Key: (base_name, w, h)
		# Value: List of (image_obj, comparison_array, sum)
		# store both the image (for remapping later on), the pixel array,
		# and pixel array sum for super fast prefilter
		unique_images: Dict[Tuple[str, int, int], List[Tuple[bpy.types.Image, NDArray[np.float32], Optional[np.float64]]]] = {}
		images_to_remove = []

		for base_name, w, h, img in groups:
			cur_img_key = (base_name, w, h)

			img_array = np.asarray(img.pixels)
			pix_sum: Optional[np.float64] = None

			# Approximation of a image content check used
			# if strict comparison is disabled. Unlike strict
			# comparison, which checks the actual pixels, this
			# sums up the pixels and uses that to represent the
			# image contents
			if not self.strict_comparison:
				num_pixels = w * h * 4
				stride = max(1, num_pixels // RGBA_PIXELS_4096_MAX)
				cur_img_data = img_array[::stride] if stride > 1 else img_array

				pix_sum = np.sum(cur_img_data)
	
			if cur_img_key not in unique_images:
				unique_images[cur_img_key] = [(img, img_array, pix_sum)]
				continue

			image_present = False
			present_image: Optional[bpy.types.Image] = None

			# Look through existing items in this Name/Size group
			for uni_image, uni_data, uni_sum in unique_images[cur_img_key]:
				# Fast prefilter, used as an alternative
				# to strict comparison
				if not self.strict_comparison and not pix_sum == uni_sum:
					continue
				elif not np.array_equal(uni_data, img_array):
					continue
				image_present = True
				present_image = uni_image
				break


			# If the image is present already, mark it
			# for removal, remap, and continue to the next image
			if image_present:
				images_to_remove.append(img)
				img.user_remap(present_image)
				continue

			# If the image is not present, add it to the list
			unique_images[cur_img_key].append((img, img_array, pix_sum))

		# Cleanup
		to_delete = [
			img for img in images_to_remove
			if img.users == 0 and not img.use_fake_user and not img.is_library_indirect]

		if to_delete:
			for img in to_delete:
				img.gl_free()
				img.buffers_free()
			bpy.data.batch_remove(ids=to_delete)

		# Report
		postcount = len(bpy.data.images)
		consolidated_count = precount - postcount

		if consolidated_count > 0:
			self.report({"INFO"}, f"Consolidated {consolidated_count} duplicate image{'s' if consolidated_count != 1 else ''} (Total: {precount} -> {postcount})")
		else:
			self.report({"INFO"}, "No duplicates found")
		return {'FINISHED'}


class MCPREP_OT_replace_missing_textures(bpy.types.Operator):
	"""Replace missing textures with matching images in the active texture pack"""
	bl_idname = "mcprep.replace_missing_textures"
	bl_label = "Find missing textures"
	bl_options = {'REGISTER', 'UNDO'}

	# deleteAlpha = False
	animateTextures: bpy.props.BoolProperty(
		name="Animate textures (may be slow first time)",
		description="Convert tiled images into image sequence for material.",
		default=True)
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "replace_missing"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):

		# get list of selected objects
		obj_list = context.selected_objects
		if len(obj_list) == 0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if len(obj_list) == 0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		count = 0
		for mat in mat_list:
			updated = False
			passes = generate.get_textures(mat)
			if not passes:
				env.log("No images found within material")
			for pass_name in passes:
				if pass_name == 'diffuse' and passes[pass_name] is None:
					res = self.load_from_texturepack(mat)
				else:
					res = generate.replace_missing_texture(passes[pass_name])
				if res == 1:
					updated = True
			if updated:
				count += 1
				env.log(f"Updated {mat.name}")
				if self.animateTextures:
					sequences.animate_single_material(
						mat,
						context.scene.render.engine,
						export_location=sequences.ExportLocation.ORIGINAL)
		if count == 0:
			self.report(
				{'INFO'},
				f"No missing image blocks detected in {len(mat_list)} materials")

		self.report({'INFO'}, f"Updated {count} materials")
		self.track_param = context.scene.render.engine

		# NOTE: This is temporary
		addon_prefs = util.get_user_preferences(context)
		self.track_exporter = addon_prefs.MCprep_exporter_type
		return {'FINISHED'}

	def load_from_texturepack(self, mat):
		"""If image datablock not found in passes, try to directly load and assign"""
		env.log(f"Loading from texpack for {mat.name}", vv_only=True)
		canon, _ = generate.get_mc_canonical_name(mat.name)
		image_path = generate.find_from_texturepack(canon)
		if isinstance(image_path, MCprepError):
			if image_path.msg:
				env.log(image_path.msg)
			else:
				env.log(f"Find missing images: No source file found for {mat.name}")
			return False

		# even if images of same name already exist, load new block
		env.log(f"Find missing images: Creating new image datablock for {mat.name}")
		# do not use 'check_existing=False' to keep compatibility pre 2.79
		image = bpy.data.images.load(str(image_path), check_existing=True)

		engine = bpy.context.scene.render.engine
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE' or engine == 'BLENDER_EEVEE_NEXT':
			status = generate.set_cycles_texture(image, mat)
		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			status = generate.set_cycles_texture(image, mat)

		return status  # True or False


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	ListMaterials,
	MCPREP_OT_reset_texturepack_path,
	MCPREP_OT_reload_materials,
	MCPREP_OT_combine_materials,
	MCPREP_OT_combine_images,
	MCPREP_OT_replace_missing_textures
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
