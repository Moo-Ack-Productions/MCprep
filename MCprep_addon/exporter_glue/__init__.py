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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import final

from ..conf import env, MCprepError
from ..commonmcobj_parser import CommonMCOBJTextureType

# Class for interpreter and interpreter
# arguments; frozen to enforce some level
# of immutability
@final
@dataclass(frozen=True)
class InterpreterWrapper:
    interpreter_exec: Path | str
    interpreter_args: list[str]

# Base exporter class, not meant to be used directly
@dataclass
class ExportBuilder(ABC):
    executable_path: Path
    output_obj_path: Path
    args: list[str] = field(default_factory=lambda: [])
    interpreter: InterpreterWrapper | None = field(init=False)

    # Make the interpreter a post-init
    # field to keep the reload operators
    # simple
    @abstractmethod
    def __post_init__(self) -> None:
        self.interpreter = None

    @abstractmethod
    def set_world_path(self, world: Path) -> None | MCprepError:
        if not world.exists():
            line, file = env.current_line_and_file()
            return MCprepError(FileNotFoundError(), line, file, f"Cannot find world: {str(world)}")
        elif not world.is_dir():
            line, file = env.current_line_and_file()
            return MCprepError(NotADirectoryError(), line, file, f"World must be a directory: {str(world)}")

    @abstractmethod
    def set_export_bounds(self, min_bounds: tuple[int, int, int], max_bounds: tuple[int, int, int]) -> None | MCprepError:
        if min_bounds == max_bounds:
            line, file = env.current_line_and_file()
            return MCprepError(ArithmeticError(), line, file, "Cannot export a bound of size 0!")

    @abstractmethod
    def set_export_offset(self, offset: tuple[float, float, float]) -> None | MCprepError:
        pass

    @abstractmethod
    def set_block_scale(self, scale: float) -> None | MCprepError:
        if scale < 0:
            line, file = env.current_line_and_file()
            return MCprepError(FloatingPointError(), line, file, "Cannot have a negative scale!")

    @abstractmethod
    def set_texture_type(self, texture_type: CommonMCOBJTextureType) -> None | MCprepError:
        pass

    @abstractmethod
    def set_split_blocks(self, setting: bool) -> None | MCprepError:
        pass

    @abstractmethod
    def prep_for_export(self) -> None | MCprepError:
        if not self.executable_path.exists():
            line, file = env.current_line_and_file()
            return MCprepError(FileNotFoundError(), line, file, f"Executable not found: {str(self.executable_path)}")
        elif self.executable_path.is_dir():
            line, file = env.current_line_and_file()
            return MCprepError(IsADirectoryError(), line, file, f"Executable path is a directory: {str(self.executable_path)}")

