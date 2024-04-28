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

import json
import os
import random
from typing import List, TypeVar, Tuple, Sequence
from pathlib import Path

import bmesh
from bpy_extras.io_utils import ImportHelper
import bpy
from bpy.types import Context, Collection, Image, Mesh
from mathutils import Vector

from .. import util
from .. import tracking

from . import spawn_util

from ..conf import env, VectorType

# For Geometry nodes modifier in 3.0
if util.bv30():
	from bpy.types import NodesModifier
else:
	NodesModifier = TypeVar("NodesModifier")

# Check spawn_util.py for the
# definition of ListEffectsAssets
ListEffectsAssets = TypeVar("ListEffectsAssets")

# -----------------------------------------------------------------------------
# Global enum values
# -----------------------------------------------------------------------------

# Enum values for effect_type for safe string comparisons.
GEO_AREA = "geo_area"
PARTICLE_AREA = "particle_area"
COLLECTION = "collection"
IMG_SEQ = "img_seq"

# Collection name for effects.
EFFECT_EXCLUDE = "Effects Exclude"

EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff"]


# -----------------------------------------------------------------------------
# Core effects types
# -----------------------------------------------------------------------------


def add_geonode_area_effect(context: Context, effect: ListEffectsAssets) -> bpy.types.Object:
	"""Create a persistent effect which is meant to emulate a wide-area effect.

	Effect is of type: ListEffectsAssets.

	Import a geonode collection from the effects_geonodes.blend file, and then
	parent it to the camera. These geonodes should function such that the
	particles are dynamically loaded based on position to camera, and don't
	require any pre-simulation time as they are deterministically placed (so
	the camera can be zooming through an area and not need to give time for a
	particle system to let some particles fall first).
	"""
	existing_geonodes = [
		ndg for ndg in bpy.data.node_groups
		if ndg.type == "GEOMETRY" and ndg.name == effect.subpath]

	# Load this geo node if it doesn't already exist.
	if not existing_geonodes:
		with bpy.data.libraries.load(effect.filepath) as (data_from, data_to):

			for this_group in data_from.node_groups:
				if this_group != effect.subpath:
					continue
				data_to.node_groups.append(this_group)
				break
		# Post
		post_geonodes = [
			ndg for ndg in bpy.data.node_groups
			if ndg.type == "GEOMETRY" and ndg.name == effect.subpath]
		diff = list(set(post_geonodes) - set(existing_geonodes))
		this_nodegroup = diff[0]
	else:
		this_nodegroup = existing_geonodes[0]

	mesh = bpy.data.meshes.new(f"{effect.name} empty mesh")
	new_obj = bpy.data.objects.new(effect.name, mesh)

	# TODO: consider trying to pick up the current collection setting,
	# or placing into an explicit effects collection.
	util.obj_link_scene(new_obj)

	geo_mod = new_obj.modifiers.new(effect.name, "NODES")
	geo_mod.node_group = this_nodegroup

	geo_update_params(context, effect, geo_mod)

	# Deselect everything and set newly added geonodes as active.
	for ob in context.scene.objects:
		if util.select_get(ob):
			util.select_set(ob, False)
	util.set_active_object(context, new_obj)
	util.select_set(new_obj, True)

	return new_obj


def add_area_particle_effect(context: Context, effect: ListEffectsAssets, location: VectorType) -> bpy.types.Object:
	"""Create a persistent effect over wide area using traditional particles.

	Effect is of type: ListEffectsAssets.

	Where geo nodes are not available (older blender versions) or if the user
	prefers to have more control of the particle system being created after.
	When created, it adds a plane over the area of the camera, with a
	determined density setting such over the given radius it emits a consistent
	amount per unit area. Ideally, the system could auto update the emission
	count even as this object is scaled.
	"""

	# Create the plane.
	mesh = get_or_create_plane_mesh("particle_plane")
	obj = bpy.data.objects.new(effect.name, mesh)
	util.obj_link_scene(obj, context)
	obj.location = location
	obj.scale = (40, 40, 40)

	# Load the indicated particle system.
	pre_systems = list(bpy.data.particles)
	with bpy.data.libraries.load(effect.filepath) as (data_from, data_to):
		for itm in data_from.particles:
			if itm == effect.name:
				data_to.particles.append(itm)
	post_systems = list(bpy.data.particles)
	imported_particles = list(set(post_systems) - set(pre_systems))[0]

	mark_particles_fake_user(imported_particles)

	# Assign the active object and selection state.
	for sel_obj in bpy.context.selected_objects:
		util.select_set(sel_obj, False)
	util.set_active_object(context, obj)
	util.select_set(obj, True)

	# Assign the newly imported system, assign generalied settings.
	bpy.ops.object.particle_system_add()
	psystem = obj.particle_systems[-1]
	psystem.settings = imported_particles
	obj.show_instancer_for_render = False

	# Update particle density to match the current timeline.
	frames = psystem.settings.frame_end - psystem.settings.frame_start
	density = psystem.settings.count / frames

	early_offset = 30  # Start partciles before scene start.
	if "snow" in effect.name.lower():
		early_offset = 150  # Much slower partciles need more time.
	psystem.settings.frame_start = context.scene.frame_start - early_offset
	psystem.settings.frame_end = context.scene.frame_end
	scene_frames = psystem.settings.frame_end - psystem.settings.frame_start
	psystem.settings.count = int(density * scene_frames)

	return obj


