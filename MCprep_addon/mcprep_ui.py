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


# library imports
import bpy
import os

# addon imports
from . import conf
from . import util
from .spawner import mobs
from .spawner import meshswap
from . import materials
from . import world_tools
from . import addon_updater_ops
from . import tracking
from .materials import skin


# -----------------------------------------------------------------------------
#	Above for class functions/operators
#	Below for UI
# -----------------------------------------------------------------------------


class McprepMobSpawnerMenu(bpy.types.Menu):
	"""Shift-A menu in the 3D view."""
	bl_label = "Mob Spawner"
	bl_idname = "mcmob_spawn_menu"
	bl_description = "Menu for placing in the shift-A add object menu"

	def draw(self, context):
		layout = self.layout

		# if mobs not loaded yet
		if len(conf.rig_list)==0:
			row = layout.row()
			row.operator("mcprep.reload_mobs", text="Load mobs", icon='HAND')
			row.scale_y = 2
			row.alignment = 'CENTER'
			return

		for n in range(len(conf.rig_list)):
			mob = conf.rig_list[n]
			#if mob[0].split(':/:')[-1]!=conf.rig_categories[c]:continue
			# eventually with icon too
			layout.operator("mcprep.mob_spawner",
						text=mob[1]
						).mcmob_type = mob[0]

		# load mobs, eventually try with categories horizontally
		# (via template_list with a collection property?)
		# for c in range(len(conf.rig_categories)):
		# 	col = layout.row()
		# 	col.label(conf.rig_categories[c])
		# 	col.separator()
		# 	for n in range(len(conf.rig_list)):
		# 		mob = conf.rig_list[n]
		# 		if mob[0].split(':/:')[-1]!=conf.rig_categories[c]:continue

		# 		# eventually with icon too
		# 		col.operator("mcprep.mob_spawner",
		# 					text=mob[1]
		# 					).mcmob_type = mob[0]


# Menu for all the meshswap objects
class McprepMeshswapPlaceMenu(bpy.types.Menu):
	bl_label = "Meshswap Objects"
	bl_idname = "mcprep_meshswapobjs"

	def draw(self, context):
		layout = self.layout
		# if True:
		# 	layout.label(text="Feature coming soon, really!", icon='ERROR')
		# 	return

		# make it for meshswap items
		meshswap_blocks = meshswap.getMeshswapList(context)
		for n in range(len(meshswap_blocks)):
			# do some kind of check for if no blocks found
			icn = "BLANK1"
			if meshswap_blocks[n][0].split("/")[0]=="Group":
				icn = "GROUP"

			p = layout.operator(
				"mcprep.meshswap_spawner",
				text=meshswap_blocks[n][1],
				icon=icn
			)
			p.meshswap_block = meshswap_blocks[n][0]
			p.location = context.scene.cursor_location


# Menu for root level of shift-A > MCprep
class McprepQuickMenu(bpy.types.Menu):
	bl_label = "MCprep"
	bl_idname = "mcprep_objects"

	def draw(self, context):
		layout = self.layout
		layout = self.layout

		if conf.preview_collections["main"] != "":
			pcoll = conf.preview_collections["main"]
			spawner = pcoll["spawner_icon"]
			meshswap = pcoll["grass_icon"]
		else:
			spawner=None
			meshswap=None

		if len(conf.rig_list)==0 or len(conf.meshswap_list)==0:
			row = layout.row()
			row.operator("mcprep.reload_spawners", text="Load spawners", icon='HAND')
			row.scale_y = 2
			row.alignment = 'CENTER'
			return

		#layout.operator_menu_enum("object.modifier_add", "type")
		if spawner is not None:
			#layout.operator_menu_enum("mcprep.mob_spawner", "mcmob_type",icon=spawner.icon_id)
			layout.menu(McprepMobSpawnerMenu.bl_idname,icon_value=spawner.icon_id)
		else:
			#layout.operator_menu_enum("mcprep.mob_spawner", "mcmob_type")
			layout.menu(McprepMobSpawnerMenu.bl_idname)
		if meshswap is not None:
			layout.menu(McprepMeshswapPlaceMenu.bl_idname,icon_value=meshswap.icon_id)
		else:
			layout.menu(McprepMeshswapPlaceMenu.bl_idname)


