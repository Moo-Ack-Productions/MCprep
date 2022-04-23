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

from .. import conf
from .. import tracking
from .. import util
import sync

def sync_default_material(context, material, link, replace):
	"""If found, load and apply the material found in a library.

	Returns:
		0 if nothing modified, 1 if modified
		None if no error or string if error
	"""
	if material.name in conf.material_sync_cache:
		import_name = material.name
	elif util.nameGeneralize(material.name) in conf.material_sync_cache:
		import_name = util.nameGeneralize(material.name)

	# if link is true, check library material not already linked
	sync_file = sync.get_sync_blend(context)
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

class MCPREP_OT_default_material(bpy.types.Operator):
    bl_idname = "mcprep.sync_default_materials"
    bl_label = "Sync Default Materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    UsePBR = bpy.props.BoolProperty(
    name="Use PBR",
    description="Use PBR or not",
    default=False)

    Engine = bpy.props.StringProperty(
    name="Engine To Use",
    description="Defines the engine to use",
    default="CYCLES")

    track_function = "sync_default_materials"
    track_param = None
    @tracking.report_error
    def execute(self, context):        
        # ------------------------------ Sync file stuff ----------------------------- #
        sync_file = sync.get_sync_blend(context)
        if not os.path.isfile(sync_file):
            if not self.skipUsage:
                self.report({'ERROR'}, "Sync file not found: " + sync_file)
            return {'CANCELLED'}

        # ------------------------- Find the default material ------------------------ #
        MaterialName = f"default_{self.UsePBR}_{self.Engine}"
        if not sync.material_in_sync_library(MaterialName, context):
            self.report({'ERROR'}, "No default material found")
            return {'CANCELLED'}
        
        # --------------------------- Get default material --------------------------- #
        affected, err = sync.sync_default_material(context, MaterialName, False, True) # no linking
        
        if err:
            conf.log("Most recent error during sync:" + str(err))
            
        return {'FINISHED'}
    
classes = (
	MCPREP_OT_default_material,
)

def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)
	bpy.app.handlers.load_post.append(sync.clear_sync_cache)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	try:
		bpy.app.handlers.load_post.remove(sync.clear_sync_cache)
	except:
		pass