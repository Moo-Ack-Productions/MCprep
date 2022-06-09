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
import platform
import random
import subprocess
from subprocess import Popen, PIPE
from attr import has
import functools

import bpy

from . import conf


# -----------------------------------------------------------------------------
# GENERAL SUPPORTING FUNCTIONS (no registration required)
# -----------------------------------------------------------------------------


def apply_colorspace(node, color_enum):
	"""Apply color space in a cross compatible way, for version and language.

	Use enum nomeclature matching Blender 2.8x Default, not 2.7 or other lang
	"""
	global noncolor_override
	noncolor_override = None

	if not node.image:
		conf.log("Node has no image applied yet, cannot change colorspace")

	# For later 2.8, fix images color space user
	if hasattr(node, "color_space"):  # 2.7 and earlier 2.8 versions
		node.color_space = 'NONE'  # for better interpretation of specmaps
	elif hasattr(node.image, "colorspace_settings"):  # later 2.8 versions
		# try default 'Non-color', fall back to best guess 'Non-Colour Data'
		if color_enum == 'Non-color' and noncolor_override is not None:
			node.image.colorspace_settings.name = noncolor_override
		else:
			try:
				node.image.colorspace_settings.name = 'Non-Color'
			except TypeError:
				node.image.colorspace_settings.name = 'Non-Colour Data'
				noncolor_override = 'Non-Colour Data'


def nameGeneralize(name):
	"""Get base name from datablock, accounts for duplicates and animated tex."""
	if duplicatedDatablock(name) is True:
		name = name[:-4]  # removes .001
	if name.endswith(".png"):
		name = name[:-4]

	# if name ends in _####, drop those numbers (for animated sequences)
	# noting it is specifically 4 numbers
	# could use regex, but some historical issues within including this lib
	# in certain blender builds
	nums = '0123456789'
	if len(name) < 5:
		return name
	any_nonnumbs = [1 if ltr in nums else 0 for ltr in name[-4:]]
	if sum(any_nonnumbs) == 4:  # all leters are numbers
		if name[-5] in ["-", "_", " "]:
			name = name[:-5]
		else:
			name = name[:-4]
	return name


def materialsFromObj(obj_list):
	"""Gets all materials on input list of objects.

	Loop over every object, adding each material if not already added
	"""
	mat_list = []
	for obj in obj_list:
		# also capture obj materials from dupliverts/instances on e.g. empties
		if hasattr(obj, "dupli_group") and obj.dupli_group:  # 2.7
			for dup_obj in obj.dupli_group.objects:
				if dup_obj not in obj_list:
					obj_list.append(dup_obj)
		elif hasattr(obj, "instance_collection") and obj.instance_collection:  # 2.8
			for dup_obj in obj.instance_collection.objects:
				if dup_obj not in obj_list:
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

	Arguments:
		directory: xyz.blend/Type, where Type is: Collection, Group, Material...
		name: asset name
		toLink: bool
	"""

	conf.log("Appending " + directory + " : " + name, vv_only=True)

	# for compatibility, add ending character
	if directory[-1] != "/" and directory[-1] != os.path.sep:
		directory += os.path.sep

	if "link_append" in dir(bpy.ops.wm):
		# OLD method of importing, e.g. in blender 2.70
		conf.log("Using old method of append/link, 2.72 <=", vv_only=True)
		bpy.ops.wm.link_append(directory=directory, filename=name, link=toLink)
	elif "link" in dir(bpy.ops.wm) and "append" in dir(bpy.ops.wm):
		conf.log("Using post-2.72 method of append/link", vv_only=True)
		if toLink:
			bpy.ops.wm.link(directory=directory, filename=name)
		elif bv28():
			bpy.ops.wm.append(
				directory=directory,
				filename=name)
		else:
			conf.log("{} {} {}".format(directory, name, active_layer))
			bpy.ops.wm.append(
				directory=directory,
				filename=name,
				active_layer=active_layer)


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
			properties = [
				p.identifier for p in mod_src.bl_rna.properties
				if not p.is_readonly]
			for prop in properties:
				setattr(dest, prop, getattr(mod_src, prop))
	return new_ob
        

@functools.cache
def getBV(major_version, minor_version):
	if hasattr(bpy.app, "version"):
		return True if bpy.app.version >= (major_version, minor_version) else False

@functools.cache
def bv28():
	"""Check if blender 2.8, for layouts, UI, and properties. """
	return getBV(2, 80)

@functools.cache
def bv30():
    """Check if we're dealing with Blender 3.0"""
    return getBV(3, 00)

@functools.cache
def get_cycles_version():
    return 2 if bv30() else 1

