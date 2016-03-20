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
from . import spawner # remove once UIlist for mobs implemented

# do this here??

try:
	import bpy.utils.previews
except:
	if conf.v:print("No custom icons in this blender instance")
	pass

# for custom icons
preview_collections = {} # move to conf..



#######
# Show MCprep preferences
class showMCprefs(bpy.types.Operator):
	"""Show MCprep preferences"""
	bl_idname = "object.mcprep_preferences"
	bl_label = "Show MCprep preferences"

	def execute(self,context):
		bpy.ops.screen.userpref_show # doesn't work unless is set as an operator button directly!!! sigh
		bpy.data.window_managers["WinMan"].addon_search = "MCprep"
		#bpy.ops.wm.addon_expand(module="MCprep_addon") # just toggles not sets it, not helpful. need to SET it to expanded
		return {'FINISHED'}


#######
# Show MCprep preferences
class spawnPathReset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "object.mcprep_spawnpathreset"
	bl_label = "Reset spawn path"

	def execute(self,context):
		
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		context.scene.mcrig_path = addon_prefs.mcrig_path
		updateRigList()
		return {'FINISHED'}



########################################################################################
#	Above for class functions/operators
#	Below for UI
########################################################################################



#######
# Panel for placing in the shift-A add object menu
class mobSpawnerMenu(bpy.types.Menu):
	bl_label = "Mob Spawner"
	bl_idname = "mcmob_spawn_menu"

	def draw(self, context):
		#self.layout.operator(AddBox.bl_idname, icon='MESH_CUBE') # not sure how to make it work for a menu
		layout = self.layout
		rigitems = getRigList()
		if conf.v:print("RIG ITEMS length:"+str(len(rigitems)))
		for n in range(len(rigitems)):
			# do some kind of check for if no rigs found
			if False:
				layout.label(text="No rigs found", icon='ERROR')
			layout.operator("object.mcprep_mobspawner", text=rigitems[n][1]).mcmob_type = rigitems[n][0]

#######
# Panel for all the meshswap objects
class meshswapPlaceMenu(bpy.types.Menu):
	bl_label = "Meshswap Objects"
	bl_idname = "mcprep_meshswapobjs"

	def draw(self, context):
		layout = self.layout
		layout.label("Still in development")

#######
# Panel for root level of shift-A > MCprep
class mcprepQuickMenu(bpy.types.Menu):
	bl_label = "MCprep"
	bl_idname = "mcprep_objects"

	def draw(self, context):
		layout = self.layout
		layout = self.layout
		if preview_collections["main"] != "":
			pcoll = preview_collections["main"]
			spawner = pcoll["spawner_icon"]
			meshswap = pcoll["grass_icon"]
			layout.menu(mobSpawnerMenu.bl_idname,icon_value=spawner.icon_id)
			layout.menu(meshswapPlaceMenu.bl_idname,icon_value=meshswap.icon_id)
		else:
			layout.menu(mobSpawnerMenu.bl_idname)
			layout.menu(meshswapPlaceMenu.bl_idname)



#######
# pop-up declaring some button is WIP still =D
class WIP(bpy.types.Menu):
	bl_label = "wip_warning"
	bl_idname = "view3D.wip_warning"

	# Set the menu operators and draw functions
	def draw(self, context):
		layout = self.layout
		row1 = layout.row()
		row1.label(text="This addon is a work in progress, this function is not yet implemented")  



