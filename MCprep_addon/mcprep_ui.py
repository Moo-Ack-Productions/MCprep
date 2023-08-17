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
import time

import bpy

# addon imports
from . import addon_updater_ops
from . import conf
from . import optimize_scene
from . import tracking
from . import util
from . import world_tools
from . import translate_enum
from .materials import material_manager
from .materials.generate import update_mcprep_texturepack_path
from .materials.skin import update_skin_path
from .spawner import effects
from .spawner import entities
from .spawner import mcmodel
from .spawner import meshswap
from .spawner import mobs
from .spawner import spawn_util
from .conf import env
from .translate_enum import TranslateKeys as TE
# from .import_bridge import bridge

# blender 2.8 icon selections
LOAD_FACTORY = 'LOOP_BACK'
HAND_ICON = 'FILE_REFRESH'
OPT_IN = 'URL'


def addon_just_updated():
	"""Indicates an addon was updated mid session, to force a user restart.

	Put into UI calls, therefore called often and should lightweight.
	"""
	if addon_updater_ops.updater.invalid_updater:
		return False
	if not addon_updater_ops.updater.json:
		return False
	did_update = addon_updater_ops.updater.json.get("just_updated") is True
	if did_update:
		return True

	# If not alreaedy flipped to be recongized as an update, do a slightly more
	# thorough check by seeing if the mcprep_data_update.json exists (ie it
	# hasn't been renamed yet to mcprep_data.json, which happens on init after
	# an install/update)
	check_interval = 5  # Time in seconds
	if time.time() - check_interval > env.last_check_for_updated:
		check_for_updated_files()
		env.last_check_for_updated = time.time()
	return


def check_for_updated_files():
	"""Checks for a file which would only exist after an auto/manual update.

	We check for the mcprep_data_update.json file, which would only exist after
	an automated or manual update and before blender has been restarted. This
	file is auto renamed to overwrite any existing mcprep_data.json file, but
	that only runs on addon startup, so it's a good flag to use to force users
	to restart.

	This covers the scenario where someone used the native blender install
	addon *instead* of the auto updater route to update the addon.
	"""
	if os.path.isfile(env.json_path_update):
		addon_updater_ops.updater.json["just_updated"] = True


def restart_layout(layout):
	"""Draws a restart button, used when addon_just_updated is true."""
	box = layout.box()
	col = box.column()
	alert_row = col.row()
	alert_row.alert = True
	alert_row.operator(
		"wm.quit_blender",
		text="Restart blender",
		icon="ERROR")
	col.label(text="to complete update")


# -----------------------------------------------------------------------------
# UI class functions
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
			row.operator(
				"mcprep.reload_mobs", text="Load mobs", icon=HAND_ICON)
			row.scale_y = 2
			row.alignment = 'CENTER'
			return

		keys = sorted(scn_props.mob_list_all.keys())
		for mobkey in keys:
			# show icon if available
			mob = scn_props.mob_list_all[mobkey]
			icn = "mob-{}".format(mob.index)
			if env.use_icons and icn in env.preview_collections["mobs"]:
				ops = layout.operator(
					"mcprep.mob_spawner",
					text=mob.name,
					icon_value=env.preview_collections["mobs"][icn].icon_id)
			elif env.use_icons:
				ops = layout.operator(
					"mcprep.mob_spawner", text=mob.name, icon="BLANK1")
			else:
				ops = layout.operator("mcprep.mob_spawner", text=mob.name)
			ops.mcmob_type = mob.mcmob_type

			# Skip prep materials in case of unique shader.
			if env.json_data and mob.name in env.json_data.get("mob_skip_prep", []):
				ops.prep_materials = False


class MCPREP_MT_meshswap_place(bpy.types.Menu):
	"""Menu for all the meshswap objects"""
	bl_label = "Meshswap Objects"
	bl_idname = "MCPREP_MT_meshswap_place"

	def draw(self, context):
		layout = self.layout
		meshswap_blocks = meshswap.getMeshswapList(context)
		if not meshswap_blocks:
			layout.label(text="No meshswap blocks found!")
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

			# Ensure meshswap with rigs is made real, so the rigs can be used.
			if env.json_data and blockset[1] in env.json_data.get("make_real", []):
				opr.make_real = True


class MCPREP_MT_item_spawn(bpy.types.Menu):
	"""Menu for loaded item spawners"""
	bl_label = "Item Spawner"
	bl_idname = "MCPREP_MT_item_spawn"

	def draw(self, context):
		layout = self.layout
		if not context.scene.mcprep_props.item_list:
			layout.label(text="No items found!")
		for item in context.scene.mcprep_props.item_list:
			icn = "item-{}".format(item.index)
			if env.use_icons and icn in env.preview_collections["items"]:
				ops = layout.operator(
					"mcprep.spawn_item", text=item.name,
					icon_value=env.preview_collections["items"][icn].icon_id)
			elif env.use_icons:
				ops = layout.operator(
					"mcprep.spawn_item", text=item.name, icon="BLANK1")
			else:
				ops = layout.operator("mcprep.spawn_item", text=item.name)
			ops.filepath = item.path


class MCPREP_MT_effect_spawn(bpy.types.Menu):
	"""Menu for loaded effect spawners"""
	bl_label = "Effects Spawner"
	bl_idname = "MCPREP_MT_effect_spawn"

	def draw(self, context):
		col = self.layout.column()
		loc = util.get_cuser_location(context)
		for effect in context.scene.mcprep_props.effects_list:
			if effect.effect_type in (effects.GEO_AREA, effects.PARTICLE_AREA):
				if effect.effect_type == effects.GEO_AREA:
					icon = "NODETREE"
				else:
					icon = "PARTICLES"
				ops = col.operator(
					"mcprep.spawn_global_effect",
					text=effect.name,
					icon=icon)
				ops.effect_id = str(effect.index)
			elif effect.effect_type == effects.COLLECTION:
				ops = col.operator(
					"mcprep.spawn_instant_effect",
					text=effect.name, icon=spawn_util.COLL_ICON)
				ops.effect_id = str(effect.index)
				ops.location = loc
				ops.frame = context.scene.frame_current
			elif effect.effect_type == effects.IMG_SEQ:
				icon = "effects-{}".format(effect.index)
				if env.use_icons and icon in env.preview_collections["effects"]:
					ops = col.operator(
						"mcprep.spawn_instant_effect",
						text=effect.name,
						icon_value=env.preview_collections["effects"][icon].icon_id)
				else:
					ops = col.operator(
						"mcprep.spawn_instant_effect",
						text=effect.name,
						icon="RENDER_RESULT")
				ops.effect_id = str(effect.index)
				ops.location = loc
				ops.frame = context.scene.frame_current


class MCPREP_MT_entity_spawn(bpy.types.Menu):
	"""Menu for loaded entity spawners"""
	bl_label = "Entity Spawner"
	bl_idname = "MCPREP_MT_entity_spawn"

	def draw(self, context):
		layout = self.layout
		entity_list = entities.getEntityList(context)
		if not entity_list:
			layout.label(text="No entities found!")
		for entity in entity_list:
			# do some kind of check for if no entities found
			icn = "BLANK1"
			if entity[0].startswith("Group"):
				icn = "GROUP"

			opr = layout.operator(
				"mcprep.entity_spawner",
				text=entity[1],
				icon=icn)
			opr.entity = entity[0]


class MCPREP_MT_model_spawn(bpy.types.Menu):
	"""Menu for loaded model spawners"""
	bl_label = "Model Spawner"
	bl_idname = "MCPREP_MT_model_spawn"

	def draw(self, context):
		layout = self.layout
		if not context.scene.mcprep_props.model_list:
			layout.label(text="No models found!")
		for model in context.scene.mcprep_props.model_list:
			opr = layout.operator(
				mcmodel.MCPREP_OT_spawn_minecraft_model.bl_idname,
				text=model.name)
			opr.filepath = model.filepath
			opr.location = util.get_cuser_location(context)


