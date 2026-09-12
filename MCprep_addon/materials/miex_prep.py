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
from .. import world_tools
from ..conf import MCPREP_RESOURCES, MCprepError, env
from . import generate
from . import uv_tools
from .generate import checklist, get_mc_canonical_name
from .prep import McprepMaterialProps, draw_mats_common
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


def find_texture_in_pack(
    pack_dir: Path,
    canon_name: str,
    orig_path: str = "",
) -> Path | None:
    """Finds texture in pack directory matching canonical name or original texture path."""
    if not pack_dir.is_dir():
        return None

    names_to_check: list[str] = []

    clean_canon = canon_name.split(":")[-1].split("/")[-1]
    if clean_canon:
        names_to_check.append(clean_canon)
        if "-" in clean_canon:
            names_to_check.append(clean_canon.split("-")[-1])

    if orig_path:
        orig_p = Path(orig_path)
        if orig_p.stem and orig_p.stem not in names_to_check:
            names_to_check.append(orig_p.stem)

    # Check relative subpaths if orig_path contained 'tex/' (e.g. "tex/minecraft/block/stone.png")
    if orig_path:
        norm_orig = orig_path.replace("\\", "/")
        if "tex/" in norm_orig:
            sub = norm_orig.split("tex/", 1)[1]
            sub_p = Path(sub)
            parts = sub_p.parts
            if len(parts) >= 2:
                namespace = parts[0]
                rest = Path(*parts[1:])
                candidates = [
                    pack_dir / "assets" / namespace / "textures" / rest,
                    pack_dir / namespace / "textures" / rest,
                    pack_dir / "assets" / namespace / rest,
                    pack_dir / "textures" / rest,
                    pack_dir / rest,
                    pack_dir / sub_p,
                ]
                for cand in candidates:
                    if cand.is_file():
                        return cand

    # Check preferred pack paths first
    for c_name in names_to_check:
        fn = f"{c_name}.png"
        preferred_paths = [
            pack_dir / "assets" / "minecraft" / "textures" / "block" / fn,
            pack_dir / "assets" / "minecraft" / "textures" / "item" / fn,
            pack_dir / "assets" / "minecraft" / "textures" / "entity" / fn,
            pack_dir / "assets" / "minecraft" / "textures" / "painting" / fn,
            pack_dir / "assets" / "minecraft" / "textures" / fn,
            pack_dir / "minecraft" / "textures" / "block" / fn,
            pack_dir / "minecraft" / "textures" / "item" / fn,
            pack_dir / "minecraft" / "textures" / "entity" / fn,
            pack_dir / "textures" / "block" / fn,
            pack_dir / "textures" / "item" / fn,
            pack_dir / "textures" / "entity" / fn,
            pack_dir / "textures" / fn,
            pack_dir / fn,
        ]
        for p in preferred_paths:
            if p.is_file():
                return p

    # Fall back to recursive search for candidate filenames
    for c_name in names_to_check:
        fn = f"{c_name}.png"
        for p in pack_dir.rglob(fn):
            if p.is_file():
                return p

    return None


