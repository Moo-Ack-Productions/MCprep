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

# Note from Mahid Sheikh, December 24th, 2023
# 
# The MCprep optimizer is to be deprecated in MCprep 3.5.2, and 
# removed in MCprep 3.6. This is for the following reasons:
# - Extremely buggy algorithm
#	- There's been times where MCprep has set the max bounces 
#     to 80 or higher, because of the way the algorithm assumes
#	  the scene's properties.
#
#	- The algorithm was made to work around the hardware I assumed
#	  a regular user would have (based on what I've seen on Minecraft
#	  animation servers), which means no actual scene profiling, just
#	  assumptions of how the scene could turn out based on materials.
#
# - Not caught up with modern Cycles improvements
#	- This was written when Cycles X was still in development. Today, 
#	  Cycles has massively improved, and Cycles X is the default, but
#	  the optimizer hasn't changed at all.
#
# - Better tools exist for automatic optimization, though nothing 
#	beats manual optimization

import bpy
from bpy.types import Context, UILayout, Node
import addon_utils

from . import util
from .materials import generate


MAX_BOUNCES = 8 # 8 is generally the standard for light bounces
MIN_BOUNCES = 2 # 2 is the lowest as it avoids issues regarding glossy
CMP_BOUNCES = MIN_BOUNCES * 2 # To avoid bounces from going bellow 2
MAX_FILTER_glossy = 1.0 # Standard in Blender
MAX_STEPS = 200 # 200 is fine for most scenes
MIN_SCRAMBLING_MULTIPLIER = 0.35 # 0.35 seems to help performance a lot, but we'll do edits to this value depending on materials
SCRAMBLING_MULTIPLIER_ADD = 0.05 # This is how much we'll add to the srambling distance multiplier 
CMP_SCRAMBLING_MULTIPLIER = MIN_SCRAMBLING_MULTIPLIER * 3 # The max since beyond this performance doesn't improve as much
VOLUMETRIC_NODES = ["ShaderNodeVolumeScatter", "ShaderNodeVolumeAbsorption", "ShaderNodeVolumePrincipled"]

# MCprep Node Settings
MCPREP_HOMOGENOUS_volume = "MCPREP_HOMOGENOUS_VOLUME"
MCPREP_NOT_HOMOGENOUS_volume = "MCPREP_NOT_HOMOGENOUS_VOLUME"


class MCprepOptimizerProperties(bpy.types.PropertyGroup):
	def scene_brightness(self, context):
		itms = [
			("BRIGHT", "Scene is bright", "Use this setting if your scene is mostly bright\nEx. outside during the day"), 
			("DARK", "Scene is dark", "Use this setting if your scene is mostly dark\nEx. caves, interiors, and outside at night")
		]
		return itms

	caustics_bool: bpy.props.BoolProperty(
		name="Caustics (slower)",
		default=False,
		description="If checked allows cautics to be enabled"
	)
	motion_blur_bool: bpy.props.BoolProperty(
		name="Motion Blur (slower)",
		default=False,
		description="If checked allows motion blur to be enabled"
	)
	scene_brightness: bpy.props.EnumProperty(
		name="",
		description="Brightness of the scene: Affects how the optimizer adjusts sampling",
		items=scene_brightness
	)
	quality_vs_speed: bpy.props.BoolProperty(
		name="Optimize scene for quality: Makes the optimizer adjust settings in a less \"destructive\" way",
		default=True
	)
	simplify: bpy.props.BoolProperty(
		name="Simplify the viewport: Reduces subdivisions to 0. Only disable if any assets will break when using this",
		default=True
	)
	scrambling_unsafe: bpy.props.BoolProperty(
		name="Automatic Scrambling Distance: Can cause artifacts when rendering",
		default=False
	)
	preview_scrambling: bpy.props.BoolProperty(
		name="Preview Scrambling in the viewport",
		default=True
	)


def panel_draw(context: Context, element: UILayout):
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
		col.prop(scn_props, "motion_blur_bool", icon="TRIA_UP")
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
		subrow.operator("mcprep.optimize_scene", text="Optimize Scene (Deprecated)")
	else:
		col.label(text="Cycles Only :C")