class MCPREP_MT_3dview_add(bpy.types.Menu):
	"""MCprep Shift-A menu for spawners"""
	bl_label = "MCprep"
	bl_idname = "MCPREP_MT_3dview_add"

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		layout = self.layout
		props = context.scene.mcprep_props

		if env.preview_collections["main"] != "":
			spawner_icon = env.preview_collections["main"].get("spawner_icon")
			meshswap_icon = env.preview_collections["main"].get("meshswap_icon")
			sword_icon = env.preview_collections["main"].get("sword_icon")
			effects_icon = env.preview_collections["main"].get("effects_icon")
			entity_icon = env.preview_collections["main"].get("entity_icon")
			model_icon = env.preview_collections["main"].get("model_icon")
		else:
			spawner_icon = None
			meshswap_icon = None
			sword_icon = None
			effects_icon = None
			entity_icon = None
			model_icon = None

		all_loaded = props.mob_list and props.meshswap_list and props.item_list
		if not env.loaded_all_spawners and not all_loaded:
			row = layout.row()
			row.operator(
				"mcprep.reload_spawners", text="Load spawners", icon=HAND_ICON)
			row.scale_y = 2
			row.alignment = 'CENTER'
			return

		if spawner_icon is not None:
			layout.menu(
				MCPREP_MT_mob_spawner.bl_idname,
				icon_value=spawner_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_mob_spawner.bl_idname)

		if model_icon is not None:
			layout.menu(
				MCPREP_MT_model_spawn.bl_idname, icon_value=model_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_model_spawn.bl_idname)

		if sword_icon is not None:
			layout.menu(
				MCPREP_MT_item_spawn.bl_idname, icon_value=sword_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_item_spawn.bl_idname)

		if effects_icon is not None:
			layout.menu(
				MCPREP_MT_effect_spawn.bl_idname, icon_value=effects_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_effect_spawn.bl_idname)

		if entity_icon is not None:
			layout.menu(
				MCPREP_MT_entity_spawn.bl_idname, icon_value=entity_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_entity_spawn.bl_idname)

		if meshswap_icon is not None:
			layout.menu(
				MCPREP_MT_meshswap_place.bl_idname,
				icon_value=meshswap_icon.icon_id)
		else:
			layout.menu(MCPREP_MT_meshswap_place.bl_idname)


def mineways_update(self, context):
	"""For updating the mineways path on OSX."""
	if ".app/" in self.open_mineways_path:
		# will run twice inherently
		temp = self.open_mineways_path.split(".app/")[0]
		self.open_mineways_path = temp + ".app"


def feature_set_update(self, context):
	tracking.Tracker.feature_set = self.feature_set
	tracking.trackUsage("feature_set", param=self.feature_set)


class McprepPreference(bpy.types.AddonPreferences):
	bl_idname = __package__
	scriptdir = bpy.path.abspath(os.path.dirname(__file__))

	def change_verbose(self, context):
		env.verbose = self.verbose

	meshswap_path: bpy.props.StringProperty(
		name="Meshswap path",
		description=(
			"Default path to the meshswap asset file, for "
			"meshswapable objects and groups"),
		subtype='FILE_PATH',
		default=scriptdir + "/MCprep_resources/mcprep_meshSwap.blend")
	entity_path: bpy.props.StringProperty(
		name="Entity path",
		description="Default path to the entity asset file, for entities",
		subtype='FILE_PATH',
		default=os.path.join(scriptdir, "MCprep_resources", "mcprep_entities.blend"))
	mob_path: bpy.props.StringProperty(
		name="Mob path",
		description="Default folder for rig loads/spawns in new blender instances",
		subtype='DIR_PATH',
		default=scriptdir + "/MCprep_resources/rigs/")
	custom_texturepack_path: bpy.props.StringProperty(
		name="Texture pack path",
		description=(
			"Path to a folder containing resources and textures to use "
			"with material prepping"),
		subtype='DIR_PATH',
		default=scriptdir + "/MCprep_resources/resourcepacks/mcprep_default/")
	skin_path: bpy.props.StringProperty(
		name="Skin path",
		description="Folder for skin textures, used in skin swapping",
		subtype='DIR_PATH',
		default=scriptdir + "/MCprep_resources/skins/")
	effects_path: bpy.props.StringProperty(
		name="Effects path",
		description="Folder for effects blend files and assets",
		subtype='DIR_PATH',
		default=scriptdir + "/MCprep_resources/effects/")
	world_obj_path: bpy.props.StringProperty(
		name="World Folder",
		description=(
			"Default folder for opening world objs from programs "
			"like jmc2obj or Mineways"),
		subtype='DIR_PATH',
		default="//")
	MCprep_groupAppendLayer: bpy.props.IntProperty(
		name="Group Append Layer",
		description=(
			"When groups are appended instead of linked, "
			"the objects part of the group will be placed in this "
			"layer, 0 means same as active layer"),
		min=0,
		max=20,
		default=20)
	MCprep_exporter_type: bpy.props.EnumProperty(
		items=[
			('(choose)', '(choose)', 'Select your exporter'),
			('jmc2obj', 'jmc2obj', 'Select if exporter used was jmc2obj'),
			('Mineways', 'Mineways', 'Select if exporter used was Mineways')],
		name="Exporter")
	preferences_tab: bpy.props.EnumProperty(
		items=[
			('settings', 'Settings', 'Change MCprep settings'),
			('tutorials', 'Tutorials', 'View MCprep tutorials & other help'),
			('tracker_updater', 'Tracking/Updater',
				'Change tracking and updating settings')],
		name="Exporter")
	verbose: bpy.props.BoolProperty(
		name="Verbose logging",
		description="Print out more information in the console",
		default=False,
		update=change_verbose)
	open_jmc2obj_path: bpy.props.StringProperty(
		name="jmc2obj path",
		description="Path to the jmc2obj executable",
		subtype='FILE_PATH',
		default="jmc2obj.jar")
	open_mineways_path: bpy.props.StringProperty(
		name="Mineways path",
		description="Path to the Mineways executable",
		subtype='FILE_PATH',
		update=mineways_update,
		default="Mineways")
	save_folder: bpy.props.StringProperty(
		name="MC saves folder",
		description=(
			"Folder containing Minecraft world saves directories, "
			"for the direct import bridge"),
		subtype='FILE_PATH',
		default='')
	feature_set: bpy.props.EnumProperty(
		items=[
			('supported', 'Supported', 'Use only supported features'),
			('experimental', 'Experimental', 'Enable experimental features')],
		name="Feature set",
		update=feature_set_update)

	# addon updater preferences

	auto_check_update: bpy.props.BoolProperty(
		name="Auto-check for Update",
		description="If enabled, auto-check for updates using an interval",
		default=True,
	)
	updater_interval_months: bpy.props.IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0
	)
	updater_interval_days: bpy.props.IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=1,
		min=0,
	)
	updater_interval_hours: bpy.props.IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23
	)
	updater_interval_minutes: bpy.props.IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59
	)

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.prop(self, "preferences_tab", expand=True)

		factor_width = 0.3

		if self.preferences_tab == "settings":

			row = layout.row()
			row.scale_y = 0.7
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

			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Entity assets")

			col = split.column()
			col.prop(self, "entity_path", text="")
			if not os.path.isfile(bpy.path.abspath(self.entity_path)):
				row = box.row()
				row.label(text="Entity file not found", icon="ERROR")

			col = split.column()
			col.prop(self, "effects_path", text="")
			if not os.path.isdir(bpy.path.abspath(self.effects_path)):
				row = box.row()
				row.label(text="Effects folder not found", icon="ERROR")

			row = layout.row()
			row.scale_y = 0.7
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
			row.scale_y = 0.7
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
			col.operator(
				"mcprep.mob_install_menu", text="Install file for mob spawning")
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open rig folder")
			p.folder = self.mob_path

			row = layout.row()
			row.scale_y = 0.7
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

			row = layout.row()
			row.scale_y = 0.7
			row.label(text="Effects")
			box = layout.box()
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col.label(text="Effect folder")
			col = split.column()
			col.prop(self, "effects_path", text="")
			split = util.layout_split(box, factor=factor_width)
			col = split.column()
			col = split.column()
			p = col.operator("mcprep.openfolder", text="Open effects folder")
			p.folder = self.effects_path

			# misc settings
			row = layout.row()
			row.prop(self, "verbose")
			row.prop(self, "feature_set")

			if self.feature_set != "supported":
				row = layout.row()
				box = row.box()
				box.scale_y = 0.7
				box.label(text="Using MCprep in experimental mode!", icon="ERROR")
				box.label(text="Early access features and requests for feedback")
				box.label(text="will be made visible. Thank you for contributing.")

		elif self.preferences_tab == "tutorials":
			layout.label(
				text="Unsure on how to use the addon? Check out these resources")
			row = layout.row()
			row.scale_y = 2
			row.operator(
				"wm.url_open",
				text="MCprep page for instructions and updates",
				icon="WORLD"
			).url = "https://theduckcow.com/dev/blender/mcprep/"

			row = layout.row()
			row.scale_y = 2
			row.operator(
				"wm.url_open",
				text="Learn MCprep + Blender, 1-minute tutorials",
				icon="FILE_MOVIE"
			).url = "https://bit.ly/MCprepTutorials"

			row = layout.row()
			row.scale_y = 1.5
			row.operator(
				"wm.url_open", text="Import Minecraft worlds"
			).url = "https://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"
			row.operator(
				"wm.url_open", text="Mob (rig) spawning"
			).url = "https://theduckcow.com/dev/blender/mcprep/mcprep-spawner/"
			row.operator(
				"wm.url_open", text="Skin swapping"
			).url = "https://theduckcow.com/dev/blender/mcprep/skin-swapping/"

			row = layout.row()
			row.scale_y = 1.5
			row.operator(
				"wm.url_open", text="jmc2obj/Mineways"
			).url = "https://theduckcow.com/dev/blender/mcprep/setup-world-exporters/"
			row.operator(
				"wm.url_open", text="World Tools"
			).url = "https://theduckcow.com/dev/blender/mcprep/world-tools/"
			row.operator(
				"wm.url_open", text="Tutorial Series"
			).url = "https://bit.ly/MCprepTutorials"

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
				bcol.operator(
					"mcprep.toggle_enable_tracking",
					text="Opt into anonymous usage tracking",
					icon=OPT_IN)
			else:
				bcol.operator(
					"mcprep.toggle_enable_tracking",
					text="Opt OUT of anonymous usage tracking",
					icon="CANCEL")

			bcol = brow.column()
			bcol.label(text="For info on anonymous usage tracking:")
			brow = box.row()
			bcol.operator(
				"wm.url_open", text="Open the Privacy Policy"
			).url = "https://theduckcow.com/privacy-policy"

			# updater draw function
			addon_updater_ops.update_settings_ui(self, context)