def add_collection_effect(context: Context, effect: ListEffectsAssets, location: VectorType, frame: int) -> bpy.types.Object:
	"""Spawn a pre-animated collection effect at a specific point and time.

	Import a new copy of a collection from the effects_collections.blend file.
	Each collection hsa some pre-animated settings. When the collection is
	imported, all animation, particle, or other time-dependent features are
	shifted by the indicated number of frames over. It is then placed as an
	expanded collection. No instancing because there's no savings.

	Effect is of type: ListEffectsAssets.

	Could potentially offer to 'prebake' so that once its loaded, it auto bakes
	any particles the collection may be using.
	"""

	pre_systems = list(bpy.data.particles)

	keyname = f"{effect.name}_frame_{frame}"
	if keyname in util.collections():
		coll = util.collections()[keyname]
	else:
		coll = import_animated_coll(context, effect, keyname)
		coll.name = f"{effect.name}_{frame}"

		# Update the animation per intended frame.
		offset_animation_to_frame(coll, frame)

		post_systems = list(bpy.data.particles)
		imported_particles = list(set(post_systems) - set(pre_systems))
		for system in imported_particles:
			mark_particles_fake_user(system)

	# Create the object instance.
	obj = util.addGroupInstance(coll.name, location)
	obj.location = location
	obj.name = keyname
	util.move_to_collection(obj, context.collection)

	# Deselect everything and set newly added empty as active.
	for ob in context.scene.objects:
		if util.select_get(ob):
			util.select_set(ob, False)
	util.set_active_object(context, obj)
	util.select_set(obj, True)


def add_image_sequence_effect(context: Context, effect: ListEffectsAssets, location: VectorType, frame: int, speed: float) -> bpy.types.Object:
	"""Spawn a short-term sequence of individual images at a point in time.

	Effect is of type: ListEffectsAssets.
	"""

	# Get the list of explicit files.
	basepath = os.path.dirname(effect.filepath)
	root = os.path.basename(effect.filepath)
	images = [
		img for img in os.listdir(basepath)
		if img.startswith(root) and os.path.isfile(os.path.join(basepath, img))
		and os.path.splitext(img)[-1].lower() in EXTENSIONS
	]

	if not images:
		raise Exception(f"Failed to load images in question: {root}")

	# Implement human sorting, such that img_2.png is before img_11.png
	human_sorted = util.natural_sort(images)

	# Create the collection to add objects into.
	keyname = f"{effect.name}_frame_{frame}@{speed:.2f}"

	# Move the source collection (world center) into excluded coll
	effects_vl = util.get_or_create_viewlayer(context, EFFECT_EXCLUDE)
	effects_vl.exclude = True
	seq_coll = bpy.data.collections.get(keyname)
	if not seq_coll:
		seq_coll = bpy.data.collections.new(name=keyname)
		effects_vl.collection.children.link(seq_coll)

	if len(seq_coll.objects) != len(human_sorted):
		# Generate the items before instancing collection/group.
		framerate = 1 / speed
		frames_added = []

		for i, img in enumerate(human_sorted):
			target_frame = int(frame + i * framerate)
			end_frame = int(frame + (i + 1) * framerate)
			if target_frame in frames_added:
				continue
			else:
				frames_added.append(target_frame)

			if end_frame == target_frame:
				end_frame += 1

			this_file = os.path.join(basepath, img)
			pre_objs = list(bpy.data.objects)
			bpy.ops.mcprep.spawn_item_file(
				filepath=this_file, thickness=0, skipUsage=True)
			post_objs = list(bpy.data.objects)
			new = list(set(post_objs) - set(pre_objs))

			if not new or len(new) != 1:
				print("Error fetching new object for frame ", target_frame)
				continue
			obj = new[0]
			obj.location = Vector([0, 0, 0])

			# Set the animation for visibility for the range of frames.
			def keyframe_current_visibility(context: Context, obj: bpy.types.Object, state: bool):
				frame = context.scene.frame_current

				obj.hide_render = state
				obj.hide_viewport = state
				obj.keyframe_insert(data_path="hide_viewport", frame=frame)
				obj.keyframe_insert(data_path="hide_render", frame=frame)

			context.scene.frame_current = target_frame - 1
			keyframe_current_visibility(context, obj, True)

			context.scene.frame_current = target_frame
			keyframe_current_visibility(context, obj, False)

			context.scene.frame_current = end_frame
			keyframe_current_visibility(context, obj, True)

			util.move_to_collection(obj, seq_coll)

	context.scene.frame_current = frame

	# Finalize creation of the instances.
	instance = util.addGroupInstance(seq_coll.name, location)
	if hasattr(instance, "empty_draw_size"):  # Older blender versions.
		instance.empty_draw_size = 0.25
	else:
		instance.empty_display_size = 1.0
		instance.empty_display_type = 'IMAGE'
		instance.use_empty_image_alpha = True
		instance.color[3] = 0.1

		# Load in the image to display in place of the empty.
		img_index = int(len(human_sorted) / 2)
		img_index = min(img_index, len(human_sorted) - 1)
		img = os.path.join(basepath, human_sorted[img_index])
		img_block = bpy.data.images.load(img, check_existing=True)
		instance.data = img_block

	# Move the new object into the active layer.
	util.move_to_collection(instance, context.collection)

	return instance


