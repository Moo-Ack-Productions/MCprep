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
import re

import bpy

from .. import conf
from .. import util
from .. import tracking
from . import mobs
from . import effects

# Top-level names used for inclusion or exclusions when filtering through
# collections in blend files for spawners: mobs, meshswap, and entities.
INCLUDE_COLL = "mcprep"
SKIP_COLL = "mcskip"  # Used for geometry and particle skips too.
SKIP_COLL_LEGACY = "noimport"  # Supporting older MCprep Meshswap lib.


# -----------------------------------------------------------------------------
# Reusable functions for spawners
# -----------------------------------------------------------------------------


def filter_collections(data_from):
	"""Generalized way to prefilter collections in a blend file.

	Enforces the awareness of inclusion and exlcusion collection names, and
	some hard coded cases to always ignore.

	Args:
		data_from: The `from` part a bpy file reader scope.
	"""
	if hasattr(data_from, "groups"):  # blender 2.7
		get_attr = "groups"
	else:  # 2.8
		get_attr = "collections"

	coll_list = [name for name in getattr(data_from, get_attr)]

	all_names = []
	mcprep_names = []

	# Do a check to see if there are any collections that explicitly
	# do include the text "MCprep" as a way of filtering which
	# collections to include. Additionally, skip any rigs containing
	# the special text for skipping.
	any_mcprep = False

	for name in coll_list:
		# special cases, skip some groups
		if util.nameGeneralize(name).lower() == "Rigidbodyworld".lower():
			continue
		if name.lower().startswith("collection"):
			continue  # will drop e.g. "Collection 1" from blender 2.7x

		short = name.replace(" ", "").replace("-", "").replace("_", "")
		if SKIP_COLL in short.lower():
			conf.log("Skipping collection: " + name)
			continue
		if SKIP_COLL_LEGACY in short.lower():
			conf.log("Skipping legacy collection: " + name)
			continue
		elif INCLUDE_COLL in name.lower():
			any_mcprep = True
			mcprep_names.append(name)
		all_names.append(name)

	if any_mcprep:
		conf.log("Filtered from {} down to {} MCprep collections".format(
			len(all_names), len(mcprep_names)))
		all_names = mcprep_names
	return all_names


def check_blend_eligible(this_file, all_files):
	"""Returns true if the path blend file is ok for this blender version.

	Created to better support older blender versions without having to
	compeltely remake new rig contirbutions from scratch. See for more details:
	https://github.com/TheDuckCow/MCprep/issues/317

	If the "pre#.#.#" suffix is found in any similar prefix named blend files,
	evaluate whether the target file itself is eligible. If pre3.0.0 is found
	in path, then this function returns False if the current blender version is
	3.0 to force loading the non pre3.0.0 version instead, and if pre3.0.0 is
	not in the path variable but pre#.#.# is found in another file, then it
	returns true. If no pre#.#.# found in any files of the common base, would
	always return True.
	"""
	basename = os.path.splitext(this_file)[0]

	# Regex code to any matches of pre#.#.# at very end of name.
	# (pre) for exact match,
	# [0-9]+ to match any 1+ numbers
	# (\.[0-9]+) for any repeat number of .#
	# +$ to ensure it's an ending group.
	code = r'(?i)(pre)[0-9]+(\.[0-9]+)+$'
	find_suffix = re.compile(code)

	def tuple_from_match(match):
		prestr = match.group(0)  # At most one group given +$ ending condition.
		vstr = prestr[3:]  # Chop off "pre".
		tuple_ver = tuple([int(n) for n in vstr.split(".")])
		return tuple_ver

	matches = find_suffix.search(basename)
	if matches:
		tuple_ver = tuple_from_match(matches)
		res = util.min_bv(tuple_ver)
		# If the suffix = 3.0 and we are BELOW 3.0, return True (use this file)
		return not res

	# Remaining case: no suffix found in this target, but see if any other
	# files have the same base and *do* have a suffix indicator.
	for afile in all_files:
		if not afile.startswith(basename):
			continue
		if afile == this_file:
			continue  # Already checked above.

		base_afile = os.path.splitext(afile)[0]
		matches = find_suffix.search(base_afile)
		if matches:
			tuple_ver = tuple_from_match(matches)
			res = util.min_bv(tuple_ver)
			# If the suffix = 3.0 in `afile` file, and current blender is
			# below 3, then `afile` is the file that should be loaded, and the
			# current file `this_file` is to be skipped.
			return res

	# If no matches (the most common case), then this file is eligible.
	return True