class MCPREP_PT_world_imports(bpy.types.Panel):
	"""World importing related settings and tools"""
	bl_label = env.translate_str(TE.WORLD_IMPORTS_HEADER)
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	# bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		addon_prefs = util.get_user_preferences(context)
		scn_props = context.scene.mcprep_props

		# check for update in background thread if appropraite
		addon_updater_ops.check_for_update_background()

		# show update ready if available
		addon_updater_ops.update_notice_box_ui(self, context)
		if addon_just_updated():
			# Don't draw restart_layout() here, as we already have a box
			return

		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		row = col.row()
		row.label(text=env.translate_str(TE.WORLD_EXPORTER_HEADER))
		row.operator(
			"mcprep.open_help", text="", icon="QUESTION", emboss=False
		).url = "https://theduckcow.com/dev/blender/mcprep/mcprep-minecraft-world-imports/"
		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		row.prop(addon_prefs, "MCprep_exporter_type", expand=True)
		row = col.row(align=True)
		if addon_prefs.MCprep_exporter_type == "(choose)":
			row.operator(
				"mcprep.open_jmc2obj", text="Select exporter!", icon='ERROR')
			row.enabled = False
		elif addon_prefs.MCprep_exporter_type == "Mineways":
			row.operator("mcprep.open_mineways")
		else:
			row.operator("mcprep.open_jmc2obj")

		wpath = addon_prefs.world_obj_path
		col.operator(
			"mcprep.import_world_split",
			text=env.translate_str(TE.OBJ_WORLD_IMPORT)).filepath = wpath

		split = layout.split()
		col = split.column(align=True)
		col.label(text=env.translate_str(TE.MCPREP_TOOLS))
		col.operator("mcprep.prep_materials", text=env.translate_str(TE.MCPREP_PREP_MATERIALS))

		if not util.is_atlas_export(context):
			row = col.row()
			row.operator(
				"mcprep.open_help", text="", icon="QUESTION", emboss=False
			).url = "https://github.com/TheDuckCow/MCprep/blob/master/docs/common_errors.md#common-error-messages-and-what-they-mean"
			row.label(text=env.translate_str(TE.OBJ_INCOMPATIBLE_TEXTURESWAP))
		p = col.operator("mcprep.swap_texture_pack")
		p.filepath = context.scene.mcprep_texturepack_path
		if context.mode == "OBJECT":
			col.operator("mcprep.meshswap", text=env.translate_str(TE.MESHSWAP))
			if addon_prefs.MCprep_exporter_type == "(choose)":
				col.label(text=TE.SELECT_EXPORTER, icon='ERROR')
		if context.mode == 'EDIT_MESH':
			col.operator("mcprep.scale_uv")
			col.operator("mcprep.select_alpha_faces")

		split = layout.split()
		col = split.column(align=True)

		# Indicate whether UI can be improved or not.
		view28 = ['SOLID', 'MATERIAL', 'RENDERED']
		
		improved_28 = util.viewport_textured(context) is True
		improved_28 &= context.scene.display.shading.type in view28
		improved_28 &= context.scene.display.shading.background_type == "WORLD"

		if improved_28:
			row = col.row(align=True)
			row.enabled = False
			row.operator(
				"mcprep.improve_ui",
				text=env.translate_str(TE.UI_ALREADY_IMPROVED), icon='SETTINGS')
		else:
			col.operator(
				"mcprep.improve_ui", text=env.translate_str(TE.UI_IMPROVE), icon='SETTINGS')

		# Optimizer Panel (only for blender 2.80+)
		row = col.row(align=True)
		icon = "TRIA_DOWN" if scn_props.show_settings_optimizer else "TRIA_RIGHT"
		row.prop(
			scn_props, "show_settings_optimizer",
			text=env.translate_str(TE.CYCLES_OPTIMIZER), icon=icon)
		if scn_props.show_settings_optimizer:
			row = col.row(align=True)
			optimize_scene.panel_draw(context, row)

		# Advanced settings.
		row = col.row(align=True)
		if not scn_props.show_settings_material:
			row.prop(
				scn_props, "show_settings_material",
				text=env.translate_str(TE.ADVANCED), icon="TRIA_RIGHT")
			row.operator(
				"mcprep.open_preferences",
				text="", icon="PREFERENCES").tab = "settings"
		else:
			row.prop(
				scn_props, "show_settings_material",
				text=env.translate_str(TE.ADVANCED), icon="TRIA_DOWN")
			row.operator(
				"mcprep.open_preferences",
				text="", icon="PREFERENCES").tab = "settings"
			box = col.box()
			b_row = box.row()
			b_col = b_row.column(align=False)
			b_col.label(text=env.translate_str(TE.TEXTURE_PACK_FOLDER))
			row = b_col.row(align=True)
			row.prop(context.scene, "mcprep_texturepack_path", text="")
			row.operator("mcprep.reset_texture_path", text="", icon=LOAD_FACTORY)

			b_row = box.row()
			b_col = b_row.column(align=True)
			sync_row = b_col.row(align=True)
			sync_row.operator("mcprep.sync_materials")
			sync_row.operator(
				"mcprep.edit_sync_materials_file", text="", icon="FILE_TICK") # or TOOL_SETTINGS.
			b_col.operator("mcprep.replace_missing_textures")
			b_col.operator("mcprep.animate_textures")
			# TODO: operator to make all local, all packed, or set to other location
			b_col.operator(
				"mcprep.combine_materials",
				text=env.translate_str(TE.COMBINE_MATERIALS)).selection_only = True
			if bpy.app.version > (2, 77):
				b_col.operator("mcprep.combine_images", text=env.translate_str(TE.COMBINE_IMAGES))

			b_col.label(text=env.translate_str(TE.MESHSWAP_SOURCE))
			subrow = b_col.row(align=True)
			subrow.prop(context.scene, "meshswap_path", text="")
			subrow.operator(
				"mcprep.meshswap_path_reset", icon=LOAD_FACTORY, text="")
			if not context.scene.meshswap_path.lower().endswith('.blend'):
				b_col.label(text=env.translate_str(TE.MESHSWAP_FILE_BLEND_ERROR), icon="ERROR")
			if not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
				b_col.label(text=env.translate_str(TE.MESHSWAP_FILE_NOT_FOUND_ERROR), icon="ERROR")

		layout = self.layout  # clear out the box formatting
		split = layout.split()
		row = split.row(align=True)


