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

from mathutils import Vector
from pathlib import Path
from typing import Optional, Union, Tuple, List, Dict
import inspect
from dataclasses import dataclass
import enum
import os
import gettext
import json

import bpy
from bpy.utils.previews import ImagePreviewCollection


# -----------------------------------------------------------------------------
# TYPING UTILITIES
# -----------------------------------------------------------------------------


class Form(enum.Enum):
	"""Texture or world import interpretation, for mapping or other needs."""
	MC = "mc"
	MINEWAYS = "mineways"
	JMC2OBJ = "jmc2obj"


class Engine(enum.Enum):
	"""String exact match to output from blender itself for branching."""
	CYCLES = "CYCLES"

	# Blender 2.8 to 4.1
	BLENDER_EEVEE = "BLENDER_EEVEE"

	# Blender 4.2 and beyond
	BLENDER_EEVEE_NEXT = "BLENDER_EEVEE_NEXT"


VectorType = Union[Tuple[float, float, float], Vector]

Skin = Tuple[str, Path]
Entity = Tuple[str, str, str]

# Represents an unknown location 
# for MCprepError. Given a global 
# constant to make it easier to use
# and check for
UNKNOWN_LOCATION = (-1, "UNKNOWN LOCATION")

# check if custom preview icons available
try:
	import bpy.utils.previews
except:
	print("MCprep: No custom icons in this blender instance")
	pass

# This enables Vivy. Only use if
# you know what you're doing!
ENABLE_VIVY = False

# -----------------------------------------------------------------------------
# ADDON GLOBAL VARIABLES AND INITIAL SETTINGS
# -----------------------------------------------------------------------------


