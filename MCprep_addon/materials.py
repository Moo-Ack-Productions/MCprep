# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2016 Patrick W. Crawford
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####


# library imports
import bpy
import os
import math

# addon imports
from . import conf
from . import util


# -----------------------------------------------------------------------------
# Material utility functions
# -----------------------------------------------------------------------------


####
# Operator, sets up the materials for better Blender Internal rendering
class MCPREP_materialChange(bpy.types.Operator):
	"""Fixes materials and textures on selected objects for Minecraft rendering"""
	bl_idname = "object.mcprep_mat_change" #"object.mc_mat_change"
	bl_label = "MCprep Materials"
	bl_options = {'REGISTER', 'UNDO'}

	useReflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropraite materials to be rendered reflective",
		default = True
		)
	
	def getListDataMats(self):

		reflective = [ 'glass', 'glass_pane_side','ice','ice_packed','iron_bars','door_iron_top','door_iron_bottom',
						'diamond_block','iron_block','gold_block','emerald_block','iron_trapdoor','glass_*',
						'Iron_Door','Glass_Pane','Glass','Stained_Glass_Pane','Iron_Trapdoor','Block_of_Iron',
						'Block_of_Diamond','Stained_Glass','Block_of_Gold','Block_of_Emerald','Packed_Ice',
						'Ice']
		water = ['water','water_flowing','Stationary_Water']
		# things are transparent by default to be safe, but if something is solid it is much
		# better to make it solid (faster render and build times)
		solid = ['sand','dirt','dirt_grass_side','dirt_grass_top','dispenser_front','furnace_top',
				'redstone_block','gold_block','stone','iron_ore','coal_ore','wool_*','stained_clay_*',
				'stone_brick','cobblestone','plank_*','log_*','farmland_wet','farmland_dry',
				'cobblestone_mossy','nether_brick','gravel','*_ore','red_sand','dirt_podzol_top',
				'stone_granite_smooth','stone_granite','stone_diorite','stone_diorite_smooth','stone_andesite',
				'stone_andesite_smooth','brick','snow','hardened_clay','sandstone_side','sandstone_side_carved',
				'sandstone_side_smooth','sandstone_top','red_sandstone_top','red_sandstone_normal','bedrock',
				'dirt_mycelium_top','stone_brick_mossy','stone_brick_cracked','stone_brick_circle',
				'stone_slab_side','stone_slab_top','netherrack','soulsand','*_block','endstone',
				'Grass_Block','Dirt','Stone_Slab','Stone','Oak_Wood_Planks','Wooden_Slab','Sand','Carpet',
				'Wool','Stained_Clay','Gravel','Sandstone','*_Fence','Wood','Acacia/Dark_Oak_Wood','Farmland',
				'Brick','Snow','Bedrock','Netherrack','Soul_Sand','End_Stone']
		emit = ['redstone_block','redstone_lamp_on','glowstone','lava','lava_flowing','fire',
				'sea_lantern',
				'Glowstone','Redstone_Lamp_(on)','Stationary_Lava','Fire','Sea_Lantern','Block_of_Redstone']

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
			if conf.v:print('\tiwarning: material '+mat.name+' has no texture slot. skipping...')
			return

		# disable all but first slot, ensure first slot enabled
		mat.use_textures[0] = True
		for index in range(1,len(texList)):
			mat.use_textures[index] = False
	   
		#generalizing the name, so that lava.001 material is recognized and given emit
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

		if not self.checklist(matGen,listData['solid']): #ie alpha is on unless turned off
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
			## ^ need to get right format to remove link, need link object, not endpoints
			nodeMix1.inputs[0].default_value = 0 # no transparency
		try:
			if nodeTex.image.source =='SEQUENCE':
				nodeTex.image_user.use_cyclic = True
				nodeTex.image_user.use_auto_refresh = True
				intlength = mat.texture_slots[0].texture.image_user.frame_duration
				nodeTex.image_user.frame_duration = intlength
		except:
			pass
	
	
	def execute(self, context):
		#get list of selected objects
		objList = context.selected_objects
		if len(objList)==0:
			self.report({'ERROR'}, "No objects selected")
			return {'CANCELLED'}

		# gets the list of materials (without repetition) in the selected object list
		matList = util.materialsFromObj(objList)
		if len(objList)==0:
			self.report({'ERROR'}, "No materials found on selected objects")
			return {'CANCELLED'}
		
		#check if linked material exists
		render_engine = bpy.context.scene.render.engine
		count = 0

		for mat in matList:
			#if linked false:
			if (True):
				if (render_engine == 'BLENDER_RENDER'):
					#print('BI mat')
					if conf.vv:print("Blender internal material prep")
					self.materialsInternal(mat)
				elif (render_engine == 'CYCLES'):
					#print('cycles mat')
					if conf.vv:print("Cycles material prep")
					self.materialsCycles(mat)
			else:
				if conf.v:print('Get the linked material instead!')
		#if checkOptin():usageStat('materialChange')
		return {'FINISHED'}



def register():
	"register"

def unregister():
	"unregister"