def apply_miex_material(
    material: Material,
    miex_mat: MiExMaterial,
    base_dir: Path | None = None,
    original_passes: dict | None = None,
    use_emission: bool = True,
    use_reflections: bool = True,
    only_solid: bool = False,
    use_extra_maps: bool = True,
    normal_intensity: float = 1.0,
) -> None:
    """Configures a Blender Material node tree according to a MiExMaterial specification."""
    material.use_nodes = True
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    anim_data = generate.copy_texture_animation_pass_settings(material)
    nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.name = "Material Output"
    output_node.label = "Material Output"
    output_node.location = (400.0, 0.0)

    created_nodes: dict[str, bpy.types.Node] = {}
    tex_y = 0.0
    shader_y = 0.0

    tag_map = {
        "FILE": "MCPREP_diffuse",
        "TEX_NORM": "MCPREP_normal",
        "NORM_MAP": "MCPREP_normal",
        "TEX_SPEC": "MCPREP_specular",
    }

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

        prop_name = tag_map.get(node_name)
        if not prop_name and "TexImage" in bl_type:
            img_val = ""
            if "image" in miex_node.attributes:
                raw_img = miex_node.attributes["image"].value
                img_val = str(raw_img).lower() if raw_img else ""
            lower_name = node_name.lower()
            if "diffuse" in lower_name or "@texture@" in img_val or "diffuse" in img_val:
                prop_name = "MCPREP_diffuse"
            elif "normal" in lower_name or "norm" in lower_name or "normal" in img_val:
                prop_name = "MCPREP_normal"
            elif "specular" in lower_name or "spec" in lower_name or "specular" in img_val:
                prop_name = "MCPREP_specular"

        if prop_name:
            if hasattr(bl_node, "mnp") and bl_node.mnp is not None:
                try:
                    setattr(bl_node.mnp, prop_name, True)
                except Exception:
                    pass
            try:
                bl_node[prop_name] = True
            except Exception:
                pass

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

    has_diffuse_tag = any(
        util.np_is_mcprep_node_prop(n, "MCPREP_diffuse") for n in created_nodes.values()
    )
    if not has_diffuse_tag:
        for bl_node in created_nodes.values():
            if bl_node.type == "TEX_IMAGE":
                if hasattr(bl_node, "mnp") and bl_node.mnp is not None:
                    try:
                        bl_node.mnp.MCPREP_diffuse = True
                    except Exception:
                        pass
                try:
                    bl_node["MCPREP_diffuse"] = True
                except Exception:
                    pass
                break

    for node_name, miex_node in miex_mat.network.items():
        bl_node = created_nodes.get(node_name)
        if not bl_node:
            continue

        for attr_name, attr in miex_node.attributes.items():
            val = attr.value

            if attr_name == "image":
                if not hasattr(bl_node, "image") or not val or not isinstance(val, (str, Path)):
                    continue
                img_path = Path(val)
                if not img_path.is_absolute():
                    if base_dir and (base_dir / img_path).is_file():
                        img_path = base_dir / img_path
                    elif bpy.data.filepath and (Path(bpy.data.filepath).parent / img_path).is_file():
                        img_path = Path(bpy.data.filepath).parent / img_path

                if img_path.is_file():
                    bl_node.image = bpy.data.images.load(str(img_path), check_existing=True)
                else:
                    for cand in (img_path.name, f"{img_path.name}.png", f"{img_path.stem}.png"):
                        if cand in bpy.data.images:
                            bl_node.image = bpy.data.images[cand]
                            break
                continue

            if attr_name == "interpolation":
                if hasattr(bl_node, "interpolation") and isinstance(val, str) and val in ("Closest", "Linear", "Cubic", "Smart"):
                    bl_node.interpolation = val
                continue

            if attr_name in ("colorspace_settings", "colorspace"):
                if not hasattr(bl_node, "image") or not bl_node.image:
                    continue
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

            if attr_name == "curves":
                if not hasattr(bl_node, "mapping") or not hasattr(bl_node.mapping, "curves") or not isinstance(val, dict):
                    continue
                curves = bl_node.mapping.curves
                for curve_idx_str, points in val.items():
                    if not curve_idx_str.isdigit():
                        continue
                    idx = int(curve_idx_str)
                    if idx >= len(curves):
                        continue
                    curve = curves[idx]
                    for pt_idx, pt in enumerate(points):
                        if pt_idx < len(curve.points):
                            curve.points[pt_idx].location = (float(pt[0]), float(pt[1]))
                        else:
                            curve.points.new(float(pt[0]), float(pt[1]))
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

            if val is None or sock is None:
                continue

            try:
                if sock.type == "RGBA":
                    if isinstance(val, (list, tuple)):
                        alpha = float(val[3]) if len(val) >= 4 else 1.0
                        sock.default_value = (float(val[0]), float(val[1]), float(val[2]), alpha)
                    elif isinstance(val, (int, float)):
                        fv = float(val)
                        sock.default_value = (fv, fv, fv, 1.0)
                elif sock.type == "VALUE" and isinstance(val, (int, float, bool)):
                    sock.default_value = float(val)
                elif sock.type == "VECTOR" and isinstance(val, (list, tuple)) and len(val) >= 3:
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
    if original_passes:
        for pass_key, pass_node_name in (("diffuse", "FILE"), ("normal", "TEX_NORM"), ("specular", "TEX_SPEC")):
            pass_node = created_nodes.get(pass_node_name)
            if pass_node and hasattr(pass_node, "image") and pass_node.image is None:
                orig_val = original_passes.get(pass_key)
                if isinstance(orig_val, bpy.types.Image):
                    pass_node.image = orig_val
                elif isinstance(orig_val, (str, Path)):
                    p_val = Path(orig_val)
                    if p_val.is_file():
                        pass_node.image = bpy.data.images.load(str(p_val), check_existing=True)
                    else:
                        for cand in (p_val.name, f"{p_val.name}.png", f"{p_val.stem}.png"):
                            if cand in bpy.data.images:
                                pass_node.image = bpy.data.images[cand]
                                break

    if anim_data:
        try:
            generate.apply_texture_animation_pass_settings(material, anim_data)
        except Exception as ex:
            env.log(f"Failed restoring animation pass settings on {material.name}: {ex}")


