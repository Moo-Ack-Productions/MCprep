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
from .spawner import spawn_util
from . import world_tools
from . import addon_updater_ops
from . import tracking
from .materials.skin import update_skin_path
from .materials.generate import update_mcprep_texturepack_path
from .materials import material_manager
# from .import_bridge import bridge

# blender 2.7 vs 2.8 icon selections
LOAD_FACTORY = 'LOOP_BACK' if util.bv28() else 'LOAD_FACTORY'
HAND_ICON = 'FILE_REFRESH' if util.bv28() else 'HAND'
OPT_IN =  'URL' if util.bv28() else 'HAND'

# -----------------------------------------------------------------------------
#	Above for class functions/operators
#	Below for UI
# -----------------------------------------------------------------------------


class MCPREP_MT_mob_spawner(bpy.types.Menu):
	"""Shift-A menu in the 3D view"""
	bl_label = "Mob Spawner"
	bl_idname = "MCPREP_MT_mob_spawner"
	bl_description = "Menu for placing in the shift-A add object menu"

	def draw(self, context):
		layout = self.layout
		scn_props = context.scene.mcprep_props

		# if mobs not loaded yet
		if not scn_props.mob_list_all:
			row = layout.row()
			row.operator("mcprep.reload_mobs", text="Load mobs",
				icon=HAND_ICON)
			row.scale_y = 2
			row.alignment = 'CENTER'
			return

		keys = sorted(scn_props.mob_list_all.keys())
		for mobkey in keys:
			# show icon if available
			mob = scn_props.mob_list_all[mobkey]
			icn = "mob-{}".format(mob.index)
			if conf.use_icons and icn in conf.preview_collections["mobs"]:
				ops =layout.operator("mcprep.mob_spawner", text=mob.name,
					icon_value=conf.preview_collections["mobs"][icn].icon_id)
			elif conf.use_icons:
				ops = layout.operator("mcprep.mob_spawner", text=mob.name,
					icon="BLANK1")
			else:
				ops = layout.operator("mcprep.mob_spawner", text=mob.name)
			ops.mcmob_type = mob.mcmob_type


class MCPREP_MT_meshswap_place(bpy.types.Menu):
	"""Menu for all the meshswap objects"""
	bl_label = "Meshswap Objects"
	bl_idname = "MCPREP_MT_meshswap_place"

	def draw(self, context):
		layout = self.layout
		meshswap_blocks = meshswap.getMeshswapList(context)
		for blockset in meshswap_blocks:
			# do some kind of check for if no blocks found
			icn = "BLANK1"
			if blockset[0].startswith("Group"):
				icn = "GROUP"

			opr = layout.operator(
				"mcprep.meshswap_spawner",
				text=blockset[1],
				icon=icn
			)
			opr.block = blockset[0]
			opr.location = util.get_cuser_location(context)


class MCPREP_MT_item_spawn(bpy.types.Menu):
	"""Menu for loaded item spawners"""
	bl_label = "Item Spawner"
	bl_idname = "MCPREP_MT_item_spawn"

	def draw(self, context):
		layout = self.layout
		for item in context.scene.mcprep_props.item_list:
			icn = "item-{}".format(item.index)
			if conf.use_icons and icn in conf.preview_collections["items"]:
				ops =layout.operator("mcprep.spawn_item", text=item.name,
					icon_value=conf.preview_collections["items"][icn].icon_id)
			elif conf.use_icons:
				ops = layout.operator("mcprep.spawn_item", text=item.name,
					icon="BLANK1")
			else:
				ops = layout.operator("mcprep.spawn_item", text=item.name)
			ops.filepath = item.path


class MCPREP_MT_3dview_add(bpy.types.Menu):
	"""MCprep Shift-A menu for spawners"""
	bl_label = "MCprep"
	bl_idname = "MCPREP_MT_3dview_add"

	def draw(self, context):
		layout = self.layout
		props = context.scene.mcprep_props

		if conf.preview_collections["main"] != "":
			spawner_icon = conf.preview_collections["main"]["spawner_icon"]
			grass_icon = conf.preview_collections["main"]["grass_icon"]
			sword_icon = conf.preview_collections["main"]["sword_icon"]
		else:
			spawner_icon=None
			grass_icon=None
			sword_icon=None

		all_loaded = props.mob_list and props.meshswap_list and props.item_list
		if not conf.loaded_all_spawners and not all_loaded:
			row = layout.row()
			row.operator("mcprep.reload_spawners", text="Load spawners",
				icon=HAND_ICON)
			row.scale_y = 2
			row.alignment = 'CENTER'
			return

		if spawner_icon is not None:
			layout.menu(MCPREP_MT_mob_spawner.bl_idname,
				icon_value=spawner_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_mob_spawner.bl_idname)
		if grass_icon is not None:
			layout.menu(MCPREP_MT_meshswap_place.bl_idname,
				icon_value=grass_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_meshswap_place.bl_idname)
		if sword_icon is not None:
			layout.menu(MCPREP_MT_item_spawn.bl_idname,
				icon_value=sword_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_item_spawn.bl_idname)


