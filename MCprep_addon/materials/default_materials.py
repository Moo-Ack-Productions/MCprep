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
from .. import tracking
from .. import util
from . import sync

def sync_default_material(context, material, default_material):
    """
    This is ideitical to the normal sync materials function but it also copies
    the material and changes the name
    """
    if default_material in conf.material_sync_cache:
        import_name = default_material
    elif util.nameGeneralize(default_material) in conf.material_sync_cache:
        import_name = util.nameGeneralize(default_material)

    # if link is true, check library material not already linked
    sync_file = sync.get_sync_blend(context)
    
    # I'm no Python expert (I prefer C++) but Google tells me that this means to copy all the elements 
    # -StandingPad
    init_mats = bpy.data.materials[:]
    util.bAppendLink(os.path.join(sync_file, "Material"), import_name, False) # no linking

    imported = set(bpy.data.materials[:]) - set(init_mats)
    if not imported:
        return 0, "Could not import " + str(material.name)
    new_material = list(imported)[0]
    
    # Copy the material and change the name
    NewDefaultMaterial = new_material.copy()
    NewDefaultMaterial.name = material.name + "_sync_default"
    
    # 2.78+ only, else silent failure
    res = util.remap_users(material, NewDefaultMaterial)
    if res != 0:
        # try a fallback where we at least go over the selected objects
        return 0, res
    
    # remove the old material since we're changing the default and we don't
    # want to overwhelm users
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
    default="cycles")
    
    SIMPLE = "simple"
    PBR = "pbr"

    track_function = "sync_default_materials"
    track_param = None
    @tracking.report_error
    def execute(self, context):        
        # ------------------------------ Sync file stuff ----------------------------- #
        sync_file = sync.get_sync_blend(context)
        if not os.path.isfile(sync_file):
            self.report({'ERROR'}, "Sync file not found: " + sync_file)
            return {'CANCELLED'}

        # ------------------------- Find the default material ------------------------ #
        MaterialName = f"default_{self.SIMPLE if not self.UsePBR else self.PBR}_{self.Engine}"
        if not sync.material_in_sync_library(MaterialName, context):
            self.report({'ERROR'}, "No default material found")
            return {'CANCELLED'}
        
        # ------------------------------ Sync materials ------------------------------ #
        mat_list = list(bpy.data.materials)
        for mat in mat_list:
            affected, err = sync.sync_default_material(context, mat, MaterialName) # no linking
            
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