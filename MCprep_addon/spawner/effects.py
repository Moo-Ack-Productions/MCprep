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
from .. import util
from .. import tracking

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
		if ndg.type == "GEOMETRY" and ndg.name == effect.name]

	# Load this geo node if it doesn't already exist.
	if not existing_geonodes:
		with bpy.data.libraries.load(effect.filepath) as (data_from, data_to):

			for this_group in data_from.node_groups:
				if this_group != effect.name:
					continue
				data_to.node_groups.append(this_group)
				break
		# Post
		post_geonodes = [
			ndg for ndg in bpy.data.node_groups
			if ndg.type == "GEOMETRY" and ndg.name == effect.name]
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

	# TODO: Conditionally create an empty, only if 'follow' input exists.
	center_empty = bpy.data.objects.new(
		name="{} origin".format(effect.name),
		object_data=None)
	util.obj_link_scene(center_empty)
	camera = context.scene.camera
	if camera:
		center_empty.parent = camera
		center_empty.location = (0, 0, -10)
	else:
		center_empty.location = util.get_cuser_location()

	# Update geo node inputs based on socket name.
	geo_fields = {
		"Camera Rotation": None,
		"Weather Folower": None,
		"Weather Grid Size x": None,
		"Weather Grid Size y": None
	}
	for inp in geo_mod.node_group.inputs:
		if inp.name in list(geo_fields):
			geo_fields[inp.name] = inp.identifier

	if geo_fields["Camera Rotation"] is None:
		print("Failed to update geonode camera input")
	else:
		geo_mod[geo_fields["Camera Rotation"]] = camera

	if geo_fields["Weather Folower"] is None:
		print("Failed to update geonode follow input")
	else:
		geo_mod[geo_fields["Weather Folower"]] = center_empty

	if geo_fields["Weather Grid Size x"] is None:
		print("Failed to update geonode follow input")
	else:
		geo_mod[geo_fields["Weather Grid Size x"]] = 33

	if geo_fields["Weather Grid Size y"] is None:
		print("Failed to update geonode follow input")
	else:
		geo_mod[geo_fields["Weather Grid Size y"]] = 33


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


# -----------------------------------------------------------------------------
# Load functions
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
		and blend.lower().endswith("blend")
	]

	for bfile in blends:
		with bpy.data.libraries.load(bfile) as (data_from, _):
			node_groups = list(data_from.node_groups)

		for itm in node_groups:
			effect = mcprep_props.effects_list.add()
			effect.effect_type = GEO_AREA
			effect.name = itm
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


class MCPREP_OT_spawn_particle_planes(bpy.types.Operator):
	"""Create a particle system from a selected image input"""
	bl_idname = "mcprep.spawn_particle_planes"
	bl_label = "Spawn Particle Planes"
	bl_options = {'REGISTER', 'UNDO'}

	filepath = bpy.props.StringProperty(
		default="",
		subtype="FILE_PATH",
		options={'HIDDEN', 'SKIP_SAVE'})
	location = bpy.props.FloatVectorProperty(
		default=(0, 0, 0), name="Location")
	frame = bpy.props.IntProperty(default=0, name="Frame")
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

		self.report({"ERROR"}, "Not yet implemented")
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
