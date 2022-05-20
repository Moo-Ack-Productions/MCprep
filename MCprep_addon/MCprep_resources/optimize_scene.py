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
from .. import util

class MCprepOptimizerProperties(bpy.types.PropertyGroup):

	def scene_brightness(self, context):
		itms = [
        ("bright", "scene is bright", ""), 
        ("dark", "scene is dark", "")
        ]
		return itms

    # --------------------------------- Caustics --------------------------------- #
	caustics_bool = bpy.props.BoolProperty(
		name="Caustics (Increases render times)",
        default=False
	)
    
    # -------------------------------- Motion Blur ------------------------------- #
	motionblur_bool = bpy.props.BoolProperty(
		name="Motion Blur (increases render times)",
        default=False
	)

    # ---------------------------------- Fast GI --------------------------------- #
	fastGI_bool = bpy.props.BoolProperty(
		name="Fast GI (Decreases render times)",
        default=False
	)
    
    # -------------------------- Materials in the scene -------------------------- #
	glossy_bool = bpy.props.BoolProperty(
		name="Glossy Materials",
        default=False
	)
    
	transmissive_bool = bpy.props.BoolProperty(
		name="Glass Materials",
        default=False
	)

	volumetric_bool = bpy.props.BoolProperty(
		name="Volumetrics" if util.bv30() else "Volumetrics (Increases render times)",
        default=False
	)
    
    # ------------------------- Time of day in the scene ------------------------- #
	scene_brightness : bpy.props.EnumProperty(
		name="",
		description="Time of day in the scene",
		items=scene_brightness
	)

def panel_draw(self, context):
    row = self.layout.row()
    col = row.column()
    engine = context.scene.render.engine
    scn_props = context.scene.optimizer_props
    if util.bv30:
        if engine == 'CYCLES':
            col.label(text="Materials in Scene")
            
            # ---------------------------------- Glossy ---------------------------------- #
            if scn_props.glossy_bool:
                col.prop(scn_props, "glossy_bool", icon="INDIRECT_ONLY_ON")
            else:
                col.prop(scn_props, "glossy_bool", icon="INDIRECT_ONLY_OFF")
            
            # ------------------------------- Transmissive ------------------------------- #
            if scn_props.transmissive_bool:
                col.prop(scn_props, "transmissive_bool", icon="FULLSCREEN_EXIT")
            else:
                col.prop(scn_props, "transmissive_bool", icon="FULLSCREEN_ENTER")
                
            # -------------------------------- Volumetric -------------------------------- #
            if scn_props.volumetric_bool:
                col.prop(scn_props, "volumetric_bool", icon="OUTLINER_OB_VOLUME")
            else:
                col.prop(scn_props, "volumetric_bool", icon="OUTLINER_DATA_VOLUME")
                
            # ---------------------------------- Options --------------------------------- #
            col.label(text="Options")
            col.label(text="Time of Day")
            col.prop(scn_props, "scene_brightness")
            col.prop(scn_props, "caustics_bool", icon="TRIA_UP")
            col.prop(scn_props, "motionblur_bool", icon="TRIA_UP")
            col.prop(scn_props, "fastGI_bool", icon="TRIA_DOWN")
            col.operator("mcprep.optimize_scene", text="Optimize Scene")
        else:
            col.label(text= "Cycles Only >:C")
    else:
        col.label(text= "Old Cycles Support Still a WIP")


