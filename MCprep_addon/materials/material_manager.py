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

from typing import Dict, List, Optional, Set, Tuple, Union, Iterable
from numpy.typing import NDArray

from dataclasses import dataclass

import numpy as np
from enum import Enum

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
	index: bpy.props.IntProperty(min=0, default=0)	# for icon drawing


# -----------------------------------------------------------------------------
# Dataclasses for material comparison 
# -----------------------------------------------------------------------------

Primitive = Union[int, float, str, bool, Tuple['Primitive', ...], None]

class AnimState(Enum):
	"""Represents the presence or absence of animation data."""
	NONE = 'None'
	ACTIVE = 'Active'

@dataclass
class KeyframeData:
	"""Stores keyframe coordinate, handle, and dynamic data."""
	co: Tuple[float, float]
	handles: Tuple[float, float, float, float] # left_x, left_y, right_x, right_y
	types: Tuple[str, str, str, str]		   # handle_l, handle_r, interp, easing
	dynamics: Tuple[float, float, float]	   # back, amplitude, period

@dataclass
class FCurveData:
	"""Stores F-Curve settings and list of keyframes."""
	data_path: str
	array_index: int
	extrapolation: str
	auto_smoothing: str
	mute: bool
	keyframes: List[KeyframeData]

@dataclass
class DriverVariableTarget:
	"""Stores driver variable target data."""
	id_name: str
	data_path: Optional[str] = None
	bone_target: Optional[str] = None
	id_type: Optional[str] = None
	transform_type: Optional[str] = None
	transform_space: Optional[str] = None
	rotation_mode: Optional[str] = None
	context_property: Optional[str] = None

@dataclass
class DriverVariableData:
	"""Stores driver variable name, type, and targets."""
	name: str
	var_type: str
	targets: List[DriverVariableTarget]

@dataclass
class DriverModifierData:
	"""Stores driver modifier type and settings."""
	mod_type: str
	settings: Dict[str, Primitive]

@dataclass
class DriverFingerprint:
	"""Stores full driver data including variables, F-curves, and modifiers."""
	drv_type: str
	expression: Optional[str]
	variables: List[DriverVariableData]
	fcurve: Optional[FCurveData]
	modifiers: List[DriverModifierData]

@dataclass
class PropertyEntry:
	"""Stores a property value along with potential driver or animation data."""
	val: Primitive
	driver: Optional[DriverFingerprint] = None
	animation: Optional[List[FCurveData]] = None

@dataclass
class NodeLinkData:
	"""Stores connection details between two node sockets."""
	from_socket: str
	from_node: str
	to_socket: str
	to_node: str

@dataclass
class NodeFingerprint:
	"""Stores node type, mute status, and input/property data."""
	node_type: str
	muted: bool
	properties: Dict[str, PropertyEntry]
	inputs: List[PropertyEntry]
	group_content: Optional['NodeTreeFingerprint'] = None

@dataclass
class NodeTreeFingerprint:
	"""Stores the list of nodes and links within a node tree."""
	nodes: List[NodeFingerprint]
	links: List[NodeLinkData]

@dataclass
class MaterialFingerprint:
	"""Stores a unique signature of a material for structural comparison."""
	mat_type: str = "FIXED_MAT"
	diffuse: Optional[Primitive] = None
	roughness: Optional[Primitive] = None
	metallic: Optional[Primitive] = None
	node_tree_data: Optional[NodeTreeFingerprint] = None
	mat_action_name: Optional[Union[str, AnimState]] = AnimState.NONE
	node_tree_action_name: Optional[Union[str, AnimState]] = AnimState.NONE
	animation: Optional[Dict[str, List[FCurveData]]] = None
	render_settings: Optional[Dict[str, PropertyEntry]] = None
	line_art_settings: Optional[Dict[str, PropertyEntry]] = None


# -----------------------------------------------------------------------------
# Material structural comparison helpers
# -----------------------------------------------------------------------------

# --- SERIALIZATION HELPERS ---

def serialize_fcurve(precision: int, fcurve: bpy.types.FCurve) -> Optional[FCurveData]:
	"""
	Converts a Blender F-Curve into a dataclass.
	Returns None if the curve has 1 or fewer keyframes, as this doesn't 
	constitute a functional animation for comparison purposes.
	"""
	# If there's only one keyframe, it's a static value, not an animation.
	# We ignore it to keep the fingerprint focused on actual movement.
	if len(fcurve.keyframe_points) <= 1:
		return

	fcurve.keyframe_points.sort()

	return FCurveData(
		data_path=fcurve.data_path,
		array_index=fcurve.array_index,
		extrapolation=fcurve.extrapolation,
		auto_smoothing=fcurve.auto_smoothing,
		mute=fcurve.mute,
		keyframes=[serialize_keyframe(precision, kp) for kp in fcurve.keyframe_points]
	)

