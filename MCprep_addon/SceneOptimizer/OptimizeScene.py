import bpy
from .. import util

class MCprepRendorProperties():
	def SceneMaterials(self, context):
		itms = [
        ("simple", "Basic materials"), 
        ("glossy", "Lots of glossy materials"), 
        ("transmissive", "Lots of transmissve materials")]
		return itms

	def TimeInScene(self, context):
		itms = [
        ("Day", "Day time"), 
        ("Night", "Night time")]
		return itms

    # --------------------------------- Caustics --------------------------------- #
	CausticsBool = bpy.props.BoolProperty(
		name="Caustics",
        default=False
	)
    
    # -------------------------------- Volumetrics ------------------------------- #
	VolumetricBool = bpy.props.BoolProperty(
		name="Volumetrics",
        default=False
	)
    
    # -------------------------------- Motion Blur ------------------------------- #
	MotionBlurBool = bpy.props.BoolProperty(
		name="Motion Blur (kills render times)",
        default=False
	)
    
    # -------------------------- Materials in the scene -------------------------- #
	SceneMaterials = bpy.props.EnumProperty(
		name="Scene Materials",
		description="What types of materials are in the scene",
		items=SceneMaterials
	)
    
    # ------------------------- Time of day in the scene ------------------------- #
	TimeInScene = bpy.props.EnumProperty(
		name="Time in Scene",
		description="Time of day in the scene",
		items=TimeInScene
	)

def draw_render_common(self, context):
    row = self.layout.row()
    col = row.column()
    engine = context.scene.render.engine
    if engine == 'CYCLES':
        col.prop(self, "SceneMaterials")
        col.prop(self, "TimeInScene")
        col.prop(self, "CausticsBool")
        col.prop(self, "VolumetricBool")
        col.prop(self, "MotionBlurBool")
        
    else:
        col.label(text= "Cycles Only >:C")

class MCPrep_OT_optimize_scene(bpy.types.Operator, MCprepRendorProperties):
    bl_idname = "mcprep.optimize_scene"
    bl_label = "Optimize Scene"
    bl_options = {'REGISTER', 'UNDO'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
        
    def draw(self, context):
        draw_render_common(self, context)
    def execute(self, context):
        CyclesComputeDeviceType = bpy.context.preferences.addons["cycles"].preferences.compute_device_type, bpy.context.scene.cycles.device
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
        Glossy = 0  
        Transmissive = 0 
        Volume = 0  
        
        """
        Volumetric Settings
        """
        MaxSteps = 0 
        
        """
        Filter Glossy and clamping settings
        """
        FilterGlossy = 0 
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
        
        
        # --------------------------------- Caustics --------------------------------- #
        if self.CausticsBool:
            ReflectiveCaustics = True 
            RefractiveCaustics = True 
        
        if self.MotionBlurBool:
            MotionBlur = True
            
        if self.VolumetricBool:
            Volume = 2
        
        # ------------------------------ Scene materials ----------------------------- #
        if self.SceneMaterials == "glossy":
            Glossy = 5
            
        elif self.SceneMaterials == "transmissive":
            Transmissive = 5
            
        elif self.SceneMaterials == "simple":
            Glossy = 2
            Transmissive = 2
        
        
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
        
        elif CyclesComputeDeviceType == "CUDA" or CyclesComputeDeviceType == "HIP":
            if CurrentRenderDevice == "CPU":
                if bpy.context.preferences.addons["cycles"].preferences.has_active_device():
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

        elif CyclesComputeDeviceType == "OPTIX":
            if CurrentRenderDevice == "CPU":
                if bpy.context.preferences.addons["cycles"].preferences.has_active_device():
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


        """Other changes"""
        bpy.context.scene.cycles.max_bounces = 8 
        bpy.context.scene.cycles.preview_samples = 32
        bpy.context.scene.render.use_simplify = True
        bpy.context.scene.render.simplify_subdivision = 0
        
        return {'FINISHED'}

classes = [
    MCPrep_OT_optimize_scene
]
def register():
	util.make_annotations(MCprepRendorProperties)
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)