class MCPrep_OT_optimize_scene(bpy.types.Operator):
    bl_idname = "mcprep.optimize_scene"
    bl_label = "Optimize Scene"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        CyclesComputeDeviceType = bpy.context.preferences.addons["cycles"].preferences.compute_device_type, bpy.context.scene.cycles.device
        scn_props = context.scene.optimizer_props
        """
        Sampling Settings
        """
        Samples = 128
        NoiseThreshold = 0.2
        MinimumSamples = 64
        
        """
        Light Bounces
        """
        Diffuse = 2 # This is default because diffuse bounces don't need to be high 
        Glossy = 1
        Transmissive = 1
        Volume = 0  
        FastGI = False;
        
        """
        Volumetric Settings
        """
        MaxSteps = 100 
        
        """
        Filter Glossy and clamping settings
        """
        FilterGlossy = 1
        ClampingIndirect = 1
        
        """
        Motion blur, caustics, etc
        """
        MotionBlur = False
        ReflectiveCaustics = False 
        RefractiveCaustics = False 
        
        """
        Optimizer Settings
        """
        Quality = True 
        
        
        # -------------------------- Render engine settings -------------------------- #
        if scn_props.caustics_bool:
            ReflectiveCaustics = True 
            RefractiveCaustics = True 
        
        if scn_props.motionblur_bool:
            MotionBlur = True
            
        if scn_props.fastGI_bool:
            FastGI = True
        # ------------------------------ Scene materials ----------------------------- #
        if scn_props.glossy_bool:
            Glossy = 3
            
        if scn_props.volumetric_bool:
            Volume = 2
            
        if scn_props.transmissive_bool:
            Transmissive = 3
            
        # -------------------------------- Time of day ------------------------------- #
        if scn_props.scene_brightness == "bright":
            NoiseThreshold = 0.2
        else:
            NoiseThreshold = 0.02
        
        # ------------------------------ Compute device ------------------------------ #
        if CyclesComputeDeviceType == "NONE":
            Samples = 128 
            if Quality:
                NoiseThreshold = 0.05
                MinimumSamples = 25 
                FilterGlossy = 0.5
                MaxSteps = 200
                
            else:
                NoiseThreshold = 0.09
                MinimumSamples = 10
                FilterGlossy = 1
                MaxSteps = 50
                
            if util.get_cycles_version() == 2:
                bpy.context.scene.render.tile_x = 32
                bpy.context.scene.render.tile_y = 32
        
        elif CyclesComputeDeviceType == "CUDA" or CyclesComputeDeviceType == "HIP":
            if CurrentRenderDevice == "CPU":
                if util.get_preferences("cycles").preferences.has_active_device():
                    print("Detected GPU: Switching to GPU...")
                    CurrentRenderDevice = "GPU"
                    
            Samples = 128 
            if Quality:
                NoiseThreshold = 0.02
                MinimumSamples = 32 
                FilterGlossy = 0.5
                MaxSteps = 200
                
            else:
                NoiseThreshold = 0.06
                MinimumSamples = 15
                FilterGlossy = 1
                MaxSteps = 70
            
            if util.get_cycles_version() == 2:
                bpy.context.scene.render.tile_x = 256
                bpy.context.scene.render.tile_y = 256

        elif CyclesComputeDeviceType == "OPTIX":
            if CurrentRenderDevice == "CPU":
                if util.get_preferences("cycles").preferences.has_active_device():
                    print("Detected GPU: Switching to GPU...") 
                    CurrentRenderDevice = "GPU"
                    
            Samples = 128 
            if Quality:
                NoiseThreshold = 0.02
                MinimumSamples = 64 
                FilterGlossy = 0.2
                MaxSteps = 250
                
            else:
                NoiseThreshold = 0.04
                MinimumSamples = 20
                FilterGlossy = 0.8
                MaxSteps = 80
            
            if util.get_cycles_version() == 2:
                bpy.context.scene.render.tile_x = 256
                bpy.context.scene.render.tile_y = 256
        
        if util.get_cycles_version() == 2:
            if CyclesComputeDeviceType == "OPENCL":
                if CurrentRenderDevice == "CPU":
                    if util.get_preferences("cycles").preferences.has_active_device():
                        print("Detected GPU: Switching to GPU...")
                        CurrentRenderDevice = "GPU"
                        
                Samples = 128 
                if Quality:
                    NoiseThreshold = 0.2
                    MinimumSamples = 32 
                    FilterGlossy = 0.9
                    MaxSteps = 100
                    
                else:
                    NoiseThreshold = 0.06
                    MinimumSamples = 15
                    FilterGlossy = 1
                    MaxSteps = 70
                
                bpy.context.scene.render.tile_x = 256
                bpy.context.scene.render.tile_y = 256
        """
        Cycles Render Settings Optimizations
        """
        
        """
        Unique changes
        """
        bpy.context.scene.cycles.samples = Samples
        bpy.context.scene.cycles.adaptive_threshold = NoiseThreshold
        bpy.context.scene.cycles.adaptive_min_samples = MinimumSamples
        bpy.context.scene.cycles.blur_glossy = FilterGlossy
        bpy.context.scene.cycles.volume_max_steps = MaxSteps
        bpy.context.scene.cycles.glossy_bounces = Glossy
        bpy.context.scene.cycles.transmission_bounces = Transmissive
        bpy.context.scene.cycles.caustics_reflective = ReflectiveCaustics
        bpy.context.scene.cycles.caustics_refractive = RefractiveCaustics
        bpy.context.scene.cycles.sample_clamp_indirect = ClampingIndirect
        bpy.context.scene.render.use_motion_blur = MotionBlur
        bpy.context.scene.cycles.volume_bounces = Volume
        bpy.context.scene.cycles.diffuse_bounces = Diffuse
        bpy.context.scene.cycles.use_fast_gi = FastGI


        """Other changes"""
        bpy.context.scene.cycles.max_bounces = 8 
        bpy.context.scene.cycles.preview_samples = 32
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
        
    bpy.types.Scene.optimizer_props = bpy.props.PointerProperty(type=MCprepOptimizerProperties)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.optimizer_props