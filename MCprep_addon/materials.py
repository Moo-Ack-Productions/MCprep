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


# library imports
import bpy
import os
import math
from bpy_extras.io_utils import ImportHelper
import shutil
import urllib.request
from bpy.app.handlers import persistent

# addon imports
from . import conf
from . import util
from . import tracking


# -----------------------------------------------------------------------------
# Material class functions
# -----------------------------------------------------------------------------



class MCPREP_materialChange(bpy.types.Operator):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "mcprep.mat_change"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

	useReflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropriate materials to be rendered reflective",
		default = True
		)

	combineMaterials = bpy.props.BoolProperty(
		name = "Combine materials",
		description = "Consolidate duplciate materials & textures",
		default = False
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	# prop: consolidate textures consolidateTextures
	# prop: set all blocks as solid (no transparency)
	# set transparency type (z versus ray)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		row = self.layout.row()
		col = row.column()
		col.prop(self, "useReflections")
		col.prop(self, "combineMaterials")
		# tick box to enable tracking

	def getListDataMats(self):

		reflective = [ 'glass', 'glass_pane_side','ice','ice_packed','iron_bars',
				'door_iron_top','door_iron_bottom','diamond_block','iron_block',
				'gold_block','emerald_block','iron_trapdoor','glass_*',
				'Iron_Door','Glass_Pane','Glass','Stained_Glass_Pane',
				'Iron_Trapdoor','Block_of_Iron','Block_of_Diamond',
				'Stained_Glass','Block_of_Gold','Block_of_Emerald',
				'Packed_Ice','Ice']
		water = ['water','water_flowing','Stationary_Water']
		# things are transparent by default to be safe, but if something is solid
		# it is better to make it solid (faster render and build times)
		solid = ['sand','dirt','dirt_grass_side','dirt_grass_top',
				'dispenser_front','furnace_top','redstone_block','gold_block',
				'stone','iron_ore','coal_ore','wool_*','stained_clay_*',
				'stone_brick','cobblestone','plank_*','log_*','farmland_wet',
				'farmland_dry','cobblestone_mossy','nether_brick','gravel',
				'*_ore','red_sand','dirt_podzol_top','stone_granite_smooth',
				'stone_granite','stone_diorite','stone_diorite_smooth',
				'stone_andesite','stone_andesite_smooth','brick','snow',
				'hardened_clay','sandstone_side','sandstone_side_carved',
				'sandstone_side_smooth','sandstone_top','red_sandstone_top',
				'red_sandstone_normal','bedrock','dirt_mycelium_top',
				'stone_brick_mossy','stone_brick_cracked','stone_brick_circle',
				'stone_slab_side','stone_slab_top','netherrack','soulsand',
				'*_block','endstone','Grass_Block','Dirt','Stone_Slab','Stone',
				'Oak_Wood_Planks','Wooden_Slab','Sand','Carpet','Wool',
				'Stained_Clay','Gravel','Sandstone','*_Fence','Wood',
				'Acacia/Dark_Oak_Wood','Farmland','Brick','Snow','Bedrock',
				'Netherrack','Soul_Sand','End_Stone']
		emit = ['redstone_block','redstone_lamp_on','glowstone','lava',
				'lava_flowing','fire','sea_lantern','Glowstone',
				'Redstone_Lamp_(on)','Stationary_Lava','Fire','Sea_Lantern',
				'Block_of_Redstone','torch_flame_noimport','Sea-Lantern']

		######## CHANGE TO MATERIALS LIBRARY
		# if v and not importedMats:print("Parsing library file for materials")
		# #attempt to LOAD information from an asset file...
		# matLibPath = bpy.context.scene.MCprep_material_path
		# if not(os.path.isfile(matLibPath)):
		# 	#extract actual path from the relative one
		# 	matLibPath = bpy.path.abspath(matLibPath)

		# WHAT IT SHOULD DO: check the NAME of the current material,
		# and ONLY import that one if it's there. maybe split this into another function
		# imported mats is a bool so we only attempt to load one time instead of like fifty.
		# now go through the new materials and change them for the old...?

		return {'reflective':reflective, 'water':water, 'solid':solid,
				'emit':emit}

	# helper function for expanding wildcard naming for generalized materials
	# maximum 1 wildcard *
	def checklist(self,matName,alist):
		if matName in alist:
			return True
		else:
			for name in alist:
				if '*' in name:
					x = name.split('*')
					if x[0] != '' and x[0] in matName:
						return True
					elif x[1] != '' and x[1] in matName:
						return True
			return False

	## HERE functions for GENERAL material setup (cycles and BI)
	def materialsInternal(self, mat):

		# defines lists for materials with special default settings.
		listData = self.getListDataMats()
		try:
			newName = mat.name+'_tex' # add exception to skip? with warning?
			texList = mat.texture_slots.values()
		except:
			if conf.v:print('\tissue: '+obj.name+' has no active material')
			return
		### Check material texture exists and set name
		try:
			bpy.data.textures[texList[0].name].name = newName
		except:
			if conf.v:print('\twarning: material '
				+mat.name+' has no texture slot. skipping...')
			return

		# disable all but first slot, ensure first slot enabled
		mat.use_textures[0] = True
		for index in range(1,len(texList)):
			mat.use_textures[index] = False

		# strip out the .00#
		matGen = util.nameGeneralize(mat.name)
		mat.use_nodes = False

		mat.use_transparent_shadows = True #all materials receive trans
		mat.specular_intensity = 0
		mat.texture_slots[0].texture.use_interpolation = False
		mat.texture_slots[0].texture.filter_type = 'BOX'
		mat.texture_slots[0].texture.filter_size = 0
		mat.texture_slots[0].use_map_color_diffuse = True
		mat.texture_slots[0].diffuse_color_factor = 1
		mat.use_textures[1] = False

		if not self.checklist(matGen,listData['solid']): # alpha default on
			bpy.data.textures[newName].use_alpha = True
			mat.texture_slots[0].use_map_alpha = True
			mat.use_transparency = True
			mat.alpha = 0
			mat.texture_slots[0].alpha_factor = 1

		if self.useReflections and self.checklist(matGen,listData['reflective']):
			mat.alpha=0.15
			mat.raytrace_mirror.use = True
			mat.raytrace_mirror.reflect_factor = 0.3
		else:
			mat.raytrace_mirror.use = False
			mat.alpha=0

		if self.checklist(matGen,listData['emit']):
			mat.emit = 1
		else:
			mat.emit = 0
		return 0

	### Function for default cycles materials
	def materialsCycles(self, mat):
		# get the texture, but will fail if NoneType
		try:
			imageTex = mat.texture_slots[0].texture.image
		except:
			return
		matGen = util.nameGeneralize(mat.name)
		listData = self.getListDataMats()

		#enable nodes
		mat.use_nodes = True
		nodes = mat.node_tree.nodes
		links = mat.node_tree.links
		nodes.clear()
		nodeDiff = nodes.new('ShaderNodeBsdfDiffuse')
		nodeGloss = nodes.new('ShaderNodeBsdfGlossy')
		nodeTrans = nodes.new('ShaderNodeBsdfTransparent')
		nodeMix1 = nodes.new('ShaderNodeMixShader')
		nodeMix2 = nodes.new('ShaderNodeMixShader')
		nodeTex = nodes.new('ShaderNodeTexImage')
		nodeOut = nodes.new('ShaderNodeOutputMaterial')

		# set location and connect
		nodeTex.location = (-400,0)
		nodeGloss.location = (0,-150)
		nodeDiff.location = (-200,-150)
		nodeTrans.location = (-200,0)
		nodeMix1.location = (0,0)
		nodeMix2.location = (200,0)
		nodeOut.location = (400,0)
		links.new(nodeTex.outputs["Color"],nodeDiff.inputs[0])
		links.new(nodeDiff.outputs["BSDF"],nodeMix1.inputs[2])
		links.new(nodeTex.outputs["Alpha"],nodeMix1.inputs[0])
		links.new(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
		links.new(nodeGloss.outputs["BSDF"],nodeMix2.inputs[2])
		links.new(nodeMix1.outputs["Shader"],nodeMix2.inputs[1])
		links.new(nodeMix2.outputs["Shader"],nodeOut.inputs[0])
		nodeTex.image = imageTex
		nodeTex.interpolation = 'Closest'

		#set other default values, e.g. the mixes
		nodeMix2.inputs[0].default_value = 0 # factor mix with glossy
		nodeGloss.inputs[1].default_value = 0.1 # roughness

		# the above are all default nodes. Now see if in specific lists
		if self.useReflections and self.checklist(matGen,listData['reflective']):
			nodeMix2.inputs[0].default_value = 0.3  # mix factor
			nodeGloss.inputs[1].default_value = 0.005 # roughness
		if self.checklist(matGen,listData['emit']):
			# add an emit node, insert it before the first mix node
			nodeMixEmitDiff = nodes.new('ShaderNodeMixShader')
			nodeEmit = nodes.new('ShaderNodeEmission')
			nodeEmit.location = (-400,-150)
			nodeMixEmitDiff.location = (-200,-150)
			nodeDiff.location = (-400,0)
			nodeTex.location = (-600,0)

			links.new(nodeTex.outputs["Color"],nodeEmit.inputs[0])
			links.new(nodeDiff.outputs["BSDF"],nodeMixEmitDiff.inputs[1])
			links.new(nodeEmit.outputs["Emission"],nodeMixEmitDiff.inputs[2])
			links.new(nodeMixEmitDiff.outputs["Shader"],nodeMix1.inputs[2])

			nodeMixEmitDiff.inputs[0].default_value = 0.9
			nodeEmit.inputs[1].default_value = 2.5
			# emit value
		if self.checklist(matGen,listData['water']):
			# setup the animation??
			nodeMix2.inputs[0].default_value = 0.2
			nodeGloss.inputs[1].default_value = 0.01 # copy of reflective for now
		if self.checklist(matGen,listData['solid']):
			#links.remove(nodeTrans.outputs["BSDF"],nodeMix1.inputs[1])
			nodeMix1.inputs[0].default_value = 0 # no transparency
		try:
			if nodeTex.image.source =='SEQUENCE':
				nodeTex.image_user.use_cyclic = True
				nodeTex.image_user.use_auto_refresh = True
				intlength = mat.texture_slots[0].texture.image_user.frame_duration
				nodeTex.image_user.frame_duration = intlength
		except:
			pass
		return 0

	def execute(self, context):

		# skip tracking if internal change
		if self.skipUsage==False:
			tracking.trackUsage("materials",bpy.context.scene.render.engine)

		#get list of selected objects
		objList = context.selected_objects
		if len(objList)==0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) from selected
		matList = util.materialsFromObj(objList)
		if len(objList)==0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}

		#check if linked material exists
		render_engine = context.scene.render.engine
		count = 0

		for mat in matList:
			#if linked false:
			if (True):
				if (render_engine == 'BLENDER_RENDER'):
					#print('BI mat')
					res = self.materialsInternal(mat)
					if res==0: count+=1
				elif (render_engine == 'CYCLES'):
					#print('cycles mat')
					res = self.materialsCycles(mat)
					if res==0: count+=1
				else:
					self.report({'ERROR'},"Only blender internal or cycles supported")
					return {'CANCELLED'}
			else:
				if conf.v:print('Get the linked material instead!')

		if self.combineMaterials==True:
			bpy.ops.mcprep.combine_materials(selection_only=True, skipUsage=True)
		self.report({"INFO"},"Modified "+str(count)+" materials")
		return {'FINISHED'}



