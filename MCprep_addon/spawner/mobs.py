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
import os
import shutil

import bpy
from bpy_extras.io_utils import ImportHelper

from .. import conf
from .. import util
from .. import tracking

from . import spawn_util


# -----------------------------------------------------------------------------
# support functions
# -----------------------------------------------------------------------------


def get_rig_list(context):
	"""Only used for operator UI Enum property in redo last / popups"""

	# may redraw too many times, perhaps have flag to prevent re-runs
	if not context.scene.mcprep_props.mob_list_all:
		update_rig_list(context)
	ret_list = [
		(mob.mcmob_type, mob.name, mob.description)
		for mob in context.scene.mcprep_props.mob_list_all]
	return ret_list


def update_rig_path(self, context):
	"""List for UI items callback of property spawn_rig_category."""
	conf.log("Updating rig path", vv_only=True)
	conf.rig_categories = []
	update_rig_list(context)
	spawn_rigs_categories(self, context)


def update_rig_list(context):
	"""Update the rig list and subcategory list"""

	def _add_rigs_from_blend(path, blend_name, category):
		"""Block for loading blend file groups to get rigs"""
		with bpy.data.libraries.load(path) as (data_from, data_to):

			extensions = [".png", ".jpg", ".jpeg"]
			icon_folder = os.path.join(os.path.dirname(path), "icons")
			run_icons = os.path.isdir(icon_folder)
			if not conf.use_icons or conf.preview_collections["mobs"] == "":
				run_icons = False

			mob_names = spawn_util.filter_collections(data_from)

			for name in mob_names:
				description = "Spawn one {x} rig".format(x=name)
				mob = context.scene.mcprep_props.mob_list_all.add()
				mob.description = description  # add in non all-list
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

				icons = [
					f for f in os.listdir(icon_folder)
					if os.path.isfile(os.path.join(icon_folder, f))
					and name.lower() == os.path.splitext(f.lower())[0]
					and not f.startswith(".")
					and os.path.splitext(f.lower())[-1] in extensions]
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

	categories = [
		f for f in os.listdir(rigpath)
		if os.path.isdir(os.path.join(rigpath, f)) and not f.startswith(".")]
	no_category_blends = [
		f for f in os.listdir(rigpath)
		if os.path.isfile(os.path.join(rigpath, f))
		and f.endswith(".blend")
		and not f.startswith(".")]

	for category in categories:
		cat_path = os.path.join(rigpath, category)
		blend_files = [
			f for f in os.listdir(cat_path)
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

	cat_mobs = [
		mob for mob in scn_props.mob_list_all
		if mob.category == category or category == "all"]
	cat_mobs.sort(key=lambda x: x.name, reverse=False)

	# consider bringing the player rigs up first
	for mob in cat_mobs:
		item = scn_props.mob_list.add()
		item.description = mob.description
		item.name = mob.name
		item.mcmob_type = mob.mcmob_type
		item.category = mob.category
		item.index = mob.index  # for icons

	if scn_props.mob_list_index >= len(scn_props.mob_list):
		scn_props.mob_list_index = len(scn_props.mob_list) - 1


# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------


class MCPREP_OT_reload_mobs(bpy.types.Operator):
	"""Force reload the mob spawner rigs, use after manually adding rigs to folders"""
	bl_idname = "mcprep.reload_mobs"
	bl_label = "Reload the rigs and cache"

	@tracking.report_error
	def execute(self, context):
		conf.rig_categories = []
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
		items=[
			('Cursor', 'Cursor', 'Move the rig to the cursor'),
			('Clear', 'Origin', 'Move the rig to the origin'),
			('Offset', 'Offset root', (
				'Offset the root bone to cursor while leaving the rest pose '
				'at the origin'))],
		name="Relocation")
	toLink = bpy.props.BoolProperty(
		name="Library Link",
		description="Library link instead of append the group",
		default=False)
	clearPose = bpy.props.BoolProperty(
		name="Clear Pose",
		description="Clear the pose to rest position",
		default=True)
	prep_materials = bpy.props.BoolProperty(
		name="Prep materials (will reset nodes)",
		description=(
			"Prep materials of the added rig, will replace cycles node groups "
			"with default"),
		default=True)

	skipUsage = bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	def draw(self, context):
		"""Draw in redo last menu or F6"""
		row = self.layout.row()
		row.prop(self, "relocation")

		row = self.layout.row(align=True)
		row.prop(self, "toLink")
		row.prop(self, "clearPose")
		row = self.layout.row(align=True)
		engine = context.scene.render.engine
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
			row.prop(self, "prep_materials")
		else:
			row.prop(self, "prep_materials", text="Prep materials")

	track_function = "mobSpawner"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		try:
			[path, name] = self.mcmob_type.split(':/:')
		except Exception as err:
			conf.log("Error: Failed to parse mcmob_type")
			self.report({'ERROR'}, "Failed to parse mcmob_type, try reloading mobs")
			return {'CANCELLED'}
		path = os.path.join(context.scene.mcprep_mob_path, path)
		conf.log("Path is now ", path)

		try:
			# must be in object mode, this make similar behavior to other objs
			bpy.ops.object.mode_set(mode='OBJECT')
		except:
			pass  # Can fail to this e.g. if no objects are selected.

		if self.toLink:
			if path == '//':
				conf.log("This is the local file. Cancelling...")
				return {'CANCELLED'}
			_ = spawn_util.load_linked(self, context, path, name)
		else:
			_ = spawn_util.load_append(self, context, path, name)

		# if there is a script with this rig, attempt to run it
		spawn_util.attemptScriptLoad(path)

		if self.prep_materials and not self.toLink and context.selected_objects:
			try:
				bpy.ops.mcprep.prep_materials(
					improveUiSettings=False, skipUsage=True)
			except:
				self.report({"WARNING"}, "Failed to prep materials on mob load")

		self.track_param = self.mcmob_type.split(":/:")[1]
		return {'FINISHED'}


