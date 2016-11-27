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

import bpy
import random

from . import conf

# -----------------------------------------------------------------------------
# GENERAL SUPPORTING FUNCTIONS
# -----------------------------------------------------------------------------

####
# strips out duplication ".001", ".002" from a name
# def nameGeneralize(name):

# 	# old way
# 	# nameList = name.split(".")
# 	# #check last item in list, to see if numeric type e.g. from .001
# 	# try:
# 	# 	x = int(nameList[-1])
# 	# 	name = nameList[0]
# 	# 	for a in nameList[1:-1]: name+='.'+a
# 	# except:
# 	# 	pass

# 	try:
# 		x = int(name[-3:])
# 		name = name[0:-4]
# 		return name
# 	except:
# 		if conf.vv:print("Error in name generalize, returning none:")
# 		if conf.vv:print(name)
# 		return None

# ---------
# Get base name from datablock
def nameGeneralize(name):
	if duplicatedDatablock(name) == True:
		return name[:-4]
	else:
		return name
	# old method
	# nameList = name.split(".")
	# #check last item in list, to see if numeric type e.g. from .001
	# try:
	# 	x = int(nameList[-1])
	# 	name = nameList[0]
	# 	for a in nameList[1:-1]: name+='.'+a
	# except:
	# 	pass
	# return name


# ---------
# gets all materials on input list of objects
def materialsFromObj(objList): # old name: getObjectMaterials
	matList = []
	#loop over every object, adding each material if not already added
	for obj in objList:
		if obj.dupli_group:
			for a in obj.dupli_group.objects:
				objList.append(a)
		if obj.type != 'MESH': continue
		objectsMaterials = obj.material_slots
		for materialID in objectsMaterials:
			if materialID.material not in matList:
				matList.append(materialID.material)
	return matList


# ---------
# gets all textures on input list of materials
# currently not used, some issue in getting NoneTypes (line if textureID.texture in..)
def texturesFromMaterials(matList): # original name: getMaterialTextures
	if len(matList)==0: return []
	texList = []
	for mat in matList:
		materialTextures = mat.texture_slots
		if len(materialTextures)==0: return []
		for textureID in materialTextures:
			if textureID.texture not in texList:
				texList.append(textureID.texture)
	return texList


# ---------
# For multiple version compatibility,
# this function generalized appending/linking
def bAppendLink(directory,name, toLink, active_layer=True):
	# blender post 2.71 changed to new append/link methods
	post272 = False
	try:
		version = bpy.data.version
		post272 = True
	except:
		pass #  "version" didn't exist before 72!
	#if (version[0] >= 2 and version[1] >= 72):
	if post272:
		# new method of importing

		# consider checking if "/" is at the end of the director,
		# add it if not

		if (toLink):
			bpy.ops.wm.link(directory=directory, filename=name)
		else:
			bpy.ops.wm.append(
					directory=directory,
					filename=name,
					active_layer=active_layer,
					) #, activelayer=True
			# if active_layer==True:

	else:
		# OLD method of importing
		bpy.ops.wm.link_append(directory=directory, filename=name, link=toLink)


# ---------
# check if a face is on the boundary between two blocks (local coordinates)
def onEdge(faceLoc):
	strLoc = [ str(faceLoc[0]).split('.')[1][0],
				str(faceLoc[1]).split('.')[1][0],
				str(faceLoc[2]).split('.')[1][0] ]
	if (strLoc[0] == '5' or strLoc[1] == '5' or strLoc[2] == '5'):
		return True
	else:
		return False


# ---------
# randomization for model imports, add extra statements for exta cases
def randomizeMeshSawp(swap,variations):
	randi=''
	if swap == 'torch':
		randomized = random.randint(0,variations-1)
		#print("## "+str(randomized))
		if randomized != 0: randi = ".{x}".format(x=randomized)
	elif swap == 'Torch':
		randomized = random.randint(0,variations-1)
		#print("## "+str(randomized))
		if randomized != 0: randi = ".{x}".format(x=randomized)
	return swap+randi


# ---------
# Check if datablock is a duplicate or not, e.g. ending in .00#
def duplicatedDatablock(name):
	try:
		if name[-4]!=".": return False
		int(name[-3:])
		return True
	except:
		return False


# ---------
# Load texture, reusing existing texture if present
def loadTexture(texture):

	# load the image only once
	base = bpy.path.basename(texture)
	# HERE load the iamge and set
	if base in bpy.data.images:
		if bpy.path.abspath(bpy.data.images[base].filepath) == bpy.path.abspath(texture):
			data_img = bpy.data.images[base]
			data_img.reload()
			if conf.v:print("Using already loaded texture")
		else:
			data_img = bpy.data.images.load(texture)
			if conf.v:print("Loading new texture image")
	else:
		data_img = bpy.data.images.load(texture)
		if conf.v:print("Loading new texture image")

	return data_img


# ---------
# Consistent, general way to remap datablock users
# todo: write equivalent function of user_remap for older blender versions
def remap_users(old, new):
	try:
		old.user_remap( new )
		return 0
	except:
		return "not available prior to blender 2.78"


# ---------
# quick script for linking all objects back into a scene
"""
import bpy

for ob in bpy.data.objects:
    if ob not in list(bpy.context.scene.objects):
        bpy.context.scene.objects.link(ob)
"""