def mineways_update(self, context):
	"""For updating the mineways path on OSX."""
	if ".app/" in self.open_mineways_path:
		# will run twice inherently
		temp = self.open_mineways_path.split(".app/")[0]
		self.open_mineways_path = temp+".app"
	return


class McprepPreference(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	def change_verbose(self, context):
		conf.v = self.verbose

	meshswap_path = bpy.props.StringProperty(
		name = "Meshswap path",
		description = ("Default path to the meshswap asset file, for "
			"meshswapable objects and groups"),
		subtype = 'FILE_PATH',
		default = scriptdir + "/MCprep_resources/mcprep_meshSwap.blend")
	mob_path = bpy.props.StringProperty(
		name = "Mob path",
		description = "Default folder for rig loads/spawns in new blender instances",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/rigs/")
	custom_texturepack_path = bpy.props.StringProperty(
		name = "Texture pack path",
		description = ("Path to a folder containing resources and textures to use "
			"with material prepping"),
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/resourcepacks/mcprep_default/")
	skin_path = bpy.props.StringProperty(
		name = "Skin path",
		description = "Folder for skin textures, used in skin swapping",
		subtype = 'DIR_PATH',
		default = scriptdir + "/MCprep_resources/skins/")
	world_obj_path = bpy.props.StringProperty(
		name = "World Folder",
		description = ("Default folder for opening world objs from programs "
			"like jmc2obj or Mineways"),
		subtype = 'DIR_PATH',
		default = "//")
	MCprep_groupAppendLayer = bpy.props.IntProperty(
		name="Group Append Layer",
		description=("When groups are appended instead of linked, "
				"the objects part of the group will be placed in this "
				"layer, 0 means same as active layer"),
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
				('tracker_updater', 'Tracking/Updater',
					'Change tracking and updating settings')],
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
	save_folder = bpy.props.StringProperty(
		name = "MC saves folder",
		description = ("Folder containing Minecraft world saves directories, "
			"for the direct import bridge"),
		subtype = 'FILE_PATH',
		default = '')

	# addon updater preferences

	auto_check_update = bpy.props.BoolProperty(
		name = "Auto-check for Update",
		description = "If enabled, auto-check for updates using an interval",
		default = True,
		)
	updater_interval_months = bpy.props.IntProperty(
		name='Months',
		description = "Number of months between checking for updates",
		default=0,
		min=0
		)
	updater_interval_days = bpy.props.IntProperty(
		name='Days',
		description = "Number of days between checking for updates",
		default=1,
		min=0,
		)
	updater_interval_hours = bpy.props.IntProperty(
		name='Hours',
		description = "Number of hours between checking for updates",
		default=0,
		min=0,
		max=23
		)
	updater_interval_minutes = bpy.props.IntProperty(
		name='Minutes',
		description = "Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59
		)

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.prop(self, "preferences_tab", expand=True)

		factor_width = 0.3
		if util.bv28():
			factor_width = 0.3

		if self.preferences_tab == "settings":

			row = layout.row()
			row.scale_y=0.7
			row.label(text="World Importing & Meshswapping")
			box = layout.box()
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Default Exporter:")
			col = split.column()
			col.prop(self, "MCprep_exporter_type", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="jmc2obj executable")
			col = split.column()
			col.prop(self, "open_jmc2obj_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Mineways executable")
			col = split.column()
			col.prop(self, "open_mineways_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="World OBJ Exports Folder")
			col = split.column()
			col.prop(self, "world_obj_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Meshwap assets")
			col = split.column()
			col.prop(self, "meshswap_path", text="")
			if not os.path.isfile(bpy.path.abspath(self.meshswap_path)):
				row = box.row()
				row.label(text="MeshSwap file not found", icon="ERROR")

			row = layout.row()
			row.scale_y=0.7
			row.label(text="Texture / Resource packs")
			box = layout.box()
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Texture pack folder")
			col = split.column()
			col.prop(self, "custom_texturepack_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Install to folder")
			# col = split.column()
			# col.operator("mcprep.skin_swapper", text="Install resource pack")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open texture pack folder")
			p.folder = self.custom_texturepack_path

			row = layout.row()
			row.scale_y=0.7
			row.label(text="Mob spawning")
			box = layout.box()
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Rig Folder")
			col = split.column()
			col.prop(self, "mob_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Select/install mobs")
			col = split.column()
			col.operator("mcprep.mob_install_menu", text="Install file for mob spawning")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open rig folder")
			p.folder = self.mob_path

			row = layout.row()
			row.scale_y=0.7
			row.label(text="Skin swapping")
			box = layout.box()
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Skin Folder")
			col = split.column()
			col.prop(self, "skin_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Install skins")
			col = split.column()
			col.operator("mcprep.add_skin", text="Install skin file for swapping")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open skin folder")
			p.folder = self.skin_path

			# misc settings
			row = layout.row()
			col = row.column()
			col.prop(self, "verbose")
			row = layout.row()

		elif self.preferences_tab == "tutorials":
			layout.label(text="Unsure on how to use the addon? Check out these resources")
			col = layout.column()
			col.scale_y = 2
			col.operator("wm.url_open",
					text="MCprep page for instructions and updates",
					icon="WORLD").url = "https://theduckcow.com/dev/blender/mcprep/"
			row = layout.row()
			row.scale_y = 1.5
			row.operator("wm.url_open",
					text="Import Minecraft worlds").url = \
					"https://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"
			row.operator("wm.url_open",
					text="Mob (rig) spawning").url = \
					"https://theduckcow.com/dev/blender/mcprep/mcprep-spawner/"
			row.operator("wm.url_open",
					text="Skin swapping").url = \
					"https://theduckcow.com/dev/blender/mcprep/skin-swapping/"
			row = layout.row()
			row.scale_y = 1.5
			row.operator("wm.url_open",
					text="jmc2obj/Mineways").url = \
					"https://theduckcow.com/dev/blender/mcprep/setup-world-exporters/"
			row.operator("wm.url_open",
					text="World Tools").url = \
					"https://theduckcow.com/dev/blender/mcprep/world-tools/"
			row.operator("wm.url_open",
					text="Tutorial Series").url = \
					"https://bit.ly/MCprepTutorials"

		elif self.preferences_tab == "tracker_updater":
			layout = self.layout
			row = layout.row()
			box = row.box()
			brow = box.row()
			brow.label(text="Anonymous user tracking settings")

			brow = box.row()
			bcol = brow.column()
			bcol.scale_y = 2

			if tracking.Tracker.tracking_enabled is False:
				bcol.operator("mcprep.toggle_enable_tracking",
						text="Opt into anonymous usage tracking",
						icon=OPT_IN)
			else:
				bcol.operator("mcprep.toggle_enable_tracking",
						text="Opt OUT of anonymous usage tracking",
						icon="CANCEL")

			bcol = brow.column()
			bcol.label(text="For info on anonymous usage tracking:")
			brow = box.row()
			bcol.operator("wm.url_open", text="Open the Privacy Policy"
				).url = "https://theduckcow.com/privacy-policy"

			# updater draw function
			addon_updater_ops.update_settings_ui(self,context)
		if not util.bv28():
			layout.label(text="Don't forget to save user preferences!")


class MCPREP_PT_world_imports(bpy.types.Panel):
	"""World importing related settings and tools"""
	bl_label = "World Imports"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if not util.bv28() else 'UI'
	# bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		addon_prefs = util.get_user_preferences(context)
		scn_props = context.scene.mcprep_props

		# check for update in background thread if appropraite
		addon_updater_ops.check_for_update_background()

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		row = col.row()
		row.label(text="World exporter")
		row.operator("mcprep.open_help", text="", icon="QUESTION", emboss=False).url = \
			"https://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"
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
		if util.bv28():
			# custom operator for splitting via mats after importing
			col.operator("mcprep.import_world_split",
				text="OBJ world import").filepath = wpath
		else:
			col.operator("import_scene.obj",
				text="OBJ world import").filepath = wpath

		split = layout.split()
		col = split.column(align=True)
		col.label(text="MCprep tools")
		col.operator("mcprep.prep_materials", text="Prep Materials")
		p = col.operator("mcprep.swap_texture_pack")
		p.filepath = context.scene.mcprep_texturepack_path
		if context.mode == "OBJECT":
			col.operator("mcprep.meshswap", text="Mesh Swap")
			if addon_prefs.MCprep_exporter_type == "(choose)":
				col.label(text="Select exporter!",icon='ERROR')
		if context.mode == 'EDIT_MESH':
			col.operator("mcprep.scale_uv")
			col.operator("mcprep.select_alpha_faces")

		#the UV's pixels into actual 3D geometry (but same material, or modified to fit)
		#col.operator("object.solidify_pixels", text="Solidify Pixels", icon='MOD_SOLIDIFY')
		split = layout.split()
		col = split.column(align=True)

		# Advanced material settings
		view27 = ['TEXTURED','MATEIRAL','RENDERED']
		view28 = ['SOLID', 'MATERIAL', 'RENDERED']
		if not util.bv28() and util.viewport_textured(context) is True and \
				util.get_preferences(context).system.use_mipmaps is False and \
				context.space_data.viewport_shade in view27:
			row = col.row(align=True)
			row.enabled = False
			row.operator("mcprep.improve_ui",
					text="(UI already improved)", icon='SETTINGS')
		elif util.bv28() and util.viewport_textured(context) is True and \
				context.scene.display.shading.type in view28 and \
				context.scene.display.shading.color_type != "TEXTURE" and \
				context.scene.display.shading.background_type == "WORLD":
			row = col.row(align=True)
			row.enabled = False
			row.operator("mcprep.improve_ui",
					text="(UI already improved)", icon='SETTINGS')
		else:
			col.operator("mcprep.improve_ui",
					text="Improve UI", icon='SETTINGS')

		row = col.row(align=True)
		if not scn_props.show_settings_material:
			row.prop(scn_props,"show_settings_material",
					text="Advanced", icon="TRIA_RIGHT")
			row.operator("mcprep.open_preferences",
					text="", icon="PREFERENCES").tab = "settings"
		else:
			row.prop(scn_props,"show_settings_material",
					text="Advanced", icon="TRIA_DOWN")
			row.operator("mcprep.open_preferences",
					text="", icon="PREFERENCES").tab = "settings"
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label(text="Texture pack folder")
			row = b_col.row(align=True)
			row.prop(context.scene, "mcprep_texturepack_path", text="")
			row.operator("mcprep.reset_texture_path", text="", icon=LOAD_FACTORY)

			b_row = box.row()
			b_col = b_row.column(align=True)
			b_col.operator("mcprep.sync_materials")
			b_col.operator("mcprep.replace_missing_textures")
			b_col.operator("mcprep.animate_textures")
			# TODO: operator to make all local, all packed, or set to other location
			b_col.operator("mcprep.combine_materials",
					text="Combine Materials").selection_only=True
			if bpy.app.version > (2,77):
				b_col.operator("mcprep.combine_images",text="Combine Images")

			b_col.label(text="Meshswap source:")
			subrow = b_col.row(align=True)
			subrow.prop(context.scene, "meshswap_path", text="")
			subrow.operator("mcprep.meshswap_path_reset", icon=LOAD_FACTORY, text="")
			if not context.scene.meshswap_path.lower().endswith('.blend'):
				b_col.label(text="MeshSwap file must be .blend", icon="ERROR")
			if not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
				b_col.label(text="MeshSwap file not found", icon="ERROR")

		layout = self.layout # clear out the box formatting
		split = layout.split()
		row = split.row(align=True)

		# show update ready if available
		addon_updater_ops.update_notice_box_ui(self, context)


class MCPREP_PT_bridge(bpy.types.Panel):
	"""MCprep panel for directly importing and reloading minecraft saves"""
	bl_label = "World Bridge"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'TOOLS' if not util.bv28() else 'UI'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		bridge.panel_draw(self, context)


class MCPREP_PT_world_tools(bpy.types.Panel):
	"""World settings and tools"""
	bl_label = "World Tools"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if not util.bv28() else 'UI'
	bl_category = "MCprep"

	def draw(self, context):
		layout = self.layout
		rw = layout.row()
		col = rw.column()
		row = col.row(align=True)
		row.label(text="World settings and lighting") # world time
		row.operator("mcprep.open_help", text="", icon="QUESTION", emboss=False
			).url = "https://theduckcow.com/dev/blender/mcprep/world-tools/"

		rw = layout.row()
		col = rw.column(align=True)
		col.operator("mcprep.add_mc_sky")
		col.operator("mcprep.world")

		layout.split()
		rw = layout.row()
		col = rw.column(align=True)
		obj = world_tools.get_time_object()
		col.label(text="Time of day")
		if obj and "MCprepHour" in obj:
			time = obj["MCprepHour"]
			col.prop(
				obj,
				'["MCprepHour"]',
				text="")
			col.label(text="{h}:{m}, day {d}".format(
				h=str(int(time%24 - time%1)).zfill(2),
				m=str(int(time%1 * 60)).zfill(2),
				d=int((time - time%24) / 24)
				))
		else:
			box = col.box()
			subcol = box.column()
			subcol.scale_y = 0.8
			subcol.label(text="No time controller,")
			subcol.label(text="add dynamic MC world.")
		# col.label(text="World setup")
		# col.operator("mcprep.world")
		# col.operator("mcprep.world", text="Add clouds")
		# col.operator("mcprep.world", text="Set Weather")


class MCPREP_PT_skins(bpy.types.Panel):
	"""MCprep panel for skin swapping"""
	bl_label = "Skin Swapper"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS' if not util.bv28() else 'UI'
	bl_category = "MCprep"

	def draw(self, context):
		layout = self.layout
		scn_props = context.scene.mcprep_props
		sind = context.scene.mcprep_skins_list_index
		mob_ind = context.scene.mcprep_props.mob_list_index
		skinname = None

		row = layout.row()
		row.label(text="Select skin")
		row.operator("mcprep.open_help", text="", icon="QUESTION", emboss=False
			).url = "https://theduckcow.com/dev/blender/mcprep/skin-swapping/"

		# set size of UIlist
		row = layout.row()
		col = row.column()

		is_sortable = len(conf.skin_list) > 1
		rows = 1
		if (is_sortable):
			rows = 4

		# any other conditions for needing reloading?
		if not conf.skin_list:
			col = layout.column()
			col.label(text="No skins found/loaded")
			p = col.operator("mcprep.reload_skins",
				text="Press to reload", icon="ERROR")
		elif conf.skin_list and len(conf.skin_list) <= sind:
			col = layout.column()
			col.label(text="Reload skins")
			p = col.operator("mcprep.reload_skins",
				text="Press to reload", icon="ERROR")
		else:
			col.template_list("MCPREP_UL_skins", "",
					context.scene, "mcprep_skins_list",
					context.scene, "mcprep_skins_list_index",
					rows=rows)

			col = layout.column(align=True)

			row = col.row(align=True)
			row.scale_y = 1.5
			if conf.skin_list:
				skinname = bpy.path.basename(
						conf.skin_list[sind][0])
				p = row.operator("mcprep.applyskin", text="Apply "+skinname)
				p.filepath = conf.skin_list[sind][1]
			else:
				row.enabled = False
				p = row.operator("mcprep.skin_swapper", text="No skins found")
			row = col.row(align=True)
			row.operator("mcprep.skin_swapper", text="Skin from file")
			row = col.row(align=True)
			row.operator("mcprep.applyusernameskin", text="Skin from username")

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		if not scn_props.show_settings_skin:
			row.prop(scn_props,"show_settings_skin",
					text="Advanced", icon="TRIA_RIGHT")
			row.operator("mcprep.open_preferences",
					text="", icon="PREFERENCES").tab = "settings"
		else:
			row.prop(scn_props,"show_settings_skin",
					text="Advanced", icon="TRIA_DOWN")
			row.operator("mcprep.open_preferences",
					text="", icon="PREFERENCES").tab = "settings"
			box = col.box()
			b_row = box.column(align=True)
			b_row.label(text="Skin path")
			b_subrow = b_row.row(align=True)
			b_subrow.prop(context.scene,"mcprep_skin_path", text="")
			b_subrow.operator("mcprep.skin_path_reset", icon=LOAD_FACTORY, text="")
			b_row.operator("mcprep.add_skin")
			b_row.operator("mcprep.remove_skin")
			b_row.operator("mcprep.download_username_list")
			b_row.operator("mcprep.reload_skins")
			if context.mode == "OBJECT" and skinname:
				row = b_row.row(align=True)
				if not scn_props.mob_list:
					row.enabled = False
					row.operator("mcprep.spawn_with_skin", text="Reload mobs below")
				elif not conf.skin_list:
					row.enabled = False
					row.operator("mcprep.spawn_with_skin", text="Reload skins above")
				else:
					name = scn_props.mob_list[mob_ind].name
					datapass = scn_props.mob_list[mob_ind].mcmob_type
					tx = "Spawn {x} with {y}".format(
								x=name, y=skinname)
					row.operator("mcprep.spawn_with_skin", text=tx)


class MCPREP_PT_spawn(bpy.types.Panel):
	"""MCprep panel for mob spawning"""
	bl_label = "Spawner"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'TOOLS' if not util.bv28() else 'UI'
	bl_category = "MCprep"

	def draw(self, context):
		if context.mode != "OBJECT":
			col = self.layout.column(align=True)
			col.label(text="Enter object mode", icon="ERROR")
			col.label(text="to use spawner", icon="BLANK1")
			col.operator("object.mode_set").mode="OBJECT"
			col.label(text="")
			return
		row = self.layout.row(align=True)
		row.prop(context.scene.mcprep_props,"spawn_mode", expand=True)
		row.operator("mcprep.open_help", text="", icon="QUESTION"
			).url = "https://theduckcow.com/dev/blender/mcprep/mcprep-spawner/"
		addon_updater_ops.check_for_update_background()
		if context.scene.mcprep_props.spawn_mode=="mob":
			self.mob_spawner(context)
		elif context.scene.mcprep_props.spawn_mode=="meshswap":
			self.meshswap(context)
		elif context.scene.mcprep_props.spawn_mode=="item":
			self.item_spawner(context)

	def mob_spawner(self, context):
		scn_props = context.scene.mcprep_props

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)

		row = col.row()
		row.prop(scn_props, "spawn_rig_category", text="")
		if scn_props.mob_list:
			row = col.row()
			row.template_list("MCPREP_UL_mob", "",
					scn_props, "mob_list",
					scn_props, "mob_list_index",
					rows=4)
		elif scn_props.mob_list_all:
			box = col.box()
			b_row = box.row()
			b_row.label(text="")
			b_col = box.column()
			b_col.scale_y = 0.7
			b_col.label(text="No mobs in category,")
			b_col.label(text="install a rig below or")
			b_col.label(text="copy file to folder.")
			b_row = box.row()
			b_row.label(text="")
		else:
			box = col.box()
			b_row = box.row()
			b_row.label(text="No mobs loaded")
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.reload_spawners",
				text="Reload assets", icon="ERROR")

		# get which rig is selected
		if scn_props.mob_list:
			name = scn_props.mob_list[scn_props.mob_list_index].name
			mcmob_type = scn_props.mob_list[scn_props.mob_list_index].mcmob_type
		else:
			name = ""
			mcmob_type = ""
		col = layout.column(align=True)
		row = col.row(align=True)
		row.scale_y = 1.5
		row.enabled = len(scn_props.mob_list)>0
		p = row.operator("mcprep.mob_spawner", text="Spawn "+name)
		if mcmob_type:
			p.mcmob_type = mcmob_type
		p = col.operator("mcprep.mob_install_menu")
		p.mob_category = scn_props.spawn_rig_category

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		if not scn_props.show_settings_spawner:
			row.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_RIGHT")
			row.operator("mcprep.open_preferences",
					text="", icon="PREFERENCES").tab = "settings"
		else:
			row.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_DOWN")
			row.operator("mcprep.open_preferences",
					text="", icon="PREFERENCES").tab = "settings"
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label(text="Mob spawner folder")
			subrow = b_col.row(align=True)
			subrow.prop(context.scene, "mcprep_mob_path", text="")
			subrow.operator("mcprep.spawn_path_reset", icon=LOAD_FACTORY, text="")
			b_row = box.row()
			b_col = b_row.column(align=True)
			b_col.operator("mcprep.openfolder", text="Open mob folder"
				).folder = context.scene.mcprep_mob_path

			if not scn_props.mob_list:
				b_col.operator("mcprep.mob_install_icon")
			else:
				icon_index = scn_props.mob_list[scn_props.mob_list_index].index
				if "mob-{}".format(icon_index) in conf.preview_collections["mobs"]:
					b_col.operator("mcprep.mob_install_icon", text="Change mob icon")
				else:
					b_col.operator("mcprep.mob_install_icon")
			b_col.operator("mcprep.mob_uninstall")
			b_col.operator("mcprep.reload_mobs", text="Reload mobs")
			b_col.label(text=mcmob_type)

	def meshswap(self, context):
		scn_props = context.scene.mcprep_props

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)

		if scn_props.meshswap_list:
			col.template_list("MCPREP_UL_meshswap", "",
					scn_props, "meshswap_list",
					scn_props, "meshswap_list_index",
					rows=4)
			# col.label(text=datapass.split("/")[0])
		elif not context.scene.meshswap_path.lower().endswith('.blend'):
			box = col.box()
			b_row = box.row()
			b_row.label(text="Meshswap file must be a .blend")
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.meshswap_path_reset", icon=LOAD_FACTORY,
				text="Reset meshswap path")
		elif not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
			box = col.box()
			b_row = box.row()
			b_row.label(text="Meshswap file not found")
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.meshswap_path_reset", icon=LOAD_FACTORY,
				text="Reset meshswap path")
		else:
			box = col.box()
			b_row = box.row()
			b_row.label(text="No blocks loaded")
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.reload_spawners",
				text="Reload assets", icon="ERROR")

		col = layout.column(align=True)
		row = col.row()
		row.scale_y = 1.5
		row.enabled = len(scn_props.meshswap_list)>0
		if scn_props.meshswap_list:
			name = scn_props.meshswap_list[scn_props.meshswap_list_index].name
			block = scn_props.meshswap_list[scn_props.meshswap_list_index].block
			p = row.operator("mcprep.meshswap_spawner", text="Place: "+name)
			p.block = block
			p.location = util.get_cuser_location(context)
		else:
			row.operator("mcprep.meshswap_spawner", text="Place block")
		# something to directly open meshswap file??

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)

		if not scn_props.show_settings_spawner:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_RIGHT")
		else:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_DOWN")
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label(text="Meshswap file")
			subrow = b_col.row(align=True)
			subrow.prop(context.scene, "meshswap_path", text="")
			subrow.operator("mcprep.meshswap_path_reset", icon=LOAD_FACTORY, text="")
			if not context.scene.meshswap_path.lower().endswith('.blend'):
				b_col.label(text="MeshSwap file must be a .blend", icon="ERROR")
			elif not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
				b_col.label(text="MeshSwap file not found", icon="ERROR")
			b_row = box.row()
			b_col = b_row.column(align=True)
			b_col.operator("mcprep.reload_meshswap")

	def item_spawner(self, context):
		"""Code for drawing the item spawner"""
		scn_props = context.scene.mcprep_props

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)

		if scn_props.item_list:
			col.template_list("MCPREP_UL_item", "",
						scn_props, "item_list",
						scn_props, "item_list_index",
						rows=4)
			col = layout.column(align=True)
			row = col.row(align=True)
			row.scale_y = 1.5
			name = scn_props.item_list[scn_props.item_list_index].name
			row.operator("mcprep.spawn_item", text="Place: "+name)
			row = col.row(align=True)
			row.operator("mcprep.spawn_item_file")
		else:
			box = col.box()
			b_row = box.row()
			b_row.label(text="No items loaded")
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.reload_spawners",
				text="Reload assets", icon="ERROR")

			col = layout.column(align=True)
			col.enabled = False
			row = col.row(align=True)
			row.scale_y = 1.5
			row.operator("mcprep.spawn_item", text="Place item")
			row = col.row(align=True)
			row.operator("mcprep.spawn_item_file")

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)

		if not scn_props.show_settings_spawner:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_RIGHT")
		else:
			col.prop(scn_props,"show_settings_spawner",
					text="Advanced", icon="TRIA_DOWN")
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label(text="Resource pack")
			subrow = b_col.row(align=True)
			subrow.prop(context.scene, "mcprep_texturepack_path", text="")
			subrow.operator("mcprep.reset_texture_path",
				icon=LOAD_FACTORY, text="")
			b_row = box.row()
			b_col = b_row.column(align=True)
			b_col.operator("mcprep.reload_items")


