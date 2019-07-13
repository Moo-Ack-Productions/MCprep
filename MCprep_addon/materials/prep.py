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


class MCPREP_OT_prep_materials(bpy.types.Operator):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "mcprep.prep_materials"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

	animateTextures = bpy.props.BoolProperty(
		name = "Animate textures (may be slow first time)",
		description = "Swap still images for the animated sequenced found in the active or default texture pack.",
		default = False)
	autoFindMissingTextures = bpy.props.BoolProperty(
		name = "Find missing images",
		description = "If the texture for an existing material is missing, try "+\
				"to load from the default texture pack instead",
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
	useExtraMaps = bpy.props.BoolProperty(
		name = "Use extra maps",
		description = "Generate materials using normal/spec maps if they are "+\
					"available, requires special texture packs",
		default = True
		)
	normalIntensity = bpy.props.FloatProperty(
		name = "Normal map intensity",
		description = "Set normal map intensity, if normal maps are found in "+\
				"the active texture pack and using normal/spec passes",
		default = 1.0,
		max=1,
		min=0
		)
	makeSolid = bpy.props.BoolProperty(
		name = "Make all materials solid",
		description = "Make all materials solid only, for shadows and rendering",
		default = False
		)

	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)
	# prop: set all blocks as solid (no transparency), assume has trans, or compute check

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=300*util.ui_scale())

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		engine = context.scene.render.engine
		if engine=='CYCLES' or engine=='BLENDER_EEVEE':
			col.prop(self, "usePrincipledShader")
		col.prop(self, "useReflections")
		col.prop(self, "makeSolid")
		col.prop(self, "animateTextures")
		col.prop(self, "autoFindMissingTextures")

		row = self.layout.row()
		col = row.column()
		col.prop(self, "useExtraMaps")
		# col = row.column()
		# col.prop(self, "normalIntensity", slider=True)

		split = self.layout.split()
		row = self.layout.row()
		col = row.column()
		col.prop(self, "improveUiSettings")
		col = row.column()
		col.prop(self, "combineMaterials")

	track_function = "materials"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):

		# get list of selected objects
		obj_list = context.selected_objects
		if not obj_list:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if not mat_list:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		# check if linked material exists
		engine = context.scene.render.engine
		count = 0

		# TODO: run differently if a linked material
		for mat in mat_list:
			passes = generate.get_textures(mat)
			if not self.useExtraMaps:
				for pass_name in passes:
					if pass_name != "diffuse":
						passes[pass_name] = None
			if self.autoFindMissingTextures:
				for pass_name in passes:
					res = generate.replace_missing_texture(passes[pass_name])
					if res>0:
						mat["texture_swapped"] = True  # used to apply saturation
			if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
				res = generate.matprep_internal(mat, passes,
					self.useReflections, self.makeSolid)
				if res==0:
					count+=1
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
			elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
				res = generate.matprep_cycles(mat, passes, self.useReflections,
					self.usePrincipledShader, self.makeSolid)
				if res==0:
					count+=1
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
			else:
				self.report({'ERROR'},"Only blender internal or cycles supported")
				return {'CANCELLED'}

		if self.combineMaterials is True:
			bpy.ops.mcprep.combine_materials(selection_only=True, skipUsage=True)
		if self.improveUiSettings:
			bpy.ops.mcprep.improve_ui()
		self.report({"INFO"},"Modified "+str(count)+" materials")
		self.track_param = context.scene.render.engine
		self.track_exporter = generate.detect_form(mat_list)
		return {'FINISHED'}


class MCPREP_OT_materials_help(bpy.types.Operator):
	"""Follow up popup to assist the user who may not have gotten expected change"""
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
			col.label(text="No specific MCprep material issue identified.")
			col.label(text="Still need help? Press OK below to open an issue.")
		elif self.help_num == 1:
			# No materials modified, because no materials detected
			col.scale_y = 0.7
			col.label(text="Could not prep materials because")
			col.label(text="because none of the selected objects")
			col.label(text="have materials. Be sure to select the")
			col.label(text="model or world import before prepping!")
		elif self.help_num == 2:
			# Missing SOME textures detected, either because find msising is off
			# or if replacement still not found even with setting on
			col.scale_y = 0.7
			col.label(text="Some materials have missing textures,")
			col.label(text="these may show up as pink or black materials")
			col.label(text="in the viewport or in a render. Try using:")
			col.label(text="file > External Data > Find missing files")
		elif self.help_num == 3:
			# It worked, but maybe the user isn't seeing what they expect
			col.scale_y = 0.7
			col.label(text="Material prepping worked, but you might need")
			col.label(text="to \"Improve UI\" or go into texture/rendered")
			col.label(text="mode (shift+z) to see imrpoved textures")

		col.prop(self, "suppress_help")
		self.help_num = 0  # reset in event of unset re-trigger

	def execute(self, context):
		if self.help_num == 0:
			bpy.ops.wm.url_open(
				url = "")

		return {'FINISHED'}


