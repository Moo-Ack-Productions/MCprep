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


# TODO: Improving material optimization
# TODO: Doing a very small optimization before rendering 
# TODO: Taking advantage of more powerful optimizations that are extremely scene dependent
import bpy
import addon_utils
from . import util
from .materials import generate


MAX_BOUNCES = 8
MIN_BOUNCES = 2
CMP_BOUNCES = MIN_BOUNCES * 2
MAX_FILTER_GLOSSY = 1.0
MAX_STEPS = 200
MIN_SCRAMBLING_MULTIPLIER = 0.35
CMP_SCRAMBLING_MULTIPLIER = MIN_SCRAMBLING_MULTIPLIER * 2


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
	scene_brightness = bpy.props.EnumProperty(
		name="",
		description="Time of day in the scene",
		items=scene_brightness
	)
	quality_vs_speed = bpy.props.BoolProperty(
		name="Optimize for Quality",
		default=True
	)
	simplify = bpy.props.BoolProperty(
		name="Simplify the viewport",
		default=True
	)
	scrambling_unsafe = bpy.props.BoolProperty(
		name="Automatic Scrambling Distance",
		default=False
	)
	preview_scrambling = bpy.props.BoolProperty(
		name="Preview Scrambling",
		default=True
	)


def panel_draw(context, element):
	box = element.box()
	col = box.column()
	engine = context.scene.render.engine
	scn_props = context.scene.optimizer_props
	if engine == 'CYCLES':
		col.label(text="Options")
		quality_icon = "INDIRECT_ONLY_ON" if scn_props.quality_vs_speed else "INDIRECT_ONLY_OFF"
		col.prop(scn_props, "quality_vs_speed", icon=quality_icon)
		col.prop(scn_props, "simplify", icon=quality_icon)

		col.label(text="Time of Day")
		col.prop(scn_props, "scene_brightness")
		col.prop(scn_props, "caustics_bool", icon="TRIA_UP")
		col.prop(scn_props, "motionblur_bool", icon="TRIA_UP")
		col.row()
		col.label(text="Unsafe Options! Use at your own risk!")
		if util.bv30():
			scrambling_unsafe_icon = "TRIA_DOWN" if scn_props.scrambling_unsafe else "TRIA_RIGHT"
			col.prop(scn_props, "scrambling_unsafe", icon=scrambling_unsafe_icon)
			if scn_props.scrambling_unsafe:
				col.prop(scn_props, "preview_scrambling")
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
		Samples = bpy.context.scene.cycles.samples # We will be doing some minor adjustments to the sample count
		MinimumSamples = None
		NoiseThreshold = 0.2


		# Light Bounces.
		Diffuse = 2  # This is default because diffuse bounces don't need to be high
		Glossy = 1
		Transmissive = 1
		Volume = 2

		# Volumetric Settings.
		MaxSteps = 100
		SteppingRate = 5

		# Filter Glossy and clamping settings.
		FilterGlossy = 1
		ClampingIndirect = 1

		# Motion blur, caustics, etc.
		MotionBlur = scn_props.motionblur_bool
		ReflectiveCaustics = scn_props.caustics_bool
		RefractiveCaustics = scn_props.caustics_bool

		# Optimizer Settings.
		Quality = scn_props.quality_vs_speed
		UseScrambling = scn_props.scrambling_unsafe
		PreviewScrambling = scn_props.preview_scrambling
		ScramblingMultiplier = MIN_SCRAMBLING_MULTIPLIER

		# Time of day.
		if scn_props.scene_brightness == "BRIGHT":
			NoiseThreshold = 0.2
		else:
			Samples += 20
			NoiseThreshold = 0.05
		
		if Quality:
			MinimumSamples = Samples // 4
			FilterGlossy = MAX_FILTER_GLOSSY // 2
			MaxSteps = MAX_STEPS # TODO: Add better volumetric optimizations

		else:
			MinimumSamples = Samples // 8
			FilterGlossy = MAX_FILTER_GLOSSY
			MaxSteps = MAX_STEPS // 2 # TODO: Add better volumetric optimizations

		# Compute device.
		if cycles_compute_device_type == "NONE":
			if UseScrambling:
				UseScrambling = False # Automatic scrambling distance is useless on CPU
				PreviewScrambling = False
				ScramblingMultiplier = 1
				print("Disabling Automatic Scrambling Distance as it is useless for CPU rendering!")
			if util.bv30() is False:
				try:
					addon_utils.enable("render_auto_tile_size", default_set=True)
					val_1, val_2 = addon_utils.check("render_auto_tile_size")
					if val_1 is not True:
						bpy.context.scene.render.tile_x = 32
						bpy.context.scene.render.tile_y = 32
				except Exception:
					bpy.context.scene.render.tile_x = 32
					bpy.context.scene.render.tile_y = 32

		elif cycles_compute_device_type in ("CUDA", "HIP"):
			if util.bv30() is False:
				try:
					addon_utils.enable("render_auto_tile_size", default_set=True)
					val_1, val_2 = addon_utils.check("render_auto_tile_size")
					if val_1 is not True:
						bpy.context.scene.render.tile_x = 256
						bpy.context.scene.render.tile_y = 256
				except Exception:
					bpy.context.scene.render.tile_x = 256
					bpy.context.scene.render.tile_y = 256
	
		elif cycles_compute_device_type == "OPTIX":
			if util.bv30() is False:
				try:
					addon_utils.enable("render_auto_tile_size", default_set=True)
					val_1, val_2 = addon_utils.check("render_auto_tile_size")
					if val_1 is not True:
						bpy.context.scene.render.tile_x = 512
						bpy.context.scene.render.tile_y = 512
				except Exception:
					bpy.context.scene.render.tile_x = 512
					bpy.context.scene.render.tile_y = 512

		elif cycles_compute_device_type == "OPENCL": # Always in any version of Blender pre-3.0
			try:
				addon_utils.enable("render_auto_tile_size", default_set=True)
				val_1, val_2 = addon_utils.check("render_auto_tile_size")
				if val_1 is not True:
					bpy.context.scene.render.tile_x = 256
					bpy.context.scene.render.tile_y = 256
			except Exception:
				bpy.context.scene.render.tile_x = 256
				bpy.context.scene.render.tile_y = 256

		# Cycles Render Settings Optimizations.
		for mat in bpy.data.materials:
			matGen = util.nameGeneralize(mat.name)
			canon, form = generate.get_mc_canonical_name(matGen)
			mat_type = None
			if generate.checklist(canon, "reflective"):
				Glossy += 1
				mat_type = "reflective"
			if generate.checklist(canon, "glass"):
				Transmissive += 1
				mat_type = "glass"

			if mat.use_nodes:
				nodes = mat.node_tree.nodes
				for node in nodes:
					if node.bl_idname == "ShaderNodeVolumeScatter" or \
						node.bl_idname == "ShaderNodeVolumeAbsorption" or \
						node.bl_idname == "ShaderNodeVolumePrincipled":
						density_socket = node.inputs["Density"] # Grab the density
						if not density_socket.is_linked:
							SteppingRate = SteppingRate + 2
						else:
							SteppingRate = SteppingRate - 2 if SteppingRate > 1 else SteppingRate # We do not want to set the stepping rate below one

						ScramblingMultiplier += 0.5
						if ScramblingMultiplier >= CMP_SCRAMBLING_MULTIPLIER: # at this point, it's worthless to keep it enabled 
							UseScrambling = False
							PreviewScrambling = False
							ScramblingMultiplier = 1.0
					# Not the best check, but better then nothing
					elif node.bl_idname == "ShaderNodeBsdfPrincipled":
						if mat_type == "reflective":
							roughness_socket = node.inputs["Roughness"]
							if not roughness_socket.is_linked and roughness_socket.default_value >= 0.2:
								Glossy = Glossy - 1 if Glossy > 1 else Glossy
						elif mat_type == "glass":
							transmission_socket = node.inputs["Transmission"]
							if not transmission_socket.is_linked and transmission_socket.default_value >= 0:
								Transmissive = Transmissive - 1 if Transmissive > 1 else Transmissive
						

		"""
		The reason we divide by 2 only if the bounces are greater then or equal to CMP_BOUNCES (MIN_BOUNCES * 2) is to 
		prevent the division operation from setting the bounces below MIN_BOUNCES.

		For instance, if the Glossy bounces are 3, and we divide by 2 anyway, the Glossy bounces would be set to 1 (we're using // for integer division), which 
		may cause issues when dealing with multiple glossy objects.

		However, this is not an issue in this case since 3 is less then CMP_BOUNCES (by default anyway)
		"""
		if Glossy >= CMP_BOUNCES:
			Glossy = Glossy // 2
		if Transmissive >= CMP_BOUNCES:
			Transmissive = Transmissive // 2

		local_max_bounce = MAX_BOUNCES
		if Glossy > MAX_BOUNCES:
			local_max_bounce = Glossy

		if Transmissive > local_max_bounce:
			local_max_bounce = Transmissive

		# Sampling settings
		# Adaptive sampling is something from Blender 2.9+
		if util.min_bv((2, 90)):
			bpy.context.scene.cycles.adaptive_threshold = NoiseThreshold
			bpy.context.scene.cycles.adaptive_min_samples = MinimumSamples
		# Scrambling distance is a 3.0 feature
		if util.bv30():
			bpy.context.scene.cycles.auto_scrambling_distance = UseScrambling
			bpy.context.scene.cycles.preview_scrambling_distance = PreviewScrambling
			bpy.context.scene.cycles.scrambling_distance = ScramblingMultiplier
		bpy.context.scene.cycles.samples = Samples

		# Volumetric settings 
		bpy.context.scene.cycles.volume_max_steps = MaxSteps
		bpy.context.scene.cycles.volume_step_rate = SteppingRate
		bpy.context.scene.cycles.volume_preview_step_rate = SteppingRate

		# Bounce settings
		bpy.context.scene.cycles.max_bounces = local_max_bounce
		bpy.context.scene.cycles.diffuse_bounces = Diffuse
		bpy.context.scene.cycles.volume_bounces = Volume
		bpy.context.scene.cycles.glossy_bounces = Glossy
		bpy.context.scene.cycles.transmission_bounces = Transmissive

		# Settings related to glossy and transmissive materials
		bpy.context.scene.cycles.blur_glossy = FilterGlossy
		bpy.context.scene.cycles.caustics_reflective = ReflectiveCaustics
		bpy.context.scene.cycles.caustics_refractive = RefractiveCaustics
		bpy.context.scene.cycles.sample_clamp_indirect = ClampingIndirect

		# Sometimes people don't want to use simplify because it messes with rigs
		if scn_props.simplify:
			bpy.context.scene.render.use_simplify = True
			bpy.context.scene.render.simplify_subdivision = 0
		bpy.context.scene.render.use_motion_blur = MotionBlur
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
