from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import override

from . import ExportBuilder
from ..conf import env, MCprepError
from ..commonmcobj_parser import CommonMCOBJTextureType

@dataclass
class Jmc2OBJExportBuilder(ExportBuilder):
    java_executable_path: Path
    args: list[str]
    world_path: str | None # Necessary because jmc2OBJ expects the world path last
    xz_min_max: tuple[int, int, int, int] | None # Used for offsets

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
                      f"--height={min_bounds[1],max_bounds[1]}"]

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
    def create_export(self) -> None | MCprepError:
        base_check = super().create_export()
        if base_check is not None:
            return base_check

        # Java is a required executable to run jmc2OBJ
        if not self.java_executable_path.exists():
            line, file = env.current_line_and_file()
            return MCprepError(FileNotFoundError(), line, file, f"Java not found: {str(self.executable_path)}")
        elif self.java_executable_path.is_dir():
            line, file = env.current_line_and_file()
            return MCprepError(IsADirectoryError(), line, file, f"Java path is a directory: {str(self.executable_path)}")

        if self.world_path is None:
            line, file = env.current_line_and_file()
            return MCprepError(FileNotFoundError(), line, file, f"No world path defined!") 

        subprocess_args = [str(self.java_executable_path), "-jar", str(self.executable_path)]
        subprocess_args += self.args
        subprocess_args.append(self.world_path)

        _ = subprocess.run(subprocess_args)
