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
import os

from .. import conf
from . import generate
from .. import tracking
from .. import util

# -----------------------------------------------------------------------------
# Supporting functions
# -----------------------------------------------------------------------------

def export_image_to_sequence(image):
	"""Convert image tiles into image sequence files.

	Returns full path of first image.
	"""

	path = "//"
	if not image.packed_file:
		if conf.v: print("Image is not packed: " + image.name)
		path = bpy.path.abspath(image.filepath)
	else:
		blend_filedir = bpy.path.abspath(bpy.data.filepath)
		path = os.path.join(os.path.dirname(blend_filedir),
							"Textures", image.name) # plus extension
	# use the source image's filepath, or fallback to blend file's,
	base_dir = os.path.dirname(path)
	base_image, ext = os.path.splittext(os.path.basename(path))

	# ind = self.get_sequence_int_index(first_img)
	# base_name = first_img[:-ind]
	# start_img = int(first_img[-ind:])

	tiles = float(image.size[1])/image.size[0]
	if int(tiles) != tiles:
		print("Not perfectly tiled image")
		return None
	else:
		tiles = int(tiles)

	pxlen = len(image.pixels)
	channels = pxlen/image.size[0]/image.size[1]

	for i in range(tiles):
		tile_name = base_image + str(i).zfill(4)
		out_path = os.path.join(base_dir, tile_name + '.' + ext )

		# new image for copying pixels over to
		img_tile = bpy.data.images.new(base_image,
			image.size[0], image.size[0])
		# lst = list(img_tile.pixels)
		# start_ind = tile_pixel_size
		# img_tile.pixels = image.pixels[]

	return None


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


def set_animated_texture(node, image_path):
	"""Take first image of sequence and apply full sequence to node."""
	image_path = bpy.path.abspath(image_path)
	base_dir = os.path.dirname(image_path)
	first_img = os.path.splittext(os.path.basename(image_path))[0]

	ind = get_sequence_int_index(first_img)
	base_name = first_img[:-ind]
	start_img = int(first_img[-ind:])
	img_sets = [f for f in os.path.listdir(base_dir)
				if f.startswith(base_name)]
	img_count = len(img_sets)

	image_data = loadTexture(first_image) # TODO
	image_data.source = 'SEQUENCE'
	node.image_user.frame_duration = img_count
	node.image_user.frame_start = start_img
	node.image_user.frame_offset = 0
	node.image_user.use_cyclic = True
	node.image_user.use_auto_refresh = True


def load_textures(texture):
	"""Load texture, reusing existing texture if present."""

	# load the image only once
	base = bpy.path.basename(texture)
	# HERE load the iamge and set
	if base in bpy.data.images:
		if bpy.path.abspath(bpy.data.images[base].filepath) == bpy.path.abspath(texture):
			data_img = bpy.data.images[base]
			data_img.reload()
			if conf.v:print("Using already loaded texture")
		else:
			data_img = bpy.data.images.load(texture)
			if conf.v:print("Loading new texture image")
	else:
		data_img = bpy.data.images.load(texture)
		if conf.v:print("Loading new texture image")

	return data_img

# -----------------------------------------------------------------------------
# Sequence texture classes
# -----------------------------------------------------------------------------

class McprepPrepAnimatedTextures(bpy.types.Operator):
	"""Replace static textures with animated versions, where present."""
	bl_idname = "mcprep.animated_textures"
	bl_label = "Animate textures"

	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	@tracking.report_error
	def execute(self, context):

		# skip tracking if internal change
		if self.skipUsage==False:
			tracking.trackUsage("prep_animated",bpy.context.scene.render.engine)

		if not bpy.data.is_saved:
			self.report({'ERROR'}, "File must be saved first")
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
			print(mat.name)

			mat_gen = util.nameGeneralize(mat.name)
			canon, form = generate.get_mc_canonical_name(mat_gen)

			if canon not in conf.json_data["blocks"]["animated"]:
				continue
			else:
				affectable_materials += 1
				if conf.v: print("Animated texture material found: " + mat.name)

			if form == "jmc2obj":
				print("DEBUG - jmc2obj aniamted texture detected")
			elif form == "mineways":
				print("DEBUG - mineways aniamted texture detected")
			else:
				print("DEBUG - other form of animated texture detected")

			# TODO:
			# image_nodes = self.get_image(mat)
			# print(image_nodes)
			# for node in image_nodes:
			# 	path = export_image_to_sequence(node.image)
			# 	if not path:
			# 		continue  # was not an image sequence
			# 	set_animated_texture(node, path)
		if affectable_materials == 0:
			self.report({"ERROR"}, "No animate-able textures found on selected objects")
			return {'CANCELLED'}

		return {'FINISHED'}

	def get_image(self, mat):
		"""Get images used within material."""

		# TODO: replace with engine-cross compatible function
		images = []
		if not mat.use_nodes:
			return None
		for node in mat.node_tree.nodes:
			if node.type != 'TEX_IMAGE':
				continue
			if not node.image:
				continue
			images.append(node.image)
		return images


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	pass


def unregister():
	pass
