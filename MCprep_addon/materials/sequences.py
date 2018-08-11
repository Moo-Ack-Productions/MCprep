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

"""
Code relating to the conversion and generation, and to limited degree,
assigment of textures which are animated.
"""

import bpy
import errno
import os

from .. import conf
from . import generate
from .. import tracking
from .. import util

# -----------------------------------------------------------------------------
# Supporting functions
# -----------------------------------------------------------------------------

def export_image_to_sequence(image_path, params, output_folder=None, form=None):
	"""Convert image tiles into image sequence files.

	image: image filepath source
	form: jmc2obj, Mineways, or None (default)
	Returns full path of first image.
	Does not auto load new images (or keep temporary ones created around)
	"""

	# TODO: move this into a dedicated 'convert sequence' function that is
	# not dependent on MC prep names and forms.
	# path = "//"
	# if not image.packed_file:
	# 	if conf.v: print("Image is not packed: " + image.name)
	# 	path = bpy.path.abspath(image.filepath)
	# else:
	# 	blend_filedir = bpy.path.abspath(bpy.data.filepath)
	# 	path = os.path.join(os.path.dirname(blend_filedir),
	# 						"Textures", image.name) # plus extension

	# use the source image's filepath, or fallback to blend file's,
	if not output_folder:
		output_folder = os.path.dirname(image_path)
	try:  # check parent folder exists/create if needed
		os.mkdir(output_folder)
	except OSError as exc:
		if exc.errno != errno.EEXIST:
			raise

	basename, ext = os.path.splitext(os.path.basename(image_path))

	# load in the image_path to a temporary datablock
	image = bpy.data.images.load(image_path)

	# ind = self.get_sequence_int_index(first_img)
	# base_name = first_img[:-ind]
	# start_img = int(first_img[-ind:])

	tiles = image.size[1]/image.size[0]
	if int(tiles) != tiles:
		print("Not perfectly tiled image")
		return None
	else:
		tiles = int(tiles)

	pxlen = len(image.pixels)
	# channels = int(pxlen/image.size[0]/image.size[1])
	# src_pixels = list(image.pixels)

	first_img = None

	for i in range(tiles):
		if conf.v:
			print("Exporting sequence tile " + str(i))
		tile_name = basename + "_" + str(i+1).zfill(4)
		out_path = os.path.join(output_folder, tile_name + ext )
		if not first_img:
			first_img = out_path

		revi = tiles-i-1 # to reverse index, based on MC tile order

		# new image for copying pixels over to
		if form != "minways":
			img_tile = bpy.data.images.new(basename + "-seq-temp",
				image.size[0], image.size[0], alpha=(image.channels==4))
			img_tile.filepath = out_path

			if len(img_tile.pixels)*tiles != len(image.pixels):
				raise Exception("Mis-match of tile size and source sequence")
			start = int(pxlen/tiles*revi)
			end = int(pxlen/tiles*(revi+1))
			img_tile.pixels = image.pixels[start:end]
			img_tile.save()
			# verify it now exists
			if not os.path.isfile(out_path):
				raise Exception("Did not successfully save tile frame from sequence")
			bpy.data.images.remove(img_tile)
		else:
			img_tile = None
			Exception("Not yet supported for mineways")


		# lst = list(img_tile.pixels)
		# start_ind = tile_pixel_size
		# img_tile.pixels = image.pixels[]
	if conf.v:
		print("Finished exporting frame sequence: " + basename)
	bpy.data.images.remove(image)

	return bpy.path.abspath(first_img)


def get_sequence_int_index(base_name):
	"""Return the index of the image name."""
	# get the number of digits at end of filename
	ind = 0
	nums = '0123456789'
	for i in range(len(base_name)):
		if not base_name[-i-1] in nums:
			break
		ind += 1
	return ind