def serialize_keyframe(precision: int, kp: bpy.types.Keyframe) -> KeyframeData:
	"""
	Extracts essential keyframe data: coordinates, handle positions,
	interpolation types, and dynamic easing properties (Back/Bounce/Elastic).
	"""
	return KeyframeData(
		co=round_value(kp.co, precision),
		handles=(*round_value(kp.handle_left, precision), *round_value(kp.handle_right, precision)),
		types=(kp.handle_left_type, kp.handle_right_type, kp.interpolation, kp.easing),
		dynamics=round_value((kp.back, kp.amplitude, kp.period), precision)
	)

# --- ANIMATION & DRIVER LOGIC ---

def get_animation_fingerprint(precision: int, id_data: bpy.types.ID, data_path: Optional[str] = None, array_index: int = -1) -> Optional[List[FCurveData]]:
	"""
	Retrieves the animation data for a specific property or data-block as a serializable fingerprint.
	"""	
	if not id_data.animation_data or not id_data.animation_data.action:
		return None

	action = id_data.animation_data.action
	fcurves_to_serialize = []
	
	# Gather relevant curves:
	if data_path:
		found = action.fcurves.find(data_path, index=array_index)
		if found:
			fcurves_to_serialize = [found]
	else:
		fcurves_to_serialize = sorted(
			[f for f in action.fcurves if f.is_valid], 
			key=lambda f: (f.data_path, f.array_index)
		)

	# Serialize and Filter
	results: List[FCurveData] = []
	
	for fcurve in fcurves_to_serialize:
		serialized = serialize_fcurve(precision, fcurve)
		if serialized is not None:
			results.append(serialized)

	# Return None if no valid (multi-keyframe) curves were found
	return results if results else None

def get_driver_fingerprint(precision: int, id_data: bpy.types.ID, data_path: str, array_index: int = -1) -> Optional[DriverFingerprint]:
	"""Captures drivers math (expression), inputs (variables), and modifiers."""

	if not id_data.animation_data or not id_data.animation_data.drivers:
		return None

	# Locate the specific driver F-Curve for the given property path
	fcurve = id_data.animation_data.drivers.find(data_path, index=array_index)
	if not fcurve:
		return None

	drv = fcurve.driver
	variables: List[DriverVariableData] = []

	# Process Variables
	for var in drv.variables:
		targets: List[DriverVariableTarget] = []
		var_type = var.type

		for tar in var.targets:
			# Every target needs an ID
			tar_obj = DriverVariableTarget(
				id_name=getattr(tar.id, "name_full", tar.id.name) if tar.id else ""
			)

			# - Contextual Logic: Only capture attributes relevant to the variable type.
			# This prevents "noise" / irrelevant unused attributes in the driver results
			
			# - Property based variables (getting a value from a UI field)
			if var_type in ('SINGLE_PROP', 'CONTEXT_PROP'):
				tar_obj.data_path = tar.data_path
				if var_type == 'SINGLE_PROP':
					tar_obj.id_type = tar.id_type
				else:
					tar_obj.context_property = tar.context_property
			
			# - Transform based variables (getting Loc/Rot/Scale from 3D space)
			elif var_type == 'TRANSFORMS':
				tar_obj.transform_type = tar.transform_type
				tar_obj.transform_space = tar.transform_space
				if tar.transform_type.startswith("ROT"):
					tar_obj.rotation_mode = tar.rotation_mode
			
			# - Distance-based variables
			elif var_type == 'LOC_DIFF':
				tar_obj.transform_space = tar.transform_space
			
			# Bones require a specific sub-target name within an Armature
			if tar.id and tar.id.type == 'ARMATURE' and tar.bone_target:
				tar_obj.bone_target = tar.bone_target

			targets.append(tar_obj)
		
		variables.append(DriverVariableData(name=var.name, var_type=var_type, targets=targets))

	# Capture Driver F-Curve Influence and Modifiers
	driver_fcurve = serialize_fcurve(precision, fcurve)
	modifiers: List[DriverModifierData] = [
		DriverModifierData(
			mod_type=mod.type,
			settings={
				# Automatically scrape all settings for this modifier type
				p.identifier: round_value(getattr(mod, p.identifier), precision)
				for p in mod.bl_rna.properties
				if not p.is_readonly and p.identifier not in ('name', 'type', 'is_active')
			})
		# Ignore modifiers that are turned off or have no strength
		for mod in fcurve.modifiers
		if not mod.mute and getattr(mod, "influence", 1.0) > 0.0
	]

	return DriverFingerprint(
		drv_type=drv.type,
		# Only 'SCRIPTED' drivers use the expression string (e.g., "var * 2")
		expression=drv.expression if drv.type == 'SCRIPTED' else None,
		variables=variables,
		fcurve=driver_fcurve,
		modifiers=modifiers
	)

