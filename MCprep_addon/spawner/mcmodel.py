import os
import json
from mathutils import Vector
from math import pi, sin, cos, radians

import bpy
import bmesh
from bpy.types import Operator
from bpy_extras.object_utils import AddObjectHelper, object_data_add
from bpy_extras.io_utils import ImportHelper

# addon imports
from .. import conf
from .. import util

def rotate_around(d,pos,origin,axis='z',offset=[8,0,8],scale=[0.063,0.063,0.063]):
	r = -radians(d)
	axis_i = ord(axis)-120 # 'x'=0, 'y'=1, 'z'=2
	a = pos[(1+axis_i)%3]
	b = pos[(2+axis_i)%3]
	c = pos[(3+axis_i)%3]
	m = origin[(1+axis_i)%3]
	n = origin[(2+axis_i)%3]
	# this equation rotates the verticies around the origin point
	new_pos = [0,0,0]
	new_pos[(1+axis_i)%3] = cos(r)*(a-m)+(b-n)*sin(r)+m
	new_pos[(2+axis_i)%3] = -sin(r)*(a-m)+cos(r)*(b-n)+n
	new_pos[(3+axis_i)%3] = c
	# offset and scale are applied to the vertices in the return
	# the default offset is what makes sure the block/item is centered
	# the default scale will match the scale of the blocks from mineways, or 1 gridspace
	return Vector((
			-(new_pos[0]-offset[0])*scale[0],
			(new_pos[2]-offset[2])*scale[2],
			(new_pos[1]-offset[1])*scale[1]
		))

