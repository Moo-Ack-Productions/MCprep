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
from typing import Dict, List, Optional, Tuple

import bpy

import numpy as np
from numpy.typing import NDArray

from . import generate
from . import resource_pack
from . import sequences
from .. import tracking
from .. import util

from ..conf import MCprepError, env

# 4096 * 4, used to cap the amount of
# pixels summed when not using the fast
# prefilter with the Combine Images operator
#
# 4096 is the amount of pixels capped to,
# and 4 is the RGBA channels
RGBA_PIXELS_4096_MAX = 16384


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
	bl_description = "Find and merge duplicate images, remapping users to a single image"
	bl_options = {'REGISTER', 'UNDO'}

	group_by_name: bpy.props.BoolProperty(
		name="Group by Name",
		description="Compare duplicates using base names (e.g., 'Texture.001' matches 'Texture')",
		default=True)

	selection_only: bpy.props.BoolProperty(
		name="Selection only",
		description="Only check images used by materials on selected objects",
		default=False)

	strict_comparison: bpy.props.BoolProperty(
		name="Strict Comparison",
		description="Compare full image content instead of samples. More accurate, but slower for large images",
		default=False)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	track_function = "combine_images"
	@tracking.report_error
	def execute(self, context):
		# Setup image list
		if self.selection_only:
			if not context.selected_objects:
				self.report({'ERROR'}, "No objects selected")
				return {'CANCELLED'}

			target_images = set()
			processed_materials = set()

			for obj in context.selected_objects:
				if not hasattr(obj.data, "materials"):
					continue

				for mat in obj.data.materials:
					if not mat or mat in processed_materials:
						continue

					processed_materials.add(mat)
					if mat.use_nodes and mat.node_tree:
						for node in mat.node_tree.nodes:
							if node.type != 'TEX_IMAGE' or not node.image:
								continue
							target_images.add(node.image)

			if not target_images:
				self.report({'INFO'}, "No images found in selection")
				return {'FINISHED'}

			images_to_check = list(target_images)
		else:
			images_to_check = list(bpy.data.images)

		precount = len(bpy.data.images)

		# Group images
		#
		# Here we use a list, since we're just trying to get the
		# raw images at this point for comparison
		groups: List[Tuple[str, int, int, bpy.types.Image]] = []
		for img in images_to_check:
			if img.type in ('RENDER_RESULT', 'COMPOSITING') or img.use_fake_user:
				continue
			w, h = img.size
			# No data or empty image, nothing to compare, skip
			if w == 0 or h == 0 or not img.has_data:
				continue

			base_name = util.nameGeneralize(img.name) if self.group_by_name else "GLOBAL"
			groups.append((base_name, w, h, img))

		# Comparison and Remapping
		# Key: (base_name, w, h)
		# Value: List of (image_obj, comparison_array, sum)
		# store both the image (for remapping later on), the pixel array,
		# and pixel array sum for super fast prefilter
		unique_images: Dict[Tuple[str, int, int], List[Tuple[bpy.types.Image, NDArray[np.float32], Optional[np.float64]]]] = {}
		images_to_remove = []

		for base_name, w, h, img in groups:
			cur_img_key = (base_name, w, h)

			img_array = np.asarray(img.pixels)
			pix_sum: Optional[np.float64] = None

			# Approximation of a image content check used
			# if strict comparison is disabled. Unlike strict
			# comparison, which checks the actual pixels, this
			# sums up the pixels and uses that to represent the
			# image contents
			if not self.strict_comparison:
				num_pixels = w * h * 4
				stride = max(1, num_pixels // RGBA_PIXELS_4096_MAX)
				cur_img_data = img_array[::stride] if stride > 1 else img_array

				pix_sum = np.sum(cur_img_data)
	
			if cur_img_key not in unique_images:
				unique_images[cur_img_key] = [(img, img_array, pix_sum)]
				continue

			image_present = False
			present_image: Optional[bpy.types.Image] = None

			# Look through existing items in this Name/Size group
			for uni_image, uni_data, uni_sum in unique_images[cur_img_key]:
				# Fast prefilter, used as an alternative
				# to strict comparison
				if not self.strict_comparison and not pix_sum == uni_sum:
					continue
				elif not np.array_equal(uni_data, img_array):
					continue
				image_present = True
				present_image = uni_image
				break


			# If the image is present already, mark it
			# for removal, remap, and continue to the next image
			if image_present:
				images_to_remove.append(img)
				img.user_remap(present_image)
				continue

			# If the image is not present, add it to the list
			unique_images[cur_img_key].append((img, img_array, pix_sum))

		# Cleanup
		to_delete = [
			img for img in images_to_remove
			if img.users == 0 and not img.use_fake_user and not img.is_library_indirect]

		if to_delete:
			for img in to_delete:
				img.gl_free()
				img.buffers_free()
			bpy.data.batch_remove(ids=to_delete)

		# Report
		postcount = len(bpy.data.images)
		consolidated_count = precount - postcount

		if consolidated_count > 0:
			self.report({"INFO"}, f"Consolidated {consolidated_count} duplicate image{'s' if consolidated_count != 1 else ''} (Total: {precount} -> {postcount})")
		else:
			self.report({"INFO"}, "No duplicates found")
		return {'FINISHED'}


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

		internal_pack = resource_pack.get_default_pack()
		if isinstance(internal_pack, MCprepError):
			if internal_pack.msg:
				env.log(internal_pack.msg)
			return False

		image_path = resource_pack.find_texture_from_layers(canon, [internal_pack])
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