def add_particle_planes_effect(context: Context, image_path: Path, location: VectorType, frame: int) -> None:
	"""Spawn a short-term particle system at a specific point and time.

	This is the only effect type that does not get pre-loaded into a list. The
	user is prompted for an image, and this is then imported, chopped into a
	few smaller square pieces, and then this collection is used as a source for
	a particle system that emits some number of particles over a 1 frame
	period of time. Ideal for footfalls, impacts, etc.
	"""

	# Add object, use lower level functions to make it run faster.
	f_name = os.path.splitext(os.path.basename(image_path))[0]
	base_name = f"{f_name}_frame_{frame}"

	mesh = get_or_create_plane_mesh("particle_plane")
	obj = bpy.data.objects.new(base_name, mesh)
	util.obj_link_scene(obj, context)
	# TODO: link to currently active collection.
	obj.location = location

	# Select and make active.
	# Setting active here ensures the emitter also gets the texture, making it
	# easier to tell which particles it emits.
	for sel_obj in bpy.context.selected_objects:
		util.select_set(sel_obj, False)
	util.set_active_object(context, obj)
	util.select_set(obj, True)

	# Generate the collection/group of objects to be spawned.
	img = bpy.data.images.get(f_name)
	img_abs_path = bpy.path.abspath(image_path)
	if not img or not bpy.path.abspath(img.filepath) == img_abs_path:
		# Check if any others loaded, otherwise just load new.
		for this_img in bpy.data.images:
			if bpy.path.abspath(this_img.filepath) == img_abs_path:
				img = this_img
				break
		if not img:
			img = bpy.data.images.load(image_path)

	pcoll = get_or_create_particle_meshes_coll(
		context, f_name, img)

	# Set the material for the emitter object. Though not actually rendered,
	# this helps clarify which particle is being emitted from this object.
	mat = None
	for ob in pcoll.objects:
		if ob.material_slots and ob.material_slots[0].material:
			mat = ob.material_slots[0].material
			break
	if mat:
		if not obj.material_slots:
			obj.data.materials.append(mat)
		# Must use 'OBEJCT' instead of mesh data, otherwise all particle
		# emitters will have the same material (how it was initially working)
		obj.material_slots[0].link = 'OBJECT'
		obj.material_slots[0].material = mat
		print(f"Linked {obj.name} with {mat.name}")

	apply_particle_settings(obj, frame, base_name, pcoll)


# -----------------------------------------------------------------------------
# Core effects supportive functions
# -----------------------------------------------------------------------------

def geo_update_params(context: Context, effect: ListEffectsAssets, geo_mod: NodesModifier) -> None:
	"""Update the paramters of the applied geonode effect.

	Loads fields to apply based on json file where necessary.
	"""

	base_file = os.path.splitext(os.path.basename(effect.filepath))[0]
	base_dir = os.path.dirname(effect.filepath)
	jpath = os.path.join(base_dir, f"{base_file}.json")
	geo_fields = {}
	if os.path.isfile(jpath):
		geo_fields = geo_fields_from_json(effect, jpath)
	else:
		env.log("No json params path for geonode effects", vv_only=True)
		return

	# Determine if these special keywords exist.
	has_followkey = False
	for input_name in geo_fields.keys():
		if geo_fields[input_name] == "FOLLOW_OBJ":
			has_followkey = True
	env.log(f"geonode has_followkey field? {has_followkey}", vv_only=True)

	# Create follow empty if required by the group.
	camera = context.scene.camera
	center_empty = None
	if has_followkey:
		center_empty = bpy.data.objects.new(
			name=f"{effect.name} origin",
			object_data=None)
		util.obj_link_scene(center_empty)
		if camera:
			center_empty.parent = camera
			center_empty.location = (0, 0, -10)
		else:
			center_empty.location = util.get_cursor_location()

	input_list = []
	input_node = None
	for nd in geo_mod.node_group.nodes:
		if nd.type == "GROUP_INPUT":
			input_node = nd
			break
	if input_node is None:
		raise RuntimeError(f"Geo node has no input group: {effect.name}")
	input_list = list(input_node.outputs)

	# Cache mapping of names like "Weather Type" to "Input_1" internals.
	geo_inp_id = {}
	for inp in input_list:
		if inp.name in list(geo_fields):
			geo_inp_id[inp.name] = inp.identifier

	# Now update the final geo node inputs based gathered settings.
	for inp in input_list:
		if inp.name in list(geo_fields):
			value = geo_fields[inp.name]
			if value == "CAMERA_OBJ":
				env.log("Set cam for geonode input", vv_only=True)
				geo_mod[geo_inp_id[inp.name]] = camera
			elif value == "FOLLOW_OBJ":
				if not center_empty:
					env.log("Geo Node effects: Center empty missing, not in preset!")
				else:
					env.log("Set follow for geonode input", vv_only=True)
					geo_mod[geo_inp_id[inp.name]] = center_empty
			else:
				env.log("Set {} for geonode input".format(inp.name), vv_only=True)
				geo_mod[geo_inp_id[inp.name]] = value
		# TODO: check if any socket name in json specified not found in node.