class MCPREP_OT_swap_texture_pack(bpy.types.Operator, ImportHelper):
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
		subcol.label(text="Select any subfolder of an")
		subcol.label(text="unzipped texture pack, then")
		subcol.label(text="press 'Swap Texture Pack'")
		subcol.label(text="after confirming these")
		subcol.label(text="settings below:")
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
		conf.log("Folder: " + folder)

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
		exporter = generate.detect_form(mat_list)
		if exporter=="mineways":
			self.report({'ERROR'}, "Not yet supported for Mineways - coming soon!")
			return {'CANCELLED'}
		self.track_exporter = exporter

		# set the scene's folder for the texturepack being swapped
		context.scene.mcprep_texturepack_path = folder

		conf.log("Materials detected: " + str(len(mat_list)))
		res = 0
		for mat in mat_list:
			res += generate.set_texture_pack(mat, folder, self.extra_passes)
			if self.animateTextures:
				sequences.animate_single_material(
					mat, context.scene.render.engine)

		self.report({'INFO'},"{} materials affected".format(res))
		self.track_param = context.scene.render.engine
		return {'FINISHED'}


class MCPREP_OT_reset_texturepack_path(bpy.types.Operator):
	bl_idname = "mcprep.reset_texture_path"
	bl_label = "Reset texture pack path"
	bl_description = "Resets the texture pack folder to the MCprep default saved in preferences"

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_texturepack_path = addon_prefs.custom_texturepack_path
		return {'FINISHED'}


class MCPREP_OT_combine_materials(bpy.types.Operator):
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
			self.report({'ERROR'},
				"Either turn selection only off or select objects with materials")
			return {'CANCELLED'}

		# 2-level structure to hold base name and all
		# materials blocks with the same base
		name_cat = {}

		def getMaterials(self, context):
			if self.selection_only is False:
				return bpy.data.materials
			else:
				mats = []
				for ob in bpy.data.objects:
					for sl in ob.material_slots:
						if sl is None or sl.material is None:
							continue
						if sl.material in mats:
							continue
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
				conf.log("Skipping, already added material", True)


		# pre 2.78 solution, deep loop
		if bpy.app.version < (2, 78):
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl == None or sl.material == None:
						continue
					if sl.material not in data:
						continue # selection only
					sl.material = bpy.data.materials[name_cat[util.nameGeneralize(sl.material.name)][0]]
			# doesn't remove old textures, but gets it to zero users

			postcount = len([True for x in bpy.data.materials if x.users >0])
			self.report({"INFO"},
				"Consolidated {x} materials, down to {y} overall".format(
				x=precount-postcount,
				y=postcount))
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in name_cat: # the keys of the dictionary
			if len(base)<2:
				continue

			name_cat[base].sort() # in-place sorting
			baseMat = bpy.data.materials[name_cat[base][0]]

			conf.log([name_cat[base]," ## ",baseMat], vv_only=True)

			for matname in name_cat[base][1:]:

				# skip if fake user set
				if bpy.data.materials[matname].use_fake_user == True:
					continue
				# otherwise, remap
				res = util.remap_users(bpy.data.materials[matname],baseMat)
				if res != 0:
					self.report({'ERROR'}, str(res))
					return {'CANCELLED'}
				old = bpy.data.materials[matname]
				conf.log("removing old? "+matname, vv_only=True)
				if removeold is True and old.users==0:
					conf.log("removing old:"+matname, vv_only=True)
					try:
						data.remove(bpy.data.materials[matname])
					except ReferenceError as err:
						print('Error trying to remove material '+matname)
						print(str(err))

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