class MCPREP_PT_bridge(bpy.types.Panel):
	"""MCprep panel for directly importing and reloading minecraft saves"""
	bl_label = "World Bridge"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_context = "objectmode"
	bl_category = "MCprep"

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return

		# bridge.panel_draw(self, context)
		pass


class MCPREP_PT_world_tools(bpy.types.Panel):
	"""World settings and tools"""
	bl_label = env.translate_str(TE.WORLD_TOOLS_HEADER)
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'	
	bl_category = "MCprep"

	def draw(self, context):
		layout = self.layout
		if addon_just_updated():
			restart_layout(layout)
			return

		rw = layout.row()
		col = rw.column()
		row = col.row(align=True)
		row.label(text=env.translate_str(TE.WORLD_SETTINGS_LIGHTING))  # world time
		row.operator(
			"mcprep.open_help", text="", icon="QUESTION", emboss=False
		).url = "https://theduckcow.com/dev/blender/mcprep/world-tools/"

		rw = layout.row()
		col = rw.column(align=True)
		col.operator("mcprep.add_mc_sky")
		col.operator("mcprep.world")
		col.operator("mcprep.render_panorama")

		layout.split()
		rw = layout.row()
		col = rw.column(align=True)
		obj = world_tools.get_time_object()
		col.label(text=env.translate_str(TE.WORLD_TIME_OF_DAY))
		if obj and "MCprepHour" in obj:
			time = obj["MCprepHour"]
			col.prop(
				obj,
				'["MCprepHour"]',
				text="")
			col.label(text="{h}:{m}, day {d}".format(
				h=str(int(time % 24 - time % 1)).zfill(2),
				m=str(int(time % 1 * 60)).zfill(2),
				d=int((time - time % 24) / 24)
			))
		else:
			box = col.box()
			subcol = box.column()
			subcol.scale_y = 0.8
			subcol.label(text=env.translate_str(TE.WORLD_ADD_WORLD_1))
			subcol.label(text=env.translate_str(TE.WORLD_ADD_WORLD_2))
		# col.label(text="World setup")
		# col.operator("mcprep.world")
		# col.operator("mcprep.world", text="Add clouds")
		# col.operator("mcprep.world", text="Set Weather")


class MCPREP_PT_skins(bpy.types.Panel):
	"""MCprep panel for skin swapping"""
	bl_label = env.translate_str(TE.SKIN_SWAPPER_HEADER)
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "MCprep"

	def draw(self, context):
		layout = self.layout
		if addon_just_updated():
			restart_layout(layout)
			return

		scn_props = context.scene.mcprep_props
		sind = context.scene.mcprep_skins_list_index
		mob_ind = context.scene.mcprep_props.mob_list_index
		skinname = None

		row = layout.row()
		row.label(text=env.translate_str(TE.SKIN_SELECT))
		row.operator(
			"mcprep.open_help", text="", icon="QUESTION", emboss=False
		).url = "https://theduckcow.com/dev/blender/mcprep/skin-swapping/"

		# set size of UIlist
		row = layout.row()
		col = row.column()

		is_sortable = len(env.skin_list) > 1
		rows = 1
		if (is_sortable):
			rows = 4

		# any other conditions for needing reloading?
		if not env.skin_list:
			col = layout.column()
			col.label(text=env.translate_str(TE.NO_SKINS_LOADED))
			p = col.operator(
				"mcprep.reload_skins", text=env.translate_str(TE.PRESS_TO_RELOAD), icon="ERROR")
		elif env.skin_list and len(env.skin_list) <= sind:
			col = layout.column()
			col.label(text=env.translate_str(TE.RELOAD_SKINS))
			p = col.operator(
				"mcprep.reload_skins", text=env.translate_str(TE.PRESS_TO_RELOAD), icon="ERROR")
		else:
			col.template_list(
				"MCPREP_UL_skins", "",
				context.scene, "mcprep_skins_list",
				context.scene, "mcprep_skins_list_index",
				rows=rows)

			col = layout.column(align=True)

			row = col.row(align=True)
			row.scale_y = 1.5
			if env.skin_list:
				skinname = bpy.path.basename(env.skin_list[sind][0])
				p = row.operator("mcprep.applyskin", text=env.translate_str(TE.APPLY) + skinname)
				p.filepath = env.skin_list[sind][1]
			else:
				row.enabled = False
				p = row.operator("mcprep.skin_swapper", text=env.translate_str(TE.NO_SKINS_LOADED))
			row = col.row(align=True)
			row.operator("mcprep.skin_swapper", text=env.translate_str(TE.SKIN_FROM_FILE))
			row = col.row(align=True)
			row.operator("mcprep.applyusernameskin", text=env.translate_str(TE.SKIN_FROM_USERNAME))

		split = layout.split()
		col = split.column(align=True)
		row = col.row(align=True)
		if not scn_props.show_settings_skin:
			row.prop(
				scn_props, "show_settings_skin",
				text=env.translate_str(TE.ADVANCED), icon="TRIA_RIGHT")
			row.operator(
				"mcprep.open_preferences",
				text="", icon="PREFERENCES").tab = "settings"
		else:
			row.prop(
				scn_props, "show_settings_skin",
				text=env.translate_str(TE.ADVANCED), icon="TRIA_DOWN")
			row.operator(
				"mcprep.open_preferences",
				text="", icon="PREFERENCES").tab = "settings"
			box = col.box()
			b_row = box.column(align=True)
			b_row.label(text=env.translate_str(TE.SKIN_PATH))
			b_subrow = b_row.row(align=True)
			b_subrow.prop(context.scene, "mcprep_skin_path", text="")
			b_subrow.operator(
				"mcprep.skin_path_reset", icon=LOAD_FACTORY, text="")
			b_row.operator("mcprep.add_skin")
			b_row.operator("mcprep.remove_skin")
			b_row.operator("mcprep.download_username_list")
			b_row.operator("mcprep.reload_skins")
			if context.mode == "OBJECT" and skinname:
				row = b_row.row(align=True)
				if not scn_props.mob_list:
					row.enabled = False
					row.operator(
						"mcprep.spawn_with_skin", text=env.translate_str(TE.RELOAD_MOBS_BELOW))
				elif not env.skin_list:
					row.enabled = False
					row.operator(
						"mcprep.spawn_with_skin", text=env.translate_str(TE.RELOAD_SKINS_ABOVE))
				else:
					name = scn_props.mob_list[mob_ind].name
					# datapass = scn_props.mob_list[mob_ind].mcmob_type
					tx = "Spawn {x} with {y}".format(x=name, y=skinname)
					row.operator("mcprep.spawn_with_skin", text=tx)


class MCPREP_PT_materials(bpy.types.Panel):
	"""MCprep panel for materials"""
	bl_label = env.translate_str(TE.MCPREP_MATERIALS_HEADER)
	bl_space_type = "PROPERTIES"
	bl_region_type = 'WINDOW'
	bl_context = "material"

	def draw(self, context):
		"""Code for drawing the material generator"""
		scn_props = context.scene.mcprep_props

		layout = self.layout
		if addon_just_updated():
			restart_layout(layout)
			return

		row = layout.row()
		# row.operator("mcprep.create_default_material")
		split = layout.split()
		col = split.column(align=True)

		if scn_props.material_list:
			col.template_list(
				"MCPREP_UL_material", "",
				scn_props, "material_list",
				scn_props, "material_list_index",
				rows=4)
			col = layout.column(align=True)
			row = col.row(align=True)
			row.scale_y = 1.5
			mat = scn_props.material_list[scn_props.material_list_index]
			ops = row.operator("mcprep.load_material", text=env.translate_str(TE.LOAD_MATERIAL_1) + mat.name)
			ops.filepath = mat.path
		else:
			box = col.box()
			b_row = box.row()
			b_row.label(text=env.translate_str(TE.NO_MATERIAL_LOADED))
			b_row = box.row()
			b_row.scale_y = 2
			b_row.operator("mcprep.reload_materials", icon="ERROR")

			col = layout.column(align=True)
			col.enabled = False
			row = col.row(align=True)
			row.scale_y = 1.5
			ops = row.operator("mcprep.load_material", text=env.translate_str(TE.LOAD_MATERIAL_2))


