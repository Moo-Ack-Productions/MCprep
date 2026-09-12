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

"""
Unified material preparation and texture swapping for MCprep using MiEx.

Bridges upstream MiEx material templates and exported _materials.json with
Blender material shader node trees. Supports OBJ imports and MiEx exports.
"""

from pathlib import Path

import bpy
from bpy.types import Context, Material
from bpy_extras.io_utils import ImportHelper

from .. import tracking
from .. import util
from ..conf import MCPREP_RESOURCES, env
from . import generate
from .generate import get_mc_canonical_name
from .miex_generator import (
    auto_generate_miex_material,
    collect_texture_passes,
)
from .miex_parser import (
    MiExMaterial,
    MiExTemplate,
    TemplateJSON,
    load_materials_json,
    parse_compact_node_type,
    parse_template,
    parse_template_file,
    resolve_includes,
)


SOCKET_NAME_MAP: dict[str, str] = {
    "diffuseColor": "Base Color",
    "baseColor": "Base Color",
    "base_color": "Base Color",
    "roughness": "Roughness",
    "metallic": "Metallic",
    "ior": "IOR",
    "opacity": "Alpha",
    "alpha": "Alpha",
    "normal": "Normal",
    "emissiveColor": "Emission Color",
    "emission_color": "Emission Color",
    "emissionStrength": "Emission Strength",
    "emission_strength": "Emission Strength",
    "transmission": "Transmission Weight",
    "transmissionWeight": "Transmission Weight",
    "transmission_weight": "Transmission Weight",
    "specular": "Specular IOR Level",
    "specular_ior_level": "Specular IOR Level",
    "Specular IOR Level": "Specular",
}

SRC_SOCKET_NAME_MAP: dict[str, str] = {
    "rgb": "Color",
    "color": "Color",
    "a": "Alpha",
    "alpha": "Alpha",
    "result": "Result",
    "out": "BSDF",
    "red": "Red",
    "green": "Green",
    "blue": "Blue",
    "r": "Red",
    "g": "Green",
    "b": "Blue",
}


def map_input_socket_name(name: str, node: bpy.types.Node) -> str:
    """Maps attribute or socket name to the matching node input socket."""
    if name in node.inputs:
        return name
    mapped = SOCKET_NAME_MAP.get(name)
    if mapped and mapped in node.inputs:
        return mapped
    mapped_cap = name.capitalize()
    if mapped_cap in node.inputs:
        return mapped_cap
    return name


def map_output_socket_name(name: str, node: bpy.types.Node) -> str:
    """Maps source output socket name to the matching node output socket."""
    if name in node.outputs:
        return name
    lower = name.lower()
    for out_name in node.outputs.keys():
        if out_name.lower() == lower:
            return out_name
    rgb_map = {
        "red": "R", "green": "G", "blue": "B",
        "r": "Red", "g": "Green", "b": "Blue",
    }
    if lower in rgb_map:
        target = rgb_map[lower]
        if target in node.outputs:
            return target
        for out_name in node.outputs.keys():
            if out_name.lower() == target.lower():
                return out_name
    mapped = SRC_SOCKET_NAME_MAP.get(name) or SRC_SOCKET_NAME_MAP.get(lower)
    if mapped and mapped in node.outputs:
        return mapped
    mapped_cap = name.capitalize()
    if mapped_cap in node.outputs:
        return mapped_cap
    return name


MIEX_TEMPLATES_DIR: Path = MCPREP_RESOURCES / "miex_templates"
TEMPLATES_DIR: Path = MIEX_TEMPLATES_DIR / "simple"


def get_default_templates(pack_name: str | generate.PackFormat = "simple") -> list[MiExTemplate]:
    """Returns built-in templates for MCprep loaded from disk."""
    if isinstance(pack_name, generate.PackFormat):
        pack_name = pack_name.name.lower()
    else:
        pack_name = str(pack_name).lower()

    pack_dir = MIEX_TEMPLATES_DIR / pack_name
    if pack_dir.is_dir():
        return load_templates_from_dir(pack_dir)
    if TEMPLATES_DIR.is_dir():
        return load_templates_from_dir(TEMPLATES_DIR)
    return []


def get_template_pack(pack_name: str | generate.PackFormat) -> list[MiExTemplate]:
    """Returns templates for the specified template pack."""
    return get_default_templates(pack_name)


def get_available_template_packs() -> list[str]:
    """Returns the names of available built-in MiEx template packs."""
    if not MIEX_TEMPLATES_DIR.is_dir():
        return ["simple"]
    packs = [p.name for p in MIEX_TEMPLATES_DIR.iterdir() if p.is_dir()]
    return sorted(packs) if packs else ["simple"]


