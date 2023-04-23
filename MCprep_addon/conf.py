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

import os

import bpy

# check if custom preview icons available
try:
	import bpy.utils.previews
except:
	print("MCprep: No custom icons in this blender instance")
	pass

# -----------------------------------------------------------------------------
# ADDON GLOBAL VARIABLES AND INITIAL SETTINGS
# -----------------------------------------------------------------------------

class MCprepEnv:
	def __init__(self):	
		self.data = None
		self.json_data = None
		self.json_path = os.path.join(
						os.path.dirname(__file__),
						"MCprep_resources",
						"mcprep_data.json")

		self.dev_file = os.path.join(
						os.path.dirname(__file__),
						"mcprep_dev.txt")

		self.json_path_update = os.path.join(
							os.path.dirname(__file__),
							"MCprep_resources",
							"mcprep_data_update.json")

		# if new update file found from install, replace old one with new
		if os.path.isfile(self.json_path_update):
			if os.path.isfile(self.json_path) is True:
				os.remove(self.json_path)
			os.rename(self.json_path_update, self.json_path)
		
		# Check to see if there's a text file for a dev build. If so,
		if os.path.isfile(self.dev_file):
			self.dev_build = True
			self.verbose = True
			self.very_verbose = True

		else:
			self.dev_build = False
			self.verbose = False
			self.very_verbose = False

		# lazy load json, ie only load it when needed (util function defined)

		# -----------------------------------------------
		# For preview icons
		# -----------------------------------------------

		self.use_icons = True
		self.preview_collections = {}

		# -----------------------------------------------
		# For initializing the custom icons
		# -----------------------------------------------
		self.icons_init()

		# -----------------------------------------------
		# For cross-addon lists
		# -----------------------------------------------

		# To ensure shift-A starts drawing sub menus after pressing load all spawns
		# as without this, if any one of the spawners loads nothing (invalid folder,
		# no blend files etc), then it would continue to ask to reload spanwers.
		self.loaded_all_spawners = False

		self.skin_list = []  # each is: [ basename, path ]
		self.rig_categories = []  # simple list of directory names
		self.entity_list = []

		# -----------------------------------------------
		# Matieral sync cahce, to avoid repeat lib reads
		# -----------------------------------------------

		# list of material names, each is a string. None by default to indicate
		# that no reading has occurred. If lib not found, will update to [].
		# If ever changing the resource pack, should also reset to None.
		self.material_sync_cache = None

	# -----------------------------------------------------------------------------
	# ICONS INIT
	# -----------------------------------------------------------------------------


	def icons_init(self):
		# start with custom icons
		# put into a try statement in case older blender version!
		global preview_collections

		collection_sets = [
			"main", "skins", "mobs", "entities", "blocks", "items", "effects", "materials"]

		try:
			for iconset in collection_sets:
				preview_collections[iconset] = bpy.utils.previews.new()

			script_path = bpy.path.abspath(os.path.dirname(__file__))
			icons_dir = os.path.join(script_path, 'icons')
			self.preview_collections["main"].load(
				"crafting_icon",
				os.path.join(icons_dir, "crafting_icon.png"),
				'IMAGE')
			self.preview_collections["main"].load(
				"meshswap_icon",
				os.path.join(icons_dir, "meshswap_icon.png"),
				'IMAGE')
			self.preview_collections["main"].load(
				"spawner_icon",
				os.path.join(icons_dir, "spawner_icon.png"),
				'IMAGE')
			self.preview_collections["main"].load(
				"sword_icon",
				os.path.join(icons_dir, "sword_icon.png"),
				'IMAGE')
			self.preview_collections["main"].load(
				"effects_icon",
				os.path.join(icons_dir, "effects_icon.png"),
				'IMAGE')
			self.preview_collections["main"].load(
				"entity_icon",
				os.path.join(icons_dir, "entity_icon.png"),
				'IMAGE')
			self.preview_collections["main"].load(
				"model_icon",
				os.path.join(icons_dir, "model_icon.png"),
				'IMAGE')
		except Exception as e:
			self.log("Old verison of blender, no custom icons available")
			self.log("\t" + str(e))
			global use_icons
			self.use_icons = False
			for iconset in collection_sets:
				self.preview_collections[iconset] = ""
    
	def log(self, statement, vv_only=False):
		if self.verbose and vv_only and self.very_verbose:
			print(statement)
		elif self.verbose:
			print(statement)

	def deprecation_warning(self):
		if self.dev_build:
			import traceback
			self.log("Deprecation Warning: This will be removed in MCprep 3.5.1!")
			traceback.print_stack()

env = MCprepEnv()

