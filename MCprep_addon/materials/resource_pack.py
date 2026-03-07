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
from enum import auto, Enum
import json
import os
from pathlib import Path
from typing import List, cast, Optional, Tuple, Union, final

import bpy

from MCprep_addon.conf import MCprepError, env

PACK_MCMETA = "pack.mcmeta"


class MCMetaErrorType(Enum):
    MISSING_FIELD = auto()
    FIELD_INVALID = auto()
    PARSED_FIELD_INVALID_TYPE = auto()


@final
class MCMetaIncorrectFormatException(Exception):
    def __init__(
        self,
        msg: str = "",
        resource_pack_name: str = "",
        err_type: MCMetaErrorType = MCMetaErrorType.MISSING_FIELD,
        additional_context: str = "",
    ) -> None:
        super().__init__(msg)

        self.resource_pack_name = resource_pack_name
        self.err_type = err_type
        self.additional_context = additional_context


@final
class MCResourcePackTextureNotFound(Exception):
    def __init__(self, msg: str = "") -> None:
        super().__init__(msg)


@dataclass
class PackVersionData:
    min_format: Tuple[int, int]
    max_format: Tuple[int, int]


@dataclass
class MCResourcePack:
    name: str
    path: Path
    pack_format: Optional[PackVersionData]


def get_resource_pack_info(
    path: Path, dont_parse_pack_mcmeta: bool = False
) -> Union[MCResourcePack, MCprepError]:
    if not path.exists():
        line, file = env.current_line_and_file()
        return MCprepError(
            FileNotFoundError(),
            line,
            file,
            f"Resource pack cannot be found at {str(path)}",
        )
    elif not path.is_dir():
        line, file = env.current_line_and_file()
        return MCprepError(
            NotADirectoryError(),
            line,
            file,
            f"Resource pack not a directory: {str(path)}",
        )

    name = path.name

    # Intended for the default resource
    # pack because it doesn't come with
    # a pack.mcmeta file for some reason.
    #
    # TODO: Figure out a way to extract the
    # pack format of the default resource pack
    # without pack.mcmeta.
    if dont_parse_pack_mcmeta:
        return MCResourcePack(name, path, None)

    pack_meta_json = Path(path, PACK_MCMETA)

    if not pack_meta_json.exists():
        line, file = env.current_line_and_file()
        return MCprepError(
            FileNotFoundError(),
            line,
            file,
            f"pack.mcmeta could not be found for {name}!",
        )
    elif not pack_meta_json.is_file():
        line, file = env.current_line_and_file()
        return MCprepError(
            FileNotFoundError(), line, file, f"pack.mcmeta for {name} is not a file!"
        )

    with open(pack_meta_json, "r") as f:
        data = json.load(f)

    if "pack" not in data:
        line, file = env.current_line_and_file()
        return MCprepError(
            MCMetaIncorrectFormatException(resource_pack_name=name),
            line,
            file,
            f"pack.mcmeta is missing 'pack' field!",
        )

    pack_data = data["pack"]

    min_format = (0, 0)
    max_format = (0, 0)

    # Treat the old format as setting min
    # and max to the same version
    if "pack_format" in pack_data:
        min_format = (pack_data["pack_format"], 0)
        max_format = (pack_data["pack_format"], 0)
    else:
        if "min_format" not in pack_data:
            line, file = env.current_line_and_file()
            return MCprepError(
                MCMetaIncorrectFormatException(resource_pack_name=name),
                line,
                file,
                f"pack.min_format is missing in mcmeta",
            )

        min_raw = pack_data["min_format"]

        if isinstance(min_raw, int):
            min_format = (min_raw, 0)
        elif isinstance(min_raw, list):
            if len(min_raw) == 1:
                min_format = (min_raw[0], 0)
            elif len(min_raw) == 2:
                min_format == tuple(min_raw)  # simpler to convert directly
        else:
            line, file = env.current_line_and_file()
            return MCprepError(
                MCMetaIncorrectFormatException(
                    resource_pack_name=name, err_type=MCMetaErrorType.FIELD_INVALID
                ),
                line,
                file,
                f"'pack.min_format' in mcmeta is not the correct format!",
            )

        if "max_format" not in pack_data:
            line, file = env.current_line_and_file()
            return MCprepError(
                MCMetaIncorrectFormatException(resource_pack_name=name),
                line,
                file,
                f"pack.max_format is missing in mcmeta!",
            )

        max_raw = pack_data["max_format"]

        # Single integers for max_format are interpreted
        # as minor versions, according to the Minecraft Wiki
        # at least
        if isinstance(max_raw, int):
            max_format = (min_format[0], max_raw)
        elif isinstance(max_raw, list):
            if len(max_raw) == 1:
                max_format = (min_format[0], max_raw[0])
            elif len(max_raw) == 2:
                max_format == tuple(max_raw)  # simpler to convert directly
        else:
            line, file = env.current_line_and_file()
            return MCprepError(
                MCMetaIncorrectFormatException(
                    resource_pack_name=name, err_type=MCMetaErrorType.FIELD_INVALID
                ),
                line,
                file,
                f"'pack.max_format' in mcmeta is not the correct format!",
            )

    # Verify data is correct
    #
    # Admittedly, we have a large block of
    # checks here, but it's to make sure that
    # the datatypes are correct at runtime
    # so that we don't have any issues.
    #
    # TODO: Simplify these checks
    line, file = env.current_line_and_file()
    if not isinstance(min_format, tuple):
        return MCprepError(
            MCMetaIncorrectFormatException(
                resource_pack_name=name,
                err_type=MCMetaErrorType.PARSED_FIELD_INVALID_TYPE,
                additional_context=f"Parsed value: {min_format}",
            ),
            line,
            file,
            "min_format is an invalid type after procesing!",
        )
    elif not isinstance(max_format, tuple):
        return MCprepError(
            MCMetaIncorrectFormatException(
                resource_pack_name=name,
                err_type=MCMetaErrorType.PARSED_FIELD_INVALID_TYPE,
                additional_context=f"Parsed value: {max_format}",
            ),
            line,
            file,
            "max_format is an invalid type after processing!",
        )
    elif not len(min_format) == 2:
        return MCprepError(
            MCMetaIncorrectFormatException(
                resource_pack_name=name,
                err_type=MCMetaErrorType.PARSED_FIELD_INVALID_TYPE,
                additional_context=f"Parsed value: {min_format}",
            ),
            line,
            file,
            "min_format is an invalid type after procesing!",
        )
    elif not len(max_format) == 2:
        return MCprepError(
            MCMetaIncorrectFormatException(
                resource_pack_name=name,
                err_type=MCMetaErrorType.PARSED_FIELD_INVALID_TYPE,
                additional_context=f"Parsed value: {max_format}",
            ),
            line,
            file,
            "max_format is an invalid type after procesing!",
        )
    elif not isinstance(min_format[0], int) or not isinstance(min_format[1], int):
        return MCprepError(
            MCMetaIncorrectFormatException(
                resource_pack_name=name,
                err_type=MCMetaErrorType.PARSED_FIELD_INVALID_TYPE,
                additional_context=f"Parsed value: {min_format}",
            ),
            line,
            file,
            "min_format is an invalid type after procesing!",
        )
    elif not isinstance(max_format[0], int) or not isinstance(max_format[1], int):
        return MCprepError(
            MCMetaIncorrectFormatException(
                resource_pack_name=name,
                err_type=MCMetaErrorType.PARSED_FIELD_INVALID_TYPE,
                additional_context=f"Parsed value: {max_format}",
            ),
            line,
            file,
            "max_format is an invalid type after procesing!",
        )

    return MCResourcePack(name, path, PackVersionData(min_format, max_format))


