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
import bpy
import os
import math
from bpy_extras.io_utils import ImportHelper
import shutil
import urllib.request
from bpy.app.handlers import persistent

# addon imports
from .. import conf
from . import generate
from .. import tracking
from .. import util


# -----------------------------------------------------------------------------
# Support functions
# -----------------------------------------------------------------------------


def reloadSkinList(context):
	"""Reload the skins in the directory for UI list"""

	skinfolder = context.scene.mcprep_skin_path
	skinfolder = bpy.path.abspath(skinfolder)
	files = [ f for f in os.listdir(skinfolder) if\
					os.path.isfile(os.path.join(skinfolder,f)) ]

	skinlist = []
	for path in files:
		if path.split(".")[-1].lower() not in ["png","jpg","jpeg","tiff"]:
			continue
		skinlist.append( (path, "{x} skin".format(x=path)) )

	# clear lists
	context.scene.mcprep_skins_list.clear()
	conf.skin_list = []

	# recreate
	for i, (skin, description) in enumerate(skinlist, 1):
		item = context.scene.mcprep_skins_list.add()
		conf.skin_list.append(  (skin,os.path.join(skinfolder,skin))  )
		item.label = description
		item.description = description
		item.name = skin


def update_skin_path(self, context):
	"""For UI list path callback"""
	if conf.vv: print("Updating rig path")
	reloadSkinList(context)


# scene update to auto load skins on load after new file
def handler_skins_enablehack(scene):
	try:
		bpy.app.handlers.scene_update_pre.remove(handler_skins_enablehack)
	except:
		pass
	if conf.vv:print("Triggering Handler_skins_load from first enable")
	handler_skins_load(scene)


@persistent
def handler_skins_load(scene):
	if conf.vv: print("Handler_skins_load running")

	try:
		if conf.vv: print("Reloading skins")
		reloadSkinList(bpy.context)
	except:
		if conf.v: print("Didn't run skin reloading callback")
		pass


def loadSkinFile(self, context, filepath, new_material=False):
	if not os.path.isfile(filepath):
		self.report({'ERROR'}, "Image file not found")
		return 1
		# special message for library linking?

	# always create a new image block, even if the name already existed
	image = util.loadTexture(filepath)

	if image.channels == 0:
		self.report({'ERROR'}, "Failed to properly load image")
		return 1

	mats = getMatsFromSelected(context.selected_objects,new_material)
	if len(mats)==0:
		self.report({'ERROR'}, "No materials found to update")
		# special message for library linking?
		return 1

	status = generate.assert_textures_on_materials(image, mats)
	if status is False:
		self.report({'ERROR'}, "No image textures found to update")
		return 1
	else:
		pass

	setUVimage(context.selected_objects, image)

	# TODO: adjust the UVs if appropriate, and fix eyes
	if image.size[0] != 0 and image.size[1]/image.size[0] != 1:
		self.report({'INFO'}, "Skin swapper works best on 1.8 skins")
		return 0
	return 0


def convert_skin_layout(image_file):
	"""Convert skin to 1.8+ layout if old format detected

	Could be improved using numpy, but avoiding the dependency.
	"""

	if not os.path.isfile(image_file):
		conf.log("Error! Image file does not exist: "+image_file)
		return False

	img = bpy.data.images.load(image_file)
	if img.size[0] == img.size[1]:
		return False
	elif img.size[0] != img.size[1]*2:
		# some image that isn't the normal 64x32 of old skin formats
		conf.log("Unknown skin image format, not converting layout")
		return False
	elif img.size[0]/64 != int(img.size[0]/64):
		conf.log("Non-regular scaling of skin image, can't process")
		return False

	conf.log("Old image format detected, converting to post 1.8 layout")

	scale = int(img.size[0]/64)
	has_alpha = img.channels == 4
	new_image = bpy.data.images.new(
		name=os.path.basename(image_file),
		width=img.size[0],
		height=img.size[1]*2,
		alpha=has_alpha)

	# copy pixels of old format into top half of new format, and save to file
	# and copy the right arm and leg pixels to the lower half
	upper_half = list(img.pixels)
	lower_half_quarter = [0]*int(len(new_image.pixels)/4)
	lower_half = []
	failout = False

	# Copy over the arm and leg to lower half, accounting for image scale
	# Take it in strips of 16 units at a time per row
	block_width = int(img.size[0]*img.channels/4) # quarter of image width
	for i in range(int(len(lower_half_quarter)/block_width)):
		# pixel row rounds down, row 0 = bottom row
		row = int(i*block_width/(64*scale*img.channels))
		# virtual column, not pixel column
		col = (i*block_width)%(64*scale*img.channels)
		# 0-3 index, L->R order: blank, leg, arm, blank
		block = int(col/64)
		if block == 0 or block == 3:
			lower_half += [0]*block_width
		elif block == 1:
			# Here we are copying the leg from block 1/4 (src) into block 2/4
			start = row*block_width*4
			end = row*block_width*4 + block_width
			lower_half += upper_half[int(start):int(end)]
		elif block == 2:
			# Here we are copying the arm from block 2.5 (src) into block 3/4
			start = row*block_width*4 + block_width*2.5
			end = row*block_width*4 + block_width + block_width*2.5
			lower_half += upper_half[int(start):int(end)]
		else:
			conf.log("Bad math! Should never go above 4 blocks")
			failout = True
			break

	# Do final combinations of quarters and halves
	if not failout:
		lower_half += lower_half_quarter
		new_pixels = lower_half + upper_half
		new_image.pixels = new_pixels
		new_image.filepath_raw = image_file
		new_image.save()
		conf.log("Saved out post 1.8 converted skin file")

	# cleanup files
	img.user_clear()
	new_image.user_clear()
	bpy.data.images.remove(img)
	bpy.data.images.remove(new_image)

	if not failout:
		return True
	else:
		return False