class MCPREP_OT_combine_images(bpy.types.Operator):
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
					if sl is None or sl.material is None or sl.material not in data:
						continue # selection only
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
			if len(base)<2:
				continue
			name_cat[base].sort() # in-place sorting
			baseImg = bpy.data.images[ name_cat[base][0] ]

			for imgname in name_cat[base][1:]:
				# skip if fake user set
				if bpy.data.images[imgname].use_fake_user is True:
					continue
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


class MCPREP_OT_scale_uv(bpy.types.Operator):
	bl_idname = "mcprep.scale_uv"
	bl_label = "Scale UV Faces"
	bl_description = "Scale all selected UV faces. See F6 or redo-last panel to adjust factor"
	bl_options = {'REGISTER', 'UNDO'}

	scale = bpy.props.FloatProperty(default=0.75, name="Scale")
	selected_only = bpy.props.BoolProperty(default=True, name="Seleced only")
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	@classmethod
	def poll(cls, context):
		return context.mode == 'EDIT_MESH' or (
			context.mode == 'OBJECT' and context.object)

	track_function = "scale_uv"
	@tracking.report_error
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
		if not context.object:
			self.report({'ERROR'}, "No active object found")
			return {'CANCELLED'}
		elif context.object.type != 'MESH':
			self.report({'ERROR'}, "Active object must be a mesh")
			return {'CANCELLED'}
		elif not context.object.data.polygons:
			self.report({'WARNING'}, "Active object has no faces")
			return {'CANCELLED'}

		if not context.object.data.uv_layers.active:#uv==None:
			self.report({'ERROR'}, "No active UV map found")
			return {'CANCELLED'}

		mode_initial = context.mode
		bpy.ops.object.mode_set(mode="OBJECT")
		ret = self.scale_uv_faces(context.object, self.scale)
		if mode_initial != 'OBJECT':
			bpy.ops.object.mode_set(mode="EDIT")

		if ret is not None:
			self.report({'ERROR'}, ret)
			conf.log("Error, "+ret)
			return {'CANCELLED'}

		return {'FINISHED'}

	def scale_uv_faces(self, ob, factor):
		"""Scale all UV face centers of an object by a given factor."""

		factor *= -1
		factor += 1
		modified = False

		uv = ob.data.uv_layers.active
		# initial_UV = [(d.uv[0], d.uv[1])
		# 				for d in ob.data.uv_layers.active.data]

		for f in ob.data.polygons:
			if not f.select and self.selected_only is True:
				continue  # if not selected, won't show up in UV editor

			# initialize for avergae center on polygon
			x=y=n=0  # x,y,number of verts in loop for average purpose
			for i in f.loop_indices:
				# a loop could be an edge or face
				l = ob.data.loops[i] # This polygon/edge
				v = ob.data.vertices[l.vertex_index]  # The vertex data that loop entry refers to
				# isolate to specific UV already used
				if not uv.data[l.index].select and self.selected_only is True:
					continue
				x+=uv.data[l.index].uv[0]
				y+=uv.data[l.index].uv[1]
				n+=1
			for i in f.loop_indices:
				if not uv.data[l.index].select and self.selected_only is True:
					continue
				l = ob.data.loops[i]
				uv.data[l.index].uv[0] = uv.data[l.index].uv[0]*(1-factor)+x/n*(factor)
				uv.data[l.index].uv[1] = uv.data[l.index].uv[1]*(1-factor)+y/n*(factor)
				modified = True
		if not modified:
			return "No UV faces selected"

		return None


