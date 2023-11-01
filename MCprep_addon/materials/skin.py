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
from pathlib import Path
from typing import Optional, List, Tuple
import shutil
import urllib.request

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.app.handlers import persistent
from bpy.types import Context, Image, Material

from . import generate
from .. import tracking
from .. import util

from ..conf import env

# -----------------------------------------------------------------------------
# Support functions
# -----------------------------------------------------------------------------


def reloadSkinList(context: Context):
	"""Reload the skins in the directory for UI list"""

	skinfolder = context.scene.mcprep_skin_path
	skinfolder = bpy.path.abspath(skinfolder)
	if os.path.isdir(skinfolder):
		files = [
			f for f in os.listdir(skinfolder)
			if os.path.isfile(os.path.join(skinfolder, f))]
	else:
		files = []

	skinlist = []
	for path in files:
		if path.split(".")[-1].lower() not in ["png", "jpg", "jpeg", "tiff"]:
			continue
		skinlist.append((path, f"{path} skin"))

	skinlist = sorted(skinlist, key=lambda x: x[0].lower())

	# clear lists
	context.scene.mcprep_skins_list.clear()
	env.skin_list = []

	# recreate
	for i, (skin, description) in enumerate(skinlist, 1):
		item = context.scene.mcprep_skins_list.add()
		env.skin_list.append(
			(skin, os.path.join(skinfolder, skin))
		)
		item.label = description
		item.description = description
		item.name = skin


def update_skin_path(self, context: Context):
	"""For UI list path callback"""
	env.log("Updating rig path", vv_only=True)
	reloadSkinList(context)


def handler_skins_enablehack(scene):
	"""Scene update to auto load skins on load after new file."""
	try:
		bpy.app.handlers.scene_update_pre.remove(handler_skins_enablehack)
	except:
		pass
	env.log("Triggering Handler_skins_load from first enable", vv_only=True)
	handler_skins_load(scene)


@persistent
def handler_skins_load(scene):
	try:
		env.log("Reloading skins", vv_only=True)
		reloadSkinList(bpy.context)
	except:
		env.log("Didn't run skin reloading callback", vv_only=True)


def loadSkinFile(self, context: Context, filepath: Path, new_material: bool=False, legacy_skin_swap_behavior: bool=False):
	if not os.path.isfile(filepath):
		self.report({'ERROR'}, f"Image file not found: {filepath}")
		return 1
		# special message for library linking?

	# always create a new image block, even if the name already existed
	image = util.loadTexture(filepath)

	if image.channels == 0:
		self.report({'ERROR'}, "Failed to properly load image")
		return 1

	mats, skipped = getMatsFromSelected(context.selected_objects, new_material)
	if not mats:
		self.report({'ERROR'}, "No materials found to update")
		# special message for library linking?
		return 1
	if skipped > 0:
		self.report(
			{'WARNING'}, "Skinswap skipped {} linked objects".format(skipped))

	status = generate.assert_textures_on_materials(image, mats, legacy_skin_swap_behavior)
	if status is False:
		self.report({'ERROR'}, "No image textures found to update")
		return 1
	else:
		pass

	# TODO: adjust the UVs if appropriate, and fix eyes
	if image.size[0] != 0 and image.size[1] / image.size[0] != 1:
		self.report({'INFO'}, "Skin swapper works best on 1.8 skins")
		return 0
	return 0