def getMatsFromSelected(selected,new_material=False):
	"""Get materials, and if new material provided, ensure material slot
	is added"""
	obj_list = []

	for ob in selected:
		if ob.type == 'MESH':
			obj_list.append(ob)
		elif ob.type == 'ARMATURE':
			for ch in ob.children:
				if ch.type == 'MESH': obj_list.append(ch)
		else:
			continue

	mat_list = []
	mat_ret = []
	for ob in obj_list:
		if new_material is False:
			for slot in ob.material_slots:
				if slot.material is None: continue
				if slot.material not in mat_ret:
					mat_ret.append(slot.material)
		else:
			for slot in ob.material_slots:
				if slot.material not in mat_list:
					if slot.material is None: continue
					mat_list.append(slot.material)
					new_mat = slot.material.copy()
					mat_ret.append(new_mat)
					slot.material = new_mat
				else:
					# if already created, re-assign with new material
					slot.material = mat_ret[ mat_list.index(slot.material) ]

	# if internal, also ensure textures are made unique per new mat
	engine = bpy.context.scene.render.engine
	if new_material and (engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME'):
		for m in mat_ret:
			for tx in m.texture_slots:
				if tx is None or tx.texture is None:
					continue
				tx.texture = tx.texture.copy()

	return mat_ret


def setUVimage(objs, image):
	"""Set image for each face for viewport displaying."""
	for obj in objs:
		if obj.type != "MESH":
			continue
		if obj.data.uv_textures.active is None:
			continue
		for uv_face in obj.data.uv_textures.active.data:
			uv_face.image = image


# -----------------------------------------------------------------------------
# Operators / UI classes
# -----------------------------------------------------------------------------


class McprepSkinUiList(bpy.types.UIList):
	"""For asset listing UIList drawing"""
	def draw_item(self, context, layout, data, set, icon,
					active_data, active_propname, index):
		layout.prop(set, "name", text="", emboss=False)
		# extra code for placing warning if skin is
		# not square, ie old texture and reocmmend converting it
		# would need to load all images first though.


class ListColl(bpy.types.PropertyGroup):
	"""For asset listing"""
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()


class McprepSkinSwapper(bpy.types.Operator, ImportHelper):
	"""Swap the skin of a rig (character, mob, etc) with another file"""
	bl_idname = "mcprep.skin_swapper"
	bl_label = "Swap skin"
	bl_options = {'REGISTER', 'UNDO'}

	filter_glob = bpy.props.StringProperty(
		default="",
		options={'HIDDEN'})
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(
		type=bpy.types.PropertyGroup,
		options={'HIDDEN', 'SKIP_SAVE'})
	filter_image = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'})

	track_function = "skin"
	track_param = "file import"
	@tracking.report_error
	def execute(self,context):
		res = loadSkinFile(self, context, self.filepath)
		if res!=0:
			return {'CANCELLED'}

		return {'FINISHED'}


class McprepApplySkin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyskin"
	bl_label = "Apply skin"
	bl_description = "Apply the active UV image to selected character materials"
	bl_options = {'REGISTER', 'UNDO'}

	filepath = bpy.props.StringProperty(
		name = "Skin",
		description = "selected",
		options = {'HIDDEN'}
		)
	new_material = bpy.props.BoolProperty(
		name = "New Material",
		description = "Create a new material instead of overwriting existing one",
		default = True
		)

	track_function = "skin"
	track_param = "ui list"
	@tracking.report_error
	def execute(self,context):
		res = loadSkinFile(self, context, self.filepath, self.new_material)
		if res!=0:
			return {'CANCELLED'}

		return {'FINISHED'}


class McprepApplyUsernameSkin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyusernameskin"
	bl_label = "Skin from user"
	bl_description = "Download and apply skin from specific username"
	bl_options = {'REGISTER', 'UNDO'}

	username = bpy.props.StringProperty(
		name="Username",
		description="Exact name of user to get texture from",
		default=""
	)
	skip_redownload = bpy.props.BoolProperty(
		name="Skip download if skin already local",
		description="Avoid re-downloading skin and apply local file instead",
		default=True
	)
	new_material = bpy.props.BoolProperty(
		name = "New Material",
		description = "Create a new material instead of overwriting existing one",
		default = True
	)
	convert_layout = bpy.props.BoolProperty(
		name = "Convert pre 1.8 skins",
		description = "If an older skin layout (pre Minecraft 1.8) is detected, convert to new format (with clothing layers)",
		default = True
	)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self,
			width=400*util.ui_scale())

	def draw(self, context):
		self.layout.label("Enter exact Minecraft username below")
		self.layout.prop(self,"username",text="")
		self.layout.prop(self,"skip_redownload")
		self.layout.label(
			"and then press OK; blender may pause briefly to download")

	track_function = "skin"
	track_param = "username"
	@tracking.report_error
	def execute(self,context):
		if self.username == "":
			self.report({"ERROR"},"Invalid username")
			return {'CANCELLED'}

		skins = [ str(skin[0]).lower() for skin in conf.skin_list ]
		paths = [ skin[1] for skin in conf.skin_list ]
		if self.username.lower() not in skins or not self.skip_redownload:
			if conf.v:
				print("Downloading skin")
			res = self.download_user(context)
			return res
		else:
			conf.log("Reusing downloaded skin")
			ind = skins.index(self.username.lower())
			res = loadSkinFile(self, context, paths[ind][1], self.new_material)
			if res != 0:
				return {'CANCELLED'}
			return {'FINISHED'}

	def download_user(self, context):
		"""Download user skin from online.

		Example link: http://minotar.net/skin/theduckcow
		"""

		src_link = "http://minotar.net/skin/"
		saveloc = os.path.join(bpy.path.abspath(context.scene.mcprep_skin_path),
								self.username.lower()+".png")

		try:
			if conf.vv:
				print("Download starting with url: "+src_link+self.username.lower())
				print("to save location: "+saveloc)
			urllib.request.urlretrieve(src_link+self.username.lower(), saveloc)
		except urllib.error.HTTPError as e:
			self.report({"ERROR"},"Could not find username")
			return {'CANCELLED'}
		except urllib.error.URLError as e:
			self.report({"ERROR"},"URL error, check internet connection")
			return {'CANCELLED'}
		except Exception as e:
			self.report({"ERROR"},"Error occured while downloading skin: "+str(e))
			return {'CANCELLED'}

		# convert to 1.8 skin as needed (double height)
		converted = False
		if self.convert_layout:
			converted = convert_skin_layout(saveloc)
		if converted:
			self.track_param = "username + 1.8 convert"
		else:
			self.track_param = "username"

		res = loadSkinFile(self, context, saveloc, self.new_material)
		if res != 0:
			return {'CANCELLED'}
		bpy.ops.mcprep.reload_skins()
		return {'FINISHED'}


