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
import os

from subprocess import Popen, PIPE

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

	if conf.vv:print("Appending ",directory," : ",name)
	post272 = False
	try:
		version = bpy.data.version
		post272 = True
	except:
		pass #  "version" didn't exist before 72!
	#if (version[0] >= 2 and version[1] >= 72):

	# for compatibility, add ending character
	if directory[-1] != "/" and directory[-1] != os.path.sep:
		directory += os.path.sep

	if post272:
		if conf.vv:print("Using post-2.72 method of append/link")
		# new method of importing

		

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
		if conf.vv:print("Using old method of append/link, 2.72 <=")
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

# ---------
# Open an external program from filepath/executbale
def open_program(executable):

	if (os.path.isfile(executable) == False):
		if (os.path.isdir(executable) == False):
			return -1
		elif ".app" not in executable:
			return -1
		

	# for mac, if folder, check that it has .app otherwise throw -1
	# (right now says will open even if just folder!!)


	p = Popen(['open',executable], stdin=PIPE, stdout=PIPE, stderr=PIPE)
	stdout, err = p.communicate(b"")

	if err != b"":
		return "Error occured while trying to open Sync: "+str(err) 

	# print("stdout?")
	# print(stdout)

	return 0

# ---------
# fix/update the mineways path for any oddities
def exec_path_expand(self, context):
	# code may trigger twice
	path = self.open_mineways_path

	# # if not .app, assume valid found
	# if ".	app" not in path: return
	
	# dirs = path.split(os.path.sep)
	# for d in dirs:

		# # if Contents in x, os.path.join(x,"Contents")
		# path = os.path.join(path, "Contents")
		# if "MacOS" not in [listdirs]: return # failed?
		# path = os.path.join(path, "MacOS")
		# if "startwine" not in [listdirs]: return # failed?
		# path = os.path.join(path, "startwine")

		# >> end command SHOULD be open Mineways.app.



# ---------
# add object instance not working, so workaround function:
def addGroupInstance(groupName,loc):
	scene = bpy.context.scene
	ob = bpy.data.objects.new(groupName, None)
	ob.dupli_type = 'GROUP'
	ob.dupli_group = bpy.data.groups.get(groupName) #.. why not more directly?
	ob.location = loc
	scene.objects.link(ob)
	ob.select = True
	# why not return the instance object??