class MCPREP_combineMaterials(bpy.types.Operator):
	bl_idname = "mcprep.combine_materials"
	bl_label = "Combine materials"
	bl_description = "Consolidate the same materials together e.g. mat.001 and mat.002"

	# arg to auto-force remove old? versus just keep as 0-users
	selection_only = bpy.props.BoolProperty(
		name = "Selection only",
		description = "Build materials to consoldiate based on selected objects only",
		default = True
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	def execute(self, context):

		# skip tracking if internal change
		if self.skipUsage==False: tracking.trackUsage("combine_materials")

		removeold = True

		if self.selection_only==True and len(context.selected_objects)==0:
			self.report({'ERROR',"Either turn selection only off or select objects with materials"})
			return {'CANCELLED'}

		# 2-level structure to hold base name and all
		# materials blocks with the same base
		nameCat = {}


		def getMaterials(self, context):
			if self.selection_only == False:
				return bpy.data.materials
			else:
				mats = []
				for ob in bpy.data.objects:
					for sl in ob.material_slots:
						if sl == None or sl.material == None:continue
						if sl.material in mats:continue
						mats.append(sl.material)
				return mats

		data = getMaterials(self, context)
		precount = len( ["x" for x in data if x.users >0] )

		if len(data)==0:
			if self.selection_only==True:
				self.report({"ERROR"},"No materials found on selected objects")
			else:
				self.report({"ERROR"},"No materials in open file")
			return {'CANCELLED'}

		# get and categorize all materials names
		for mat in data:
			base = util.nameGeneralize(mat.name)
			if base not in nameCat:
				nameCat[base] = [mat.name]
			elif mat.name not in nameCat[base]:
				nameCat[base].append(mat.name)
			else:
				if conf.vv:print("Skipping, already added material")


		# pre 2.78 solution, deep loop
		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl == None or sl.material == None:continue
					if sl.material not in data: continue # selection only
					sl.material = bpy.data.materials[nameCat[ util.nameGeneralize(sl.material.name) ][0]]
			# doesn't remove old textures, but gets it to zero users

			postcount = len( ["x" for x in bpy.data.materials if x.users >0] )
			self.report({"INFO"},
				"Consolidated {x} materials, down to {y} overall".format(
				x=precount-postcount,
				y=postcount))
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in nameCat: # the keys of the dictionary
			if len(base)<2: continue

			nameCat[base].sort() # in-place sorting
			baseMat = bpy.data.materials[ nameCat[base][0] ]

			if conf.vv:print(nameCat[base], "##", baseMat )

			for matname in nameCat[base][1:]:

				# skip if fake user set
				if bpy.data.materials[matname].use_fake_user == True: continue
				# otherwise, remap
				res = util.remap_users(bpy.data.materials[matname],baseMat)
				if res != 0:
					self.report({'ERROR'}, str(res))
					return {'CANCELLED'}
				old = bpy.data.materials[matname]
				if conf.vv:print("removing old? ",bpy.data.materials[matname])
				if removeold==True and old.users==0:
					if conf.vv:print("removing old:")
					data.remove( bpy.data.materials[matname] )

			# Final step.. rename to not have .001 if it does
			genBase = util.nameGeneralize(baseMat.name)
			if baseMat.name != genBase:
				if genBase in bpy.data.materials and bpy.data.materials[genBase].users!=0:
					pass
				else:
					baseMat.name = genBase
			else:
				baseMat.name = genBase
			if conf.vv:print("Final: ",baseMat)

		postcount = len( ["x" for x in getMaterials(self, context) if x.users >0] )
		self.report({"INFO"},
				"Consolidated {x} materials down to {y}".format(
				x=precount,
				y=postcount))

		return {'FINISHED'}


class MCPREP_combineImages(bpy.types.Operator):
	bl_idname = "mcprep.combine_images"
	bl_label = "Combine images"
	bl_description = "Consolidate the same images together e.g. img.001 and img.002"

	# arg to auto-force remove old? versus just keep as 0-users
	selection_only = bpy.props.BoolProperty(
		name = "Selection only",
		description = "Build images to consoldiate based on selected objects' materials only",
		default = False
		)
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	def execute(self, context):

		# skip tracking if internal change
		if self.skipUsage==False: tracking.trackUsage("combine_images")

		removeold = True

		if self.selection_only==True and len(context.selected_objects)==0:
			self.report({'ERROR',"Either turn selection only off or select objects with materials/images"})
			return {'CANCELLED'}

		# 2-level structure to hold base name and all
		# images blocks with the same base

		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			self.report({'ERROR',"Must use blender 2.78 or higher to use this operator"})
			return {'CANCELLED'}

		if self.selection_only==True:
			self.report({'ERROR'},"Combine images does not yet work for selection only, retry with option disabled")
			return {'CANCELLED'}

		nameCat = {}
		data = bpy.data.images

		precount = len(data)

		# get and categorize all image names
		for im in bpy.data.images:
			base = util.nameGeneralize(im.name)
			if base not in nameCat:
				nameCat[base] = [im.name]
			elif im.name not in nameCat[base]:
				nameCat[base].append(im.name)
			else:
				if conf.vv:print("Skipping, already added image")

		# pre 2.78 solution, deep loop
		if (bpy.app.version[0]>=2 and bpy.app.version[1] >= 78) == False:
			for ob in bpy.data.objects:
				for sl in ob.material_slots:
					if sl == None or sl.material == None:continue
					if sl.material not in data: continue # selection only
					sl.material = data[nameCat[ util.nameGeneralize(sl.material.name) ][0]]
			# doesn't remove old textures, but gets it to zero users

			postcount = len( ["x" for x in bpy.data.materials if x.users >0] )
			self.report({"INFO"},
				"Consolidated {x} materials, down to {y} overall".format(
				x=precount-postcount,
				y=postcount))
			return {'FINISHED'}

		# perform the consolidation with one basename set at a time
		for base in nameCat:
			if len(base)<2: continue

			nameCat[base].sort() # in-place sorting
			baseImg = bpy.data.images[ nameCat[base][0] ]

			for imgname in nameCat[base][1:]:

				# skip if fake user set
				if bpy.data.images[imgname].use_fake_user == True: continue

				# otherwise, remap
				util.remap_users(data[imgname],baseImg)
				old = bpy.data.images[imgname]
				if removeold==True and old.users==0:
					bpy.data.images.remove( bpy.data.images[imgname] )

			# Final step.. rename to not have .001 if it does
			if baseImg.name != util.nameGeneralize(baseImg.name):
				if util.nameGeneralize(baseImg.name) in data and \
						bpy.data.images[util.nameGeneralize(baseImg.name)].users!=0:
					pass
				else:
					baseImg.name = util.nameGeneralize(baseImg.name)
			else:
				baseImg.name = util.nameGeneralize(baseImg.name)

		postcount = len( ["x" for x in bpy.data.images if x.users >0] )
		self.report({"INFO"},
				"Consolidated {x} images down to {y}".format(
				x=precount,
				y=postcount))

		return {'FINISHED'}



class MCPREP_scaleUV(bpy.types.Operator):
	bl_idname = "mcprep.scale_uv"
	bl_label = "Scale Faces"
	bl_description = "Scale all selected UV faces"
	bl_options = {'REGISTER', 'UNDO'}

	scale = bpy.props.FloatProperty(default=1.0,name="Scale")
	first_mouse_x = bpy.props.IntProperty() # hidden
	first_mouse_y = bpy.props.IntProperty() # hidden
	initial_UV = []
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	# 1) Need to save orig_center (x,y) point of all selected faces
	# 2) factor ALWAYS = sqrtdist(initial center - current xy)/sqrtdist(initial_medium - orig_xy)
	# 3) and the sign (positive or negative) is from dot product (scalar) agaisnt orig
	#    vector direction of orig_xy - orig_center
	# 4) Draw a dotted line from curser loc to said origin, plus  in/out arrows aligned to vector
	# 5) Add scale values update parameter in view below on window
	# 6) Add ability to enter text value for scale e.g. type in 0.5 during modal

	# It already works for individual faces...
	# but not when their borders are already touching (which is the use case here)

	# @classmethod
	# def poll(cls, context):
	# 	return context.mode == 'EDIT'

	def modal(self, context, event):
		ob = context.object
		print("EEEVVEENNT: ",event.type,event,type(event))
		if event.type == 'MOUSEMOVE':
			delta = event.mouse_x - self.first_mouse_x
			#context.object.location.x = self.first_value + delta * 0.01
			bpy.ops.object.mode_set(mode="OBJECT")
			factor = 1+delta*0.01
			# ret = self.scale_UV_faces(context, ob, factor)
			ret = self.scale_UV_faces(context, ob, factor)
			bpy.ops.object.mode_set(mode="EDIT")

		elif event.type in {'LEFTMOUSE', 'RET'}:
			# set scale factor here?
			delta = event.mouse_x - self.first_mouse_x
			self.scale = 1+self.first_mouse_x + delta*0.01
			bpy.ops.object.mode_set(mode="EDIT")
			return {'FINISHED'}

		elif event.type in {'RIGHTMOUSE', 'ESC'}:
			bpy.ops.object.mode_set(mode="OBJECT")
			ret = self.scale_UV_faces(context, ob, 1) # unset back to original data
			bpy.ops.object.mode_set(mode="EDIT")
			return {'CANCELLED'}

		return {'RUNNING_MODAL'}

	def invoke(self, context, event):

		# skip tracking if internal change
		if self.skipUsage==False: tracking.trackUsage("scale_UV_faces")

		ob = context.object
		if ob==None:
			self.report({'WARNING'}, "No active object found")
			return {'CANCELLED'}
		elif ob.type != 'MESH':
			self.report({'WARNING'}, "Active object must be a mesh")
			return {'CANCELLED'}
		elif len(ob.data.polygons)==0:
			self.report({'WARNING'}, "Active object has no faces to delete")
			return {'CANCELLED'}

		if not ob.data.uv_layers.active:#uv==None:
			self.report({'WARNING'}, "No active UV map found")
			return {'CANCELLED'}

		bpy.ops.object.mode_set(mode="OBJECT")
		self.first_mouse_x = event.mouse_x
		#zip the data... so that format is [(x,y),(x,y)]
		self.initial_UV = [ (d.uv[0], d.uv[1]) for d in ob.data.uv_layers.active.data]
		print(self.initial_UV)
		#self.initial_UV = list(ob.data.uv_layers.active.data)
		bpy.ops.object.mode_set(mode="EDIT")

		context.window_manager.modal_handler_add(self)
		return {'RUNNING_MODAL'}


	# def execute(self, context):

	# 	# INITIAL WIP
	# 	"""
	# 	# WIP
	# 	ob = context.active_object
	# 	# copied from elsewhere
	# 	uvs = ob.data.uv_layers[0].data
	# 	matchingVertIndex = list(chain.from_iterable(polyIndices))
	# 	# example, matching list of uv coord and 3dVert coord:
	# 	uvs_XY = [i.uv for i in Object.data.uv_layers[0].data]
	# 	vertXYZ= [v.co for v in Object.data.vertices]
	# 	matchingVertIndex = list(chain.from_iterable([p.vertices for p in Object.data.polygons]))
	# 	# and now, the coord to pair with uv coord:
	# 	matchingVertsCoord = [vertsXYZ[i] for i in matchingVertIndex]
	# 	"""

	# 	bpy.ops.object.mode_set(mode="OBJECT")
	# 	ret = self.scale_UV_faces(context, bpy.context.object,self.scale)
	# 	bpy.ops.object.mode_set(mode="EDIT")
	# 	if ret != None:
	# 		self.report({ret[0]},ret[1])
	# 		if conf.v:print(ret[0]+", "+ret[1])
	# 		return {'CANCELLED'}

	# 	return {'FINISHED'}

	def scale_UV_faces(self, context, ob, factor):

		# transform the scale factor properly to implementation below
		factor *= -1
		factor += 1
		mod = False

		uv = ob.data.uv_layers.active

		for f in ob.data.polygons:

			if f.select!=True:continue # if not selected, won't show up in UV editor
			# initialize for avergae center on polygon (probably a better way exists)
			x=0
			y=0
			n=0 # number of verts in loop for average purpose
			for i in f.loop_indices:
				l = ob.data.loops[i] # The loop entry this polygon point refers to
				v = ob.data.vertices[l.vertex_index]  # The vertex data that loop entry refers to
				#print("\tLoop index", l.index, "points to vertex index", l.vertex_index,"at position", v.co)
				# isolate to specific UV already used
				#print("\t\tUV map coord: ", uv.data[l.index].uv)
				if uv.data[l.index].select == False:continue
				x+=uv.data[l.index].uv[0]
				y+=uv.data[l.index].uv[1]
				n+=1
			for i in f.loop_indices:
				if uv.data[l.index].select == False:continue
				l = ob.data.loops[i]
				# hmm.. seems initial_UV index order does NOT remain consistent
				uv.data[l.index].uv[0] = self.initial_UV[l.index][0]*(1-factor)+x/n*(factor)
				uv.data[l.index].uv[1] = self.initial_UV[l.index][1]*(1-factor)+y/n*(factor)
				mod=True
		if mod==False:
			return ("ERROR","No UV faces selected")

		return None


class MCPREP_isolate_alpha_uvs(bpy.types.Operator):
	bl_idname = "mcprep.isolate_alpha_uvs"
	bl_label = "Alpha faces"
	bl_description = "Select or delete alpha faces of a mesh"
	bl_options = {'REGISTER', 'UNDO'}

	# deleteAlpha = False
	skipUsage = bpy.props.BoolProperty(
		default = False,
		options={'HIDDEN'}
		)

	def execute(self, context):

		bpy.ops.object.mode_set(mode="OBJECT")
		# if doing multiple objects, iterate over loop of this function
		ret = self.select_alpha(None, bpy.context, bpy.context.object, 1)
		bpy.ops.object.mode_set(mode="EDIT")

		return {"FINISHED"}

	def select_alpha(self, context, ob, thresh):

		if ob==None:
			return ("ERROR","No active object found")
		elif ob.type != 'MESH':
			return ("ERROR","Active object must be a mesh")
		elif len(ob.data.polygons)==0:
			return ("ERROR","Active object has no faces to delete")

		uv = ob.data.uv_layers.active

		if uv==None:
			return ("ERROR","No active UV map found")

		# img =
		# if ob.data.uv_textures.active == None: continue
		for uv_face in ob.data.uv_textures.active.data:
			uv_face.image = image

		return ("WARNING","Not implemented yet")



class MCPREP_improveUI(bpy.types.Operator):
	"""Improve the UI with specific view settings"""
	bl_idname = "mcprep.improve_ui"
	bl_label = "Improve UI"
	bl_description = "Improve UI for minecraft textures: disable mipmaps & set texture solid"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		context.space_data.show_textured_solid = True
		context.user_preferences.system.use_mipmaps = False

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Skin swapping lists
# -----------------------------------------------------------------------------


# for asset listing UIList drawing
class MCPREP_skin_UIList(bpy.types.UIList):
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):
		layout.prop(set, "name", text="", emboss=False)
		# extra code for placing warning if skin is
		# not square, ie old texture and reocmmend converting it
		# would need to load all images first though.


