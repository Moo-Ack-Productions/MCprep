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


import bpy

import time

from .. import conf
from . import generate
from .. import tracking
from .. import util


# -----------------------------------------------------------------------------
# UV functions
# -----------------------------------------------------------------------------

def get_uv_bounds_per_material(obj):
	"""Return the maximum uv bounds per object, split per material

	Returns:
		dict: index of material name, value list of minx, maxx, miny, maxy,
			where values are in UV terms (0-1, unless wrapping)
	"""
	if not obj or obj.type != 'MESH':
		return {}
	mats = util.materialsFromObj([obj])
	if not mats:
		return {}

	active_uv = obj.data.uv_layers.active
	if not active_uv or not active_uv.data:
		return {}

	# order of minx, maxx, miny, maxy,
	# min's start with 1 so comparisons can go lower,
	# max's start with 0 so comparisons can go higher
	res = {mat.name: [1, 0, 1, 0] for mat in mats}

	# TODO: add other key for max_uvsize, to detect cases like lava and water
	# where multiple materials are in one but UVs split over multiple blocks.
	# In the meantime, threshold of 0.25 set by parent function is a sweetspot
	for poly in obj.data.polygons:
		m_index = poly.material_index
		mslot = obj.material_slots[m_index]
		if not mslot or not mslot.material:
			continue

		# TODO: Consider breaking early after reaching the first N hits of a
		# given material face within the same object, to avoid slowdown for
		# very large worlds. Butm early tests show that UV check is still small
		# compared to overall process time of either swap tex or anim tex.

		mkey = mslot.material.name
		for loop_ind in poly.loop_indices:
			# a loop could be an edge or face
			# loop = obj.data.loops[i] # This polygon/edge
			uvx, uvy = active_uv.data[loop_ind].uv
			if uvx < res[mkey][0]:  # min x
				res[mkey][0] = uvx
			if uvx > res[mkey][1]:  # max x
				res[mkey][1] = uvx
			if uvy < res[mkey][2]:  # min y
				res[mkey][2] = uvy
			if uvy > res[mkey][3]:  # max y
				res[mkey][3] = uvy
	return res


def detect_invalid_uvs_from_objs(obj_list):
	"""Detect all-in one combined images from concentrated UV layouts.

	Returns:
		bool: True for invalid layout, False of ok layout
		list: Of objects which appear to have invalid UVs
	"""
	invalid = False
	invalid_objects = []

	# if bounded coverage is less on either axis, treat invalid.
	# This threshold is slightly arbitrary, can't use 1.0 as some meshes are
	# rightfully not up against bounds of image. But generally, for combined
	# images the area covered is closer to 0.05
	thresh = 0.25
	conf.log("Doing check for invalid UV faces", vv_only=True)
	t0 = time.time()

	for obj in obj_list:
		uv_bounds = get_uv_bounds_per_material(obj)
		mis_mats = [
			mt for mt in uv_bounds
			if uv_bounds[mt][1] - uv_bounds[mt][0] < thresh
			and uv_bounds[mt][3] - uv_bounds[mt][2] < thresh
		]

		# if multiple materials on object and others don't alert, then toss
		# out as 'valid'; example scenario of the bottom face of a sign will
		# alert on its own (and is its own material), but rest of the sign is
		# indeed beyond and valid.
		if len(mis_mats) < len(uv_bounds):
			continue

		# otherwise, alert that this obj appears to have invalid UVs
		if mis_mats:
			invalid = True
			invalid_objects.append(obj)
	t1 = time.time()
	t_diff = t1 - t0  # round to .1s
	conf.log("UV check took {}s".format(t_diff), vv_only=True)
	return invalid, invalid_objects


# -----------------------------------------------------------------------------
# UV Operator definitions
# -----------------------------------------------------------------------------


