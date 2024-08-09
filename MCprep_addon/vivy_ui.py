import json
import bpy
from .materials import vivy_materials
from .conf import env

class VivyNodeToolProps(bpy.types.PropertyGroup):
    # Query materials in JSON
    #
    # TODO: Cache the JSON at some
    # point to reduce IO
    def query_materials(self, context):
        itms = []
        active_material = context.active_object.active_material.name
        if env.vivy_material_json is not None:
            if "materials" in env.vivy_material_json:
                mats = env.vivy_material_json["materials"]
                itms = [(mat, mat, "") for mat in mats if mats[mat]["base_material"] != active_material]
        return itms

    # Material name, description, and type
    material_name: bpy.props.StringProperty(name="Material Name", 
                                            maxlen=50,
                                            default="")
    desc: bpy.props.StringProperty(name="Description", 
                                        maxlen=75,
                                        default="")
    as_what: bpy.props.EnumProperty(name="As What?",
                                           items=[
                                            ("regular", "As Material", ""),
                                            ("refine", "As Refinement", "")])

    # Names for pass nodes
    diffuse_name: bpy.props.StringProperty(name="Diffuse Node Name", 
                                            maxlen=25,
                                            default="Diffuse")
    specular_name: bpy.props.StringProperty(name="Specular Node Name", 
                                            maxlen=25,
                                            default="Specular")
    normal_name: bpy.props.StringProperty(name="Normal Node Name", 
                                            maxlen=25,
                                            default="Normal")

    # Selected pass for the UI
    selected_pass: bpy.props.EnumProperty(name="Set Node as Pass",
                                          items=[
                                          ("normal", "Normal", "Normal maps"),
                                          ("specular", "Specular", "Specular maps")])

    # refinements
    refinement_type: bpy.props.EnumProperty(name="Refinement Type",
                                           items=[("emissive", "Emissive",     "Emissive Material"),
                                                ("reflective", "Glossy",       "Glossy Material"),
                                                ("metallic",   "Metal",        "Metallic Material"),
                                                ("glass",      "Transmissive", "Glass Material"),
                                                ("fallback_s", "Fallback (Missing Specular Map)", "Fallback material if the specular pass is missing"),
                                                ("fallback_n", "Fallback (Missing Normal Map)", "Fallback material if the normal pass is missing"),
                                                ("fallback",   "Complete Fallback", "Fallback material if no PBR textures exist")
                                            ])
    refinement_of: bpy.props.EnumProperty(name="Refinement of",
                                         items=query_materials)

class VIVY_OT_register_material(bpy.types.Operator):
    bl_idname = "vivy_node_tools.register_material"
    bl_label = "Register Material"

    def execute(self, context):
        vprop = context.scene.vivy_node_tools
        
        # Check if string has a name
        if context.active_object.active_material.name.strip() == "":
            self.report({'ERROR'}, "Name is required")
            return {'CANCELLED'}

        # We do seperate open calls because
        # Python is absolutely annoying with doing
        # it all in one block. In theory, a race 
        # condition exists in this code as the file
        # referred to in `json_path` may have changed
        # between calls, but let's hope it doesn't 
        # manifest itself
        #
        # TODO: Figure out how to do this all in one block
        json_path = vivy_materials.get_vivy_json()
        env.reload_vivy_json() # To make sure we get the latest data
        data = env.vivy_material_json
        
        if data is None:
            self.report({'ERROR'}, "No data, report a bug on Vivy's GitHub repo!")
            return {'CANCELLED'}

        if "materials" in data and vprop.material_name in data["materials"]:
            self.report({'ERROR'}, "Name already registered!")
            return {'CANCELLED'}
        
        active_material = context.active_object.active_material.name

        # Blender does allow pinning of a material's nodetree,
        # which in theory would make this None
        if active_material is None:
            self.report({'ERROR'}, "No active material selected! Maybe there's no active object?")
            return {'CANCELLED'}

        anode = context.active_node
        if anode is None:
            self.report({'ERROR'}, "No node selected!")
            return {'CANCELLED'}
        elif anode.type != "TEX_IMAGE":
            self.report({'ERROR'}, "Selected node is not an Image texture node!")
            return {'CANCELLED'}
        anode.name = vprop.diffuse_name
        
        # Set the material data
        if "materials" not in data:
            data["materials"] = {}
        mats = data["materials"]
        mats[vprop.material_name] = {
            "base_material" : active_material,
            "desc" : vprop.desc,
            "passes" : {
                "diffuse" : vprop.diffuse_name
            }
        }
        
        # Set the mapping to use for the UI
        if "mapping" not in data:
            data["mapping"] = {}
        mapping = data["mapping"]
        
        if active_material not in mapping:
            mapping[active_material] = [{
                                    "material" : vprop.material_name
                                }]
        else:
            # Check if it's actually a list. If it is, append
            # to the list. Otherwise, return an error and exit 
            # gracefully
            if isinstance(mapping[active_material], list):
                mapping[active_material].append({
                                                "material" : vprop.material_name
                                            })
            else:
                self.report({'ERROR'}, "Mapping in Vivy JSON is of the incorrect format!")
                return {'CANCELLED'}

        with open(json_path, 'w') as f:
            json.dump(data, f)
        
        env.reload_vivy_json() # Reload once afterwards too
        return {'FINISHED'}