# for asset listing
class ListColl(bpy.types.PropertyGroup):
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()


# reload the skins in the directory for UI list
def reloadSkinList(context):

	skinfolder = context.scene.mcskin_path
	skinfolder = bpy.path.abspath(skinfolder)
	files = [ f for f in os.listdir(skinfolder) if\
					os.path.isfile(os.path.join(skinfolder,f)) ]

	skinlist = []
	for path in files:
		if path.split(".")[-1].lower() not in ["png","jpg","jpeg","tiff"]: continue
		skinlist.append( (path, "{x} skin".format(x=path)) )

	# clear lists
	context.scene.mcprep_skins_list.clear()
	conf.skin_list = []

	# recreate
	for i, (skin, description) in enumerate(skinlist, 1):
		item = context.scene.mcprep_skins_list.add()
		conf.skin_list.append(  (skin,os.path.join(skinfolder,skin))  )
		item.label = description
		item.description = description
		item.name = skin


# for UI list path callback
def update_skin_path(self, context):
	if conf.vv:print("Updating rig path")
	reloadSkinList(context)


def getMatsFromSelected(selected,new_material=False):
	# pre-expand
	obj_list = []

	for ob in selected:
		if ob.type == 'MESH':
			obj_list.append(ob)
		elif ob.type == 'ARMATURE':
			for ch in ob.children:
				if ch.type == 'MESH': obj_list.append(ch)
		else:
			continue

	mat_list = []
	mat_ret = []
	for ob in obj_list:
		# get all materials
		if new_material==False:
			for slot in ob.material_slots:
				if slot.material==None:continue
				if slot.material not in mat_ret:
					mat_ret.append(slot.material)
		else:
			for slot in ob.material_slots:
				if slot.material not in mat_list:
					if slot.material==None:continue
					mat_list.append(slot.material)
					new_mat = slot.material.copy()
					mat_ret.append(new_mat)
					slot.material = new_mat
				else:
					# if already created, re-assign with new material
					slot.material = mat_ret[ mat_list.index(slot.material) ]

	# if internal, also ensure textures are made unique per new mat
	if new_material and bpy.context.scene.render.engine == 'BLENDER_RENDER':
		for m in mat_ret:
			for tx in m.texture_slots:
				if tx==None:continue
				if tx.texture==None:continue
				tx.texture = tx.texture.copy()

	return mat_ret


