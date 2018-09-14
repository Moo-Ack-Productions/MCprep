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
from . import sequences
from .. import tracking
from .. import util


# -----------------------------------------------------------------------------
# Material class functions
# -----------------------------------------------------------------------------


class McprepPrepMaterials(bpy.types.Operator):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "mcprep.prep_materials"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

	animateTextures = bpy.props.BoolProperty(
		name = "Animate textures (may be slow first time)",
		description = "Swap still images for the animated sequenced found in the active or default texturepack.",
		default = False)
	autoFindMissingTextures = bpy.props.BoolProperty(
		name = "Auto-find missing images",
		description = "If the texture for an existing material is missing, try "+\
				"to load from the default texturepack instead",
		default = True
		)
	combineMaterials = bpy.props.BoolProperty(
		name = "Combine materials",
		description = "Consolidate duplciate materials & textures",
		default = False
		)
	improveUiSettings = bpy.props.BoolProperty(
		name = "Improve UI",
		description = "Automatically improve relevant UI settings",
		default = True)
	usePrincipledShader = bpy.props.BoolProperty(
		name = "Use Principled Shader (if available)",
		description = "If available and using cycles, build materials using the "+\
				"principled shader",
		default = True
		)
	useReflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropriate materials to be rendered reflective",
		default = True
		)

	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)
	# prop: set all blocks as solid (no transparency), assume has trans, or compute check

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		col.prop(self, "useReflections")
		col.prop(self, "animateTextures")
		col.prop(self, "combineMaterials")
		col.prop(self, "autoFindMissingTextures")
		engine = context.scene.render.engine
		if engine=='CYCLES' or engine=='BLENDER_EEVEE':
			col.prop(self, "usePrincipledShader")
		col.prop(self, "improveUiSettings")

	track_function = "materials"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):

		# get list of selected objects
		obj_list = context.selected_objects
		if len(obj_list)==0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if len(obj_list)==0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		# check if linked material exists
		engine = context.scene.render.engine
		count = 0

		for mat in mat_list:
			# TODO: run differently if a linked material
			passes = generate.get_textures(mat)
			if self.autoFindMissingTextures:
				for pass_name in passes:
					res = generate.replace_missing_texture(passes[pass_name])
					if res>0:
						mat["texture_swapped"] = True  # used to apply saturation
			if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
				res = generate.matprep_internal(
						mat, passes, self.useReflections)
				if res==0: count+=1
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
			elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
				res = generate.matprep_cycles(
						mat, passes, self.useReflections, self.usePrincipledShader)
				if res==0: count+=1
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
			else:
				self.report({'ERROR'},"Only blender internal or cycles supported")
				return {'CANCELLED'}

		if self.combineMaterials==True:
			bpy.ops.mcprep.combine_materials(selection_only=True, skipUsage=True)
		if self.improveUiSettings:
			bpy.ops.mcprep.improve_ui()
		self.report({"INFO"},"Modified "+str(count)+" materials")
		self.track_param = context.scene.render.engine

		return {'FINISHED'}