# If the code looks similar to the 
# code for VIVY_OT_register_material, 
# that's because I copied pasted the 
# operator and adjusted some stuff 
#
# I'm lazy, I know
class VIVY_OT_set_pass(bpy.types.Operator):
    bl_idname = "vivy_node_tools.set_pass"
    bl_label = "Set Pass for Image Node"

    def execute(self, context):
        vprop = context.scene.vivy_node_tools

        # Check if string has a name
        if context.active_object.active_material.name.strip() == "":
            self.report({'ERROR'}, "Name is required")
            return {'CANCELLED'}
        
        # We do seperate open calls because
        # Python is absolutely annoying with doing
        # it all in one block. In theory, a race 
        # condition exists in this code as the file
        # referred to in `json_path` may have changed
        # between calls, but let's hope it doesn't 
        # manifest itself
        #
        # TODO: Figure out how to do this all in one block
        json_path = vivy_materials.get_vivy_json()
        env.reload_vivy_json() # To make sure we get the latest data
        data = env.vivy_material_json
        
        if data is None:
            self.report({'ERROR'}, "No data, report a bug on Vivy's GitHub repo!")
            return {'CANCELLED'}
        
        active_material = context.active_object.active_material.name

        # Blender does allow pinning of a material's nodetree,
        # which in theory would make this None
        if active_material is None:
            self.report({'ERROR'}, "No active material selected! Maybe there's no active object?")
            return {'CANCELLED'}

        # Set the mapping to use for the UI
        if "mapping" not in data:
            self.report({'ERROR'}, "Materials must be registered first!")
            return {'CANCELLED'}
        
        # Set the material data
        if "materials" not in data:
            self.report({'ERROR'}, "Materials must be registered first!")
            return {'CANCELLED'}

        mapping = data["mapping"]
        mats = data["materials"]
        if active_material not in mapping:
            self.report({'ERROR'}, "Active material not used in Vivy library!")
            return {'CANCELLED'}
        else:
            amats = mapping[active_material]
            if isinstance(amats, list):
                anode = context.active_node
                if anode is None:
                    self.report({'ERROR'}, "No node selected!")
                    return {'CANCELLED'}
                elif anode.type != "TEX_IMAGE":
                    self.report({'ERROR'}, "Selected node is not an Image texture node!")
                    return {'CANCELLED'}
                anode.name = vprop.specular_name if vprop.selected_pass == "specular" else vprop.normal_name
                for m in amats:
                    if "refinement" in m:
                        continue
                    mats[m["material"]]["passes"][vprop.selected_pass] = vprop.specular_name if vprop.selected_pass == "specular" else vprop.normal_name
            else:
                self.report({'ERROR'}, "Mapping in Vivy JSON is of the incorrect format!")
                return {'CANCELLED'}
        
        with open(json_path, 'w') as f:
            json.dump(data, f)
        
        env.reload_vivy_json() # Reload once afterwards too
        return {'FINISHED'}