def geo_fields_from_json(effect: ListEffectsAssets, jpath: Path) -> dict:
	"""Extract json values from a file for a given effect.

	Parse for a json structure with a hierarhcy of:

	geo node group name:
		sub effect name e.g. "rain":
			input setting name: value

	Special values for given keys (where key is the geonode UI name):
		CAMERA_OBJ: Tells MCprep to assign the active camera object to slot.
		FOLLOW_OBJ: Tells MCprep to assign a generated empty to this slot.
	"""
	env.log(f"Loading geo fields form json: {jpath}")
	with open(jpath) as fopen:
		jdata = json.load(fopen)

	# Find the matching
	geo_fields = {}
	for geonode_name in list(jdata):
		if geonode_name != effect.subpath:
			continue
		for effect_preset in list(jdata[geonode_name]):
			if effect_preset == effect.name:
				geo_fields = jdata[geonode_name][effect_preset]
				break
	if not geo_fields:
		print("Failed to load presets for this effect from json")
	return geo_fields


def get_or_create_plane_mesh(
	mesh_name: str, uvs: Sequence[Tuple[int, int]] = []) -> Mesh:
	"""Generate a 1x1 plane with UVs stretched out to ends, cache if exists.

	Arg `uvs` represents the 4 coordinate values clockwise from top left of the
	mesh, with values of 0-1.
	"""

	# Create or fetch mesh, returned existing cache if it exists.
	mesh = bpy.data.meshes.get(mesh_name)
	if mesh is None:
		mesh = bpy.data.meshes.new(mesh_name)
	else:
		return mesh

	bm = bmesh.new()
	uv_layer = bm.loops.layers.uv.verify()

	verts = [
		[-0.5, 0.5, 0],  # Top left, clockwise down.
		[0.5, 0.5, 0],
		[0.5, -0.5, 0],
		[-0.5, -0.5, 0]
	]
	for v in reversed(verts):
		bm.verts.new(v)

	if not uvs:
		uvs = [[0, 0], [1, 0], [1, 1], [0, 1]]
	if len(uvs) != 4:
		raise Exception(f"Wrong number of coords for UVs: {len(uvs)}")

	face = bm.faces.new(bm.verts)
	face.normal_update()

	for i, loop in enumerate(reversed(face.loops)):
		loop[uv_layer].uv = uvs[i]

	bm.to_mesh(mesh)
	bm.free()

	return mesh


def get_or_create_particle_meshes_coll(context: Context, particle_name: str, img: Image) -> Collection:
	""" TODO 2.7
	Generate a selection of subsets of a given image for use in particles.

	The goal is that instead of spawning entire, complete UVs of the texture,
	we spawn little subsets of the particles.

	Returns a collection or group depending on bpy version.
	"""
	# Check if it exists already, and if it has at least one object,
	# assume we'll just use those.
	particle_key = f"{particle_name}_particles"
	particle_coll = util.collections().get(particle_key)
	if particle_coll:
		# Check if any objects.
		if len(particle_coll.objects) > 0:
			return particle_coll

	# Create the collection/group.
	particle_view = util.get_or_create_viewlayer(context, particle_key)
	particle_view.exclude = True

	# Get or create the material.
	if particle_name in bpy.data.materials:
		mat = bpy.data.materials.get(particle_name)
	else:
		bpy.ops.mcprep.load_material(filepath=img.filepath, skipUsage=True)
		mat = bpy.data.materials.get(particle_name)

	# The different variations of UV slices to create, clockwise from top left.
	num = 4.0  # Number created is this squared.
	uv_variants = {}

	for x in range(int(num)):
		for y in range(int(num)):
			this_key = "{}-{}".format(x, y)
			# Reference: [0, 0], [1, 0], [1, 1], [0, 1]
			uv_variants[this_key] = [
				[x / num, y / num],
				[(x + 1) / num, y / num],
				[(x + 1) / num, (y + 1) / num],
				[x / num, (y + 1) / num]
			]

	# Decide randomly which ones to create (making all would be excessive).
	while len(uv_variants) > 6:
		keys = list(uv_variants)
		del_index = random.randrange(len(keys))
		del uv_variants[keys[del_index]]

	for key in uv_variants:
		name = f"{particle_name}_particle_{key}"
		mesh = get_or_create_plane_mesh(name, uvs=uv_variants[key])
		obj = bpy.data.objects.new(name, mesh)
		obj.data.materials.append(mat)

		util.move_to_collection(obj, particle_view.collection)

	return particle_view.collection