def load_templates_from_dir(dir_path: Path) -> list[MiExTemplate]:
    """Loads and resolves all MiEx material template JSON files in a directory."""
    if not dir_path.is_dir():
        return []

    raw_templates: dict[str, MiExTemplate] = {}
    for json_file in dir_path.rglob("*.json"):
        try:
            tpl = parse_template_file(json_file)
            raw_templates[tpl.name] = tpl
        except Exception as ex:
            env.log(f"Failed parsing template {json_file}: {ex}")

    resolved: list[MiExTemplate] = []
    for tpl in raw_templates.values():
        resolved.append(resolve_includes(tpl, raw_templates))

    resolved.sort(key=lambda t: t.priority, reverse=True)
    return resolved


def find_materials_json(search_dir: Path) -> Path | None:
    """Finds _materials.json or materials.json in search_dir or its parent."""
    target_dir = search_dir if search_dir.is_dir() else search_dir.parent
    if not target_dir.is_dir():
        return None

    candidates = [
        target_dir / "_materials.json",
        target_dir / "materials.json",
        target_dir.parent / "_materials.json",
        target_dir.parent / "materials.json",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def find_texture_in_pack(pack_dir: Path, canon_name: str) -> Path | None:
    """Finds texture in pack directory matching the canonical name."""
    if not pack_dir.is_dir():
        return None

    clean_name = canon_name.split(":")[-1].split("/")[-1]
    filename = f"{clean_name}.png"
    preferred_paths = [
        pack_dir / "assets" / "minecraft" / "textures" / "block" / filename,
        pack_dir / "minecraft" / "textures" / "block" / filename,
        pack_dir / "textures" / "block" / filename,
        pack_dir / filename,
    ]
    for p in preferred_paths:
        if p.is_file():
            return p

    for p in pack_dir.rglob(filename):
        if p.is_file():
            return p
    return None


def apply_miex_material(
    material: Material,
    miex_mat: MiExMaterial,
    base_dir: Path | None = None,
) -> None:
    """Configures a Blender Material node tree according to a MiExMaterial specification."""
    material.use_nodes = True
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.name = "Material Output"
    output_node.label = "Material Output"
    output_node.location = (400.0, 0.0)

    created_nodes: dict[str, bpy.types.Node] = {}
    tex_y = 0.0
    shader_y = 0.0

    for node_name, miex_node in miex_mat.network.items():
        if not miex_node.node_type:
            continue
        try:
            node_info = parse_compact_node_type(miex_node.node_type)
            bl_type = node_info.node_name
        except ValueError:
            bl_type = miex_node.node_type

        if bl_type == "UsdPreviewSurface":
            bl_type = "ShaderNodeBsdfPrincipled"
        elif bl_type == "ShaderNodeSeparateColor" and not hasattr(bpy.types, "ShaderNodeSeparateColor"):
            bl_type = "ShaderNodeSeparateRGB"

        if not hasattr(bpy.types, bl_type):
            env.log(f"Unknown Blender node type: {bl_type}, skipping node {node_name}")
            continue

        bl_node = nodes.new(bl_type)
        bl_node.name = node_name
        bl_node.label = node_name

        if bl_type == "ShaderNodeRGBCurve" and node_name in ("NORM_CURVE", "Normal Inverse"):
            try:
                c1 = bl_node.mapping.curves[1]
                if c1.points[0].location[1] == 0.0 and c1.points[1].location[1] == 1.0:
                    c1.points[0].location = (0.0, 1.0)
                    c1.points[1].location = (1.0, 0.0)
                    bl_node.mapping.update()
            except Exception:
                pass

        if "TexImage" in bl_type:
            bl_node.location = (-400.0, tex_y)
            tex_y -= 280.0
            if hasattr(bl_node, "interpolation"):
                bl_node.interpolation = "Closest"
        elif "Bsdf" in bl_type:
            bl_node.location = (0.0, shader_y)
            shader_y -= 320.0
        else:
            bl_node.location = (-150.0, tex_y)
            tex_y -= 200.0

        created_nodes[node_name] = bl_node

    for node_name, miex_node in miex_mat.network.items():
        bl_node = created_nodes.get(node_name)
        if not bl_node:
            continue

        for attr_name, attr in miex_node.attributes.items():
            val = attr.value

            if attr_name == "image" and hasattr(bl_node, "image"):
                if isinstance(val, (str, Path)) and val:
                    img_path = Path(val)
                    if not img_path.is_absolute():
                        if base_dir and (base_dir / img_path).is_file():
                            img_path = base_dir / img_path
                        elif bpy.data.filepath:
                            blend_parent = Path(bpy.data.filepath).parent
                            if (blend_parent / img_path).is_file():
                                img_path = blend_parent / img_path

                    if img_path.is_file():
                        bl_node.image = bpy.data.images.load(str(img_path), check_existing=True)
                    elif img_path.name in bpy.data.images:
                        bl_node.image = bpy.data.images[img_path.name]
                continue

            if attr_name == "interpolation" and hasattr(bl_node, "interpolation"):
                if isinstance(val, str) and val in ("Closest", "Linear", "Cubic", "Smart"):
                    bl_node.interpolation = val
                continue

            if attr_name in ("colorspace_settings", "colorspace") and hasattr(bl_node, "image") and bl_node.image:
                if str(val).lower() in ("non-color", "non_color", "non-color data"):
                    util.apply_noncolor_data(bl_node)
                elif isinstance(val, list):
                    for cs in val:
                        try:
                            bl_node.image.colorspace_settings.name = str(cs)
                            break
                        except Exception:
                            pass
                elif isinstance(val, str):
                    try:
                        bl_node.image.colorspace_settings.name = val
                    except Exception:
                        pass
                continue

            if attr_name == "curves" and hasattr(bl_node, "mapping") and hasattr(bl_node.mapping, "curves"):
                if isinstance(val, dict):
                    for curve_idx_str, points in val.items():
                        try:
                            idx = int(curve_idx_str)
                            if idx < len(bl_node.mapping.curves):
                                curve = bl_node.mapping.curves[idx]
                                for pt_idx, pt in enumerate(points):
                                    if pt_idx < len(curve.points):
                                        curve.points[pt_idx].location = (float(pt[0]), float(pt[1]))
                                    else:
                                        curve.points.new(float(pt[0]), float(pt[1]))
                        except Exception as ex:
                            env.log(f"Failed setting curve {curve_idx_str}: {ex}")
                    try:
                        bl_node.mapping.update()
                    except Exception:
                        pass
                continue

            if hasattr(bl_node, attr_name) and not (hasattr(bl_node, "inputs") and attr_name in bl_node.inputs):
                try:
                    setattr(bl_node, attr_name, val)
                    continue
                except Exception:
                    pass

            target_sock_name = map_input_socket_name(attr_name, bl_node)
            sock = None
            if target_sock_name in bl_node.inputs:
                sock = bl_node.inputs[target_sock_name]
            elif attr_name.isdigit() and int(attr_name) < len(bl_node.inputs):
                sock = bl_node.inputs[int(attr_name)]

            if val is not None and sock is not None:
                try:
                    if sock.type == "RGBA":
                        if isinstance(val, (list, tuple)):
                            if len(val) == 3:
                                sock.default_value = (float(val[0]), float(val[1]), float(val[2]), 1.0)
                            elif len(val) >= 4:
                                sock.default_value = (float(val[0]), float(val[1]), float(val[2]), float(val[3]))
                        elif isinstance(val, (int, float)):
                            fv = float(val)
                            sock.default_value = (fv, fv, fv, 1.0)
                    elif sock.type == "VALUE":
                        if isinstance(val, (int, float, bool)):
                            sock.default_value = float(val)
                    elif sock.type == "VECTOR":
                        if isinstance(val, (list, tuple)) and len(val) >= 3:
                            sock.default_value = (float(val[0]), float(val[1]), float(val[2]))
                except Exception as ex:
                    env.log(f"Failed setting socket default {attr_name} on {node_name}: {ex}")

    # Connect internal links
    for node_name, miex_node in miex_mat.network.items():
        bl_node = created_nodes.get(node_name)
        if not bl_node:
            continue

        for attr_name, attr in miex_node.attributes.items():
            if not attr.connection:
                continue
            input_attr = attr.connection.split("/")[-1]
            if "." not in input_attr:
                continue
            src_node_name, raw_src_socket = input_attr.split(".", 1)
            src_node = created_nodes.get(src_node_name)
            if not src_node:
                continue

            src_socket_name = map_output_socket_name(raw_src_socket, src_node)
            target_socket_name = map_input_socket_name(attr_name, bl_node)

            src_sock = (
                src_node.outputs[int(src_socket_name)]
                if src_socket_name.isdigit() and int(src_socket_name) < len(src_node.outputs)
                else src_node.outputs.get(src_socket_name)
            )
            target_sock = (
                bl_node.inputs[int(target_socket_name)]
                if target_socket_name.isdigit() and int(target_socket_name) < len(bl_node.inputs)
                else bl_node.inputs.get(target_socket_name)
            )

            if src_sock and target_sock:
                links.new(src_sock, target_sock)

    # Connect terminals
    for term_name, conn in miex_mat.terminals.items():
        clean_term = term_name[5:] if term_name.startswith("json:") else term_name
        target_socket_name = clean_term.capitalize()

        if target_socket_name not in output_node.inputs:
            target_socket = output_node.inputs[0]
        else:
            target_socket = output_node.inputs[target_socket_name]

        input_attr = conn.split("/")[-1]
        if "." not in input_attr:
            continue

        src_node_name, raw_src_socket = input_attr.split(".", 1)
        src_node = created_nodes.get(src_node_name)
        if not src_node:
            continue

        src_socket_name = map_output_socket_name(raw_src_socket, src_node)
        if src_socket_name in src_node.outputs:
            links.new(src_node.outputs[src_socket_name], target_socket)

    use_backface_culling = True
    for miex_node in miex_mat.network.values():
        if "Backface Culling" in miex_node.attributes:
            val = miex_node.attributes["Backface Culling"].value
            use_backface_culling = bool(val)

    try:
        material.use_backface_culling = use_backface_culling
    except Exception:
        pass
    try:
        material.use_backface_culling_shadow = use_backface_culling
    except Exception:
        pass
    try:
        material.blend_method = "HASHED"
    except Exception:
        pass


def prep_single_material(
    material: Material,
    templates: list[MiExTemplate],
    materials_cache: dict[Path, dict[str, MiExMaterial]] | None = None,
) -> bool:
    """Preps a single Blender Material using the MiEx pipeline."""
    if not material or material.library or material.get("MCPREP_NO_PREP", False):
        return False

    passes = generate.get_textures(material)
    diffuse_img = passes.get("diffuse")
    diff_path: Path | None = None
    if diffuse_img and diffuse_img.filepath:
        raw_path = Path(bpy.path.abspath(diffuse_img.filepath))
        if raw_path.is_file():
            diff_path = raw_path

    if diff_path:
        mat_json_file = find_materials_json(diff_path.parent)
        if mat_json_file:
            if materials_cache is not None and mat_json_file in materials_cache:
                exported_mats = materials_cache[mat_json_file]
            else:
                exported_mats = load_materials_json(mat_json_file)
                if materials_cache is not None:
                    materials_cache[mat_json_file] = exported_mats

            canon_name, _ = get_mc_canonical_name(material.name)
            miex_mat = exported_mats.get(material.name) or exported_mats.get(canon_name)
            if miex_mat:
                apply_miex_material(material, miex_mat, base_dir=mat_json_file.parent)
                material["MCPREP_MIEX_PREPPED"] = True
                return True

    texture_paths: dict[str, Path] = {}
    if diff_path:
        texture_paths = collect_texture_passes(diff_path)
    else:
        canon_name, _ = get_mc_canonical_name(material.name)
        texture_paths = {"diffuse": Path(canon_name)}

    miex_mat = auto_generate_miex_material(
        material_name=material.name,
        texture_paths=texture_paths,
        templates=templates,
    )
    if not miex_mat:
        return False

    base_dir = diff_path.parent if diff_path else None
    apply_miex_material(material, miex_mat, base_dir=base_dir)
    material["MCPREP_MIEX_PREPPED"] = True
    return True


def arrange_material_nodes(node_tree: bpy.types.NodeTree) -> None:
    """Arranges node tree using the nodearrange library."""
    if not node_tree or not node_tree.nodes:
        return
    try:
        from ..lib.nodearrange import arrange_tree

        arrange_tree(node_tree)
    except Exception as ex:
        env.log(f"nodearrange layout error: {ex}")


class MCPREP_OT_miex_prep_materials(bpy.types.Operator):
    """Preps materials on selected objects using MiEx material templates or exported materials JSON"""
    bl_idname = "mcprep.miex_prep_materials"
    bl_label = "Prep MiEx Materials"
    bl_description = "Convert materials on selected objects using MiEx templates or exported _materials.json"
    bl_options = {'REGISTER', 'UNDO'}

    pack_format: bpy.props.EnumProperty(
        name="Pack Format",
        description="MiEx template pack format to use",
        items=[
            ("simple", "Simple (no PBR)", "Use simple shader setup with no PBR or emission falloff"),
            ("specular", "Specular", "Sets the pack format to Specular"),
            ("seus", "SEUS", "Sets the pack format to SEUS"),
        ],
        default="simple",
    )

    templates_dir: bpy.props.StringProperty(
        name="Templates Directory",
        description="Optional directory containing custom MiEx template JSON files",
        subtype="DIR_PATH",
        default="",
    )

    track_function = "miex_prep_materials"
    track_param = None
    track_exporter = None

    @tracking.report_error
    def execute(self, context: Context):
        obj_list = context.selected_objects
        if not obj_list:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}

        mat_list = util.materialsFromObj(obj_list)
        if not mat_list:
            self.report({'ERROR'}, "No materials found on selected objects")
            return {'CANCELLED'}

        templates = get_default_templates(self.pack_format)
        if self.templates_dir:
            custom_dir = Path(bpy.path.abspath(self.templates_dir))
            if custom_dir.is_dir():
                custom_templates = load_templates_from_dir(custom_dir)
                if custom_templates:
                    templates = custom_templates + templates

        materials_cache: dict[Path, dict[str, MiExMaterial]] = {}
        prepped_count = 0

        for mat in mat_list:
            if prep_single_material(mat, templates, materials_cache):
                prepped_count += 1
                if mat.node_tree:
                    arrange_material_nodes(mat.node_tree)

        self.report({'INFO'}, f"Prepped {prepped_count} material(s) with MiEx pipeline")
        return {'FINISHED'}


