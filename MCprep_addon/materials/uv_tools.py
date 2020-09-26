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

from .. import conf
from . import generate
from .. import tracking
from .. import util


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


# -----------------------------------------------------------------------------
#	Registration
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