class MCPREP_PT_materials(bpy.types.Panel):
	"""MCprep panel for materials"""
	bl_label = "MCprep materials"
	bl_space_type = "PROPERTIES"
	bl_region_type = 'WINDOW'
	bl_context = "material"

	def draw(self, context):
		"""Code for drawing the material generator"""
		scn_props = context.scene.mcprep_props

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)

		if scn_props.material_list:
			col.template_list("MCPREP_UL_material", "",
						scn_props, "material_list",
						scn_props, "material_list_index",
						rows=4)
			col = layout.column(align=True)
			row = col.row(align=True)
			row.scale_y = 1.5
			name = scn_props.material_list[scn_props.material_list_index].name
			row.operator("mcprep.load_material", text="Load: "+name)
		else:
			box = col.box()
			b_row = box.row()
			b_row.label(text="No materials loaded")
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.reload_materials", icon="ERROR")

			col = layout.column(align=True)
			col.enabled = False
			row = col.row(align=True)
			row.scale_y = 1.5
			row.operator("mcprep.load_material", text="Load material")


class MCPREP_PT_materials_subsettings(bpy.types.Panel):
	"""MCprep panel for advanced material settings and functions"""
	bl_label = "Advanced"
	bl_parent_id = "MCPREP_PT_materials"
	bl_space_type = "PROPERTIES"
	bl_region_type = 'WINDOW'
	bl_context = "material"

	def draw(self, context):
		b_row = self.layout.row()
		b_col = b_row.column(align=False)
		b_col.label(text="Resource pack")
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "mcprep_texturepack_path", text="")
		subrow.operator("mcprep.reset_texture_path",
			icon=LOAD_FACTORY, text="")
		b_row = self.layout.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_materials")


