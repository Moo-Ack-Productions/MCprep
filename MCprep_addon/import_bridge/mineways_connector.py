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

"""Mineways Connector

Pure-python wrapper for running and managing Mienways exports.
"""

import tempfile
import os
import platform
from subprocess import Popen, PIPE

from . import connector_common as common

# import connector_common as common


class MinewaysConnector(common.Common):
    """Pure python bridge class for calling and controlling Mineways sans UI"""

    def save_script(self, cmds):
        """Save script commands to temp file, returning the path"""
        fd, path = tempfile.mkstemp(suffix=".mwscript")
        try:
            with os.fdopen(fd, "w") as tmp:
                tmp.write("\n".join(cmds) + "\n")
        except Exception as err:
            print("Error occured:", err)
        return path

    def run_mineways_command(self, cmd_file):
        """Open mineways exec, with file if relevant"""

        # TMP, create log output file
        # logout = 'Z:\\Users\\patrickcrawford\\Desktop\\mineways_logging.text'
        # logout = '/Users/patrickcrawford/Desktop/mineways_logging.text'

        if platform.system() == "Darwin":  # ie OSX
            # if OSX, include wine in command (assumes installed)
            cmd = ["wine", self.exec_path, cmd_file]  # , '-l', logout
        else:
            cmd = [self.exec_path, cmd_file]

        if self.open_ui is False:
            cmd.append("-m")

        print("Commands sent to mineways:")
        print(cmd)
        p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, err = p.communicate(b"")
        print(str(stdout))

        if err != b"":
            return "Error occured while running command: " + str(err)
        return [False, []]

    def default_mcprep_obj(self):
        """Decent default commands to set for output"""
        cmds = [
            "Set render type: Wavefront OBJ absolute indices",
            "Units for the model vertex data itself: meters",
            "File type: Export full color texture patterns",
            "Texture output RGB: YES",
            "Texture output A: no",  # default was YES, matters?
            "Texture output RGBA: YES",
            "Export separate objects: YES",
            "Individual blocks: no",
            "Material per object: YES",
            "Split by block type: YES",
            "G3D full material: no",
            "Make Z the up direction instead of Y: no",
            "Create composite overlay faces: no",
            "Center model: no",  # default YES
            "Export lesser blocks: YES",
            "Fatten lesser blocks: no",
            "Create block faces at the borders: no",  # default YES
            "Make tree leaves solid: no",
            "Use biomes: no",
            "Rotate model 0.000000 degrees",
            "Scale model by making each block 1000 mm high",
            "Fill air bubbles: no; Seal off entrances: no; Fill in isolated tunnels in base of model: no",
            "Connect parts sharing an edge: no; Connect corner tips: no; Weld all shared edges: no",
            "Delete floating objects: trees and parts smaller than 16 blocks: no",
            "Hollow out bottom of model, making the walls 1000 mm thick: no; Superhollow: no",
            "Melt snow blocks: no",
        ]
        return cmds

    def run_export_multiple(self, export_path, coord_list):
        """Run mineways export based on world name and coordinates.

        Arguments:
                world: Name of the world matching folder in save folder
                min_corner: First coordinate for volume
                max_corner: Second coordinate for volume
        Returns:
                List of intended obj files, may not exist yet
        """

        cmds = []
        cmds.append("Minecraft world: " + str(self.world))
        if self.layer:
            cmds.append("View " + self.layer)

        # Add all default world options relevant for 3D rendering
        cmds += self.default_mcprep_obj()

        for coord_a, coord_b in coord_list:
            if len(coord_a) != 3 or len(coord_b) != 3:
                raise Exception("Coordinates must be length 3")
            for point in coord_a + coord_b:
                if not isinstance(point, int):
                    raise Exception("Coordinates must be integers")

            cmds.append(
                "Selection location min to max: {}, {}, {} to {}, {}, {}".format(
                    min(coord_a[0], coord_b[0]),
                    min(coord_a[1], coord_b[1]),
                    min(coord_a[2], coord_b[2]),
                    max(coord_a[0], coord_b[0]),
                    max(coord_a[1], coord_b[1]),
                    max(coord_a[2], coord_b[2]),
                )
            )

            # backslash paths for both OSX via wine and Windows
            if not self.open_ui:
                outfile = export_path.replace("/", "\\")
                # outfile = export_path + '\\out_file_test.obj'
                # e.g. Z:\Users\...\out_file_test.obj
                cmds.append("Export for rendering: " + outfile)

        if not self.open_ui:
            cmds.append("Close")  # ensures Mineways closes at the end

        cmd_file = self.save_script(cmds)
        print(cmd_file)
        res = self.run_mineways_command(cmd_file)
        print("Success?", res)
        os.remove(cmd_file)
        # if os.path.isfile(outfile): # also check time


def run_test():
    """Run default test open and export."""

    exec_path = (
        "/Users/patrickcrawford/Documents/blender/minecraft/mineways/Mineways.exe"
    )
    saves_path = "/Users/patrickcrawford/Library/Application Support/minecraft/saves/"

    connector = MinewaysConnector(exec_path, saves_path)
    print("Running Mineways - MCprep bridge test")
    worlds = connector.list_worlds()
    print(worlds)

    world = "QMAGNET's Test Map [1.12.1] mod"
    print("using hard-coded world: ", world)
    coord_a = [198, 43, 197]  # same as the "Selection", vs non-empty selection
    coord_b = [237, 255, 235]  #

    # takes single set of coordinate inputs,
    # the multi version would have a list of 2-coords
    print("Running export")
    obj_path = (
        "C:\\Users\\patrickcrawford\\Desktop\\temp\\out_file_test.obj"  # also works
    )
    # out_path = 'Z:\\Users\\patrickcrawford\\Desktop\\temp'  # def. works
    connector.set_world(world)
    connector.run_export_single(obj_path, coord_a, coord_b)


if __name__ == "__main__":
    run_test()