class MCprepEnv:
	def __init__(self):
		self.data = None
		self.json_data: Optional[Dict] = None
		self.json_path: Path = Path(os.path.dirname(__file__), "MCprep_resources", "mcprep_data.json")
		self.json_path_update: Path = Path(os.path.dirname(__file__), "MCprep_resources", "mcprep_data_update.json")

		self.dev_file: Path = Path(os.path.dirname(__file__), "mcprep_dev.txt")
		self.languages_folder: Path = Path(os.path.dirname(__file__), "MCprep_resources", "Languages")
		self.translations: Path = Path(os.path.dirname(__file__), "translations.py")

		self.last_check_for_updated = 0

		# Check to see if there's a text file for a dev build. If so,
		if self.dev_file.exists():
			self.dev_build = True
			self.verbose = True
			self.very_verbose = True
			self.log("Dev Build!")

		else:
			self.dev_build = False
			self.verbose = False
			self.very_verbose = False

		# lazy load json, ie only load it when needed (util function defined)

		# -----------------------------------------------
		# For preview icons
		# -----------------------------------------------

		self.use_icons: bool = True
		self.preview_collections: Dict[str, ImagePreviewCollection] = {}

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
		self.loaded_all_spawners: bool = False

		self.skin_list: List[Skin] = []  # each is: [ basename, path ]
		self.rig_categories: List[str] = []  # simple list of directory names
		self.entity_list: List[Entity] = []

		# -----------------------------------------------
		# Matieral sync cahce, to avoid repeat lib reads
		# -----------------------------------------------

		# list of material names, each is a string. None by default to indicate
		# that no reading has occurred. If lib not found, will update to [].
		# If ever changing the resource pack, should also reset to None.
		self.material_sync_cache: List = []
	
		# Whether we use PO files directly or use the converted form
		self.use_direct_i18n = False
		# i18n using Python's gettext module
		#
		# This only runs if translations.py does not exist
		if not self.translations.exists():
			self.languages: dict[str, gettext.NullTranslations] = {}
			for language in self.languages_folder.iterdir():
				self.languages[language.name] = gettext.translation("mcprep", 
										 self.languages_folder, 
										 fallback=True,
										 languages=[language.name])
			self.use_direct_i18n = True
			self.log("Loaded direct i18n!")

		# Cache for Vivy materials. Identical to self.material_sync_cache, but
		# as a seperate variable to avoid conflicts
		self.vivy_cache = None
		
		# The JSON file for Vivy's materials
		self.vivy_material_json: Optional[Dict] = None
		self.reload_vivy_json() # Get latest JSON data

	def reload_vivy_json(self) -> None:
		json_path = Path(os.path.join(os.path.dirname(__file__), "MCprep_resources", "vivy_materials.json"))
		if not json_path.exists():
			json_path.touch()
			self.vivy_material_json = {}
		else: 
			with open(json_path, 'r') as f:
				self.vivy_material_json = json.load(f) if json_path.stat().st_size != 0 else {}
	
	# This allows us to translate strings on the fly
	def _(self, msg: str) -> str:
		if not self.use_direct_i18n:
			return msg
		if bpy.context.preferences.view.language in self.languages:
			return self.languages[bpy.context.preferences.view.language].gettext(msg)
		else:
			return self.languages["en_US"].gettext(msg)

	def update_json_dat_path(self):
		"""If new update file found from install, replace old one with new.

		Should be called as part of register, as otherwise this renaming will
		trigger the renaming of the source file in git history when running
		tests.
		"""
		if self.json_path_update.exists():
			self.json_path_update.replace(self.json_path)

	# -----------------------------------------------------------------------------
	# ICONS INIT
	# -----------------------------------------------------------------------------

	def icons_init(self):
		self.clear_previews()

		collection_sets = [
			"main", "skins", "mobs", "entities", "blocks", "items", "effects", "materials"]

		try:
			for iconset in collection_sets:
				self.preview_collections[iconset] = bpy.utils.previews.new()

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
			self.log(e)
			global use_icons
			self.use_icons = False
			for iconset in collection_sets:
				self.preview_collections[iconset] = ""

	def clear_previews(self):
		for pcoll in self.preview_collections.values():
			try:
				bpy.utils.previews.remove(pcoll)
			except Exception as e:
				self.log('Issue clearing preview set ' + str(pcoll))
				print(e)
		self.preview_collections.clear()

	def log(self, statement: str, vv_only: bool = False):
		if self.verbose and vv_only and self.very_verbose:
			print(statement)
		elif self.verbose:
			print(statement)

	def deprecation_warning(self):
		if self.dev_build:
			import traceback
			self.log("Deprecation Warning: This will be removed in MCprep 3.5.1!")
			traceback.print_stack()

	def current_line_and_file(self) -> Tuple[int, str]:
		"""
		Wrapper to get the current line number and file path for
		MCprepError.

		This function can not return an MCprepError value as doing
		so would be more complicated for the caller. As such, if 
		this fails, we return values -1 and "UNKNOWN LOCATION" to 
		indicate that we do not know the line number or file path 
		the error occured on.

		Returns:
			- If success: Tuple[int, str] representing the current 
			line and file path 

			- If fail: (-1, "UNKNOWN LOCATION")
		"""
		# currentframe can return a None value
		# in certain cases
		cur_frame = inspect.currentframe()
		if not cur_frame:
			return UNKNOWN_LOCATION
		
		# Get the previous frame since the
		# current frame is made for this function,
		# not the function/code that called 
		# this function
		prev_frame = cur_frame.f_back
		if not prev_frame:
			return UNKNOWN_LOCATION

		frame_info = inspect.getframeinfo(prev_frame)
		return frame_info.lineno, frame_info.filename

@dataclass
class MCprepError(object):
	"""
	Object that is returned when 
	an error occurs. This is meant
	to give more information to the 
	caller so that a better error 
	message can be made

	Attributes
	------------
	err_type: BaseException
		The error type; uses standard 
		Python exceptions
		

	line: int
		Line the exception object was 
		created on. The preferred method 
		to do this is to use currentframe 
		and getframeinfo from the inspect 
		module

	file: str
		Path of file the exception object
		was created in. The preferred way 
		to get this is __file__

	msg: Optional[str]
		Optional message to display for an 
		exception. Use this if the exception 
		type may not be so clear cut
	"""
	err_type: BaseException
	line: int 
	file: str
	msg: Optional[str] = None

env = MCprepEnv()

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

def register():
	global env
	if not env.json_data:
		# Enforce re-creation of data structures, to ensure populated after
		# the addon was disabled once (or more) and then re-enabled, while
		# avoiding a double call to init() on the first time load.
		env = MCprepEnv()
		env.update_json_dat_path()


def unregister():
	env.clear_previews()
	env.json_data = None  # actively clearing out json data for next open

	env.loaded_all_spawners = False
	env.skin_list = []
	env.rig_categories = []
	env.material_sync_cache = []
	env.vivy_cache = []