def attemptScriptLoad(path):
	"""Search for script that matches name of the blend file"""

	# TODO: should also look into the blend if appropriate
	# if the script already exists in blender, assume can reuse this
	if not path[-5:] == "blend":
		return
	path = path[:-5] + "py"

	if os.path.basename(path) in [txt.name for txt in bpy.data.texts]:
		conf.log("Script {} already imported, not importing a new one".format(
			os.path.basename(path)))
		return

	if not os.path.isfile(path):
		return  # no script found
	conf.log("Script found, loading and running it")
	text = bpy.data.texts.load(filepath=path, internal=True)
	try:
		ctx = bpy.context.copy()
		ctx['edit_text'] = text
	except Exception as err:
		print("MCprep: Error trying to create context to run script in:")
		print(str(err))
	try:
		bpy.ops.text.run_script(ctx)
		ctx.use_fake_user = True
		ctx.use_module = True
	except:
		conf.log("Failed to run the script, not registering")
		return
	conf.log("Ran the script")
	text.use_module = True


def fix_armature_target(self, context, new_objs, src_coll):
	"""Addresses 2.8 bug where make real might not update armature source"""

	src_armas = [
		arma for arma in src_coll.objects if arma.type == 'ARMATURE']
	new_armas = [
		arma for arma in new_objs if arma.type == 'ARMATURE']
	src_armas_basnames = [util.nameGeneralize(obj.name) for obj in src_armas]
	new_armas_basnames = [util.nameGeneralize(obj.name) for obj in new_armas]
	if not new_armas:
		return  # Nothing we can do to fix if new arma not existing.
	for obj in new_objs:
		for mod in obj.modifiers:
			# two scenarios:
			# if 2.7: armature modifier already changed, copy over anim data
			# if 2.8: swap modifier armature and also copy over anim data
			if mod.type != 'ARMATURE':
				continue
			# if not (mod.object in new_objs or mod.object in src_armas):
			#       continue # all good (from mod arma target perspective)
			if mod.object not in src_armas and mod.object not in new_armas:
				continue  # Unknown source, no way to know how to fix this.
			target_base = util.nameGeneralize(mod.object.name)
			if target_base not in new_armas_basnames:
				continue  # Shouldn't occur, but skip if it does.

			new_target = new_armas[new_armas_basnames.index(target_base)]
			old_target = src_armas[src_armas_basnames.index(target_base)]

			# for blender 2.8, bug is that target is still old_target
			# but for blender 2.7, the mod target will already have changed
			if old_target.animation_data:
				new_target.animation_data_create()
				new_target.animation_data.action = old_target.animation_data.action
				conf.log(
					"Updated animation of armature for instance of " + src_coll.name)

			if mod.object in new_objs:
				continue  # Was already the new object target for modifier.
			mod.object = new_target
			conf.log(
				"Updated target of armature for instance of " + src_coll.name)


def prep_collection(self, context, name, pre_groups):
	"""Prep the imported collection, ran only if newly imported (not cached)"""

	# Group method first, move append to according layer
	for ob in util.get_objects_conext(context):
		util.select_set(ob, False)

	layers = [False] * 20
	if not hasattr(context.scene, "layers"):
		# TODO: here add all subcollections to an MCprepLib collection.
		pass
	elif self.append_layer == 0:
		layers = context.scene.layers
	else:
		layers[self.append_layer - 1] = True
	objlist = []
	group = None
	for coll in util.collections():
		if coll in pre_groups:
			continue
		if coll.name.lower().startswith("collection"):
			continue  # Will drop e.g. "Collection 1" from blender 2.7x.
		for ob in coll.objects:
			if ob.name in context.scene.objects:
				# context.scene.objects.unlink(ob)
				objlist.append(ob)
		if util.nameGeneralize(coll.name) == util.nameGeneralize(name):
			group = coll

	if group is None:
		return None

	if self.prep_materials is True:
		for ob in objlist:
			util.select_set(ob, True)
		try:
			bpy.ops.mcprep.prep_materials(
				autoFindMissingTextures=False,
				improveUiSettings=False,
				skipUsage=True)  # if cycles
		except:
			print("Could not prep materials")
		for ob in util.get_objects_conext(context):
			util.select_set(ob, False)

	if hasattr(context.scene, "layers"):  # 2.7 only
		for obj in objlist:
			obj.layers = layers
	return group


