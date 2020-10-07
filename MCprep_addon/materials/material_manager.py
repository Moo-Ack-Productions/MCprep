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
from . import generate
from . import sequences
from .. import tracking
from .. import util


# -----------------------------------------------------------------------------
# UI and utility functions
# -----------------------------------------------------------------------------


def reload_materials(context):
	"""Reload the material UI list"""
	mcprep_props = context.scene.mcprep_props
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	extensions = [".png",".jpg",".jpeg"]

	mcprep_props.material_list.clear()
	if conf.use_icons and conf.preview_collections["items"]:
		try:
			bpy.utils.previews.remove(conf.preview_collections["items"])
		except:
			conf.log("MCPREP: Failed to remove icon set, items")

	if not os.path.isdir(resource_folder):
		conf.log("Error, resource folder does not exist")
		return
	elif os.path.isdir(os.path.join(resource_folder,"textures")):
		resource_folder = os.path.join(resource_folder,"textures")
	elif os.path.isdir(os.path.join(resource_folder,"minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"minecraft","textures")
	elif os.path.isdir(os.path.join(resource_folder,"assets","minecraft","textures")):
		resource_folder = os.path.join(resource_folder,"assets","minecraft","textures")

	search_paths = [
		resource_folder,
		os.path.join(resource_folder,"blocks"),
		os.path.join(resource_folder,"block")]
	files = []

	for path in search_paths:
		if not os.path.isdir(path):
			continue
		files += [os.path.join(path, image_file)
					for image_file in os.listdir(path)
					if os.path.isfile(os.path.join(path, image_file))
					and os.path.splitext(image_file.lower())[-1] in extensions]
	for i, image_file in enumerate(sorted(files)):
		basename = os.path.splitext(os.path.basename(image_file))[0]
		if basename.endswith("_s") or basename.endswith("_n"):
			continue # ignore the pbr passes
		canon, _ = generate.get_mc_canonical_name(basename) # basename.replace("_", " ")
		asset = mcprep_props.material_list.add()
		asset.name = canon
		asset.description = "Generate {} ({})".format(canon, basename)
		asset.path = image_file
		asset.index = i

		# if available, load the custom icon too
		if not conf.use_icons or conf.preview_collections["items"] == "":
			continue
		conf.preview_collections["items"].load(
			"item-{}".format(i), image_file, 'IMAGE')

	if mcprep_props.material_list_index >= len(mcprep_props.material_list):
		mcprep_props.material_list_index = len(mcprep_props.material_list) - 1


class ListMaterials(bpy.types.PropertyGroup):
	"""For UI drawing of item assets and holding data"""
	# inherited: name
	description = bpy.props.StringProperty()
	path = bpy.props.StringProperty(subtype='FILE_PATH')
	index = bpy.props.IntProperty(min=0, default=0)  # for icon drawing


# -----------------------------------------------------------------------------
# Material data management operators
# -----------------------------------------------------------------------------


class MCPREP_OT_reset_texturepack_path(bpy.types.Operator):
	bl_idname = "mcprep.reset_texture_path"
	bl_label = "Reset texture pack path"
	bl_description = "Resets the texture pack folder to the MCprep default saved in preferences"
	bl_options = {'REGISTER', 'UNDO'}

	@tracking.report_error
	def execute(self, context):
		addon_prefs = util.get_user_preferences(context)
		context.scene.mcprep_texturepack_path = addon_prefs.custom_texturepack_path
		return {'FINISHED'}


class MCPREP_OT_reload_materials(bpy.types.Operator):
	bl_idname = "mcprep.reload_materials"
	bl_label = "Reload materials"
	bl_description = "Reload the material library"

	@tracking.report_error
	def execute(self, context):
		reload_materials(context)
		return {'FINISHED'}


class MCPREP_OT_combine_materials(bpy.types.Operator):
	bl_idname = "mcprep.combine_materials"
	bl_label = "Combine materials"
	bl_description = "Consolidate the same materials together e.g. mat.001 and mat.002"
	bl_options = {'REGISTER', 'UNDO'}

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

		postcount = len(["x" for x in getMaterials(self, context) if x.users >0])
		self.report({"INFO"}, "Consolidated {x} materials down to {y}".format(
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
				conf.log("Skipping, already added image", vv_only=True)

		# pre 2.78 solution, deep loop
		if bpy.app.version < (2,78):
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl is None or sl.material is None or sl.material not in data:
						continue # selection only
					sl.material = data[name_cat[util.nameGeneralize(sl.material.name)][0]]
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

		postcount = len(["x" for x in bpy.data.images if x.users >0])
		self.report({"INFO"}, "Consolidated {x} images down to {y}".format(
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
		image = bpy.data.images.load(image_path, check_existing=False)

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
	ListMaterials,
	MCPREP_OT_reset_texturepack_path,
	MCPREP_OT_reload_materials,
	MCPREP_OT_combine_materials,
	MCPREP_OT_combine_images,
	MCPREP_OT_replace_missing_textures
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