# called for any texture changing
# input a list of material & an already loaded image datablock
def changeTexture(image, materials):
	render_engine = bpy.context.scene.render.engine
	if (render_engine == 'BLENDER_RENDER'):
		if conf.vv:print("Blender internal skin swapping")
		status = swapInternal(image, materials)
	elif (render_engine == 'CYCLES'):
		if conf.vv:print("Cycles skin swapping")
		status =swapCycles(image, materials)
	return status


# scene update to auto load skins on load after new file
def handler_skins_enablehack(scene):
	try:
		bpy.app.handlers.scene_update_pre.remove(handler_skins_enablehack)
	except:
		pass
	if conf.vv:print("Triggering Handler_skins_load from first enable")
	handler_skins_load(scene)


@persistent
def handler_skins_load(scene):
	if conf.vv:print("Handler_skins_load running")

	try:
		if conf.vv:print("Reloading skins")
		reloadSkinList(bpy.context)
	except:
		if conf.v:print("Didn't run skin reloading callback")
		pass


# input is either UV image itself or filepath
def swapCycles(image, mats):
	if conf.vv:print("Texture swapping cycles")
	changed = 0
	for mat in mats:
		if mat.node_tree == None:continue
		for node in mat.node_tree.nodes:
			if node.type != "TEX_IMAGE": continue
			node.image = image
			changed+=1

	if changed == 0:
		return False # nothing updated
	else:
		return True # updated at least one texture (the first)


