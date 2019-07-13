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


# library imports
import errno
import operator
import os
import shutil

import bpy
from bpy_extras.io_utils import ImportHelper

from .. import conf
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# support functions
# -----------------------------------------------------------------------------


def get_rig_list(context):
	"""Only used for operator UI Enum property in redo last / popups"""

	# may redraw too many times, perhaps have flag to prevent re-runs
	if not context.scene.mcprep_props.mob_list_all:
		update_rig_list(context)
	ret_list = [(mob.mcmob_type, mob.name, mob.description)
		for mob in context.scene.mcprep_props.mob_list_all]
	return ret_list


def update_rig_path(self, context):
	"""List for UI items callback of property spawn_rig_category."""
	conf.log("Updating rig path", vv_only=True)
	update_rig_list(context)
	spawn_rigs_categories(self, context)


def update_rig_list(context):
	"""Update the rig list and subcategory list"""

	def _add_rigs_from_blend(path, blend_name, category):
		"""Block for loading blend file groups to get rigs"""
		with bpy.data.libraries.load(path) as (data_from, data_to):
			if hasattr(data_from, "groups"): # blender 2.7
				get_attr = "groups"
			else: # 2.8
				get_attr = "collections"

			extensions = [".png",".jpg",".jpeg"]
			icon_folder = os.path.join(os.path.dirname(path), "icons")
			run_icons = os.path.isdir(icon_folder)
			if not conf.use_icons or conf.preview_collections["mobs"] == "":
				run_icons = False

			for name in getattr(data_from, get_attr):
				# special cases, skip some groups
				if name.lower() == "Rigidbodyworld".lower():
					continue
				description = "Spawn one {x} rig".format(x=name)
				mob = context.scene.mcprep_props.mob_list_all.add()
				mob.description = description # add in non all-list
				mob.name = name.title()
				mob.category = category
				mob.index = len(context.scene.mcprep_props.mob_list_all)
				if category:
					mob.mcmob_type = os.path.join(
						category, blend_name) + ":/:" + name
				else:
					mob.mcmob_type = blend_name + ":/:" + name

				# if available, load the custom icon too
				if not run_icons:
					continue

				icons = [f for f in os.listdir(icon_folder)
							if os.path.isfile(os.path.join(icon_folder, f))
							and name.lower() == os.path.splitext(f.lower())[0]
							and not f.startswith(".")
							and os.path.splitext(f.lower())[-1] in extensions
							]
				if not icons:
					continue
				conf.preview_collections["mobs"].load(
					"mob-{}".format(mob.index),
					os.path.join(icon_folder, icons[0]),
					'IMAGE')

	rigpath = bpy.path.abspath(context.scene.mcprep_mob_path)
	context.scene.mcprep_props.mob_list.clear()
	context.scene.mcprep_props.mob_list_all.clear()

	if conf.use_icons and conf.preview_collections["mobs"]:
		print("Removing mobs preview collection")
		try:
			bpy.utils.previews.remove(conf.preview_collections["mobs"])
		except:
			conf.log("MCPREP: Failed to remove icon set, mobs")

	if os.path.isdir(rigpath) is False:
		conf.log("Rigpath directory not found")
		return

	categories = [f	for f in os.listdir(rigpath)
					if os.path.isdir(os.path.join(rigpath, f))
					and not f.startswith(".")]
	no_category_blends = [f	for f in os.listdir(rigpath)
							if os.path.isfile(os.path.join(rigpath, f))
							and f.endswith(".blend")
							and not f.startswith(".")]

	for category in categories:
		cat_path = os.path.join(rigpath, category)
		blend_files = [f for f in os.listdir(cat_path)
						if os.path.isfile(os.path.join(cat_path, f))
						and f.endswith(".blend")
						and not f.startswith(".")]

		for blend_name in blend_files:
			blend_path = os.path.join(cat_path, blend_name)
			_add_rigs_from_blend(blend_path, blend_name, category)

	# Update the list with non-categorized mobs (ie root of target folder)
	for blend_name in no_category_blends:
		blend_path = os.path.join(rigpath, blend_name)
		_add_rigs_from_blend(blend_path, blend_name, "")

	update_rig_category(context)