class MCPREP_OT_install_mob(bpy.types.Operator, ImportHelper):
	"""Install mob operator."""
	bl_idname = "mcprep.mob_install_menu"
	bl_label = "Install new mob"
	bl_description = (
		"Install custom rig popup for the mob spawner, all groups/collections "
		"in selected blend file will become individually spawnable")

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
		ret += [
			(f, f.title(), "{} mob".format(f.title()))
			for f in os.listdir(path)
			if os.path.isdir(os.path.join(path, f)) and not f.startswith(".")]
		ret.append(("no_category", "No Category", "Uncategorized mob"))  # last entry
		return ret

	mob_category = bpy.props.EnumProperty(
		items=getCategories,
		name="Mob Category")

	@tracking.report_error
	def execute(self, context):
		drpath = context.scene.mcprep_mob_path
		newrig = bpy.path.abspath(self.filepath)

		if not os.path.isfile(newrig):
			conf.log("Error: Rig blend file not found!")
			self.report({'ERROR'}, "Rig blend file not found!")
			return {'CANCELLED'}

		if not newrig.lower().endswith('.blend'):
			conf.log("Error: Not a blend file! Select a .blend file with a rig")
			self.report({'ERROR'}, "Not a blend file! Select a .blend file with a rig")
			return {'CANCELLED'}

		# now check the rigs folder indeed exists
		drpath = bpy.path.abspath(drpath)
		if not os.path.isdir(drpath):
			conf.log("Error: Rig directory is not valid!")
			self.report({'ERROR'}, "Rig directory is not valid!")
			return {'CANCELLED'}

		# check the file for any groups, any error return failed
		with bpy.data.libraries.load(newrig) as (data_from, data_to):
			install_groups = spawn_util.filter_collections(data_from)

		if 'Collection' in install_groups:  # don't count the default 2.8 group
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
			self.report(
				{'ERROR'},
				"Failed to copy, manually install by copying blend to folder: {}".format(
					end_path))
			return {'CANCELLED'}

		# now do same to install py files if any or icons
		# failure here is non critical
		try:
			if os.path.isfile(newrig[:-5] + "py"):
				# if there is a script, install that too
				shutil.copy2(
					newrig[:-5] + "py",
					os.path.join(end_path, filename[:-5] + "py"))
		except IOError as err:
			print(err)
			self.report(
				{'WARNING'},
				"Failed attempt to copy python file: {}".format(
					end_path))

		# copy all relevant icons, based on groups installed
		# ## matching same folde or subfolder icons to append
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
							print(dst)
							print(exc)
						elif exc.errno != errno.EEXIST:
							print("Path does not exist: " + dst)
							print(exc)
				for icn in icon_files:
					icn_base = os.path.basename(icn)
					try:
						shutil.copy2(icn, os.path.join(dst, icn_base))
					except IOError as err:
						print("Failed to copy over icon file " + icn)
						print("to " + os.path.join(icondir, icn_base))
						print(err)

		# reload the cache
		update_rig_list(context)
		self.report({'INFO'}, "Mob-file Installed")

		return {'FINISHED'}

	def identify_icons(self, group_names, path):
		"""Copy over all matching icons from single specific folder"""
		if not group_names:
			return []
		extensions = [".png", ".jpg", ".jpeg"]
		icons = []
		for name in group_names:
			icons += [
				os.path.join(path, f) for f in os.listdir(path)
				if os.path.isfile(os.path.join(path, f))
				and name.lower() in f.lower()
				and not f.startswith(".")
				and os.path.splitext(f.lower())[-1] in extensions]
		return icons


