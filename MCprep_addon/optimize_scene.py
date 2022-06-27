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
MIN_BOUNCES = 2
CMP_BOUNCES = MIN_BOUNCES * 2


class MCprepOptimizerProperties(bpy.types.PropertyGroup):
	def scene_brightness(self, context):
		itms = [
			("BRIGHT", "Scene is bright", "Use this setting if your scene is mostly bright\nEx. outside during the day"), 
			("DARK", "Scene is dark", "Use this setting if your scene is mostly dark\nEx. caves, interiors, and outside at night")
		]
		return itms

	caustics_bool = bpy.props.BoolProperty(
		name="Caustics (slower)",
		default=False,
		description="If checked allows cautics to be enabled"
	)
	motionblur_bool = bpy.props.BoolProperty(
		name="Motion Blur (slower)",
		default=False,
		description="If checked allows motion blur to be enabled"
	)
	volumetric_bool = bpy.props.BoolProperty(
		name="Volumetrics" + " (slower)" if util.bv30() else "",
		default=False
	)
	scene_brightness = bpy.props.EnumProperty(
		name="",
		description="Time of day in the scene",
		items=scene_brightness
	)
	quality_vs_speed = bpy.props.BoolProperty(
		name="Optimize for Quality",
		default=True
	)


def panel_draw(context, element):
	box = element.box()
	col = box.column()
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
		col.row()
		col.label(text="")
		subrow = col.row()
		subrow.scale_y = 1.5
		subrow.operator("mcprep.optimize_scene", text="Optimize Scene")
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
		has_active_device = cprefs.preferences.has_active_device()
		if cprefs is not None and has_active_device:
			cycles_compute_device_type = cprefs.preferences.compute_device_type

		# Sampling Settings.
		NoiseThreshold = 0.2

		# Light Bounces.
		Diffuse = 2  # This is default because diffuse bounces don't need to be high
		Glossy = 1
		Transmissive = 1
		Volume = 0

		# Volumetric Settings.
		MaxSteps = 100

		# Filter Glossy and clamping settings.
		FilterGlossy = 1
		ClampingIndirect = 1

		# Motion blur, caustics, etc.
		MotionBlur = scn_props.motionblur_bool
		ReflectiveCaustics = scn_props.caustics_bool
		RefractiveCaustics = scn_props.caustics_bool

		# Optimizer Settings.
		Quality = scn_props.quality_vs_speed

		# Render engine settings.
		if scn_props.volumetric_bool:
			Volume = 2

		# Time of day.
		if scn_props.scene_brightness == "BRIGHT":
			NoiseThreshold = 0.2
		else:
			NoiseThreshold = 0.05

		# Compute device.
		if cycles_compute_device_type == "NONE":
			Samples = 128
			if Quality:
				MinimumSamples = 25
				FilterGlossy = 0.5
				MaxSteps = 200

			else:
				MinimumSamples = 10
				FilterGlossy = 1
				MaxSteps = 50

				if util.bv30() is False:
					val_1, val_2 = addon_utils.check("render_auto_tile_size")

					if val_1 is True:
						addon_utils.enable("render_auto_tile_size", default_set=True)
					else:
						bpy.context.scene.render.tile_x = 32
						bpy.context.scene.render.tile_y = 32

		elif cycles_compute_device_type in ("CUDA", "HIP"):
			if Quality:
				FilterGlossy = 0.5
				MaxSteps = 200

			else:
				FilterGlossy = 1
				MaxSteps = 70

			if util.bv30() is False:
				val_1, val_2 = addon_utils.check("render_auto_tile_size")
				if val_1 is True:
					addon_utils.enable("render_auto_tile_size", default_set=True)
				else:
					bpy.context.scene.render.tile_x = 256
					bpy.context.scene.render.tile_y = 256

		elif cycles_compute_device_type == "OPTIX":
			if Quality:
				FilterGlossy = 0.2
				MaxSteps = 250

			else:
				FilterGlossy = 0.8
				MaxSteps = 80

			if util.bv30() is False:
				val_1, val_2 = addon_utils.check("render_auto_tile_size")
				if val_1 is True:
					addon_utils.enable("render_auto_tile_size", default_set=True)
				else:
					bpy.context.scene.render.tile_x = 256
					bpy.context.scene.render.tile_y = 256

		elif cycles_compute_device_type == "OPENCL":
			if Quality:
				FilterGlossy = 0.9
				MaxSteps = 100

			else:
				FilterGlossy = 1
				MaxSteps = 70

			val_1, val_2 = addon_utils.check("render_auto_tile_size")
			if val_1 is True:
				addon_utils.enable("render_auto_tile_size", default_set=True)
			else:
				bpy.context.scene.render.tile_x = 256
				bpy.context.scene.render.tile_y = 256

		# Cycles Render Settings Optimizations.
		for mat in bpy.data.materials:
			matGen = util.nameGeneralize(mat.name)
			canon, form = generate.get_mc_canonical_name(matGen)
			if generate.checklist(canon, "reflective"):
				Glossy += 1
			if generate.checklist(canon, "glass"):
				Transmissive += 1

		if Glossy >= CMP_BOUNCES:
			Glossy = Glossy // 2
		if Transmissive >= CMP_BOUNCES:
			Transmissive = Transmissive // 2

		local_max_bounce = MAX_BOUNCES
		if Glossy > MAX_BOUNCES:
			local_max_bounce = Glossy

		if Transmissive > local_max_bounce:
			local_max_bounce = Transmissive

		# Cycles changes.
		if util.min_bv((2, 90)):
			bpy.context.scene.cycles.adaptive_threshold = NoiseThreshold
		bpy.context.scene.cycles.blur_glossy = FilterGlossy
		bpy.context.scene.cycles.volume_max_steps = MaxSteps
		bpy.context.scene.cycles.glossy_bounces = Glossy
		bpy.context.scene.cycles.transmission_bounces = Transmissive
		bpy.context.scene.cycles.caustics_reflective = ReflectiveCaustics
		bpy.context.scene.cycles.caustics_refractive = RefractiveCaustics
		bpy.context.scene.cycles.sample_clamp_indirect = ClampingIndirect
		bpy.context.scene.cycles.volume_bounces = Volume
		bpy.context.scene.cycles.diffuse_bounces = Diffuse
		bpy.context.scene.cycles.max_bounces = local_max_bounce

		# Render changes.
		bpy.context.scene.render.use_motion_blur = MotionBlur
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
