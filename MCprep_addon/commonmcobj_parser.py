# BSD 3-Clause License
# 
# Copyright (c) 2024, Mahid Sheikh <mahid@standingpad.org>
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The parser is under a more permissive BSD 3-Clause license to make it easier 
# for developers to use in non-GPL code. Normally, I wouldn't do dual licensing,
# but in this case, it makes sense as it would allow developers to reuse this 
# parser for their own uses under more permissive terms. This doesn't change anything 
# related to MCprep, which is GPL, as BSD 3-Clause is compatible with GPL. The 
# only part that might conflict is Clause 3, but it could be argued that one
# can't do that under GPL anyway, or any license for that matter, and that 
# Clause 3 is just a reminder to developers.
#
# - Mahid Sheikh

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, TextIO

MAX_SUPPORTED_VERSION = 1

class CommonMCOBJTextureType(Enum):
    ATLAS = "ATLAS"
    INDIVIDUAL_TILES = "INDIVIDUAL_TILES"

@dataclass
class CommonMCOBJ:
    """
    Python representation of the CommonMCOBJ header
    """
    # Version of the CommonMCOBJ spec
    version: int
    
    # Exporter name in all lowercase
    exporter: str 
    
    # Name of source world
    world_name: str 
    
    # Path of source world*
    world_path: str 
    
    # Min values of the selection bounding box
    export_bounds_min: Tuple[int, int, int]
    
    # Max values of the selection bounding box
    export_bounds_max: Tuple[int, int, int]
    
    # Offset from (0, 0, 0)
    export_offset: Tuple[float, float, float]
    
    # Scale of each block in meters; by default, this should be 1 meter
    block_scale: float

    # Coordinate offset for blocks
    block_origin_offset: Tuple[float, float, float]
    
    # Is the Z axis of the OBJ considered up?
    z_up: bool
    
    # Are the textures using large texture atlases or 
    # individual textures?
    texture_type: CommonMCOBJTextureType
    
    # Are blocks split by type?
    has_split_blocks: bool
    
    # Original header
    original_header: Optional[str]

def parse_common_header(header_lines: list[str]) -> CommonMCOBJ:
    """
    Parses the CommonMCOBJ header information from a list of strings.

    header_lines list[str]: 
        list of strings representing each line of the header.

    returns:
        CommonMCOBJ object
    """

    # Split at the colon and clean up formatting
    def clean_and_extract(line: str) -> Tuple[str, str]:
        split = line.split(':', 1)
        pos = 0
        for i,x in enumerate(split[0]):
            if x.isalpha():
                pos = i                      
                break
        return (split[0][pos:], split[1].strip())
    
    # Basic values
    header = CommonMCOBJ(
        version=0,
        exporter="NULL",
        world_name="NULL",
        world_path="NULL",
        export_bounds_min=(0, 0, 0),
        export_bounds_max=(0, 0, 0),
        export_offset=(0, 0, 0),
        block_scale=0,
        block_origin_offset=(0, 0, 0),
        z_up=False,
        texture_type=CommonMCOBJTextureType.ATLAS,
        has_split_blocks=False,
        original_header=None
    )
    
    # Keys whose values do not need extra processing
    NO_VALUE_PARSE = [
        "exporter", 
        "world_name", 
        "world_path",
    ]

    # Keys whose values are tuples
    TUPLE_PARSE_INT = [
        "export_bounds_min",
        "export_bounds_max",
    ]

    TUPLE_PARSE_FLOAT = [
        "export_offset",
        "block_origin_offset"
    ]
    
    # Keys whose values are booleans
    BOOLEAN_PARSE = [
        "z_up",
        "has_split_blocks"
    ]
    
    # Although CommonMCOBJ states that 
    # order does matter in the header, 
    # future versions may change the order
    # of some values, so it's best to 
    # use a non-order specific parser
    for line in header_lines:
        if ":" not in line:
            continue 
        key, value = clean_and_extract(line)

        if key == "version":
            try:
                header.version = int(value)
                if header.version > MAX_SUPPORTED_VERSION:
                    header.original_header = "\n".join(header_lines)
            except Exception:
                pass

        elif key == "block_scale":
            try:
                header.block_scale = float(value)
            except Exception:
                pass

        elif key == "texture_type":
            try:
                header.texture_type = CommonMCOBJTextureType[value]
            except Exception:
                pass

        # All of these are parsed the same, with 
        # no parsing need to value
        #
        # No keys here will be classed as failed
        elif key in NO_VALUE_PARSE:
            setattr(header, key, value)

        # All of these are parsed the same, with 
        # parsing the value to a tuple
        elif key in TUPLE_PARSE_INT:
            try:
                setattr(header, key, tuple(map(int, value[1:-1].split(', '))))
            except Exception:
                pass

        elif key in TUPLE_PARSE_FLOAT:
            try:
                setattr(header, key, tuple(map(float, value[1:-1].split(', '))))
            except Exception:
                pass

        elif key in BOOLEAN_PARSE:
            try:
                setattr(header, key, value == "true")
            except Exception:
                pass

    return header

def parse_header(f: TextIO) -> Optional[CommonMCOBJ]:
    """
    Parses a file and returns a CommonMCOBJ object if 
    the header exists.
    
    f: TextIO
        File object
    
    Returns:
        - CommonMCOBJ object if header exists
        - None otherwise
    """

    header: List[str] = []
    found_header = False
    
    # Read in the header
    for l in f:
        tl = " ".join(l.rstrip().split())
        if tl == "# COMMON_MC_OBJ_START":
            header.append(tl)
            found_header = True 
            continue
        elif tl == "# COMMON_MC_OBJ_END":
            header.append(tl)
            break
        if not found_header or tl == "#":
            continue 
        header.append(tl)
    if not len(header):
        return None
    return parse_common_header(header)