def add_element(elm_from=[0,0,0],elm_to=[16,16,16],rot_origin=[8,8,8],rot_axis='y',rot_angle=0):
	'''this function calculates and defines the verts, edge, and faces that will be created'''
	verts = [
		rotate_around(rot_angle,[elm_from[0], elm_to[1], elm_from[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_to[0], elm_to[1], elm_from[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_to[0], elm_from[1], elm_from[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_from[0], elm_from[1], elm_from[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_from[0], elm_to[1], elm_to[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_to[0], elm_to[1], elm_to[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_to[0], elm_from[1], elm_to[2]],rot_origin,rot_axis),
		rotate_around(rot_angle,[elm_from[0], elm_from[1], elm_to[2]],rot_origin,rot_axis),
	]

	edges = []
	faces = [[0, 1, 2, 3],[5, 4, 7, 6],[1, 0, 4, 5],[7, 6, 2, 3],[4, 0, 3, 7],[1, 5, 6, 2]]
	
	return [verts,edges,faces]

def add_material(name = "material", pth = ""): 
	'''creates a simple material with an image texture from pth'''
	conf.log(name+": "+pth)
	mat = bpy.data.materials.new(name=name)
	mat.blend_method = 'CLIP'
	mat.shadow_method = 'CLIP'
	mat.use_nodes = True
	matnodes = mat.node_tree.nodes

	tex = matnodes.new('ShaderNodeTexImage')
	if os.path.isfile(pth):
		img = bpy.data.images.load(pth, check_existing=True)
		tex.image = img
	tex.interpolation = 'Closest'

	shader = matnodes['Principled BSDF']
	mat.node_tree.links.new(shader.inputs['Base Color'], tex.outputs['Color'])
	mat.node_tree.links.new(shader.inputs['Alpha'], tex.outputs['Alpha'])

	return mat

def locate_image(context,textures,img,model_filepath):
	'''finds and returns the filepath of the image texture'''
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)

	local_path = textures[img]
	if local_path[0] == '#': # reference to another texture
		return locate_image(context,textures,local_path[1:],model_filepath)
		# note this will result in multiple materials that use the same texture
		# considering reworking this function to also create the material so these can point towards the same material 
	else:
		if local_path[0] == '.': # path is local to the model file
			directory = os.path.dirname(model_filepath)
		else:
			if(len(local_path.split(":"))==1):
				namespace = "minecraft"
			else:
				namespace = local_path.split(":")[0]
				local_path = local_path.split(":")[1]

			directory = os.path.join(resource_folder,"assets",namespace,"textures")
		return os.path.realpath(os.path.join(directory,local_path)+".png")

def read_model(context, model_filepath): 
	'''reads the json file and pulls out the textures and elements needed to construct the model
	
	this function is recursively called to also get the elements and textures from the parent models
	the elements from the child will always overwrite the parent's elements
	individual textures from the child will overwrite the same texture from the parent.
	'''
	with open(model_filepath, 'r') as f:
			obj_data = json.load(f)
	
	resource_folder = bpy.path.abspath(context.scene.mcprep_texturepack_path)
	
	elements = None
	textures = None

	parent = obj_data.get("parent")
	if parent is not None:
		if parent == "builtin/generated" or parent == "item/generated":
			pass # generates the model from the texture
		elif parent == "builtin/entity":
			pass # model from an entity file, only for chests, ender chests, mob heads, shields, banners and tridents
		else:
			if(len(parent.split(":")) == 1):
				namespace = "minecraft"
				parent_filepath = parent
			else:
				namespace = parent.split(":")[0]
				parent_filepath = parent.split(":")[1]
			
			models_dir = os.path.join(resource_folder,"assets",namespace,"models")
			elements, textures = read_model(context,os.path.join(models_dir,parent_filepath)+".json")
	
	current_elements = obj_data.get("elements")
	if current_elements is not None:
		elements = current_elements # overwrites any elements from parents

	current_textures = obj_data.get("textures")
	if current_textures is not None:
		if textures is None: textures = current_textures
		else:
			for img in current_textures:
				textures[img] = current_textures[img]

	conf.log("\nfile:"+str(model_filepath))
	conf.log("parent:"+str(parent))
	conf.log("elements:"+str(elements))
	conf.log("textures:"+str(textures))

	return elements, textures

def add_model(model_filepath, obj_name="MinecraftModel"):
	
	mesh = bpy.data.meshes.new(obj_name)  # add a new mesh
	obj = bpy.data.objects.new(obj_name, mesh)  # add a new object using the mesh

	collection = bpy.context.collection
	view_layer = bpy.context.view_layer
	collection.objects.link(obj)  # put the object into the scene (link)
	view_layer.objects.active = obj  # set as the active object in the scene
	obj.select_set(True)  # select object

	bm = bmesh.new()

	mesh.uv_layers.new()
	uv_layer = bm.loops.layers.uv.verify()
	elements, textures = read_model(bpy.context, model_filepath)

	materials=[]
	for img in textures:
		if img!="particle":
			tex_pth=locate_image(bpy.context,textures,img,model_filepath)
			mat = add_material(obj_name+"_"+img, tex_pth)
			obj.data.materials.append(mat)
			materials.append("#"+img)

	if elements is None:
		elements=[{'from':[0,0,0],'to':[0,0,0]}] # temp default elements

	for e in elements:
		rotation = e.get("rotation")
		if rotation is None:
			rotation={"angle": 0, "axis": "y", "origin": [8, 8, 8]} # rotation default
		
		element = add_element(e['from'],e['to'],rotation['origin'],rotation['axis'],rotation['angle']) 
		verts=[bm.verts.new(v) for v in element[0]]  # add a new vert
		uvs=[[1,1],[0,1],[0,0],[1,0]]
		face_dir=["north","south","up","down","west","east"] # face directions defaults
		faces = e.get("faces")
		for i in range(len(element[2])):
			f = element[2][i]
			
			if not faces:
				continue
				
			d_face=faces.get(face_dir[i])
			if not d_face:
				continue
			
			face=bm.faces.new((verts[f[0]],verts[f[1]],verts[f[2]],verts[f[3]]))
			face.normal_update()

			uv_rot = d_face.get("rotation") # uv can be rotated 0, 90, 180, or 270 degrees
			if uv_rot is None:
				uv_rot = 0

			uv_idx = int(uv_rot/90) # the index of the first uv cord
									# the rotation is achieved by shifting the order of the uv coords
			uv_coords = d_face.get("uv") # in the format [x1, y1, x2, y2]
			if uv_coords is None:
				uv_coords = [0,0,16,16]
				
			uvs = [ [uv_coords[2]/16,1-(uv_coords[1]/16)], # [x2, y1]
					[uv_coords[0]/16,1-(uv_coords[1]/16)], # [x1, y1]
					[uv_coords[0]/16,1-(uv_coords[3]/16)], # [x1, y2]
					[uv_coords[2]/16,1-(uv_coords[3]/16)]  # [x2, y2]
				  ] # uv in the model is between 0 to 16 regardless of resolution, in blender its 0 to 1
					# the y-axis is inverted when compared to blender uvs, which is why it is subtracted from 1
					# essentially this converts the json uv points to the blender equivelent

			for j in range(len(face.loops)):
				face.loops[j][uv_layer].uv = uvs[(j+uv_idx)%len(uvs)] # the order of the uv coords is determened by the rotation of the uv
																	  # as an example, if the uv is rotated by 180 degrees, the first index will be 2 than 3, 0, 1

			face_mat = d_face.get("texture")
			if face_mat is not None:
				face.material_index = materials.index(face_mat)

	# make the bmesh the object's mesh
	bm.to_mesh(mesh)  
	bm.free()

def draw_import_mcmodel(self, context):
	layout = self.layout
	layout.operator("mcprep.import_mcmodel" , text="Minecraft Model (.json)")


class MCPREP_OT_import_minecraft_model(bpy.types.Operator, ImportHelper):
	"""Tooltip"""
	bl_idname = "mcprep.import_mcmodel"
	bl_label = ""
	bl_options = {'REGISTER', 'UNDO'}

	filename_ext=".json"
	filter_glob = bpy.props.StringProperty(
		default="*.json",
		options={'HIDDEN'},
		maxlen=255  # Max internal buffer length, longer would be clamped.
	)

	def execute(self, context):
		filename = os.path.splitext(os.path.basename(self.filepath))[0]
		add_model(os.path.normpath(self.filepath), filename)
		return {'FINISHED'}

classes = (
	MCPREP_OT_import_minecraft_model,
)

def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)

	bpy.types.TOPBAR_MT_file_import.append(draw_import_mcmodel)

def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(draw_import_mcmodel)

	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)