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

import bpy
import random
import os

from subprocess import Popen, PIPE, call

from . import conf

# -----------------------------------------------------------------------------
# GENERAL SUPPORTING FUNCTIONS (no registration required)
# -----------------------------------------------------------------------------

# ---------
# Get base name from datablock
def nameGeneralize(name):
	if duplicatedDatablock(name) == True:
		return name[:-4]
	else:
		return name


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
		version = bpy.app.version
		post272 = True
		post280 = bpy.app.version >= (2, 80)
	except:
		pass #  "version" didn't exist before 72!
	#if (version[0] >= 2 and version[1] >= 72):

	print("DEBUG 2.8 loader",version, post272, post280)

	# for compatibility, add ending character
	if directory[-1] != "/" and directory[-1] != os.path.sep:
		directory += os.path.sep

	if post272:
		if conf.vv:print("Using post-2.72 method of append/link")
		# new method of importing

		if toLink:
			bpy.ops.wm.link(directory=directory, filename=name)
		elif post280==True:
			bpy.ops.wm.append(
					directory=directory,
					filename=name,
					)
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
# cross platform way to open folder in host operating system
def open_folder_crossplatform(folder):
	folder = bpy.path.abspath(folder)
	if not os.path.isdir(folder):
		return False
	try:
		# windows... untested
		subprocess.Popen('explorer "{x}"'.format(x=folder))
		#return True
	except:
		try:
			# mac... works on Yosemite minimally
			subprocess.call(["open", folder])
			#return True
		except:
			# linux
			try:
				subprocess.call(["xdg-open", folder])
				#return True
			except:
				return False


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
	scene.objects.link(ob)
	ob.location = loc
	ob.select = True
	return ob


# ---------
# or instead of this, a class which keeps record of inputs and interprets
# the state output as per blender norm, e.g. transformmodal(3d=False) keeps stream
# of the transform operations and options, ignoring the rest, including interpreting
# of toggles of axis etc. stream output in standard way, e.g. [val, mods]
# Examples of transform stream:
# -/2x becomes [-0.5, 'x']
# -/2x/ becomes [-2, 'x']
# but! it shouldn't just append the string... that could become memory leak...
# it should save the STATE of the stream at any given moment internally
# should it should be an instance of a class variable, with functions on that class
# shared
class event_stream(): #class event_stream(Object)

	# global event vars
	nums = ['NUMPAD_0','zero',
			'NUMPAD_1','one',
			'NUMPAD_2','two',
			'NUMPAD_3','three',
			'NUMPAD_4','four',
			'NUMPAD_5','five',
			'NUMPAD_6','six',
			'NUMPAD_7','seven',
			'NUMPAD_8','eight',
			'NUMPAD_9','nine',
		]
	nums_eval = [0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9]

	# text = []
	neg_vals = ['MINUS','NUMPAD_MINUS']

	# modifiers
	mods = ['shift?','alt?','ctrl?','OSKEY',"etc....."]

	# initializations
	def __init__(self):
		self.x=False
		self.y=False
		self.z=False
		self.neg=None # can have negative modified without specifying value
		self.value=None # if None, then no value initially set
		self.valuestr=None # not sure if needed, but keep value as string for padding

	# streaming functions
	def stream_transform(val,two_dim=False):
		# interpret val, and update state
		if val in neg_vals:
			# if not yet initialized for use, set to True, else toggle
			self.neg = True if self.neg == None else not self.neg
		# elif val in ...

	def getKeyval(event):

		if event.type in nums:
			return ["INTEGER",nums_eval[nums.index(event.type)]]
		elif event.type in neg:
			return ["NEGATIVE",""]
		elif event.type == "X":
			return ["X",""]