# -----------------------------------------------------------------------------
#	Above for UI
#	Below for registration stuff
# -----------------------------------------------------------------------------


def draw_mcprepadd(self, context):
	"""Append to Shift+A, icon for top-level MCprep section."""
	layout = self.layout
	pcoll = conf.preview_collections["main"]
	if pcoll != "":
		my_icon = pcoll["crafting_icon"]
		layout.menu(MCPREP_MT_3dview_add.bl_idname, icon_value=my_icon.icon_id)
	else:
		layout.menu(MCPREP_MT_3dview_add.bl_idname)


def mcprep_uv_tools(self, context):
	"""Appended to UV tools in UV image editor tab, in object edit mode."""
	layout = self.layout
	layout.separator()
	layout.label(text="MCprep tools")
	col = layout.column(align=True)
	col.operator("mcprep.scale_uv")
	col.operator("mcprep.select_alpha_faces")


def mcprep_image_tools(self, context):
	"""Tools that will display in object mode in the UV image editor."""
	row = self.layout.row()
	img = context.space_data.image
	if img:
		path = context.space_data.image.filepath
	else:
		path = ""
	if not path:
		txt = "(Save image first)"
		row.enabled = False
	else:
		txt = "Spawn as item"
	if not img:
		row.enabled = False
	if conf.preview_collections["main"] != "":
		sword_icon = conf.preview_collections["main"]["sword_icon"]
	else:
		sword_icon = None

	if sword_icon:
		row.operator("mcprep.spawn_item", text=txt,
			icon_value=sword_icon.icon_id).filepath = path
	else:
		row.operator("mcprep.spawn_item", text=txt).filepath = path


