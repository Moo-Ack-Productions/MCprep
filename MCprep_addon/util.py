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

import json
import operator
import os
import random
import subprocess
from subprocess import Popen, PIPE

import bpy

from . import conf

# -----------------------------------------------------------------------------
# GENERAL SUPPORTING FUNCTIONS (no registration required)
# -----------------------------------------------------------------------------


def nameGeneralize(name):
	"""Get base name from datablock, accounts for duplicates and animated tex."""
	if duplicatedDatablock(name) == True:
		name = name[:-4] # removes .001 or .png

	# if name ends in _####, drop those numbers (for animated sequences)
		"""Return the index of the image name, number of digits at filename end."""
	ind = 0
	nums = '0123456789'
	for i in range(len(name)):
		if not name[-i-1] in nums:
			break
		ind += 1
	if ind > 0:
		if name[-ind] in ["-", "_", " "]:
			name = name[:-ind-1]
		else:
			name = name[:-ind]
	return name


def materialsFromObj(obj_list):
	"""Gets all materials on input list of objects.

	Loop over every object, adding each material if not already added
	"""

	mat_list = []
	for obj in obj_list:
		# also capture obj materials from dupliverts/instances on e.g. empties
		if hasattr(obj, "dupli_group") and obj.dupli_group: # 2.7
			for dup_obj in obj.dupli_group.objects:
				obj_list.append(dup_obj)
		elif hasattr(obj, "instance_collection") and obj.instance_collection: # 2.8
			for dup_obj in obj.instance_collection.objects:
				obj_list.append(dup_obj)
		if obj.type != 'MESH':
			continue
		for slot in obj.material_slots:
			if slot.material is not None and slot.material not in mat_list:
				mat_list.append(slot.material)
	return mat_list


def bAppendLink(directory, name, toLink, active_layer=True):
	"""For multiple version compatibility, this function generalized
	appending/linking blender post 2.71 changed to new append/link methods

	Note that for 2.8 compatibility, the directory passed in should
	already be correctly identified (eg Group or Collection)
	"""

	conf.log("Appending " + directory + " : " + name, vv_only=True)
	post272 = False
	post280 = False
	try:
		version = bpy.app.version
		post272 = True
		post280 = bv28()
	except:
		pass #  "version" didn't exist before 72!
	#if (version[0] >= 2 and version[1] >= 72):

	# for compatibility, add ending character
	if directory[-1] != "/" and directory[-1] != os.path.sep:
		directory += os.path.sep

	if post272:
		conf.log("Using post-2.72 method of append/link", vv_only=True)
		# new method of importing

		if toLink:
			bpy.ops.wm.link(directory=directory, filename=name)
		elif post280 is True:
			bpy.ops.wm.append(
					directory=directory,
					filename=name
					)
		else:
			conf.log("{} {} {}".format(directory, name, active_layer))
			bpy.ops.wm.append(
					directory=directory,
					filename=name,
					active_layer=active_layer
					) #, activelayer=True
	else:
		# OLD method of importing
		conf.log("Using old method of append/link, 2.72 <=", vv_only=True)
		bpy.ops.wm.link_append(directory=directory, filename=name, link=toLink)


def obj_copy(base, context=None, vertex_groups=True, modifiers=True):
	"""Copy an object's data, vertex groups, and modifiers without operators.

	Input must be a valid object in bpy.data.objects
	"""
	if not base or base.name not in bpy.data.objects:
		raise Exception("Invalid object passed")
	if not context:
		context = bpy.context

	new_ob = bpy.data.objects.new(base.name, base.data.copy())
	obj_link_scene(new_ob, context)

	if vertex_groups:
		verts = len(base.data.vertices)
		for vgroup in base.vertex_groups:
			print("Running vertex group: ", vgroup.name)
			new_g = new_ob.vertex_groups.new(name=vgroup.name)
			for i in range(0, verts):
				try:
					new_g.add([i], vgroup.weight(i), "REPLACE")
				except:
					pass  # no way to check if a given vertex is part of src group

	if modifiers:
		for mod_src in base.modifiers:
			dest = new_ob.modifiers.get(mod_src.name, None)
			if not dest:
				dest = new_ob.modifiers.new(mod_src.name, mod_src.type)
			properties = [p.identifier for p in mod_src.bl_rna.properties
					  if not p.is_readonly]
			for prop in properties:
				setattr(dest, prop, getattr(mod_src, prop))
	return new_ob


