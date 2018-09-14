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

def animate_single_material(mat, engine, export_location='original', clear_cache=False):
	"""Animates texture for single material, including all passes.

	Args:
		mat: the existing material
		engine: target render engine
		export_location: enum of {original, texturepack, local}
		clear_cache: whether to pre-remove existing sequence if existing
	Returns:
		Bool (if affectable), Bool (if actually updated or not)
	"""
	mat_gen = util.nameGeneralize(mat.name)
	canon, form = generate.get_mc_canonical_name(mat_gen)

	if canon not in conf.json_data["blocks"]["animated"]:
		return False, False
	else:
		if conf.v:
			print("Animate-able texture material found: " + mat.name)

	# get the base image from the texturepack (cycles/BI general)
	image_path_canon = generate.find_from_texturepack(canon)
	if not image_path_canon:
		if conf.v:
			print("Could not fine texturepack for animate-able image")
		return True, False

	# apply the sequence if any found, will be empty dict if not
	tile_path_dict = generate_material_sequence(mat, image_path_canon, form,
										export_location, clear_cache)
	if tile_path_dict == {} and conf.v:
		print("No sequence/passes found to generate")
	if conf.v:
		print("Tilepathdict:")
		print(tile_path_dict)

	affected_materials = 0
	for pass_name in tile_path_dict:
		if not tile_path_dict[pass_name]:  # ie ''
			if conf.v: print("Skipping passname: " + pass_name)
			continue
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
			node = generate.get_node_for_pass(mat, pass_name)
			if not node:
				print("Did not get node for pass "+pass_name)
				continue
			set_sequence_to_texnode(node, tile_path_dict[pass_name])
			affected_materials += 1
		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			texture = generate.get_texlayer_for_pass(mat, pass_name)
			if not texture:
				print("Did not get texture for pass "+pass_name)
				continue
			set_sequence_to_texnode(texture, tile_path_dict[pass_name])
			affected_materials += 1
	return True, affected_materials>0


def generate_material_sequence(mat, image_path, form, export_location, clear_cache):
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
	if export_location == "local":
		if not bpy.data.filepath:
			raise Exception("Must save file before using local option save location")
		temp_abs = bpy.path.abspath(bpy.data.filepath)
		seq_path_base = os.path.join(os.path.dirname(temp_abs), "Textures")
	elif export_location == "original":
		seq_path_base =  os.path.dirname(bpy.path.abspath(image_path))

	if conf.v:
		print("Pre-sequence details")
		print(image_path)
		print(image_dict)
		print(img_pass_dict)
		print(seq_path_base)
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
		print("Running on file:")
		# print(passfile)
		print(bpy.path.abspath(passfile))

		# Create the sequence subdir (without race condition)
		pass_name = os.path.splitext(os.path.basename(passfile))[0]
		if not seq_path_base:
			seq_path = os.path.join(os.path.dirname(passfile), pass_name)
		else:
			seq_path = os.path.join(seq_path_base, pass_name)
		if conf.v:
			print("Using sequence directory: "+seq_path)

		try:  # check parent folder exists/create if needed
			os.mkdir(os.path.dirname(seq_path))  # as opposed to dirname(seq_path)
		except OSError as exc:
			if exc.errno == errno.EACCES:
				raise Exception(perm_denied)
			elif exc.errno != errno.EEXIST:
				raise
		try:  # check parent folder exists/create if needed
			os.mkdir(seq_path)  # as opposed to dirname(seq_path)
		except OSError as exc:
			if exc.errno == errno.EACCES:
				raise Exception(perm_denied)
			elif exc.errno != errno.EEXIST:
				raise

		# overwrite the files found if not cached
		if not os.path.isdir(seq_path):
			raise Exception("Path does not exist: "+seq_path)
		cached = [tile for tile in os.listdir(seq_path)
				if os.path.isfile(os.path.join(seq_path, tile))
				and tile.startswith(pass_name)]
		if cached:
			print("Cached detected")

		if clear_cache and cached:
			for tile in cached:
				try:
					os.remove(os.path.join(seq_path, tile))
				except OSError as exc:
					if exc.errno == errno.EACCES:
						raise Exception(perm_denied)

		# generate the sequences
		params = [] # TODO: get from json file
		if clear_cache or not cached:
			first_tile = export_image_to_sequence(passfile, params, seq_path, form)
		else:
			first_tile = os.path.join(seq_path, sorted(cached)[0])

		# save first tile to dict
		image_dict[img_pass] = bpy.path.abspath(first_tile)
	return image_dict


def export_image_to_sequence(image_path, params, output_folder=None, form=None):
	"""Convert image tiles into image sequence files.

	image_path: image filepath source
	params: Settings from the json file or otherwise on *how* to animate it
		e.g. ["linear", 2, false] = linear animation, 2 seconds long, and _?
	form: jmc2obj, Mineways, or None (default)
	Returns:
		Full path of first image on success.
	Does not auto load new images (or keep temporary ones created around)
	"""

	# use the source image's filepath, or fallback to blend file's,
	if not output_folder:
		output_folder = os.path.dirname(image_path)
	try:  # check parent folder exists/create if needed
		os.mkdir(output_folder)
	except OSError as exc:
		if exc.errno != errno.EEXIST:
			raise

	# load in the image_path to a temporary datablock
	image = bpy.data.images.load(image_path)

	# ind = self.get_sequence_int_index(first_img)
	# base_name = first_img[:-ind]
	# start_img = int(first_img[-ind:])
	basename, ext = os.path.splitext(os.path.basename(image_path))
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
			raise Exception("No Animate Textures Mineways support yet")

		# lst = list(img_tile.pixels)
		# start_ind = tile_pixel_size
		# img_tile.pixels = image.pixels[]
	if conf.v:
		print("Finished exporting frame sequence: " + basename)
	bpy.data.images.remove(image)

	return bpy.path.abspath(first_img)


def get_sequence_int_index(base_name):
	"""Return the index of the image name, number of digits at filename end."""
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


# -----------------------------------------------------------------------------
# Sequence texture classes
# -----------------------------------------------------------------------------


class McprepPrepAnimatedTextures(bpy.types.Operator):
	"""Replace static textures with animated versions, where present."""
	bl_idname = "mcprep.animate_textures"
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
		description = "Set where to export (or duplicate to) tile sequence images."
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options = {'HIDDEN'}
		)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

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

	track_function = "animate_tex"
	track_param = None
	track_exporter = None
	@tracking.report_error
	def execute(self, context):
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
		res = generate.detect_form(mats)
		if res=="mineways":
			self.report({'ERROR'}, "Not yet supported for Mineways - coming soon!")
			return {'CANCELLED'}

		affectable_materials = 0
		affected_materials = 0
		for mat in mats:
			affectable, affected = animate_single_material(
				mat, context.scene.render.engine,
				self.export_location, self.clear_cache)
			if affectable:
				affectable_materials += 1
			if affected:
				affected_materials += 1

		if affectable_materials == 0:
			self.report({"ERROR"},
				"No animate-able textures found on selected objects")
			return {'CANCELLED'}
		elif affected_materials == 0:
			self.report({"ERROR"},
				"Animated materials found, but none applied.")
			return {'CANCELLED'}
		else:
			self.report({'INFO'}, "Modified {} material(s)".format(
				affected_materials))
			self.track_param = context.scene.render.engine
			return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	pass


def unregister():
	pass