class MCPREP_OT_uninstall_mob(bpy.types.Operator):
	"""Uninstall selected mob by deleting source blend file"""
	bl_idname = "mcprep.mob_uninstall"
	bl_label = "Uninstall mob"

	path = ""
	listing = []

	def invoke(self, context, event):
		self.preDraw(context)
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

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
				count += 1

	def draw(self, context):
		row = self.layout.row()
		row.scale_y = 0.5
		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index].mcmob_type
		path = mob.split(":/:")[0]
		path = os.path.join(context.scene.mcprep_mob_path, path)
		if len(self.listing) > 1:
			row.label(text="Multiple mobs found in target blend file:")
			row = self.layout.row()
			row.scale_y = 0.5

			# draw 3-column list of mobs to be deleted
			col1 = row.column()
			col1.scale_y = 0.6
			col2 = row.column()
			col2.scale_y = 0.6
			col3 = row.column()
			col3.scale_y = 0.6
			count = 0
			for grp in self.listing:
				count += 1
				if count % 3 == 0:
					col1.label(text=grp)
				elif count % 3 == 1:
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
	def execute(self, context):
		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index].mcmob_type
		try:
			path = mob.split(":/:")[0]
			path = os.path.join(context.scene.mcprep_mob_path, path)
		except Exception as e:
			self.report({'ERROR'}, "Could not resolve file to delete")
			print("Error trying to remove mob file: " + str(e))
			return {'CANCELLED'}

		if os.path.isfile(path) is False:
			conf.log("Error: Source filepath not found, didn't delete: " + path)
			self.report({'ERROR'}, "Source filepath not found, didn't delete")
			return {'CANCELLED'}
		else:
			try:
				os.remove(path)
			except Exception as err:
				conf.log("Error: could not delete file: " + str(err))
				self.report({'ERROR'}, "Could not delete file")
				return {'CANCELLED'}
		self.report({'INFO'}, "Removed: " + str(path))
		conf.log("Removed file: " + str(path))
		bpy.ops.mcprep.reload_mobs()
		return {'FINISHED'}


class MCPREP_OT_install_mob_icon(bpy.types.Operator, ImportHelper):
	"""Install custom icon for select group in mob spawner UI list"""
	bl_idname = "mcprep.mob_install_icon"
	bl_label = "Install mob icon"

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

		extensions = [".png", ".jpg", ".jpeg"]
		ext = os.path.splitext(self.filepath)[-1]  # get extension, includes .
		if ext.lower() not in extensions:
			self.report({'ERROR'}, "Wrong filetype, must be png or jpg")
			return {'CANCELLED'}

		scn_props = context.scene.mcprep_props
		mob = scn_props.mob_list[scn_props.mob_list_index]
		_, name = mob.mcmob_type.split(':/:')
		path = context.scene.mcprep_mob_path

		icon_dir = os.path.join(path, mob.category, "icons")
		new_file = os.path.join(icon_dir, name + ext)
		print("New icon file name would be:")
		print(new_file)

		if not os.path.isdir(icon_dir):
			try:
				os.mkdir(icon_dir)
			except OSError as exc:
				if exc.errno == errno.EACCES:
					print("Permission denied, try running blender as admin")
				elif exc.errno != errno.EEXIST:
					print("Path does not exist: " + icon_dir)

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
			self.report(
				{'ERROR'},
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
# Mob category related
# -----------------------------------------------------------------------------


def spawn_rigs_categories(self, context):
	"""Used as enum UI list for spawn_rig_category dropdown"""
	items = []
	items.append(("all", "All Mobs", "Show all mobs loaded"))

	categories = conf.rig_categories
	if not conf.rig_categories:
		it = context.scene.mcprep_mob_path
		categories = [
			f for f in os.listdir(it) if os.path.isdir(os.path.join(it, f))]
		conf.rig_categories = categories
	for item in categories:
		ui_name = item + " mobs"
		items.append((
			item, ui_name.title(),
			"Show all mobs in the '" + item + "' category"))

	items.append(("no_category", "Uncategorized", "Show all uncategorized mobs"))
	return items


def spawn_rigs_category_load(self, context):
	"""Update function for UI property spawn rig category"""
	update_rig_category(context)
	return


# -----------------------------------------------------------------------------
# Registration
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