#######
# preferences UI
class MCprepPreference(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	meshswap_path = bpy.props.StringProperty(
		name = "meshswap_path",
		description = "Asset file for meshswapable objects and groups",
		subtype = 'FILE_PATH',
		default = scriptdir + "/mcprep_meshSwap.blend")
	mcrig_path = bpy.props.StringProperty(
		name = "mcrig_path",
		description = "Folder for rigs to spawn in, default for new blender instances",
		subtype = 'DIR_PATH',
		default = scriptdir + "/rigs/")
	mcprep_use_lib = bpy.props.BoolProperty(
		name = "Link meshswapped groups & materials",
		description = "Use library linking when meshswapping or material matching",
		default = False)
	MCprep_groupAppendLayer = bpy.props.IntProperty(
		name="Group Append Layer",
		description="When groups are appended instead of linked, the objects part of the group will be placed in this layer, 0 means same as active layer",
		min=0,
		max=20,
		default=20)
	MCprep_exporter_type = bpy.props.EnumProperty(
		items = [('(choose)', '(choose)', 'Select your exporter'),
				('jmc2obj', 'jmc2obj', 'Select if exporter used was jmc2obj'),
				('Mineways', 'Mineways', 'Select if exporter used was Mineways')],
		name = "Exporter")
	checked_update = bpy.props.BoolProperty(
		name = "mcprep_updatecheckbool",
		description = "Has an update for MCprep been checked for already",
		default = False)
	update_avaialble = bpy.props.BoolProperty(
		name = "mcprep_update",
		description = "True if an update is available",
		default = False)
	mcprep_meshswapjoin = bpy.props.BoolProperty(
		name = "mcprep_meshswapjoin",
		description = "Join individuals objects together during meshswapping",
		default = True)

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.label("Meshswap")
		layout = layout.box()
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Default Exporter:")
		col = split.column()
		col.prop(self, "MCprep_exporter_type", text="")
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Meshwap assets")
		col = split.column()
		col.prop(self, "meshswap_path", text="")

		layout = self.layout
		row = layout.row()
		row.label("Mob spawning")
		layout = layout.box()
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Rig Folder")
		col = split.column()
		col.prop(self, "mcrig_path", text="")
		split = layout.split(percentage=0.3)
		col = split.column()
		col.label("Select/install mobs")
		col = split.column()
		col.operator("object.mcmob_install_menu", text="Install file for mob spawning")
		col = split.column()
		col.operator("object.mc_openrigpath", text="Open rig folder")

		# misc settings
		layout = self.layout
		row = layout.row()
		row.prop(self, "mcprep_use_lib")
		row = layout.row()

		# another row for 
		layout = self.layout
		split = layout.split(percentage=0.5)
		col = split.column()
		row = layout.row()
		# if checkOptin():
		# 	col.operator("object.mc_toggleoptin", text="Opt OUT of anonymous usage tracking", icon='CANCEL')
		# else:
		# 	col.operator("object.mc_toggleoptin", text="Opt into of anonymous usage tracking", icon='HAND')
		#row = layout.row()
		col = split.column()
		col.operator("object.mcprep_openreleasepage", text="MCprep page for instructions and updates", icon="WORLD")
		row = layout.row()
		row.label("Don't forget to save user preferences!")



#######
# MCprep panel for these declared tools
class MCpanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "World Imports"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		
		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		col.label("World exporter:")
		split = layout.split()
		col = split.row(align=True)
		row = col.row(align=True)
		row.prop(addon_prefs,"MCprep_exporter_type", expand=True)

		
		split = layout.split()
		col = split.column(align=True)

		col.label("MCprep tools")
		col.operator("object.mc_mat_change", text="Prep Materials", icon='MATERIAL')
		col.operator("object.mc_meshswap", text="Mesh Swap", icon='LINK_BLEND')
		#the UV's pixels into actual 3D geometry (but same material, or modified to fit)
		#col.operator("object.solidify_pixels", text="Solidify Pixels", icon='MOD_SOLIDIFY')
		split = layout.split()
		row = split.row(align=True)
		if addon_prefs.MCprep_exporter_type == "(choose)":
			row.label(text="Select exporter!",icon='ERROR')
		elif addon_prefs.MCprep_exporter_type == "Mineways":
			col.label (text="Check block size is")
			col.label (text="1x1x1, not .1x.1.x.1")
			# Attempt AutoFix, another button
			col.operator("object.fixmeshswapsize", text="Quick upscale from 0.1")
		else:
			row.label('jmc2obj works best :)')

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)

		if not context.scene.mcprep_showsettings:
			row.prop(context.scene,"mcprep_showsettings", text="settings", icon="TRIA_RIGHT")
			#row.operator("object.mcprep_preferences",icon="PREFERENCES",text='')
			row.operator("screen.userpref_show",icon="PREFERENCES",text='')

		else:
			row.prop(context.scene,"mcprep_showsettings", text="settings", icon="TRIA_DOWN")
			row.operator("screen.userpref_show",icon="PREFERENCES",text='')
			layout = layout.box()

			split = layout.split(percentage=1)
			col = split.column(align=True)
			col.prop(addon_prefs,"mcprep_meshswapjoin",text="Join same blocks together")
			col.prop(addon_prefs,"mcprep_use_lib",text="Link groups")
			col.label("Append layer")
			col.prop(addon_prefs,"MCprep_groupAppendLayer",text="")
			if addon_prefs.mcprep_use_lib == True:
				col.enabled = False
			col.label(text="Meshswap source:")
			col.prop(addon_prefs,"meshswap_path",text="")

		layout = self.layout # clear out the box formatting
		split = layout.split()
		row = split.row(align=True)
		if conf.update_ready==True:# checkForUpdate(): # and not v: # for dev testing, don't show?
			row.label (text="Update ready!", icon='ERROR')
			split = layout.split()
			row = split.row(align=True)
			row.operator("wm.url_open",text="Get it now", icon="HAND").url = \
					"https://github.com/TheDuckCow/MCprep/releases"


