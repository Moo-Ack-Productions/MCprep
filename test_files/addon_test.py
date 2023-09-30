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

import unittest

import bpy


class AddonTest(unittest.TestCase):
    """Create addon level tests, and ensures enabled for later tests."""

    def test_enable(self):
        """Ensure the addon can be directly enabled."""
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def test_disable_enable(self):
        """Ensure we can safely disable and re-enable addon without error."""
        bpy.ops.preferences.addon_disable(module="MCprep_addon")
        bpy.ops.preferences.addon_enable(module="MCprep_addon")


if __name__ == '__main__':
    unittest.main(exit=False)