class MCPrep_OT_optimize_scene(bpy.types.Operator):
	bl_idname = "mcprep.optimize_scene"
	bl_label = "Optimize Scene"
	bl_options = {'REGISTER', 'UNDO'}

	def __init__(self) -> None:
		# Sampling Settings.
		self.samples = bpy.context.scene.cycles.samples # We will be doing some minor adjustments to the sample count
		self.minimum_samples = None
		self.noise_threshold = 0.2

		# Light Bounces.
		self.diffuse = 2  # This is default because diffuse bounces don't need to be high
		self.glossy = 1
		self.transmissive = 1
		self.volume = 2

		# volumetric Settings.
		self.max_steps = 100
		self.stepping_rate = 5
		self.homogenous_volumes = 0
		self.not_homogenous_volumes = 0

		# Filter glossy and clamping settings.
		self.filter_glossy = 1
		self.clamping_indirect = 1

		# Motion blur, caustics, etc.
		self.motion_blur = None
		self.reflective_caustics = None
		self.refractive_caustics = None

		# Optimizer Settings.
		self.quality = None
		self.uses_scrambling = None
		self.preview_scrambling = None
		self.scrambling_multiplier = MIN_SCRAMBLING_MULTIPLIER
	
	def is_vol(self, context: Context, node: Node) -> None:
		density_socket = node.inputs["Density"] # Grab the density
		node_name = util.nameGeneralize(node.name).rstrip()  # Get the name (who knew this could be used on nodes?)
		# Sometimes there may be something linked to the density but it's fine to treat it as a homogeneous volume
		# This allows the user to control the addon at the node level
		if not density_socket.is_linked:
			if node_name == MCPREP_NOT_HOMOGENOUS_volume:
				self.not_homogenous_volumes -= 1
			else:
				self.homogenous_volumes += 1
		else:
			if node_name == MCPREP_HOMOGENOUS_volume:
				self.homogenous_volumes += 1
			else:
				self.not_homogenous_volumes += 1

		self.scrambling_multiplier += SCRAMBLING_MULTIPLIER_ADD
		if self.scrambling_multiplier >= CMP_SCRAMBLING_MULTIPLIER: # at this point, it's worthless to keep it enabled 
			self.uses_scrambling = False
			self.preview_scrambling = False
			self.scrambling_multiplier = 1.0

		print(self.homogenous_volumes, " ", self.not_homogenous_volumes)

	def is_pricipled(self, context: Context, mat_type: str, node: Node) -> None:
		if mat_type == "reflective":
			roughness_socket = node.inputs["Roughness"]
			if not roughness_socket.is_linked and roughness_socket.default_value >= 0.2:
				self.glossy = self.glossy - 1 if self.glossy > 2 else 2
		elif mat_type == "glass":
			if "Transmission" in node.inputs:  # pre 4.0 way
				transmission_socket = node.inputs["Transmission"]
			else:  # Blender 4.0+
				transmission_socket = node.inputs["Transmission Weight"]
			if not transmission_socket.is_linked and transmission_socket.default_value >= 0:
				self.transmissive = self.transmissive - 2 if self.transmissive > 1 else 2

	def execute(self, context):
		# ! Calling this twice seems to remove all unused materials
		# TODO: find a better way of doing this
		try:
			bpy.ops.outliner.orphans_purge()
			bpy.ops.outliner.orphans_purge()
		except Exception as e:
			print("Failed to purge orphans:")
			print(e)
		prefs = util.get_preferences(context)
		cprefs = prefs.addons.get("cycles")
		scn_props = context.scene.optimizer_props

		# Get the compute device type.
		cycles_compute_device_type = None
		has_active_device = cprefs.preferences.has_active_device()
		if cprefs is not None and has_active_device:
			cycles_compute_device_type = cprefs.preferences.compute_device_type

		# Sampling Settings.
		self.samples = bpy.context.scene.cycles.samples # We will be doing some minor adjustments to the sample count
		self.minimum_samples = None
		self.noise_threshold = 0.2


		# Light Bounces.
		self.diffuse = 2  # This is default because diffuse bounces don't need to be high
		self.glossy = 1
		self.transmissive = 1
		self.volume = 2

		# volumetric Settings.
		self.max_steps = 100
		self.stepping_rate = 5
		self.homogenous_volumes = 0
		self.not_homogenous_volumes = 0

		# Filter glossy and clamping settings.
		self.filter_glossy = 1
		self.clamping_indirect = 1

		# Motion blur, caustics, etc.
		self.motion_blur = scn_props.motion_blur_bool
		self.reflective_caustics = scn_props.caustics_bool
		self.refractive_caustics = scn_props.caustics_bool

		# Optimizer Settings.
		self.quality = scn_props.quality_vs_speed
		self.uses_scrambling = scn_props.scrambling_unsafe
		self.preview_scrambling = scn_props.preview_scrambling
		self.scrambling_multiplier = MIN_SCRAMBLING_MULTIPLIER

		# Time of day.
		if scn_props.scene_brightness == "BRIGHT":
			self.noise_threshold = 0.2
		else:
			self.samples += 20
			self.noise_threshold = 0.05
		
		if self.quality:
			self.minimum_samples = self.samples // 4
			self.filter_glossy = MAX_FILTER_glossy // 2
			self.max_steps = MAX_STEPS # TODO: Add better volumetric optimizations

		else:
			self.minimum_samples = self.samples // 8
			self.filter_glossy = MAX_FILTER_glossy
			self.max_steps = MAX_STEPS // 2 # TODO: Add better volumetric optimizations

		# Compute device.
		if cycles_compute_device_type == "NONE":
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
				self.glossy += 1
				mat_type = "reflective"
			if generate.checklist(canon, "glass"):
				self.transmissive += 1
				mat_type = "glass"

			if mat.use_nodes:
				nodes = mat.node_tree.nodes
				for node in nodes:
					print(node.bl_idname)
					if node.bl_idname in VOLUMETRIC_NODES:
						self.is_vol(context, node)

					# Not the best check, but better then nothing
					if node.bl_idname == "ShaderNodeBsdfPrincipled":
						self.is_pricipled(context, mat_type, node)
				
				if self.homogenous_volumes > 0 or self.not_homogenous_volumes > 0:
					volumes_rate = self.homogenous_volumes - self.not_homogenous_volumes
					if volumes_rate > 0:
						self.stepping_rate += 2 * volumes_rate
						mat.cycles.homogenous_volume = True
					elif volumes_rate < 0:
						self.stepping_rate -= 2 * abs(volumes_rate) # get the absolute value of volumes_rate since it's negative
						if self.stepping_rate < 2:
							self.stepping_rate = 2 # 2 is the lowest stepping rate


		"""
		The reason we divide by 2 only if the bounces are greater then or equal to CMP_BOUNCES (MIN_BOUNCES * 2) is to 
		prevent the division operation from setting the bounces below MIN_BOUNCES.

		For instance, if the glossy bounces are 3, and we divide by 2 anyway, the glossy bounces would be set to 1 (we're using // for integer division), which 
		may cause issues when dealing with multiple glossy objects.

		However, this is not an issue in this case since 3 is less then CMP_BOUNCES (by default anyway)
		"""
		if self.glossy >= CMP_BOUNCES:
			self.glossy = self.glossy // 2
		if self.transmissive >= CMP_BOUNCES:
			self.transmissive = self.transmissive // 2

		local_max_bounce = MAX_BOUNCES
		if self.glossy > local_max_bounce:
			local_max_bounce = self.glossy

		if self.transmissive > local_max_bounce:
			local_max_bounce = self.transmissive

		# Sampling settings
		# Adaptive sampling is something from Blender 2.9+
		if util.min_bv((2, 90)):
			bpy.context.scene.cycles.adaptive_threshold = self.noise_threshold
			bpy.context.scene.cycles.adaptive_min_samples = self.minimum_samples
		# Scrambling distance is a 3.0 feature
		if util.bv30() and self.uses_scrambling:
			bpy.context.scene.cycles.auto_scrambling_distance = self.uses_scrambling
			bpy.context.scene.cycles.preview_scrambling_distance = self.preview_scrambling
			bpy.context.scene.cycles.scrambling_distance = self.scrambling_multiplier

			if self.uses_scrambling is not False:
				bpy.context.scene.cycles.min_light_bounces = 1
				bpy.context.scene.cycles.min_transparent_bounces = 2

		bpy.context.scene.cycles.samples = self.samples

		# volumetric settings 
		bpy.context.scene.cycles.volume_max_steps = self.max_steps
		bpy.context.scene.cycles.volume_step_rate = self.stepping_rate
		bpy.context.scene.cycles.volume_preview_step_rate = self.stepping_rate

		# Bounce settings
		bpy.context.scene.cycles.max_bounces = local_max_bounce
		bpy.context.scene.cycles.diffuse_bounces = self.diffuse
		bpy.context.scene.cycles.volume_bounces = self.volume
		bpy.context.scene.cycles.glossy_bounces = self.glossy
		bpy.context.scene.cycles.transmission_bounces = self.transmissive

		# Settings related to glossy and transmissive materials
		bpy.context.scene.cycles.blur_glossy = self.filter_glossy
		bpy.context.scene.cycles.caustics_reflective = self.reflective_caustics
		bpy.context.scene.cycles.caustics_refractive = self.refractive_caustics
		bpy.context.scene.cycles.sample_clamp_indirect = self.clamping_indirect

		# Sometimes people don't want to use simplify because it messes with rigs
		bpy.context.scene.render.use_simplify = scn_props.simplify
		bpy.context.scene.render.simplify_subdivision = 0
		bpy.context.scene.render.use_motion_blur = self.motion_blur
		return {'FINISHED'}


classes = (
	MCprepOptimizerProperties,
	MCPrep_OT_optimize_scene
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Scene.optimizer_props = bpy.props.PointerProperty(
		type=MCprepOptimizerProperties)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.optimizer_props
