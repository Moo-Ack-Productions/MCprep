import bpy
import json
from .conf import env
from .util import is_vivy_enabled
from .materials import vivy_materials

class ListVivyMaterials(bpy.types.PropertyGroup):
    def items_materials(self, context):
        items = []
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

class VIVY_UL_materials(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if env.vivy_material_json is not None:
                layout.label(text=item.name)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)

class VIVY_OT_reload_editor(bpy.types.Operator):
    bl_idname = "vivy.reload_editor"
    bl_label = "Reload Vivy Materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        env.reload_vivy_json(context.scene.vivy_file_path)
        reload_vivy_materials(context)
        return {'FINISHED'}

class VIVY_OT_apply_changes(bpy.types.Operator):
    bl_idname = "vivy.apply_changes"
    bl_label = "Apply Changes to Current Material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        env.reload_vivy_json()
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
                orig_passes["diffuse"] = name.diffuse
                orig_passes["specular"] = name.specular
                orig_passes["normal"] = name.normal
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
                        "diffuse": mat.diffuse,
                        "specular": mat.specular,
                        "normal": mat.normal
                    }
                }

            json_path = vivy_materials.get_vivy_json()
            with open(json_path, 'w') as f:
                json.dump(data, f)
        return {'FINISHED'}

class VIVY_PT_editor(bpy.types.Panel):
    bl_label = "Vivy Config Editor"
    bl_idname = "VIVY_PT_editor"
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
            layout.template_list("VIVY_UL_materials", 
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
            layout.operator("vivy.apply_changes")
        else:
            layout.operator("vivy.reload_editor")   

classes = [
    VIVY_OT_reload_editor,
    VIVY_OT_apply_changes,
    VIVY_PT_editor,
    VIVY_UL_materials,
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