def get_rig_from_objects(objects):
	"""From a list of objects, return the the primary rig (best guess)"""
	prox_obj = None
	for obj in objects:
		if obj.type != 'ARMATURE':
			continue
		elif obj.name.lower().endswith('.arma'):
			prox_obj = obj
			break
		elif not prox_obj:
			prox_obj = obj
		elif "rig" in obj.name.lower() and "rig" not in prox_obj.name.lower():
			prox_obj = obj
	return prox_obj


def offset_root_bone(context, armature):
	"""Used to offset bone to world location (cursor)"""
	conf.log("Attempting offset root")
	set_bone = False
	lower_bones = [bone.name.lower() for bone in armature.pose.bones]
	lower_name = None
	for name in ["main", "root", "base", "master"]:
		if name in lower_bones:
			lower_name = name
			break
	if not lower_name:
		return False

	for bone in armature.pose.bones:
		if bone.name.lower() != lower_name:
			continue
		bone.location = util.matmul(
			bone.bone.matrix.inverted(),
			util.get_cuser_location(context),
			armature.matrix_world.inverted()
		)

		set_bone = True
		break
	return set_bone


def load_linked(self, context, path, name):
	"""Process for loading mob or entity via linked library.

	Used by mob spawner when chosing to link instead of append.
	"""

	path = bpy.path.abspath(path)
	act = None
	if hasattr(bpy.data, "groups"):
		util.bAppendLink(path + '/Group', name, True)
		act = context.object  # assumption of object after linking, 2.7 only
	elif hasattr(bpy.data, "collections"):
		util.bAppendLink(path + '/Collection', name, True)
		if len(context.selected_objects) > 0:
			act = context.selected_objects[0]  # better for 2.8
		else:
			print("Error: Should have had at least one object selected.")

	# util.bAppendLink(os.path.join(path, g_or_c), name, True)
	# proxy any and all armatures
	# here should do all that jazz with hacking by copying files, checking
	# nth number probably consists of checking currently linked libraries,
	# checking if which have already been linked into existing rigs.
	# if util.bv28() and context.selected_objects:
	# 	act = context.selected_objects[0] # better for 2.8
	# elif context.object:
	# 	act = context.object  # assumption of object after linking
	conf.log("Identified new obj as: {}".format(
		act), vv_only=True)

	if not act:
		self.report({'ERROR'}, "Could not grab linked in object if any.")
		return
	if self.relocation == "Origin":
		act.location = (0, 0, 0)

	# find the best armature to proxy, if any
	prox_obj = None
	if not act.type == "EMPTY":
		self.report({'WARNING'}, "Linked object should be type: empty")
		return
	elif not util.instance_collection(act):
		self.report({'WARNING'}, "Linked object has no dupligroup")
		return
	else:
		prox_obj = get_rig_from_objects(
			util.instance_collection(act).objects)
	if not prox_obj:
		self.report({'WARNING'}, "No object found to proxy")
		return

	if "proxy_make" in dir(bpy.ops.object):
		# The pre 3.0 way.
		# Can't check using hasattr, as the leftover class is still there
		# even though the operator no longer is callable.
		bpy.ops.object.proxy_make(object=prox_obj.name)
	elif hasattr(bpy.ops.object, "make_override_library"):
		# Was in some 2.9x versions, but prefer proxy_make for consistency.
		pre_colls = list(bpy.data.collections)
		bpy.ops.object.make_override_library()  # Must be active.
		post_colls = list(bpy.data.collections)
		new_colls = list(set(post_colls) - set(pre_colls))
		if len(new_colls) == 1:
			act = get_rig_from_objects(new_colls[0].all_objects)
			util.set_active_object(context, act)
		else:
			print("Error: failed to get new override collection")
			raise Exception("Failed to get override collection")

	coll = util.instance_collection(act)
	if hasattr(coll, "dupli_offset"):
		gl = coll.dupli_offset
	elif hasattr(act, "instance_offset"):
		gl = coll.instance_offset
	else:
		# fallback to ensure gl defined as showed up in user errors,
		# but not clear how this happens
		print("WARNING: Assigned fallback gl of (0,0,0)")
		gl = (0, 0, 0)
	# cl = util.get_cuser_location(context)

	if self.relocation == "Offset":
		# do the offset stuff, set active etc
		bpy.ops.transform.translate(value=(-gl[0], -gl[1], -gl[2]))

	try:
		bpy.ops.object.mode_set(mode='POSE')
		act = bpy.context.object
	except:
		self.report({'WARNING'}, "Could not enter pose mode on linked character")
		return
	if self.clearPose:
		bpy.ops.pose.select_all(action='SELECT')
		bpy.ops.pose.rot_clear()
		bpy.ops.pose.scale_clear()
		bpy.ops.pose.loc_clear()
	if self.relocation == "Offset":
		set_bone = offset_root_bone(context, act)
		if not set_bone:
			print(
				"MCprep mob spawning works better when the root bone's name is 'MAIN'")
			self.report(
				{'INFO'}, "This addon works better when the root bone's name is 'MAIN'")