def apply_particle_settings(
	obj: bpy.types.Object, frame: int, base_name: str, pcoll: Collection) -> None:
	"""Update the particle settings for particle planes."""
	obj.scale = (0.5, 0.5, 0.5)  # Tighen up the area it spawns over.

	bpy.ops.object.particle_system_add()  # Must be active object.
	psystem = obj.particle_systems[-1]  # = ... # How to gen new system?

	psystem.name = base_name
	psystem.seed = frame
	psystem.settings.count = 5
	psystem.settings.frame_start = frame
	psystem.settings.frame_end = frame + 1
	psystem.settings.lifetime = 30
	psystem.settings.lifetime_random = 0.2
	psystem.settings.emit_from = 'FACE'
	psystem.settings.distribution = 'RAND'
	psystem.settings.normal_factor = 1.5
	psystem.settings.use_rotations = True
	psystem.settings.rotation_factor_random = 1
	psystem.settings.particle_size = 0.2
	psystem.settings.factor_random = 1

	obj.show_instancer_for_render = False
	psystem.settings.render_type = 'COLLECTION'
	psystem.settings.instance_collection = pcoll


def mark_particles_fake_user(particles: bpy.types.ParticleSettings):
	"""Assigns particle objects as fake users, to avoid blender's cleanup."""
	if not hasattr(particles, "instance_object"):
		return
	print("DID THIS RUN? marking as fake user on: ", particles, "-", particles.instance_object)
	if particles.instance_object:
		particles.instance_object.use_fake_user = True


def import_animated_coll(
	context: Context, effect: ListEffectsAssets, keyname: str) -> Collection:
	"""Import and return a new animated collection given a specific key."""
	init_colls = list(util.collections())
	any_imported = False
	with bpy.data.libraries.load(effect.filepath) as (data_from, data_to):
		collections = spawn_util.filter_collections(data_from)
		for itm in collections:
			if itm != effect.name:
				continue
			data_to.collections.append(itm)
			any_imported = True

	final_colls = list(util.collections())
	new_colls = list(set(final_colls) - set(init_colls))
	if not new_colls:
		if any_imported:
			env.log("New collection loaded, but not picked up")
		else:
			env.log("No colleections imported or recognized")
		raise Exception("No collections imported")
	elif len(new_colls) > 1:
		# Pick the closest fitting one. At worst, will pick a random one.
		coll = None
		for this_coll in new_colls:
			if util.nameGeneralize(this_coll.name) == effect.name:
				coll = this_coll
		if not coll:
			raise Exception("Could not import required collection")
	else:
		coll = new_colls[0]

	# Move the source collection (world center) into excluded coll
	effects_vl = util.get_or_create_viewlayer(context, EFFECT_EXCLUDE)
	effects_vl.exclude = True
	effects_vl.collection.children.link(coll)

	return coll


def offset_animation_to_frame(collection: Collection, frame: int) -> None:
	"""Offset all animations and particles based on the given frame."""
	if frame == 1:
		return
	frame -= 1

	objs = []
	actions = []
	mats = []

	objs = list(collection.all_objects)

	# Expand the list by checking for any empties instancing other collections.
	for obj in objs:
		if obj.instance_collection:
			objs.extend(list(obj.instance_collection.all_objects))

	# Make unique.
	objs = list(set(objs))

	for obj in objs:
		if obj.animation_data and obj.animation_data.action:
			actions.append(obj.animation_data.action)
		for sys in obj.particle_systems:
			# Be sure to change end frame first, otherwise its overridden.
			sys.settings.frame_end += frame
			sys.settings.frame_start += frame
		for slot in obj.material_slots:
			if slot.material:
				mats.append(slot.material)
	mats = list(set(mats))

	for mat in mats:
		if mat.animation_data:
			# Materials with animation data
			actions.append(mat.animation_data.action)
		if mat.node_tree.animation_data:
			actions.append(mat.node_tree.animation_data.action)
		for node in mat.node_tree.nodes:
			# Nodegroups that contain animations within.
			if hasattr(node, "node_tree") and node.node_tree.animation_data:
				actions.append(node.node_tree.animation_data.action)

	actions = list(set(actions))

	# Finally, perform the main operation of shifting keyframes.
	for action in actions:
		for fcurve in action.fcurves:
			# Ensure we move points in reverse order, otherwise adjacent frames
			# will overwrite each other.
			points = list(fcurve.keyframe_points)
			points.sort(key=lambda x: x.co.x)
			for point in points:
				point.co.x += frame
				point.handle_left.x += frame
				point.handle_right.x += frame


# -----------------------------------------------------------------------------
# List UI load functions
# -----------------------------------------------------------------------------


def update_effects_path(self, context: Context) -> None:
	"""List for UI effects callback ."""
	env.log("Updating effects path", vv_only=True)
	update_effects_list(context)