# for custom menu registration, icon for spawner MCprep menu of shift-A
def draw_mobspawner(self, context):
	layout = self.layout
	pcoll = conf.preview_collections["main"]
	if pcoll != "":
		my_icon = pcoll["spawner_icon"]
		layout.menu(mobSpawnerMenu.bl_idname,icon_value=my_icon.icon_id)
	else:
		layout.menu(mobSpawnerMenu.bl_idname)


# for updating the mineways path on OSX
def mineways_update(self, context):
	if ".app/" in self.open_mineways_path:
		# will run twice inherently
		temp = self.open_mineways_path.split(".app/")[0]
		self.open_mineways_path = temp+".app"
	return


# preferences UI
class McprepPreference(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	def change_verbose(self, context):
		conf.v = self.verbose

	meshswap_path = bpy.props.StringProperty(
		name = "Meshswap path",
		description = "Default path to the meshswap asset file, for meshswapable objects and groups",
		subtype = 'FILE_PATH',
		default = scriptdir + "/MCprep_resources/mcprep_meshSwap.blend")
	mob_path = bpy.props.StringProperty(
		name = "Mob path",
		description = "Default folder for rig loads/spawns in new blender instances",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/rigs/")
	custom_texturepack_path = bpy.props.StringProperty(
		name = "Texturepack path",
		description = "Path to a folder containing resources and textures to use"+\
			"with material prepping",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/resourcepacks/mcprep_default/")
	skin_path = bpy.props.StringProperty(
		name = "Skin path",
		description = "Folder for skin textures, used in skin swapping",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/skins/")
	world_obj_path = bpy.props.StringProperty(
		name = "World Folder",
		description = "Default folder for opening world objs from programs like jmc2obj or Mineways",
		subtype = 'DIR_PATH',
		default = "//")
	# mcprep_use_lib = bpy.props.BoolProperty(
	# 	name = "Link meshswapped groups & materials",
	# 	description = "Use library linking when meshswapping or material matching",
	# 	default = False)
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
	preferences_tab = bpy.props.EnumProperty(
		items = [('settings', 'Settings', 'Change MCprep settings'),
				('tutorials', 'Tutorials', 'View MCprep tutorials & other help'),
				('tracker_updater', 'Tracking/Updater', 'Change tracking and updating settings')],
		name = "Exporter")
	verbose = bpy.props.BoolProperty(
		name = "Verbose logging",
		description = "Print out more information in the console",
		default = False,
		update = change_verbose)
	open_jmc2obj_path = bpy.props.StringProperty(
		name = "jmc2obj path",
		description = "Path to the jmc2obj executable",
		subtype = 'FILE_PATH',
		default = "jmc2obj.jar")
	open_mineways_path = bpy.props.StringProperty(
		name = "Mineways path",
		description = "Path to the Mineways executable",
		subtype = 'FILE_PATH',
		update=mineways_update,
		default = "Mineways")
	# open_mineways_path_mac = bpy.props.StringProperty(
	# 	name = "Mineways path",
	# 	description = "Path to the Mineways executable",
	# 	subtype = 'FILE_PATH',
	# 	default = "mineways.app")

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
		default=1,
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

			row.label("World Importing & Meshswapping")
			box = layout.box()
			split = box.split(percentage=0.3)
			col = split.column()
			col.label("Default Exporter:")
			col = split.column()
			col.prop(self, "MCprep_exporter_type", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("jmc2obj executable")
			col = split.column()
			col.prop(self, "open_jmc2obj_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Mineways executable")
			col = split.column()
			col.prop(self, "open_mineways_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("World OBJ Exports Folder")
			col = split.column()
			col.prop(self, "world_obj_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Default texture pack")
			col = split.column()
			col.prop(self, "custom_texturepack_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Meshwap assets")
			col = split.column()
			col.prop(self, "meshswap_path", text="")

			row = layout.row()
			row.label("Texture / Resource packs")
			box = layout.box()
			split = box.split(percentage=0.3)
			col = split.column()
			col.label("Texture pack folder")
			col = split.column()
			col.prop(self, "custom_texturepack_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Install to folder")
			col = split.column()
			col.operator("mcprep.skin_swapper", text="Install resource pack")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open texture pack folder")
			p.folder = self.custom_texturepack_path

			row = layout.row()
			row.label("Mob spawning")
			box = layout.box()
			split = box.split(percentage=0.3)
			col = split.column()
			col.label("Rig Folder")
			col = split.column()
			col.prop(self, "mob_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Select/install mobs")
			col = split.column()
			col.operator("mcprep.mob_install_menu", text="Install file for mob spawning")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open rig folder")
			p.folder = self.mob_path

			row = layout.row()
			row.label("Skin swapping")
			box = layout.box()
			split = box.split(percentage=0.3)
			col = split.column()
			col.label("Skin Folder")
			col = split.column()
			col.prop(self, "skin_path", text="")
			split = layout.split(percentage=0.3)
			col = split.column()
			col.label("Install skins")
			col = split.column()
			col.operator("mcprep.skin_swapper", text="Install skin file for swapping")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open skin folder")
			p.folder = self.skin_path

			# misc settings
			row = layout.row()
			col = row.column()
			col.prop(self, "verbose")
			row = layout.row()

		elif self.preferences_tab == "tutorials":
			layout.label("Unsure on how to use the addon? Check out these resources")
			col = layout.column()
			col.operator("wm.url_open",
					text="MCprep page for instructions and updates",
					icon="WORLD").url = "http://theduckcow.com/dev/blender/mcprep/"
			row = layout.row()
			col = row.column()
			col.operator("wm.url_open",
					text="Import Minecraft worlds").url = \
					"http://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"
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
			brow = box.row()
			bcol.operator("wm.url_open",
					text="Open the Privacy Policy").url = \
					"http://theduckcow.com/privacy-policy"

			# updater draw function
			addon_updater_ops.update_settings_ui(self,context)

		layout.label("Don't forget to save user preferences!")


# ---------
# World importing related & material settings
class McprepWorldImports(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "World Imports"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	# bl_context = "objectmode"
	bl_category = "MCprep"

	# def draw_header(self, context):
	# 	col = self.layout.column()
	# 	# col.scale = 0.75
	# 	col.operator("wm.url_open",
	# 		text="", icon="QUESTION",
	# 		emboss=False).url="http://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"

	def draw(self, context):
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		scn_props = context.scene.mcprep_props

		# check for update in background thread if appropraite
		addon_updater_ops.check_for_update_background()

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		row = col.row()
		row.label("World exporter")
		row.operator("mcprep.open_help", text="", icon="QUESTION").url = \
			"http://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"
		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		row.prop(addon_prefs,"MCprep_exporter_type", expand=True)
		row = col.row(align=True)
		if addon_prefs.MCprep_exporter_type == "(choose)":
			row.operator("mcprep.open_jmc2obj",text="Select exporter!",icon='ERROR')
			row.enabled = False
		elif addon_prefs.MCprep_exporter_type == "Mineways":
			row.operator("mcprep.open_mineways")
		else:
			row.operator("mcprep.open_jmc2obj")

		wpath = addon_prefs.world_obj_path
		col.operator("import_scene.obj","OBJ world import").filepath = wpath

		split = layout.split()
		col = split.column(align=True)
		col.label("MCprep tools")
		col.operator("mcprep.prep_materials", text="Prep Materials")
		p = col.operator("mcprep.swap_texture_pack")
		p.filepath = context.scene.mcprep_custom_texturepack_path
		col.operator("mcprep.meshswap", text="Mesh Swap")

		#the UV's pixels into actual 3D geometry (but same material, or modified to fit)
		#col.operator("object.solidify_pixels", text="Solidify Pixels", icon='MOD_SOLIDIFY')
		split = layout.split()
		col = split.column(align=True)
		if addon_prefs.MCprep_exporter_type == "(choose)":
			col.label(text="Select exporter!",icon='ERROR')

		# Advanced material settings
		texviewable = ['SOLID','TEXTURED','MATEIRAL','RENDERED']
		if context.space_data.show_textured_solid == True and \
				context.user_preferences.system.use_mipmaps == False and \
				context.space_data.viewport_shade in texviewable:
			row = col.row(align=True)
			row.enabled = False
			row.operator("mcprep.improve_ui",
					text="(UI already improved)", icon='SETTINGS')
		else:
			col.operator("mcprep.improve_ui",
					text="Improve UI", icon='SETTINGS')

		if not scn_props.show_settings_material:
			col.prop(scn_props,"show_settings_material",
					text="Advanced", icon="TRIA_RIGHT")
		else:
			col.prop(scn_props,"show_settings_material",
					text="Advanced", icon="TRIA_DOWN")
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			row = b_col.row(align=True)
			row.prop(context.scene, "mcprep_custom_texturepack_path", text="")
			row.operator("mcprep.reset_texture_path", text="", icon="LOAD_FACTORY")

			b_row = box.row()
			b_col = b_row.column(align=True)
			b_col.operator("mcprep.replace_missing_textures", text="Find missing")
			b_col.operator("mcprep.animated_textures")
			# TODO: operator to make all local, all packed, or set to other location
			b_col.operator("mcprep.improve_ui", text="[WIP]Set tex location")
			b_col.operator("mcprep.combine_materials",
					text="Combine Materials").selection_only=True
			if bpy.app.version > (2,77):
				b_col.operator("mcprep.combine_images",text="Combine Images")

			b_col.label(text="Meshswap source:")
			b_col.prop(addon_prefs,"meshswap_path",text="")
			b_col.operator("mcprep.open_preferences",
					icon="PREFERENCES",text='Open preferences').tab = "settings"

		layout = self.layout # clear out the box formatting
		split = layout.split()
		row = split.row(align=True)

		# show update ready if available
		addon_updater_ops.update_notice_box_ui(self, context)


# ---------
# World settings and tools, WIP
class McprepWorldToolsPanel():  # bpy.types.Panel
	"""MCprep addon panel"""
	# bl_label = "World Tools"
	# bl_space_type = 'VIEW_3D'
	# bl_region_type = 'TOOLS'
	# bl_category = "MCprep"

	def draw(self, context):
		layout = self.layout
		rw = layout.row()
		col = rw.column(align=True)
		col.label("World time")

		if util.bv28():
			col.label("[not 2.8-ready]", icon="ERROR")
		elif "mcprep_world" not in bpy.data.groups:
			col.label("No sun/moon found,", icon="ERROR")
			col.operator("mcprep.add_sun_or_moon")
		else:
			col.prop(context.scene.mcprep_props,"world_time",text="")
			p = col.operator("mcprep.time_set")
			p.day_offset = int(context.scene.mcprep_props.world_time/24000)

		layout.split()

		rw = layout.row()
		col = rw.column(align=True)
		col.label("World setup")
		col.operator("mcprep.world")
		col.operator("mcprep.world", text="Add clouds")
		col.operator("mcprep.world", text="Set Weather")


# ---------
# MCprep panel for skin swapping
# (multiple contexts)
class McprepSkinsPanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "Skin Swapper"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = "MCprep"

	def draw(self, context):
		layout = self.layout
		scn_props = context.scene.mcprep_props
		sind = context.scene.mcprep_skins_list_index
		mob_ind = context.scene.mcprep_mob_list_index

		row = layout.row()
		row.label("Select skin")
		row.operator("mcprep.open_help", text="", icon="QUESTION").url = \
			"http://theduckcow.com/dev/blender/mcprep/skin-swapping/"

		# set size of UIlist
		row = layout.row()
		col = row.column()

		is_sortable = len(conf.skin_list) > 1
		rows = 1
		if (is_sortable):
			rows = 4

		# any other conditions for needing reloading?
		if len(conf.skin_list)==0:
			col = layout.column()
			col.label("No skins loaded")
			p = col.operator("mcprep.reload_skins","Press to reload", icon="ERROR")
			return

		col.template_list("McprepSkinUiList", "",
				context.scene, "mcprep_skins_list",
				context.scene, "mcprep_skins_list_index",
				rows=rows)

		col = layout.column(align=True)

		row = col.row(align=True)
		row.scale_y = 1.5
		if len (conf.skin_list)>0:
			skinname = bpy.path.basename(
					conf.skin_list[sind][0])
			p = row.operator("mcprep.applyskin","Apply "+skinname)
			p.filepath = conf.skin_list[sind][1]
		else:
			row.enabled = False
			p = row.operator("mcprep.skin_swapper","No skins found")
		row = col.row(align=True)
		row.operator("mcprep.skin_swapper","Skin from file")
		row = col.row(align=True)
		row.operator("mcprep.applyusernameskin","Skin from username")

		split = layout.split()
		col = split.column(align=True)
		if not scn_props.show_settings_skin:
			col.prop(scn_props,"show_settings_skin",
					text="Advanced", icon="TRIA_RIGHT")
		else:
			col.prop(scn_props,"show_settings_skin",
					text="Advanced", icon="TRIA_DOWN")
			box = col.box()
			b_row = box.column(align=True)
			b_row.label("Skin path")
			b_row.prop(context.scene,"mcprep_skin_path", text="")
			b_row.operator("mcprep.add_skin")
			b_row.operator("mcprep.remove_skin")
			b_row.operator("mcprep.reload_skins")
			if context.mode == "OBJECT":
				row = b_row.row(align=True)
				if len (conf.rig_list_sub)==0:
					row.enabled = False
					row.operator("mcprep.spawn_with_skin","Reload mobs below")
				elif len (conf.skin_list)==0:
					row.enabled = False
					row.operator("mcprep.spawn_with_skin","Reload skins above")
				else:
					name = conf.rig_list_sub[mob_ind][1]
					datapass = conf.rig_list_sub[mob_ind][0]
					tx = "Spawn {x} with {y}".format(
								x=name, y=skinname)
					row.operator("mcprep.spawn_with_skin",tx)


class McprepSpawnPanel(bpy.types.Panel):
	"""MCprep panel for mob spawning"""
	bl_label = "Spawner"
	bl_space_type = "VIEW_3D"
	bl_region_type = "TOOLS"
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		row = self.layout.row(align=True)
		row.prop(context.scene.mcprep_props,"spawn_mode", text="")
		row.operator("mcprep.open_help", text="", icon="QUESTION").url = \
			"http://theduckcow.com/dev/blender/mcprep/mcprep-spawner/"
		addon_updater_ops.check_for_update_background()
		if context.scene.mcprep_props.spawn_mode=="mob":
			self.mob_spawner(context)
		elif context.scene.mcprep_props.spawn_mode=="meshswap":
			self.meshswap(context)

	def mob_spawner(self, context):
		scn_props = context.scene.mcprep_props

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)

		# any other conditions for needing reloading?
		if len(conf.rig_list)==0:
			col = layout.column()
			col.label("No mobs loaded")
			row2 = col.row()
			row2.scale_y = 2
			row2.operator("mcprep.reload_spawners","Reload assets", icon="ERROR")
			return

		rows = 4
		row = layout.row()
		row.prop(scn_props, "spawn_rig_category", text="")
		row = layout.row()
		row.template_list("McprepMobUiList", "",
				context.scene, "mcprep_mob_list",
				context.scene, "mcprep_mob_list_index",
				rows=rows)

		row = layout.row()
		col = row.column(align=True)
		# get which rig is selected
		if conf.rig_list_sub:
			name = conf.rig_list_sub[context.scene.mcprep_mob_list_index][1]
			datapass = conf.rig_list_sub[context.scene.mcprep_mob_list_index][0]
			col.label(datapass.split(":/:")[0])
			spawn_row = col.row(align=True)
			spawn_row.scale_y = 1.5
			p = spawn_row.operator("mcprep.mob_spawner","Spawn "+name)
			p.mcmob_type = datapass
			p = col.operator("mcprep.mob_install_menu")
			p.mob_category = scn_props.spawn_rig_category
		else:
			# other condition for reloading??/if none found
			col.label("No mobs loaded")
			row2 = col.row()
			row2.scale_y = 2
			row2.operator("mcprep.spawnpathreset","Press to reload", icon="ERROR")

		split = layout.split()
		col = split.column(align=True)
		if not scn_props.show_settings_spawner:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_RIGHT")
		else:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_DOWN")
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label("Mob spawner folder")
			b_col.prop(context.scene,"mcprep_mob_path",text="")
			b_row = box.row()
			b_col = b_row.column(align=True)
			p = b_col.operator("mcprep.openfolder", text="Open mob folder")
			p.folder = context.scene.mcprep_mob_path
			b_col.operator("mcprep.mob_uninstall")
			b_col.operator("mcprep.reload_mobs", text="Reload mobs")
			b_col.operator("mcprep.spawnpathreset")

	def meshswap(self, context):
		scn_props = context.scene.mcprep_props

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)

		# any other conditions for needing reloading?
		if len(conf.rig_list)==0:
			col = layout.column()
			col.label("No blocks loaded")
			row2 = col.row()
			row2.scale_y = 2
			row2.operator("mcprep.reload_spawners","Reload assets", icon="ERROR")
			return

		row = layout.row()
		rows = 4
		col = row.column(align=True)
		col.template_list("McprepMeshswapUiList", "",
				context.scene, "mcprep_meshswap_list",
				context.scene, "mcprep_meshswap_list_index",
				rows=rows)

		# something to directly open meshswap file??
		row = layout.row()
		name = conf.meshswap_list[context.scene.mcprep_meshswap_list_index][1]
		p = row.operator("mcprep.meshswap_spawner","Place: "+name)
		datapass = conf.meshswap_list[context.scene.mcprep_meshswap_list_index][0]
		p.meshswap_block = datapass
		p.location = context.scene.cursor_location
		# col.label(datapass.split("/")[0])

		split = layout.split()
		col = split.column(align=True)
		if not scn_props.show_settings_spawner:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_RIGHT")
		else:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_DOWN")
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label("Meshswap file")
			b_col.prop(context.scene,"meshswap_path", text="")


# -----------------------------------------------------------------------------
#	Above for UI
#	Below for registration stuff
# -----------------------------------------------------------------------------

# for custom menu registration, icon for top-level MCprep menu of shift-A
def draw_mcprepadd(self, context):
	layout = self.layout
	pcoll = conf.preview_collections["main"]
	if pcoll != "":
		my_icon = pcoll["crafting_icon"]
		layout.menu(McprepQuickMenu.bl_idname,icon_value=my_icon.icon_id)
	else:
		layout.menu(McprepQuickMenu.bl_idname)


# -----------------------------------------------
# Addon wide properties (aside from user preferences)
# -----------------------------------------------
class McprepProps(bpy.types.PropertyGroup):

	# not available here
	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

	# depreciated, keeping to prevent re-registration errors
	show_settings_material = bpy.props.BoolProperty(
		name = "show material settings", #  mcprep_showsettings
		description = "Show extra MCprep panel settings",
		default = False)
	show_settings_skin = bpy.props.BoolProperty(
		name = "show skin settings",
		description = "Show extra MCprep panel settings",
		default = False)
	show_settings_spawner = bpy.props.BoolProperty(
		name = "show spawner settings",
		description = "Show extra MCprep panel settings",
		default = False)
	use_reflections = bpy.props.BoolProperty(
		name = "Use reflections",
		description = "Allow appropriate materials to be rendered reflective",
		default = True
		)
	combine_materials = bpy.props.BoolProperty(
		name = "Combine materials",
		description = "Consolidate duplciate materials & textures",
		default = False
		)
	use_principled_shader = bpy.props.BoolProperty(
		name = "Use Principled Shader",
		description = "If available and using cycles, build materials using the principled shader",
		default = True
		)
	autoFindMissingTextures = bpy.props.BoolProperty(
		name = "Auto-find missing images",
		description = "If the texture for an existing material is missing, "+\
			"try to load from the default texturepack instead",
		default = True  # decide this behavior
		)

	# Rig settings
	spawn_rig_category = bpy.props.EnumProperty(
		name="Mob category",
		description="Category of mobs & character rigs to spawn",
		update=mobs.spawn_rigs_category_load,
		items=mobs.spawn_rigs_categories
	)
	spawn_mode = bpy.props.EnumProperty(
		name="Spawn Mode",
		description="Set mode for rig/object spawner",
		items = [('mob', 'Mob', 'Show mob spawner'),
				('meshswap', 'Meshswap', 'Show meshswap spawner')]
	)

	# World settings
	world_time = bpy.props.IntProperty(
		name="Time",
		description="Set world time. 0=Day start, 12000=nightfall",
		default=8000,
		soft_min=0,
		soft_max=24000,
		update=world_tools.world_time_update
	)


# -----------------------------------------------------------------------------
# Register functions
# -----------------------------------------------------------------------------


def register():

	bpy.types.Scene.mcprep_props = bpy.props.PointerProperty(type=McprepProps)

	# scene settings (later re-attempt to put into props group)
	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

	bpy.types.Scene.mcprep_mob_path = bpy.props.StringProperty(
		name = "Mob folder",
		description = "Folder for rigs to spawn in, saved with this blend file data",
		subtype = 'DIR_PATH',
		update = mobs.update_rig_path,
		default = addon_prefs.mob_path)
	bpy.types.Scene.mcprep_skin_path = bpy.props.StringProperty(
		name = "Skin folder",
		description = "Folder for skin textures, used in skin swapping",
		subtype = 'DIR_PATH',
		update = skin.update_skin_path,
		default = addon_prefs.skin_path)
	bpy.types.Scene.meshswap_path = bpy.props.StringProperty(
		name = "Meshswap file",
		description = "File for meshswap library",
		subtype = 'FILE_PATH',
		update = meshswap.update_meshswap_path,
		default = addon_prefs.meshswap_path)
	bpy.types.Scene.mcprep_custom_texturepack_path = bpy.props.StringProperty(
		name = "Path to texturepack",
		subtype = 'DIR_PATH',
		description = "Path to a folder containing resources and textures to use"+\
			"with material prepping",
		default=addon_prefs.custom_texturepack_path,
		)

	conf.v = addon_prefs.verbose
	bpy.types.INFO_MT_add.append(draw_mcprepadd)


def unregister():

	bpy.types.INFO_MT_add.remove(draw_mcprepadd)

	del bpy.types.Scene.mcprep_props
	del bpy.types.Scene.mcprep_mob_path
	del bpy.types.Scene.mcprep_skin_path
