import bpy
from .conf import env

class ListVivyMaterials(bpy.types.PropertyGroup):
	name: bpy.props.StringProperty()

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
		env.reload_vivy_json()
		reload_vivy_materials(context)
		return {'FINISHED'}

class VIVY_PT_editor(bpy.types.Panel):
	bl_label = "Vivy Editor"
	bl_space_type = "PROPERTIES"
	bl_region_type = 'WINDOW'
	bl_context = "world"

	def draw(self, context):
		layout = self.layout
		vprop = context.scene.vivy_editor_props
		if vprop.vivy_materials and env.vivy_material_json is not None:
			layout.template_list("VIVY_UL_materials", "", vprop, "vivy_materials", vprop, "vivy_materials_index", rows=4)
			mat = vprop.vivy_materials[vprop.vivy_materials_index]
			mp = env.vivy_material_json["materials"][mat.name]
			box = layout.box()
			box.label(text=f"{mat.name} Properties")

			row = box.row()
			row.label(text=f"Base Material: {mp['base_material']}")
			row = box.row()
			row.label(text=mp["desc"])
			
			if "passes" in mp:
				nbox = box.box()
				nbox.label(text="Passes")
				for p in mp["passes"]:
					row = nbox.row()
					row.label(text=f"{p.capitalize()}: {mp['passes'][p]}")
			if "refinements" in mp:
				nbox = box.box()
				nbox.label(text="Refinements")
				for r in mp["refinements"]:
					row = nbox.row()
					row.label(text=f"{r.capitalize()}: {mp['refinements'][r]}")
				
		else:
			layout.operator("vivy.reload_editor")	

classes = [
	VIVY_OT_reload_editor,
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