def prep_single_material(
    material: Material,
    templates: list[MiExTemplate],
    materials_cache: dict[Path, dict[str, MiExMaterial]] | None = None,
    pack_format: str = "simple",
    use_extra_maps: bool = True,
    use_reflections: bool = True,
    use_emission: bool = True,
    only_solid: bool = False,
    auto_find_missing: bool = False,
    texturepack_path: Path | None = None,
    normal_intensity: float = 1.0,
    explicit_diffuse_path: Path | None = None,
    animate_textures: bool = False,
) -> bool:
    """Preps a single Blender Material using the MiEx pipeline."""
    if not material or material.library or material.get("MCPREP_NO_PREP", False):
        return False

    passes = generate.get_textures(material)
    if auto_find_missing:
        for pass_name in list(passes.keys()):
            if passes.get(pass_name):
                res = generate.replace_missing_texture(passes[pass_name])
                if res > 0:
                    material["texture_swapped"] = True

    mat_gen = util.nameGeneralize(material.name)
    canon_name, _ = get_mc_canonical_name(mat_gen)

    diffuse_img = passes.get("diffuse")
    diff_path: Path | None = None
    if explicit_diffuse_path and explicit_diffuse_path.is_file():
        diff_path = explicit_diffuse_path
        diffuse_img = bpy.data.images.load(str(diff_path), check_existing=True)
        passes["diffuse"] = diffuse_img
    elif diffuse_img and diffuse_img.filepath:
        raw_path = Path(bpy.path.abspath(diffuse_img.filepath))
        if raw_path.is_file():
            diff_path = raw_path

    # If diffuse texture not found on disk, attempt lookup in active texture pack
    active_pack = texturepack_path
    if not active_pack and hasattr(bpy.context.scene, "mcprep_texturepack_path") and bpy.context.scene.mcprep_texturepack_path:
        p = Path(bpy.path.abspath(bpy.context.scene.mcprep_texturepack_path))
        if p.is_dir():
            active_pack = p

    orig_fp = diffuse_img.filepath if (diffuse_img and diffuse_img.filepath) else (diffuse_img.name if diffuse_img else "")

    if not diff_path and active_pack:
        tex_res = find_texture_in_pack(active_pack, canon_name, orig_path=orig_fp)
        if not tex_res:
            tex_res = generate.find_from_texturepack(canon_name, active_pack)
            if isinstance(tex_res, MCprepError) or not tex_res or not tex_res.is_file():
                tex_res = None
        if tex_res and tex_res.is_file():
            diff_path = tex_res
            if not diffuse_img:
                diffuse_img = bpy.data.images.load(str(diff_path), check_existing=True)
                passes["diffuse"] = diffuse_img

    # Check for exported _materials.json (MiEx export workflow)
    mat_json_file = None
    if diff_path:
        mat_json_file = find_materials_json(diff_path.parent)
    if not mat_json_file and active_pack:
        mat_json_file = find_materials_json(active_pack)

    if mat_json_file:
        if materials_cache is not None and mat_json_file in materials_cache:
            exported_mats = materials_cache[mat_json_file]
        else:
            exported_mats = load_materials_json(mat_json_file)
            if materials_cache is not None:
                materials_cache[mat_json_file] = exported_mats

        miex_mat = exported_mats.get(material.name) or exported_mats.get(canon_name)
        if miex_mat:
            apply_miex_material(material, miex_mat, base_dir=mat_json_file.parent, original_passes=passes)
            material["MCPREP_MIEX_PREPPED"] = True
            if explicit_diffuse_path:
                material["texture_swapped"] = True
            if animate_textures:
                try:
                    from . import sequences

                    engine = bpy.context.scene.render.engine if bpy.context and bpy.context.scene else 'CYCLES'
                    sequences.animate_single_material(
                        material,
                        engine,
                        export_location=sequences.ExportLocation.ORIGINAL,
                    )
                except Exception as ex:
                    env.log(f"Failed to animate texture on {material.name}: {ex}")
            return True

    # Discover texture passes
    texture_paths: dict[str, Path] = {}
    if diff_path:
        # Load additional passes from disk (like normal and spec maps)
        if use_extra_maps and pack_format != "simple":
            texture_paths = collect_texture_passes(diff_path)
        else:
            texture_paths = {"diffuse": diff_path}
    elif diffuse_img:
        texture_paths = {"diffuse": Path(diffuse_img.name)}
    else:
        texture_paths = {"diffuse": Path(canon_name)}

    # Also pick up normal/specular images already attached to material
    if use_extra_maps and pack_format != "simple":
        if passes.get("normal") and passes["normal"].filepath:
            np = Path(bpy.path.abspath(passes["normal"].filepath))
            if np.is_file():
                texture_paths["normal"] = np
        if passes.get("specular") and passes["specular"].filepath:
            sp = Path(bpy.path.abspath(passes["specular"].filepath))
            if sp.is_file():
                texture_paths["specular"] = sp

    if not use_emission:
        texture_paths.pop("emission", None)

    is_solid = only_solid or checklist(canon_name, "solid")
    extra_flags = {
        "use_emission": use_emission,
        "use_reflections": use_reflections,
        "use_extra_maps": use_extra_maps,
        "only_solid": only_solid,
        "normal_intensity": normal_intensity,
        "reflective": checklist(canon_name, "reflective") if use_reflections else False,
        "metallic": checklist(canon_name, "metallic") if use_reflections else False,
        "emit": (checklist(canon_name, "emit") or "emit" in material.name.lower()) if use_emission else False,
        "solid": is_solid,
        "backface_culling": checklist(canon_name, "backface_culling"),
        "pack_format": pack_format,
        "shading_mode": pack_format,
    }

    miex_mat = auto_generate_miex_material(
        material_name=material.name,
        texture_paths=texture_paths,
        templates=templates,
        extra_flags=extra_flags,
    )
    if not miex_mat:
        return False

    base_dir = diff_path.parent if diff_path else None
    apply_miex_material(material, miex_mat, base_dir=base_dir, original_passes=passes)

    if hasattr(material, "blend_method"):
        material.blend_method = 'OPAQUE' if is_solid else 'HASHED'
    if hasattr(material, "shadow_method"):
        material.shadow_method = 'OPAQUE' if is_solid else 'HASHED'

    material["MCPREP_MIEX_PREPPED"] = True
    if explicit_diffuse_path:
        material["texture_swapped"] = True

    if animate_textures:
        try:
            from . import sequences

            engine = bpy.context.scene.render.engine if bpy.context and bpy.context.scene else 'CYCLES'
            sequences.animate_single_material(
                material,
                engine,
                export_location=sequences.ExportLocation.ORIGINAL,
            )
        except Exception as ex:
            env.log(f"Failed to animate texture on {material.name}: {ex}")

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


