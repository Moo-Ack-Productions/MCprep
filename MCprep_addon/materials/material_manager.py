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

from typing import Dict, List, Optional, Set, Tuple, Union, Any, Deque
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

IGNORE_MAT_SETTINGS = {
	'name', 'use_fake_user', 'is_runtime_data', 'tag', 'asset_data',
	'preview_render_type', 'use_preview_world', 'use_nodes', 'node_tree',
	'diffuse_color', 'specular_color', 'roughness', 'specular_intensity',
	'metallic', 'line_color', 'animation_data'
}

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
# Material structural comparison helpers
# -----------------------------------------------------------------------------

# --- SERIALIZATION HELPERS ---

def serialize_fcurve(fcurve: bpy.types.FCurve) -> Dict[str, Any]:
	"""
	Converts an F-Curve data-block into a dictionary of primitive values for structural comparison.
	"""
	fcurve.keyframe_points.sort()

	return {
		"array_index": fcurve.array_index,
		"extrapolation": fcurve.extrapolation,
		"auto_smoothing": fcurve.auto_smoothing,
		"mute": fcurve.mute,
		"keyframes": [
			serialize_keyframe(kp)
			for kp in fcurve.keyframe_points
		],
	}

def serialize_keyframe(kp: bpy.types.Keyframe) -> Dict[str, Any]:
	"""
	Serializes individual keyframe points, rounding float values to ensure consistent hashing.
	"""
	return {
		"co": tuple(round(v, 6) for v in kp.co),
		"handle_left": tuple(round(v, 6) for v in kp.handle_left),
		"handle_right": tuple(round(v, 6) for v in kp.handle_right),
		"handle_left_type": kp.handle_left_type,
		"handle_right_type": kp.handle_right_type,
		"interpolation": kp.interpolation,
		"easing": kp.easing,
		"back": round(kp.back, 6),
		"amplitude": round(kp.amplitude, 6),
		"period": round(kp.period, 6),
	}

def serialize_action(action: Optional[bpy.types.Action]) -> Optional[Dict[str, Any]]:
	"""Serializes an entire Action (collection of F-Curves)."""
	if not action:
		return None

	fcurves = sorted(action.fcurves, key=lambda f: (f.data_path, f.array_index))

	return {
		# "name": action.name, # make togglable optional by user
		"fcurves": [serialize_fcurve(f) for f in fcurves]
	}

# --- ANIMATION & DRIVER LOGIC ---
def get_animation_fingerprint(id_data: bpy.types.ID, data_path: Optional[str] = None, array_index: Optional[int] = None) -> Optional[Dict[str, Any]]:
	"""
	Retrieves the animation data for a specific property or data-block as a serializable fingerprint.
	"""
	if not id_data.animation_data or not id_data.animation_data.action:
		return None

	action = id_data.animation_data.action

	if data_path:
		fcurve = next((f for f in action.fcurves if f.data_path == data_path and
					  (array_index is None or f.array_index == array_index)), None)
		return serialize_fcurve(fcurve) if fcurve else None

	fcurves = sorted(action.fcurves, key=lambda f: (f.data_path, f.array_index))
	return {"fcurves": [serialize_fcurve(f) for f in fcurves]}

def get_driver_fingerprint(id_data: bpy.types.ID, data_path: str, array_index: Optional[int] = None) -> Optional[Dict[str, Any]]:
	"""
	Captures driver expressions, variables, and modifier stacks into a serializable structure.
	"""
	if not id_data.animation_data:
		return None

	fcurve = next((d for d in id_data.animation_data.drivers if d.data_path == data_path and (array_index is None or d.array_index == array_index)), None)
	if not fcurve:
		return None

	drv = fcurve.driver

	# 1. Basic Driver Settings
	driver_data = {"type": drv.type,}
	if drv.type == 'SCRIPTED':
		driver_data["expression"] = drv.expression

	# 2. Variable Logic (Only properties that affect driver result)

	driver_data["variables"] = []
	for var in drv.variables:
		var_data = {"name": var.name, "type": var.type, "targets": []}

		for tar in var.targets:
			tar_info = {}
			if var.type == 'CONTEXT_PROP':
				tar_info["context_property"] = tar.context_property
				tar_info["data_path"] = tar.data_path
				var_data["targets"].append(tar_info)
				continue

			tar_info = {"id": getattr(tar.id, "name_full", tar.id.name)}

			if tar.bone_target:
				tar_info["bone_target"] = tar.bone_target

			if var.type == 'SINGLE_PROP':
				tar_info["id_type"] = tar.id_type
				tar_info["data_path"] = tar.data_path

			elif var.type == 'TRANSFORMS':
				tar_info["transform_type"] = tar.transform_type
				if tar.transform_type.startswith("ROT"):
					tar_info["rotation_mode"] = tar.rotation_mode
				tar_info["transform_space"] = tar.transform_space

			elif var.type == 'LOC_DIFF':
				tar_info["transform_space"] = tar.transform_space

			var_data["targets"].append(tar_info)
		driver_data["variables"].append(var_data)

	# 3. F-Curve
	driver_data["fcurve"] = serialize_fcurve(fcurve)

	# 4. F-Curve Modifiers (Skip if muted or influence is 0)
	driver_data["modifiers"] = []
	for mod in fcurve.modifiers:
		if mod.mute or getattr(mod, "influence", 1.0) <= 0.0:
			continue

		m_data = {"type": mod.type}
		for prop in mod.bl_rna.properties:
			if not prop.is_readonly and prop.identifier not in {'name', 'type', 'is_active'}:
				m_data[prop.identifier] = to_primitive(getattr(mod, prop.identifier))
		driver_data["modifiers"].append(m_data)

	return driver_data

