import bpy
import json
from .conf import env
from .util import is_vivy_enabled
from .materials import vivy_materials

# Placeholder for None since bpy doesn't allow
# setting properties to None
#
# If a user-supplied value matches this, I don't
# know what to say
MCPREP_VIVY_NONE = "@MCPREP_VIVY_NONE"

class ListVivyMaterials(bpy.types.PropertyGroup):
    def items_materials(self, context):
        items = [(MCPREP_VIVY_NONE, "", "")]
        for mat in bpy.data.materials:
            items.append((mat.name, mat.name, ""))
        return items

    def get_name(self):
        return self.get("name", "NAME")

    def set_name(self, value):
        env.vivy_name_changes[value] = self.get("name", "NAME")
        self["name"] = value
            
    name: bpy.props.StringProperty(name="Name", description="Name of Vivy material", default="NAME", get=get_name, set=set_name)
    desc: bpy.props.StringProperty(name="Desc", description="Description of Vivy material", default="DESC")
    base_material: bpy.props.EnumProperty(name="Base Mat", items=items_materials, description="Base material of Vivy material")

    # Passes
    diffuse: bpy.props.StringProperty(name="Diffuse Pass", description="Name of node that holds diffuse pass", default="DIFFUSE")
    specular: bpy.props.StringProperty(name="Specular Pass", description="Name of node that holds specular pass", default="SPECULAR")
    normal: bpy.props.StringProperty(name="Normal Pass", description="Name of node that holds normal pass", default="NORMAL")

    emissive: bpy.props.EnumProperty(name="Emit refinement", items=items_materials, description="Material for emmisive materials")
    reflective: bpy.props.EnumProperty(name="Reflective refinement", items=items_materials, description="Material for reflective materials")
    metallic: bpy.props.EnumProperty(name="Metallic refinement", items=items_materials, description="Material for metallic materials")
    glass: bpy.props.EnumProperty(name="Glass refinement", items=items_materials, description="Material for glass materials")
    fallback_s: bpy.props.EnumProperty(name="Fallback specular refinement", items=items_materials, description="Material for missing specular materials")
    fallback_n: bpy.props.EnumProperty(name="Fallback normal refinement", items=items_materials, description="Material for missing normal materials")
    fallback: bpy.props.EnumProperty(name="Fallback refinement", items=items_materials, description="Material for missing specular and normal materials")

class VivyEditorProps(bpy.types.PropertyGroup):
    vivy_materials: bpy.props.CollectionProperty(type=ListVivyMaterials)
    vivy_materials_index: bpy.props.IntProperty(default=0)

def reload_vivy_materials(context):
    vprop = context.scene.vivy_editor_props
    if env.vivy_material_json is not None and "materials" in env.vivy_material_json:
        material_data = env.vivy_material_json["materials"]
        for mat in material_data:
            vmat = vprop.vivy_materials.add()
            vmat.name = mat 
            vmat.desc = material_data[mat]["desc"]
            vmat.base_material = material_data[mat]["base_material"]

            # passes
            passes_data = material_data[mat]["passes"]
            vmat.diffuse = passes_data["diffuse"] if "diffuse" in passes_data else ""
            vmat.specular = passes_data["specular"] if "specular" in passes_data else ""
            vmat.normal = passes_data["normal"] if "normal" in passes_data else ""

            # refinements
            if "refinements" in material_data[mat]:
                refinements_data = material_data[mat]["refinements"]
                vmat.emissive = refinements_data["emissive"] if "emissive" in refinements_data else MCPREP_VIVY_NONE
                vmat.reflective = refinements_data["reflective"] if "reflective" in refinements_data else MCPREP_VIVY_NONE
                vmat.metallic = refinements_data["metallic"] if "metallic" in refinements_data else MCPREP_VIVY_NONE
                vmat.glass = refinements_data["glass"] if "glass" in refinements_data else MCPREP_VIVY_NONE
                vmat.fallback_s = refinements_data["fallback_s"] if "fallback_s" in refinements_data else MCPREP_VIVY_NONE
                vmat.fallback_n = refinements_data["fallback_n"] if "fallback_n" in refinements_data else MCPREP_VIVY_NONE
                vmat.fallback = refinements_data["fallback"] if "fallback" in refinements_data else MCPREP_VIVY_NONE

class MCPREP_UL_vivy_materials(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if env.vivy_material_json is not None:
                layout.label(text=item.name)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)

class MCPREP_OT_vivy_reload_editor(bpy.types.Operator):
    bl_idname = "vivy.reload_editor"
    bl_label = "Reload Vivy Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        env.reload_vivy_json(context.scene.vivy_file_path)
        reload_vivy_materials(context)
        return {'FINISHED'}