class MCPREP_PT_materials_subsettings(bpy.types.Panel):
	"""MCprep panel for advanced material settings and functions"""
	bl_label = env.translate_str(TE.ADVANCED)
	bl_parent_id = "MCPREP_PT_materials"
	bl_space_type = "PROPERTIES"
	bl_region_type = 'WINDOW'
	bl_context = "material"

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return

		b_row = self.layout.row()
		b_col = b_row.column(align=False)
		b_col.label(text=env.translate_str(TE.RESOURCE_PACK))
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "mcprep_texturepack_path", text="")
		subrow.operator(
			"mcprep.reset_texture_path", icon=LOAD_FACTORY, text="")
		b_row = self.layout.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_materials")


# -----------------------------------------------------------------------------
# Spawner related UI
# -----------------------------------------------------------------------------

def draw_mode_warning(ui_element):
	col = ui_element.column(align=True)
	col.label(text=env.translate_str(TE.ENTER_OBJECT_MODE_1), icon="ERROR")
	col.label(text=env.translate_str(TE.ENTER_OBJECT_MODE_2), icon="BLANK1")
	col.operator("object.mode_set").mode = "OBJECT"
	col.label(text="")


def mob_spawner(self, context):
	scn_props = context.scene.mcprep_props

	layout = self.layout
	layout.label(text=env.translate_str(TE.IMPORT_PRERIGGED))
	split = layout.split()
	col = split.column(align=True)

	row = col.row()
	row.prop(scn_props, "spawn_rig_category", text="")
	if scn_props.mob_list:
		row = col.row()
		row.template_list(
			"MCPREP_UL_mob", "",
			scn_props, "mob_list",
			scn_props, "mob_list_index",
			rows=4)
	elif scn_props.mob_list_all:
		box = col.box()
		b_row = box.row()
		b_row.label(text="")
		b_col = box.column()
		b_col.scale_y = 0.7
		b_col.label(text=env.translate_str(TE.NO_MOBS_IN_CATEGORY_1))
		b_col.label(text=env.translate_str(TE.NO_MOBS_IN_CATEGORY_2))
		b_col.label(text=env.translate_str(TE.NO_MOBS_IN_CATEGORY_3))
		b_row = box.row()
		b_row.label(text="")
	else:
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.NO_MOBS_LOADED))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.reload_spawners", text=env.translate_str(TE.RELOAD_ASSETS), icon="ERROR")

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
	row.enabled = len(scn_props.mob_list) > 0
	p = row.operator("mcprep.mob_spawner", text=env.translate_str(TE.SPAWN) + name)
	if mcmob_type:
		p.mcmob_type = mcmob_type

	# Skip prep materials in case of unique shader.
	if env.json_data and name in env.json_data.get("mob_skip_prep", []):
		p.prep_materials = False

	p = col.operator("mcprep.mob_install_menu")
	p.mob_category = scn_props.spawn_rig_category

	split = layout.split()
	col = split.column(align=True)
	row = col.row(align=True)
	if not scn_props.show_settings_spawner:
		row.prop(
			scn_props, "show_settings_spawner",
			text=env.translate_str(TE.ADVANCED), icon="TRIA_RIGHT")
		row.operator(
			"mcprep.open_preferences",
			text="", icon="PREFERENCES").tab = "settings"
	else:
		row.prop(
			scn_props, "show_settings_spawner",
			text=env.translate_str(TE.ADVANCED), icon="TRIA_DOWN")
		row.operator(
			"mcprep.open_preferences",
			text="", icon="PREFERENCES").tab = "settings"
		box = col.box()
		b_row = box.row()
		b_col = b_row.column(align=False)
		b_col.label(text=env.translate_str(TE.MOB_SPAWNER_FOLDER))
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "mcprep_mob_path", text="")
		subrow.operator(
			"mcprep.spawn_path_reset", icon=LOAD_FACTORY, text="")
		b_row = box.row()
		b_col = b_row.column(align=True)
		ops = b_col.operator("mcprep.openfolder", text=env.translate_str(TE.OPEN_MOB_FOLDER))
		ops.folder = context.scene.mcprep_mob_path

		if not scn_props.mob_list:
			b_col.operator("mcprep.mob_install_icon")
		else:
			icon_index = scn_props.mob_list[scn_props.mob_list_index].index
			if "mob-{}".format(icon_index) in env.preview_collections["mobs"]:
				b_col.operator(
					"mcprep.mob_install_icon", text=env.translate_str(TE.CHANGE_MOB_ICON))
			else:
				b_col.operator("mcprep.mob_install_icon")
		b_col.operator("mcprep.mob_uninstall")
		b_col.operator("mcprep.reload_mobs", text=env.translate_str(TE.RELOAD_MOBS))
		b_col.label(text=mcmob_type)


def meshswap_spawner(self, context):
	scn_props = context.scene.mcprep_props

	layout = self.layout
	layout.label(text="Import pre-made blocks (e.g. lights)")
	split = layout.split()
	col = split.column(align=True)

	if scn_props.meshswap_list:
		col.template_list(
			"MCPREP_UL_meshswap", "",
			scn_props, "meshswap_list",
			scn_props, "meshswap_list_index",
			rows=4)
		# col.label(text=datapass.split("/")[0])
	elif not context.scene.meshswap_path.lower().endswith('.blend'):
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.MESHSWAP_BLEND))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.meshswap_path_reset", icon=LOAD_FACTORY,
			text=env.translate_str(TE.RESET_MESHSWAP_PATH))
	elif not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.MESHSWAP_FILE_NOT_FOUND_ERROR))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.meshswap_path_reset", icon=LOAD_FACTORY,
			text=env.translate_str(TE.RESET_MESHSWAP_PATH))
	else:
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.NO_BLOCKS_LOADED))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.reload_spawners",
			text=env.translate_str(TE.RELOAD_ASSETS), icon="ERROR")

	col = layout.column(align=True)
	row = col.row()
	row.scale_y = 1.5
	row.enabled = len(scn_props.meshswap_list) > 0
	if scn_props.meshswap_list:
		name = scn_props.meshswap_list[scn_props.meshswap_list_index].name
		block = scn_props.meshswap_list[scn_props.meshswap_list_index].block
		method = scn_props.meshswap_list[scn_props.meshswap_list_index].method
		p = row.operator("mcprep.meshswap_spawner", text=env.translate_str(TE.PLACE) + name)
		p.block = block
		p.method = method
		p.location = util.get_cuser_location(context)
		# Ensure meshswap with rigs is made real, so the rigs can be used.
		if env.json_data and block in env.json_data.get("make_real", []):
			p.make_real = True

	else:
		row.operator("mcprep.meshswap_spawner", text=env.translate_str(TE.PLACE_BLOCK))
	# something to directly open meshswap file??

	split = layout.split()
	col = split.column(align=True)
	row = col.row(align=True)

	if not scn_props.show_settings_spawner:
		col.prop(
			scn_props, "show_settings_spawner",
			text=env.translate_str(TE.ADVANCED), icon="TRIA_RIGHT")
	else:
		col.prop(
			scn_props,
			"show_settings_spawner",
			text=env.translate_str(TE.ADVANCED), icon="TRIA_DOWN")
		box = col.box()
		b_row = box.row()
		b_col = b_row.column(align=False)
		b_col.label(text=env.translate_str(TE.MESHSWAP_FILE))
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "meshswap_path", text="")
		subrow.operator(
			"mcprep.meshswap_path_reset", icon=LOAD_FACTORY, text="")
		if not context.scene.meshswap_path.lower().endswith('.blend'):
			b_col.label(text=env.translate_str(TE.MESHSWAP_BLEND), icon="ERROR")
		elif not os.path.isfile(bpy.path.abspath(context.scene.meshswap_path)):
			b_col.label(text=env.translate_str(TE.MESHSWAP_FILE_NOT_FOUND_ERROR), icon="ERROR")
		b_row = box.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_meshswap")


