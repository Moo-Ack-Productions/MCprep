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


# -----------------------------------------------------------------------------
# ADDON GLOBAL VARIABLES AND INITIAL SETTINGS
# -----------------------------------------------------------------------------

import bpy
import os

# check if custom preview icons available
try:
	import bpy.utils.previews
except:
	print("MCprep: No custom icons in this blender instance")
	pass

def init():

	# -----------------------------------------------
	# Verbose, use as conf.v
	# Used to print out extra information, set false with distribution
	# -----------------------------------------------
	global dev
	dev = False

	global v
	v = True # $VERBOSE, UI setting

	global vv
	vv = dev # $VERYVERBOSE

	# -----------------------------------------------
	# To prevent recusrive function calls on property changes
	# -----------------------------------------------

	global internal_change
	internal_change = False


	# -----------------------------------------------
	# To display smart warnings and fixes
	# -----------------------------------------------

	global mcprep_warnings
	mcprep_warnings = []
	# examples: is your scene scaled at /10 for mineways?


	# -----------------------------------------------
	# JSON attributes
	# -----------------------------------------------


	# shouldn't load here, just globalize any json data?

	global data
	import os
	# import json

	global json_data # mcprep_data.json
	json_data = None # later will load addon information etc

	global json_user # mcprep_user.json
	json_user = None # later will load user saved information


	# if existing json_data_update exists, overwrite it
	setup_path = os.path.join(os.path.dirname(__file__),"mcprep_data.json")
	if os.path.isfile( os.path.join(os.path.dirname(__file__),\
			"mcprep_data_update.json") ) == True:
		
		# remove old json
		if os.path.isfile(setup_path) == True:
			os.remove(setup_path)
		# change to new name
		os.rename(os.path.join(os.path.dirname(__file__),\
			"mcprep_data_update.json"), setup_path)


	# if os.path.isdir(MCprep_resources) is false: create it (and then we know assets = 0)


	# -----------------------------------------------
	# For preview icons
	# -----------------------------------------------

	global use_icons
	use_icons = True
	global preview_collections
	preview_collections = {}
	global thumb_ids
	thumb_ids = {}

	# actual setup/icon loading in the according files
	

	# -----------------------------------------------
	# For installing assets
	# -----------------------------------------------

	global count_install_assets
	count_install_assets = 0
	global missing_assets
	missing_assets = []
	global missing_details
	missing_details = ""
	global asset_filepath
	asset_filepath = ""
	global assets_installed
	assets_installed = False


	# -----------------------------------------------
	# For installing assets
	# -----------------------------------------------

	global update_ready
	update_ready = False

	# in a background thread, connect to see if ready. 
	# have an internal count thing that requests to enable checking
	# or force users to decide after 5 uses, ie blocking the panels

	# -----------------------------------------------
	# For initializing the custom icons
	# -----------------------------------------------
	icons_init()


	# -----------------------------------------------
	# For cross-addon lists
	# -----------------------------------------------
	global skin_list
	skin_list = [] # each is: [ basename, path ]
	
	global rig_list
	global rig_list_sub
	global rig_categories
	
	rig_list = [] # each is: [ relative path+':/:'+name+':/:'+catgry,  
				  #            name.title(),
				  #            description ]
	rig_list_sub = [] # shorthand for categories
	rig_categories = [] # simple list of directory names

	global active_mob
	global active_mob_subind

	# for radio button active mob
	active_mob = "" # format "relative path+':/:'+name+':/:'+catgry"
	active_mob_subind = -1

	global meshswap_list
	meshswap_list = []


# -----------------------------------------------------------------------------
# ICONS INIT
# -----------------------------------------------------------------------------


def icons_init():
	# start with custom icons
	# put into a try statement in case older blender version!
	global preview_collections
	global v

	try:
		custom_icons = bpy.utils.previews.new()
		script_path = bpy.path.abspath(os.path.dirname(__file__))
		icons_dir = os.path.join(script_path,'icons')
		custom_icons.load("crafting_icon", os.path.join(icons_dir, "crafting_icon.png"), 'IMAGE')
		custom_icons.load("grass_icon", os.path.join(icons_dir, "grass_icon.png"), 'IMAGE')
		custom_icons.load("spawner_icon", os.path.join(icons_dir, "spawner_icon.png"), 'IMAGE')
		preview_collections["main"] = custom_icons
	except Exception as e:
		if v:print("Old verison of blender, no custom icons available")
		if v:print("\t"+str(e))
		preview_collections["main"] = ""
	
	# initialize the rest
	preview_collections["skins"] = ""
	preview_collections["mobs"] = ""
	preview_collections["blocks"] = ""


# -----------------------------------------------------------------------------
# GLOBAL REGISTRATOR INIT
# -----------------------------------------------------------------------------


def register():
	pass


def unregister():
	global preview_collections
	# if preview_collections["main"] != "":
	# 	for pcoll in preview_collections.values():
	# 		#print("clearing?",pcoll)
	# 		bpy.utils.previews.remove(pcoll)
	# 	preview_collections.clear()
	
