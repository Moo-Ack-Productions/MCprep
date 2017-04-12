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

	# poll, and prompt to download if not present w/ tutorial link

	def execute(self,context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		res = util.open_program(addon_prefs.open_jmc2obj_path)

		if res ==-1:
			bpy.ops.mcprep.install_jmc2obj('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif res !=0:
			self.report({'ERROR'},res)
			return {'CANCELLED'}
		else:
			self.report({'INFO'},"jmc2obj should open soon")
		
		return {'FINISHED'}


class MCP_install_jmc2obj(bpy.types.Operator):
	"""Utility class to prompt Mineways installing"""
	bl_idname = "mcprep.install_jmc2obj"
	bl_label = "Install jmc2obj"
	bl_description = "Prompt to install the Mineways world exporter"

	# error message
	
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400, height=200)
	
	def draw(self, context):
		self.layout.label("Valid program path not found!")
		self.layout.separator()
		self.layout.label("Need to install jmc2obj?")
		self.layout.operator("wm.url_open","Click to download").url =\
				"http://www.jmc2obj.net/"
		split = self.layout.split() 
		self.layout.label("Then, go to MCprep's user preferences and set the jmc2obj")
		self.layout.label(" path to jmc2obj_ver#.jar, for example")
		self.layout.operator("mcprep.open_preferences","Open MCprep preferences")

		# tutorial link
		#self.layout.label("or Mineways.app, for example") 

	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)

		return {'FINISHED'}


class MCP_open_mineways(bpy.types.Operator):
	"""Open the mineways executbale"""
	bl_idname = "mcprep.open_mineways"
	bl_label = "Open Mineways"
	bl_description = "Open the Mineways executbale"

	# poll, and prompt to download if not present w/ tutorial link

	def execute(self,context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		res = util.open_program(addon_prefs.open_mineways_path)

		if res ==-1:
			bpy.ops.mcprep.install_mineways('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif res !=0:
			self.report({'ERROR'},res)
			return {'CANCELLED'}
		else:
			self.report({'INFO'},"Mineways should open soon")
		
		return {'FINISHED'}


class MCP_install_mineways(bpy.types.Operator):
	"""Utility class to prompt Mineways installing"""
	bl_idname = "mcprep.install_mineways"
	bl_label = "Install Mineways"
	bl_description = "Prompt to install the Mineways world exporter"

	# error message
	
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400, height=200)
	
	def draw(self, context):
		self.layout.label("Valid program path not found!")
		self.layout.separator()
		self.layout.label("Need to install Mineways?")
		self.layout.operator("wm.url_open","Click to download").url =\
				"http://www.realtimerendering.com/erich/minecraft/public/mineways/"
		split = self.layout.split() 
		self.layout.label("Then, go to MCprep's user preferences and set the")
		self.layout.label(" Mineways path to Mineways.exe or Mineways.app, for example")
		self.layout.operator("mcprep.open_preferences","Open MCprep preferences")

		# tutorial link
		#self.layout.label("or Mineways.app, for example") 

	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)

		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Above for UI
#	Below for register
# -----------------------------------------------------------------------------



def register():
	pass

def unregister():
	pass

