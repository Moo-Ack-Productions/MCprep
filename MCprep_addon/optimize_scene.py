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
import addon_utils
from . import util
from .materials import generate


MAX_BOUNCES = 8


class MCprepOptimizerProperties(bpy.types.PropertyGroup):
	def scene_brightness(self, context):
		itms = [
			("BRIGHT", "Scene is bright", "Use this setting if your scene is mostly bright\nEx. outside during the day"), 
			("DARK", "Scene is dark", "Use this setting if your scene is mostly dark\nEx. caves, interiors, and outside at night")
		]
		return itms

	caustics_bool = bpy.props.BoolProperty(
		name="Caustics (Increases render times)",
		default=False,
		description="If checked allows cautics to be enabled"
	)
	motionblur_bool = bpy.props.BoolProperty(
		name="Motion Blur (increases render times)",
		default=False,
		description="If checked allows motion blur to be enabled"
	)
	volumetric_bool = bpy.props.BoolProperty(
		name="Volumetrics" if util.bv30() else "Volumetrics (Increases render times)",
		default=False
	)
	scene_brightness = bpy.props.EnumProperty(
		name="",
		description="Time of day in the scene",
		items=scene_brightness
	)
	quality_vs_speed = bpy.props.BoolProperty(
		name="Optimize based on Quality",
		default=True
	)


def panel_draw(self, context):
	row = self.layout.row()
	col = row.column()
	engine = context.scene.render.engine
	scn_props = context.scene.optimizer_props
	if engine == 'CYCLES':
		col.label(text="Options")
		volumetric_icon = "OUTLINER_OB_VOLUME" if scn_props.volumetric_bool else "OUTLINER_DATA_VOLUME"
		quality_icon = "INDIRECT_ONLY_ON" if scn_props.quality_vs_speed else "INDIRECT_ONLY_OFF"
		col.prop(scn_props, "volumetric_bool", icon=volumetric_icon)
		col.prop(scn_props, "quality_vs_speed", icon=quality_icon)

		col.label(text="Time of Day")
		col.prop(scn_props, "scene_brightness")
		col.prop(scn_props, "caustics_bool", icon="TRIA_UP")
		col.prop(scn_props, "motionblur_bool", icon="TRIA_UP")
		col.operator("mcprep.optimize_scene", text="Optimize Scene")
	else:
		col.label(text="Cycles Only :C")


class MCPrep_OT_optimize_scene(bpy.types.Operator):
	bl_idname = "mcprep.optimize_scene"
	bl_label = "Optimize Scene"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		global MAX_BOUNCES
		MAX_BOUNCES = 8

		# ! Calling this twice seems to remove all unused materials
		# TODO: find a better way of doing this
		bpy.ops.outliner.orphans_purge()
		bpy.ops.outliner.orphans_purge()
		prefs = util.get_preferences(context)
		cprefs = prefs.addons.get("cycles")
		scn_props = context.scene.optimizer_props

		# Get the compute device type.
		cycles_compute_device_type = None
		current_render_device = None
		has_active_device = cprefs.preferences.has_active_device()
		if cprefs is not None and has_active_device:
			cycles_compute_device_type = cprefs.preferences.compute_device_type
			current_render_device = bpy.context.scene.cycles.device

		# Sampling Settings.
		noise_threshold = 0.2

		# Light Bounces.
		diffuse = 2  # This is default because diffuse bounces don't need to be high.
		glossy = 1
		transmissive = 1
		volume = 0

		# Volumetric Settings.
		max_steps = 100

		# Filter Glossy and clamping settings.
		filter_glossy = 1
		clamping_indirect = 1

		# Motion blur, caustics, etc.
		motion_blur = scn_props.motionblur_bool
		reflective_caustics = scn_props.caustics_bool
		refractive_caustics = scn_props.caustics_bool

		# Optimizer Settings.
		quality = scn_props.quality_vs_speed

		# Render engine settings.
		if scn_props.volumetric_bool:
			volume = 2

		# Time of day.
		if scn_props.scene_brightness == "BRIGHT":
			noise_threshold = 0.2
		else:
			noise_threshold = 0.02

		# Compute device.
		if cycles_compute_device_type == "NONE":
			if quality:
				filter_glossy = 0.5
				max_steps = 200

			else:
				filter_glossy = 1
				max_steps = 50

			if util.bv30() is False:
				addon_utils.enable("render_auto_tile_size", default_set=True)

		elif cycles_compute_device_type in ("CUDA", "HIP"):
			if quality:
				filter_glossy = 0.5
				max_steps = 200

			else:
				filter_glossy = 1
				max_steps = 70

			if util.bv30() is False:
				addon_utils.enable("render_auto_tile_size", default_set=True)

		elif cycles_compute_device_type == "OPTIX":
			if quality:
				filter_glossy = 0.2
				max_steps = 250

			else:
				filter_glossy = 0.8
				max_steps = 80

			if util.bv30() is False:
				addon_utils.enable("render_auto_tile_size", default_set=True)

		elif util.bv30() is False:
			if cycles_compute_device_type == "OPENCL":
				if quality:
					filter_glossy = 0.9
					max_steps = 100

				else:
					filter_glossy = 1
					max_steps = 70

				addon_utils.enable("render_auto_tile_size", default_set=True)

		# Cycles Render Settings Optimizations.
		for mat in bpy.data.materials:
			mat_gen = util.nameGeneralize(mat.name)
			canon, form = generate.get_mc_canonical_name(mat_gen)
			if generate.checklist(canon, "reflective"):
				glossy += 1
			if generate.checklist(canon, "glass"):
				transmissive += 1

		if glossy > MAX_BOUNCES:
			MAX_BOUNCES = glossy

		if transmissive > MAX_BOUNCES:
			MAX_BOUNCES = transmissive

		# Unique changes.
		bpy.context.scene.cycles.adaptive_threshold = noise_threshold
		bpy.context.scene.cycles.blur_glossy = filter_glossy
		bpy.context.scene.cycles.volume_max_steps = max_steps
		bpy.context.scene.cycles.glossy_bounces = glossy
		bpy.context.scene.cycles.transmission_bounces = transmissive
		bpy.context.scene.cycles.caustics_reflective = reflective_caustics
		bpy.context.scene.cycles.caustics_refractive = refractive_caustics
		bpy.context.scene.cycles.sample_clamp_indirect = clamping_indirect
		bpy.context.scene.render.use_motion_blur = motion_blur
		bpy.context.scene.cycles.volume_bounces = volume
		bpy.context.scene.cycles.diffuse_bounces = diffuse

		# Other changes.
		bpy.context.scene.cycles.max_bounces = MAX_BOUNCES
		bpy.context.scene.render.use_simplify = True
		bpy.context.scene.render.simplify_subdivision = 0
		return {'FINISHED'}


classes = (
	MCprepOptimizerProperties,
	MCPrep_OT_optimize_scene
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)

	bpy.types.Scene.optimizer_props = bpy.props.PointerProperty(
		type=MCprepOptimizerProperties)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.optimizer_props
