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

# addon imports
from .. import conf
from . import generate
from . import sequences
from .. import tracking
from .. import util


# -----------------------------------------------------------------------------
# Material class functions
# -----------------------------------------------------------------------------
class McprepMaterialProps():
	"""Class to inheret reused MCprep settings.

	Benefit is to also enforce the same options, required where exec funcitons
	pass through from one operator to the other (e.g. prep mats on swap packs)
	"""
	animateTextures = bpy.props.BoolProperty(
		name = "Animate textures (may be slow first time)",
		description = ("Swap still images for the animated sequenced found in "
			"the active or default texture pack."),
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
		description = ("If available and using cycles, build materials using the "
				"principled shader"),
		default = True
		)
	useReflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropriate materials to be rendered reflective",
		default = True
		)
	useExtraMaps = bpy.props.BoolProperty(
		name = "Use extra maps",
		description = ("load other image passes like normal and "
				"spec maps if available"),
		default = True
		)
	normalIntensity = bpy.props.FloatProperty(
		name = "Normal map intensity",
		description = ("Set normal map intensity, if normal maps are found in "
				"the active texture pack and using normal/spec passes"),
		default = 1.0,
		max=1,
		min=0
		)
	makeSolid = bpy.props.BoolProperty(
		name = "Make all materials solid",
		description = "Make all materials solid only, for shadows and rendering",
		default = False
		)
	syncMaterials = bpy.props.BoolProperty(
		name = "Sync materials",
		description = ("Synchronize materials with those in the active "
			"pack's materials.blend file"),
		default = True
		)
	packFormat = bpy.props.EnumProperty(
		name="Pack Format",
		description="Change the pack format when using a PBR resource pack.",
		items=[
			("specular", "Specular", "Sets the pack format to Specular."),
			("seus", "SEUS", "Sets the pack format to SEUS.")],
		default="specular"
	)


class MCPREP_OT_prep_materials(bpy.types.Operator, McprepMaterialProps):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "mcprep.prep_materials"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

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
			col.prop(self, "packFormat")
			col.prop(self, "usePrincipledShader")
		col.prop(self, "useReflections")
		col.prop(self, "makeSolid")
		col.prop(self, "animateTextures")
		col.prop(self, "autoFindMissingTextures")

		row = self.layout.row()
		row.prop(self, "useExtraMaps")
		row.prop(self, "syncMaterials")

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
			if not self.skipUsage:
				self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if not mat_list:
			if not self.skipUsage:
				self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		# check if linked material exists
		engine = context.scene.render.engine
		count = 0
		count_lib_skipped = 0

		for mat in mat_list:
			if not mat:
				conf.log("During prep, found null material:"+str(mat), vv_only=True)
				continue
			elif mat.library:
				count_lib_skipped += 1
				continue

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
			elif engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
				res = generate.matprep_cycles(mat, passes, self.useReflections,
					self.usePrincipledShader, self.makeSolid, self.packFormat)
				if res==0:
					count+=1
			else:
				self.report({'ERROR'}, "Only Blender Internal, Cycles, or Eevee supported")
				return {'CANCELLED'}

			if self.animateTextures:
				sequences.animate_single_material(
					mat, context.scene.render.engine)

		if self.syncMaterials is True:
			bpy.ops.mcprep.sync_materials(
				selected=True, link=False, replace_materials=False, skipUsage=True)
		if self.combineMaterials is True:
			bpy.ops.mcprep.combine_materials(selection_only=True, skipUsage=True)
		if self.improveUiSettings:
			bpy.ops.mcprep.improve_ui()

		if self.skipUsage is True:
			pass # don't report if a meta-call
		elif count_lib_skipped > 0:
			self.report({"INFO"},
				"Modified {} materials, skipped {} linked ones.".format(
					count, count_lib_skipped))
		elif count >0:
			self.report({"INFO"},"Modified "+str(count)+" materials")
		else:
			self.report({"ERROR"}, "Nothing modified, be sure you selected objects with existing materials!")

		addon_prefs = util.get_user_preferences(context)
		self.track_param = context.scene.render.engine
		self.track_exporter = addon_prefs.MCprep_exporter_type
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


