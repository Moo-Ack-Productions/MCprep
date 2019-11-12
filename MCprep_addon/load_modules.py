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
	# importlib.reload(bridge)
	importlib.reload(mcprep_ui)
	importlib.reload(util)
	importlib.reload(tracking)
	importlib.reload(addon_updater)
	importlib.reload(addon_updater_ops)
	importlib.reload(generate)

	if conf.v:
		print("Reload, verbose is enabled")

else:
	import bpy
	from . import (
		conf,
		tracking,
		mcprep_ui,
		util_operators,
		world_tools,
		addon_updater_ops,
		util,
		tracking,
		addon_updater,
		addon_updater_ops
	)
	from .materials import(
		prep,
		skin,
		sequences,
		generate
		)
	from .spawner import(
		spawn_util,
		mobs,
		meshswap,
		item
		)
	# from .mineways_bridge import(
	# 	bridge
	# 	)


module_list = (
	util_operators,
	prep,
	skin,
	sequences,
	spawn_util,
	meshswap,
	mobs,
	item,
	world_tools,
	# bridge,
	mcprep_ui,
	)


def register(bl_info):
	conf.register()
	tracking.register(bl_info)
	for mod in module_list:
		mod.register()

	# addon updater code and configurations
	addon_updater_ops.register(bl_info)

	if conf.v:
		print("MCprep: Verbose is enabled")
	if conf.vv:
		print("MCprep: Very Verbose is enabled")


def unregister(bl_info):
	for mod in reversed(module_list):
		mod.unregister()

	tracking.unregister()
	conf.unregister()

	# addon updater code and configurations
	addon_updater_ops.unregister()
