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

# -----------------------------------------------------------------------------
# Additional disclaimer & terms
# -----------------------------------------------------------------------------

"""
By installing and using this addon, you agree to the following privacy policy:
http://theduckcow.com/privacy-policy/
which should have been present on the original download page.

Source code available on github as well as more information:
https://github.com/TheDuckCow/MCprep

Authors: Patrick W. Crawford, Google LLC
License: GPLv3
Disclaimer: This is not an official Google product

"""

# -----------------------------------------------------------------------------
#
# -----------------------------------------------------------------------------


bl_info = {
	"name": "MCprep",
	"category": "Object",
	"version": (3, 0, 3),
	"blender": (2, 78, 0),
	"location": "3D window toolshelf > MCprep tab",
	"description": "Minecraft workflow addon for rendering and animation",
	"warning": "",
	"wiki_url": "http://TheDuckCow.com/MCprep",
	"author": "Patrick W. Crawford <support@theduckcow.com>",
	"tracker_url":"https://github.com/TheDuckCow/MCprep/issues"
}


if "bpy" in locals():

	import importlib
	try:
		conf.init()
	except:
		print("Issue in re-running conf.init()")
	importlib.reload(mcprep_ui)
	importlib.reload(materials)
	importlib.reload(meshswap)
	importlib.reload(spawner)
	importlib.reload(world_tools)
	importlib.reload(tracking)


	conf.init()  #initialize global variables
	if conf.v:print("Reload, verbose is enabled")

else:
	import bpy
	from . import conf
	conf.init()  #initialize global variables

	# import the rest
	from . import (
		mcprep_ui,
		materials,
		meshswap,
		spawner,
		world_tools,
		addon_updater_ops,
		tracking
	)

	if conf.v:print("MCprep: Verbose is enabled")
	if conf.vv:print("MCprep: Very Verbose is enabled")


def register():

	bpy.utils.register_module(__name__)
	mcprep_ui.register()
	materials.register()
	meshswap.register()
	spawner.register()
	world_tools.register()
	tracking.register(bl_info)

	# addon updater code and configurations
	addon_updater_ops.register(bl_info)


def unregister():

	bpy.utils.unregister_module(__name__)
	conf.unregister()
	mcprep_ui.unregister()
	materials.unregister()
	meshswap.unregister()
	spawner.unregister()
	world_tools.unregister()
	tracking.unregister()

	# addon updater code and configurations
	addon_updater_ops.unregister()


if __name__ == "__main__":
	register()