class VIVY_OT_set_refinement(bpy.types.Operator):
    bl_idname = "vivy_node_tools.set_refinement"
    bl_label = "Set Material as Refinement"

    def execute(self, context):
        vprop = context.scene.vivy_node_tools
        
        # We do seperate open calls because
        # Python is absolutely annoying with doing
        # it all in one block. In theory, a race 
        # condition exists in this code as the file
        # referred to in `json_path` may have changed
        # between calls, but let's hope it doesn't 
        # manifest itself
        #
        # TODO: Figure out how to do this all in one block
        json_path = vivy_materials.get_vivy_json()
        env.reload_vivy_json() # To make sure we get the latest data
        data = env.vivy_material_json
        
        if data is None:
            self.report({'ERROR'}, "No data, report a bug on Vivy's GitHub repo!")
            return {'CANCELLED'}
        
        active_material = context.active_object.active_material.name

        # Blender does allow pinning of a material's nodetree,
        # which in theory would make this None
        if active_material is None:
            self.report({'ERROR'}, "No active material selected! Maybe there's no active object?")
            return {'CANCELLED'}

        # Set the mapping to use for the UI
        if "mapping" not in data:
            self.report({'ERROR'}, "Materials must be registered first!")
            return {'CANCELLED'}
        
        # Set the material data
        if "materials" not in data:
            self.report({'ERROR'}, "Materials must be registered first!")
            return {'CANCELLED'}

        mapping = data["mapping"]
        mats = data["materials"]

        if vprop.refinement_of not in mats:
            self.report({'ERROR'}, "Attempted to add a refinement to material that isn't registered!")
            return {'CANCELLED'}

        if active_material not in mapping:
            mapping[active_material] = []
        
        if "refinements" not in mats[vprop.refinement_of]:
            mats[vprop.refinement_of]["refinements"] = {}
        mats[vprop.refinement_of]["refinements"][vprop.refinement_type] = active_material
        mapping[active_material].append({
                                        "material" : vprop.refinement_of,
                                        "refinement" : vprop.refinement_type
                                })

        with open(json_path, 'w') as f:
            json.dump(data, f)
        
        return {'FINISHED'}