# ! Deprecated as of MCprep 3.4.2
def init():
	env.deprecation_warning()
	# -----------------------------------------------
	# Verbose, use as env.verbose
	# Used to print out extra information, set false with distribution
	# -----------------------------------------------
	# ! Deprecated as of MCprep 3.4.2
	global dev
	dev = True

	# ! Deprecated as of MCprep 3.4.2
	global v
	v = True  # $VERBOSE, UI setting

	# ! Deprecated as of MCprep 3.4.2
	global vv
	vv = dev  # $VERYVERBOSE

	# -----------------------------------------------
	# JSON attributes
	# -----------------------------------------------

	# shouldn't load here, just globalize any json data?

	# ! Deprecated as of MCprep 3.4.2
	global data
	# import json

	# ! Deprecated as of MCprep 3.4.2
	global json_data  # mcprep_data.json
	json_data = None  # later will load addon information etc

	# if existing json_data_update exists, overwrite it
	# ! Deprecated as of MCprep 3.4.2
	global json_path
	json_path = os.path.join(
		os.path.dirname(__file__),
		"MCprep_resources",
		"mcprep_data.json")
	json_path_update = os.path.join(
		os.path.dirname(__file__),
		"MCprep_resources",
		"mcprep_data_update.json")

	# if new update file found from install, replace old one with new
	if os.path.isfile(json_path_update):
		if os.path.isfile(json_path) is True:
			os.remove(json_path)
		os.rename(json_path_update, json_path)

	# lazy load json, ie only load it when needed (util function defined)

	# -----------------------------------------------
	# For preview icons
	# -----------------------------------------------

	# ! Deprecated as of MCprep 3.4.2
	global use_icons
	use_icons = True
	# ! Deprecated as of MCprep 3.4.2
	global preview_collections
	preview_collections = {}

	# -----------------------------------------------
	# For initializing the custom icons
	# -----------------------------------------------
	icons_init()

	# -----------------------------------------------
	# For cross-addon lists
	# -----------------------------------------------

	# To ensure shift-A starts drawing sub menus after pressing load all spawns
	# as without this, if any one of the spawners loads nothing (invalid folder,
	# no blend files etc), then it would continue to ask to reload spanwers.
	# ! Deprecated as of MCprep 3.4.2
	global loaded_all_spawners
	loaded_all_spawners = False

	# ! Deprecated as of MCprep 3.4.2
	global skin_list
	skin_list = []  # each is: [ basename, path ]

	# ! Deprecated as of MCprep 3.4.2
	global rig_categories
	rig_categories = []  # simple list of directory names

	# ! Deprecated as of MCprep 3.4.2
	global entity_list
	entity_list = []

	# -----------------------------------------------
	# Matieral sync cahce, to avoid repeat lib reads
	# -----------------------------------------------

	# list of material names, each is a string. None by default to indicate
	# that no reading has occurred. If lib not found, will update to [].
	# If ever changing the resource pack, should also reset to None.
	# ! Deprecated as of MCprep 3.4.2
	global material_sync_cache
	material_sync_cache = None


# ! Deprecated as of MCprep 3.4.2
# -----------------------------------------------------------------------------
# ICONS INIT
# -----------------------------------------------------------------------------

def icons_init():
	env.deprecation_warning()
	# start with custom icons
	# put into a try statement in case older blender version!
	global preview_collections
	global v

	collection_sets = [
		"main", "skins", "mobs", "entities", "blocks", "items", "effects", "materials"]

	try:
		for iconset in collection_sets:
			preview_collections[iconset] = bpy.utils.previews.new()

		script_path = bpy.path.abspath(os.path.dirname(__file__))
		icons_dir = os.path.join(script_path, 'icons')
		preview_collections["main"].load(
			"crafting_icon",
			os.path.join(icons_dir, "crafting_icon.png"),
			'IMAGE')
		preview_collections["main"].load(
			"meshswap_icon",
			os.path.join(icons_dir, "meshswap_icon.png"),
			'IMAGE')
		preview_collections["main"].load(
			"spawner_icon",
			os.path.join(icons_dir, "spawner_icon.png"),
			'IMAGE')
		preview_collections["main"].load(
			"sword_icon",
			os.path.join(icons_dir, "sword_icon.png"),
			'IMAGE')
		preview_collections["main"].load(
			"effects_icon",
			os.path.join(icons_dir, "effects_icon.png"),
			'IMAGE')
		preview_collections["main"].load(
			"entity_icon",
			os.path.join(icons_dir, "entity_icon.png"),
			'IMAGE')
		preview_collections["main"].load(
			"model_icon",
			os.path.join(icons_dir, "model_icon.png"),
			'IMAGE')
	except Exception as e:
		log("Old verison of blender, no custom icons available")
		log("\t" + str(e))
		global use_icons
		use_icons = False
		for iconset in collection_sets:
			preview_collections[iconset] = ""

# ! Deprecated as of MCprep 3.4.2
def log(statement, vv_only=False):
	env.deprecation_warning()
	if env.verbose and vv_only and env.very_verbose:
		print(statement)
	elif env.verbose:
		print(statement)

def updater_select_link_function(self, tag):
	"""Indicates what zip file to use for updating from a tag structure.

	Injected function to avoid being overwritten in future updates.
	"""
	link = tag["zipball_url"]  # Fallback is full source code.

	# However, prefer puling the uploaded addon zip build.
	if "assets" in tag and "browser_download_url" in tag["assets"][0]:
		link = tag["assets"][0]["browser_download_url"]
	return link


# -----------------------------------------------------------------------------
# GLOBAL REGISTRATOR INIT
# -----------------------------------------------------------------------------

# ! Deprecated as of MCprep 3.4.2
def register():
	env.deprecation_warning()
	init()


def unregister():
	if env.use_icons:
		for pcoll in env.preview_collections.values():
			try:
				bpy.utils.previews.remove(pcoll)
			except:
				log('Issue clearing preview set ' + str(pcoll))
	env.preview_collections.clear()

	env.json_data = None  # actively clearing out json data for next open

	env.loaded_all_spawners = False
	env.skin_list = []
	env.rig_categories = []
	env.material_sync_cache = []