# input is either UV image itself or filepath
def swapInternal(image, mats):
	changed = 0
	for mat in mats:
		for sl in mat.texture_slots:
			if sl==None or sl.texture == None or sl.texture.type != 'IMAGE': continue
			#print("Found a good texture slot! orig image: "+str(sl.texture.image.name))
			sl.texture.image = image
			changed += 1
			break
	if changed == 0:
		return False # nothing updated
	else:
		return True # updated at least one texture (the first)


def loadSkinFile(self, context, filepath, new_material=False):
	if os.path.isfile(filepath)==False:
		self.report({'ERROR'}, "Image file not found")
		# special message for library linking?

	image = util.loadTexture(filepath)
	mats = getMatsFromSelected(context.selected_objects,new_material)
	if len(mats)==0:
		self.report({'ERROR'}, "No materials found to update")
		# special message for library linking?
		return 1

	# do th change, will update according to render engine
	status = changeTexture(image, mats)
	if status == False:
		self.report({'ERROR'}, "No image textures found to update")
		return 1
	else:
		pass

	# adjust the UVs if appropriate
	setUVimage(context.selected_objects,image)

	# and fix eyes if appropriate
	if image.size[1]/image.size[0] != 1:
		self.report({'INFO'}, "Skin swapper works best on 1.8 skins")
		return 0
	return 0


