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
import subprocess

# addon imports
from . import conf
from . import util
from . import spawner # remove once UIlist for mobs implemented
from . import materials
from . import addon_updater_ops
from . import tracking


# check if custom preview icons available
try:
	import bpy.utils.previews
except:
	if conf.v:print("No custom icons in this blender instance")
	pass

# for custom icons
preview_collections = {} # move to conf..


class showMCprefs(bpy.types.Operator):
	"""Show MCprep preferences"""
	bl_idname = "mcprep.open_preferences"
	bl_label = "Show MCprep preferences"

	tab = bpy.props.EnumProperty(
		items = [('settings', 'Open settings', 'Open MCprep preferences settings'),
				('tutorials', 'Open tutorials', 'View tutorials'),
				('tracker_updater', 'Open tracker/updater settings', 'Open user tracking & addon updating settings')],
		name = "Exporter")

	def execute(self,context):
		bpy.ops.screen.userpref_show('INVOKE_AREA')
		context.user_preferences.active_section = "ADDONS"
		bpy.data.window_managers["WinMan"].addon_search = "MCprep"
		try:
			#  if info["show_expanded"] != True:

			#
			#, where info comes from for mod, info in addons:
			# and addons is:
			# import addon_utils
			# addons = [(mod, addon_utils.module_bl_info(mod)) for mod in addon_utils.modules(refresh=False)]
			#
			# ie, get MCprep from mod in addon_utils.modules(refresh=False)
			# and then just 	grab 
			# [addon_utils.module_bl_info(mod)]


			# less ideal way but works
			# for mod in 
			# addon = addon_utils.module_bl_info(mode)
			import addon_utils
			addon = addon_utils.module_bl_info(__package__)
			if addon["show_expanded"] != True:
				print("not expanded, expanding?")
				bpy.ops.wm.addon_expand(module=__package__)
		except:
			if conf.v: print("Couldn't toggle MCprep preferences being expended")

		preferences_tab = self.tab
		# # just toggles not sets it, not helpful. need to SET it to expanded
		return {'FINISHED'}


class openFolder(bpy.types.Operator):
	"""Open the rig folder for mob spawning"""
	bl_idname = "mcprep.openfolder"
	bl_label = "Open folder"

	folder = bpy.props.StringProperty(
		name="Folderpath",
		default="//")

	def execute(self,context):
		
		if os.path.isdir(bpy.path.abspath(self.folder))==False:
			self.report({'ERROR'}, "Invalid folder path: {x}".format(x=self.folder))
			return {'CANCELLED'}

		try:
			# windows... untested
			subprocess.Popen('explorer "{x}"'.format(x=bpy.path.abspath(self.folder)))
		except:
			try:
				# mac... works on Yosemite minimally
				subprocess.call(["open", bpy.path.abspath(self.folder)])
			except:
				self.report({'ERROR'},
					"Didn't open folder, navigate to it manually: {x}".format(x=self.folder))
				return {'CANCELLED'}
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Above for class functions/operators
#	Below for UI
# -----------------------------------------------------------------------------




# Menu for placing in the shift-A add object menu
class mobSpawnerMenu(bpy.types.Menu):
	bl_label = "Mob Spawner"
	bl_idname = "mcmob_spawn_menu"

	def draw(self, context):
		#self.layout.operator(AddBox.bl_idname, icon='MESH_CUBE') # not sure how to make it work for a menu
		layout = self.layout
		rigitems = spawner.getRigList(context)
		# add a categories thing too.
		for n in range(len(rigitems)):
			# do some kind of check for if no rigs found
			if False:
				layout.label(text="No rigs found", icon='ERROR')
			layout.operator("mcprep.mob_spawner", text=rigitems[n][1]).mcmob_type = rigitems[n][0]