class McprepMaterialHelp(bpy.types.Operator):
	"""Follow up popup to assist the user who may not have gotten expected change."""
	bl_idname = "mcprep.prep_materials_help"
	bl_label = "MCprep Materials Help"
	bl_options = {'REGISTER', 'UNDO'}

	def update_supress_help(self, context):
		"""Update trigger for supressing help popups."""
		if conf.v and self.suppress_help:
			print("Supressing future help popups")
		elif conf.v and not self.suppress_help:
			print("Re-enabling popup warnings")

	help_num = bpy.props.IntProperty(
		default = 0,
		options = {'HIDDEN'}
		)
	suppress_help = bpy.props.BoolProperty(
		name = "Don't show this again",
		default = False,
		options = {'HIDDEN'},
		update = update_supress_help
		)

	def invoke(self, context, event):
		# check here whether to trigger popup, based on supression
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

	def draw(self, context):
		layout = self.layout
		col = layout.column()
		if self.help_num == 0:
			# No specific error occured
			col.scale_y = 0.7
			col.label("No specific MCprep material issue identified.")
			col.label("Still need help? Press OK below to open an issue.")
		elif self.help_num == 1:
			# No materials modified, because no materials detected
			col.scale_y = 0.7
			col.label("Could not prep materials because")
			col.label("because none of the selected objects")
			col.label("have materials. Be sure to select the")
			col.label("model or world import before prepping!")
		elif self.help_num == 2:
			# Missing SOME textures detected, either because find msising is off
			# or if replacement still not found even with setting on
			col.scale_y = 0.7
			col.label("Some materials have missing textures,")
			col.label("these may show up as pink or black materials")
			col.label("in the viewport or in a render. Try using:")
			col.label("file > External Data > Find missing files")
		elif self.help_num == 3:
			# It worked, but maybe the user isn't seeing what they expect
			col.scale_y = 0.7
			col.label("Material prepping worked, but you might need")
			col.label("to \"Improve UI\" or go into texture/rendered")
			col.label("mode (shift+z) to see imrpoved textures")

		col.prop(self, "suppress_help")
		self.help_num = 0  # reset in event of unset re-trigger

	def execute(self, context):
		if self.help_num == 0:
			bpy.ops.wm.url_open(
				url = "")

		return {'FINISHED'}


class McprepSwapTexturePack(bpy.types.Operator, ImportHelper):
	"""Swap current textures for that of a texture pack folder"""
	bl_idname = "mcprep.swap_texture_pack"
	bl_label = "Swap Texture Pack"
	bl_description = "Change the texture pack for all materials of selected objects, "+\
				"select a folder path for an unzipped resource pack or texture folder"
	bl_options = {'REGISTER', 'UNDO'}

	# filename_ext = ".zip"
	# filter_glob = bpy.props.StringProperty(
	# 		default="*",
	# 		options={'HIDDEN'},
	# 		)
	# fileselectparams = "use_filter_blender"
	# files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
	filter_glob = bpy.props.StringProperty(
		default="",
		options = {'HIDDEN'}
		)
	use_filter_folder = True
	fileselectparams = "use_filter_blender"
	filepath = bpy.props.StringProperty(subtype='DIR_PATH')
	# files = bpy.props.CollectionProperty(
	# 	type=bpy.types.PropertyGroup,
	# 	options={'HIDDEN', 'SKIP_SAVE'}
	# 	)
	filter_image = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'}
		)
	filter_folder = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'}
		)
	extra_passes = bpy.props.BoolProperty(
		name = "Extra passes (if available)",
		description = "If enabled, load other image passes like normal and spec"+\
				" maps if available",
		default = True,
		)
	animateTextures = bpy.props.BoolProperty(
			name = "Animate textures (first time may be slow)",
			description = "Convert tiled images into image sequence for material.",
			default = True)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		subcol = col.column()
		subcol.scale_y = 0.7
		subcol.label("Select any subfolder of an")
		subcol.label("unzipped texturepack, then")
		subcol.label("press 'Swap Texture Pack'")
		subcol.label("after confirming these")
		subcol.label("settings below:")
		col.prop(self, "extra_passes")
		col.prop(self, "animateTextures")

	track_function = "texture_pack"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self,context):

		# check folder exist, but keep relative if relevant
		folder = self.filepath
		if os.path.isfile(bpy.path.abspath(folder)):
			folder = os.path.dirname(folder)
		if conf.v: print("Folder: ", folder)

		if not os.path.isdir(bpy.path.abspath(folder)):
			self.report({'ERROR'}, "Selected folder does not exist")
			return {'CANCELLED'}

		# get list of selected objects
		obj_list = context.selected_objects
		if len(obj_list)==0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if len(obj_list)==0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}
		res = generate.detect_form(mat_list)
		if res=="mineways":
			self.report({'ERROR'}, "Not yet supported for Mineways - coming soon!")
			return {'CANCELLED'}
		self.track_exporter = res

		# set the scene's folder for the texturepack being swapped
		context.scene.mcprep_custom_texturepack_path = folder

		if conf.v: print("Materials detected:",len(mat_list))
		res = 0
		for mat in mat_list:
			res += generate.set_texture_pack(mat, folder, self.extra_passes)
			if self.animateTextures:
				sequences.animate_single_material(
					mat, context.scene.render.engine, )

		self.report({'INFO'},"{} materials affected".format(res))
		self.track_param = context.scene.render.engine
		self.track_exporter = generate.detect_form(mat_list)

		return {'FINISHED'}