def setUVimage(objs,image):
	for ob in objs:
		if ob.type != "MESH": continue
		if ob.data.uv_textures.active == None: continue
		for uv_face in ob.data.uv_textures.active.data:
			uv_face.image = image

# -----------------------------------------------------------------------------
# Skin swapping classes
# -----------------------------------------------------------------------------



class MCPREP_skinSwapper(bpy.types.Operator, ImportHelper):
	"""Swap the skin of a (character) with another file"""
	bl_idname = "mcprep.skin_swapper"
	bl_label = "Swap skin"
	bl_description = "Swap the skin of a rig with another file"
	bl_options = {'REGISTER', 'UNDO'}

	# filename_ext = ".zip"
	filter_glob = bpy.props.StringProperty(
			default="*",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

	def execute(self,context):
		tracking.trackUsage("skin","file import")
		res = loadSkinFile(self, context, self.filepath)
		if res!=0:
			return {'CANCELLED'}

		return {'FINISHED'}


class MCPREP_applySkin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyskin"
	bl_label = "Apply skin"
	bl_description = "Apply the active UV image to selected character materials"
	bl_options = {'REGISTER', 'UNDO'}

	filepath = bpy.props.StringProperty(
		name="Skin",
		description="selected",
		)
	new_material = bpy.props.BoolProperty(
		name="New Material",
		description="Create a new material instead of overwriting existing one",
		default=True)

	def execute(self,context):
		tracking.trackUsage("skin","ui list")
		res = loadSkinFile(self, context, self.filepath, self.new_material)
		if res!=0:
			return {'CANCELLED'}

		return {'FINISHED'}


class MCPREP_applyUsernameSkin(bpy.types.Operator):
	"""Apply the active UIlist skin to select characters"""
	bl_idname = "mcprep.applyusernameskin"
	bl_label = "Skin from user"
	bl_description = "Download and apply skin from specific username"
	bl_options = {'REGISTER', 'UNDO'}

	username = bpy.props.StringProperty(
		name="Username",
		description="Exact name of user to get texture from",
		default="")

	skip_redownload = bpy.props.BoolProperty(
		name="Skip download if skin already local",
		description="Avoid re-downloading skin and apply local file instead",
		default=True)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		self.layout.label("Enter exact Minecraft username below")
		self.layout.prop(self,"username",text="")
		self.layout.prop(self,"skip_redownload")
		self.layout.label(
			"and then press OK; blender may pause briefly to download")

	def execute(self,context):
		if self.username == "":
			self.report({"ERROR","Invalid username"})
			return {'CANCELLED'}
		tracking.trackUsage("skin","username")

		skins = [ str(skin[0]).lower() for skin in conf.skin_list ]
		paths = [ skin[1] for skin in conf.skin_list ]
		if self.username.lower() not in skins or self.skip_redownload==False:
			if conf.v:print("Donwloading skin")
			self.downloadUser(context)
		else:
			if conf.v:print("Reusing downloaded skin")
			ind = skins.index(self.username.lower())
			res = loadSkinFile(self, context, paths[ind][1])
		return {'FINISHED'}

	def downloadUser(self, context):
		#http://minotar.net/skin/theduckcow
		src_link = "http://minotar.net/skin/"
		saveloc = os.path.join(bpy.path.abspath(context.scene.mcskin_path),
								self.username.lower()+".png")

		#urllib.request.urlretrieve(src_link+self.username.lower(), saveloc)
		try:
			if conf.vv:print("Download starting with url: "+src_link+self.username.lower())
			if conf.vv:print("to save location: "+saveloc)
			urllib.request.urlretrieve(src_link+self.username.lower(), saveloc)
		except urllib.error.HTTPError as e:
			self.report({"ERROR"},"Could not find username")
			return {'CANCELLED'}
		except urllib.error.URLError as e:
			self.report({"ERROR"},"URL error, check internet connection")
			return {'CANCELLED'}
		except Exception as e:
			self.report({"ERROR"},"Error occured while downloading skin: "+str(e))
			return {'CANCELLED'}

		res = loadSkinFile(self, context, saveloc)
		bpy.ops.mcprep.reload_skins()



class MCPREP_skinFixEyes(bpy.types.Operator):
	"""AFix the eyes of a rig to fit a rig"""
	bl_idname = "mcprep.fix_skin_eyes"
	bl_label = "Fix eyes"
	bl_description = "Fix the eyes of a rig to fit a rig"
	bl_options = {'REGISTER', 'UNDO'}

	# initial_eye_type: unknown (default), 2x2 square, 1x2 wide.

	def execute(self,context):

		# take the active texture input (based on selection)
		print("fix eyes")
		self.report({'ERROR'}, "Work in progress operator")
		return {'CANCELLED'}

		return {'FINISHED'}



class MCPREP_addSkin(bpy.types.Operator, ImportHelper):
	bl_idname = "mcprep.add_skin"
	bl_label = "Add skin"
	bl_description = "Add a new skin to the active folder"
	bl_options = {'REGISTER', 'UNDO'}

	# filename_ext = ".zip" # needs to be only tinder
	filter_glob = bpy.props.StringProperty(
			default="*",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

	def execute(self,context):

		new_skin = bpy.path.abspath(self.filepath)
		if os.path.isfile(new_skin) == False:
			self.report({"ERROR"},"Not a image file path")
			return {'CANCELLED'}

		# copy the skin file
		base = bpy.path.basename(new_skin)
		shutil.copy2(new_skin, os.path.join(context.scene.mcskin_path,base))

		# in future, select multiple
		bpy.ops.mcprep.reload_skins()
		self.report({"INFO"},"Added 1 skin") # more in the future

		return {'FINISHED'}



class MCPREP_removeSkin(bpy.types.Operator):
	bl_idname = "mcprep.remove_skin"
	bl_label = "Remove skin"
	bl_description = "Remove a skin from the active folder"
	bl_options = {'REGISTER', 'UNDO'}

	index = bpy.props.IntProperty(
			default=0)

	def execute(self,context):

		if self.index >= len(conf.skin_list):
			self.report({"ERROR"},"Indexing error")
			return {'CANCELLED'}

		file = conf.skin_list[self.index][-1]

		if os.path.isfile(file) == False:
			self.report({"ERROR"},"Skin not found to delete")
			return {'CANCELLED'}

		os.remove(file)

		# refresh the folder
		bpy.ops.mcprep.reload_skins()
		if context.scene.mcprep_skins_list_index >= len(conf.skin_list):
			context.scene.mcprep_skins_list_index = len(conf.skin_list)-1

		# in future, select multiple
		self.report({"INFO"},"Removed "+bpy.path.basename(file))

		return {'FINISHED'}



class MCPREP_reloadSkins(bpy.types.Operator):
	bl_idname = "mcprep.reload_skins"
	bl_label = "Reload skin"
	bl_description = "Reload the skins folder"

	def execute(self, context):
		reloadSkinList(context)
		return {'FINISHED'}



class MCPREP_spawn_with_skin(bpy.types.Operator):
	bl_idname = "mcprep.spawn_with_skin"
	bl_label = "Spawn with skin"
	bl_description = "Spawn rig and apply selected skin"

	relocation = bpy.props.EnumProperty(
		items = [('None', 'Cursor', 'No relocation'),
				('Clear', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root', 'Offset the root bone to curse while moving the rest pose to the origin')],
		name = "Relocation")
	toLink = bpy.props.BoolProperty(
		name = "Library Link",
		description = "Library link instead of append the group",
		default = False
		)
	clearPose = bpy.props.BoolProperty(
		name = "Clear Pose",
		description = "Clear the pose to rest position",
		default = True
		)

	def execute(self, context):
		if len (conf.skin_list)>0:
			skinname = bpy.path.basename(
					conf.skin_list[context.scene.mcprep_skins_list_index][0] )
		else:
			self.report({'ERROR'}, "No skins found")
			return {'CANCELLED'}

		active_mob = conf.rig_list_sub[context.scene.mcprep_mob_list_index][0]

		# try not to use internal ops because of analytics
		bpy.ops.mcprep.mob_spawner(
				mcmob_type=active_mob,
				relocation = self.relocation,
				toLink = self.toLink,
				clearPose = self.clearPose)

		# bpy.ops.mcprep.spawn_with_skin() spawn based on active mob
		ind = context.scene.mcprep_skins_list_index
		bpy.ops.mcprep.applyskin(filepath=conf.skin_list[ind][1])

		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Above for UI
#	Below for register
# -----------------------------------------------------------------------------



def register():
	bpy.types.Scene.mcprep_skins_list = \
			bpy.props.CollectionProperty(type=ListColl)
	bpy.types.Scene.mcprep_skins_list_index = bpy.props.IntProperty(default=0)

	# to auto-load the skins
	if conf.vv:print("Adding reload skin handler to scene")
	try:
		bpy.app.handlers.scene_update_pre.append(handler_skins_enablehack)
	except:
		print("Failed to register scene update handler")
		pass
	bpy.app.handlers.load_post.append(handler_skins_load)


def unregister():
	del bpy.types.Scene.mcprep_skins_list
	del bpy.types.Scene.mcprep_skins_list_index

	try:
		bpy.app.handlers.load_post.remove(handler_skins_load)
		bpy.app.handlers.scene_update_pre.remove(handler_skins_enablehack)
	except:
		pass