BV_IS_28 = None  # global initialization
def bv28():
	"""Check if blender 2.8, for layouts, UI, and properties. """
	global BV_IS_28
	if not BV_IS_28:
		BV_IS_28 = hasattr(bpy.app, "version") and bpy.app.version >= (2, 80)
	return BV_IS_28


def onEdge(faceLoc):
	"""Check if a face is on the boundary between two blocks (local coordinates)."""
	strLoc = [ str(faceLoc[0]).split('.')[1][0],
				str(faceLoc[1]).split('.')[1][0],
				str(faceLoc[2]).split('.')[1][0] ]
	if (strLoc[0] == '5' or strLoc[1] == '5' or strLoc[2] == '5'):
		return True
	else:
		return False


def randomizeMeshSawp(swap,variations):
	"""Randomization for model imports, add extra statements for exta cases."""
	randi=''
	if swap == 'torch':
		randomized = random.randint(0,variations-1)
		if randomized != 0:
			randi = ".{x}".format(x=randomized)
	elif swap == 'Torch':
		randomized = random.randint(0,variations-1)
		if randomized != 0: randi = ".{x}".format(x=randomized)
	return swap+randi


def duplicatedDatablock(name):
	"""Check if datablock is a duplicate or not, e.g. ending in .00# """
	try:
		if name[-4]!=".": return False
		int(name[-3:])
		return True
	except:
		return False


def loadTexture(texture):
	"""Load texture once, reusing existing texture if present."""

	base = nameGeneralize(bpy.path.basename(texture))
	if base in bpy.data.images:
		if bpy.path.abspath(bpy.data.images[base].filepath) == bpy.path.abspath(texture):
			data_img = bpy.data.images[base]
			data_img.reload()
			conf.log("Using already loaded texture", vv_only=True)
		else:
			data_img = bpy.data.images.load(texture)
			conf.log("Loading new texture image", vv_only=True)
	else:
		data_img = bpy.data.images.load(texture)
		conf.log("Loading new texture image", vv_only=True)
	return data_img


def remap_users(old, new):
	"""Consistent, general way to remap datablock users."""
	# Todo: write equivalent function of user_remap for older blender versions
	try:
		old.user_remap( new )
		return 0
	except:
		return "not available prior to blender 2.78"


def link_selected_objects_to_scene():
	# Quick script for linking all objects back into a scene
	# Not used by addon, but shortcut useful in one-off cases to copy/run code
	for ob in bpy.data.objects:
		if ob not in list(bpy.context.scene.objects):
			obj_link_scene(ob)


def open_program(executable):
	# Open an external program from filepath/executbale
	executable = bpy.path.abspath(executable)
	if (os.path.isfile(executable) == False):
		if (os.path.isdir(executable) == False):
			return -1
		elif ".app" not in executable:
			return -1

	try:  # first attempt to use blender's built-in method
		res = bpy.ops.wm.path_open(filepath=executable)
		if res == {"FINISHED"}:
			return 0
	except:
		pass

	# for mac, if folder, check that it has .app otherwise throw -1
	# (right now says will open even if just folder!!)

	p = Popen(['open',executable], stdin=PIPE, stdout=PIPE, stderr=PIPE)
	stdout, err = p.communicate(b"")

	if err != b"":
		return "Error occured while trying to open Sync: "+str(err)

	return 0


def open_folder_crossplatform(folder):
	"""Cross platform way to open folder in host operating system."""

	folder = bpy.path.abspath(folder)
	if not os.path.isdir(folder):
		return False

	try:  # first attempt to use blender's built-in method
		res = bpy.ops.wm.path_open(filepath=folder)
		if res == {"FINISHED"}:
			return True
	except:
		pass

	try:
		# windows... untested
		subprocess.Popen('explorer "{x}"'.format(x=folder))
		return True
	except:
		try:
			# mac... works on Yosemite minimally
			subprocess.call(["open", folder])
			return True
		except:
			# linux
			try:
				subprocess.call(["xdg-open", folder])
				return True
			except:
				return False


def exec_path_expand(self, context):
	"""Fix/update the mineways path for any oddities"""

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


def addGroupInstance(group_name, loc, select=True):
	"""Add object instance not working, so workaround function."""
	scene = bpy.context.scene
	ob = bpy.data.objects.new(group_name, None)
	if bv28():
		ob.instance_type = 'COLLECTION'
		ob.instance_collection = collections().get(group_name)
		scene.collection.objects.link(ob)  # links to scene collection
	else:
		ob.dupli_type = 'GROUP'
		ob.dupli_group = collections().get(group_name)
		scene.objects.link(ob)
	ob.location = loc
	select_set(ob, select)
	return ob


