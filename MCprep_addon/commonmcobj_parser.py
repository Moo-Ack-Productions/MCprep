from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, TextIO

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
        exported_bounds_min=(0, 0, 0),
        exported_bounds_max=(0, 0, 0),
        export_offset=(0, 0, 0),
        block_scale=0,
        block_origin_offset=(0, 0, 0),
        z_up=False,
        texture_type=CommonMCOBJTextureType.ATLAS,
        has_split_blocks=False
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
            header.version = int(value)

        elif key == "block_scale":
            header.block_scale = float(value)

        elif key == "texture_type":
            header.texture_type = CommonMCOBJTextureType[value]

        # All of these are parsed the same, with 
        # no parsing need to value
        elif key in NO_VALUE_PARSE:
            setattr(header, key, value)

        # All of these are parsed the same, with 
        # parsing the value to a tuple
        elif key in TUPLE_PARSE_INT:
            setattr(header, key, tuple(map(int, value[1:-1].split(', '))))

        elif key in TUPLE_PARSE_FLOAT:
            setattr(header, key, tuple(map(float, value[1:-1].split(', '))))

        elif key in BOOLEAN_PARSE:
            setattr(header, key, value == "true")

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
    lines = f.readlines()

    header: List[str] = []
    found_header = False
    
    # Read in the header
    for l in lines:
        tl = " ".join(l.split())
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