class MCPREP_OT_miex_swap_texture_pack(bpy.types.Operator, ImportHelper):
    """Swap current textures for that of a texture pack folder using MiEx templates"""
    bl_idname = "mcprep.miex_swap_texture_pack"
    bl_label = "Swap Texture Pack (MiEx)"
    bl_description = "Change the texture pack for materials on selected objects and rebuild via MiEx"
    bl_options = {'REGISTER', 'UNDO'}

    pack_format: bpy.props.EnumProperty(
        name="Pack Format",
        description="MiEx template pack format to use if pack does not include templates",
        items=[
            ("simple", "Simple (no PBR)", "Use simple shader setup with no PBR or emission falloff"),
            ("specular", "Specular", "Sets the pack format to Specular"),
            ("seus", "SEUS", "Sets the pack format to SEUS"),
        ],
        default="simple",
    )

    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN"},
    )
    use_filter_folder = True
    fileselectparams = "use_filter_blender"
    filepath: bpy.props.StringProperty(subtype="DIR_PATH")

    track_function = "miex_swap_texture_pack"
    track_param = None
    track_exporter = None

    @tracking.report_error
    def execute(self, context: Context):
        raw_path = self.filepath
        if not raw_path:
            self.report({'ERROR'}, "No folder selected")
            return {'CANCELLED'}

        pack_dir = Path(bpy.path.abspath(raw_path))
        if pack_dir.is_file():
            pack_dir = pack_dir.parent
        if not pack_dir.is_dir():
            self.report({'ERROR'}, "Selected folder does not exist")
            return {'CANCELLED'}

        obj_list = context.selected_objects
        if not obj_list:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}

        mat_list = util.materialsFromObj(obj_list)
        if not mat_list:
            self.report({'ERROR'}, "No materials found on selected objects")
            return {'CANCELLED'}

        templates = get_default_templates(self.pack_format)
        template_candidates = [
            pack_dir / "materials" / "minecraft" / "templates",
            pack_dir / "materials" / "templates",
            pack_dir / "templates",
            pack_dir / "materials",
            pack_dir,
        ]
        for cand in template_candidates:
            if cand.is_dir():
                pack_templates = load_templates_from_dir(cand)
                if pack_templates:
                    templates = pack_templates + templates
                    break

        swapped_count = 0
        for mat in mat_list:
            if not mat or mat.library or mat.get("MCPREP_NO_PREP", False):
                continue

            passes = generate.get_textures(mat)
            diff_img = passes.get("diffuse")
            stem = Path(diff_img.filepath).stem if diff_img and diff_img.filepath else mat.name
            clean_stem = stem.split(":")[-1].split("/")[-1]
            canon_name, _ = get_mc_canonical_name(clean_stem)

            new_tex_path = find_texture_in_pack(pack_dir, canon_name)
            if not new_tex_path:
                continue

            new_passes = collect_texture_passes(new_tex_path)
            miex_mat = auto_generate_miex_material(
                material_name=mat.name,
                texture_paths=new_passes,
                templates=templates,
            )
            if not miex_mat:
                continue

            apply_miex_material(mat, miex_mat, base_dir=new_tex_path.parent)
            if mat.node_tree:
                arrange_material_nodes(mat.node_tree)
            mat["MCPREP_MIEX_PREPPED"] = True
            mat["texture_swapped"] = True
            swapped_count += 1

        self.report({'INFO'}, f"Swapped textures on {swapped_count} material(s) via MiEx")
        return {'FINISHED'}


classes = (
    MCPREP_OT_miex_prep_materials,
    MCPREP_OT_miex_swap_texture_pack,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