class MCPREP_OT_miex_prep_materials(bpy.types.Operator, McprepMaterialProps):
    """Preps materials on selected objects using MiEx material templates or exported materials JSON"""
    bl_idname = "mcprep.miex_prep_materials"
    bl_label = "Prep Materials"
    bl_description = "Convert materials on selected objects using MiEx templates or exported _materials.json"
    bl_options = {'REGISTER', 'UNDO'}

    pack_format: bpy.props.StringProperty(
        name="Pack Format Alias",
        description="Alias for packFormat",
        default="",
        options={'HIDDEN'},
    )
    templates_dir: bpy.props.StringProperty(
        name="Templates Directory",
        description="Optional directory containing custom MiEx template JSON files",
        subtype="DIR_PATH",
        default="",
        options={'HIDDEN'},
    )

    track_function = "miex_prep_materials"
    track_param = None
    track_exporter = None

    def invoke(self, context: Context, event: bpy.types.Event):
        if hasattr(context.scene, "mcprep_miex_pack_format"):
            self.packFormat = context.scene.mcprep_miex_pack_format
        if hasattr(context.scene, "mcprep_miex_templates_path") and context.scene.mcprep_miex_templates_path:
            self.templates_dir = context.scene.mcprep_miex_templates_path
        return context.window_manager.invoke_props_dialog(
            self, width=300 * util.ui_scale()
        )

    def draw(self, context: Context):
        draw_mats_common(self, context)

    @tracking.report_error
    def execute(self, context: Context):
        active_pack = self.pack_format if self.pack_format else self.packFormat
        if hasattr(context.scene, "mcprep_miex_pack_format"):
            context.scene.mcprep_miex_pack_format = active_pack

        obj_list = context.selected_objects
        if not obj_list:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}

        mat_list = util.materialsFromObj(obj_list)
        if not mat_list:
            self.report({'ERROR'}, "No materials found on selected objects")
            return {'CANCELLED'}

        templates = get_default_templates(active_pack)
        custom_dir_str = self.templates_dir or getattr(context.scene, "mcprep_miex_templates_path", "")
        if custom_dir_str:
            custom_dir = Path(bpy.path.abspath(custom_dir_str))
            if custom_dir.is_dir():
                custom_templates = load_templates_from_dir(custom_dir)
                if custom_templates:
                    templates = custom_templates + templates

        materials_cache: dict[Path, dict[str, MiExMaterial]] = {}
        prepped_count = 0

        texpack_path = None
        if hasattr(context.scene, "mcprep_texturepack_path") and context.scene.mcprep_texturepack_path:
            p = Path(bpy.path.abspath(context.scene.mcprep_texturepack_path))
            if p.is_dir():
                texpack_path = p

        for mat in mat_list:
            prepped = prep_single_material(
                mat,
                templates=templates,
                materials_cache=materials_cache,
                pack_format=active_pack,
                use_extra_maps=self.useExtraMaps,
                use_reflections=self.useReflections,
                use_emission=self.useEmission,
                only_solid=self.makeSolid,
                auto_find_missing=self.autoFindMissingTextures,
                texturepack_path=texpack_path,
                normal_intensity=self.normalIntensity,
                animate_textures=self.animateTextures,
            )
            if prepped:
                prepped_count += 1
                if mat.node_tree:
                    arrange_material_nodes(mat.node_tree)
            elif self.animateTextures:
                try:
                    from . import sequences
                    sequences.animate_single_material(
                        mat,
                        context.scene.render.engine,
                        export_location=sequences.ExportLocation.ORIGINAL,
                    )
                except Exception as ex:
                    env.log(f"Failed to animate texture on {mat.name}: {ex}")

        # Sync materials
        if self.syncMaterials and hasattr(bpy.ops.mcprep, "sync_materials"):
            try:
                bpy.ops.mcprep.sync_materials(
                    selected=True, link=False, replace_materials=False, skipUsage=True
                )
            except Exception as ex:
                env.log(f"Failed to sync materials: {ex}")

        # Combine materials
        if self.combineMaterials and hasattr(bpy.ops.mcprep, "combine_materials"):
            try:
                bpy.ops.mcprep.combine_materials(selection_only=True, skipUsage=True)
            except Exception as ex:
                env.log(f"Failed to combine materials: {ex}")

        # Improve UI
        if self.improveUiSettings and hasattr(bpy.ops.mcprep, "improve_ui"):
            try:
                bpy.ops.mcprep.improve_ui()
            except Exception as err:
                env.log(f"Failed to improve UI: {err}")

        self.report({'INFO'}, f"Prepped {prepped_count} material(s) with MiEx pipeline")
        return {'FINISHED'}