# --- NODE TREE ANALYSIS ---

def extract_property(target_val: object, id_block: bpy.types.ID, data_path: str, precision: int) -> PropertyEntry:
	"""
	Bundles a property's current value with its associated animation 
	and driver data.

	target_val: The actual value (already retrieved).
	id_block: The owner of the animation (Material/NodeTree).
	data_path: The RNA path for driver/animation lookup.
	"""
	return PropertyEntry(
		val=round_value(target_val, precision),
		driver=get_driver_fingerprint(precision, id_block, data_path),
		animation=get_animation_fingerprint(precision, id_block, data_path)
	)

def get_material_fingerprint(material: bpy.types.Material, compare_settings: bool, use_action_names: bool, precision: int) -> MaterialFingerprint:
	"""Generates a unique signature of a material's node tree and render settings to identify duplicates."""
	fp = MaterialFingerprint()

	# 1. Handle Surface Type
	if not material.node_tree:
		fp.mat_type = "FIXED_MAT"
		fp.diffuse = round_value(material.diffuse_color, precision)
		fp.roughness = round_value(material.roughness, precision)
		fp.metallic = round_value(material.metallic, precision)
	else:
		fp.mat_type = "NODE_TREE"
		fp.node_tree_data = get_node_group_fingerprint(material.node_tree, precision)

	# 2. Gather Action Names (Optional metadata)
	if use_action_names:
		if material.animation_data and material.animation_data.action:
			fp.mat_action_name = material.animation_data.action.name
		
		nt = material.node_tree
		if nt and nt.animation_data and nt.animation_data.action:
			fp.node_tree_action_name = nt.animation_data.action.name

	# 3. Full Animation Data (F-Curves)
	anim_list = get_animation_fingerprint(precision, material)
	if anim_list:
		fp.animation = {}
		for f in anim_list:
			# Group by data_path to match Dict[str, List[FCurveData]]
			if f.data_path not in fp.animation:
				fp.animation[f.data_path] = []
			fp.animation[f.data_path].append(f)
	else:
		fp.animation = None

	# 4. Gather Settings and Line Art
	if compare_settings:
		# Material Render Settings
		fp.render_settings = {
			prop.identifier: extract_property(getattr(material, prop.identifier), material, prop.identifier, precision)
			for prop in material.bl_rna.properties
			if not prop.is_readonly and prop.identifier not in IGNORE_MAT_SETTINGS
		}

		# Line Art Settings (Nested object property)
		if hasattr(material, "lineart"):
			la = material.lineart
			fp.line_art_settings = {
				prop.identifier: extract_property(getattr(la, prop.identifier), material, f"lineart.{prop.identifier}", precision)
				for prop in la.bl_rna.properties
				if not prop.is_readonly and prop.identifier not in IGNORE_MAT_SETTINGS
			}

	return fp