#######
# MCprep panel for mob spawning
class MCpanelSpawn(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "Mob Spawner"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		
		layout = self.layout
		layout.label("Spawn rig folder")
		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		row.prop(context.scene,"mcrig_path",text="")
		row = col.row(align=True)
		row.operator("object.mc_openrigpath", text="Open folder", icon='FILE_FOLDER')
		row.operator("object.mcprep_spawnpathreset", icon='LOAD_FACTORY', text='')
		row.operator("object.mc_reloadcache", icon='LOOP_BACK', text='')
		
		# here for the automated rest of them

		# change this to a UI list! jeez..


		rigitems = spawner.getRigList()
		catlabel = ""
		split = layout.split()
		# do some kind of check for if no rigs found
		col = split.column(align=True)
		last = False
		if len(rigitems) == 0:
			layout.label(text="No rigs found", icon='ERROR')
		else:
			for n in range(len(rigitems)):
				
				tmp = rigitems[n][0].split(":/:")
				if tmp[-1] != catlabel:
					
					if catlabel !="":
						col.operator("object.mcmob_install_menu","Install {x}".format(x=catlabel),icon="PLUS").mob_category = catlabel
					catlabel = tmp[-1]
					split = layout.split()
					col = split.column(align=True)
					if catlabel=="//\//":
						col.label(text="Uncategorized mobs")
						last = True
					else:
						col.label(text="{x} mobs".format(x=catlabel.title()))
				#credit = tmp[0].split(" - ")[-1].split(".")[0]  # looks too messy to have in the button itself,
				# maybe place in the redo last menu
				#tx = "{x}  (by {y})".format(x=rigitems[n][1],y=credit)
				col.operator("object.mcprep_mobspawner", text=rigitems[n][1].title()).mcmob_type = rigitems[n][0]

			#col.operator("object.mcmob_install_menu","Install {x}".format(x=catlabel),icon="PLUS").mob_category = catlabel # the last one
			if last: #there were uncategorized rigs
				col.operator("object.mcmob_install_menu","Install uncategorized",icon="PLUS").mob_category = "no_category" # the last one
			else: # there weren't, so fix UI to created that section
				col.operator("object.mcmob_install_menu","Install {x}".format(x=catlabel),icon="PLUS").mob_category = catlabel
				split = layout.split()
				col = split.column(align=True)
				col.label(text="(Uncategorized mobs)")
				col.operator("object.mcmob_install_menu","Install without category",icon="PLUS").mob_category = "no_category" # the last one


		layout = self.layout # clear out the box formatting
		split = layout.split()
		row = split.row(align=True)
		if conf.update_ready==True:#checkForUpdate() and not v:
			row.label (text="Update ready!", icon='ERROR')
			split = layout.split()
			row = split.row(align=True)
			row.operator("wm.url_open",text="Get it now", icon="HAND").url = \
					"https://github.com/TheDuckCow/MCprep/releases"


#######
# WIP OK button general purpose
class dialogue(bpy.types.Operator):
	bl_idname = "object.dialogue"
	bl_label = "dialogue"
	message = "Library error, check path to assets has the meshSwap blend"
	
	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)
		return {'FINISHED'}
	
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400, height=200)
		#return wm.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.label(self.message)