def load_append(self, context, path, name):
	"""Append an entire collection/group into this blend file and fix armature.

	Used for both mob spawning and entity spawning with appropriate handling
	of rig objects. Not used by meshswap.
	"""
	if path == '//':
		# This means the group HAS already been appended..
		# Could try to recopy thsoe elements, or try re-appending with
		# renaming of the original group
		self.report({'ERROR'}, "Group name already exists in local file")
		conf.log("Group already appended/is here")
		return

	path = bpy.path.abspath(path)
	# capture state before, technically also copy
	sel = bpy.context.selected_objects
	for ob in util.get_objects_conext(context):
		util.select_set(ob, False)
	# consider taking pre-exisitng group names and giving them a temp name
	# to name back at the end

	if hasattr(bpy.data, "groups"):
		subpath = 'Group'
	elif hasattr(bpy.data, "collections"):
		subpath = 'Collection'
	else:
		raise Exception("No Group or Collection bpy API endpoint")

	conf.log(os.path.join(path, subpath) + ', ' + name)
	pregroups = list(util.collections())
	util.bAppendLink(os.path.join(path, subpath), name, False)
	postgroups = list(util.collections())

	g1 = None
	new_groups = list(set(postgroups) - set(pregroups))
	if not new_groups and name in util.collections():
		# this is more likely to fail but serves as a fallback
		conf.log("Mob spawn: Had to go to fallback group name grab")
		grp_added = util.collections()[name]
	elif not new_groups:
		conf.log("Warning, could not detect imported group")
		self.report({'WARNING'}, "Could not detect imported group")
		return
	else:
		grp_added = new_groups[0]  # assume first

	conf.log("Identified object {} with group {} as just imported".format(
		g1, grp_added), vv_only=True)

	# if rig not centered in original file, assume its group is
	if hasattr(grp_added, "dupli_offset"):  # 2.7
		gl = grp_added.dupli_offset
	elif hasattr(grp_added, "instance_offset"):  # 2.8
		gl = grp_added.instance_offset
	else:
		conf.log("Warning, could not set offset for group; null type?")
		gl = (0, 0, 0)
	cl = util.get_cuser_location(context)

	# For some reason, adding group objects on its own doesn't work
	all_objects = context.selected_objects
	addedObjs = [ob for ob in grp_added.objects]
	for ob in all_objects:
		if ob not in addedObjs:
			conf.log("This obj not in group: " + ob.name)
			# removes things like random bone shapes pulled in,
			# without deleting them, just unlinking them from the scene
			util.obj_unlink_remove(ob, False, context)

	if not util.bv28():
		grp_added.name = "reload-blend-to-remove-this-empty-group"
		for obj in grp_added.objects:
			grp_added.objects.unlink(obj)
			util.select_set(obj, True)
		grp_added.user_clear()
	else:
		for obj in grp_added.objects:
			if obj not in context.view_layer.objects[:]:
				continue
			util.select_set(obj, True)

	# try:
	# 	util.collections().remove(grp_added)
	# 	This can cause redo last issues
	# except:
	# 	pass
	rig_obj = get_rig_from_objects(addedObjs)
	if not rig_obj:
		conf.log("Could not get rig object")
		self.report({'WARNING'}, "No armatures found!")
	else:
		conf.log("Using object as primary rig: " + rig_obj.name)
		try:
			util.set_active_object(context, rig_obj)
		except RuntimeError:
			conf.log("Failed to set {} as active".format(rig_obj))
			rig_obj = None

	if rig_obj and self.clearPose or rig_obj and self.relocation == "Offset":
		if self.relocation == "Offset":
			bpy.ops.transform.translate(value=(-gl[0], -gl[1], -gl[2]))
		try:
			bpy.ops.object.mode_set(mode='POSE')
		except Exception as e:
			self.report({'ERROR'}, "Failed to enter pose mode: " + str(e))
			print("Failed to enter pose mode, see logs")
			print("Exception: ", str(e))
			print(bpy.context.object)
			print(rig_obj)
			print("Mode: ", context.mode)
			print("-- end error context printout --")

		posemode = context.mode == 'POSE'

		if self.clearPose:
			if rig_obj.animation_data:
				rig_obj.animation_data.action = None
			# transition to clear out pose this way
			# for b in ob.pose.bones:
			# old way, with mode set
			if posemode:
				bpy.ops.pose.select_all(action='SELECT')
				bpy.ops.pose.rot_clear()
				bpy.ops.pose.scale_clear()
				bpy.ops.pose.loc_clear()

		if self.relocation == "Offset" and posemode:
			set_bone = offset_root_bone(context, rig_obj)
			if not set_bone:
				conf.log(
					"This addon works better when the root bone's name is 'MAIN'")
				self.report(
					{'INFO'},
					"Works better if armature has a root bone named 'MAIN' or 'ROOT'")

	# now do the extra options, e.g. the object-level offsets
	if context.mode != 'OBJECT':
		bpy.ops.object.mode_set(mode='OBJECT')
	if self.relocation == "Origin":
		bpy.ops.transform.translate(value=(-gl[0], -gl[1], -gl[2]))
	elif self.relocation == "Cursor":
		bpy.ops.transform.translate(value=(
			cl[0] - gl[0],
			cl[1] - gl[1],
			cl[2] - gl[2]))
	# add the original selection back
	for objs in sel:
		util.select_set(objs, True)

# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------


class MCPREP_OT_reload_spawners(bpy.types.Operator):
	"""Relaod meshswapping and spawning lists"""
	bl_idname = "mcprep.reload_spawners"
	bl_label = "Reload meshswap and mob spawners"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		_ = util.load_mcprep_json()  # For cases when to prep/make real.
		bpy.ops.mcprep.reload_meshswap()
		bpy.ops.mcprep.reload_mobs()
		bpy.ops.mcprep.reload_items()
		bpy.ops.mcprep.reload_effects()
		bpy.ops.mcprep.reload_entities()
		bpy.ops.mcprep.reload_models()

		# to prevent re-drawing "load spawners!" if any one of the above
		# loaded nothing for any reason.
		conf.loaded_all_spawners = True

		return {'FINISHED'}


class MCPREP_OT_spawn_path_reset(bpy.types.Operator):
	"""Reset the spawn path to the default in addon preferences panel"""
	bl_idname = "mcprep.spawn_path_reset"
	bl_label = "Reset spawn path"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_mob_path = addon_prefs.mob_path
		mobs.update_rig_list(context)
		return {'FINISHED'}


# -----------------------------------------------------------------------------
# UI list related
# -----------------------------------------------------------------------------


class MCPREP_UL_mob(bpy.types.UIList):
	"""For mob asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "mob-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not conf.use_icons:
				layout.label(text=set.name)
			elif conf.use_icons and icon in conf.preview_collections["mobs"]:
				layout.label(
					text=set.name,
					icon_value=conf.preview_collections["mobs"][icon].icon_id)
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["mobs"]:
				layout.label(
					text="",
					icon_value=conf.preview_collections["mobs"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class MCPREP_UL_meshswap(bpy.types.UIList):
	"""For meshswap asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			layout.label(text=set.name)
		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='QUESTION')


class MCPREP_UL_entity(bpy.types.UIList):
	"""For entity asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			layout.label(text=set.name)
		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='QUESTION')


class MCPREP_UL_model(bpy.types.UIList):
	"""For model asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			layout.label(text=set.name)
		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label(text="", icon='QUESTION')