def update_rig_category(context):
	"""Update the list of mobs for the given category from the master list"""

	scn_props = context.scene.mcprep_props

	if not scn_props.mob_list_all:
		conf.log("No rigs found, failed to update category")
		scn_props.mob_list.clear()
		return

	category = scn_props.spawn_rig_category
	if category == "no_category":
		category = ""  # to match how the attribute is saved
	scn_props.mob_list.clear()

	cat_mobs = [mob for mob in scn_props.mob_list_all
				if mob.category == category or category == "all"]
	cat_mobs.sort(key=lambda x: x.name, reverse=False)

	# consider bringing the player rigs up first
	for mob in cat_mobs:
		item = scn_props.mob_list.add()
		item.description = mob.description
		item.name = mob.name
		item.mcmob_type = mob.mcmob_type
		item.category = mob.category
		item.index = mob.index # for icons

	if scn_props.mob_list_index >= len(scn_props.mob_list):
		scn_props.mob_list_index = len(scn_props.mob_list)-1


# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------


class MCPREP_OT_reload_mobs(bpy.types.Operator):
	"""Force reload the mob spawner rigs, use after manually adding rigs to folders"""
	bl_idname = "mcprep.reload_mobs"
	bl_label = "Reload the rigs and cache"

	@tracking.report_error
	def execute(self, context):
		update_rig_list(context)
		return {'FINISHED'}