class MCPREP_OT_select_alpha_faces(bpy.types.Operator):
	bl_idname = "mcprep.select_alpha_faces"
	bl_label = "Select alpha faces"
	bl_description = "Select or delete transparent UV faces of a mesh"
	bl_options = {'REGISTER', 'UNDO'}

	delete = bpy.props.BoolProperty(
		name="Delete faces",
		description="Delete detected transparent mesh faces",
		default = False
		)
	threshold = bpy.props.FloatProperty(
		name="Threshold",
		description="How transparent pixels need to be to select",
		default = 0.2,
		min=0.0,
		max=1.0
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	@classmethod
	def poll(cls, context):
		return context.mode == 'EDIT_MESH'

	track_function = "alpha_faces"
	@tracking.report_error
	def execute(self, context):

		ob = context.object
		if ob is None:
			self.report({"ERROR"}, "No active object found")
			return {"CANCELLED"}
		elif ob.type != 'MESH':
			self.report({"ERROR"}, "Active object must be a mesh")
			return {"CANCELLED"}
		elif not ob.data.polygons:
			self.report({"WARNING"}, "Active object has no faces")
			return {"CANCELLED"}
		elif not ob.material_slots:
			self.report({"ERROR"}, "Active object has no materials to check image for.")
			return {"CANCELLED"}
		if ob.data.uv_layers.active is None:
			self.report({"ERROR"}, "No active UV map found")

		# if doing multiple objects, iterate over loop of this function
		bpy.ops.mesh.select_mode(type='FACE')

		# UV data only available in object mode, have to switch there and back
		bpy.ops.object.mode_set(mode="OBJECT")
		ret = self.select_alpha(ob, self.threshold)
		bpy.ops.object.mode_set(mode="EDIT")
		if ret:
			self.report({"ERROR"}, ret)
			return {"CANCELLED"}

		if not ret and self.delete:
			conf.log("Delet faces")
			bpy.ops.mesh.delete(type='FACE')

		return {"FINISHED"}

	def select_alpha(self, ob, threshold):
		"""Core function to select alpha faces based on active material/image."""
		if not ob.material_slots:
			conf.log("No materials, skipping.")
			return "No materials"

		# pre-cache the materials and their respective images for comparing
		textures = []
		for index in range(len(ob.material_slots)):
			mat = ob.material_slots[index].material
			if not mat:
				textures.append(None)
				continue
			image = generate.get_textures(mat)["diffuse"]
			if not image:
				textures.append(None)
				continue
			elif image.channels != 4:
				textures.append(None) # no alpha channel anyways
				conf.log("No alpha channel for: "+image.name)
				continue
			textures.append(image)
		data = [None for tex in textures]

		uv = ob.data.uv_layers.active
		for f in ob.data.polygons:
			if len(f.loop_indices) < 3:
				continue # don't select edges or vertices
			fnd = f.material_index
			image = textures[fnd]
			if not image:
				conf.log("Could not get image from face's material")
				return "Could not get image from face's material"

			# lazy load alpha part of image to memory, hold for whole operator
			if not data[fnd]:
				data[fnd] = list(image.pixels)[3::4]

			# relate the polygon to the UV layer to the image coordinates
			shape = []
			for i in f.loop_indices:
				loop = ob.data.loops[i]
				x = uv.data[loop.index].uv[0]%1 # TODO: fix this wraparound hack
				y = uv.data[loop.index].uv[1]%1
				shape.append((x,y))

			# print("The shape coords:")
			# print(shape)
			# could just do "the closest" pixel... but better is weighted area
			if not shape:
				continue

			xlist, ylist = tuple([list(tup) for tup in zip(*shape)])
			# not sure if I actually want to +0.5 to the values to get middle..
			xmin = round(min(xlist)*image.size[0])-0.5
			xmax = round(max(xlist)*image.size[0])-0.5
			ymin = round(min(ylist)*image.size[1])-0.5
			ymax = round(max(ylist)*image.size[1])-0.5
			conf.log(["\tSet size:",xmin,xmax,ymin,ymax], vv_only=True)

			# assuming faces are roughly rectangular, sum pixels a face covers
			asum = 0
			acount = 0
			for row in range(image.size[1]):
				if row < ymin or row > ymax:
					continue
				for col in range(image.size[0]):
					if col >= xmin and col <= xmax:
						asum += data[fnd][image.size[1]*row + col]
						acount += 1

			if acount == 0:
				acount = 1
			ratio = float(asum)/float(acount)
			if ratio < float(threshold):
				print("\t{} - Below threshold, select".format(ratio))
				f.select = True
			else:
				print("\t{} - above thresh, NO select".format(ratio))
				f.select = False
		return


class MCPREP_OT_replace_missing_textures(bpy.types.Operator):
	"""Replace any missing textures with matching images in the active texture pack"""
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
				conf.log("Updated " + mat.name)
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
					conf.log("Animated texture")
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


classes = (
	MCPREP_OT_prep_materials,
	MCPREP_OT_materials_help,
	MCPREP_OT_swap_texture_pack,
	MCPREP_OT_reset_texturepack_path,
	MCPREP_OT_combine_materials,
	MCPREP_OT_combine_images,
	MCPREP_OT_scale_uv,
	MCPREP_OT_select_alpha_faces,
	MCPREP_OT_replace_missing_textures
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