class MCPREP_OT_vivy_apply_changes(bpy.types.Operator):
    bl_idname = "vivy.apply_changes"
    bl_label = "Apply Changes to Current Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    # TODO: Find a more elegant way to handle
    # all of this.
    def execute(self, context):
        env.reload_vivy_json(context.scene.vivy_file_path)
        if env.vivy_material_json is not None and "materials" in env.vivy_material_json:
            vprop = context.scene.vivy_editor_props
            mat = vprop.vivy_materials[vprop.vivy_materials_index]
            data = env.vivy_material_json
            
            old_name = None
            if mat.name in env.vivy_name_changes:
                old_name = mat.name

                # Go backwards from the new name to 
                # the old name. Eventually, you will
                # find it
                while old_name not in data["materials"]:
                    old_name = env.vivy_name_changes[old_name]
            
            if old_name:
                original_data = data["materials"].pop(old_name)
                original_data["desc"] = mat.desc
                original_data["base_material"] = mat.base_material
                
                # passes
                orig_passes = original_data["passes"]
                orig_passes["diffuse"] = mat.diffuse if mat.diffuse != "" else MCPREP_VIVY_NONE
                orig_passes["specular"] = mat.specular if mat.specular != "" else MCPREP_VIVY_NONE
                orig_passes["normal"] = mat.normal if mat.normal != "" else MCPREP_VIVY_NONE
                
                # refinements
                orig_refinements = original_data["refinements"]
                orig_refinements["emissive"] = mat.emissive
                orig_refinements["reflective"] = mat.reflective
                orig_refinements["metallic"] = mat.metallic
                orig_refinements["glass"] = mat.glass
                orig_refinements["fallback_s"] = mat.fallback_s
                orig_refinements["fallback_n"] = mat.fallback_n
                orig_refinements["fallback"] = mat.fallback

                data["materials"][mat.name] = original_data
                
                # Update mappings as well for
                # the UI
                for key in data["mapping"]:
                    data_mapping = data["mapping"][key]
                    for map in data_mapping:
                        if map["material"] != old_name:
                            continue
                        map["material"] = mat.name
            else:
                data["materials"][mat.name] = {
                    "desc": mat.desc,
                    "base_material": mat.base_material,
                    "passes" : {
                        "diffuse": mat.diffuse if mat.diffuse != "" else MCPREP_VIVY_NONE,
                        "specular": mat.specular if mat.specular != "" else MCPREP_VIVY_NONE,
                        "normal": mat.normal if mat.normal != "" else MCPREP_VIVY_NONE
                    },
                    "refinements" : {
                        "emissive": mat.emissive,
                        "reflective": mat.reflective,
                        "metallic": mat.metallic,
                        "glass": mat.glass,
                        "fallback_s": mat.fallback_s,
                        "fallback_n": mat.fallback_n,
                        "fallback": mat.fallback
                    }
                }
            
            for key in data["materials"]:
                passes = data["materials"][key]["passes"] if "passes" in data["materials"][key] else {}
                refinements = data["materials"][key]["refinements"] if "refinements" in data["materials"][key] else {}

                c_passes = passes.copy()
                c_refinements = refinements.copy()
                
                for pkey in passes:
                    if passes[pkey] == MCPREP_VIVY_NONE:
                        c_passes.pop(pkey)
                for rkey in refinements:
                    if refinements[rkey] == MCPREP_VIVY_NONE:
                        c_refinements.pop(rkey)
                
                if len(c_passes):
                    data["materials"][key]["passes"] = c_passes
                if len(c_refinements):
                    data["materials"][key]["refinements"] = c_refinements

            json_path = vivy_materials.get_vivy_json()
            with open(json_path, 'w') as f:
                json.dump(data, f)
        return {'FINISHED'}

class MCPREP_PT_vivy_editor(bpy.types.Panel):
    bl_label = "Vivy Config Editor"
    bl_idname = "MCPREP_PT_vivy_editor"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Vivy"
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        return str(vivy_materials.get_vivy_blend().absolute()) == bpy.data.filepath and is_vivy_enabled(context)

    def draw(self, context):
        layout = self.layout
        vprop = context.scene.vivy_editor_props
        if vprop.vivy_materials and env.vivy_material_json is not None:
            layout.template_list("MCPREP_UL_vivy_materials", 
                                 "", 
                                 vprop, 
                                 "vivy_materials", 
                                 vprop, 
                                 "vivy_materials_index", 
                                 rows=4)
            mat = vprop.vivy_materials[vprop.vivy_materials_index]
            box = layout.box()
            box.label(text=f"{mat.name} Properties")
            row = box.row()
            row.prop(mat, "name")
            row = box.row()
            row.prop(mat, "desc")
            row = box.row()
            row.prop(mat, "base_material")
            row = box.row()
            row.prop(mat, "diffuse")
            row = box.row()
            row.prop(mat, "specular")
            row = box.row()
            row.prop(mat, "normal")
            row = box.row()
            row.prop(mat, "emissive")
            row = box.row()
            row.prop(mat, "reflective")
            row = box.row()
            row.prop(mat, "metallic")
            row = box.row()
            row.prop(mat, "glass")
            row = box.row()
            row.prop(mat, "fallback_s")
            row = box.row()
            row.prop(mat, "fallback_n")
            row = box.row()
            row.prop(mat, "fallback")

            layout.operator("vivy.apply_changes")
        else:
            layout.operator("vivy.reload_editor")   

classes = [
    MCPREP_OT_vivy_reload_editor,
    MCPREP_OT_vivy_apply_changes,
    MCPREP_PT_vivy_editor,
    MCPREP_UL_vivy_materials,
    ListVivyMaterials,
    VivyEditorProps,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vivy_editor_props = bpy.props.PointerProperty(type=VivyEditorProps)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.vivy_editor_props