def update_effects_list(context: Context) -> None:
	"""Update the effects list."""
	mcprep_props = context.scene.mcprep_props
	mcprep_props.effects_list.clear()

	if env.use_icons and env.preview_collections["effects"]:
		try:
			bpy.utils.previews.remove(env.preview_collections["effects"])
		except Exception as e:
			print(e)
			env.log("MCPREP: Failed to remove icon set, effects")

	load_geonode_effect_list(context)
	load_area_particle_effects(context)
	load_collection_effects(context)
	load_image_sequence_effects(context)


def load_geonode_effect_list(context: Context) -> None:
	"""Load effects defined by geonodes for wide area effects."""
	if not util.bv30():
		print("Not loading geonode effects")
		return

	mcprep_props = context.scene.mcprep_props
	path = context.scene.mcprep_effects_path
	path = os.path.join(path, "geonodes")

	if not os.path.isdir(path):
		print("The geonode directory is missing! Reinstall MCprep")
		print(path)
		return

	# Find all files with geonodes.
	blends = [
		os.path.join(path, blend) for blend in os.listdir(path)
		if os.path.isfile(os.path.join(path, blend))
		and blend.lower().endswith(".blend")
	]
	json_files = [
		os.path.join(path, jsf) for jsf in os.listdir(path)
		if os.path.isfile(os.path.join(path, jsf))
		and jsf.lower().endswith(".json")
	]

	env.log("json pairs of blend files", vv_only=True)
	env.log(json_files, vv_only=True)

	for bfile in blends:
		row_items = []
		using_json = False
		js_equiv = f"{os.path.splitext(bfile)[0]}.json"
		if js_equiv in json_files:
			env.log(f"Loading json preset for geonode for {bfile}")
			# Read nodegroups to include from json presets file.
			jpath = f"{os.path.splitext(bfile)[0]}.json"
			with open(jpath) as jopen:
				jdata = json.load(jopen)
			row_items = jdata.keys()
			using_json = True
		else:
			env.log(f"Loading nodegroups from blend for geonode effects: {bfile}")
			# Read nodegroup names from blend file directly.
			with bpy.data.libraries.load(bfile) as (data_from, _):
				row_items = list(data_from.node_groups)

		for itm in row_items:
			if spawn_util.SKIP_COLL in itm.lower():  # mcskip
				continue

			if using_json:
				# First key in index is nodegroup, save to subpath, but then
				# the present name (list of keys within) are the actual names.
				for preset in jdata[itm]:
					env.log(f"\tgeonode preset: {preset}", vv_only=True)
					effect = mcprep_props.effects_list.add()
					effect.name = preset  # This is the assign json preset name.
					effect.subpath = itm  # This is the node group name.
					effect.effect_type = GEO_AREA
					effect.filepath = bfile
					effect.index = len(mcprep_props.effects_list) - 1  # For icon index.

			else:
				# Using the nodegroup name itself as the key, no subpath.
				effect = mcprep_props.effects_list.add()
				effect.name = itm
				effect.subpath = itm  # Always the nodegroup name.
				effect.effect_type = GEO_AREA
				effect.filepath = bfile
				effect.index = len(mcprep_props.effects_list) - 1  # For icon index.


def load_area_particle_effects(context : Context) -> None:
	"""Load effects defined by wide area particle effects (non geo nodes).

	This is a fallback for older versions of blender which don't have geonodes,
	or where geonodes aren't working well or someone just wants to use
	particles.
	"""
	mcprep_props = context.scene.mcprep_props
	path = context.scene.mcprep_effects_path
	path = os.path.join(path, "particle")

	if not os.path.isdir(path):
		print("The particle directory is missing! Reinstall MCprep")
		print(path)
		return

	# Find all files with geonodes.
	blends = [
		os.path.join(path, blend) for blend in os.listdir(path)
		if os.path.isfile(os.path.join(path, blend))
		and blend.lower().endswith("blend")
	]

	for bfile in blends:
		with bpy.data.libraries.load(bfile) as (data_from, _):
			particles = list(data_from.particles)

		for itm in particles:
			effect = mcprep_props.effects_list.add()
			effect.effect_type = PARTICLE_AREA
			effect.name = itm
			effect.filepath = bfile
			effect.index = len(mcprep_props.effects_list) - 1  # For icon index.


def load_collection_effects(context: Context) -> None:
	"""Load effects defined by collections saved to an effects blend file."""
	mcprep_props = context.scene.mcprep_props
	path = context.scene.mcprep_effects_path
	path = os.path.join(path, "collection")

	if not os.path.isdir(path):
		print("The collection directory is missing! Reinstall MCprep")
		print(path)
		return

	# Find all files with geonodes.
	blends = [
		os.path.join(path, blend) for blend in os.listdir(path)
		if os.path.isfile(os.path.join(path, blend))
		and blend.lower().endswith("blend")
	]

	for bfile in blends:
		with bpy.data.libraries.load(bfile) as (data_from, _):
			collections = spawn_util.filter_collections(data_from)

		for itm in collections:
			effect = mcprep_props.effects_list.add()
			effect.effect_type = "collection"
			effect.name = itm
			effect.filepath = bfile
			effect.index = len(mcprep_props.effects_list) - 1  # For icon index.