class McprepResetTexturepackPath(bpy.types.Operator):
	bl_idname = "mcprep.reset_texture_path"
	bl_label = "Reset texturepack path"
	bl_description = "Resets the texturepack folder to the MCprep default saved in preferences"

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_prefs()
		context.scene.mcprep_custom_texturepack_path = addon_prefs.custom_texturepack_path
		return {'FINISHED'}


class McprepCombineMaterials(bpy.types.Operator):
	bl_idname = "mcprep.combine_materials"
	bl_label = "Combine materials"
	bl_description = "Consolidate the same materials together e.g. mat.001 and mat.002"

	# arg to auto-force remove old? versus just keep as 0-users
	selection_only = bpy.props.BoolProperty(
		name = "Selection only",
		description = "Build materials to consoldiate based on selected objects only",
		default = True
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	track_function = "combine_materials"
	@tracking.report_error
	def execute(self, context):
		removeold = True

		if self.selection_only==True and len(context.selected_objects)==0:
			self.report({'ERROR',"Either turn selection only off or select objects with materials"})
			return {'CANCELLED'}

		# 2-level structure to hold base name and all
		# materials blocks with the same base
		name_cat = {}

		def getMaterials(self, context):
			if self.selection_only == False:
				return bpy.data.materials
			else:
				mats = []
				for ob in bpy.data.objects:
					for sl in ob.material_slots:
						if sl == None or sl.material == None:continue
						if sl.material in mats:continue
						mats.append(sl.material)
				return mats

		data = getMaterials(self, context)
		precount = len( ["x" for x in data if x.users >0] )

		if len(data)==0:
			if self.selection_only==True:
				self.report({"ERROR"},"No materials found on selected objects")
			else:
				self.report({"ERROR"},"No materials in open file")
			return {'CANCELLED'}

		# get and categorize all materials names
		for mat in data:
			base = util.nameGeneralize(mat.name)
			if base not in name_cat:
				name_cat[base] = [mat.name]
			elif mat.name not in name_cat[base]:
				name_cat[base].append(mat.name)
			else:
				if conf.vv:print("Skipping, already added material")


		# pre 2.78 solution, deep loop
		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl == None or sl.material == None:continue
					if sl.material not in data: continue # selection only
					sl.material = bpy.data.materials[name_cat[ util.nameGeneralize(sl.material.name) ][0]]
			# doesn't remove old textures, but gets it to zero users

			postcount = len( ["x" for x in bpy.data.materials if x.users >0] )
			self.report({"INFO"},
				"Consolidated {x} materials, down to {y} overall".format(
				x=precount-postcount,
				y=postcount))
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in name_cat: # the keys of the dictionary
			if len(base)<2: continue

			name_cat[base].sort() # in-place sorting
			baseMat = bpy.data.materials[ name_cat[base][0] ]

			if conf.vv:print(name_cat[base], "##", baseMat )

			for matname in name_cat[base][1:]:

				# skip if fake user set
				if bpy.data.materials[matname].use_fake_user == True: continue
				# otherwise, remap
				res = util.remap_users(bpy.data.materials[matname],baseMat)
				if res != 0:
					self.report({'ERROR'}, str(res))
					return {'CANCELLED'}
				old = bpy.data.materials[matname]
				if conf.vv:print("removing old? ",bpy.data.materials[matname])
				if removeold==True and old.users==0:
					if conf.vv:print("removing old:")
					data.remove( bpy.data.materials[matname] )

			# Final step.. rename to not have .001 if it does
			genBase = util.nameGeneralize(baseMat.name)
			if baseMat.name != genBase:
				if genBase in bpy.data.materials and bpy.data.materials[genBase].users!=0:
					pass
				else:
					baseMat.name = genBase
			else:
				baseMat.name = genBase
			if conf.vv:print("Final: ",baseMat)

		postcount = len( ["x" for x in getMaterials(self, context) if x.users >0] )
		self.report({"INFO"},
				"Consolidated {x} materials down to {y}".format(
				x=precount,
				y=postcount))

		return {'FINISHED'}


class McprepCombineImages(bpy.types.Operator):
	bl_idname = "mcprep.combine_images"
	bl_label = "Combine images"
	bl_description = "Consolidate the same images together e.g. img.001 and img.002"

	# arg to auto-force remove old? versus just keep as 0-users
	selection_only = bpy.props.BoolProperty(
		name = "Selection only",
		description = "Build images to consoldiate based on selected objects' materials only",
		default = False
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	track_function = "combine_images"
	@tracking.report_error
	def execute(self, context):
		removeold = True

		if self.selection_only==True and len(context.selected_objects)==0:
			self.report({'ERROR',"Either turn selection only off or select objects with materials/images"})
			return {'CANCELLED'}

		# 2-level structure to hold base name and all
		# images blocks with the same base
		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			self.report({'ERROR',"Must use blender 2.78 or higher to use this operator"})
			return {'CANCELLED'}

		if self.selection_only==True:
			self.report({'ERROR'},"Combine images does not yet work for selection only, retry with option disabled")
			return {'CANCELLED'}

		name_cat = {}
		data = bpy.data.images

		precount = len(data)

		# get and categorize all image names
		for im in bpy.data.images:
			base = util.nameGeneralize(im.name)
			if base not in name_cat:
				name_cat[base] = [im.name]
			elif im.name not in name_cat[base]:
				name_cat[base].append(im.name)
			else:
				if conf.vv:print("Skipping, already added image")

		# pre 2.78 solution, deep loop
		if bpy.app.version < (2,78):
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl == None or sl.material == None:continue
					if sl.material not in data: continue # selection only
					sl.material = data[name_cat[ util.nameGeneralize(sl.material.name) ][0]]
			# doesn't remove old textures, but gets it to zero users

			postcount = len( ["x" for x in bpy.data.materials if x.users >0] )
			self.report({"INFO"},
				"Consolidated {x} materials, down to {y} overall".format(
				x=precount-postcount,
				y=postcount))
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in name_cat:
			if len(base)<2: continue

			name_cat[base].sort() # in-place sorting
			baseImg = bpy.data.images[ name_cat[base][0] ]

			for imgname in name_cat[base][1:]:

				# skip if fake user set
				if bpy.data.images[imgname].use_fake_user == True: continue

				# otherwise, remap
				util.remap_users(data[imgname],baseImg)
				old = bpy.data.images[imgname]
				if removeold==True and old.users==0:
					bpy.data.images.remove( bpy.data.images[imgname] )

			# Final step.. rename to not have .001 if it does
			if baseImg.name != util.nameGeneralize(baseImg.name):
				if util.nameGeneralize(baseImg.name) in data and \
						bpy.data.images[util.nameGeneralize(baseImg.name)].users!=0:
					pass
				else:
					baseImg.name = util.nameGeneralize(baseImg.name)
			else:
				baseImg.name = util.nameGeneralize(baseImg.name)

		postcount = len( ["x" for x in bpy.data.images if x.users >0] )
		self.report({"INFO"},
				"Consolidated {x} images down to {y}".format(
				x=precount,
				y=postcount))

		return {'FINISHED'}


class McprepScaleUV():  # bpy.types.Operator
	bl_idname = "mcprep.scale_uv"
	bl_label = "Scale Faces"
	bl_description = "Scale all selected UV faces"
	bl_options = {'REGISTER', 'UNDO'}

	scale = bpy.props.FloatProperty(default=1.0,name="Scale")
	first_mouse_x = bpy.props.IntProperty() # hidden
	first_mouse_y = bpy.props.IntProperty() # hidden
	initial_UV = []
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)
	ob = None

	# 1) Need to save orig_center (x,y) point of all selected faces
	# 2) factor ALWAYS = sqrtdist(initial center - current xy)/sqrtdist(initial_medium - orig_xy)
	# 3) and the sign (positive or negative) is from dot product (scalar) agaisnt orig
	#    vector direction of orig_xy - orig_center
	# 4) Draw a dotted line from curser loc to said origin, plus  in/out arrows aligned to vector
	# 5) Add scale values update parameter in view below on window
	# 6) Add ability to enter text value for scale e.g. type in 0.5 during modal

	# It already works for individual faces...
	# but not when their borders are already touching (which is the use case here)

	# @classmethod
	# def poll(cls, context):
	# 	return context.mode == 'EDIT' or (context.mode == 'OBJECT' and context.object)

	def modal(self, context, event):
		print("EEEVVEENNT: ", event.type,event,type(event))
		if event.type == 'MOUSEMOVE':
			delta = event.mouse_x - self.first_mouse_x
			#context.object.location.x = self.first_value + delta * 0.01
			# bpy.ops.object.mode_set(mode="OBJECT")
			factor = 1+delta*0.01
			# ret = self.scale_UV_faces(context, ob, factor)
			ret = self.scale_UV_faces(context, self.ob, factor)
			# bpy.ops.object.mode_set(mode="EDIT")

		elif event.type in {'LEFTMOUSE', 'RET'}:
			# set scale factor here?
			delta = event.mouse_x - self.first_mouse_x
			self.scale = 1+self.first_mouse_x + delta*0.01
			bpy.ops.object.mode_set(mode="EDIT")
			return {'FINISHED'}

		elif event.type in {'RIGHTMOUSE', 'ESC'}:
			# bpy.ops.object.mode_set(mode="OBJECT")
			ret = self.scale_UV_faces(context, self.ob, 1) # unset back to original data
			bpy.ops.object.mode_set(mode="EDIT")
			return {'CANCELLED'}

		return {'RUNNING_MODAL'}

	def invoke(self, context, event):
		self.ob = context.object
		if self.ob==None:
			self.report({'WARNING'}, "No active object found")
			return {'CANCELLED'}
		elif self.ob.type != 'MESH':
			self.report({'WARNING'}, "Active object must be a mesh")
			return {'CANCELLED'}
		elif len(self.ob.data.polygons)==0:
			self.report({'WARNING'}, "Active object has no faces to delete")
			return {'CANCELLED'}

		if not self.ob.data.uv_layers.active:#uv==None:
			self.report({'WARNING'}, "No active UV map found")
			return {'CANCELLED'}

		bpy.ops.object.mode_set(mode="OBJECT")
		self.first_mouse_x = event.mouse_x
		#zip the data... so that format is [(x,y),(x,y)]
		self.initial_UV = [(d.uv[0], d.uv[1])
							for d in self.ob.data.uv_layers.active.data]
		# print(self.initial_UV)
		self.initial_UV = list(self.ob.data.uv_layers.active.data)
		# bpy.ops.object.mode_set(mode="EDIT")
		bpy.ops.object.mode_set(mode="OBJECT")
		context.window_manager.modal_handler_add(self)
		return {'RUNNING_MODAL'}


	def execute(self, context):

		# INITIAL WIP
		"""
		# WIP
		ob = context.active_object
		# copied from elsewhere
		uvs = ob.data.uv_layers[0].data
		matchingVertIndex = list(chain.from_iterable(polyIndices))
		# example, matching list of uv coord and 3dVert coord:
		uvs_XY = [i.uv for i in Object.data.uv_layers[0].data]
		vertXYZ= [v.co for v in Object.data.vertices]
		matchingVertIndex = list(chain.from_iterable([p.vertices for p in Object.data.polygons]))
		# and now, the coord to pair with uv coord:
		matchingVertsCoord = [vertsXYZ[i] for i in matchingVertIndex]
		"""

		bpy.ops.object.mode_set(mode="OBJECT")
		ret = self.scale_UV_faces(context, bpy.context.object,self.scale)
		bpy.ops.object.mode_set(mode="EDIT")
		if ret != None:
			self.report({ret[0]},ret[1])
			if conf.v: print(ret[0]+", "+ret[1])
			return {'CANCELLED'}

		return {'FINISHED'}

	def scale_UV_faces(self, context, ob, factor):

		# transform the scale factor properly to implementation below
		factor *= -1
		factor += 1
		mod = False

		uv = ob.data.uv_layers.active

		for f in ob.data.polygons:
			# if not selected, won't show up in UV editor
			if f.select!=True:continue
			# initialize for avergae center on polygon (probably a better way exists)
			x=y=n=0 # x,y,number of verts in loop for average purpose
			for i in f.loop_indices:
				l = ob.data.loops[i] # The loop entry this polygon point refers to
				v = ob.data.vertices[l.vertex_index]  # The vertex data that loop entry refers to
				#print("\tLoop index", l.index, "points to vertex index", l.vertex_index,"at position", v.co)
				# isolate to specific UV already used
				#print("\t\tUV map coord: ", uv.data[l.index].uv)
				if uv.data[l.index].select == False:continue
				x+=uv.data[l.index].uv[0]
				y+=uv.data[l.index].uv[1]
				n+=1
			for i in f.loop_indices:
				if uv.data[l.index].select == False:continue
				l = ob.data.loops[i]
				# hmm.. seems initial_UV index order does NOT remain consistent
				uv.data[l.index].uv[0] = self.initial_UV[l.index][0]*(1-factor)+x/n*(factor)
				uv.data[l.index].uv[1] = self.initial_UV[l.index][1]*(1-factor)+y/n*(factor)
				mod=True
		if mod==False:
			return ("ERROR","No UV faces selected")

		return None


class McprepIsolate_alpha_uvs(): #bpy.types.Operator
	bl_idname = "mcprep.isolate_alpha_uvs"
	bl_label = "Alpha faces"
	bl_description = "Select or delete alpha faces of a mesh"
	bl_options = {'REGISTER', 'UNDO'}

	# deleteAlpha = False
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)
	delete = bpy.props.BoolProperty(
		name="Delete faces",
		description="Select and auto-delete transparent faces, based on active image per face",
		default = False,
		)

	track_function = "isolate_uv"
	@tracking.report_error
	def execute(self, context):

		# bpy.ops.object.mode_set(mode="OBJECT")
		# bpy.ops.object.mode_set(mode="EDIT")
		# if doing multiple objects, iterate over loop of this function
		ret = self.select_alpha(context, context.object, 1)
		if ret==True:
			if self.delete: print("DELETE faces")

		return {"FINISHED"}

	def select_alpha(self, context, ob, thresh):

		if ob==None:
			return ("ERROR","No active object found")
		elif ob.type != 'MESH':
			return ("ERROR","Active object must be a mesh")
		elif len(ob.data.polygons)==0:
			return ("ERROR","Active object has no faces")

		uv = ob.data.uv_layers.active
		if uv==None:
			return ("ERROR","No active UV map found")

		# img =
		# if ob.data.uv_textures.active == None: continue
		for uv_face in ob.data.uv_textures.active.data:
			uv_face.image = image

		return ("WARNING","Not implemented yet")