# -----------------------------------------------
# Addon wide properties (aside from user preferences)
# -----------------------------------------------


class McprepProps(bpy.types.PropertyGroup):
	"""Properties saved to an individual scene"""

	# not available here
	addon_prefs = util.get_user_preferences()

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
				('meshswap', 'MeshSwap', 'Show MeshSwap spawner'),
				('item', 'Items', 'Show item spawner')]
	)

	# spawn lists
	mob_list = bpy.props.CollectionProperty(type=spawn_util.ListMobAssets)
	mob_list_index = bpy.props.IntProperty(default=0)
	mob_list_all = bpy.props.CollectionProperty(type=spawn_util.ListMobAssetsAll)
	meshswap_list = bpy.props.CollectionProperty(type=spawn_util.ListMeshswapAssets)
	meshswap_list_index = bpy.props.IntProperty(default=0)
	item_list = bpy.props.CollectionProperty(type=spawn_util.ListItemAssets)
	item_list_index = bpy.props.IntProperty(default=0)
	material_list = bpy.props.CollectionProperty(type=material_manager.ListMaterials)
	material_list_index = bpy.props.IntProperty(default=0)


# -----------------------------------------------------------------------------
# Register functions
# -----------------------------------------------------------------------------


classes = (
	McprepPreference,
	McprepProps,
	MCPREP_MT_mob_spawner,
	MCPREP_MT_meshswap_place,
	MCPREP_MT_item_spawn,
	MCPREP_MT_3dview_add,
	MCPREP_PT_world_imports,
	# MCPREP_PT_bridge,
	MCPREP_PT_world_tools,
	MCPREP_PT_skins,
	MCPREP_PT_spawn,
	MCPREP_PT_materials,
	MCPREP_PT_materials_subsettings,
)