class MCPREP_OT_scale_uv(bpy.types.Operator):
	bl_idname = "mcprep.scale_uv"
	bl_label = "Scale UV Faces"
	bl_description = "Scale all selected UV faces. See F6 or redo-last panel to adjust factor"
	bl_options = {'REGISTER', 'UNDO'}

	scale = bpy.props.FloatProperty(default=0.75, name="Scale")
	selected_only = bpy.props.BoolProperty(default=True, name="Seleced only")
	skipUsage = bpy.props.BoolProperty(default=False, options={'HIDDEN'})

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
		matchingVertIndex = list(chain.from_iterable(
			[p.vertices for p in Object.data.polygons]))
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

		if not context.object.data.uv_layers.active:
			self.report({'ERROR'}, "No active UV map found")
			return {'CANCELLED'}

		mode_initial = context.mode
		bpy.ops.object.mode_set(mode="OBJECT")
		ret = self.scale_uv_faces(context.object, self.scale)
		if mode_initial != 'OBJECT':
			bpy.ops.object.mode_set(mode="EDIT")

		if ret is not None:
			self.report({'ERROR'}, ret)
			conf.log("Error, " + ret)
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
			x = y = n = 0  # x,y,number of verts in loop for average purpose
			for loop_ind in f.loop_indices:
				# a loop could be an edge or face
				# The vertex data that loop entry refers to:
				# v = ob.data.vertices[l.vertex_index]
				# isolate to specific UV already used
				if not uv.data[loop_ind].select and self.selected_only is True:
					continue
				x += uv.data[loop_ind].uv[0]
				y += uv.data[loop_ind].uv[1]
				n += 1
			for loop_ind in f.loop_indices:
				if not uv.data[loop_ind].select and self.selected_only is True:
					continue
				uv.data[loop_ind].uv[0] = uv.data[loop_ind].uv[0]*(1-factor)+x/n*(factor)
				uv.data[loop_ind].uv[1] = uv.data[loop_ind].uv[1]*(1-factor)+y/n*(factor)
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
		default=False)
	threshold = bpy.props.FloatProperty(
		name="Threshold",
		description="How transparent pixels need to be to select",
		default=0.2,
		min=0.0,
		max=1.0)
	skipUsage = bpy.props.BoolProperty(default=False, options={'HIDDEN'})

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
				textures.append(None)  # no alpha channel anyways
				conf.log("No alpha channel for: " + image.name)
				continue
			textures.append(image)
		data = [None for tex in textures]

		uv = ob.data.uv_layers.active
		for f in ob.data.polygons:
			if len(f.loop_indices) < 3:
				continue  # don't select edges or vertices
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
				x = uv.data[loop.index].uv[0] % 1  # TODO: fix this wraparound hack
				y = uv.data[loop.index].uv[1] % 1
				shape.append((x, y))

			# print("The shape coords:")
			# print(shape)
			# could just do "the closest" pixel... but better is weighted area
			if not shape:
				continue

			xlist, ylist = tuple([list(tup) for tup in zip(*shape)])
			# not sure if I actually want to +0.5 to the values to get middle..
			xmin = round(min(xlist) * image.size[0]) - 0.5
			xmax = round(max(xlist) * image.size[0]) - 0.5
			ymin = round(min(ylist) * image.size[1]) - 0.5
			ymax = round(max(ylist) * image.size[1]) - 0.5
			conf.log(["\tSet size:", xmin, xmax, ymin, ymax], vv_only=True)

			# assuming faces are roughly rectangular, sum pixels a face covers
			asum = 0
			acount = 0
			for row in range(image.size[1]):
				if row < ymin or row > ymax:
					continue
				for col in range(image.size[0]):
					if col >= xmin and col <= xmax:
						try:
							asum += data[fnd][image.size[1] * row + col]
							acount += 1
						except IndexError as err:
							print("Index error while parsing col {}, row {}: {}".format(
								col, row, err))

			if acount == 0:
				acount = 1
			ratio = float(asum) / float(acount)
			if ratio < float(threshold):
				print("\t{} - Below threshold, select".format(ratio))
				f.select = True
			else:
				print("\t{} - above thresh, NO select".format(ratio))
				f.select = False
		return


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_scale_uv,
	MCPREP_OT_select_alpha_faces,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