class MCPREP_OT_swap_texture_pack(bpy.types.Operator, ImportHelper, McprepMaterialProps):
	"""Swap current textures for that of a texture pack folder"""
	bl_idname = "mcprep.swap_texture_pack"
	bl_label = "Swap Texture Pack"
	bl_description = ("Change the texture pack for all materials of selected objects, "
		"select a folder path for an unzipped resource pack or texture folder")
	bl_options = {'REGISTER', 'UNDO'}


	filter_glob = bpy.props.StringProperty(
		default="",
		options = {'HIDDEN'}
		)
	use_filter_folder = True
	fileselectparams = "use_filter_blender"
	filepath = bpy.props.StringProperty(subtype='DIR_PATH')
	filter_image = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'}
		)
	filter_folder = bpy.props.BoolProperty(
		default=True,
		options={'HIDDEN', 'SKIP_SAVE'}
		)
	prepMaterials = bpy.props.BoolProperty(
			name = "Prep materials",
			description = "Runs prep materials after texture swap to regenerate materials.",
			default=False)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	@classmethod
	def poll(cls, context):
		addon_prefs = util.get_user_preferences(context)
		return addon_prefs.MCprep_exporter_type != "(choose)"

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
		col.prop(self, "useExtraMaps")
		col.prop(self, "animateTextures")
		col.prop(self, "prepMaterials")
		if self.prepMaterials:
			col.prop(self, "packFormat")
			col.prop(self, "usePrincipledShader")
			col.prop(self, "useReflections")
			col.prop(self, "autoFindMissingTextures")
			col.prop(self, "syncMaterials")
			col.prop(self, "improveUiSettings")
			col.prop(self, "combineMaterials")

	track_function = "texture_pack"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self,context):
		addon_prefs = util.get_user_preferences(context)

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
		# TODO: add cehck for "mineways combined" and call out not supported
		# if exporter=="mineways":
		# 	self.report({'ERROR'}, "Not yet supported for Mineways - coming soon!")
		# 	return {'CANCELLED'}
		self.track_exporter = addon_prefs.MCprep_exporter_type

		# set the scene's folder for the texturepack being swapped
		context.scene.mcprep_texturepack_path = folder

		conf.log("Materials detected: " + str(len(mat_list)))
		res = 0
		for mat in mat_list:
			self.preprocess_material(mat)
			res += generate.set_texture_pack(mat, folder, self.useExtraMaps)
			if self.animateTextures:
				sequences.animate_single_material(
					mat, context.scene.render.engine)
			generate.set_saturation_material(mat) # may be a double call if was animated tex

		if self.prepMaterials:
			MCPREP_OT_prep_materials.execute(self, context)

		self.report({'INFO'},"{} materials affected".format(res))
		self.track_param = context.scene.render.engine
		return {'FINISHED'}

	def preprocess_material(self, material):
		"""Preprocess materials for special edge cases"""

		# in texture packs, this is actually just a transparent overaly -
		# but in Mineways export, this is the flattened grass/drit block side
		if material.name == "grass_block_side_overlay":
			material.name = "grass_block_side"
			conf.log("Renamed material: grass_block_side_overlay to grass_block_side")


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
						data.remove(old)
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
			conf.log(["Final: ",baseMat], vv_only=True)

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
			self.report({'ERROR'},"Either turn selection only off or select objects with materials/images")
			return {'CANCELLED'}

		# 2-level structure to hold base name and all
		# images blocks with the same base
		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			self.report({'ERROR'}, "Must use blender 2.78 or higher to use this operator")
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
			if not passes:
				conf.log("No images found within material")
			for pass_name in passes:
				if pass_name == 'diffuse' and passes[pass_name] is None:
					res = self.load_from_texturepack(mat)
				else:
					res = generate.replace_missing_texture(passes[pass_name])
				if res == 1:
					updated = True
			if updated:
				count += 1
				conf.log("Updated " + mat.name)
				if self.animateTextures:
					sequences.animate_single_material(
						mat, context.scene.render.engine)
		if count == 0:
			self.report({'INFO'},
				"No missing image blocks detected in {} materials".format(
				len(mat_list)))

		self.report({'INFO'}, "Updated {} materials".format(count))
		self.track_param = context.scene.render.engine
		addon_prefs = util.get_user_preferences(context)
		self.track_exporter = addon_prefs.MCprep_exporter_type
		return {'FINISHED'}

	def load_from_texturepack(self, mat):
		"""If image datablock not found in passes, try to directly load and assign"""
		conf.log("Loading from texpack for "+mat.name, vv_only=True)
		canon, _ = generate.get_mc_canonical_name(mat.name)
		image_path = generate.find_from_texturepack(canon)
		if not image_path or not os.path.isfile(image_path):
			conf.log("Find missing images: No source file found for "+mat.name)
			return False

		# even if images of same name already exist, load new block
		conf.log("Find missing images: Creating new image datablock for "+mat.name)
		image = bpy.data.images.load(image_path)

		engine = bpy.context.scene.render.engine
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
			status = generate.set_cycles_texture(image, mat)
		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			status = generate.set_cycles_texture(image, mat)

		return status # True or False


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
	MCPREP_OT_replace_missing_textures
)


def register():
	util.make_annotations(McprepMaterialProps)
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