def face_on_edge(faceLoc):
	"""Check if a face is on the boundary between two blocks (local coordinates)."""
	face_decimals = [loc - loc // 1 for loc in faceLoc]
	if face_decimals[0] > 0.4999 and face_decimals[0] < 0.501:
		return True
	elif face_decimals[1] > 0.499 and face_decimals[1] < 0.501:
		return True
	elif face_decimals[2] > 0.499 and face_decimals[2] < 0.501:
		return True
	return False


def randomizeMeshSawp(swap, variations):
	"""Randomization for model imports, add extra statements for exta cases."""
	randi = ''
	if swap == 'torch':
		randomized = random.randint(0, variations - 1)
		if randomized != 0:
			randi = ".{x}".format(x=randomized)
	elif swap == 'Torch':
		randomized = random.randint(0, variations - 1)
		if randomized != 0:
			randi = ".{x}".format(x=randomized)
	return swap + randi


def duplicatedDatablock(name):
	"""Check if datablock is a duplicate or not, e.g. ending in .00# """
	try:
		if name[-4] != ".":
			return False
		int(name[-3:])  # Will force ValueError if not a number.
		return True
	except IndexError:
		return False
	except ValueError:
		return False


def loadTexture(texture):
	"""Load texture once, reusing existing texture if present."""
	base = nameGeneralize(bpy.path.basename(texture))
	if base in bpy.data.images:
		base_filepath = bpy.path.abspath(bpy.data.images[base].filepath)
		if base_filepath == bpy.path.abspath(texture):
			data_img = bpy.data.images[base]
			data_img.reload()
			conf.log("Using already loaded texture", vv_only=True)
		else:
			data_img = bpy.data.images.load(texture, check_existing=True)
			conf.log("Loading new texture image", vv_only=True)
	else:
		data_img = bpy.data.images.load(texture, check_existing=True)
		conf.log("Loading new texture image", vv_only=True)
	return data_img


def remap_users(old, new):
	"""Consistent, general way to remap datablock users."""
	# Todo: write equivalent function of user_remap for older blender versions
	try:
		old.user_remap(new)
		return 0
	except:
		return "not available prior to blender 2.78"


def get_objects_conext(context):
	"""Returns list of objects, either from view layer if 2.8 or scene if 2.8"""
	if bv28():
		return context.view_layer.objects
	return context.scene.objects


def link_selected_objects_to_scene():
	"""Quick script for linking all objects back into a scene.

	Not used by addon, but shortcut useful in one-off cases to copy/run code
	"""
	for ob in bpy.data.objects:
		if ob not in list(bpy.context.scene.objects):
			obj_link_scene(ob)


def open_program(executable):
	# Open an external program from filepath/executbale
	executable = bpy.path.abspath(executable)
	conf.log("Open program request: " + executable)

	# input could be .app file, which appears as if a folder
	if not os.path.isfile(executable):
		conf.log("File not executable")
		if not os.path.isdir(executable):
			return -1
		elif not executable.lower().endswith(".app"):
			return -1

	# try to open with wine, if available
	osx_or_linux = platform.system() == "Darwin"
	osx_or_linux = osx_or_linux or 'linux' in platform.system().lower()
	if executable.lower().endswith('.exe') and osx_or_linux:
		conf.log("Opening program via wine")
		p = Popen(['which', 'wine'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
		stdout, err = p.communicate(b"")
		has_wine = stdout and not err

		if has_wine:
			# wine is installed; this will hang blender until mineways closes.
			p = Popen(['wine', executable], stdin=PIPE, stdout=PIPE, stderr=PIPE)
			conf.log(
				"Opening via wine + direct executable, will hang blender till closed")

			# communicating with process makes it hang, so trust it works
			# stdout, err = p.communicate(b"")
			# for line in iter(p.stdout.readline, ''):
			# 	# will print lines as they come, instead of just at end
			# 	print(stdout)
			return 0

	try:  # attempt to use blender's built-in method
		res = bpy.ops.wm.path_open(filepath=executable)
		if res == {"FINISHED"}:
			conf.log("Opened using built in path opener")
			return 0
		else:
			conf.log("Did not get finished response: ", str(res))
	except:
		conf.log("failed to open using builtin mehtod")
		pass

	if platform.system() == "Darwin" and executable.lower().endswith(".app"):
		# for mac, if folder, check that it has .app otherwise throw -1
		# (right now says will open even if just folder!!)
		conf.log("Attempting to open .app via system Open")
		p = Popen(['open', executable], stdin=PIPE, stdout=PIPE, stderr=PIPE)
		stdout, err = p.communicate(b"")
		if err != b"":
			return "Error occured while trying to open executable: " + str(err)
	return "Failed to open executable"


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
		pass
	try:
		# mac... works on Yosemite minimally
		subprocess.call(["open", folder])
		return True
	except:
		pass
	try:
		# linux
		subprocess.call(["xdg-open", folder])
		return True
	except:
		return False


def addGroupInstance(group_name, loc, select=True):
	"""Add object instance not working, so workaround function."""
	# The built in method fails, bpy.ops.object.group_instance_add(...)
	# UPDATE: I reported the bug, and they fixed it nearly instantly =D
	# but it was recommended to do the below anyways.

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
		"blocks": {
			"reflective": [],
			"water": [],
			"solid": [],
			"emit": [],
			"desaturated": [],
			"animated": [],
			"block_mapping_mc": {},
			"block_mapping_jmc": {},
			"block_mapping_mineways": {},
			"canon_mapping_block": {}
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
		return prefs.system.dpi / 72
	else:
		return 1


def uv_select(obj, action='TOGGLE'):
	"""Direct way to select all UV verts of an object, assumings 1 uv layer.

	Actions are: SELECT, DESELECT, TOGGLE.
	"""
	if not obj.data.uv_layers.active:
		return  # consider raising error
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


def move_to_collection(obj, collection):
	"""Move out of all collections and into this specified one. 2.8 only"""
	for col in obj.users_collection:
		col.objects.unlink(obj)
	collection.objects.link(obj)


def get_or_create_viewlayer(context, collection_name):
	"""Returns or creates the view layer for a given name. 2.8 only.

	Only searches within same viewlayer; not exact match but a non-case
	sensitive contains-text of collection_name check. If the collection exists
	elsewhere by name, ignore (could be used for something else) and generate
	a new one; maye cause any existing collection to be renamed, but is still
	left unaffected in whatever view layer it exists.
	"""
	master_vl = context.view_layer.layer_collection
	response_vl = None
	for child in master_vl.children:
		if collection_name.lower() not in child.name.lower():
			continue
		response_vl = child
		break
	if response_vl is None:
		new_coll = bpy.data.collections.new(collection_name)
		context.scene.collection.children.link(new_coll)

		# assumes added to scene's active view layer root via link above
		response_vl = master_vl.children[new_coll.name]
	return response_vl


# -----------------------------------------------------------------------------
# Cross blender 2.7 and 2.8 functions
# -----------------------------------------------------------------------------


def make_annotations(cls):
	"""Add annotation attribute to class fields to avoid Blender 2.8 warnings"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return cls
	if bpy.app.version < (2, 93, 0):
		bl_props = {
			k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
	else:
		bl_props = {
			k: v for k, v in cls.__dict__.items()
			if isinstance(v, bpy.props._PropertyDeferred)}
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
		context.view_layer.objects.active = obj  # the 2.8 way
	else:
		context.scene.objects.active = obj  # the 2.7 way


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
		obj.hide_viewport = state  # where state is a boolean True or False
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

	if hasattr(context.space_data, "show_textured_solid"):  # 2.7
		return context.space_data.show_textured_solid
	elif hasattr(context.scene, "display"):  # 2.8
		# makes textured if any
		return context.scene.display.shading.color_type == "TEXTURE"
	return None  # unsure


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
	if hasattr(context.scene, "cursor_location"):  # 2.7
		context.scene.cursor_location = loc
	else:
		context.scene.cursor.location = loc


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
			pass  # if not in master collection
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
	"""Multiplciation of matrix and/or vectors in cross compatible way.

	This is a workaround for the syntax that otherwise could be used a @ b.
	"""
	if bv28():
		# does not exist pre 2.7<#?>, syntax error
		mtm = getattr(operator, "matmul")
		if v3:
			return mtm(v1, mtm(v2, v3))
		return mtm(v1, v2)
	if v3:
		return v1 * v2 * v3
	return v1 * v2


def scene_update(context=None):
	"""Update scene in cross compatible way, to update desp graph"""
	if not context:
		context = bpy.context
	if hasattr(context.scene, "update"):  # 2.7
		context.scene.update()
	elif hasattr(context, "view_layer"):  # 2.8
		context.view_layer.update()


def move_assets_to_excluded_layer(context, collections):
	"""Utility to move source collections to excluded layer to not be rendered"""
	initial_view_coll = context.view_layer.active_layer_collection

	# Then, setup the exclude view layer
	spawner_exclude_vl = get_or_create_viewlayer(
		context, "Spawner Exclude")
	spawner_exclude_vl.exclude = True

	for grp in collections:
		if grp.name not in initial_view_coll.collection.children:
			continue  # not linked, likely a sub-group not added to scn
		spawner_exclude_vl.collection.children.link(grp)
		initial_view_coll.collection.children.unlink(grp)