class VIVY_PT_node_tools(bpy.types.Panel):
    bl_label = "Vivy Tools"
    bl_idname = "VIVY_PT_node_tools"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Vivy"
    bl_context = "scene" 
    
    @classmethod
    def poll(cls, context):
        return context.area.ui_type == "ShaderNodeTree" and str(vivy_materials.get_vivy_blend().absolute()) == bpy.data.filepath
    
    # Refinements section
    def draw_refinements(self, context, row):
        layout = self.layout
        vprop = context.scene.vivy_node_tools
        row.label(text="Refinement type:")
        row = layout.row()
        row.prop(vprop, "refinement_type", text="")
        row = layout.row()
        row.label(text="Refinement of:")
        row = layout.row()
        row.prop(vprop, "refinement_of", text="")
        row = layout.row()
        row.operator("vivy_node_tools.set_refinement")

    def draw(self, context): 
        layout = self.layout
        row = layout.row()
        anode = context.active_node
        vprop = context.scene.vivy_node_tools
        active_material = context.active_object.active_material.name \
            if context.active_object.active_material.name is not None else None

        # We are assuming the data is up to date 
        # based on how the addon works and is supposed
        # to be used
        data = env.vivy_material_json
        if data is None:
            row = layout.row()
            row.label(text="No data, report a bug on Vivy's GitHub repo!")
            return

        # If no mappings exist or the material is 
        # not registered, then give the registration
        # menu
        if "mapping" not in data or active_material not in data["mapping"]:
            if anode is not None and anode.type == "TEX_IMAGE":
                row.label(text="Material Name:")
                row = layout.row()
                row.prop(vprop, "material_name", text="")
                row = layout.row()
                row.label(text="Material Description:")
                row = layout.row()
                row.prop(vprop, "desc", text="")
                row = layout.row()
                row.label(text="Name of Diffuse Node:")
                row = layout.row()
                row.prop(vprop, "diffuse_name", text="")
                row = layout.row()
                row.label(text="Set Type:")
                row = layout.row()
                row.prop(vprop, "as_what", text="")
                row = layout.row()

                # Grey out button if no name is inputed 
                # or if it's all spaces
                row.enabled = vprop.material_name.strip() != ""

                if vprop.as_what == "refine":
                    self.draw_refinements(context, row)
                elif vprop.as_what == "regular":
                    row.operator("vivy_node_tools.register_material")
            else:
                row.label(text="Select the image node that'll hold the diffuse pass")

        # If the material is known, then give access
        # to more advanced features, like refinements 
        # and whatnot
        elif "mapping" in data and active_material in data["mapping"]:
            # This will give some information 
            # on the material being worked on
            # at the moment
            lib_mats = data["mapping"][active_material]
            if isinstance(lib_mats, list):
                for mat in lib_mats:
                    box = layout.box()
                    box.label(text=mat["material"])
                    brow = box.row()
                    if "refinement" in mat:
                        brow.label(text=f"Refinement of: {mat['material']}")
                        brow = box.row()
                        refinement = mat["refinement"]
                        if refinement == "emissive":
                            brow.label(text="Emission", icon="OUTLINER_OB_LIGHT")
                        if refinement == "reflective":
                            brow.label(text="Glossy", icon="NODE_MATERIAL")
                        if refinement == "metallic":
                            brow.label(text="Metalic", icon="NODE_MATERIAL")
                        if refinement == "glass":
                            brow.label(text="Transmissive", icon="OUTLINER_OB_LIGHTPROBE")
                        if refinement == "fallback_s":
                            brow.label(text="Fallback for Missing Specular")
                        if refinement == "fallback_n":
                            brow.label(text="Fallback for Missing Normal")
                        if refinement == "fallback":
                            brow.label(text="Complete Fallback for No Extra Passes")
                    else:
                        md = data["materials"][mat["material"]]
                        brow.label(text="Supports Passes For:")
                        brow = box.row()
                        brow.label(text="Diffuse", icon="MATERIAL")
                        if "specular" in md["passes"]:
                            brow = box.row()
                            brow.label(text="Specular", icon="NODE_MATERIAL")
                        if "normal" in md["passes"]:
                            brow = box.row()
                            brow.label(text="Normal", icon="ORIENTATION_NORMAL")
            
            row = layout.row()
            if anode is not None and anode.type == "TEX_IMAGE":
                row.label(text="Set Pass For:")
                row = layout.row()
                row.prop(vprop, "selected_pass", text="")
                row = layout.row()

                # To make the UI easier to understand,
                # we change the property shown based
                # on the selected pass
                if vprop.selected_pass == "specular":
                    row.label(text="Name of Specular Node:")
                    row = layout.row()
                    row.prop(vprop, "specular_name", text="")
                elif vprop.selected_pass == "normal":
                    row.label(text="Name of Normal Node:")
                    row = layout.row()
                    row.prop(vprop, "normal_name", text="")
                row = layout.row()
                row.operator("vivy_node_tools.set_pass")
                row = layout.row()

class VIVY_PT_node_tools_refinement(bpy.types.Panel):
    bl_label = "Refinements"
    bl_idname = "VIVY_PT_node_tools_refinement"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Vivy"
    bl_context = "scene" 
    bl_parent_id = "VIVY_PT_node_tools"
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):
        if not (context.area.ui_type == "ShaderNodeTree" and str(vivy_materials.get_vivy_blend().absolute()) == bpy.data.filepath):
            return False

        active_material = context.active_object.active_material.name \
            if context.active_object.active_material.name is not None else None
        data = env.vivy_material_json
        if "mapping" in data:
            if active_material in data["mapping"]:
                for m in data["mapping"][active_material]:
                    if "refinement" in m:
                        return False
            else:
                return False
        return True

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        layout = self.layout
        vprop = context.scene.vivy_node_tools
        row.label(text="Refinement type:")
        row = layout.row()
        row.prop(vprop, "refinement_type", text="")
        row = layout.row()
        row.label(text="Refinement of:")
        row = layout.row()
        row.prop(vprop, "refinement_of", text="")
        row = layout.row()
        row.operator("vivy_node_tools.set_refinement")

classes = [
    VivyNodeToolProps,
    VIVY_PT_node_tools,
    VIVY_PT_node_tools_refinement,
    VIVY_OT_register_material,
    VIVY_OT_set_pass,
    VIVY_OT_set_refinement
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        bpy.types.Scene.vivy_node_tools = bpy.props.PointerProperty(type=VivyNodeToolProps)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.vivy_node_tools
