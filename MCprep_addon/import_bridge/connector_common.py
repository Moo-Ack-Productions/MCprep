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

"""Connector Common module

Pure-python, common set of world exporter-invariant functions and features,
primarily for getting data from a world save file, and common setups used by
any importer executables (including Mineways and jmc2obj).
"""

import os
from . import nbt


class Common(object):
    def __init__(self, exec_path, saves, open_ui=False):
        self.exec_path = exec_path  # path to mineways/Jmc2Obj executable
        self.saves_path = saves  # path to folder of world saves (directories)
        self.open_ui = open_ui  # If true, opens UI; if not, minimized & closes
        self.world = None  # folder name of save, child of saves_path above
        self.layer = None  # one of Overworld, Nether, The End

        self.player_loc = None

    def set_world(self, world, layer="Overworld"):
        """Set the world save and region."""
        if layer not in ["Overworld", "Nether", "The End"]:
            raise Exception("layer")
        self.world = world
        self.layer = layer

    def list_worlds(self):
        """Get the list of MC worlds on this machine"""
        worlds = [
            fold
            for fold in os.listdir(self.saves_path)
            if os.path.isdir(os.path.join(self.saves_path, fold))
        ]
        return worlds

    def world_path(self):
        """Returns the complete world path"""
        if not self.saves_path or not self.world:
            return None
        else:
            return os.path.join(self.saves_path, self.world)

    def get_player_location(self):
        """Looks at level file and returns last player location"""
        path = None
        uuid = None
        location = None
        for root, dirs, files in os.walk(self.world_path()):
            for file in files:
                if file.endswith(".dat") and len(file) == 40:
                    uuid = file[0:36]
                    path = os.path.join(root, file)
                    break
            if path:
                break
                # player(uuid, os.path.join(root, file))

        nbtfile = nbt.nbt.NBTFile(path, "rb")
        if "Pos" in nbtfile:
            location = list(nbtfile["Pos"])
        # elif "bukkit" in nbtfile and "lastPlayed" in nbtfile["bukkit"]:
        # 	location = "{},{},{}".format(
        # 		nbtfile["bukkit"]["lastKnownName"],
        # 		uuid,
        # 		nbtfile["bukkit"]["lastPlayed"])
        # 	location = location.split(',')

        return location

    def get_map_pixels(self, coord_list):
        """Returns a list of pixels top-down for the given world selection

        Arguments:
                coord_list: list/tuple of coordinate pairs, each defining a chunk
        Returns:
                list of a list of hsl tuples for the given coordinates
        """

        # config settings for mapping blocks to top-down pixel rendering

        world = WorldFolder(world_folder)
        bb = world.get_boundingbox()
        world_map = Image.new("RGB", (16 * bb.lenx(), 16 * bb.lenz()))
        t = world.chunk_count()
        try:
            i = 0.0
            for chunk in world.iter_chunks():
                if i % 50 == 0:
                    sys.stdout.write("Rendering image")
                elif i % 2 == 0:
                    sys.stdout.write(".")
                    sys.stdout.flush()
                elif i % 50 == 49:
                    sys.stdout.write("%5.1f%%\n" % (100 * i / t))
                i += 1
                chunkmap = self.get_map_chunk(chunk)
                x, z = chunk.get_coords()
                world_map.paste(chunkmap, (16 * (x - bb.minx), 16 * (z - bb.minz)))
            print(" done\n")
            filename = os.path.basename(world_folder) + ".png"
            world_map.save(filename, "PNG")
            print("Saved map as %s" % filename)
        except KeyboardInterrupt:
            print(" aborted\n")
            filename = os.path.basename(world_folder) + ".partial.png"
            world_map.save(filename, "PNG")
            print("Saved map as %s" % filename)
            return 75  # EX_TEMPFAIL
        if show:
            world_map.show()

    def get_map_chunk(self, chunk):
        """Returns image array for given input chunk"""

        block_ignore = ["air"]
        block_colors = {
            "acacia_leaves": {"h": 114, "s": 64, "l": 22},
            "acacia_log": {"h": 35, "s": 93, "l": 30},
            "air": {"h": 0, "s": 0, "l": 0},
            "andesite": {"h": 0, "s": 0, "l": 32},
            "azure_bluet": {"h": 0, "s": 0, "l": 100},
            "bedrock": {"h": 0, "s": 0, "l": 10},
            "birch_leaves": {"h": 114, "s": 64, "l": 22},
            "birch_log": {"h": 35, "s": 93, "l": 30},
            "blue_orchid": {"h": 0, "s": 0, "l": 100},
            "bookshelf": {"h": 0, "s": 0, "l": 100},
            "brown_mushroom": {"h": 0, "s": 0, "l": 100},
            "brown_mushroom_block": {"h": 0, "s": 0, "l": 100},
            "cactus": {"h": 126, "s": 61, "l": 20},
            "cave_air": {"h": 0, "s": 0, "l": 0},
            "chest": {"h": 0, "s": 100, "l": 50},
            "clay": {"h": 7, "s": 62, "l": 23},
            "coal_ore": {"h": 0, "s": 0, "l": 10},
            "cobblestone": {"h": 0, "s": 0, "l": 25},
            "cobblestone_stairs": {"h": 0, "s": 0, "l": 25},
            "crafting_table": {"h": 0, "s": 0, "l": 100},
            "dandelion": {"h": 60, "s": 100, "l": 60},
            "dark_oak_leaves": {"h": 114, "s": 64, "l": 22},
            "dark_oak_log": {"h": 35, "s": 93, "l": 30},
            "dark_oak_planks": {"h": 35, "s": 93, "l": 30},
            "dead_bush": {"h": 0, "s": 0, "l": 100},
            "diorite": {"h": 0, "s": 0, "l": 32},
            "dirt": {"h": 27, "s": 51, "l": 15},
            "end_portal_frame": {"h": 0, "s": 100, "l": 50},
            "farmland": {"h": 35, "s": 93, "l": 15},
            "fire": {"h": 55, "s": 100, "l": 50},
            "flowing_lava": {"h": 16, "s": 100, "l": 48},
            "flowing_water": {"h": 228, "s": 50, "l": 23},
            "glass_pane": {"h": 0, "s": 0, "l": 100},
            "granite": {"h": 0, "s": 0, "l": 32},
            "grass": {"h": 94, "s": 42, "l": 25},
            "grass_block": {"h": 94, "s": 42, "l": 32},
            "gravel": {"h": 21, "s": 18, "l": 20},
            "ice": {"h": 240, "s": 10, "l": 95},
            "infested_stone": {"h": 320, "s": 100, "l": 50},
            "iron_ore": {"h": 22, "s": 65, "l": 61},
            "iron_bars": {"h": 22, "s": 65, "l": 61},
            "ladder": {"h": 35, "s": 93, "l": 30},
            "lava": {"h": 16, "s": 100, "l": 48},
            "lilac": {"h": 0, "s": 0, "l": 100},
            "lily_pad": {"h": 114, "s": 64, "l": 18},
            "lit_pumpkin": {"h": 24, "s": 100, "l": 45},
            "mossy_cobblestone": {"h": 115, "s": 30, "l": 50},
            "mushroom_stem": {"h": 0, "s": 0, "l": 100},
            "oak_door": {"h": 35, "s": 93, "l": 30},
            "oak_fence": {"h": 35, "s": 93, "l": 30},
            "oak_fence_gate": {"h": 35, "s": 93, "l": 30},
            "oak_leaves": {"h": 114, "s": 64, "l": 22},
            "oak_log": {"h": 35, "s": 93, "l": 30},
            "oak_planks": {"h": 35, "s": 93, "l": 30},
            "oak_pressure_plate": {"h": 35, "s": 93, "l": 30},
            "oak_stairs": {"h": 114, "s": 64, "l": 22},
            "peony": {"h": 0, "s": 0, "l": 100},
            "pink_tulip": {"h": 0, "s": 0, "l": 0},
            "poppy": {"h": 0, "s": 100, "l": 50},
            "pumpkin": {"h": 24, "s": 100, "l": 45},
            "rail": {"h": 33, "s": 81, "l": 50},
            "red_mushroom": {"h": 0, "s": 50, "l": 20},
            "red_mushroom_block": {"h": 0, "s": 50, "l": 20},
            "rose_bush": {"h": 0, "s": 0, "l": 100},
            "sugar_cane": {"h": 123, "s": 70, "l": 50},
            "sand": {"h": 53, "s": 22, "l": 58},
            "sandstone": {"h": 48, "s": 31, "l": 40},
            "seagrass": {"h": 94, "s": 42, "l": 25},
            "sign": {"h": 114, "s": 64, "l": 22},
            "spruce_leaves": {"h": 114, "s": 64, "l": 22},
            "spruce_log": {"h": 35, "s": 93, "l": 30},
            "stone": {"h": 0, "s": 0, "l": 32},
            "stone_slab": {"h": 0, "s": 0, "l": 32},
            "tall_grass": {"h": 94, "s": 42, "l": 25},
            "tall_seagrass": {"h": 94, "s": 42, "l": 25},
            "torch": {"h": 60, "s": 100, "l": 50},
            "snow": {"h": 240, "s": 10, "l": 85},
            "spawner": {"h": 180, "s": 100, "l": 50},
            "vine": {"h": 114, "s": 64, "l": 18},
            "wall_torch": {"h": 60, "s": 100, "l": 50},
            "water": {"h": 228, "s": 50, "l": 23},
            "wheat": {"h": 123, "s": 60, "l": 50},
            "white_wool": {"h": 0, "s": 0, "l": 100},
        }

        pixels = b""

        for z in range(16):
            for x in range(16):
                # Find the highest block in this column
                max_height = chunk.get_max_height()
                ground_height = max_height
                tints = []
                for y in range(max_height, -1, -1):
                    block_id = chunk.get_block(x, y, z)
                    if block_id != None:
                        if block_id not in block_ignore or y == 0:
                            # Here is ground level
                            ground_height = y
                            break

                if block_id != None:
                    if block_id in block_colors:
                        color = block_colors[block_id]
                    else:
                        color = {"h": 0, "s": 0, "l": 100}
                        print("warning: unknown color for block id: %s" % block_id)
                        print("hint: add that block to the 'block_colors' map")
                else:
                    color = {"h": 0, "s": 0, "l": 0}

                height_shift = 0  # (ground_height-64)*0.25

                final_color = {
                    "h": color["h"],
                    "s": color["s"],
                    "l": color["l"] + height_shift,
                }
                if final_color["l"] > 100:
                    final_color["l"] = 100
                if final_color["l"] < 0:
                    final_color["l"] = 0

                # Apply tints from translucent blocks
                for tint in reversed(tints):
                    final_color = hsl_slide(final_color, tint, 0.4)

                rgb = hsl2rgb(final_color["h"], final_color["s"], final_color["l"])

                pixels += pack("BBB", rgb[0], rgb[1], rgb[2])

        im = Image.frombytes("RGB", (16, 16), pixels)

    def run_export_single(self, obj_path, coord_a, coord_b):
        """Run export based on world name and coordinates."""
        return self.run_export_multiple(obj_path, [[coord_a, coord_b]])

    def run_export_multiple(self, export_path, coord_list):
        """Run export based on world name and coordinates.

        Arguments:
                world: Name of the world matching folder in save folder
                min_corner: First coordinate for volume
                max_corner: Second coordinate for volume
        Returns:
                List of intended obj files, may not exist yet
        """
        return []

    def run_async_proc(self, func, args):
        """Run a function execution in another thread"""
