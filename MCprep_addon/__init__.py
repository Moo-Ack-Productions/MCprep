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
https://theduckcow.com/privacy-policy/
which should have been present on the original download page.

Source code available on github as well as more information:
https://github.com/TheDuckCow/MCprep

Authors: Patrick W. Crawford, Google LLC
License: GPLv3
Disclaimer: This is not an official Google product

"""

# ----------------------------- For any developer ---------------------------- #
# Increment this number for each time you get a "inconsistent use of spaces and tab error"
# 								error = 51

bl_info = {
	"name": "MCprep Kaion",
	"category": "Object",
	"version": (3, 4, 1, 3),
	"blender": (2, 80, 0),
	"location": "3D window toolshelf > MCprep tab",
	"description": "Rolling release version of MCprep",
	"warning": "",
	"wiki_url": "https://TheDuckCow.com/MCprep",
	"author": "StandingPad Animations",
	"tracker_url": "https://github.com/StandingPadAnimations/MCprep-Kaion/issues"
}

import importlib

if "load_modules" in locals():
	importlib.reload(load_modules)
else:
	from . import load_modules

import bpy


def register():
	load_modules.register(bl_info)


def unregister():
	load_modules.unregister(bl_info)


if __name__ == "__main__":
	register()
