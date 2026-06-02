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

from dataclasses import dataclass
from pathlib import Path
from typing import final, override

from . import ExportBuilder, InterpreterWrapper
from ..conf import env, MCprepError
from ..commonmcobj_parser import CommonMCOBJTextureType

@final
@dataclass
class Jmc2OBJExportBuilder(ExportBuilder):
    world_path: str | None = None # Necessary because jmc2OBJ expects the world path last
    xz_min_max: tuple[int, int, int, int] | None = None # Used for offsets

    @override
    def __post_init__(self) -> None:
        self.interpreter = InterpreterWrapper("java", ["-jar"])

    @override
    def set_world_path(self, world: Path) -> None | MCprepError:
        base_check = super().set_world_path(world)
        if base_check is not None:
            return base_check
        self.world_path = str(world)

    @override
    def set_export_bounds(self, min_bounds: tuple[int, int, int], max_bounds: tuple[int, int, int]) -> None | MCprepError:
        base_check = super().set_export_bounds(min_bounds, max_bounds)
        if base_check is not None:
            return base_check

        self.xz_min_max = (min_bounds[0],min_bounds[2],max_bounds[0],max_bounds[2])
        self.args += [f"--area={','.join(str(x) for x in self.xz_min_max)}",
                      f"--height={min_bounds[1]},{max_bounds[1]}"]

    @override
    def set_export_offset(self, offset: tuple[float, float, float]) -> None | MCprepError:
        # If a Y-offset other than 0 is used,
        # assume it was centered. Otherwise, check
        # if the X and Z are centered (to handle the
        # edge case of an export with minY set to 0)
        # Source: https://github.com/jmc2obj/j-mc-2-obj/blob/master/src/org/jmc/ObjExporter.java#L98-L103
        if offset[1] != 0:
            self.args.append("--offset=center")
            return

        # Kind of a horrifying block, but this
        # is enough to make Mypy not freak out from
        # type narrowing
        def average_offset(m: int, n: int) -> int:
            return int(-1 * (m + (n - m) / 2))

        # Use an assert as this function should
        # be called after the bounds are set
        assert self.xz_min_max is not None

        x_average = average_offset(self.xz_min_max[0], self.xz_min_max[2])
        z_average = average_offset(self.xz_min_max[1], self.xz_min_max[3])
        if offset[0] == x_average and offset[1] == z_average:
            self.args.append("--offset=center")
        else:
            self.args.append(f"--offset={offset[0]},{offset[2]}")

    @override
    def set_block_scale(self, scale: float) -> None | MCprepError:
        base_check = super().set_block_scale(scale)
        if base_check is not None:
            return base_check
        self.args.append(f"--scale={scale}")

    # As far as we're aware, jmc2OBJ only does tiled
    # exports, not atlas exports
    @override
    def set_texture_type(self, texture_type: CommonMCOBJTextureType) -> None | MCprepError:
        return

    @override
    def set_split_blocks(self, setting: bool) -> None | MCprepError:
        if not setting:
            return
        self.args.append("--object-per-mat")

    @override
    def prep_for_export(self) -> None | MCprepError:
        base_check = super().prep_for_export()
        if base_check is not None:
            return base_check
        if not self.world_path:
            line, file = env.current_line_and_file()
            return MCprepError(Exception(), line, file, "No world path set!")
        self.args.append(f"--output=\"{str(self.output_obj_path)}\"")
        self.args.append(self.world_path)
