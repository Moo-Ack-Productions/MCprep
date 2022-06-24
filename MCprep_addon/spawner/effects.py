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

import bmesh
from bpy_extras.io_utils import ImportHelper
import bpy

from .. import conf
from .. import util
from .. import tracking

from . import spawn_util

# -----------------------------------------------------------------------------
# Global enum values
# -----------------------------------------------------------------------------

# Enum values for effect_type for safe string comparisons.
GEO_AREA = "geo_area"
PARTICLE_AREA = "particle_area"
COLLECTION = "collection"
IMG_SEQ = "img_seq"


# -----------------------------------------------------------------------------
# Core effects types
# -----------------------------------------------------------------------------


def add_geonode_area_effect(context, effect):
	"""Create a persistent effect which is meant to emulate a wide-area effect.

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
		print("DIFF OF geo node groups:", diff)
		this_nodegroup = diff[0]
	else:
		this_nodegroup = existing_geonodes[0]

	mesh = bpy.data.meshes.new(effect.name + " empty mesh")
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


def add_area_particle_effect(context, effect, location):
	"""Create a persistent effect over wide area using traditional particles.

	Where geo nodes are not available (older blender versions) or if the user
	prefers to have more control of the particle system being created after.
	When created, it adds a plane over the area of the camera, with a
	determined density setting such over the given radius it emits a consistent
	amount per unit area. Ideally, the system could auto update the emission
	count even as this object is scaled.
	"""


def add_collection_effect(context, effect, location, frame):
	"""Spawn a pre-animated collection effect at a specific point and time.

	Import a new copy of a collection from the effects_collections.blend file.
	Each collection hsa some pre-animated settings. When the collection is
	imported, all animation, particle, or other time-dependent features are
	shifted by the indicated number of frames over. It is then placed as an
	expanded collection. No instancing because there's no savings.

	Could potentially offer to 'prebake' so that once its loaded, it auto bakes
	any particles the collection may be using.
	"""


def add_image_sequence_effect(context, effect, location, frame):
	"""Spawn a short-term sequence of individual images at a point in time."""

	# Could implement as an actual image sequence texture (lowest 'cost'),
	# or have it do import item on each frame, and then create empty instances
	# placed in time so it's spaced out as desired. This would also allow for
	# adding 'thicknes' to the effect if ever wanted, which is interesting.

	# Examples include: Sword swing, bubble popping. By default loaded from
	# the textures/particle folder, where each frame is already its own image.


def add_particle_planes_effect(context, image_path, location, frame):
	"""Spawn a short-term particle system at a specific point and time.

	This is the only effect type that does not get pre-loaded into a list. The
	user is prompted for an image, and this is then imported, chopped into a
	few smaller square pieces, and then this collection is used as a source for
	a particle system that emits some number of particles over a 1-3 frame
	period of time. Ideal for footfalls, impacts, etc.
	"""

	# Add object, use lower level functions to make it run faster.
	f_name = os.path.splitext(os.path.basename(image_path))[0]
	base_name = "{}_frame_{}".format(f_name, frame)

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

	apply_particle_settings(obj, frame, base_name, pcoll)


# -----------------------------------------------------------------------------
# Core effects supportive functions
# -----------------------------------------------------------------------------

def geo_update_params(context, effect, geo_mod):
	"""Update the paramters of the applied geonode effect.

	Loads fields to apply based on json file where necessary.
	"""

	base_file = os.path.splitext(os.path.basename(effect.filepath))[0]
	base_dir = os.path.dirname(effect.filepath)
	jpath = os.path.join(base_dir, base_file + ".json")
	geo_fields = {}
	if os.path.isfile(jpath):
		geo_fields = geo_fields_from_json(effect, jpath)
	else:
		conf.log("No json params path for geonode effects", vv_only=True)
		return

	# Determine if these special keywords exist.
	has_followkey = False
	for input_name in geo_fields.keys():
		if geo_fields[input_name] == "FOLLOW_OBJ":
			has_followkey = True
	conf.log("geonode has_followkey field? " + str(has_followkey), vv_only=True)

	# Create follow empty if required by the group.
	camera = context.scene.camera
	center_empty = None
	if has_followkey:
		center_empty = bpy.data.objects.new(
			name="{} origin".format(effect.name),
			object_data=None)
		util.obj_link_scene(center_empty)
		if camera:
			center_empty.parent = camera
			center_empty.location = (0, 0, -10)
		else:
			center_empty.location = util.get_cuser_location()

	# Cache mapping of names like "Weather Type" to "Input_1" internals.
	geo_inp_id = {}
	for inp in geo_mod.node_group.inputs:
		if inp.name in list(geo_fields):
			geo_inp_id[inp.name] = inp.identifier

	# Now update the final geo node inputs based gathered settings.
	for inp in geo_mod.node_group.inputs:
		if inp.name in list(geo_fields):
			value = geo_fields[inp.name]
			if value == "CAMERA_OBJ":
				conf.log("Set cam for geonode input", vv_only=True)
				geo_mod[geo_inp_id[inp.name]] = camera
			elif value == "FOLLOW_OBJ":
				if not center_empty:
					print(">> Center empty missing, not in preset in preset!")
				else:
					conf.log("Set follow for geonode input", vv_only=True)
					geo_mod[geo_inp_id[inp.name]] = center_empty
			else:
				conf.log("Set {} for geonode input".format(inp.name), vv_only=True)
				geo_mod[geo_inp_id[inp.name]] = value
		# TODO: check if any socket name in json specified not found in node.


def geo_fields_from_json(effect, jpath):
	"""Extract json values from a file for a given effect.

	Parse for a json structure with a hierarhcy of:

	geo node group name:
		sub effect name e.g. "rain":
			input setting name: value

	Special values for given keys (where key is the geonode UI name):
		CAMERA_OBJ: Tells MCprep to assign the active camera object to slot.
		FOLLOW_OBJ: Tells MCprep to assign a generated empty to this slot.
	"""
	conf.log("Loading geo fields form json: " + jpath)
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


def get_or_create_plane_mesh(mesh_name, uvs=[]):
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
	for v in verts:
		bm.verts.new(v)

	if not uvs:
		uvs = [[0, 0], [1, 0], [1, 1], [0, 1]]
	if len(uvs) != 4:
		raise Exception("Wrong number of coords for UVs: " + str(len(uvs)))

	face = bm.faces.new(bm.verts)
	face.normal_update()

	for i, loop in enumerate(face.loops):
		loop[uv_layer].uv = uvs[i]

	bm.to_mesh(mesh)
	bm.free()

	return mesh


def get_or_create_particle_meshes_coll(context, particle_name, img):
	"""Generate a selection of subsets of a given image for use in partucles.

	The goal is that instead of spawning entire, complete UVs of the texture,
	we spawn little subsets of the particles.

	Returns a collection or group depending on bpy version.
	"""
	# Check if it exists already, and if it has at least one object,
	# assume we'll just use those.
	particle_key = particle_name + "_particles"
	particle_coll = util.collections().get(particle_key)
	if particle_coll:
		# Check if any objects.
		if util.bv28() and len(particle_coll.objects) > 0:
			return particle_coll

	# Create the collection/group.
	if util.bv28():
		particle_view = util.get_or_create_viewlayer(context, particle_key)
		particle_view.exclude = True
	else:
		particle_group = bpy.data.groups.new(name=particle_key)

	# Get or create the material.
	if particle_name in bpy.data.materials:
		mat = bpy.data.materials.get(particle_name)
	else:
		bpy.ops.mcprep.load_material(filepath=img.filepath)
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
		print("Delete: ", del_index, keys[del_index])
		del uv_variants[keys[del_index]]

	print("all uv variants: ", list(uv_variants))
	for key in uv_variants:
		name = particle_name + "_particle_" + key
		print("Gen this UV: ", uv_variants[key])
		mesh = get_or_create_plane_mesh(name, uvs=uv_variants[key])
		obj = bpy.data.objects.new(name, mesh)
		obj.data.materials.append(mat)

		if util.bv28():
			util.move_to_collection(obj, particle_view.collection)
		else:
			particle_group.objects.link(obj)

	if util.bv28():
		return particle_view.collection
	else:
		return particle_group


def apply_particle_settings(obj, frame, base_name, pcoll):
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
	psystem.settings.normal_factor = -1.5
	psystem.settings.use_rotations = True
	psystem.settings.rotation_factor_random = 1
	psystem.settings.particle_size = 0.2
	psystem.settings.factor_random = 1

	if util.bv28():
		obj.show_instancer_for_render = False
		psystem.settings.render_type = 'COLLECTION'
		psystem.settings.instance_collection = pcoll
	else:
		psystem.settings.use_render_emitter = False
		psystem.settings.render_type = 'GROUP'
		psystem.settings.dupli_group = pcoll


# -----------------------------------------------------------------------------
# List UI load functions
# -----------------------------------------------------------------------------


def update_effects_path(self, context):
	"""List for UI effects callback ."""
	conf.log("Updating effects path", vv_only=True)
	update_effects_list(context)


def update_effects_list(context):
	"""Update the effects list."""
	mcprep_props = context.scene.mcprep_props
	mcprep_props.effects_list.clear()

	if conf.use_icons and conf.preview_collections["effects"]:
		try:
			bpy.utils.previews.remove(conf.preview_collections["effects"])
		except Exception as e:
			print(e)
			conf.log("MCPREP: Failed to remove icon set, effects")

	load_geonode_effect_list(context)
	load_area_particle_effects(context)
	load_collection_effects(context)
	load_image_sequence_effects(context)


def load_geonode_effect_list(context):
	"""Load effects defined by geonodes for wide area effects."""
	if bpy.app.version < (3, 0):  # Validate if should be 3.1
		print("Not loading geonode effects")
		# TODO: Test on 3.0 too in case it does work somehow.
		return

	mcprep_props = context.scene.mcprep_props
	path = context.scene.mcprep_effects_path
	path = os.path.join(path, "geonodes")

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

	conf.log("json pairs of blend files", vv_only=True)
	conf.log(json_files, vv_only=True)

	for bfile in blends:
		row_items = []
		using_json = False
		js_equiv = os.path.splitext(bfile)[0] + ".json"
		if js_equiv in json_files:
			conf.log("Loading json preset for geonode for " + bfile)
			# Read nodegroups to include from json presets file.
			jpath = os.path.splitext(bfile)[0] + ".json"
			with open(jpath) as jopen:
				jdata = json.load(jopen)
			row_items = jdata.keys()
			using_json = True
		else:
			conf.log("Loading nodegroups from blend for geonode effects: " + bfile)
			# Read nodegroup names from blend file directly.
			with bpy.data.libraries.load(bfile) as (data_from, _):
				row_items = list(data_from.node_groups)

		for itm in row_items:
			if spawn_util.SKIP_COLL in itm.lower():  # mcskip
				continue

			if using_json:
				# First key in index is nodegroup, save to subpath, but then
				# the present name (list of keys within) are the actual names
				for preset in jdata[itm]:
					conf.log("\tgeonode preset: " + preset, vv_only=True)
					effect = mcprep_props.effects_list.add()
					effect.name = preset  # This is the assign json preset name.
					effect.subpath = itm  # This is the node group name.
					effect.effect_type = GEO_AREA
					effect.filepath = bfile
					effect.index = len(mcprep_props.effects_list) - 1  # For icon index.

			else:
				# Using the nodegroup name itself as the key, no subpath
				effect = mcprep_props.effects_list.add()
				effect.name = itm
				effect.subpath = itm  # Always the nodegroup name.
				effect.effect_type = GEO_AREA
				effect.filepath = bfile
				effect.index = len(mcprep_props.effects_list) - 1  # For icon index.


def load_area_particle_effects(context):
	"""Load effects defined by wide area particle effects (non geo nodes).

	This is a fallback for older versions of blender which don't have geonodes,
	or where geonodes aren't working well or someone just wants to use
	particles.
	"""
	mcprep_props = context.scene.mcprep_props
	path = context.scene.mcprep_effects_path
	path = os.path.join(path, "particle")

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


def load_collection_effects(context):
	"""Load effects defined by collections saved to an effects blend file."""
	mcprep_props = context.scene.mcprep_props
	path = context.scene.mcprep_effects_path
	path = os.path.join(path, "collection")

	# Find all files with geonodes.
	blends = [
		os.path.join(path, blend) for blend in os.listdir(path)
		if os.path.isfile(os.path.join(path, blend))
		and blend.lower().endswith("blend")
	]

	for bfile in blends:
		with bpy.data.libraries.load(bfile) as (data_from, _):
			collections = list(data_from.collections)

		for itm in collections:
			effect = mcprep_props.effects_list.add()
			effect.effect_type = "collection"
			effect.name = itm
			effect.filepath = bfile
			effect.index = len(mcprep_props.effects_list) - 1  # For icon index.


def load_image_sequence_effects(context):
	"""Load effects from the particles folder that should be animated."""
	mcprep_props = context.scene.mcprep_props

	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	extensions = [".png", ".jpg", ".jpeg"]

	# Check levels
	lvl_0 = os.path.join(resource_folder, "particle")
	lvl_1 = os.path.join(resource_folder, "textures", "particle")
	lvl_2 = os.path.join(resource_folder, "minecraft", "textures", "particle")
	lvl_3 = os.path.join(resource_folder, "assets", "minecraft", "textures", "particle")

	if not os.path.isdir(resource_folder):
		conf.log("Error, resource folder does not exist")
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
		os.path.splitext(fname)[0].split("_")[0]
		for fname in rfiles
		if os.path.isfile(os.path.join(resource_folder, fname))
		and os.path.splitext(fname)[-1].lower() in extensions
	]
	effect_files = list(set(effect_files))

	for itm in effect_files:
		effect = mcprep_props.effects_list.add()
		effect.effect_type = "img_seq"
		effect.name = itm.capitalize()
		effect.description = "Instance the {} particle aniamted sequence".format(
			itm)

		# Note: the item being added is NOT a full filepath, but the prefix.
		effect.filepath = os.path.join(resource_folder, itm)

		effect.index = len(mcprep_props.effects_list) - 1  # For icon index.

		# Try to load a middle frame as the icon.
		if not conf.use_icons or conf.preview_collections["effects"] == "":
			continue
		effect_files = [
			os.path.join(resource_folder, fname)
			for fname in rfiles
			if os.path.isfile(os.path.join(resource_folder, fname))
			and fname.startswith(itm)
			and os.path.splitext(fname)[-1].lower() in extensions
		]
		if effect_files:
			# 0 if 1 item, otherwise greater side of median.
			e_index = int(len(effect_files) / 2)
			conf.preview_collections["effects"].load(
				"effects-{}".format(effect.index), effect_files[e_index], 'IMAGE')


# -----------------------------------------------------------------------------
# Support functions
# -----------------------------------------------------------------------------


def create_auto_footfall_particle_plane():
	"""Create particle effects at every point in time the object hits another.

	This would be an advanced feature, using particle plans as the base. It
	should be the resultant instances of particle planes into its own single
	collection which can be regenerated if the animation of the object/rig is
	ever updated. The detector should be a footfall empty that ends up being
	parented via copy-location constraint (with an offset) based on the
	selected bone or mesh.

	When processing, it should know to hide the objects in the same parent
	structure (e.g. legs, shoe meshes, armature) so it only does ray casting
	against other items in the scene. Should be based on what is visible so
	the artist has more control of what it tries to detect.
	"""

	# TODO: Implement this after the core particle plane effect exists.


# -----------------------------------------------------------------------------
# Operator classes
# -----------------------------------------------------------------------------


class MCPREP_OT_reload_effects(bpy.types.Operator):
	"""Reload effects spawner, use after changes to/new effects files"""
	bl_idname = "mcprep.reload_effects"
	bl_label = "Reload effects"

	@tracking.report_error
	def execute(self, context):
		update_effects_list(context)
		return {'FINISHED'}


class MCPREP_OT_global_effect(bpy.types.Operator):
	"""Spawn an global effect such as weather particles"""
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
			else:
				display_type = "particle system effect"
			elist.append((
				str(effect.index),
				effect.name,
				"Add {} {} from {}".format(
					effect.name,
					display_type,
					os.path.basename(effect.filepath))
			))
		return elist

	effect_id = bpy.props.EnumProperty(items=effects_enum, name="Effect")
	skipUsage = bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	track_function = "effect_global"
	@tracking.report_error
	def execute(self, context):
		mcprep_props = context.scene.mcprep_props
		effect = mcprep_props.effects_list[int(self.effect_id)]
		if effect.effect_type == GEO_AREA:
			add_geonode_area_effect(context, effect)
			self.report(
				{"INFO"},
				"Added geo nodes, edit modifier for further control")
		elif effect.effect_type == PARTICLE_AREA:
			cam = context.scene.camera
			if cam:
				location = context.scene.camera.location
			else:
				location = util.get_cuser_location(context)
			add_area_particle_effect(context, effect, location)
			self.report({"ERROR"}, "Not yet implemented")
		self.track_param = effect.name
		return {'FINISHED'}


class MCPREP_OT_instant_effect(bpy.types.Operator):
	"""Spawn an effect that takes place at specific time and position"""
	bl_idname = "mcprep.spawn_instant_effect"
	bl_label = "Instant effect"
	bl_options = {'REGISTER', 'UNDO'}

	def effects_enum(self, context):
		"""Identifies eligible instant effects to include in the dropdown."""
		mcprep_props = context.scene.mcprep_props
		elist = []
		for effect in mcprep_props.effects_list:
			if effect.effect_type not in ('collection', 'img_seq'):
				continue
			if effect.effect_type == COLLECTION:
				display_type = "preanimated collection effect"
			else:
				display_type = "image sequence effect"
			elist.append((
				str(effect.index),
				effect.name,
				"Add {} {} from {}".format(
					effect.name,
					display_type,
					os.path.basename(effect.filepath))
			))
		return elist

	effect_id = bpy.props.EnumProperty(items=effects_enum, name="Effect")
	location = bpy.props.FloatVectorProperty(default=(0, 0, 0), name="Location")
	frame = bpy.props.IntProperty(default=0, name="Frame")
	skipUsage = bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	@classmethod
	def poll(cls, context):
		return context.mode == 'OBJECT'

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	track_function = "effect_instant"
	@tracking.report_error
	def execute(self, context):
		mcprep_props = context.scene.mcprep_props
		effect = mcprep_props.effects_list[int(self.effect_id)]
		if effect.effect_type == "collection":
			add_collection_effect(
				context, effect, self.location, self.frame)
			self.report({"ERROR"}, "Not yet implemented")
		elif effect.effect_type == "img_seq":
			add_image_sequence_effect(
				context, effect, self.location, self.frame)
			self.report({"ERROR"}, "Not yet implemented")
		self.track_param = effect.name
		return {'CANCELLED'}


class MCPREP_OT_spawn_particle_planes(bpy.types.Operator, ImportHelper):
	"""Create a particle system from a selected image input"""
	bl_idname = "mcprep.spawn_particle_planes"
	bl_label = "Spawn Particle Planes"
	bl_options = {'REGISTER', 'UNDO'}

	location = bpy.props.FloatVectorProperty(
		default=(0, 0, 0), name="Location")
	frame = bpy.props.IntProperty(default=0, name="Frame")

	# Importer helper
	filter_glob = bpy.props.StringProperty(
		default="*.png;*.jpg;*.jpeg;*.tiff",
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"

	skipUsage = bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "particle_planes"
	@tracking.report_error
	def execute(self, context):
		path = bpy.path.abspath(self.filepath)
		name = os.path.basename(path)
		name = os.path.splitext(name)[0]

		add_particle_planes_effect(
			context, self.filepath, self.location, self.frame)

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
	MCPREP_OT_reload_effects,
	MCPREP_OT_global_effect,
	MCPREP_OT_instant_effect,
	MCPREP_OT_spawn_particle_planes,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
