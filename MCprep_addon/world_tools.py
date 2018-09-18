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

	track_function = "open_program"
	track_param = "jmc2obj"
	@tracking.report_error
	def execute(self,context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		res = util.open_program(addon_prefs.open_jmc2obj_path)

		if res ==-1:
			bpy.ops.mcprep.install_jmc2obj('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif res !=0:
			self.report({'ERROR'},str(res))
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
		return wm.invoke_popup(self, width=400*util.ui_scale(), height=200)

	def draw(self, context):
		self.layout.label("Valid program path not found!")
		self.layout.separator()
		self.layout.label("Need to install jmc2obj?")
		self.layout.operator("wm.url_open","Click to download").url =\
				"http://www.jmc2obj.net/"
		split = self.layout.split()
		col = self.layout.column()
		col.scale_y = 0.7
		col.label("Then, go to MCprep's user preferences and set the jmc2obj")
		col.label(" path to jmc2obj_ver#.jar, for example")
		row = self.layout.row(align=True)
		row.operator("mcprep.open_preferences","Open MCprep preferences")
		row.operator("wm.url_open","Open tutorial").url =\
				"http://theduckcow.com/dev/blender/mcprep/setup-world-exporters/"
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

	track_function = "open_program"
	track_param = "mineways"
	@tracking.report_error
	def execute(self,context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		res = util.open_program(addon_prefs.open_mineways_path)

		if res ==-1:
			bpy.ops.mcprep.install_mineways('INVOKE_DEFAULT')
			return {'CANCELLED'}
		elif res !=0:
			self.report({'ERROR'},str(res))
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
		return wm.invoke_popup(self, width=400*util.ui_scale(), height=200)

	def draw(self, context):
		self.layout.label("Valid program path not found!")
		self.layout.separator()
		self.layout.label("Need to install Mineways?")
		self.layout.operator("wm.url_open","Click to download").url =\
				"http://www.realtimerendering.com/erich/minecraft/public/mineways/"
		split = self.layout.split()
		col = self.layout.column()
		col.scale_y = 0.7
		col.label("Then, go to MCprep's user preferences and set the")
		col.label(" Mineways path to Mineways.exe or Mineways.app, for example")
		row = self.layout.row(align=True)
		row.operator("mcprep.open_preferences","Open MCprep preferences")
		row.operator("wm.url_open","Open tutorial").url =\
				"http://theduckcow.com/dev/blender/mcprep/setup-world-exporters/"
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
	bl_options = {'REGISTER', 'UNDO'}

	track_function = "prep_world"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		engine = bpy.context.scene.render.engine
		self.track_param = engine
		if engine == 'CYCLES' or engine == 'BLENDER_EEVEE':
			self.prep_world_cycles(context)
		elif engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			self.prep_world_internal(context)
		else:
			self.report({'ERROR'}, "Must be cycles or blender internal renderer")
		return {'FINISHED'}

	def prep_world_cycles(self, context):
		if not context.scene.world or not context.scene.world.use_nodes:
			context.scene.world.use_nodes = True

		world_nodes = context.scene.world.node_tree.nodes
		world_links = context.scene.world.node_tree.links
		# if len(world_nodes) <= 2:
		world_nodes.clear()
		skynode = world_nodes.new("ShaderNodeTexSky")
		background = world_nodes.new("ShaderNodeBackground")
		output = world_nodes.new("ShaderNodeOutputWorld")
		skynode.location = (-280, 300)
		background.location = (10, 300)
		output.location = (300, 300)
		world_links.new(skynode.outputs["Color"], background.inputs[0])
		world_links.new(background.outputs["Background"], output.inputs[0])

		context.scene.world.light_settings.use_ambient_occlusion = False
		context.scene.cycles.caustics_reflective = False
		context.scene.cycles.caustics_refractive = False

		# higher = faster, though potentially noisier; this is a good balance
		context.scene.cycles.light_sampling_threshold = 0.1
		context.scene.cycles.max_bounces = 8

		# Renders faster at a (minor?) cost of the image output
		# TODO: given the output change, consider make a bool toggle for this
		bpy.context.scene.render.use_simplify = True
		bpy.context.scene.cycles.ao_bounces = 2
		bpy.context.scene.cycles.ao_bounces_render = 2

	def prep_world_internal(self, context):
		# check for any suns with the sky setting on;
		context.scene.world.use_nodes = False
		context.scene.world.horizon_color = (0.00938029, 0.0125943, 0.0140572)
		context.scene.world.light_settings.use_ambient_occlusion = True
		context.scene.world.light_settings.ao_blend_type = 'MULTIPLY'
		context.scene.world.light_settings.ao_factor = 0.1
		context.scene.world.light_settings.use_environment_light = True
		context.scene.world.light_settings.environment_energy = 0.05
		context.scene.render.use_shadows = True
		context.scene.render.use_raytrace = True
		context.scene.render.use_textures = True

		# check for any sunlamps with sky setting
		sky_used = False
		for lamp in context.scene.objects:
			if lamp.type != "LAMP" or lamp.data.type != "SUN":
				continue
			if lamp.data.sky.use_sky:
				sky_used = True
				break
		if sky_used:
			if conf.v: print("MCprep sky being used with atmosphere")
			context.scene.world.use_sky_blend = False
			context.scene.world.horizon_color = (0.00938029, 0.0125943, 0.0140572)
		else:
			if conf.v: print("No MCprep sky with atmosphere")
			context.scene.world.use_sky_blend = True
			context.scene.world.horizon_color = (0.647705, 0.859927, 0.940392)
			context.scene.world.zenith_color = (0.0954261, 0.546859, 1)


class MCP_add_world_time(bpy.types.Operator):
	"""Add sun, moon (WIP), and world time settings to scene."""
	bl_idname = "mcprep.add_world_time"
	bl_label = "Add sun/time"
	bl_options = {'REGISTER', 'UNDO'}

	remove_existing_suns = bpy.props.BoolProperty(
		name = "Remove suns",
		description = "Remove any existing sunlamps",
		default = True
		)

	track_function = "world_time"
	track_param = None
	@tracking.report_error
	def execute(self, context):

		new_objs = []
		new_sun = self.create_sunlamp(context)
		new_objs.append(new_sun)

		# create sun mesh
		# create moon mesh (and lamp)
			# could we actually create these as world decals instead of meshes?
		# setup drivers according to time setting
		# set a reasonable initial default

		if "mcprep_world" in bpy.data.groups:
			bpy.data.groups["mcprep_world"].name = "mcprep_world_old"
		time_group = bpy.data.groups.new("mcprep_world")
		for obj in new_objs:
			time_group.objects.link(obj)

		return {'FINISHED'}

	def create_sunlamp(self, context):
		if self.remove_existing_suns:
			for lamp in context.scene.objects:
				if lamp.type != "LAMP" or lamp.data.type != "SUN":
					continue
				context.scene.objects.unlink(lamp)
				bpy.data.objects.remove(lamp)

		newlamp = bpy.data.lamps.new("Sun", "SUN")
		obj = bpy.data.objects.new("Sunlamp", newlamp)
		obj.location = (0,0,20)
		obj.rotation_euler[0] = 0.481711
		obj.rotation_euler[1] = 0.303687
		obj.rotation_euler[1] = 0.527089
		context.scene.objects.link(obj)
		context.scene.update()
		# update horizon info
		engine = bpy.context.scene.render.engine

		if engine == 'BLENDER_RENDER' or engine == 'BLENDER_GAME':
			context.scene.world.horizon_color = (0.00938029, 0.0125943, 0.0140572)
			obj.data.sky.use_sky = True  # use sun orientation settings if BI
			obj.data.shadow_method = 'RAY_SHADOW'
			obj.data.shadow_soft_size = 0.5
			context.scene.world.use_sky_blend = False

			for lamp in context.scene.objects:
				if lamp.type != "LAMP" or lamp.data.type != "SUN":
					continue
				if lamp == obj:
					continue
				lamp.data.sky.use_sky = False
		self.track_param = engine
		return obj


class MCP_time_set(bpy.types.Operator):
	"""Set the time affecting light, sun and moon position, similar to in-game commands"""
	bl_idname = "mcprep.time_set"
	bl_label = "Set time of day"
	bl_options = {'REGISTER', 'UNDO'}

	# subject center to place lighting around
	time_enum = bpy.props.EnumProperty(
		name="Time selection",
		description="Select between the different reflections",
		items=[
			("1000","Day","Time (day)=1,000, morning time"),
			("6000","Noon","Time=6,000, sun is at zenith"),
			("12000","Sunset","Time=12,000, sun starts setting"), # Approx matching resource
			("13000","Night","Time (night)=13,000"), # matches command
			("18000","Midnight","Time=18,000, moon at zenish"), # matches reference
			("23000","Sunrise","Time set day=23,000, sun first visible")
			],
	)
	day_offset = bpy.props.IntProperty(
		name="Day offset",
		description="Offset by number of days (ie +/- 24000*n)",
		default=0
	)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

	def draw(self, context):
		self.layout.prop(self, "time_enum")
		self.layout.prop(self, "day_offset")
		self.layout.prop(self, "keyframe")

	@tracking.report_error
	def execute(self, context):
		new_time = 24000*self.day_offset
		new_time += int(self.time_enum)
		context.scene.mcprep_props.world_time = new_time
		if bpy.context.scene.tool_settings.use_keyframe_insert_auto:
			if not context.scene.animation_data:
				context.scene.animation_data_create()
			anim_data = context.scene.animation_data
			if not anim_data.action:
				ac = bpy.data.actions.new("SceneAnimation")
				anim_data.action = ac
			context.scene.mcprep_props.keyframe_insert(
				"world_time")

		return {'FINISHED'}


def world_time_update(self, context):
	"""Handler which updates the current world time on a frame change.

	Maybe don't need this in favor of using a driver for simplicity
	"""

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