class MCPREP_OT_mob_spawner(bpy.types.Operator):
	"""Show menu and spawn built-in or custom rigs into a scene"""
	bl_idname = "mcprep.mob_spawner"
	bl_label = "Mob Spawner"
	bl_description = "Spawn built-in or custom rigs into the scene"
	bl_options = {'REGISTER', 'UNDO'}

	def riglist_enum(self, context):
		return get_rig_list(context)

	mcmob_type = bpy.props.EnumProperty(items=riglist_enum, name="Mob Type")
	relocation = bpy.props.EnumProperty(
		items = [('Cursor', 'Cursor', 'Move the rig to the cursor'),
				('Clear', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root', 'Offset the root bone to cursor while leaving the rest pose at the origin')],
		name = "Relocation"
		)
	toLink = bpy.props.BoolProperty(
		name = "Library Link",
		description = "Library link instead of append the group",
		default = False
		)
	clearPose = bpy.props.BoolProperty(
		name = "Clear Pose",
		description = "Clear the pose to rest position",
		default = True
		)
	auto_prep = bpy.props.BoolProperty(
		name = "Prep materials (will reset nodes)",
		description = "Prep materials of the added rig, will replace cycles node groups with default",
		default = True
		)

	def draw(self, context):
		"""Draw in redo last menu or F6"""
		row = self.layout.row()
		row.prop(self,"relocation")

		row = self.layout.row(align=True)
		row.prop(self,"toLink")
		row.prop(self,"clearPose")
		row = self.layout.row(align=True)
		engine = context.scene.render.engine
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
			row.prop(self, "auto_prep")
		else:
			row.prop(self, "auto_prep", text="Prep materials")

	@staticmethod
	def attemptScriptLoad(path):
		# search for script that matches name of the blend file
		# should also look into the blend if appropriate
		if not path[-5:]=="blend":
			return
		path = path[:-5]+"py"
		if not os.path.isfile(path):
			return # no script found
		conf.log("Script found, loading and running it")
		text = bpy.data.texts.load(filepath=path, internal=True)
		try:
			ctx = bpy.context.copy()
			ctx['edit_text'] = text
		except Exception as err:
			print("Error trying to create context to run script in:")
			print(str(err))
		try:
			bpy.ops.text.run_script(ctx)
		except:
			conf.log("Failed to run the script, not registering")
			return
		conf.log("Ran the script")
		text.use_module = True

	def setRootLocation(self,context):
		pass
		# should be the consolidated code for
		# both linking and appending below, .. they branched right now.

	track_function = "mobSpawner"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		try:
			[path, name] = self.mcmob_type.split(':/:')
			path = os.path.join(context.scene.mcprep_mob_path,path)
			conf.log("Path is now ",path)
		except:
			conf.log("Error: No rigs found!")
			self.report({'ERROR'}, "No mobs found in folder!")
			return {'CANCELLED'}

		try:
			# must be in object mode, this make similar behavior to other objs
			bpy.ops.object.mode_set(mode='OBJECT')
		except:
			pass # can fail to this e.g. if no objects are selected

		if self.toLink:
			if path == '//':
				# not sure what that means here
				conf.log("This is the local file. Cancelling...")
				return {'CANCELLED'}
			res = self.load_linked(context, path, name)
		else:
			# append the rig, the whole group.. though honestly ideally not, and just append the right objs
			#idea: link in group, inevtiably need to make into this blend file but then get the remote's
			# all object names, then unlink/remove group (and object it creates) and directly append all those objects
			# OOORR do append the group, then remove the group but keep the individual objects
			# that way we know we don't append in too many objects (e.g. parents pulling in children/vice versa)
			res = self.load_append(context, path, name)
			# also issue of "undo/redo"... groups stay linked/ as groups even if this happens!

		# if there is a script with this rig, attempt to run it
		self.attemptScriptLoad(path)

		if self.auto_prep and not self.toLink and context.selected_objects:
			bpy.ops.mcprep.prep_materials(skipUsage=True)

		self.track_param = self.mcmob_type.split(":/:")[1]
		return {'FINISHED'}

	@staticmethod
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
			elif "rig" in obj.name and "rig" not in prox_obj.name.lower():
				prox_obj = obj
		return prox_obj

	@staticmethod
	def offset_root_bone(context, armature):
		"""Used to offset bone to world location (cursor)"""
		conf.log("Attempting offset root")
		set_bone = False
		lower_bones = [bone.name.lower() for bone in armature.pose.bones]
		lower_name = None
		for name in ["main", "root", "base", "master"]:
			if name in  lower_bones:
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
		"""Process for loading mob via linked library"""

		path = bpy.path.abspath(path)
		act = None
		if hasattr(bpy.data, "groups"):
			util.bAppendLink(path + '/Group', name, True)
			act = context.object  # assumption of object after linking, 2.7 only
		elif hasattr(bpy.data, "collections"):
			util.bAppendLink(path + '/Collection', name, True)
			act = context.selected_objects[0] # better for 2.8

		# util.bAppendLink(os.path.join(path, g_or_c), name, True)
		# proxy any and all armatures
		# here should do all that jazz with hacking by copying files, checking nth number
		#probably consists of checking currently linked libraries, checking if which
		#have already been linked into existing rigs
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
			act.location = (0,0,0)

		# find the best armature to proxy, if any
		prox_obj = None
		if not act.type == "EMPTY":
			self.report({'WARNING'}, "Linked object should be type: empty")
			return
		elif not util.instance_collection(act):
			self.report({'WARNING'}, "Linked object has no dupligroup")
			return
		else:
			prox_obj = self.get_rig_from_objects(
				util.instance_collection(act).objects)
		if not prox_obj:
			self.report({'WARNING'}, "No object found to proxy")
			return

		bpy.ops.object.proxy_make(object=prox_obj.name)
		coll = util.instance_collection(act)
		if hasattr(coll, "dupli_offset"):
			gl = coll.dupli_offset
		elif hasattr(act, "instance_offset"):
			gl = coll.instance_offset
		# cl = util.get_cuser_location(context)

		if self.relocation == "Offset":
			# do the offset stuff, set active etc
			bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))

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
			set_bone = self.offset_root_bone(context, act)
			if not set_bone:
				print("MCprep mob spawning works better when the root bone's name is 'MAIN'")
				self.report({'INFO'}, "This addon works better when the root bone's name is 'MAIN'")


	def load_append(self, context, path, name):
		if path == '//':
			# This means the group HAS already been appended..
			# Could try to recopy thsoe elements, or try re-appending with
			# renaming of the original group
			self.report({'ERROR'}, "Group name already exists in local file")
			conf.log("Group already appended/is here")
			return

		path = bpy.path.abspath(path)
		sel = bpy.context.selected_objects # capture state before, technically also copy
		for ob in context.scene.objects:
			util.select_set(ob, False)
		# consider taking pre-exisitng group names and giving them a temp name to name back at the end

		if hasattr(bpy.data, "groups"):
			subpath = 'Group'
		elif hasattr(bpy.data, "collections"):
			subpath = 'Collection'

		conf.log(os.path.join(path, subpath) + ', ' + name)
		pregroups = list(util.collections())
		util.bAppendLink(os.path.join(path, subpath), name, False)
		postgroups = list(util.collections())

		g1 = None
		new_groups = list(set(postgroups)-set(pregroups))
		if not new_groups and name in util.collections():
			# this is more likely to fail but serves as a fallback
			conf.log("Mob spawn: Had to go to fallback group name grab")
			grp_added = util.collections()[name]
		elif not new_groups:
			conf.log("Warning, could not detect imported group")
			self.report({'WARNING'}, "Could not detect imported group")
			return
		else:
			grp_added = new_groups[0] # assume first

		conf.log("Identified object {} with group {} as just imported".format(
			g1, grp_added), vv_only=True)

		# if rig not centered in original file, assume its group is
		if hasattr(grp_added, "dupli_offset"): # 2.7
			gl = grp_added.dupli_offset
		elif hasattr(grp_added, "instance_offset"): # 2.8
			gl = grp_added.instance_offset
		else:
			conf.log("Warning, could not set offset for group; null type?")
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
				util.select_set(obj, True)

		# try:
		# 	util.collections().remove(grp_added)
		# 	This can cause redo last issues
		# except:
		# 	pass
		rig_obj = self.get_rig_from_objects(addedObjs)
		if not rig_obj:
			conf.log("Could not get rig object")
			self.report({'WARNING'}, "No armatures found!")
		else:
			conf.log("Using object as primary rig: "+rig_obj.name)
			util.set_active_object(context, rig_obj)

		if rig_obj and self.clearPose or rig_obj and self.relocation=="Offset":
			if self.relocation == "Offset":
				bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
			try:
				bpy.ops.object.mode_set(mode='POSE')
			except Exception as e:
				self.report({'ERROR'},"Exception occured, see logs")
				print("Exception: ",str(e))
				print(bpy.context.object)
				print(rig_obj)
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
				set_bone = self.offset_root_bone(context, rig_obj)
				if not set_bone:
					conf.log("This addon works better when the root bone's name is 'MAIN'")
					self.report({'INFO'}, "Works better if armature has a root bone named 'MAIN' or 'ROOT'")

		# now do the extra options, e.g. the object-level offsets
		if context.mode != 'OBJECT':
			bpy.ops.object.mode_set(mode='OBJECT')
		if self.relocation == "Origin":
			bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
		elif self.relocation=="Cursor":
			bpy.ops.transform.translate(value=(cl[0]-gl[0],
												cl[1]-gl[1],
												cl[2]-gl[2]))
		# add the original selection back
		for objs in sel:
			util.select_set(objs, True)