def load_mcprep_json():
	"""Load in the json file, defered so not at addon enable time."""
	path = conf.json_path
	default = {
		"blocks":{
			"reflective":[],
			"water":[],
			"solid":[],
			"emit":[],
			"desaturated":[],
			"animated":[],
			"block_mapping_mc":{},
			"block_mapping_jmc":{},
			"block_mapping_mineways":{}
		}
	}
	if not os.path.isfile(path):
		conf.log("Error, json file does not exist: " + path)
		conf.json_data = default
		return False
	with open(path) as data_file:
		try:
			conf.json_data = json.load(data_file)
			conf.log("Successfully read the JSON file")
			return True
		except Exception as err:
			print("Failed to load json file:")
			print('\t', err)
			conf.json_data = default

def ui_scale():
	"""Returns scale of UI, for width drawing. Compatible down to blender 2.72"""
	prefs = get_preferences()
	if not hasattr(prefs, "view"):
		return 1
	elif hasattr(prefs.view, "ui_scale") and hasattr(prefs.view, "pixel_size"):
		return prefs.view.ui_scale * prefs.system.pixel_size
	elif hasattr(prefs.system, "dpi"):
		return prefs.system.dpi/72
	else:
		return 1


class event_stream():
	"""Class for reuse in streaming modals

	or instead of this, a class which keeps record of inputs and interprets
	the state output as per blender norm, e.g. transformmodal(3d=False) keeps stream
	of the transform operations and options, ignoring the rest, including interpreting
	of toggles of axis etc. stream output in standard way, e.g. [val, mods]
	Examples of transform stream:
	-/2x becomes [-0.5, 'x']
	-/2x/ becomes [-2, 'x']
	but! it shouldn't just append the string... that could become memory leak...
	it should save the STATE of the stream at any given moment internally
	should it should be an instance of a class variable, with functions on that class
	shared
	"""

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

	def __init__(self):
		"""Object initialization"""
		self.x=False
		self.y=False
		self.z=False
		self.neg=None # can have negative modified without specifying value
		self.value=None # if None, then no value initially set
		self.valuestr=None # not sure if needed, but keep value as string for padding

	def stream_transform(self, val,two_dim=False):
		"""Streaming functions"""
		# interpret val, and update state
		if val in self.neg_vals:
			# if not yet initialized for use, set to True, else toggle
			self.neg = True if self.neg == None else not self.neg
		# elif val in ...

	def getKeyval(self, event):
		"""Key evaluations for modal"""
		if event.type in self.nums:
			return ["INTEGER", self.nums_eval[self.nums.index(event.type)]]
		elif event.type in self.neg:
			return ["NEGATIVE",""]
		elif event.type == "X":
			return ["X",""]


def uv_select(obj, action='TOGGLE'):
	"""Direct way to select all UV verts of an object, assumings 1 uv layer.

	Actions are: SELECT, DESELECT, TOGGLE.
	"""
	if not obj.data.uv_layers.active:
		return# consider raising error
	uv_layer = obj.data.uv_layers.active
	if action == 'TOGGLE':
		for face in obj.data.polygons:
			face.select = not face.select
	elif action == 'SELECT':
		for face in obj.data.polygons:
			# if len(face.loop_indices) < 3:
			# 	continue
			face.select = True
	elif action == 'DESELECT':
		for face in obj.data.polygons:
			# if len(face.loop_indices) < 3:
			# 	continue
			face.select = False


# -----------------------------------------------------------------------------
# Cross blender 2.7 and 2.8 functions
# -----------------------------------------------------------------------------


def make_annotations(cls):
	"""Add annotation attribute to class fields to avoid Blender 2.8 warnings"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return cls
	bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
	if bl_props:
		if '__annotations__' not in cls.__dict__:
			setattr(cls, '__annotations__', {})
		annotations = cls.__dict__['__annotations__']
		for k, v in bl_props.items():
			annotations[k] = v
			delattr(cls, k)
	return cls


def layout_split(layout, factor=0.0, align=False):
	"""Intermediate method for pre and post blender 2.8 split UI function"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return layout.split(percentage=factor, align=align)
	return layout.split(factor=factor, align=align)


def get_user_preferences(context=None):
	"""Intermediate method for pre and post blender 2.8 grabbing preferences"""
	if not context:
		context = bpy.context
	prefs = None
	if hasattr(context, "user_preferences"):
		prefs = context.user_preferences.addons.get(__package__, None)
	elif hasattr(context, "preferences"):
		prefs = context.preferences.addons.get(__package__, None)
	if prefs:
		return prefs.preferences
	# To make the addon stable and non-exception prone, return None
	# raise Exception("Could not fetch user preferences")
	return None


