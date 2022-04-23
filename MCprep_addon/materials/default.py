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
        MaterialName = f"default_{self.UsePBR}_{self.Engine}"
        sync_file = sync.get_sync_blend(context)
        if not os.path.isfile(sync_file):
            if not self.skipUsage:
                self.report({'ERROR'}, "Sync file not found: " + sync_file)
            return {'CANCELLED'}
        
        