def set_sequence_to_texnode(node, image_path):
	"""Take first image of sequence and apply full sequence to a node.

	Note: this also works as-is where "node" is actually a texture block
	"""

	# TODO: Verify works for BI as-is

	image_path = bpy.path.abspath(image_path)
	base_dir = os.path.dirname(image_path)
	first_img = os.path.splitext(os.path.basename(image_path))[0]
	print("IMAGE path to apply: "+image_path + ", node/tex: "+node.name)

	ind = get_sequence_int_index(first_img)
	base_name = first_img[:-ind]
	start_img = int(first_img[-ind:])
	img_sets = [f for f in os.listdir(base_dir)
				if f.startswith(base_name)]
	img_count = len(img_sets)

	image_data = bpy.data.images.load(image_path)
	if conf.v:
		print("Loaded in " + str(image_data))
	image_data.source = 'SEQUENCE'
	node.image = image_data
	node.image_user.frame_duration = img_count
	node.image_user.frame_start = start_img
	node.image_user.frame_offset = 0
	node.image_user.use_cyclic = True
	node.image_user.use_auto_refresh = True


# def load_textures(texture):
# 	"""Load texture, reusing existing texture if present."""

# 	# ISN"T THIS DUPLICATIVE CODE? remove
#	# BUT, should this be incorporated to texture loading, to re-use blocks?

# 	# load the image only once
# 	base = bpy.path.basename(texture)
# 	# HERE load the iamge and set
# 	if base in bpy.data.images:
# 		if bpy.path.abspath(bpy.data.images[base].filepath) == bpy.path.abspath(texture):
# 			data_img = bpy.data.images[base]
# 			data_img.reload()
# 			if conf.v:print("Using already loaded texture")
# 		else:
# 			data_img = bpy.data.images.load(texture)
# 			if conf.v:print("Loading new texture image")
# 	else:
# 		data_img = bpy.data.images.load(texture)
# 		if conf.v:print("Loading new texture image")

# 	return data_img


# -----------------------------------------------------------------------------
# Sequence texture classes
# -----------------------------------------------------------------------------