class McprepReplaceMissingTextures(bpy.types.Operator):
	"""For all image blocks in the file where the filepath is missing or image
	could not be loaded, see if the image can be replaced by one in the active
	resource pack."""
	bl_idname = "mcprep.replace_missing_textures"
	bl_label = "Find missing textures"
	bl_options = {'REGISTER', 'UNDO'}

	# deleteAlpha = False
	animateTextures = bpy.props.BoolProperty(
		name = "Animate textures (may be slow first time)",
		description = "Convert tiled images into image sequence for material.",
		default = True)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	track_function = "replace_missing"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):

		# get list of selected objects
		obj_list = context.selected_objects
		if len(obj_list)==0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if len(obj_list)==0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		count = 0
		for mat in mat_list:
			updated = False
			passes = generate.get_textures(mat)
			for pass_name in passes:
				res = generate.replace_missing_texture(passes[pass_name])
				if res == 1:
					updated = True
			if updated:
				count += 1
				if conf.v: print("Updated " + mat.name)
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
					if conf.v: print("Animated texture")
		if count == 0:
			self.report({'INFO'},
				"No missing image blocks detected in {} materials".format(
				len(mat_list)))

		self.report({'INFO'}, "Updated {} materials".format(count))
		self.track_param = context.scene.render.engine
		self.track_exporter = generate.detect_form(mat_list)

		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	pass


def unregister():
	pass
