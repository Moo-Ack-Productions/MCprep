# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2016 Patrick W. Crawford
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

import bpy
import random

from . import conf
from . import util


# -----------------------------------------------------------------------------
# supporting functions
# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------



class MCP_open_jmc2obj(bpy.types.Operator):
	"""Open the jmc2obj executbale"""
	bl_idname = "mcprep.open_jmc2obj"
	bl_label = "Open jmc2obj"
	bl_description = "Open the jmc2obj executbale"

	def execute(self,context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		res = util.open_program(addon_prefs.open_jmc2obj_path)

		if res !=0:
			self.reprot({'ERROR'},res)
			return {'CANCELLED'}
		else:
			self.report({'INFO'},"jmc2obj should open soon")
		
		return {'FINISHED'}


class MCP_open_mineways(bpy.types.Operator):
	"""Open the mineways executbale"""
	bl_idname = "mcprep.open_mineways"
	bl_label = "Open Mineways"
	bl_description = "Open the Mineways executbale"

	def execute(self,context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		util.open_program(addon_prefs.open_mineways_path)
		
		return {'FINISHED'}



# -----------------------------------------------------------------------------
#	Above for UI
#	Below for register
# -----------------------------------------------------------------------------



def register():
	pass

def unregister():
	pass