class MCPREP_OT_miex_swap_texture_pack(
    bpy.types.Operator, ImportHelper, McprepMaterialProps
):
    """Swap current textures for that of a texture pack folder using MiEx templates"""
    bl_idname = "mcprep.miex_swap_texture_pack"
    bl_label = "Swap Texture Pack (MiEx)"
    bl_description = "Change the texture pack for materials on selected objects and rebuild via MiEx"
    bl_options = {'REGISTER', 'UNDO'}

    pack_format: bpy.props.StringProperty(
        name="Pack Format Alias",
        description="Alias for packFormat",
        default="",
        options={"HIDDEN"},
    )

    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN"},
    )
    use_filter_folder = True
    fileselectparams = "use_filter_blender"
    filepath: bpy.props.StringProperty(subtype="DIR_PATH")
    folder: bpy.props.StringProperty(subtype="DIR_PATH")
    texturepack_path: bpy.props.StringProperty(subtype="DIR_PATH")
    filter_image: bpy.props.BoolProperty(
        default=True,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    filter_folder: bpy.props.BoolProperty(
        default=True,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    prepMaterials: bpy.props.BoolProperty(
        name="Prep materials",
        description="Runs prep materials after texture swap to regenerate materials",
        default=True,
    )
    prep_materials: bpy.props.BoolProperty(
        name="Prep materials alias",
        description="Alias for prepMaterials",
        default=True,
        options={"HIDDEN"},
    )

    track_function = "miex_swap_texture_pack"
    track_param = None
    track_exporter = None

    def draw(self, context: Context):
        layout = self.layout
        col = layout.column()
        subcol = col.column()
        subcol.scale_y = 0.7
        subcol.label(text="Select any subfolder of an")
        subcol.label(text="unzipped texture pack, then")
        subcol.label(text="press 'Swap Texture Pack'")
        subcol.label(text="after confirming these")
        subcol.label(text="settings below:")
        col.prop(self, "useExtraMaps")
        col.prop(self, "animateTextures")
        col.prop(self, "prepMaterials")
        if self.prepMaterials:
            col.prop(self, "packFormat")
            col.prop(self, "useReflections")
            col.prop(self, "makeSolid")
            col.prop(self, "autoFindMissingTextures")
            col.prop(self, "syncMaterials")
            col.prop(self, "improveUiSettings")
            col.prop(self, "combineMaterials")
            col.prop(self, "useEmission")

    @tracking.report_error
    def execute(self, context: Context):
        active_pack = self.pack_format if self.pack_format else self.packFormat
        if hasattr(context.scene, "mcprep_miex_pack_format"):
            context.scene.mcprep_miex_pack_format = active_pack
        raw_path = self.filepath or self.folder or self.texturepack_path
        if not raw_path and hasattr(context.scene, "mcprep_texturepack_path"):
            raw_path = context.scene.mcprep_texturepack_path
        if not raw_path:
            self.report({'ERROR'}, "No folder selected")
            return {'CANCELLED'}

        pack_dir = Path(bpy.path.abspath(raw_path))
        if pack_dir.is_file():
            pack_dir = pack_dir.parent
        if not pack_dir.is_dir():
            self.report({'ERROR'}, "Selected folder does not exist")
            return {'CANCELLED'}

        context.scene.mcprep_texturepack_path = str(pack_dir)

        obj_list = context.selected_objects
        if not obj_list:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}

        mat_list = util.materialsFromObj(obj_list)
        if not mat_list:
            self.report({'ERROR'}, "No materials found on selected objects")
            return {'CANCELLED'}

        invalid_uv = False
        if not world_tools.is_commonmc_obj(context):
            invalid_uv, _ = uv_tools.detect_invalid_uvs_from_objs(obj_list)

        templates = get_default_templates(active_pack)
        custom_dir_str = getattr(context.scene, "mcprep_miex_templates_path", "")
        if custom_dir_str:
            custom_dir = Path(bpy.path.abspath(custom_dir_str))
            if custom_dir.is_dir():
                custom_templates = load_templates_from_dir(custom_dir)
                if custom_templates:
                    templates = custom_templates + templates

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

        do_prep = self.prepMaterials and self.prep_materials
        materials_cache: dict[Path, dict[str, MiExMaterial]] = {}
        swapped_count = 0

        for mat in mat_list:
            if not mat or mat.library or mat.get("MCPREP_NO_PREP", False):
                continue

            passes = generate.get_textures(mat)
            diff_img = passes.get("diffuse")
            stem = (
                Path(diff_img.filepath).stem
                if diff_img and diff_img.filepath
                else (Path(diff_img.name).stem if diff_img else mat.name)
            )
            clean_stem = stem.split(":")[-1].split("/")[-1]
            canon_name, _ = get_mc_canonical_name(clean_stem)
            orig_fp = diff_img.filepath if (diff_img and diff_img.filepath) else (diff_img.name if diff_img else "")

            new_tex_path = find_texture_in_pack(pack_dir, canon_name, orig_path=orig_fp)
            if not new_tex_path:
                tex_res = generate.find_from_texturepack(canon_name, pack_dir)
                if tex_res and not isinstance(tex_res, MCprepError) and tex_res.is_file():
                    new_tex_path = tex_res

            if not new_tex_path:
                continue

            if do_prep:
                if prep_single_material(
                    mat,
                    templates=templates,
                    materials_cache=materials_cache,
                    pack_format=active_pack,
                    use_extra_maps=self.useExtraMaps,
                    use_reflections=self.useReflections,
                    use_emission=self.useEmission,
                    only_solid=self.makeSolid,
                    auto_find_missing=self.autoFindMissingTextures,
                    texturepack_path=pack_dir,
                    normal_intensity=self.normalIntensity,
                    explicit_diffuse_path=new_tex_path,
                    animate_textures=self.animateTextures,
                ):
                    if mat.node_tree:
                        arrange_material_nodes(mat.node_tree)
                    swapped_count += 1
                elif self.animateTextures:
                    try:
                        from . import sequences

                        sequences.animate_single_material(
                            mat,
                            context.scene.render.engine,
                            export_location=sequences.ExportLocation.ORIGINAL,
                        )
                    except Exception as ex:
                        env.log(f"Failed to animate texture on {mat.name}: {ex}")
            else:
                new_img = util.loadTexture(str(new_tex_path))
                if generate.set_cycles_texture(new_img, mat, extra_passes=self.useExtraMaps):
                    mat["texture_swapped"] = True
                    swapped_count += 1

                if self.animateTextures:
                    try:
                        from . import sequences

                        sequences.animate_single_material(
                            mat,
                            context.scene.render.engine,
                            export_location=sequences.ExportLocation.ORIGINAL,
                        )
                    except Exception as ex:
                        env.log(f"Failed to animate texture on {mat.name}: {ex}")

        # Post-prep operations
        if do_prep:
            if self.syncMaterials and hasattr(bpy.ops.mcprep, "sync_materials"):
                try:
                    bpy.ops.mcprep.sync_materials(
                        selected=True, link=False, replace_materials=False, skipUsage=True
                    )
                except Exception as ex:
                    env.log(f"Failed to sync materials: {ex}")

            if self.combineMaterials and hasattr(bpy.ops.mcprep, "combine_materials"):
                try:
                    bpy.ops.mcprep.combine_materials(selection_only=True, skipUsage=True)
                except Exception as ex:
                    env.log(f"Failed to combine materials: {ex}")

            if self.improveUiSettings and hasattr(bpy.ops.mcprep, "improve_ui"):
                try:
                    bpy.ops.mcprep.improve_ui()
                except Exception as err:
                    env.log(f"Failed to improve UI: {err}")

        if invalid_uv:
            self.report({'WARNING'}, "Detected scaled UVs, incompatible with swap textures")

        self.report({'INFO'}, f"Swapped textures on {swapped_count} material(s) via MiEx")
        return {'FINISHED'}


class MCPREP_OT_miex_reset_templates_path(bpy.types.Operator):
    """Resets the custom MiEx templates path"""
    bl_idname = "mcprep.miex_reset_templates_path"
    bl_label = "Reset MiEx Templates Path"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context):
        if hasattr(context.scene, "mcprep_miex_templates_path"):
            context.scene.mcprep_miex_templates_path = ""
        return {'FINISHED'}


class MCPREP_OT_miex_open_templates_folder(bpy.types.Operator):
    """Opens the active MiEx template folder in file manager"""
    bl_idname = "mcprep.miex_open_templates_folder"
    bl_label = "Open Template Folder"
    bl_options = {'REGISTER'}

    def execute(self, context: Context):
        if hasattr(context.scene, "mcprep_miex_templates_path") and context.scene.mcprep_miex_templates_path:
            custom_path = Path(bpy.path.abspath(context.scene.mcprep_miex_templates_path))
            if custom_path.is_dir():
                util.open_folder_crossplatform(str(custom_path))
                return {'FINISHED'}
        pack_format = getattr(context.scene, "mcprep_miex_pack_format", "simple")
        target_dir = MIEX_TEMPLATES_DIR / pack_format
        if not target_dir.is_dir():
            target_dir = MIEX_TEMPLATES_DIR / "simple"
        if target_dir.is_dir():
            util.open_folder_crossplatform(str(target_dir))
        return {'FINISHED'}


classes = (
    MCPREP_OT_miex_prep_materials,
    MCPREP_OT_miex_swap_texture_pack,
    MCPREP_OT_miex_reset_templates_path,
    MCPREP_OT_miex_open_templates_folder,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
