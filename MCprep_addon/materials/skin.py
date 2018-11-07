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

	setUVimage(context.selected_objects,image)

	# TODO: adjust the UVs if appropriate, and fix eyes
	if image.size[0] != 0 and image.size[1]/image.size[0] != 1:
		self.report({'INFO'}, "Skin swapper works best on 1.8 skins")
		return 0
	return 0


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


def setUVimage(objs,image):
	for ob in objs:
		if ob.type != "MESH": continue
		if ob.data.uv_textures.active is None: continue
		for uv_face in ob.data.uv_textures.active.data:
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

	# filename_ext = ".zip"
	filter_glob = bpy.props.StringProperty(
			default="*",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

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
		default = True,
		options = {'HIDDEN'})

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
		default="")

	skip_redownload = bpy.props.BoolProperty(
		name="Skip download if skin already local",
		description="Avoid re-downloading skin and apply local file instead",
		default=True)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

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
			if conf.v: print("Reusing downloaded skin")
			ind = skins.index(self.username.lower())
			res = loadSkinFile(self, context, paths[ind][1])
			if res != 0:
				return {'CANCELLED'}
			return {'FINISHED'}

	def download_user(self, context):
		#http://minotar.net/skin/theduckcow
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

		res = loadSkinFile(self, context, saveloc)
		if res != 0:
			return {'CANCELLED'}
		bpy.ops.mcprep.reload_skins()
		return {'FINISHED'}


class McprepSkinFixEyes():  # bpy.types.Operator
	"""AFix the eyes of a rig to fit a rig"""
	bl_idname = "mcprep.fix_skin_eyes"
	bl_label = "Fix eyes"
	bl_description = "Fix the eyes of a rig to fit a rig"
	bl_options = {'REGISTER', 'UNDO'}

	# initial_eye_type: unknown (default), 2x2 square, 1x2 wide.

	@tracking.report_error
	def execute(self,context):
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

		# in future, select multiple
		bpy.ops.mcprep.reload_skins()
		self.report({"INFO"},"Added 1 skin") # more in the future

		return {'FINISHED'}


class McprepRemoveSkin(bpy.types.Operator):
	bl_idname = "mcprep.remove_skin"
	bl_label = "Remove skin"
	bl_description = "Remove a skin from the active folder (will delete file)"

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

	def draw(self, context):
		skin_path = conf.skin_list[context.scene.mcprep_skins_list_index]
		col = self.layout.column()
		col.scale_y = 0.7
		col.label("Warning, will delete file:")
		col.label("File: "+os.path.basename(skin_path[0]))
		col.label("Folder: "+os.path.dirname(skin_path[-1]))

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
		items = [('None', 'Cursor', 'No relocation'),
				('Clear', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root','Offset the root bone to curse while moving the rest pose to the origin')],
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
		if len (conf.skin_list)>0:
			skinname = bpy.path.basename(
					conf.skin_list[context.scene.mcprep_skins_list_index][0] )
		else:
			self.report({'ERROR'}, "No skins found")
			return {'CANCELLED'}

		active_mob = conf.rig_list_sub[context.scene.mcprep_mob_list_index][0]
		self.track_param = active_mob

		# try not to use internal ops because of analytics
		bpy.ops.mcprep.mob_spawner(
				mcmob_type=active_mob,
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
	bpy.types.Scene.mcprep_skins_list = \
			bpy.props.CollectionProperty(type=ListColl)
	bpy.types.Scene.mcprep_skins_list_index = bpy.props.IntProperty(default=0)

	# to auto-load the skins
	if conf.vv:print("Adding reload skin handler to scene")
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