def get_default_pack() -> Union[MCResourcePack, MCprepError]:
    """Return the default texture pack bundled with MCprep."""
    internal_pack = Path(
        cast(str, bpy.path.abspath(bpy.context.scene.mcprep_texturepack_path))
    )
    return get_resource_pack_info(internal_pack)


def find_from_texturepack(
    blockname: str, resource_folder: Path
) -> Union[Path, MCprepError]:
    """Given a blockname (and resource folder), find image filepath.

    Finds textures following any pack which should have this structure, and
    the input folder or default resource folder could target at any of the
    following sublevels above the <subfolder> level.
    //pack_name/assets/minecraft/textures/<subfolder>/<blockname.png>

    Returns:
            - Path if successful
            - MCprepError if error occurs (may return with a message)
    """

    if not resource_folder.exists() or not resource_folder.is_dir():
        env.log("Error, resource folder does not exist")
        line, file = env.current_line_and_file()
        return MCprepError(
            FileNotFoundError(),
            line,
            file,
            f"Resource pack folder at {resource_folder} does not exist!",
        )

    # Check multiple paths, picking the first match (order is important),
    # goal of picking out the /textures folder.
    check_dirs = [
        Path(resource_folder, "textures"),
        Path(resource_folder, "minecraft", "textures"),
        Path(resource_folder, "assets", "minecraft", "textures"),
    ]
    for path in check_dirs:
        if path.exists():
            resource_folder = path
            break

    search_paths = [
        resource_folder,
        # Both singular and plural shown below as it has varied historically.
        Path(resource_folder, "blocks"),
        Path(resource_folder, "block"),
        Path(resource_folder, "items"),
        Path(resource_folder, "item"),
        Path(resource_folder, "entity"),
        Path(resource_folder, "models"),
        Path(resource_folder, "model"),
    ]
    res = None

    # first see if subpath included is found, prioritize use of that
    extensions = [".png", ".jpg", ".jpeg"]
    if "/" in blockname:
        newpath = blockname.replace("/", os.path.sep)
        for ext in extensions:
            if Path(resource_folder, newpath + ext).exists():
                res = Path(resource_folder, newpath + ext)
                return res
        newpath = os.path.basename(blockname)  # case where goes into other subpaths
        for ext in extensions:
            if Path(resource_folder, newpath + ext).exists():
                res = Path(resource_folder, newpath + ext)
                return res

    # fallback (more common case), wide-search for
    for path in search_paths:
        if not path.is_dir():
            continue
        for ext in extensions:
            check_path = Path(path, blockname + ext)
            if check_path.exists() and check_path.is_file():
                res = Path(path, blockname + ext)
                return res

    # Mineways fallback
    for suffix in ["-Alpha", "-RGB", "-RGBA"]:
        if blockname.endswith(suffix):
            res = Path(resource_folder, "mineways_assets", f"mineways{suffix}.png")
            if res.exists() and res.is_file():
                return res

    if res is None:
        line, file = env.current_line_and_file()
        return MCprepError(MCResourcePackTextureNotFound(), line, file)
    return res


def find_texture_from_layers(
    block_name: str, resource_pack_layers: List[MCResourcePack]
) -> Union[Path, MCprepError]:
    """Given a list of resource packs, in order from top to bottom, search for a texture.

    Returns:
        - Path to the texture if it exists in any of the resource packs
        - MCprepError with err_type set to MCResourcePackTextureNotFound
        - If an alternate error occurs, then MCprepError with err_type set
          any other exception class
    """
    for pack in resource_pack_layers:
        res = find_from_texturepack(block_name, pack.path)
        if isinstance(res, MCprepError):
            if isinstance(res.err_type, MCResourcePackTextureNotFound):
                continue
            return res
        return res

    line, file = env.current_line_and_file()
    return MCprepError(MCResourcePackTextureNotFound(), line, file)
