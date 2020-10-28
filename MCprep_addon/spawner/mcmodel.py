import bpy
import bmesh
from bpy.types import Operator
from bpy.props import *
from bpy_extras.object_utils import AddObjectHelper, object_data_add
from mathutils import Vector
from math import pi, sin, cos, radians

from bpy_extras.io_utils import ImportHelper

import json
import os

def rotate_around(d,pos,origin,axis='z',offset=[8,0,8],scale=[0.063,0.063,0.063]):
    r=-radians(d)
    axis_i = ord(axis)-120 # 'x'=0, 'y'=1, 'z'=2
    a=pos[(1+axis_i)%3]
    b=pos[(2+axis_i)%3]
    c=pos[(3+axis_i)%3]
    m=origin[(1+axis_i)%3]
    n=origin[(2+axis_i)%3]
    # this equation rotates the verticies around the origin point
    new_pos=[0,0,0]
    new_pos[(1+axis_i)%3]=cos(r)*(a-m)+(b-n)*sin(r)+m
    new_pos[(2+axis_i)%3]=-sin(r)*(a-m)+cos(r)*(b-n)+n
    new_pos[(3+axis_i)%3]=c
    # offset and scale are applied to the vertices in the return
    # the default offset is what makes sure the block/item is centered
    # the default scale will match the scale of the blocks from mineways, or 1 gridspace
    return Vector((
        -(new_pos[0]-offset[0])*scale[0],
        (new_pos[2]-offset[2])*scale[2],
        (new_pos[1]-offset[1])*scale[1]
        ))

def add_element(elm_from=[0,0,0],elm_to=[16,16,16],rot_origin=[8,8,8],rot_axis='y',rot_angle=0):
    # this function calculates and defines the verts, edge, and faces that will be created
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

def add_material(name="material", pth=""):
    print(name+": "+pth)
    mat = bpy.data.materials.new(name=name)
    mat.blend_method = 'CLIP'
    mat.shadow_method = 'CLIP'
    mat.use_nodes = True
    matnodes = mat.node_tree.nodes

    tex = matnodes.new('ShaderNodeTexImage')
    if os.path.isfile(pth):
        img = bpy.data.images.load(pth, check_existing=True)
        tex.image=img
    tex.interpolation='Closest'

    shader = matnodes['Principled BSDF']
    mat.node_tree.links.new(shader.inputs['Base Color'], tex.outputs['Color'])
    mat.node_tree.links.new(shader.inputs['Alpha'], tex.outputs['Alpha'])

    return mat


def add_object(object, obj_name="MinecraftModel", mesh_name="MinecraftModel_mesh", directory=""):
 
    mesh = bpy.data.meshes.new(mesh_name)  # add a new mesh
    obj = bpy.data.objects.new(obj_name, mesh)  # add a new object using the mesh

    collection = bpy.context.collection
    view_layer = bpy.context.view_layer
    collection.objects.link(obj)  # put the object into the scene (link)
    view_layer.objects.active = obj  # set as the active object in the scene
    obj.select_set(True)  # select object

    mesh = bpy.context.object.data
    bm = bmesh.new()

    mesh.uv_layers.new()
    uv_layer = bm.loops.layers.uv.verify()

    textures = object.get("textures") # currently only looks for textures local to file, need to implement namespace ID with resource packs.
    for img in textures:
        if img!="particle":
            tex_file=textures[img].split('/')[len(textures[img].split('/'))-1]
            print(tex_file, len(tex_file.split('.')))
            tex_pth=textures[img] if len(tex_file.split('.'))>1 else textures[img]+".png"
            
            mat = add_material(img, os.path.realpath(directory+tex_pth))
            obj.data.materials.append(mat)

    elements = object.get("elements")
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
            f=element[2][i]
            if faces:
                d_face=faces.get(face_dir[i])
                if d_face:
                    face=bm.faces.new((verts[f[0]],verts[f[1]],verts[f[2]],verts[f[3]]))
                    face.normal_update()

                    uv_rot = d_face.get("rotation")
                    if uv_rot is None:
                        uv_rot = 0

                    uv_idx = int(uv_rot/90)

                    uv_cords = d_face.get("uv")
                    if uv_cords is None:
                        uv_cords=[0,0,16,16]
                        
                    uvs=[
                        [uv_cords[2]/16,1-(uv_cords[1]/16)],
                        [uv_cords[0]/16,1-(uv_cords[1]/16)],
                        [uv_cords[0]/16,1-(uv_cords[3]/16)],
                        [uv_cords[2]/16,1-(uv_cords[3]/16)]
                        ]

                    for j in range(len(face.loops)):
                        face.loops[j][uv_layer].uv = uvs[(j+uv_idx)%len(uvs)]

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
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        with open(self.filepath, 'r') as f:
            obj_data=json.loads(f.read())

        directories = self.filepath.split('\\')
        filename = directories[len(directories)-1][:-len(self.filename_ext)]
        add_object(obj_data, filename, filename+"_mesh", self.filepath[:-len(filename+self.filename_ext)])
        return {'FINISHED'}

def register():
    bpy.utils.register_class(MCPREP_OT_import_minecraft_model)
    bpy.types.TOPBAR_MT_file_import.append(draw_import_mcmodel)

def unregister():

    bpy.utils.unregister_class(MCPREP_OT_import_minecraft_model)