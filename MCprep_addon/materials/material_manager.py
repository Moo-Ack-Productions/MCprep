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

import hashlib
import numpy as np

from . import generate
from . import sequences
from .. import tracking
from .. import util

from ..conf import MCprepError, env


# -----------------------------------------------------------------------------
# UI and utility functions
# -----------------------------------------------------------------------------


def reload_materials(context):
	"""Reload the material UI list"""
	mcprep_props = context.scene.mcprep_props
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	extensions = [".png", ".jpg", ".jpeg"]

	mcprep_props.material_list.clear()
	if env.use_icons and env.preview_collections["materials"]:
		try:
			bpy.utils.previews.remove(env.preview_collections["materials"])
		except:
			env.log("Failed to remove icon set, materials")

	if not os.path.isdir(resource_folder):
		env.log("Error, resource folder does not exist")
		return

	# Check multiple paths, picking the first match (order is important),
	# goal of picking out the /textures folder.
	check_dirs = [
		os.path.join(resource_folder, "textures"),
		os.path.join(resource_folder, "minecraft", "textures"),
		os.path.join(resource_folder, "assets", "minecraft", "textures")]
	for path in check_dirs:
		if os.path.isdir(path):
			resource_folder = path
			break

	search_paths = [
		resource_folder,
		os.path.join(resource_folder, "blocks"),
		os.path.join(resource_folder, "block")]
	files = []

	for path in search_paths:
		if not os.path.isdir(path):
			continue
		files += [
			os.path.join(path, image_file)
			for image_file in os.listdir(path)
			if os.path.isfile(os.path.join(path, image_file))
			and os.path.splitext(image_file.lower())[-1] in extensions]
	for i, image_file in enumerate(sorted(files)):
		basename = os.path.splitext(os.path.basename(image_file))[0]
		if basename.endswith("_s") or basename.endswith("_n"):
			continue  # ignore the pbr passes

		canon, _ = generate.get_mc_canonical_name(basename)
		asset = mcprep_props.material_list.add()
		asset.name = canon
		asset.description = f"Generate {canon} ({basename})"
		asset.path = image_file
		asset.index = i

		# if available, load the custom icon too
		if not env.use_icons or env.preview_collections["materials"] == "":
			continue
		env.preview_collections["materials"].load(
			f"material-{i}", image_file, 'IMAGE')

	if mcprep_props.material_list_index >= len(mcprep_props.material_list):
		mcprep_props.material_list_index = len(mcprep_props.material_list) - 1


class ListMaterials(bpy.types.PropertyGroup):
	"""For UI drawing of item assets and holding data"""
	# inherited: name
	description: bpy.props.StringProperty()
	path: bpy.props.StringProperty(subtype='FILE_PATH')
	index: bpy.props.IntProperty(min=0, default=0)  # for icon drawing


# -----------------------------------------------------------------------------
# Material data management operators
# -----------------------------------------------------------------------------