def get_preferences(context=None):
	"""Function to easily get general user prefs in 2.7 and 2.8 friendly way"""
	if hasattr(context, "user_preferences"):
		return context.user_preferences
	elif hasattr(context, "preferences"):
		return context.preferences
	return None


def set_active_object(context, obj):
	"""Get the active object in a 2.7 and 2.8 compatible way"""
	if hasattr(context, "view_layer"):
		context.view_layer.objects.active = obj # the 2.8 way
	else:
		context.scene.objects.active = obj # the 2.7 way


def select_get(obj):
	"""Multi version compatibility for getting object selection"""
	if hasattr(obj, "select_get"):
		return obj.select_get()
	else:
		return obj.select


def select_set(obj, state):
	"""Multi version compatibility for setting object selection"""
	if hasattr(obj, "select_set"):
		obj.select_set(state)
	else:
		obj.select = state


def hide_viewport(obj, state):
	"""Multi version compatibility for setting the viewport hide state"""
	if hasattr(obj, "hide_viewport"):
		obj.hide_viewport = state # where state is a boolean True or False
	else:
		obj.hide = state


def collections():
	"""Returns group or collection object for 2.7 and 2.8"""
	if hasattr(bpy.data, "collections"):
		return bpy.data.collections
	else:
		return bpy.data.groups


def viewport_textured(context=None):
	"""Returns state of viewport solid being textured or not"""
	if not context:
		context = bpy.context

	if hasattr(context.space_data, "show_textured_solid"): # 2.7
		return context.space_data.show_textured_solid
	elif hasattr(context.scene, "display"): # 2.8
		# makes textured if any
		return context.scene.display.shading.color_type == "TEXTURE"
	return None # unsure


def get_cuser_location(context=None):
	"""Returns the location vector of the 3D cursor"""
	if not context:
		context = bpy.context
	if hasattr(context.scene, "cursor_location"):
		return context.scene.cursor_location
	elif hasattr(context.scene, "cursor") and hasattr(context.scene.cursor, "location"):
		return context.scene.cursor.location  # later 2.8 builds
	elif hasattr(context.space_data, "cursor_location"):
		return context.space_data.cursor_location
	elif hasattr(context.space_data, "cursor") and hasattr(context.space_data.cursor, "location"):
		return context.space_data.cursor.location
	print("MCPREP WARNING! Unable to get cursor location, using (0,0,0)")
	return (0, 0, 0)


def set_cuser_location(loc, context=None):
	"""Returns the location vector of the 3D cursor"""
	if not context:
		context = bpy.context
	if hasattr(context.scene, "cursor_location"):
		context.scene.cursor_location = loc
	else:
		context.space_data.cursor_location = loc


def instance_collection(obj):
	"""Cross compatible way to get an objects dupligroup or collection"""
	if hasattr(obj, "dupli_group"):
		return obj.dupli_group
	elif hasattr(obj, "instance_collection"):
		return obj.instance_collection


def obj_link_scene(obj, context=None):
	"""Links object to scene, or for 2.8, the scene master collection"""
	if not context:
		context = bpy.context
	if hasattr(context.scene.objects, "link"):
		context.scene.objects.link(obj)
	elif hasattr(context.scene, "collection"):
		context.scene.collection.objects.link(obj)
	# context.scene.update() # needed?


def obj_unlink_remove(obj, remove, context=None):
	"""Unlink an object from the scene, and remove from data if specified"""
	if not context:
		context = bpy.context
	if hasattr(context.scene.objects, "unlink"):  # 2.7
		context.scene.objects.unlink(obj)
	elif hasattr(context.scene, "collection"):  # 2.8
		try:
			context.scene.collection.objects.unlink(obj)
		except RuntimeError:
			pass # if not in master collection
		colls = list(obj.users_collection)
		for coll in colls:
			coll.objects.unlink(obj)
	if remove is True:
		obj.user_clear()
		bpy.data.objects.remove(obj)


def users_collection(obj):
	"""Returns the collections/group of an object"""
	if hasattr(obj, "users_collection"):
		return obj.users_collection
	elif hasattr(obj, "users_group"):
		return obj.users_group


def matmul(v1, v2, v3=None):
	"""Multiplciation of matrix and/or vectors in cross compatible way"""
	if bv28():
		mtm = getattr(operator, "matmul") # does not exist pre 2.7<#?>, syntax error
		if v3:
			return mtm(v1, mtm(v2, v3))
		return mtm(v1, v2)
	if v3:
		return v1 * v2 * v3
	return v1 * v2