def item_spawner(self, context):
	"""Code for drawing the item spawner"""
	scn_props = context.scene.mcprep_props
	
	layout = self.layout
	layout.label(env.translate_str(TE.ITEM_FROM_TEXTURE))
	split = layout.split()
	col = split.column(align=True)

	if scn_props.item_list:
		col.template_list(
			"MCPREP_UL_item", "",
			scn_props, "item_list",
			scn_props, "item_list_index",
			rows=4)
		col = layout.column(align=True)
		row = col.row(align=True)
		row.scale_y = 1.5
		name = scn_props.item_list[scn_props.item_list_index].name
		row.operator("mcprep.spawn_item", text=env.translate_str(TE.PLACE) + name)
		row = col.row(align=True)
		row.operator("mcprep.spawn_item_file")
	else:
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.NO_ITEMS_LOADED))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.reload_spawners",
			text=env.translate_str(TE.RELOAD_ASSETS), icon="ERROR")

		col = layout.column(align=True)
		col.enabled = False
		row = col.row(align=True)
		row.scale_y = 1.5
		row.operator("mcprep.spawn_item", text=env.translate_str(TE.PLACE_ITEM))
		row = col.row(align=True)
		row.operator("mcprep.spawn_item_file")

	split = layout.split()
	col = split.column(align=True)
	row = col.row(align=True)

	if not scn_props.show_settings_spawner:
		col.prop(
			scn_props, "show_settings_spawner",
			text=env.translate_str(TE.ADVANCED), icon="TRIA_RIGHT")
	else:
		col.prop(
			scn_props, "show_settings_spawner",
			text=env.translate_str(TE.ADVANCED), icon="TRIA_DOWN")
		box = col.box()
		b_row = box.row()
		b_col = b_row.column(align=False)
		b_col.label(text=env.translate_str(TE.RESOURCE_PACK))
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "mcprep_texturepack_path", text="")
		subrow.operator(
			"mcprep.reset_texture_path", icon=LOAD_FACTORY, text="")
		b_row = box.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_items")


def entity_spawner(self, context):
	scn_props = context.scene.mcprep_props

	layout = self.layout
	layout.label(text=env.translate_str(TE.IMPORT_ENTITIES))
	split = layout.split()
	col = split.column(align=True)

	if scn_props.entity_list:
		col.template_list(
			"MCPREP_UL_entity", "",
			scn_props, "entity_list",
			scn_props, "entity_list_index",
			rows=4)

	elif not context.scene.entity_path.lower().endswith('.blend'):
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.ENTITY_BLEND))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.entity_path_reset", icon=LOAD_FACTORY,
			text="Reset entity path")
	elif not os.path.isfile(bpy.path.abspath(context.scene.entity_path)):
		box = col.box()
		b_row = box.row()
		b_row.label(text=env.translate_str(TE.ENTITY_FILE_NOT_FOUND_ERROR))
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.entity_path_reset", icon=LOAD_FACTORY,
			text=env.translate_str(TE.RESET_ENTITY_PATH))
	else:
		box = col.box()
		b_row = box.row()
		b_row.label(text="No entities loaded")
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.reload_spawners",
			text=env.translate_str(TE.RELOAD_ASSETS), icon="ERROR")

	col = layout.column(align=True)
	row = col.row()
	row.scale_y = 1.5
	row.enabled = len(scn_props.entity_list) > 0
	if scn_props.entity_list:
		name = scn_props.entity_list[scn_props.entity_list_index].name
		entity = scn_props.entity_list[scn_props.entity_list_index].entity
		p = row.operator("mcprep.entity_spawner", text=env.translate_str(TE.SPAWN) + name)
		p.entity = entity
	else:
		row.operator("mcprep.entity_spawner", text=TE.SPAWN_ENTITY)

	split = layout.split()
	col = split.column(align=True)
	row = col.row(align=True)

	if not scn_props.show_settings_spawner:
		col.prop(
			scn_props, "show_settings_spawner",
			text=TE.ADVANCED, icon="TRIA_RIGHT")
	else:
		col.prop(
			scn_props, "show_settings_spawner",
			text=TE.ADVANCED, icon="TRIA_DOWN")
		box = col.box()
		b_row = box.row()
		b_col = b_row.column(align=False)
		b_col.label(text="Entity file")
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "entity_path", text="")
		subrow.operator("mcprep.entity_path_reset", icon=LOAD_FACTORY, text="")
		if not context.scene.entity_path.lower().endswith('.blend'):
			b_col.label(text=TE.MESHSWAP_FILE_BLEND_ERROR, icon="ERROR")
		elif not os.path.isfile(bpy.path.abspath(context.scene.entity_path)):
			b_col.label(text=TE.MESHSWAP_FILE_NOT_FOUND_ERROR, icon="ERROR")
		b_row = box.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_entities")


def model_spawner(self, context):
	"""Code for drawing the model block spawner"""
	scn_props = context.scene.mcprep_props
	addon_prefs = util.get_user_preferences(context)

	layout = self.layout
	layout.label(text="Generate models from .json files")
	split = layout.split()
	col = split.column(align=True)

	if scn_props.model_list:
		col.template_list(
			"MCPREP_UL_model", "",
			scn_props, "model_list",
			scn_props, "model_list_index",
			rows=4)

		col = layout.column(align=True)
		row = col.row(align=True)
		row.scale_y = 1.5
		model = scn_props.model_list[scn_props.model_list_index]
		ops = row.operator("mcprep.spawn_model", text="Place: " + model.name)
		ops.location = util.get_cuser_location(context)
		ops.filepath = model.filepath
		if addon_prefs.MCprep_exporter_type == "Mineways":
			ops.snapping = "offset"
		elif addon_prefs.MCprep_exporter_type == "jmc2obj":
			ops.snapping = "center"
	else:
		box = col.box()
		b_row = box.row()
		b_row.label(text="No models loaded")
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.reload_spawners",
			text="Reload assets", icon="ERROR")

		col = layout.column(align=True)
		row = col.row(align=True)
		row.enabled = False
		row.scale_y = 1.5
		row.operator(mcmodel.MCPREP_OT_spawn_minecraft_model.bl_idname)

	ops = col.operator("mcprep.import_model_file")
	ops.location = util.get_cuser_location(context)
	if addon_prefs.MCprep_exporter_type == "Mineways":
		ops.snapping = "center"
	elif addon_prefs.MCprep_exporter_type == "jmc2obj":
		ops.snapping = "offset"

	split = layout.split()
	col = split.column(align=True)
	row = col.row(align=True)

	if not scn_props.show_settings_spawner:
		col.prop(
			scn_props, "show_settings_spawner",
			text="Advanced", icon="TRIA_RIGHT")
	else:
		col.prop(
			scn_props, "show_settings_spawner",
			text="Advanced", icon="TRIA_DOWN")
		box = col.box()
		b_row = box.row()
		b_col = b_row.column(align=False)
		b_col.label(text="Resource pack")
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "mcprep_texturepack_path", text="")
		subrow.operator(
			"mcprep.reset_texture_path", icon=LOAD_FACTORY, text="")
		b_row = box.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_models")