class MCPREP_OT_reset_texturepack_path(bpy.types.Operator):
	bl_idname = "mcprep.reset_texture_path"
	bl_label = "Reset texture pack path"
	bl_description = (
		"Resets the texture pack folder to the MCprep default saved in preferences")
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
	bl_description = (
		"Consolidate the same materials together e.g. mat.001 and mat.002")
	bl_options = {'REGISTER', 'UNDO'}

	# arg to auto-force remove old? versus just keep as 0-users
	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description="Build materials to consolidate based on selected objects only",
		default=True)
	skipUsage: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

	track_function = "combine_materials"
	@tracking.report_error
	def execute(self, context):
		removeold = True

		if self.selection_only is True and len(context.selected_objects) == 0:
			self.report(
				{'ERROR'},
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
		precount = len(["x" for x in data if x.users > 0])

		if not data:
			if self.selection_only:
				self.report({"ERROR"}, "No materials found on selected objects")
			else:
				self.report({"ERROR"}, "No materials in open file")
			return {'CANCELLED'}

		# get and categorize all materials names
		for mat in data:
			base = util.nameGeneralize(mat.name)
			if base not in name_cat:
				name_cat[base] = [mat.name]
			elif mat.name not in name_cat[base]:
				name_cat[base].append(mat.name)
			else:
				env.log("Skipping, already added material", True)

		# Pre 2.78 solution, deep loop.
		if bpy.app.version < (2, 78):
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl is None or sl.material is None:
						continue
					if sl.material not in data:
						continue  # Selection only.
					name_ref = name_cat[util.nameGeneralize(sl.material.name)][0]
					sl.material = bpy.data.materials[name_ref]
			# doesn't remove old textures, but gets it to zero users

			postcount = len([True for x in bpy.data.materials if x.users > 0])
			self.report(
				{"INFO"},
				f"Consolidated {precount - postcount} materials, down to {postcount} overall")
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in name_cat:  # The keys of the dictionary.
			if len(base) < 2:
				continue

			name_cat[base].sort()  # in-place sorting
			baseMat = bpy.data.materials[name_cat[base][0]]

			env.log(f"{name_cat[base]} ##  {baseMat}", vv_only=True)

			for matname in name_cat[base][1:]:
				# skip if fake user set
				if bpy.data.materials[matname].use_fake_user is True:
					continue
				# otherwise, remap
				bpy.data.materials[matname].user_remap(baseMat)
				old = bpy.data.materials[matname]
				env.log(f"removing old? {matname}", vv_only=True)
				if removeold is True and old.users == 0:
					env.log(f"removing old:{matname}", vv_only=True)
					try:
						data.remove(old)
					except ReferenceError as err:
						print(f'Error trying to remove material {matname}')
						print(str(err))
					except ValueError as err:
						print(f'Error trying to remove material {matname}')
						print(str(err))

			# Final step.. rename to not have .001 if it does,
			# unless the target base-named material still exists and has users.
			gen_base = util.nameGeneralize(baseMat.name)
			gen_material = bpy.data.materials.get(gen_base)
			if baseMat.name != gen_base:
				if gen_material and gen_material.users != 0:
					pass
				else:
					baseMat.name = gen_base
			else:
				baseMat.name = gen_base
			env.log(f"Final: {baseMat}", vv_only=True)

		postcount = len(["x" for x in getMaterials(self, context) if x.users > 0])
		self.report({"INFO"}, f"Consolidated {precount} materials down to {postcount}")

		return {'FINISHED'}


class MCPREP_OT_combine_images(bpy.types.Operator):
	bl_idname = "mcprep.combine_images"
	bl_label = "Combine images"
	bl_description = "Consolidate images with the same name (e.g. img.001 & img.002) and identical pixel data"
	bl_options = {'REGISTER', 'UNDO'}

	# arg to auto-force remove old? versus just keep as 0-users
	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description=(
			"Build images to consolidate based on selected objects' materials only"),
		default=False)
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "combine_images"
	@tracking.report_error
	def execute(self, context):
		removeold = True

		if bpy.app.version < (2, 78):
			self.report(
				{'ERROR'}, "Must use blender 2.78 or higher to use this operator")
			return {'CANCELLED'}

		if self.selection_only and len(context.selected_objects) == 0:
			self.report(
				{'ERROR'},
				"Either turn selection only off or select objects with materials/images")
			return {'CANCELLED'}

		if self.selection_only:
			self.report({'ERROR'}, (
				"Combine images does not yet work for selection only, retry "
				"with option disabled"))
			return {'CANCELLED'}

		data = bpy.data.images
		precount = len(data)

		# Group images
		groups = {}
		for im in data:
			if im.type == 'RENDER_RESULT': continue

			base_name = util.nameGeneralize(im.name)
			group_key = (base_name, im.size[0], im.size[1])

			if group_key not in groups:
				groups[group_key] = []
			groups[group_key].append(im)

		# Process groups
		for key, im_list in groups.items():
			if len(im_list) < 2:
				continue

			im_list.sort(key=lambda x: x.name)

			target_img = im_list[0]
			target_hash = self.get_image_hash(target_img)

			if not target_hash:
				continue

			for i in range(1, len(im_list)):
				current_img = im_list[i]

				# skip if fake user set
				if current_img.use_fake_user:
					continue

				current_hash = self.get_image_hash(current_img)

				if current_hash == target_hash:
					current_img.user_remap(target_img)
					if removeold and current_img.users == 0:
						data.remove(current_img)
				else:
					continue

			# Rename target to clean base name
			clean_name = key[0]
			if target_img.name != clean_name:
				if clean_name not in data or data[clean_name].users == 0:
					target_img.name = clean_name

		postcount = len(data)
		if precount - postcount > 0:
			self.report({"INFO"}, f"Consolidated {precount} images down to {postcount}")
		else:
			self.report({"INFO"}, "No images found to condense")

		return {'FINISHED'}

	def get_image_hash(self, img):
		"""Generates a MD5 hash from image pixel data"""
		
		if not img.has_data or sum(img.size) == 0:
			return None

		try:
			width, height = img.size
			pixels = np.empty(width * height * 4, dtype=np.float32)
			img.pixels.foreach_get(pixels)
			
			# Calculate buffer (sample every Nth pixel), only start buffering when image is larger than 4096 pixels (bigger than 64 x 64)
			buffer = max(1, (width * height) // 4096)

			# Reshape so buffer skips WHOLE pixels, keeping RGBA grouped
			sampled = pixels.view().reshape(-1, 4)[::buffer]
			
			return hashlib.md5(sampled.tobytes()).hexdigest()
			
		except Exception as e:
			print(f"Failed to hash {img.name}: {e}")
			return None



class MCPREP_OT_replace_missing_textures(bpy.types.Operator):
	"""Replace missing textures with matching images in the active texture pack"""
	bl_idname = "mcprep.replace_missing_textures"
	bl_label = "Find missing textures"
	bl_options = {'REGISTER', 'UNDO'}

	# deleteAlpha = False
	animateTextures: bpy.props.BoolProperty(
		name="Animate textures (may be slow first time)",
		description="Convert tiled images into image sequence for material.",
		default=True)
	skipUsage: bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "replace_missing"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):

		# get list of selected objects
		obj_list = context.selected_objects
		if len(obj_list) == 0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		mat_list = util.materialsFromObj(obj_list)
		if len(obj_list) == 0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		count = 0
		for mat in mat_list:
			updated = False
			passes = generate.get_textures(mat)
			if not passes:
				env.log("No images found within material")
			for pass_name in passes:
				if pass_name == 'diffuse' and passes[pass_name] is None:
					res = self.load_from_texturepack(mat)
				else:
					res = generate.replace_missing_texture(passes[pass_name])
				if res == 1:
					updated = True
			if updated:
				count += 1
				env.log(f"Updated {mat.name}")
				if self.animateTextures:
					sequences.animate_single_material(
						mat,
						context.scene.render.engine,
						export_location=sequences.ExportLocation.ORIGINAL)
		if count == 0:
			self.report(
				{'INFO'},
				f"No missing image blocks detected in {len(mat_list)} materials")

		self.report({'INFO'}, f"Updated {count} materials")
		self.track_param = context.scene.render.engine

		# NOTE: This is temporary
		addon_prefs = util.get_user_preferences(context)
		self.track_exporter = addon_prefs.MCprep_exporter_type
		return {'FINISHED'}

	def load_from_texturepack(self, mat):
		"""If image datablock not found in passes, try to directly load and assign"""
		env.log(f"Loading from texpack for {mat.name}", vv_only=True)
		canon, _ = generate.get_mc_canonical_name(mat.name)
		image_path = generate.find_from_texturepack(canon)
		if isinstance(image_path, MCprepError):
			if image_path.msg:
				env.log(image_path.msg)
			else:
				env.log(f"Find missing images: No source file found for {mat.name}")
			return False

		# even if images of same name already exist, load new block
		env.log(f"Find missing images: Creating new image datablock for {mat.name}")
		# do not use 'check_existing=False' to keep compatibility pre 2.79
		image = bpy.data.images.load(str(image_path), check_existing=True)

		engine = bpy.context.scene.render.engine
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE' or engine == 'BLENDER_EEVEE_NEXT':
			status = generate.set_cycles_texture(image, mat)
		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			status = generate.set_cycles_texture(image, mat)

		return status  # True or False


# -----------------------------------------------------------------------------
# Registration
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
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
