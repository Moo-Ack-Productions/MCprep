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


import importlib

import bpy

# Per module loading for stable, in-session updates, even if new files are added
if "conf" in locals():
	importlib.reload(conf)
else:
	from . import conf

if "tracking" in locals():
	importlib.reload(tracking)
else:
	from . import tracking

if "util_operators" in locals():
	importlib.reload(util_operators)
else:
	from . import util_operators

if "material_manager" in locals():
	importlib.reload(material_manager)
else:
	from .materials import material_manager

if "prep" in locals():
	importlib.reload(prep)
else:
	from .materials import prep

if "sequences" in locals():
	importlib.reload(sequences)
else:
	from .materials import sequences

if "skin" in locals():
	importlib.reload(skin)
else:
	from .materials import skin

if "sync" in locals():
	importlib.reload(sync)
else:
	from .materials import sync

if "uv_tools" in locals():
	importlib.reload(uv_tools)
else:
	from .materials import uv_tools

if "spawn_util" in locals():
	importlib.reload(spawn_util)
else:
	from .spawner import spawn_util

if "meshswap" in locals():
	importlib.reload(meshswap)
else:
	from .spawner import meshswap

if "mcmodel" in locals():
	importlib.reload(mcmodel)
else:
	from .spawner import mcmodel

if "mobs" in locals():
	importlib.reload(mobs)
else:
	from .spawner import mobs

if "entities" in locals():
	importlib.reload(entities)
else:
	from .spawner import entities

if "world_tools" in locals():
	importlib.reload(world_tools)
else:
	from . import world_tools

if "item" in locals():
	importlib.reload(item)
else:
	from .spawner import item

if "effects" in locals():
	importlib.reload(effects)
else:
	from .spawner import effects

# if "bridge" in locals():
# 	importlib.reload(bridge)
# else:
# 	from .mineways_bridge import bridge

if "mcprep_ui" in locals():
	importlib.reload(mcprep_ui)
else:
	from . import mcprep_ui

if "util" in locals():
	importlib.reload(util)
else:
	from . import util

if "tracking" in locals():
	importlib.reload(tracking)
else:
	from . import tracking

if "addon_updater" in locals():
	importlib.reload(addon_updater)
else:
	from . import addon_updater

if "addon_updater_ops" in locals():
	importlib.reload(addon_updater_ops)
else:
	from . import addon_updater_ops

if "generate" in locals():
	importlib.reload(generate)
else:
	from .materials import generate
if "vivy_materials" in locals():
	importlib.reload(vivy_materials)
else:
	from .materials import vivy_materials

if "vivy_ui" in locals():
	importlib.reload(vivy_ui)
else:
	from . import vivy_ui 
if "vivy_editor" in locals():
	importlib.reload(vivy_editor)
else:
	from . import vivy_editor

# Only include those with a register function, which is not all
module_list = (
	conf,
	util_operators,
	material_manager,
	prep,
	skin,
	sequences,
	sync,
	uv_tools,
	spawn_util,
	meshswap,
	mobs,
	entities,
	mcmodel,
	item,
	effects,
	world_tools,
	# bridge,
	mcprep_ui,
)

vivy_modules = (
	vivy_materials,
	vivy_ui,
	vivy_editor
)


def register(bl_info):
	if not conf.env.use_direct_i18n:
		from . import translations
		bpy.app.translations.register(__name__, translations.MCPREP_TRANSLATIONS)

	tracking.register(bl_info)
	for mod in module_list:
		mod.register()

	if conf.ENABLE_VIVY:
		for mod in vivy_modules:
			mod.register()

	# addon updater code and configurations
	addon_updater_ops.register(bl_info)

	# Inject the custom updater function, to use release zip instead src.
	addon_updater_ops.updater.select_link = conf.updater_select_link_function

	conf.env.log("MCprep: Verbose is enabled")
	conf.env.log("MCprep: Very Verbose is enabled", vv_only=True)



def unregister(bl_info):
	for mod in reversed(module_list):
		mod.unregister()

	if conf.ENABLE_VIVY:
		for mod in reversed(vivy_modules):
			mod.register()

	tracking.unregister()
	conf.unregister()

	# addon updater code and configurations
	addon_updater_ops.unregister()
	if not conf.env.use_direct_i18n:
		bpy.app.translations.unregister(__name__)