# Menu for all the meshswap objects
class meshswapPlaceMenu(bpy.types.Menu):
	bl_label = "Meshswap Objects"
	bl_idname = "mcprep_meshswapobjs"

	def draw(self, context):
		layout = self.layout
		if True:
			layout.label(text="Feature coming soon, really!", icon='ERROR')
			return

		# make it for meshswap items
		rigitems = spawner.getRigList(context)
		for n in range(len(rigitems)):
			# do some kind of check for if no rigs found
			layout.operator("mcprep.meshswap_spawner", text=rigitems[n][1]).mcmob_type = rigitems[n][0]


# Menu for root level of shift-A > MCprep
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




# pop-up declaring some button is WIP still =D
class WIP(bpy.types.Menu):
	bl_label = "wip_warning"
	bl_idname = "view3D.wip_warning"

	# Set the menu operators and draw functions
	def draw(self, context):
		layout = self.layout
		row1 = layout.row()
		row1.label(text="This addon is a work in progress, this function is not yet implemented")  




# preferences UI
class MCprepPreference(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	def change_verbose(self, context):
		conf.v = self.verbose

	meshswap_path = bpy.props.StringProperty(
		name = "Meshswap path",
		description = "Asset file for meshswapable objects and groups",
		subtype = 'FILE_PATH',
		default = scriptdir + "/MCprep_resources/default_mcprep/mcprep_meshSwap.blend")
	mcrig_path = bpy.props.StringProperty(
		name = "Rig path",
		description = "Folder for rigs to spawn in, default for new blender instances",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/default_mcprep/rigs/")
	mcskin_path = bpy.props.StringProperty(
		name = "Skin path",
		description = "Folder for skin textures, used in skin swapping",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/skins/")
	mcprep_use_lib = bpy.props.BoolProperty(
		name = "Link meshswapped groups & materials",
		description = "Use library linking when meshswapping or material matching",
		default = False)
	MCprep_groupAppendLayer = bpy.props.IntProperty(
		name="Group Append Layer",
		description="When groups are appended instead of linked, "+\
				"the objects part of the group will be placed in this "+\
				"layer, 0 means same as active layer",
		min=0,
		max=20,
		default=20)
	MCprep_exporter_type = bpy.props.EnumProperty(
		items = [('(choose)', '(choose)', 'Select your exporter'),
				('jmc2obj', 'jmc2obj', 'Select if exporter used was jmc2obj'),
				('Mineways', 'Mineways', 'Select if exporter used was Mineways')],
		name = "Exporter")
	mcprep_meshswapjoin = bpy.props.BoolProperty(
		name = "Meshswap join",
		description = "Join individuals objects together during meshswapping",
		default = True)
	preferences_tab = bpy.props.EnumProperty(
		items = [('settings', 'Settings', 'Change MCprep settings'),
				('tutorials', 'Tutorials', 'View MCprep tutorials & other help'),
				('tracker_updater', 'Tracking/Updater', 'Change tracking and updating settings')],
		name = "Exporter")
	verbose = bpy.props.BoolProperty(
		name = "Verbose",
		description = "Print out more information in the console",
		default = False,
		update = change_verbose)

	# addon updater preferences

	auto_check_update = bpy.props.BoolProperty(
		name = "Auto-check for Update",
		description = "If enabled, auto-check for updates using an interval",
		default = True,
		)
	updater_intrval_months = bpy.props.IntProperty(
		name='Months',
		description = "Number of months between checking for updates",
		default=0,
		min=0
		)
	updater_intrval_days = bpy.props.IntProperty(
		name='Days',
		description = "Number of days between checking for updates",
		default=7,
		min=0,
		)
	updater_intrval_hours = bpy.props.IntProperty(
		name='Hours',
		description = "Number of hours between checking for updates",
		default=0,
		min=0,
		max=23
		)
	updater_intrval_minutes = bpy.props.IntProperty(
		name='Minutes',
		description = "Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59
		)



	def draw(self, context):
		layout = self.layout
		row = layout.row()
		#row.template_header()
		row.prop(self, "preferences_tab", expand=True)

		if self.preferences_tab == "settings":
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
			col.operator("object.mc_openrigpath", text="Open rig folder") #mcprep.openfolder

			layout = self.layout
			row = layout.row()
			row.label("Skin swapping")
			layout = layout.box()
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Skin Folder")
			col = split.column()
			col.prop(self, "mcskin_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Install skins")
			col = split.column()
			col.operator("mcprep.skin_swapper", text="Install skin file for swapping")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open skin folder")
			p.folder = self.mcskin_path

			# misc settings
			layout = self.layout
			row = layout.row()
			col = row.column()
			col.prop(self, "mcprep_use_lib")
			col = row.column()
			col.prop(self, "verbose")
			row = layout.row()

		elif self.preferences_tab == "tutorials":
			layout.label("Unsure on how to use the addon? Check out these resources")
			col = layout.column()
			col.operator("wm.url_open",
					text="MCprep page for instructions and updates",
					icon="WORLD").url = "https://github.com/TheDuckCow/MCprep"

			row = layout.row()
			col = row.column()
			col.operator("wm.url_open",
					text="Import Minecraft worlds").url = \
					"https://youtu.be/iRixJzraHFI?list=PL8X_CzUEVBfaajwyguIj_utPXO4tEOr7a"
			col = row.column()
			col.operator("wm.url_open",
					text="Mob (rig) spawning").url = \
					"https://youtu.be/asB4UcBuWBw?list=PL8X_CzUEVBfaajwyguIj_utPXO4tEOr7a"
			col = row.column()
			col.operator("wm.url_open",
					text="Demo video/trailer").url = \
					"https://youtu.be/C3YoZx-seFE?list=PL8X_CzUEVBfaajwyguIj_utPXO4tEOr7a"
			row = layout.row()
			
		elif self.preferences_tab == "tracker_updater":
			layout = self.layout
			row = layout.row()
			box = row.box()
			brow = box.row()
			brow.label("Anonymous user tracking settings")


			brow = box.row()
			bcol = brow.column()
			bcol.scale_y = 2

			if tracking.Tracker.tracking_enabled == False:
				bcol.operator("mcprep.toggle_enable_tracking",
						"Opt into anonymous usage tracking",
						icon = "HAND")
			else:
				bcol.operator("mcprep.toggle_enable_tracking",
						"Opt OUT of anonymous usage tracking",
						icon = "CANCEL")

			bcol = brow.column()
			bcol.label("For info on anonymous usage tracking:")
			bcol.operator("wm.url_open",
					text="Open the Privacy Policy").url = \
					"http://theduckcow.com/privacy-policy"

			
			# row.operator(//url,"Read the privacy policy/terms")
			# UI list this info?
			# label("All information collected is anonymous")
			# label("Data collected when enabled includes:")
			# label("- Blender version")
			# label("- MCprep version")
			# label("- OS name/version")
			# label("- MCprep operator used")
			# label("- anonymous ID")
			# label("- Timestamp of when the operator was used")
			# label("No other information is collected.")

			# label("The anonymous local ID name is solely used")
			# label("to track how often a single user uses a function")
			# label("and cannot be traced back to an individual user")


			# if checkOptin():
			# 	col.operator("object.mc_toggleoptin", text="Opt OUT of anonymous usage tracking", icon='CANCEL')
			# else:
			# 	col.operator("object.mc_toggleoptin", text="Opt into of anonymous usage tracking", icon='HAND')
			#row = layout.row()

			# additional tracking info

			# updater draw function
			addon_updater_ops.update_settings_ui(self,context)
			
		layout.label("Don't forget to save user preferences!")			


# ---------
# General addon panel, world importing & material settings
class MCpanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "World Imports"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

		# check for update in background thread if appropraite
		addon_updater_ops.check_for_update_background(context)
		
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
		col.operator("mcprep.mat_change",
				text="Prep Materials", icon='MATERIAL')

		col.operator("mcprep.combine_materials",
				text="Combine Materials",
				icon="GHOST").selection_only=True
		if (bpy.app.version[0]	==2 and bpy.app.version[1] > 77) or (bpy.app.version[0]>2):
			col.operator("mcprep.combine_images",
					text="Combine Images",
					icon="GHOST")

		if context.space_data.show_textured_solid == True and \
				context.user_preferences.system.use_mipmaps == False:
			row = col.row(align=True)
			row.enabled = False
			row.operator("mcprep.improve_ui",
					text="(UI already improved)", icon='SETTINGS')		
		else:
			col.operator("mcprep.improve_ui",
					text="Improve UI", icon='SETTINGS')
		
		col.operator("mcprep.meshswap", text="Mesh Swap", icon='LINK_BLEND')
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


		if not context.scene.mcprep_props.mcprep_showsettings:
			row.prop(context.scene.mcprep_props,"mcprep_showsettings",
					text="settings", icon="TRIA_RIGHT")
			row.operator("mcprep.open_preferences",
					icon="PREFERENCES",text='').tab = "settings"

		else:
			row.prop(context.scene.mcprep_props,
					"mcprep_showsettings",
					text="settings", icon="TRIA_DOWN")
			row.operator("mcprep.open_preferences",
					icon="PREFERENCES",text='').tab = "settings"
			layout = layout.box()

			split = layout.split(percentage=1)
			col = split.column(align=True)
			col.prop(addon_prefs,"mcprep_meshswapjoin",
					text="Join same blocks together")
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

		# show update ready if available
		addon_updater_ops.update_notice_box_ui(self, context)


		if conf.update_ready==True:# checkForUpdate(): # and not v: # for dev testing, don't show?
			row.label (text="Update ready!", icon='ERROR')
			split = layout.split()
			row = split.row(align=True)
			row.operator("wm.url_open",text="Get it now", icon="HAND").url = \
					"https://github.com/TheDuckCow/MCprep/releases"



# ---------
# MCprep panel for skin swapping
class MCpanelSkins(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "Skin Swapper"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):

		layout = self.layout
		# layout.label("Skin directory")
		# split = layout.split()
		# col = split.column(align=True)
		# row = col.row(align=True)
		# row.prop(context.scene,"mcskin_path",text="")
		# row.operator("mcprep.reload_skins", icon='LOOP_BACK', text='')
		# row = col.row(align=True)
		# layout.operator("mcprep.fix_skin_eyes")


		# set size of UIlist
		row = layout.row()
		col = row.column()



		is_sortable = len(conf.skin_list) > 1
		rows = 1
		if (is_sortable):
			rows = 4

		# row = col.row()
		col.prop(context.scene,"mcskin_path",text="Source")

		# any other conditions for needing reloading?
		if len(conf.skin_list)==0:
			col = layout.column()
			col.label("No skins loaded")
			p = col.operator("mcprep.reload_skins","Press to reload", icon="ERROR")
			return

		col.template_list("MCPREP_skin_UIList", "",
				context.scene, "mcprep_skins_list",
				context.scene, "mcprep_skins_list_index",
				rows=rows)
		
		col = row.column(align=True)
		col.operator("mcprep.add_skin", icon='ZOOMIN', text="")
		col.operator("mcprep.remove_skin",
				icon='ZOOMOUT',
				text="").index = context.scene.mcprep_skins_list_index
		col.operator("mcprep.reload_skins", icon='LOOP_BACK', text='')


		col = layout.column(align=True)

		row = col.row(align=True)
		if len (conf.skin_list)>0:
			skinname = bpy.path.basename(
					conf.skin_list[context.scene.mcprep_skins_list_index][0] )
			p = row.operator("mcprep.applyskin","Apply: "+skinname) 
			p.filepath = conf.skin_list[context.scene.mcprep_skins_list_index][1]
		else:
			row.enabled = False
			p = row.operator("mcprep.skin_swapper","No skins found")
		row = col.row(align=True)
		row.operator("mcprep.skin_swapper","Skin from file")
		row = col.row(align=True)
		row.operator("mcprep.applyusernameskin","Skin from username")


# ---------
# MCprep panel for mob spawning
class MCpanelSpawn(bpy.types.Panel):
	"""MCprep spawning panel"""
	bl_label = "Spawner"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):

		# check for update if appropriate
		addon_updater_ops.check_for_update_background(context)
		settings = context.scene.mcprep_props
		
		layout = self.layout
		row = layout.row()
		row.prop(settings, "spawn_rig_category", text="")

		# any other conditions for needing reloading?
		if len(conf.rig_list)==0:
			col = layout.column()
			col.label("No mobs loaded")
			p = col.operator("mcprep.spawnpathreset","Press to reload", icon="ERROR")
			return
		
		row = layout.row()
		rows = 4
		# is_sortable = len(conf.rig_list) > 1
		# if (is_sortable):
		# 	rows = 4

		col = row.column(align=True)

		col.template_list("MCPREP_mob_UIList", "",
				context.scene, "mcprep_mob_list",
				context.scene, "mcprep_mob_list_index",
				rows=rows)
		
		col = row.column(align=True)
		p = col.operator("object.mcmob_install_menu","",icon="ZOOMIN")
		p.mob_category = settings.spawn_rig_category
		col.operator("mcprep.mcmob_uninstall", icon='ZOOMOUT', text="")
		
		# instead of open, make it change folder.
		col.operator("object.mc_openrigpath", text="", icon='FILE_FOLDER')
		col.operator("mcprep.reload_mobs", icon='FILE_REFRESH', text='')
		col.operator("mcprep.spawnpathreset", icon='LOAD_FACTORY', text='')

		row = layout.row()
		col = row.column(align=True)
		# get which rig is selected
		if len(conf.rig_list_sub)>0:
			name = conf.rig_list_sub[context.scene.mcprep_mob_list_index][1]
			p = col.operator("mcprep.mob_spawner","Spawn: "+name)
			p.mcmob_type = conf.rig_list_sub[context.scene.mcprep_mob_list_index][0]
		else:
			# other condition for reloading??/if none found
			col.label("No mobs loaded")
			p = col.operator("mcprep.spawnpathreset","Press to reload", icon="ERROR")



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
	
	def draw(self, context):
		self.layout.label(self.message)



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


# -----------------------------------------------
# Addon wide properties (aside from user preferences)
# ----------------------------------------------- 
class MCprep_props(bpy.types.PropertyGroup):

	# not available here
	#addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

	mcprep_showsettings = bpy.props.BoolProperty(
		name = "mcprep_showsettings",
		description = "Show extra settings in the MCprep panel",
		default = False)

	spawn_rig_category = bpy.props.EnumProperty(
		name="Mob category",
		description="Category of mobs & character rigs to spawn",
		update=spawner.spawn_rigs_category_load,
		items=spawner.spawn_rigs_categories #
	)



# -----------------------------------------------
# Register functions
# ----------------------------------------------- 


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

	bpy.types.Scene.mcprep_props = bpy.props.PointerProperty(type=MCprep_props)

	# scene settings (later re-attempt to put into props group)
	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

	bpy.types.Scene.mcrig_path = bpy.props.StringProperty(
		name = "mcrig_path",
		description = "Folder for rigs to spawn in, saved with this blend file data",
		subtype = 'DIR_PATH',
		default = addon_prefs.mcrig_path)
	bpy.types.Scene.mcskin_path = bpy.props.StringProperty(	
		name = "mcskin_path",
		description = "Folder for skin textures, used in skin swapping",
		subtype = 'DIR_PATH',
		update=materials.update_skin_path,
		default = addon_prefs.mcskin_path)

	conf.v = addon_prefs.verbose

	bpy.types.INFO_MT_add.append(draw_mcprepadd)
	

def unregister():

	bpy.types.INFO_MT_add.remove(draw_mcprepadd)
	
	del bpy.types.Scene.mcprep_props

	if preview_collections["main"] != "":
		for pcoll in preview_collections.values():
			#print("clearing?",pcoll)
			bpy.utils.previews.remove(pcoll)
		preview_collections.clear()