class MCPREP_OT_install_mob(bpy.types.Operator, ImportHelper):
	"""Install custom rig popup for the mob spawner, all groups in selected blend file will become individually spawnable"""
	bl_idname = "mcprep.mob_install_menu"
	bl_label = "Install new mob"

	filename_ext = ".blend"
	filter_glob = bpy.props.StringProperty(
			default="*.blend",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"

	def getCategories(self, context):
		path = bpy.path.abspath(context.scene.mcprep_mob_path)
		ret = []
		ret.append(("all", "No Category", "Uncategorized mob"))
		ret += [(f, f.title(), "{} mob".format(f.title()))
				for f in os.listdir(path)
				if os.path.isdir(os.path.join(path, f))
				and not f.startswith(".")]
		ret.append(("no_category", "No Category", "Uncategorized mob")) # last entry
		return ret

	mob_category = bpy.props.EnumProperty(
		items = getCategories,
		name = "Mob Category")

	@tracking.report_error
	def execute(self, context):
		drpath = context.scene.mcprep_mob_path
		newrig = bpy.path.abspath(self.filepath)

		if not os.path.isfile(newrig):
			conf.log("Error: Rig blend file not found!")
			self.report({'ERROR'}, "Rig blend file not found!")
			return {'CANCELLED'}

		# now check the rigs folder indeed exists
		drpath = bpy.path.abspath(drpath)
		if not os.path.isdir(drpath):
			conf.log("Error: Rig directory is not valid!")
			self.report({'ERROR'}, "Rig directory is not valid!")
			return {'CANCELLED'}

		# check the file for any groups, any error return failed
		with bpy.data.libraries.load(newrig) as (data_from, data_to):
			if hasattr(data_from, "groups"): # blender 2.7
				get_attr = "groups"
			else: # 2.8
				get_attr = "collections"
			install_groups = list(getattr(data_from, get_attr)) # list of str's

		if 'Collection' in install_groups: # don't count the default 2.8 group
			install_groups.pop(install_groups.index('Collection'))

		if not install_groups:
			conf.log("Error: no groups found in blend file!")
			self.report({'ERROR'}, "No groups found in blend file!")
			return {'CANCELLED'}

		# copy this file to the rig folder
		filename = os.path.basename(newrig)
		if self.mob_category != "no_category" and self.mob_category != "all":
			end_path = os.path.join(drpath, self.mob_category)
		else:
			end_path = drpath

		try:
			shutil.copy2(newrig, os.path.join(end_path, filename))
		except IOError as err:
			print(err)
			# can fail if permission denied, i.e. an IOError error
			self.report({'ERROR'},
				"Failed to copy, manually install by copying blend to folder: {}".format(
					end_path))
			return {'CANCELLED'}

		# now do same to install py files if any or icons
		# failure here is non critical
		try:
			if os.path.isfile(newrig[:-5]+"py"):
				# if there is a script, install that too
				shutil.copy2(newrig[:-5]+"py",
					os.path.join(end_path, filename[:-5]+"py"))
		except IOError as err:
			print(err)
			self.report({'WARNING'},
				"Failed attempt to copy python file: {}".format(
					end_path))

		# copy all relevant icons, based on groups installed
		### matching same folde or subfolder icons to append
		if conf.use_icons:
			basedir = os.path.dirname(newrig)
			icon_files = self.identify_icons(install_groups, basedir)
			icondir = os.path.join(basedir, "icons")
			if os.path.isdir(icondir):
				icon_files += self.identify_icons(install_groups, icondir)
			if icon_files:
				dst = os.path.join(end_path, "icons")
				if not os.path.isdir(dst):
					try:
						os.mkdir(dst)
					except OSError as exc:
						if exc.errno == errno.EACCES:
							print("Permission denied, try running blender as admin")
						elif exc.errno != errno.EEXIST:
							print("Path does not exist: "+dst)
				for icn in icon_files:
					icn_base = os.path.basename(icn)
					try:
						shutil.copy2(icn, os.path.join(dst, icn_base))
					except IOError as err:
						print("Failed to copy over icon file "+icn)
						print("to "+os.path.join(icondir, icn_base))

		# reload the cache
		update_rig_list(context)
		self.report({'INFO'}, "Mob-file Installed")

		return {'FINISHED'}

	def identify_icons(self, group_names, path):
		"""Copy over all matching icons from single specific folder"""
		if not group_names:
			return []
		extensions = [".png",".jpg",".jpeg"]
		icons = []
		for name in group_names:
			icons += [os.path.join(path, f) for f in os.listdir(path)
						if os.path.isfile(os.path.join(path, f))
						and name.lower() in f.lower()
						and not f.startswith(".")
						and os.path.splitext(f.lower())[-1] in extensions
						]
		return icons


class MCPREP_OT_uninstall_mob(bpy.types.Operator):
	"""Uninstall selected mob by deleting source blend file"""
	bl_idname = "mcprep.mob_uninstall"
	bl_label = "Uninstall mob"

	path = ""
	listing = []

	def invoke(self, context, event):
		self.preDraw(context)
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

	def preDraw(self, context):
		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index].mcmob_type
		self.path = ""

		try:
			self.path = mob.split(":/:")[0]
		except Exception as e:
			self.report({'ERROR'}, "Could not resolve file to delete")
			print("Error: {}".format(e))
			return {'CANCELLED'}

		# see how many groups use this blend file
		count = 0
		self.listing = []
		for mob in scn_props.mob_list_all:
			path, name = mob.mcmob_type.split(":/:")
			if path == self.path:
				self.listing.append(name)
				count+=1

	def draw(self, context):
		row = self.layout.row()
		row.scale_y=0.5
		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index].mcmob_type
		path = mob.split(":/:")[0]
		path = os.path.join(context.scene.mcprep_mob_path, path)
		if len(self.listing)>1:
			row.label(text="Multiple mobs found in target blend file:")
			row = self.layout.row()
			row.scale_y=0.5

			# draw 3-column list of mobs to be deleted
			col1 = row.column()
			col1.scale_y=0.6
			col2 = row.column()
			col2.scale_y=0.6
			col3 = row.column()
			col3.scale_y=0.6
			count = 0
			for grp in self.listing:
				count+=1
				if count%3==0:
					col1.label(text=grp)
				elif count%3==1:
					col2.label(text=grp)
				else:
					col3.label(text=grp)
			row = self.layout.row()
			row.label(text="Press okay to delete these mobs and file:")
		else:
			col = row.column()
			col.scale_y = 0.7
			col.label(text="Press okay to delete mob and file:")
		row = self.layout.row()
		row.label(text=path)

	@tracking.report_error
	def execute(self,context):
		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index].mcmob_type
		try:
			path = mob.split(":/:")[0]
			path = os.path.join(context.scene.mcprep_mob_path,path)
		except Exception as e:
			self.report({'ERROR'}, "Could not resolve file to delete")
			print("Error trying to remove mob file: "+str(e))
			return {'CANCELLED'}

		if os.path.isfile(path) == False:
			conf.log("Error: Source filepath not found, didn't delete: "+path)
			self.report({'ERROR'}, "Source filepath not found, didn't delete")
			return {'CANCELLED'}
		else:
			try:
				os.remove(path)
			except:
				conf.log("Error: could not delete file")
				self.report({'ERROR'}, "Could not delete file")
				return {'CANCELLED'}
		self.report({'INFO'},"Removed: "+str(path))
		conf.log("Removed file: "+str(path))
		bpy.ops.mcprep.reload_mobs()
		return {'FINISHED'}


