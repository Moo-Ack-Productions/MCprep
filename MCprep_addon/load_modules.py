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

# modules = {
# 	0:{"name":"conf", "path":""},
# 	1:{"name":"tracking", "path":""},
# 	2:{"name":"spawn_util", "path":"spawner."},
# 	3:{"name":"meshswap", "path":"spawner."},
# 	4:{"name":"mobs", "path":"spawner."},
# 	5:{"name":"prep", "path":"materials."},
# 	6:{"name":"skin", "path":"materials."},
# 	7:{"name":"world_tools", "path":""},
# 	8:{"name":"mcprep_ui", "path":""}
# }

# for mod in sorted(list(modules)):
# 	if modules[mod]["name"] in locals():
# 		importlib.reload(locals()[modules[mod]["name"]])
# 	else:
# 		importlib.import_module(
# 			modules[mod]["path"] + modules[mod]["name"],
# 			__file__)

if "bpy" in locals():

	importlib.reload(conf)
	importlib.reload(tracking)
	importlib.reload(util_operators)
	importlib.reload(prep)
	importlib.reload(skin)
	importlib.reload(sequences)
	importlib.reload(spawn_util)
	importlib.reload(meshswap)
	importlib.reload(mobs)
	importlib.reload(world_tools)
	importlib.reload(item)
	importlib.reload(mcprep_ui)


	# for mod in sorted(list(modules)):
	# 	if modules[mod]["name"] in locals():
	# 		importlib.reload(locals()[modules[mod]["name"]])

	if conf.v:print("Reload, verbose is enabled")
	if conf.vv:print("MCprep: Very Verbose is enabled")

else:
	import bpy

	from . import (
		conf,
		tracking,
		mcprep_ui,
		util_operators,
		world_tools,
		addon_updater_ops
	)
	from .materials import(
		prep,
		skin,
		sequences
		)
	from .spawner import(
		spawn_util,
		mobs,
		meshswap,
		item
		)


def register(bl_info):


	# for mod_num in sorted(list(modules)):
	# 	mod = locals()[modules[mod_num]['name']]
	# 	if hasattr(mod, "register"):
	# 		getattr(mod, "register")()
	# 	else:
	# 		print("Error, {} does not have a register function".format(
	# 			modules[mod_num]['name']))

	conf.register()
	tracking.register(bl_info)
	util_operators.register()
	prep.register()
	skin.register()
	sequences.register()
	spawn_util.register()
	meshswap.register()
	mobs.register()
	item.register()
	world_tools.register()
	mcprep_ui.register()

	# addon updater code and configurations
	addon_updater_ops.register(bl_info)

	if conf.v:print("MCprep: Verbose is enabled")
	if conf.vv:print("MCprep: Very Verbose is enabled")


def unregister(bl_info):

	mcprep_ui.unregister()
	world_tools.unregister()
	item.unregister()
	mobs.unregister()
	meshswap.unregister()
	spawn_util.unregister()
	sequences.unregister()
	skin.unregister()
	prep.unregister()
	util_operators.unregister()
	tracking.unregister()
	conf.unregister()

	# addon updater code and configurations
	addon_updater_ops.unregister()