# --- NODE TREE ANALYSIS ---

def get_material_fingerprint(material: bpy.types.Material, exclude_settings: bool) -> Dict[str, Any]:
	"""
	Generates a unique signature of a material's node tree and render settings to identify duplicates.
	"""
	if not material.node_tree:
		fp = {
			"type": "FIXED_MAT",
			"diffuse": to_primitive(material.diffuse_color),
			"roughness": material.roughness,
			"metallic": material.metallic
		}
	else:
		fp = {
			"type": "NODE_TREE",
			"data": get_node_group_fingerprint(material.node_tree)
		}

	# Gather Animation
	anim = get_animation_fingerprint(material)
	if anim:
		fp["animation"] = anim

	# Gather Material / Render Settings
	if not exclude_settings:
		render_settings = {}
		for prop in material.bl_rna.properties:
			if prop.is_readonly or prop.identifier in IGNORE_MAT_SETTINGS:
				continue

			val_data = {"val": to_primitive(getattr(material, prop.identifier))}

			# Check for driver
			driver = get_driver_fingerprint(material, prop.identifier)
			if driver is not None:
				val_data["driver"] = driver

			render_settings[prop.identifier] = val_data

		fp["render_settings"] = render_settings

		# Gather Line Art Settings
		line_art_settings = {}
		if hasattr(material, "lineart"):
			la = material.lineart
			for prop in la.bl_rna.properties:
				if prop.is_readonly or prop.identifier in IGNORE_MAT_SETTINGS:
					continue

				value = getattr(la, prop.identifier)
				if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
					value = [to_primitive(v) for v in value]
				else:
					value = to_primitive(value)

				val_data = {"val": value}

				# Check for driver
				driver = get_driver_fingerprint(material, f"line_art.{prop.identifier}")
				if driver is not None:
					val_data["driver"] = driver

				line_art_settings[prop.identifier] = val_data

	return fp

def get_node_group_fingerprint(node_tree: bpy.types.NodeTree) -> Optional[Dict[str, Any]]:
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

			prop_entry = {"val": to_primitive(getattr(node, prop.identifier))}

			# Check Driver & Anim
			driver = get_driver_fingerprint(node_tree, data_path)
			anim = get_animation_fingerprint(node_tree, data_path)
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
				input_data = {"idx": socket_idx, "val": to_primitive(default_val)}

				# Check Driver & Anim
				driver = get_driver_fingerprint(node_tree, data_path)
				anim = get_animation_fingerprint(node_tree, data_path)
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
					driver = get_driver_fingerprint(node_tree, data_path, array_idx)
					anim = get_animation_fingerprint(node_tree, data_path, array_idx)
					if driver: input_data["driver"] = driver
					if anim: input_data["animation"] = anim

					node_data["inputs"].append(input_data)


		if node.bl_idname in {'ShaderNodeGroup', 'GeometryNodeGroup'} and node.node_tree: # 'GeometryNodeGroup' included for future merge geoNode operator
			node_data["group_content"] = get_node_group_fingerprint(node.node_tree)
		nodes_data.append(node_data)

	links_data = []
	for node in active_nodes:
		if node.bl_idname in {'NodeFrame', 'NodeReroute'}: continue
		for socket in node.inputs:
			if socket.is_linked:
				src = trace_socket(socket)
				if src.node in active_nodes:
					links_data.append({"from_socket": src.name, "from_node": src.node.bl_idname, "to_socket": socket.name, "to_node": node.bl_idname})

	return {"nodes": nodes_data, "links": sorted(links_data, key=lambda x: str(x))}

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
			if node.bl_idname in {'ShaderNodeGroup', 'GeometryNodeGroup'} and node.node_tree:
				count += _recursive_count(node.node_tree)
		return count

	return _recursive_count(material.node_tree)

def to_primitive(val: Any) -> Union[int, float, str, bool, list, None]:
	"""
	Converts Blender-specific data types into standard Python primitives for serialization.
	"""
	if isinstance(val, (int, float)):
		return round(val, 6)
	elif isinstance(val, (str, bool, type(None))):
		return val
	elif hasattr(val, "to_list"):
		return [round(x, 6) for x in val.to_list()]
	elif hasattr(val, "__iter__"):
		return [to_primitive(x) for x in val]
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
	outputNodes = [n for n in node_tree.nodes if n.bl_idname in {'ShaderNodeOutputMaterial', 'NodeGroupOutput'}]
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
	bl_options = {'REGISTER', 'UNDO'} #add group_undo?

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
						if mat and not mat.library:
							materials_to_check.add(mat)
			materials_to_check = list(materials_to_check)
		else:
			materials_to_check = [m for m in bpy.data.materials if not m.library]

		if not materials_to_check:
			self.report({'INFO'}, "No materials found to process")
			return {'FINISHED'}

		precount = len(bpy.data.materials)

		# 2. Grouping by Fingerprint
		# Structure: { group_key: [ {fingerprint: dict, materials: [mat1, mat2]} ] }
		fingerprint_groups = {}

		for mat in materials_to_check:
			group_key = mat.name.split('.')[0] if self.group_by_name else "GLOBAL"
			fp = get_material_fingerprint(mat, self.exclude_mat_settings)

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

		for old_mat, master_mat in merge_map.items():
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