def get_node_group_fingerprint(node_tree: bpy.types.NodeTree, precision: int) -> Optional[NodeTreeFingerprint]:
	"""Recursively maps the connected node network, properties, and internal group contents."""   
	if not node_tree:
		return

	# Filter: Only process nodes that actually lead to an output.
	# This prevents 'stray' nodes from making two materials look different.
	active_nodes = get_connected_nodes(node_tree)
	nodes_data: List[NodeFingerprint] = []

	# Sort: We sort by type and name so that the order of nodes in 
	# the list is always identical (deterministic) for the same setup.
	for node in sorted(active_nodes, key=lambda n: (n.bl_idname, n.name)):
		if node.bl_idname in ('NodeFrame', 'NodeReroute'):
			continue

		# Capture Attributes: Every input property, slider, checkbox, enum, etc. on the node.
		properties = {
			p.identifier: extract_property(getattr(node, p.identifier), node_tree, f'nodes["{node.name}"].{p.identifier}', precision)
			for p in node.bl_rna.properties
			if p.identifier not in IGNORE_PROPS and not p.is_readonly
		}

		# Capture Inputs: Only record inputs that are NOT linked (static values).
		# Linked inputs are handled later in the 'links_data' section.
		inputs = [
			extract_property(socket.default_value, node_tree, f'nodes["{node.name}"].inputs[{i}].default_value', precision)
			for i, socket in enumerate(node.inputs)
			if not socket.is_linked and hasattr(socket, "default_value")
		]

		# RECURSION: If this node is a group, we call this function again
		# to fingerprint the 'inside' of the group. This can go many levels deep.
		nested_group = None
		if node.bl_idname == 'ShaderNodeGroup' and node.node_tree:
			nested_group = get_node_group_fingerprint(node.node_tree, precision)

		nodes_data.append(NodeFingerprint(
			node_type=node.bl_idname,
			muted=node.mute,
			properties=properties,
			inputs=inputs,
			group_content=nested_group
		))

	# Links: Define the "wiring" of the network. 
	# We trace from the Destination (input) back to the Source (output).
	links_data = [
		NodeLinkData(
			from_socket=(source_socket := trace_socket(dest_socket)).name,
			from_node=source_socket.node.bl_idname,
			to_socket=dest_socket.name,
			to_node=node.bl_idname)

		for node in active_nodes if node.bl_idname not in ('NodeFrame', 'NodeReroute')
		for dest_socket in node.inputs if dest_socket.is_linked and (source_socket := trace_socket(dest_socket)).node in active_nodes
	]

	# Sorting links by a string representation ensures the link order 
	# doesn't change if the user re-wired nodes in a different sequence.
	return NodeTreeFingerprint(nodes=nodes_data, links=sorted(links_data, key=lambda x: str(x)))

def node_tree_counter(node_tree: bpy.types.NodeTree) -> int:
	"""
	Counts all functional nodes. If a NodeGroup is found, 
	it enters that sub-tree and adds those nodes to the total count.
	"""
	count = 0
	for node in node_tree.nodes:
		# Frames and Reroutes are organizational, not functional
		if node.bl_idname in ('NodeFrame', 'NodeReroute'):
			continue
		count += 1

		# If it's a group, count its internal nodes too
		if node.bl_idname == 'ShaderNodeGroup' and node.node_tree:
			count += node_tree_counter(node.node_tree)
	return count

def count_nodes_in_material(material: bpy.types.Material) -> int:
	"""Wrapper that performs a recursive count of all functional nodes within a material and its nested node groups."""
	if not material.node_tree:
		return 0
	return node_tree_counter(material.node_tree)

def round_value(val: object, decimals: int = 4) -> Primitive:
	"""
	Recursively rounds floating-point values within nested data structures and Blender types.

	Preserves the original data types where possible. If a container is immutable
	or cannot be re-instantiated (e.g., `bpy_prop_array`), it returns
	a standard tuple of the rounded values.

	Args:
		val (object): The input value or container to process.
		decimals (int, optional): The number of decimal places to round to.
			If float('inf'), exact values are returned (no rounding). | Default 4.

	Returns:
		Primitive: The processed structure with rounded floats. Falls back to a tuple if the
			original type cannot be re-instantiated.
	"""

	if val is None:
		return val

	# Standard non-roundable primitive types
	if isinstance(val, (str, bool, int)):
		return val

	# Direct float rounding
	if isinstance(val, float):
		if decimals == float('inf'):
			return val  # No rounding, return original value as-is
		return round(val, decimals)

	# Handle Mappings (Dictionaries)
	if isinstance(val, Mapping):
		return {k: round_value(v, decimals) for k, v in val.items()}

	# Handle Mathutils and Iterables
	if isinstance(val, (Iterable, Vector, Color, Euler, Quaternion, Matrix)):
		# Recursively process elements
		rounded_data = [round_value(x, decimals) for x in val]

		# Try to reconstruct the original container type (Vector, Color, etc.)
		val_type = type(val)
		try:
			# Special case: Euler rotation order preserved
			if isinstance(val, Euler):
				return val_type(rounded_data, val.order)

			return val_type(rounded_data)

		except (TypeError, ValueError):
			# Fallback for read-only/uninstantiable types (e.g., bpy_prop_array)
			return tuple(rounded_data)

	# Return as-is if type is unknown/currently not supported/not roundable
	return val