def convert_skin_layout(image_file: Path) -> bool:
	"""Convert skin to 1.8+ layout if old format detected

	Could be improved using numpy, but avoiding the dependency.
	"""

	if not os.path.isfile(image_file):
		env.log(f"Error! Image file does not exist: {image_file}")
		return False

	img = bpy.data.images.load(image_file)
	if img.size[0] == img.size[1]:
		return False
	elif img.size[0] != img.size[1] * 2:
		# some image that isn't the normal 64x32 of old skin formats
		env.log("Unknown skin image format, not converting layout")
		return False
	elif img.size[0] / 64 != int(img.size[0] / 64):
		env.log("Non-regular scaling of skin image, can't process")
		return False

	env.log("Old image format detected, converting to post 1.8 layout")

	scale = int(img.size[0] / 64)
	has_alpha = img.channels == 4
	new_image = bpy.data.images.new(
		name=os.path.basename(image_file),
		width=img.size[0],
		height=img.size[1] * 2,
		alpha=has_alpha)

	# copy pixels of old format into top half of new format, and save to file
	# and copy the right arm and leg pixels to the lower half
	upper_half = list(img.pixels)
	lower_half_quarter = [0] * int(len(new_image.pixels) / 4)
	lower_half = []
	failout = False

	# Copy over the arm and leg to lower half, accounting for image scale
	# Take it in strips of 16 units at a time per row
	block_width = int(img.size[0] * img.channels / 4)  # quarter of image width
	for i in range(int(len(lower_half_quarter) / block_width)):
		# pixel row rounds down, row 0 = bottom row
		row = int(i * block_width / (64 * scale * img.channels))
		# virtual column, not pixel column
		col = (i * block_width) % (64 * scale * img.channels)
		# 0-3 index, L->R order: blank, leg, arm, blank
		block = int(col / 64)
		if block == 0 or block == 3:
			lower_half += [0] * block_width
		elif block == 1:
			# Here we are copying the leg from block 1/4 (src) into block 2/4
			start = row * block_width * 4
			end = row * block_width * 4 + block_width
			lower_half += upper_half[int(start):int(end)]
		elif block == 2:
			# Here we are copying the arm from block 2.5 (src) into block 3/4
			start = row * block_width * 4 + block_width * 2.5
			end = (row * block_width * 4) + block_width + (block_width * 2.5)
			lower_half += upper_half[int(start):int(end)]
		else:
			env.log("Bad math! Should never go above 4 blocks")
			failout = True
			break

	# Do final combinations of quarters and halves
	if not failout:
		lower_half += lower_half_quarter
		new_pixels = lower_half + upper_half
		new_image.pixels = new_pixels
		new_image.filepath_raw = image_file
		new_image.save()
		env.log("Saved out post 1.8 converted skin file")

	# cleanup files
	img.user_clear()
	new_image.user_clear()
	bpy.data.images.remove(img)
	bpy.data.images.remove(new_image)

	if not failout:
		return True
	else:
		return False