class McprepSkinFixEyes():  # bpy.types.Operator
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


class McprepAddSkin(bpy.types.Operator, ImportHelper):
	bl_idname = "mcprep.add_skin"
	bl_label = "Add skin"
	bl_description = "Add a new skin to the active folder"

	# filename_ext = ".zip" # needs to be only tinder
	filter_glob = bpy.props.StringProperty(
			default="*",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

	convert_layout = bpy.props.BoolProperty(
		name = "Convert pre 1.8 skins",
		description = "If an older skin layout (pre Minecraft 1.8) is detected, convert to new format (with clothing layers)",
		default = True
	)

	track_function = "add_skin"
	track_param = None
	@tracking.report_error
	def execute(self,context):

		source_location = bpy.path.abspath(self.filepath)
		base = os.path.basename(source_location)
		new_location = os.path.join(context.scene.mcprep_skin_path, base)
		if os.path.isfile(source_location) == False:
			self.report({"ERROR"}, "Not a image file path")
			return {'CANCELLED'}
		elif source_location == new_location:
			self.report({"WARNING"}, "File already installed")
			return {'CANCELLED'}
		elif os.path.isdir(os.path.dirname(new_location)) == False:
			self.report({"ERROR"}, "Target folder for installing does not exist")
			return {'CANCELLED'}

		# copy the skin file
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
		self.report({"INFO"},"Added 1 skin") # more in the future

		return {'FINISHED'}


class McprepRemoveSkin(bpy.types.Operator):
	bl_idname = "mcprep.remove_skin"
	bl_label = "Remove skin"
	bl_description = "Remove a skin from the active folder (will delete file)"

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(
			self, width=400*util.ui_scale())

	def draw(self, context):
		skin_path = conf.skin_list[context.scene.mcprep_skins_list_index]
		col = self.layout.column()
		col.scale_y = 0.7
		col.label("Warning, will delete file {} from".format(
			os.path.basename(skin_path[0])))
		col.label(os.path.dirname(skin_path[-1]))

	@tracking.report_error
	def execute(self,context):

		if context.scene.mcprep_skins_list_index >= len(conf.skin_list):
			self.report({"ERROR"},"Indexing error")
			return {'CANCELLED'}

		file = conf.skin_list[context.scene.mcprep_skins_list_index][-1]

		if os.path.isfile(file) == False:
			self.report({"ERROR"},"Skin not found to delete")
			return {'CANCELLED'}
		os.remove(file)

		# refresh the folder
		bpy.ops.mcprep.reload_skins()
		if context.scene.mcprep_skins_list_index >= len(conf.skin_list):
			context.scene.mcprep_skins_list_index = len(conf.skin_list)-1

		# in future, select multiple
		self.report({"INFO"},"Removed "+bpy.path.basename(file))

		return {'FINISHED'}


class McprepReloadSkins(bpy.types.Operator):
	bl_idname = "mcprep.reload_skins"
	bl_label = "Reload skins"
	bl_description = "Reload the skins folder"

	@tracking.report_error
	def execute(self, context):
		reloadSkinList(context)
		return {'FINISHED'}


class McprepResetSkinPath(bpy.types.Operator):
	bl_idname = "mcprep.skin_path_reset"
	bl_label = "Reset skin path"
	bl_description = "Reset the skins folder"

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_prefs()
		context.scene.mcprep_skin_path = addon_prefs.skin_path
		return {'FINISHED'}


class McprepSpawn_with_skin(bpy.types.Operator):
	bl_idname = "mcprep.spawn_with_skin"
	bl_label = "Spawn with skin"
	bl_description = "Spawn rig and apply selected skin"

	relocation = bpy.props.EnumProperty(
		items = [('Cursor', 'Cursor', 'No relocation'),
				('Origin', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root',
					'Offset the root bone to curse while moving the rest pose to the origin')],
		name = "Relocation")
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

	track_function = "spawn_with_skin"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		scn_props = context.scene.mcprep_props
		if len (conf.skin_list)>0:
			skinname = bpy.path.basename(
					conf.skin_list[context.scene.mcprep_skins_list_index][0] )
		else:
			self.report({'ERROR'}, "No skins found")
			return {'CANCELLED'}

		mob = scn_props.mob_list[scn_props.mob_list_index]
		self.track_param = mob.name

		# try not to use internal ops because of analytics
		bpy.ops.mcprep.mob_spawner(
				mcmob_type=mob.mcmob_type,
				relocation = self.relocation,
				toLink = self.toLink,
				clearPose = self.clearPose)

		# bpy.ops.mcprep.spawn_with_skin() spawn based on active mob
		ind = context.scene.mcprep_skins_list_index
		bpy.ops.mcprep.applyskin(filepath=conf.skin_list[ind][1])

		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	bpy.types.Scene.mcprep_skins_list = bpy.props.CollectionProperty(
		type=ListColl)
	bpy.types.Scene.mcprep_skins_list_index = bpy.props.IntProperty(default=0)

	# to auto-load the skins
	conf.log("Adding reload skin handler to scene", vv_only=True)
	try:
		bpy.app.handlers.scene_update_pre.append(handler_skins_enablehack)
	except:
		print("Failed to register scene update handler")
	bpy.app.handlers.load_post.append(handler_skins_load)


def unregister():
	del bpy.types.Scene.mcprep_skins_list
	del bpy.types.Scene.mcprep_skins_list_index

	try:
		bpy.app.handlers.load_post.remove(handler_skins_load)
		bpy.app.handlers.scene_update_pre.remove(handler_skins_enablehack)
	except:
		pass