def load_image_sequence_effects(context: Context) -> None:
	"""Load effects from the particles folder that should be animated."""
	mcprep_props = context.scene.mcprep_props

	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)

	# Check levels.
	lvl_0 = os.path.join(resource_folder, "particle")
	lvl_1 = os.path.join(resource_folder, "textures", "particle")
	lvl_2 = os.path.join(resource_folder, "minecraft", "textures", "particle")
	lvl_3 = os.path.join(resource_folder, "assets", "minecraft", "textures", "particle")

	if not os.path.isdir(resource_folder):
		env.log(
			"The particle resource directory is missing! Assign another resource pack")
		return
	elif os.path.isdir(lvl_0):
		resource_folder = lvl_0
	elif os.path.isdir(lvl_1):
		resource_folder = lvl_1
	elif os.path.isdir(lvl_2):
		resource_folder = lvl_2
	elif os.path.isdir(lvl_3):
		resource_folder = lvl_3

	# List all files and reduce to basename: fname_01.png to fname.
	rfiles = os.listdir(resource_folder)
	effect_files = [
		os.path.splitext(fname)[0].rsplit("_", 1)[0]
		for fname in rfiles
		if os.path.isfile(os.path.join(resource_folder, fname))
		and os.path.splitext(fname)[-1].lower() in EXTENSIONS
	]
	effect_files = list(set(effect_files))

	effect_files = sorted(effect_files)

	for itm in effect_files:
		effect = mcprep_props.effects_list.add()
		effect.effect_type = "img_seq"
		effect.name = itm.replace("_", " ").capitalize()
		effect.description = "Instance the {} particle aniamted sequence".format(
			itm)

		# Note: the item being added is NOT a full filepath, but the prefix.
		effect.filepath = os.path.join(resource_folder, itm)

		effect.index = len(mcprep_props.effects_list) - 1  # For icon index.

		# Try to load a middle frame as the icon.
		if not env.use_icons or env.preview_collections["effects"] == "":
			continue
		effect_files = [
			os.path.join(resource_folder, fname)
			for fname in rfiles
			if os.path.isfile(os.path.join(resource_folder, fname))
			and fname.startswith(itm)
			and os.path.splitext(fname)[-1].lower() in EXTENSIONS
		]
		if effect_files:
			# 0 if 1 item, otherwise greater side of median.
			e_index = int(len(effect_files) / 2)
			env.preview_collections["effects"].load(
				"effects-{}".format(effect.index), effect_files[e_index], 'IMAGE')


# -----------------------------------------------------------------------------
# Operator classes
# -----------------------------------------------------------------------------