def register():
	for cls in classes:
		util.make_annotations(cls)
		bpy.utils.register_class(cls)

	bpy.types.Scene.mcprep_props = bpy.props.PointerProperty(type=McprepProps)

	# scene settings (later re-attempt to put into props group)
	addon_prefs = util.get_user_preferences()

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
		update = update_skin_path,
		default = addon_prefs.skin_path)
	bpy.types.Scene.meshswap_path = bpy.props.StringProperty(
		name = "Meshswap file",
		description = "File for meshswap library",
		subtype = 'FILE_PATH',
		update = meshswap.update_meshswap_path,
		default = addon_prefs.meshswap_path)
	bpy.types.Scene.mcprep_texturepack_path = bpy.props.StringProperty(
		name = "Path to texture pack",
		subtype = 'DIR_PATH',
		description = ("Path to a folder containing resources and textures to use "
			"with material prepping"),
		update=update_mcprep_texturepack_path,
		default=addon_prefs.custom_texturepack_path
		)

	conf.v = addon_prefs.verbose
	if hasattr(bpy.types, "INFO_MT_add"): # 2.7
		bpy.types.INFO_MT_add.append(draw_mcprepadd)
	elif hasattr(bpy.types, "VIEW3D_MT_add"): # 2.8
		bpy.types.VIEW3D_MT_add.append(draw_mcprepadd)

	if hasattr(bpy.types, "IMAGE_PT_tools_transform_uvs"): # 2.7 only
		bpy.types.IMAGE_PT_tools_transform_uvs.append(mcprep_uv_tools)
	if hasattr(bpy.types, "IMAGE_MT_uvs"): # 2.8 *and* 2.7
		# this is a dropdown menu for UVs, not a panel
		bpy.types.IMAGE_MT_uvs.append(mcprep_uv_tools)
	# bpy.types.IMAGE_MT_image.append(mcprep_image_tools) # crashes, re-do ops


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	if hasattr(bpy.types, "INFO_MT_add"): # 2.7
		bpy.types.INFO_MT_add.remove(draw_mcprepadd)
	elif hasattr(bpy.types, "VIEW3D_MT_add"): # 2.8
		bpy.types.VIEW3D_MT_add.remove(draw_mcprepadd)

	if hasattr(bpy.types, "IMAGE_PT_tools_transform_uvs"): # 2.7
		bpy.types.IMAGE_PT_tools_transform_uvs.remove(mcprep_uv_tools)
	if hasattr(bpy.types, "IMAGE_MT_uvs"): # 2.8 *and* 2.7
		bpy.types.IMAGE_MT_uvs.remove(mcprep_uv_tools)
	# bpy.types.IMAGE_MT_image.remove(mcprep_image_tools)

	del bpy.types.Scene.mcprep_props
	del bpy.types.Scene.mcprep_mob_path
	del bpy.types.Scene.meshswap_path
	del bpy.types.Scene.mcprep_skin_path
	del bpy.types.Scene.mcprep_texturepack_path