####
# This allows you to right click on a button and link to the manual
def ops_manual_map():
	url_manual_prefix = "https://github.com/TheDuckCow/MCprep"
	url_manual_mapping = (
		("bpy.ops.mesh.add_object", "Modeling/Objects"),
		)
	return url_manual_prefix, url_manual_mapping


# -----------------------------------------------------------------------------
#	Above for UI
#	Below for registration stuff
# -----------------------------------------------------------------------------


# for custom menu registration, icon for spawner MCprep menu of shift-A
def draw_mobspawner(self, context):
	layout = self.layout
	pcoll = preview_collections["main"]
	if pcoll != "":
		my_icon = pcoll["spawner_icon"]
		layout.menu(mobSpawnerMenu.bl_idname,icon_value=my_icon.icon_id)
	else:
		layout.menu(mobSpawnerMenu.bl_idname)


# for custom menu registration, icon for top-level MCprep menu of shift-A
def draw_mcprepadd(self, context):
	layout = self.layout
	pcoll = preview_collections["main"]
	if pcoll != "":
		my_icon = pcoll["crafting_icon"]
		layout.menu(mcprepQuickMenu.bl_idname,icon_value=my_icon.icon_id)
	else:
		layout.menu(mcprepQuickMenu.bl_idname)



def register():
	# start with custom icons
	# put into a try statement in case older blender version!

	try:
		custom_icons = bpy.utils.previews.new()
		script_path = bpy.path.abspath(os.path.dirname(__file__))
		icons_dir = os.path.join(script_path,'icons')
		custom_icons.load("crafting_icon", os.path.join(icons_dir, "crafting_icon.png"), 'IMAGE')
		custom_icons.load("grass_icon", os.path.join(icons_dir, "grass_icon.png"), 'IMAGE')
		custom_icons.load("spawner_icon", os.path.join(icons_dir, "spawner_icon.png"), 'IMAGE')
		preview_collections["main"] = custom_icons
	except:
		if conf.v:print("Old verison of blender, no custom icons available")
		preview_collections["main"] = ""


	bpy.types.Scene.mcprep_showsettings = bpy.props.BoolProperty(
		name = "mcprep_showsettings",
		description = "Show extra settings in the MCprep panel",
		default = False)

	bpy.types.INFO_MT_add.append(draw_mcprepadd)

	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
	bpy.types.Scene.mcrig_path = bpy.props.StringProperty(
		name = "mcrig_path",
		description = "Folder for rigs to spawn in, saved with this blend file data",
		subtype = 'DIR_PATH',
		default = addon_prefs.mcrig_path)

	#bpy.utils.register_manual_map(ops_manual_map)
	
	# install()
	if conf.v:print("MCprep register complete")

def unregister():

	bpy.types.INFO_MT_add.remove(draw_mcprepadd)
	del bpy.types.Scene.mcprep_showsettings
	#global custom_icons
	#bpy.utils.previews.remove(custom_icons)
	#print("unreg:")
	#print(preview_collections)
	if preview_collections["main"] != "":
		for pcoll in preview_collections.values():
			#print("clearing?",pcoll)
			bpy.utils.previews.remove(pcoll)
		preview_collections.clear()

	#bpy.utils.unregister_manual_map(ops_manual_map)