class MCPREP_OT_effects_path_reset(bpy.types.Operator):
	"""Reset the effects path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.effects_path_reset"
	bl_label = "Reset effects path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_effects_path = addon_prefs.effects_path
		update_effects_list(context)
		return {'FINISHED'}


class MCPREP_OT_reload_effects(bpy.types.Operator):
	"""Reload effects spawner, use after changes to/new effects files"""
	bl_idname = "mcprep.reload_effects"
	bl_label = "Reload effects"

	@tracking.report_error
	def execute(self, context):
		update_effects_list(context)
		return {'FINISHED'}


class MCPREP_OT_global_effect(bpy.types.Operator):
	"""Spawn a global effect such as weather particles"""
	bl_idname = "mcprep.spawn_global_effect"
	bl_label = "Global effect"
	bl_options = {'REGISTER', 'UNDO'}

	def effects_enum(self, context):
		"""Identifies eligible global effects to include in the dropdown."""
		mcprep_props = context.scene.mcprep_props
		elist = []
		for effect in mcprep_props.effects_list:
			if effect.effect_type not in (GEO_AREA, PARTICLE_AREA):
				continue
			if effect.effect_type == GEO_AREA:
				display_type = "geometry node effect"
				short_type = " (Geo nodes)"
			else:
				display_type = "particle system effect"
				short_type = " (Particles)"
			elist.append((
				str(effect.index),
				effect.name + short_type,
				"Add {} {} from {}".format(
					effect.name,
					display_type,
					os.path.basename(effect.filepath)
				)
			))
		return elist

	effect_id: bpy.props.EnumProperty(items=effects_enum, name="Effect")
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	track_function = "effect_global"
	@tracking.report_error
	def execute(self, context):
		mcprep_props = context.scene.mcprep_props
		effect = mcprep_props.effects_list[int(self.effect_id)]

		if not os.path.isfile(bpy.path.abspath(effect.filepath)):
			self.report({'WARNING'}, "Target effects file not found")
			bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
			return {'CANCELLED'}

		if effect.effect_type == GEO_AREA:
			add_geonode_area_effect(context, effect)
			self.report(
				{"INFO"},
				"Added geo nodes, edit modifier for further control")
		elif effect.effect_type == PARTICLE_AREA:
			cam = context.scene.camera
			use_camera = False
			vartical_offset = Vector([0, 0, 15])
			if cam:
				location = context.scene.camera.location + vartical_offset
				use_camera = True
			else:
				location = util.get_cursor_location(context)

			obj = add_area_particle_effect(context, effect, location)
			if use_camera:
				const = obj.constraints.new('COPY_LOCATION')
				const.target = cam
				const.use_z = False
				obj.location = location

		self.track_param = effect.name
		return {'FINISHED'}


class MCPREP_OT_instant_effect(bpy.types.Operator):
	"""Spawn an effect that takes place at specific time and position"""
	bl_idname = "mcprep.spawn_instant_effect"
	bl_label = "Instant effect"
	bl_options = {'REGISTER', 'UNDO'}

	def effects_enum(self, context: Context) -> List[tuple]:
		"""Identifies eligible instant effects to include in the dropdown."""
		mcprep_props = context.scene.mcprep_props
		elist = []
		for effect in mcprep_props.effects_list:
			if effect.effect_type == COLLECTION:
				display_type = "preanimated collection effect"
			elif effect.effect_type == IMG_SEQ:
				display_type = "image sequence effect"
			else:
				continue
			elist.append((
				str(effect.index),
				effect.name,
				"Add {} {} from {}".format(
					effect.name,
					display_type,
					os.path.basename(effect.filepath))
			))
		return elist

	effect_id: bpy.props.EnumProperty(items=effects_enum, name="Effect")
	location: bpy.props.FloatVectorProperty(default=(0, 0, 0), name="Location")
	frame: bpy.props.IntProperty(
		default=0,
		name="Frame",
		description="Start frame for animation")
	speed: bpy.props.FloatProperty(
		default=1.0,
		min=0.1,
		name="Speed",
		description="Make the effect run faster (skip frames) or slower (hold frames)")
	show_image: bpy.props.BoolProperty(
		default=False,
		name="Show image preview",
		description="Show a middle animation frame as a viewport preview")
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	track_function = "effect_instant"
	@tracking.report_error
	def execute(self, context):
		mcprep_props = context.scene.mcprep_props
		effect = mcprep_props.effects_list[int(self.effect_id)]

		if effect.effect_type == "collection":
			if not os.path.isfile(bpy.path.abspath(effect.filepath)):
				self.report({'WARNING'}, "Target effects file not found")
				bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
				return {'CANCELLED'}
			add_collection_effect(context, effect, self.location, self.frame)

		elif effect.effect_type == "img_seq":
			base_path = os.path.dirname(effect.filepath)
			if not os.path.isdir(bpy.path.abspath(base_path)):
				self.report({'WARNING'}, "Target effects file not found: base_path")
				print(base_path)
				bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
				return {'CANCELLED'}

			inst = add_image_sequence_effect(
				context, effect, self.location, self.frame, self.speed)
			if not self.show_image:
				inst.data = None

		self.track_param = effect.name
		return {'FINISHED'}


class MCPREP_OT_spawn_particle_planes(bpy.types.Operator, ImportHelper):
	"""Create a particle system from a selected image input"""
	bl_idname = "mcprep.spawn_particle_planes"
	bl_label = "Spawn Particle Planes"
	bl_options = {'REGISTER', 'UNDO'}

	location: bpy.props.FloatVectorProperty(
		default=(0, 0, 0), name="Location")
	frame: bpy.props.IntProperty(default=0, name="Frame")

	# Importer helper
	exts = ";".join(["*" + ext for ext in EXTENSIONS])
	filter_glob: bpy.props.StringProperty(
		default=exts,
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"

	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "particle_planes"
	@tracking.report_error
	def execute(self, context):
		path = bpy.path.abspath(self.filepath)
		name = os.path.basename(path)
		name = os.path.splitext(name)[0]

		try:
			add_particle_planes_effect(
				context, self.filepath, self.location, self.frame)
		except FileNotFoundError as e:
			print("Particle effect file error:", e)
			self.report({'WARNING'}, "File not found")
			bpy.ops.mcprep.prompt_reset_spawners('INVOKE_DEFAULT')
			return {'CANCELLED'}

		context.scene.mcprep_particle_plane_file = self.filepath

		self.track_param = name
		return {'FINISHED'}


# Potential future features:

# class MCPREP_OT_break_block(bpy.types.Operator):
# Complete with adding the animation overlay (shader), as well as adding a
# particle plane effect on breakage based on the block broken.

# class MCPREP_OT_fall_impact(bpy.types.Operator):
# Impact effect from falling from distance, auto pick up textures from ground.

# class MCPREP_OT_auto_footfall_particle(bpy.types.Operator):
# To enumate particles that a player has when running, and picking up the
# material of the surface it is running on.
# This could possibly also include an "auto splash" feature, splashing
# really has two particle effects: bubbles, and water splashes.


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_effects_path_reset,
	MCPREP_OT_reload_effects,
	MCPREP_OT_global_effect,
	MCPREP_OT_instant_effect,
	MCPREP_OT_spawn_particle_planes,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