class MCPREP_UL_item(bpy.types.UIList):
	"""For item asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "item-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not conf.use_icons:
				layout.label(text=set.name)
			elif conf.use_icons and icon in conf.preview_collections["items"]:
				layout.label(
					text=set.name,
					icon_value=conf.preview_collections["items"][icon].icon_id)
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["items"]:
				layout.label(
					text="",
					icon_value=conf.preview_collections["items"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class MCPREP_UL_effects(bpy.types.UIList):
	"""For effects asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "effects-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:

			# Add icons based on the type of effect.
			if set.effect_type == effects.GEO_AREA:
				layout.label(text=set.name, icon="NODETREE")
			elif set.effect_type == effects.PARTICLE_AREA:
				layout.label(text=set.name, icon="PARTICLES")
			elif set.effect_type == effects.COLLECTION:
				layout.label(text=set.name, icon="OUTLINER_COLLECTION")
			elif set.effect_type == effects.IMG_SEQ:
				if conf.use_icons and icon in conf.preview_collections["effects"]:
					layout.label(
						text=set.name,
						icon_value=conf.preview_collections["effects"][icon].icon_id)
				else:
					layout.label(text=set.name, icon="RENDER_RESULT")
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["effects"]:
				layout.label(
					text="",
					icon_value=conf.preview_collections["effects"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class MCPREP_UL_material(bpy.types.UIList):
	"""For material library UIList drawing"""
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		icon = "material-{}".format(set.index)
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			if not conf.use_icons:
				layout.label(text=set.name)
			elif conf.use_icons and icon in conf.preview_collections["materials"]:
				layout.label(
					text=set.name,
					icon_value=conf.preview_collections["materials"][icon].icon_id)
			else:
				layout.label(text=set.name, icon="BLANK1")

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			if conf.use_icons and icon in conf.preview_collections["materials"]:
				layout.label(
					text="",
					icon_value=conf.preview_collections["materials"][icon].icon_id)
			else:
				layout.label(text="", icon='QUESTION')


class ListMobAssetsAll(bpy.types.PropertyGroup):
	"""For listing hidden group of all mobs, regardless of category"""
	description = bpy.props.StringProperty()
	category = bpy.props.StringProperty()
	mcmob_type = bpy.props.StringProperty()
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


class ListMobAssets(bpy.types.PropertyGroup):
	"""For UI drawing of mob assets and holding data"""
	description = bpy.props.StringProperty()
	category = bpy.props.StringProperty()  # category it belongs to
	mcmob_type = bpy.props.StringProperty()
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


class ListMeshswapAssets(bpy.types.PropertyGroup):
	"""For UI drawing of meshswap assets and holding data"""
	block = bpy.props.StringProperty()  # block name only like "fire"
	method = bpy.props.EnumProperty(
		name="Import method",
		# Collection intentionally first to be default for operator calls.
		items=[
			("collection", "Collection/group asset", "Collection/group asset"),
			("object", "Object asset", "Object asset"),
		]
	)
	description = bpy.props.StringProperty()


class ListEntityAssets(bpy.types.PropertyGroup):
	"""For UI drawing of meshswap assets and holding data"""
	entity = bpy.props.StringProperty()  # virtual enum, Group/name
	description = bpy.props.StringProperty()


class ListItemAssets(bpy.types.PropertyGroup):
	"""For UI drawing of item assets and holding data"""
	# inherited: name
	description = bpy.props.StringProperty()
	path = bpy.props.StringProperty(subtype='FILE_PATH')
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


class ListModelAssets(bpy.types.PropertyGroup):
	"""For UI drawing of mc model assets and holding data"""
	filepath = bpy.props.StringProperty(subtype="FILE_PATH")
	description = bpy.props.StringProperty()
	# index = bpy.props.IntProperty(min=0, default=0)  # icon pulled by name.


class ListEffectsAssets(bpy.types.PropertyGroup):
	"""For UI drawing for different kinds of effects"""
	# inherited: name
	filepath = bpy.props.StringProperty(subtype="FILE_PATH")
	subpath = bpy.props.StringProperty(
		description="Collection/particle/nodegroup within this file",
		default="")
	description = bpy.props.StringProperty()
	effect_type = bpy.props.EnumProperty(
		name="Effect type",
		items=(
			(effects.GEO_AREA, 'Geonode area', 'Instance wide-area geonodes effect'),
			(effects.PARTICLE_AREA, 'Particle area', 'Instance wide-area particle effect'),
			(effects.COLLECTION, 'Collection effect', 'Instance pre-animated collection'),
			(effects.IMG_SEQ, 'Image sequence', 'Instance an animated image sequence effect'),
		))
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	ListMobAssetsAll,
	ListMobAssets,
	ListMeshswapAssets,
	ListItemAssets,
	ListEntityAssets,
	ListModelAssets,
	ListEffectsAssets,
	MCPREP_UL_material,
	MCPREP_UL_mob,
	MCPREP_UL_meshswap,
	MCPREP_UL_entity,
	MCPREP_UL_model,
	MCPREP_UL_item,
	MCPREP_UL_effects,
	MCPREP_OT_reload_spawners,
	MCPREP_OT_spawn_path_reset,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