def effects_spawner(self, context):
	"""Code for drawing the effects spawner"""
	scn_props = context.scene.mcprep_props

	layout = self.layout
	col = layout.column(align=True)
	col.label(text="Load/generate effects")

	# Alternate draw approach, using UI list.
	if scn_props.effects_list:
		col.template_list(
			"MCPREP_UL_effects", "",
			scn_props, "effects_list",
			scn_props, "effects_list_index",
			rows=4)
		col = layout.column(align=True)
		row = col.row(align=True)
		row.scale_y = 1.5
		effect = scn_props.effects_list[scn_props.effects_list_index]
		if effect.effect_type in (effects.GEO_AREA, effects.PARTICLE_AREA):
			ops = row.operator(
				"mcprep.spawn_global_effect", text="Add: " + effect.name)
			ops.effect_id = str(effect.index)
		elif effect.effect_type in (effects.COLLECTION, effects.IMG_SEQ):
			ops = row.operator(
				"mcprep.spawn_instant_effect", text="Add: " + effect.name)
			ops.effect_id = str(effect.index)
			ops.location = util.get_cuser_location(context)
			ops.frame = context.scene.frame_current
	else:
		box = col.box()
		b_row = box.row()
		b_row.label(text="No effects loaded")
		b_row = box.row()
		b_row.scale_y = 2
		b_row.operator(
			"mcprep.reload_spawners",
			text="Reload assets", icon="ERROR")

		col = layout.column(align=True)
		row = col.row(align=True)
		row.scale_y = 1.5
		row.enabled = False
		row.operator("mcprep.spawn_item", text="Add effect")
	row = col.row(align=True)
	ops = row.operator("mcprep.spawn_particle_planes")
	ops.location = util.get_cuser_location(context)
	ops.frame = context.scene.frame_current

	# If particle planes has not been changed yet this session,
	# use the texture pack location in
	if not context.scene.mcprep_particle_plane_file:
		initial_sel = os.path.join(
			context.scene.mcprep_texturepack_path,
			"assets", "minecraft", "textures", "block", "dirt.png")
		alt_sel = os.path.join(
			context.scene.mcprep_texturepack_path,
			"assets", "minecraft", "textures", "block")
		if os.path.isfile(initial_sel):
			ops.filepath = initial_sel
		elif os.path.isdir(alt_sel):
			ops.filepath = alt_sel
		else:
			ops.filepath = context.scene.mcprep_texturepack_path
	else:
		ops.filepath = context.scene.mcprep_particle_plane_file

	col = layout.column()
	if not scn_props.show_settings_effect:
		col.prop(
			scn_props, "show_settings_effect",
			text="Advanced", icon="TRIA_RIGHT")
	else:
		col.prop(
			scn_props, "show_settings_effect",
			text="Advanced", icon="TRIA_DOWN")
		box = col.box()
		b_row = box.row()
		b_col = b_row.column(align=False)
		b_col.label(text="Effects folder")
		subrow = b_col.row(align=True)
		subrow.prop(context.scene, "mcprep_effects_path", text="")
		subrow.operator("mcprep.effects_path_reset", icon=LOAD_FACTORY, text="")

		box.label(text="Texture pack folder")
		row = box.row(align=True)
		row.prop(context.scene, "mcprep_texturepack_path", text="")
		row.operator("mcprep.reset_texture_path", text="", icon=LOAD_FACTORY)

		base = bpy.path.abspath(context.scene.mcprep_effects_path)
		if not os.path.isdir(base):
			b_col.label(text="Effects folder not found", icon="ERROR")
		elif not os.path.isdir(os.path.join(base, "collection")):
			b_col.label(text="Effects/collection folder not found", icon="ERROR")
		elif not os.path.isdir(os.path.join(base, "geonodes")):
			b_col.label(text="Effects/geonodes folder not found", icon="ERROR")
		elif not os.path.isdir(os.path.join(base, "particle")):
			b_col.label(text="Effects/particle folder not found", icon="ERROR")
		b_row = box.row()
		b_col = b_row.column(align=True)
		b_col.operator("mcprep.reload_effects")


class MCPREP_PT_spawn(bpy.types.Panel):
	"""MCprep panel for mob spawning"""
	bl_label = "Spawner"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_category = "MCprep"

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		row = self.layout.row(align=True)
		row.label(text="Click triangle to open")
		ops = row.operator(
			"mcprep.open_help", text="", icon="QUESTION", emboss=False)
		ops.url = "https://theduckcow.com/dev/blender/mcprep/mcprep-spawner/"
		addon_updater_ops.check_for_update_background()


class MCPREP_PT_mob_spawner(bpy.types.Panel):
	"""MCprep panel for mob spawning"""
	bl_label = "Mob spawner"
	bl_parent_id = "MCPREP_PT_spawn"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'	
	bl_category = "MCprep"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		is_obj_mode = context.mode == "OBJECT"
		if not is_obj_mode:
			draw_mode_warning(self.layout)
			return
		mob_spawner(self, context)

	def draw_header(self, context):
		if not env.use_icons or env.preview_collections["main"] == "":
			return
		icon = env.preview_collections["main"].get("spawner_icon")
		if not icon:
			return
		self.layout.label(text="", icon_value=icon.icon_id)


class MCPREP_PT_model_spawner(bpy.types.Panel):
	"""MCprep panel for model/block spawning"""
	bl_label = "Block (model) spawner"
	bl_parent_id = "MCPREP_PT_spawn"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_category = "MCprep"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		is_obj_mode = context.mode == "OBJECT"
		if not is_obj_mode:
			draw_mode_warning(self.layout)
			return
		model_spawner(self, context)

	def draw_header(self, context):
		if not env.use_icons or env.preview_collections["main"] == "":
			return
		icon = env.preview_collections["main"].get("model_icon")
		if not icon:
			return
		self.layout.label(text="", icon_value=icon.icon_id)


class MCPREP_PT_item_spawner(bpy.types.Panel):
	"""MCprep panel for item spawning"""
	bl_label = "Item spawner"
	bl_parent_id = "MCPREP_PT_spawn"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_category = "MCprep"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		is_obj_mode = context.mode == "OBJECT"
		is_pose_mode = context.mode == "POSE"
		if not is_obj_mode and not is_pose_mode:
			draw_mode_warning(self.layout)
			return
		item_spawner(self, context)

	def draw_header(self, context):
		if not env.use_icons or env.preview_collections["main"] == "":
			return
		icon = env.preview_collections["main"].get("sword_icon")
		if not icon:
			return
		self.layout.label(text="", icon_value=icon.icon_id)


class MCPREP_PT_effects_spawner(bpy.types.Panel):
	"""MCprep panel for effects spawning"""
	bl_label = "Effects + weather"
	bl_parent_id = "MCPREP_PT_spawn"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_category = "MCprep"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		is_obj_mode = context.mode == "OBJECT"
		if not is_obj_mode:
			draw_mode_warning(self.layout)
			return
		effects_spawner(self, context)

	def draw_header(self, context):
		if not env.use_icons or env.preview_collections["main"] == "":
			return
		icon = env.preview_collections["main"].get("effects_icon")
		if not icon:
			return
		self.layout.label(text="", icon_value=icon.icon_id)


class MCPREP_PT_entity_spawner(bpy.types.Panel):
	"""MCprep panel for entity spawning"""
	bl_label = "Entity spawner"
	bl_parent_id = "MCPREP_PT_spawn"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_category = "MCprep"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		is_obj_mode = context.mode == "OBJECT"
		if not is_obj_mode:
			draw_mode_warning(self.layout)
			return
		entity_spawner(self, context)

	def draw_header(self, context):
		if not env.use_icons or env.preview_collections["main"] == "":
			return
		icon = env.preview_collections["main"].get("entity_icon")
		if not icon:
			return
		self.layout.label(text="", icon_value=icon.icon_id)


class MCPREP_PT_meshswap_spawner(bpy.types.Panel):
	"""MCprep panel for meshswap spawning"""
	bl_label = "Meshswap spawner"
	bl_parent_id = "MCPREP_PT_spawn"
	bl_space_type = "VIEW_3D"
	bl_region_type = 'UI'
	bl_category = "MCprep"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		if addon_just_updated():
			restart_layout(self.layout)
			return
		is_obj_mode = context.mode == "OBJECT"
		if not is_obj_mode:
			draw_mode_warning(self.layout)
			return
		meshswap_spawner(self, context)

	def draw_header(self, context):
		if not env.use_icons or env.preview_collections["main"] == "":
			return
		icon = env.preview_collections["main"].get("meshswap_icon")
		if not icon:
			return
		self.layout.label(text="", icon_value=icon.icon_id)


