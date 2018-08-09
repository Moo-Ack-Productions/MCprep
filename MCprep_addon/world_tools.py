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
import random
import traceback

from . import conf
from . import util
from . import tracking


# -----------------------------------------------------------------------------
# supporting functions
# -----------------------------------------------------------------------------



# -----------------------------------------------------------------------------
# open mineways/jmc2obj related
# -----------------------------------------------------------------------------



class MCP_open_jmc2obj(bpy.types.Operator):
	"""Open the jmc2obj executbale"""
	bl_idname = "mcprep.open_jmc2obj"
	bl_label = "Open jmc2obj"
	bl_description = "Open the jmc2obj executbale"

	# poll, and prompt to download if not present w/ tutorial link
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	@tracking.report_error
	def execute(self,context):
		if self.skipUsage==False:
			tracking.trackUsage("open_program","jmc2obj")

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
	"""Utility class to prompt jmc2obj installing"""
	bl_idname = "mcprep.install_jmc2obj"
	bl_label = "Install jmc2obj"
	bl_description = "Prompt to install the jmc2obj world exporter"

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
		col = self.layout.colunm()
		col.scale_y = 0.7
		col.label("Then, go to MCprep's user preferences and set the jmc2obj")
		col.label(" path to jmc2obj_ver#.jar, for example")
		row = self.layout.row(align=True)
		row.operator("mcprep.open_preferences","Open MCprep preferences")
		row.operator("wm.url_open","Open tutorial").url =\
				"http://theduckcow.com/dev/blender/mcprep/"
		return

	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)

		return {'FINISHED'}


class MCP_open_mineways(bpy.types.Operator):
	"""Open the Mineways executbale"""
	bl_idname = "mcprep.open_mineways"
	bl_label = "Open Mineways"
	bl_description = "Open the Mineways executbale"

	# poll, and prompt to download if not present w/ tutorial link
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	@tracking.report_error
	def execute(self,context):
		if self.skipUsage==False:
			tracking.trackUsage("open_program","mineways")

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
		col = self.layout.colunm()
		col.scale_y = 0.7
		col.label("Then, go to MCprep's user preferences and set the")
		col.label(" Mineways path to Mineways.exe or Mineways.app, for example")
		row = self.layout.row(align=True)
		row.operator("mcprep.open_preferences","Open MCprep preferences")
		row.operator("wm.url_open","Open tutorial").url =\
				"http://theduckcow.com/dev/blender/mcprep/"
		return

	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Additional world tools
# -----------------------------------------------------------------------------


class MCP_prep_world(bpy.types.Operator):
	"""Class to prep world settings to appropriate default"""
	bl_idname = "mcprep.world"
	bl_label = "Prep World"
	bl_description = "Prep world render settings to something generally useful"

	@tracking.report_error
	def execute(self, context):

		print("WORK IN PROGRESS")
		Trigger_intentional_error_here

		return {'FINISHED'}



class MCP_add_sun_or_moon(bpy.types.Operator):
	"""Add a sun or moon setup into scene"""
	bl_idname = "mcprep.add_sun_or_moon"
	bl_label = "Add sun & moon"
	bl_description = "Add sun or moon to scene"

	@tracking.report_error
	def execute(self, context):

		print("WORK IN PROGRESS")
		if True:
			self.report({"ERROR"},"Not yet developed")
			return {'CANCELLED'}

		return {'FINISHED'}


class MCP_time_set(bpy.types.Operator):
	"""Set the time to a major unit"""
	bl_idname = "mcprep.time_set"
	bl_label = "Set time"
	bl_description = "Set the time affecting light, sun and moon position, similar to in-game commands"

	# subject center to place lighting around
	time_enum = bpy.props.EnumProperty(
		name="Time selection",
		description="Select between the different reflections",
		items=[
			("1000","Day","Time (day)=1,000"), # matches command
			("6000","Noon","Time=6,000"), # Sun is at zenith
			("12000","Sunset","Time=12,000"), # Approx matching resource
			("13000","Night","Time (night)=13,000"), # matches command
			("18000","Midnight","Time=18,000"), # matches reference
			("23000","Sunrise","Time set day=23,000") # sun first visible
			],
	)

	day_offset = bpy.props.IntProperty(
		name="Day offset",
		description="Offset by number of days (ie +/- 24000*n)",
		default=0
	)

	@tracking.report_error
	def execute(self, context):

		print("WORK IN PROGRESS")
		if True:
			self.report({"ERROR"},"Not yet developed")
			return {'CANCELLED'}

		# add the day offset first
		new_time = 24000*self.day_offset

		# switch against scenarios
		new_time += int(self.time_enum)

		context.scene.mcprep_props.world_time = new_time
		# insert keyframe if appropriate

		return {'FINISHED'}


def world_time_update(self, context):

	time = context.scene.mcprep_props.world_time
	# translate time into rotation of sun/moon rig
	# see: http://minecraft.gamepedia.com/Day-night_cycle
	# set to the armature.... would be even better if it was somehow driver-set.

	# if real python code requried to set this up, generate and auto-run python
	# script, though more ideally just set drivers based on the time param

	return


# -----------------------------------------------------------------------------
#	Above for UI
#	Below for register
# -----------------------------------------------------------------------------


def register():
	pass

def unregister():
	pass