class MCPREP_OT_install_mob_icon(bpy.types.Operator, ImportHelper):
	"""Install custom icon for select group in mob spawner UI list"""
	bl_idname = "mcprep.mob_install_icon"
	bl_label = "Install mob icon"

	#filename_ext = ".blend"
	# filter_glob = bpy.props.StringProperty(
	# 		default="*.blend",
	# 		options={'HIDDEN'},
	# 		)
	# fileselectparams = "use_filter_image"
	filter_glob = bpy.props.StringProperty(
		default="",
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	filter_image = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'})

	def execute(self, context):
		if not self.filepath:
			self.report({'ERROR'}, "No filename selected")
			return {'CANCELLED'}
		elif not os.path.isfile(self.filepath):
			self.report({'ERROR'}, "File not found")
			return {'CANCELLED'}

		extensions = [".png",".jpg",".jpeg"]
		ext = os.path.splitext(self.filepath)[-1] # get extension, includes .
		if ext.lower() not in extensions:
			self.report({'ERROR'}, "Wrong filetype, must be png or jpg")
			return {'CANCELLED'}

		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index]
		_, name = mob.mcmob_type.split(':/:')
		path = context.scene.mcprep_mob_path


		icon_dir = os.path.join(path, mob.category, "icons")
		new_file = os.path.join(icon_dir, name+ext)
		print("New icon file name would be:")
		print(new_file)

		if not os.path.isdir(icon_dir):
			try:
				os.mkdir(icon_dir)
			except OSError as exc:
				if exc.errno == errno.EACCES:
					print("Permission denied, try running blender as admin")
				elif exc.errno != errno.EEXIST:
					print("Path does not exist: "+icon_dir)

		# if the file exists already, remove it.
		if os.path.isfile(new_file):
			try:
				os.remove(new_file)
			except Exception as err:
				print("Failed to remove previous icon file")
				print(err)

		try:
			shutil.copy2(self.filepath, new_file)
		except IOError as err:
			print("Failed to copy, manually copy to file name: {}".format(
					new_file))
			print(err)
			self.report({'ERROR'},
				"Failed to copy, manually copy to file name: {}".format(
					new_file))
			return {'CANCELLED'}

		# if successful, load or reload icon id
		icon_id = "mob-{}".format(mob.index)
		if icon_id in conf.preview_collections["mobs"]:
			print("Deloading old icon for this mob")
			print(dir(conf.preview_collections["mobs"][icon_id]))
			conf.preview_collections["mobs"][icon_id].reload()
		else:
			conf.preview_collections["mobs"].load(icon_id, new_file, 'IMAGE')
			print("Icon reloaded")

		return {'FINISHED'}

# -----------------------------------------------------------------------------
#	Mob category related
# -----------------------------------------------------------------------------


def spawn_rigs_categories(self, context):
	"""Used as enum UI list for spawn_rig_category dropdown"""
	items = []
	items.append(("all","All Mobs","Show all mobs loaded"))

	categories = conf.rig_categories
	if not conf.rig_categories:
		it = context.scene.mcprep_mob_path
		categories = [f for f in os.listdir(it)
						if os.path.isdir(os.path.join(it,f))]
		conf.rig_categories = categories
	for item in categories:
		ui_name = item+" mobs"
		items.append((item, ui_name.title(),
			"Show all mobs in the '"+item+"' category"))

	items.append(("no_category", "Uncategorized", "Show all uncategorized mobs"))
	return items


def spawn_rigs_category_load(self, context):
	"""Update function for UI property spawn rig category"""
	update_rig_category(context)
	return


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_reload_mobs,
	MCPREP_OT_mob_spawner,
	MCPREP_OT_install_mob,
	MCPREP_OT_uninstall_mob,
	MCPREP_OT_install_mob_icon
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
