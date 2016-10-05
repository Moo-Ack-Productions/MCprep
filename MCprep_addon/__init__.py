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
# Additional disclaimer & terms
# -----------------------------------------------------------------------------

"""
By installing and using this addon, you agree to the following privacy policy:
http://theduckcow.com/privacy-policy/
which should have been present on the original download page.


This code is open source under the MIT license.
Its purpose is to increase the workflow of creating Minecraft
related renders and animations, by automating certain tasks.

Developed and tested for blender 2.72* up to the indicated blender version below
* testing is out of date

Source code available on github as well as more information:
https://github.com/TheDuckCow/MCprep

"""

# -----------------------------------------------------------------------------
# 
# -----------------------------------------------------------------------------


bl_info = {
	"name": "MCprep",
	"category": "Object",
	"version": (3, 0, 0),
	"blender": (2, 78, 0),
	"location": "3D window toolshelf > MCprep tab",
	"description": "Minecraft workflow addon for rendering and animation",
	"warning": "",
	"wiki_url": "https://TheDuckCow.com/MCprep",
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
	importlib.reload(tracking)
	

	conf.init()  #initialize global variables
	if conf.v:print("Reload, verbose is enabled")

else:
	import bpy
	from . import (
		conf,
		mcprep_ui,
		materials,
		meshswap,
		spawner,
		addon_updater_ops,
		tracking
	)
	conf.init()  #initialize global variables
	if conf.v:print("MCprep: Verbose is enabled")
	if conf.vv:print("MCprep: Very Verbose is enabled")


def register():
	
	# call error if modules not able to import, popup message
	# if "conf" not in locals():
	# 	raise ValueError("Addon not installed properly, you MUST install the MCprep zip file, NOT the __init__.py file. See http://bit.ly/MCprep")

	bpy.utils.register_module(__name__)
	mcprep_ui.register()
	materials.register()
	meshswap.register()
	spawner.register()
	tracking.register(bl_info)

	# addon updater code and configurations
	addon_updater_ops.register(bl_info)
	

def unregister():

	bpy.utils.unregister_module(__name__)
	mcprep_ui.unregister()
	materials.unregister()
	meshswap.unregister()
	spawner.unregister()
	tracking.unregister()
	


if __name__ == "__main__":
	register()