def trace_socket(dest_socket: bpy.types.NodeSocket) -> bpy.types.NodeSocket:
	"""Follows a node socket link back to its source, traversing reroute nodes."""
	if not dest_socket or not dest_socket.is_linked:
		return dest_socket
	
	# Start at the first link connected to the destination socket
	current_link = dest_socket.links[0]
	source_node = current_link.from_node

	# If the source is a reroute, we need to walk "behind" it recursively
	while source_node and source_node.bl_idname == 'NodeReroute':
		reroute_input = source_node.inputs[0]
		if not reroute_input.is_linked:
			return reroute_input
		
		current_link = reroute_input.links[0]
		source_node = current_link.from_node

	# Once we hit a non-reroute node, return the actual source output socket
	return current_link.from_socket

def get_connected_nodes(node_tree: bpy.types.NodeTree) -> Set[bpy.types.Node]:
	"""
	Traces the node tree backwards from the Material or Group outputs.
	This ensures we only fingerprint nodes that actually contribute 
	to the final render, ignoring "floating" or disconnected nodes.
	"""
	if not node_tree:
		return set()
	
	# Identify the starting output node of the data flow - typically the Material Output node, but also Group Outputs for nested groups
	outputs = [n for n in node_tree.nodes if n.bl_idname in ('ShaderNodeOutputMaterial', 'NodeGroupOutput')]
	connected = set()
	queue = deque(outputs)

	# Breadth-first search through the node tree, following links backwards from outputs to inputs
	while queue:
		node = queue.popleft()
		if node in connected:
			continue
		connected.add(node)
		for socket in node.inputs:
			for link in socket.links:
				if link.from_node not in connected:
					queue.append(link.from_node)
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

	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description="Only check materials used by selected objects",
		default=True)

	compare_name: bpy.props.BoolProperty(
		name="Compare Material Name",
		description="Only compare materials with matching base names (ignores .001, .002, etc.)",
		default=False)

	compare_settings: bpy.props.BoolProperty(
		name="Compare Material Settings",
		description="Compare materials settings alongside nodes",
		default=True)

	compare_action_name: bpy.props.BoolProperty(
		name="Compare Action Name",
		description="Treat materials with different Action names as unique, even if their animation data matches",
		default=False)

	matching_precision: bpy.props.EnumProperty(
		items=[
			('OFF', "Off (Exact)", "No rounding. Values must match exactly"),
			('STRICT', "Strict (4 decimals)", "High precision matching. Values must be nearly identical (e.g. 0.1234)"),
			('LOOSE', "Loose (2 decimals)", "Forgiving matching. Values like 0.12 and 0.124 will match"),
			('ROUGH', "Rough (1 decimal)", "Very loose matching. Values like 0.1 and 0.14 will match"),
		],
		name="Value Matching",
		description="Controls how precisely float values are compared (node inputs, colors, vectors, animation keyframes)",
		default='STRICT'
	)

	master_selection: bpy.props.EnumProperty(
		items=[
		('LOW_NODES', "Fewest Nodes",
		"Keep the simplest material (fewest nodes)."),

		('HIGH_NODES', "Most Nodes",
		"Keep the most complex material (most nodes)."),

		('HIGH_USERS', "Most Users",
		"Keep the material used by the most objects."),

		('LOW_USERS', "Fewest Users",
		"Keep the material used by the fewest objects."),
		],
		name="Material to Keep",
		description="Choose which material remains when duplicates are merged. All others are remapped to the selected material",
		default='LOW_NODES'
	)

	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

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
				if not hasattr(obj.data, "materials"):
					continue
				
				for mat in obj.data.materials:
					if not mat or mat.library or mat.is_library_indirect:
						continue
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
			group_key = util.nameGeneralize(mat.name) if self.compare_name else "GLOBAL"
			fp = get_material_fingerprint(mat, self.compare_settings, self.compare_action_name, precision_val)

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
				mats.sort(key=lambda m: (count_nodes_in_material(m), len(m.name)))

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

	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description="Only check images used by materials on selected objects",
		default=True)

	compare_name: bpy.props.BoolProperty(
		name="Compare Image Name",
		description="Compare duplicates using base names (e.g., 'Texture.001' matches 'Texture')",
		default=True)

	compare_pixels: bpy.props.BoolProperty(
		name="Compare Pixels (slower)",
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

			base_name = util.nameGeneralize(img.name) if self.compare_name else "GLOBAL"
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
			if not self.compare_pixels:
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
				if not self.compare_pixels and not pix_sum == uni_sum:
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