class McprepPrepAnimatedTextures(bpy.types.Operator):
	"""Replace static textures with animated versions, where present."""
	bl_idname = "mcprep.animated_textures"
	bl_label = "Animate textures"

	clear_cache = bpy.props.BoolProperty(
		default = False,
		name = "Clear cache of previous animated sequence exports",
		description = "Always regenerate tile files, even if tiles may already exist"
		)
	export_location = bpy.props.EnumProperty(
		name = "Save location",
		items = [
			("original", "Next to current source image", "Save animation tiles next to source image"),
			("texturepack", "Inside MCprep texturepack", "Save animation tiles to current MCprep texturepack (useful for future re-use)"),
			("local", "Next to this blend file", "Save animation tiles next to current saved blend file")],
		description = "Set where to export (or duplicate to) tile sequence images"
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		subcol = col.column()
		subcol.scale_y = 0.7
		subcol.label("Converts still textures into animated ones")
		subcol.label("using the active resource pack's maps,")
		subcol.label("saves each animation tile to an image on disk.")
		col.prop(self, "export_location")
		col.prop(self, "clear_cache")

	@tracking.report_error
	def execute(self, context):

		# skip tracking if internal change
		if self.skipUsage==False:
			tracking.trackUsage("prep_animated",bpy.context.scene.render.engine)

		if not bpy.data.is_saved and self.export_location == "local":
			self.report({'ERROR'}, "File must be saved first if saving sequence locally")
			return {'CANCELLED'}

		objs = context.selected_objects
		if not len(objs):
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		mats = util.materialsFromObj(objs)
		if not len(mats):
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		affectable_materials = 0
		affected_materials = 0
		for mat in mats:
			mat_gen = util.nameGeneralize(mat.name)
			canon, form = generate.get_mc_canonical_name(mat_gen)

			if canon not in conf.json_data["blocks"]["animated"]:
				continue
			else:
				affectable_materials += 1
				if conf.v:
					print("Animated texture material found: " + mat.name)

			# get the base image from the texturepack (cycles/BI general)
			image_path_canon = generate.find_from_texturepack(canon)
			if not image_path_canon:
				if conf.v:
					print("Could not fine texturepack image")
				continue

			# apply the sequence if any found, will be empty dict if not
			tile_path_dict = self.generate_sequence(mat, image_path_canon, form)
			if tile_path_dict == {} and conf.v:
				print("No sequence/passes found to generate")
			if conf.v:
				print("Tilepathdict:")
				print(tile_path_dict)
			for pass_name in tile_path_dict:
				if not tile_path_dict[pass_name]:  # ie ''
					if conf.v: print("Skipping passname: " + pass_name)
					continue
				if context.scene.render.engine == "CYCLES":
					node = generate.get_node_for_pass(mat, pass_name)
					if not node:
						print("Did not get node for pass "+pass_name)
						continue
					set_sequence_to_texnode(node, tile_path_dict[pass_name])
					affected_materials += 1
				elif context.scene.render.engine == "INTERNAL":
					texture = generate.get_texlayer_for_pass(mat, pass_name)
					if not texture:
						print("Did not get texture for pass "+pass_name)
						continue
					set_sequence_to_texnode(texture, tile_path_dict[pass_name])
					affected_materials += 1

		if affectable_materials == 0:
			self.report({"ERROR"},
				"No animate-able textures found on selected objects")
			return {'CANCELLED'}
		elif affected_materials == 0:
			self.report({"ERROR"},
				"Animated materials found, but none applied.")
		else:
			self.report({'INFO'}, "Modified {} material(s)".format(
				affected_materials))
		return {'FINISHED'}

	def generate_sequence(self, mat, image_path, form):
		"""Generate sequence for single material given image passes found.

		Returns Dictionary of the image paths to the first tile of each
			material pass type detected (e.g. diffuse, specular, normal)
		"""

		# get the currently assigned image passes (normal, spec. etc)
		#image_dict = generate.get_textures(mat)
		image_dict = {}

		# gets available passes from current texturepack for given name
		img_pass_dict = generate.find_additional_passes(image_path)

		seq_path_base = None  # defaults to folder in resource pack
		# if self.export_location == "texturepack"
		if self.export_location == "local":
			seq_path_base = os.path.join(os.path.dirname(bpy.data.filepath),
											"Textures")
		elif self.export_location == "original":
			seq_path_base =  os.path.dirname(bpy.path.abspath(image_path))

		if conf.v:
			print("Pre-sequence details")
			print(image_path)
			print(image_dict)
			print(img_pass_dict)
			print("---")

		if form == "jmc2obj":
			print("DEBUG - jmc2obj aniamted texture detected")
		elif form == "mineways":
			print("DEBUG - mineways aniamted texture detected")
		else:
			print("DEBUG - other form of animated texture detected")

		perm_denied = "Permission denied, could not make folder - try " + \
			"running blender as admin"

		for img_pass in img_pass_dict:
			passfile = img_pass_dict[img_pass]

			# Create the sequence subdir (without race condition)
			pass_name = os.path.splitext(os.path.basename(passfile))[0]
			if not seq_path_base:
				seq_path = os.path.join(os.path.dirname(passfile), pass_name)
			else:
				seq_path = os.path.join(seq_path_base, pass_name)
			if conf.v:
				print("Using sequence directory: "+seq_path)


			try:  # check parent folder exists/create if needed
				os.mkdir(os.path.dirname(seq_path))
			except OSError as exc:
				if exc.errno == errno.EACCES:
					raise Exception(perm_denied)
				elif exc.errno != errno.EEXIST:
					raise

			# overwrite the files found if not cached
			cached = [tile for tile in os.listdir(seq_path)
					if os.path.isfile(os.path.join(seq_path, tile))
					and tile.startswith(pass_name)]
			print("Cached detected:")
			print(cached)

			if self.clear_cache and cached:
				for tile in cached:
					try:
						os.remove(os.path.join(seq_path, tile))
					except OSError as exc:
						if exc.errno == errno.EACCES:
							raise Exception(perm_denied)

			# generate the sequences
			if self.clear_cache or not cached:
				first_tile = export_image_to_sequence(passfile, seq_path, form)
			else:
				first_tile = os.path.join(seq_path, sorted(cached)[0])

			# save first tile to dict
			image_dict[img_pass] = bpy.path.abspath(first_tile)
		return image_dict


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	pass


def unregister():
	pass