# -----------------------------------------------------------------------------
# Above for UI
# Below for registration stuff
# -----------------------------------------------------------------------------


def draw_mcprepadd(self, context):
	"""Append to Shift+A, icon for top-level MCprep section."""
	layout = self.layout
	pcoll = env.preview_collections["main"]
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
	if env.preview_collections["main"] != "":
		sword_icon = env.preview_collections["main"]["sword_icon"]
	else:
		sword_icon = None

	if sword_icon:
		row.operator(
			"mcprep.spawn_item", text=txt,
			icon_value=sword_icon.icon_id).filepath = path
	else:
		row.operator("mcprep.spawn_item", text=txt).filepath = path


# -----------------------------------------------
# Addon wide properties (aside from user preferences)
# -----------------------------------------------


class McprepProps(bpy.types.PropertyGroup):
	"""Properties saved to an individual scene"""

	# not available here
	# addon_prefs = util.get_user_preferences()

	# depreciated, keeping to prevent re-registration errors
	show_settings_material: bpy.props.BoolProperty(
		name="show material settings",
		description="Show extra MCprep panel settings",
		default=False)
	show_settings_skin: bpy.props.BoolProperty(
		name="show skin settings",
		description="Show extra MCprep panel settings",
		default=False)
	show_settings_optimizer: bpy.props.BoolProperty(
		name="show optimizer settings",
		description="Show extra MCprep panel settings",
		default=False)
	show_settings_spawner: bpy.props.BoolProperty(
		name="show spawner settings",
		description="Show extra MCprep panel settings",
		default=False)
	show_settings_effect: bpy.props.BoolProperty(
		name="show effect settings",
		description="Show extra MCprep panel settings",
		default=False)

	# Rig settings
	spawn_rig_category: bpy.props.EnumProperty(
		name="Mob category",
		description="Category of mobs & character rigs to spawn",
		update=mobs.spawn_rigs_category_load,
		items=mobs.spawn_rigs_categories
	)
	spawn_mode: bpy.props.EnumProperty(
		name="Spawn Mode",
		description="Set mode for rig/object spawner",
		items=[
			('mob', 'Mob', 'Show mob spawner'),
			('model', 'Block', 'Show model (block) spawner'),
			('item', 'Item', 'Show item spawner'),
			('entity', 'Entity', 'Show entity spawner'),
			('meshswap', 'MeshSwap', 'Show MeshSwap spawner')]
	)

	# spawn lists
	mob_list: bpy.props.CollectionProperty(type=spawn_util.ListMobAssets)
	mob_list_index: bpy.props.IntProperty(default=0)
	mob_list_all: bpy.props.CollectionProperty(
		type=spawn_util.ListMobAssetsAll)
	meshswap_list: bpy.props.CollectionProperty(
		type=spawn_util.ListMeshswapAssets)
	meshswap_list_index: bpy.props.IntProperty(default=0)
	item_list: bpy.props.CollectionProperty(type=spawn_util.ListItemAssets)
	item_list_index: bpy.props.IntProperty(default=0)
	material_list: bpy.props.CollectionProperty(
		type=material_manager.ListMaterials)
	material_list_index: bpy.props.IntProperty(default=0)
	entity_list: bpy.props.CollectionProperty(type=spawn_util.ListEntityAssets)
	entity_list_index: bpy.props.IntProperty(default=0)
	model_list: bpy.props.CollectionProperty(type=spawn_util.ListModelAssets)
	model_list_index: bpy.props.IntProperty(default=0)

	# Effects are uniqune in that they are loaded into a list structure,
	# but the UI list itself is not directly displayed. Rather, dropdowns
	# will iterate over this to populate based on type.
	effects_list: bpy.props.CollectionProperty(type=spawn_util.ListEffectsAssets)
	effects_list_index: bpy.props.IntProperty(default=0)


# -----------------------------------------------------------------------------
# Register functions
# -----------------------------------------------------------------------------


classes = (
	McprepPreference,
	McprepProps,
	MCPREP_MT_mob_spawner,
	MCPREP_MT_meshswap_place,
	MCPREP_MT_item_spawn,
	MCPREP_MT_effect_spawn,
	MCPREP_MT_entity_spawn,
	MCPREP_MT_model_spawn,
	MCPREP_MT_3dview_add,
	MCPREP_PT_world_imports,
	# MCPREP_PT_bridge,
	MCPREP_PT_world_tools,
	MCPREP_PT_skins,
	MCPREP_PT_spawn,
	MCPREP_PT_mob_spawner,
	MCPREP_PT_model_spawner,
	MCPREP_PT_item_spawner,
	MCPREP_PT_effects_spawner,
	MCPREP_PT_entity_spawner,
	MCPREP_PT_meshswap_spawner,
	MCPREP_PT_materials,
	MCPREP_PT_materials_subsettings,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.Scene.mcprep_props = bpy.props.PointerProperty(type=McprepProps)

	# scene settings (later re-attempt to put into props group)
	addon_prefs = util.get_user_preferences()

	bpy.types.Scene.mcprep_mob_path = bpy.props.StringProperty(
		name="Mob folder",
		description="Folder for rigs to spawn in, saved with this blend file data",
		subtype='DIR_PATH',
		update=mobs.update_rig_path,
		default=addon_prefs.mob_path)
	bpy.types.Scene.mcprep_skin_path = bpy.props.StringProperty(
		name="Skin folder",
		description="Folder for skin textures, used in skin swapping",
		subtype='DIR_PATH',
		update=update_skin_path,
		default=addon_prefs.skin_path)
	bpy.types.Scene.meshswap_path = bpy.props.StringProperty(
		name="Meshswap file",
		description="File for meshswap library",
		subtype='FILE_PATH',
		update=meshswap.update_meshswap_path,
		default=addon_prefs.meshswap_path)
	bpy.types.Scene.mcprep_effects_path = bpy.props.StringProperty(
		name="Effects folder",
		description="Folder for handcrafted effects like particles and geonodes",
		subtype='DIR_PATH',
		update=effects.update_effects_path,
		default=addon_prefs.effects_path)
	bpy.types.Scene.mcprep_particle_plane_file = bpy.props.StringProperty(
		name="Particle planes file set",
		description="Has the particle planes file been changed",
		subtype='FILE_PATH',
		default='')
	bpy.types.Scene.entity_path = bpy.props.StringProperty(
		name="Entity file",
		description="File for entity library",
		subtype='FILE_PATH',
		update=entities.update_entity_path,
		default=addon_prefs.entity_path)
	bpy.types.Scene.mcprep_texturepack_path = bpy.props.StringProperty(
		name="Path to texture pack",
		subtype='DIR_PATH',
		description=(
			"Path to a folder containing resources and textures to use "
			"with material prepping"),
		update=update_mcprep_texturepack_path,
		default=addon_prefs.custom_texturepack_path)

	env.verbose = addon_prefs.verbose
	if hasattr(bpy.types, "VIEW3D_MT_add"):  # 2.8
		bpy.types.VIEW3D_MT_add.append(draw_mcprepadd)

	if hasattr(bpy.types, "IMAGE_MT_uvs"):  # 2.8 *and* 2.7
		# this is a dropdown menu for UVs, not a panel
		env.log("IMAGE_MT_uvs registration!")
		bpy.types.IMAGE_MT_uvs.append(mcprep_uv_tools)
	# bpy.types.IMAGE_MT_image.append(mcprep_image_tools) # crashes, re-do ops


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)

	if hasattr(bpy.types, "VIEW3D_MT_add"):  # 2.8
		bpy.types.VIEW3D_MT_add.remove(draw_mcprepadd)

	if hasattr(bpy.types, "IMAGE_MT_uvs"):  # 2.8 *and* 2.7
		bpy.types.IMAGE_MT_uvs.remove(mcprep_uv_tools)
	# bpy.types.IMAGE_MT_image.remove(mcprep_image_tools)

	del bpy.types.Scene.mcprep_props
	del bpy.types.Scene.mcprep_mob_path
	del bpy.types.Scene.meshswap_path
	del bpy.types.Scene.entity_path
	del bpy.types.Scene.mcprep_skin_path
	del bpy.types.Scene.mcprep_texturepack_path