def getMatsFromSelected(selected: List[bpy.types.Object], new_material: bool=False) -> Tuple[List[Material], List[bpy.types.Object]]:
	"""Get materials; if new material provided, ensure material slot is added

	Used by skin swapping, to either update existing material or create new one
	"""
	obj_list = []
	for ob in selected:
		if ob.type == 'MESH':
			obj_list.append(ob)
		elif ob.type == 'ARMATURE':
			for ch in ob.children:
				if ch.type == 'MESH':
					obj_list.append(ch)
		else:
			continue

	obj_list = list(set(obj_list))
	mat_list = []
	mat_ret = []
	linked_objs = 0

	for ob in obj_list:
		if ob.data.library:
			env.log("Library object, skipping")
			linked_objs += 1
			continue
		elif new_material is False:
			for slot in ob.material_slots:
				if slot.material is None:
					continue
				if slot.material not in mat_ret:
					mat_ret.append(slot.material)
		else:
			for slot in ob.material_slots:
				if slot.material not in mat_list:
					if slot.material is None:
						continue
					mat_list.append(slot.material)
					new_mat = slot.material.copy()
					mat_ret.append(new_mat)
					slot.material = new_mat
				else:
					# if already created, re-assign with new material
					slot.material = mat_ret[mat_list.index(slot.material)]

	# if internal, also ensure textures are made unique per new mat
	# TODO Remove 2.7
	engine = bpy.context.scene.render.engine
	if new_material and (engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME'):
		for m in mat_ret:
			for tx in m.texture_slots:
				if tx is None or tx.texture is None:
					continue
				tx.texture = tx.texture.copy()

	return mat_ret, linked_objs


def download_user(self, context: Context, username: str) -> Optional[Path]:
	"""Download user skin from online.

	Reusable function from within two common operators for downloading skin.
	Example link: http://minotar.net/skin/theduckcow
	"""
	env.log(f"Downloading skin: {username}")

	src_link = "http://minotar.net/skin/"
	saveloc = os.path.join(
		bpy.path.abspath(context.scene.mcprep_skin_path),
		username.lower() + ".png")

	try:
		if env.very_verbose:
			print(f"Download starting with url: {src_link} - {username.lower()}")
			print(f"to save location: {saveloc}")
		urllib.request.urlretrieve(src_link + username.lower(), saveloc)
	except urllib.error.HTTPError as e:
		print(e)
		self.report({"ERROR"}, "Could not find username")
		return None
	except urllib.error.URLError as e:
		print(e)
		self.report({"ERROR"}, "URL error, check internet connection")
		return None
	except Exception as e:
		print(f"Error occured while downloading skin: {e}")
		self.report({"ERROR"}, f"Error occured while downloading skin: {e}")
		return None

	# convert to 1.8 skin as needed (double height)
	converted = False
	if self.convert_layout:
		converted = convert_skin_layout(saveloc)
	if converted:
		self.track_param = "username + 1.8 convert"
	else:
		self.track_param = "username"
	return saveloc


# -----------------------------------------------------------------------------
# Operators / UI classes
# -----------------------------------------------------------------------------


class MCPREP_UL_skins(bpy.types.UIList):
	"""For asset listing UIList drawing"""
	bl_idname = "MCPREP_UL_skins"
	def draw_item(
		self, context, layout, data, set, icon, active_data, active_propname, index):
		layout.prop(set, "name", text="", emboss=False)
		# extra code for placing warning if skin is
		# not square, ie old texture and reocmmend converting it
		# would need to load all images first though.


class ListColl(bpy.types.PropertyGroup):
	"""For asset listing"""
	label: bpy.props.StringProperty()
	description: bpy.props.StringProperty()


class MCPREP_OT_swap_skin_from_file(bpy.types.Operator, ImportHelper):
	"""Swap the skin of a rig (character, mob, etc) with another file"""
	bl_idname = "mcprep.skin_swapper"
	bl_label = "Swap skin"
	bl_options = {'REGISTER', 'UNDO'}

	filter_glob: bpy.props.StringProperty(
		default="",
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	files: bpy.props.CollectionProperty(
		type=bpy.types.PropertyGroup,
		options={'HIDDEN', 'SKIP_SAVE'})
	filter_image: bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'})
	new_material: bpy.props.BoolProperty(
		name="New Material",
		description="Create a new material instead of overwriting existing one",
		default=True)
	legacy_skin_swap_behavior: bpy.props.BoolProperty(
		name="Use Legacy Skin Swap Behavior",
		description="Swap textures in all image nodes that exist on the selected material; will be deprecated in the next release",
		default=False)
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	track_function = "skin"
	track_param = "file import"
	@tracking.report_error
	def execute(self, context):
		res = loadSkinFile(self, context, self.filepath, self.new_material, self.legacy_skin_swap_behavior)
		if res != 0:
			return {'CANCELLED'}

		return {'FINISHED'}


class MCPREP_OT_apply_skin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyskin"
	bl_label = "Apply skin"
	bl_description = "Apply the active UV image to selected character materials"
	bl_options = {'REGISTER', 'UNDO'}

	filepath: bpy.props.StringProperty(
		name="Skin",
		description="selected",
		options={'HIDDEN'})
	new_material: bpy.props.BoolProperty(
		name="New Material",
		description="Create a new material instead of overwriting existing one",
		default=True)
	legacy_skin_swap_behavior: bpy.props.BoolProperty(
		name="Use Legacy Skin Swap Behavior",
		description="Swap textures in all image nodes that exist on the selected material; will be deprecated in the next release",
		default=False)
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "skin"
	track_param = "ui list"
	@tracking.report_error
	def execute(self, context):
		res = loadSkinFile(self, context, self.filepath, self.new_material, self.legacy_skin_swap_behavior)
		if res != 0:
			return {'CANCELLED'}

		return {'FINISHED'}


class MCPREP_OT_apply_username_skin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyusernameskin"
	bl_label = "Skin from user"
	bl_description = "Download and apply skin from specific username"
	bl_options = {'REGISTER', 'UNDO'}

	username: bpy.props.StringProperty(
		name="Username",
		description="Exact name of user to get texture from",
		default="")
	skip_redownload: bpy.props.BoolProperty(
		name="Skip download if skin already local",
		description="Avoid re-downloading skin and apply local file instead",
		default=True)
	new_material: bpy.props.BoolProperty(
		name="New Material",
		description="Create a new material instead of overwriting existing one",
		default=True)
	convert_layout: bpy.props.BoolProperty(
		name="Convert pre 1.8 skins",
		description=(
			"If an older skin layout (pre Minecraft 1.8) is detected, convert "
			"to new format (with clothing layers)"),
		default=True)
	legacy_skin_swap_behavior: bpy.props.BoolProperty(
		name="Use Legacy Skin Swap Behavior",
		description="Swap textures in all image nodes that exist on the selected material; will be deprecated in the next release",
		default=False)
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

	def draw(self, context):
		self.layout.label(text="Enter exact Minecraft username below")
		self.layout.prop(self, "username", text="")
		self.layout.prop(self, "skip_redownload")
		self.layout.label(
			text="and then press OK; blender may pause briefly to download")

	track_function = "skin"
	track_param = "username"
	@tracking.report_error
	def execute(self, context):
		if self.username == "":
			self.report({"ERROR"}, "Invalid username")
			return {'CANCELLED'}

		user_ref = self.username.lower() + ".png"

		skins = [str(skin[0]).lower() for skin in env.skin_list]
		paths = [skin[1] for skin in env.skin_list]
		if user_ref not in skins or not self.skip_redownload:
			# Do the download
			saveloc = download_user(self, context, self.username)
			if not saveloc:
				return {'CANCELLED'}

			# Now load the skin
			res = loadSkinFile(self, context, saveloc, self.new_material, self.legacy_skin_swap_behavior)
			if res != 0:
				return {'CANCELLED'}
			bpy.ops.mcprep.reload_skins()
			return {'FINISHED'}
		else:
			env.log("Reusing downloaded skin")
			ind = skins.index(user_ref)
			res = loadSkinFile(self, context, paths[ind], self.new_material, self.legacy_skin_swap_behavior)
			if res != 0:
				return {'CANCELLED'}
			return {'FINISHED'}


class MCPREP_OT_skin_fix_eyes():  # bpy.types.Operator
	"""Fix the eyes of a rig to fit a rig"""
	bl_idname = "mcprep.fix_skin_eyes"
	bl_label = "Fix eyes"
	bl_description = "Fix the eyes of a rig to fit a rig"
	bl_options = {'REGISTER', 'UNDO'}

	# initial_eye_type: unknown (default), 2x2 square, 1x2 wide.

	@tracking.report_error
	def execute(self, context):
		# take the active texture input (based on selection)
		print("fix eyes")
		self.report({'ERROR'}, "Work in progress operator")
		return {'CANCELLED'}


class MCPREP_OT_add_skin(bpy.types.Operator, ImportHelper):
	bl_idname = "mcprep.add_skin"
	bl_label = "Add skin"
	bl_description = "Add a new skin to the active folder"

	# filename_ext = ".zip" # needs to be only tinder
	filter_glob: bpy.props.StringProperty(default="*", options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	files: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

	convert_layout: bpy.props.BoolProperty(
		name="Convert pre 1.8 skins",
		description=(
			"If an older skin layout (pre Minecraft 1.8) is detected, convert "
			"to new format (with clothing layers)"),
		default=True)
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	track_function = "add_skin"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		source_location = bpy.path.abspath(self.filepath)
		base = os.path.basename(source_location)
		new_location = os.path.join(context.scene.mcprep_skin_path, base)
		new_location = bpy.path.abspath(new_location)
		if os.path.isfile(source_location) is False:
			self.report({"ERROR"}, "Not a image file path")
			return {'CANCELLED'}
		elif source_location == new_location:
			self.report({"WARNING"}, "File already installed")
			return {'CANCELLED'}
		elif os.path.isdir(os.path.dirname(new_location)) is False:
			self.report({"ERROR"}, "Target folder for installing does not exist")
			return {'CANCELLED'}

		# copy the skin file, overwritting if appropriate
		if os.path.isfile(new_location):
			os.remove(new_location)
		shutil.copy2(source_location, new_location)

		# convert to 1.8 skin as needed (double height)
		converted = False
		if self.convert_layout:
			converted = convert_skin_layout(new_location)
		if converted is True:
			self.track_param = "1.8 convert"
		else:
			self.track_param = None

		# in future, select multiple
		bpy.ops.mcprep.reload_skins()
		self.report({"INFO"}, "Added 1 skin")  # more in the future

		return {'FINISHED'}


class MCPREP_OT_remove_skin(bpy.types.Operator):
	bl_idname = "mcprep.remove_skin"
	bl_label = "Remove skin"
	bl_description = "Remove a skin from the active folder (will delete file)"

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

	def draw(self, context):
		skin_path = env.skin_list[context.scene.mcprep_skins_list_index]
		col = self.layout.column()
		col.scale_y = 0.7
		col.label(text=f"Warning, will delete file {os.path.basename(skin_path[0])} from")
		col.label(text=os.path.dirname(skin_path[-1]))

	@tracking.report_error
	def execute(self, context):

		if not env.skin_list:
			self.report({"ERROR"}, "No skins loaded in memory, try reloading")
			return {'CANCELLED'}
		if context.scene.mcprep_skins_list_index >= len(env.skin_list):
			self.report({"ERROR"}, "Indexing error")
			return {'CANCELLED'}

		file = env.skin_list[context.scene.mcprep_skins_list_index][-1]

		if os.path.isfile(file) is False:
			self.report({"ERROR"}, "Skin not found to delete")
			return {'CANCELLED'}
		os.remove(file)

		# refresh the folder
		bpy.ops.mcprep.reload_skins()
		if context.scene.mcprep_skins_list_index >= len(env.skin_list):
			context.scene.mcprep_skins_list_index = len(env.skin_list) - 1

		# in future, select multiple
		self.report({"INFO"}, f"Removed {bpy.path.basename(file)}")

		return {'FINISHED'}


class MCPREP_OT_reload_skin(bpy.types.Operator):
	bl_idname = "mcprep.reload_skins"
	bl_label = "Reload skins"
	bl_description = "Reload the skins folder"

	@tracking.report_error
	def execute(self, context):
		skinfolder = context.scene.mcprep_skin_path
		skinfolder = bpy.path.abspath(skinfolder)
		reloadSkinList(context)  # run load even if none found
		if not os.path.isdir(skinfolder):
			self.report({'ERROR'}, "Skin directory does not exist")
			return {'CANCELLED'}
		return {'FINISHED'}


class MCPREP_OT_reset_skin_path(bpy.types.Operator):
	bl_idname = "mcprep.skin_path_reset"
	bl_label = "Reset skin path"
	bl_description = "Reset the skins folder"

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_skin_path = addon_prefs.skin_path
		return {'FINISHED'}


class MCPREP_OT_spawn_mob_with_skin(bpy.types.Operator):
	bl_idname = "mcprep.spawn_with_skin"
	bl_label = "Spawn with skin"
	bl_description = "Spawn rig and apply selected skin"

	relocation: bpy.props.EnumProperty(
		items=[
			('Cursor', 'Cursor', 'No relocation'),
			('Clear', 'Origin', 'Move the rig to the origin'),
			('Offset', 'Offset root', (
				'Offset the root bone to curse while moving the rest pose to '
				'the origin'))],
		name="Relocation")
	toLink: bpy.props.BoolProperty(
		name="Library Link",
		description="Library link instead of append the group",
		default=False)
	clearPose: bpy.props.BoolProperty(
		name="Clear Pose",
		description="Clear the pose to rest position",
		default=True)
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	track_function = "spawn_with_skin"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		scn_props = context.scene.mcprep_props
		if not env.skin_list:
			self.report({'ERROR'}, "No skins found")
			return {'CANCELLED'}

		mob = scn_props.mob_list[scn_props.mob_list_index]
		self.track_param = mob.name

		bpy.ops.mcprep.mob_spawner(
			mcmob_type=mob.mcmob_type,
			relocation=self.relocation,
			toLink=self.toLink,
			clearPose=self.clearPose,
			skipUsage=True)

		# bpy.ops.mcprep.spawn_with_skin() spawn based on active mob
		ind = context.scene.mcprep_skins_list_index
		_ = loadSkinFile(self, context, env.skin_list[ind][1])

		return {'FINISHED'}


class MCPREP_OT_download_username_list(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.download_username_list"
	bl_label = "Download username list"
	bl_description = "Download a list of skins from comma-separated usernames"
	bl_options = {'REGISTER', 'UNDO'}

	username_list: bpy.props.StringProperty(
		name="Username list",
		description="Comma-separated list of usernames to download.",
		default=""
	)
	skip_redownload: bpy.props.BoolProperty(
		name="Skip download if skin already local",
		description="Avoid re-downloading skin and apply local file instead",
		default=True
	)
	convert_layout: bpy.props.BoolProperty(
		name="Convert pre 1.8 skins",
		description=(
			"If an older skin layout (pre Minecraft 1.8) is detected, convert "
			"to new format (with clothing layers)"),
		default=True
	)
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'}
	)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400 * util.ui_scale())

	def draw(self, context):
		self.layout.label(text="Enter comma-separted list of usernames below")
		self.layout.prop(self, "username_list", text="")
		self.layout.prop(self, "skip_redownload")
		self.layout.label(
			text="and then press OK; blender may pause briefly to download")

	track_function = "skin"
	track_param = "username_list"
	@tracking.report_error
	def execute(self, context):
		if self.username_list == "":
			self.report({"ERROR"}, "Username list is empty!")
			return {'CANCELLED'}
		# Take comma-separated string, split into list and remove whitespace.
		user_list = [skn.strip() for skn in self.username_list.split(",")]
		user_list = list(set(user_list))  # Make list unique.

		# Currently loaded
		skins = [str(skin[0]).lower() for skin in env.skin_list]
		issue_skins = []
		for username in user_list:
			if username.lower() not in skins or not self.skip_redownload:
				saveloc = download_user(self, context, username)
				if not saveloc:
					issue_skins.append(username)

		bpy.ops.mcprep.reload_skins()

		if issue_skins and len(issue_skins) == len(user_list):
			self.report({"ERROR"}, "Failed to download any skins, see console.")
			return {'CANCELLED'}
		elif issue_skins and len(issue_skins) < len(user_list):
			self.report(
				{"WARNING"},
				f"Could not download {len(issue_skins)} of {len(user_list)} skins, see console")
			return {'FINISHED'}
		else:
			self.report({"INFO"}, f"Downloaded {len(user_list)} skins")
			return {'FINISHED'}


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_UL_skins,
	ListColl,
	MCPREP_OT_swap_skin_from_file,
	MCPREP_OT_apply_skin,
	MCPREP_OT_apply_username_skin,
	MCPREP_OT_download_username_list,
	# MCPREP_OT_skin_fix_eyes,
	MCPREP_OT_add_skin,
	MCPREP_OT_remove_skin,
	MCPREP_OT_reload_skin,
	MCPREP_OT_reset_skin_path,
	MCPREP_OT_spawn_mob_with_skin,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Scene.mcprep_skins_list = bpy.props.CollectionProperty(
		type=ListColl)
	bpy.types.Scene.mcprep_skins_list_index = bpy.props.IntProperty(default=0)

	# to auto-load the skins
	env.log("Adding reload skin handler to scene", vv_only=True)
	try:
		bpy.app.handlers.scene_update_pre.append(handler_skins_enablehack)
	except:
		print("Failed to register scene update handler")
	bpy.app.handlers.load_post.append(handler_skins_load)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	del bpy.types.Scene.mcprep_skins_list
	del bpy.types.Scene.mcprep_skins_list_index

	try:
		bpy.app.handlers.load_post.remove(handler_skins_load)
		bpy.app.handlers.scene_update_pre.remove(handler_skins_enablehack)
	except:
		pass
