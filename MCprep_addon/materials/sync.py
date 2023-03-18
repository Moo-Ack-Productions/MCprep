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
from bpy.app.handlers import persistent

from ..conf import env 
from .. import tracking
from .. import util

from ..conf import env

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

@persistent
def clear_sync_cache(scene):
	env.log("Resetting sync mat cache", vv_only=True)
	env.material_sync_cache = None


def get_sync_blend(context):
	"""Return the sync blend file path that might exist, based on active pack"""
	resource_pack = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	return os.path.join(resource_pack, "materials.blend")


def reload_material_sync_library(context):
	"""Reloads the library and cache"""
	sync_file = get_sync_blend(context)
	if not os.path.isfile(sync_file):
		env.material_sync_cache = []
		return

	with bpy.data.libraries.load(sync_file) as (data_from, _):
		env.material_sync_cache = list(data_from.materials)
	env.log("Updated sync cache", vv_only=True)


def material_in_sync_library(material, context):
	"""Returns true if the material is in the sync mat library blend file"""
	if env.material_sync_cache is None:
		reload_material_sync_library(context)
	if util.nameGeneralize(material.name) in env.material_sync_cache:
		return True
	elif material.name in env.material_sync_cache:
		return True
	return False


def sync_material(context, material, link, replace):
	"""If found, load and apply the material found in a library.

	Returns:
		0 if nothing modified, 1 if modified
		None if no error or string if error
	"""
	if material.name in env.material_sync_cache:
		import_name = material.name
	elif util.nameGeneralize(material.name) in env.material_sync_cache:
		import_name = util.nameGeneralize(material.name)

	# if link is true, check library material not already linked
	sync_file = get_sync_blend(context)
	init_mats = bpy.data.materials[:]
	util.bAppendLink(os.path.join(sync_file, "Material"), import_name, link)

	imported = set(bpy.data.materials[:]) - set(init_mats)
	if not imported:
		return 0, "Could not import " + str(material.name)
	new_material = list(imported)[0]

	# 2.78+ only, else silent failure
	res = util.remap_users(material, new_material)
	if res != 0:
		# try a fallback where we at least go over the selected objects
		return 0, res
	if replace is True:
		bpy.data.materials.remove(material)

	return 1, None


# -----------------------------------------------------------------------------
# Operator
# -----------------------------------------------------------------------------


class MCPREP_OT_sync_materials(bpy.types.Operator):
	"""Synchronize materials with those in the active pack's materials.blend file"""
	bl_idname = "mcprep.sync_materials"
	bl_label = "Sync Materials"
	bl_options = {'REGISTER', 'UNDO'}

	selected = bpy.props.BoolProperty(
		name="Only selected",
		description=(
			"Affect only the materials on selected objects, otherwise "
			"sync all materials in blend file"),
		default=True)
	link = bpy.props.BoolProperty(
		name="Link",
		description="Link instead of appending material",
		default=False)
	replace_materials = bpy.props.BoolProperty(
		name="Replace",
		description="Delete the local materials being synced, where matched",
		default=False)
	skipUsage = bpy.props.BoolProperty(
		default=False,
		options={'HIDDEN'})

	track_function = "sync_materials"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		inital_selection = context.selected_objects
		initial_active = context.object

		sync_file = get_sync_blend(context)
		if not os.path.isfile(sync_file):
			if not self.skipUsage:
				self.report({'ERROR'}, "Sync file not found: " + sync_file)
			return {'CANCELLED'}

		if sync_file == bpy.data.filepath:
			if not self.skipUsage:
				self.report({'ERROR'}, "This IS the sync file - can't sync with itself!")
			return {'CANCELLED'}

		# get list of selected objects
		if self.selected is True:
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
		else:
			mat_list = list(bpy.data.materials)

		# consider force reloading the material library blend
		eligible = 0
		modified = 0
		last_err = None
		for mat in mat_list:
			if not material_in_sync_library(mat, context):
				continue
			affected, err = sync_material(
				context, mat, self.link, self.replace_materials)
			eligible += 1
			modified += affected
			if err:
				last_err = err

		if last_err:
			env.log("Most recent error during sync:" + str(last_err))

		# Re-establish initial state, as append material clears selections
		for obj in inital_selection:
			util.select_set(obj, True)
		util.set_active_object(context, initial_active)

		if eligible == 0:
			self.report({'INFO'}, "No materials matched the sync library")
			return {'CANCELLED'}
		elif modified == 0:
			if not self.skipUsage:
				self.report({'ERROR'}, (
					"No materials modified, though some "
					"detected in the sync library: ") + last_err)
			# raise exception? This shouldn't occur
			return {'CANCELLED'}
		elif modified == 1:
			self.report({'INFO'}, "Synced 1 material")
		else:
			self.report({'INFO'}, "Synced {} materials".format(modified))
		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	MCPREP_OT_sync_materials,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.app.handlers.load_post.append(clear_sync_cache)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	try:
		bpy.app.handlers.load_post.remove(clear_sync_cache)
	except:
		pass
