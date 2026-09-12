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

"""MiEx material auto-generator.

Reuses existing MCprep canonical name resolution, texture pass discovery,
and block checklists to auto-generate MiEx materials from texture paths.
"""

from dataclasses import dataclass, field
import fnmatch
from pathlib import Path

from .. import util
from ..conf import env
from .generate import checklist, find_additional_passes, get_mc_canonical_name
from .miex_parser import (
    AttributeValue,
    MiExAttribute,
    MiExMaterial,
    MiExNode,
    MiExTemplate,
)


def matches_selection(texture_id: str, pattern: str) -> bool:
    """Checks if a texture identifier matches a template's selection pattern.
    
    MiEx templates define a list of glob patterns in 'selection', such as:
    - '*' (matches any texture)
    - 'minecraft:block/amethyst*' (wildcard match for amethyst blocks)
    - 'minecraft:block/stone' (exact namespace match)
    
    For OBJ workflows where namespaces might be omitted (e.g. 'dirt' instead of
    'minecraft:block/dirt'), we match against both the full texture identifier
    and the stripped base name to ensure compatibility across export types.
    """
    if pattern == "*":
        return True
    if fnmatch.fnmatch(texture_id, pattern):
        return True

    # Fallback for OBJ exports without minecraft:block/ namespace prefix
    bare_name = texture_id.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    pattern_bare = pattern.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return fnmatch.fnmatch(bare_name, pattern_bare)


def find_matching_template(
    texture_id: str,
    templates: list[MiExTemplate],
) -> MiExTemplate | None:
    """Selects the highest-priority template matching the texture identifier."""
    matching: list[MiExTemplate] = []
    for template in templates:
        for pattern in template.selection:
            if matches_selection(texture_id, pattern):
                matching.append(template)
                break

    if not matching:
        return None

    matching.sort(key=lambda t: t.priority, reverse=True)
    return matching[0]


def collect_texture_passes(diffuse_path: Path) -> dict[str, Path]:
    """Uses MCprep's find_additional_passes to discover normal/specular/emission passes."""
    found_passes = find_additional_passes(diffuse_path)
    passes: dict[str, Path] = {}
    for pass_name, pass_file in found_passes.items():
        if pass_file:
            passes[pass_name] = Path(pass_file)

    # Always ensure diffuse is set
    passes["diffuse"] = diffuse_path

    # Check for emissive texture if not detected
    parent_dir = diffuse_path.parent
    stem = diffuse_path.stem
    for suffix in ("_e", "_emission", "_emit"):
        candidate = parent_dir / f"{stem}{suffix}{diffuse_path.suffix}"
        if candidate.is_file():
            passes["emission"] = candidate
            break

    return passes


def get_mcprep_biome_color(canon_name: str) -> list[float] | None:
    """Retrieves the RGBA color for a desaturated block from MCprep JSON."""
    if not env.json_data or "blocks" not in env.json_data:
        util.load_mcprep_json()
    if not env.json_data or "blocks" not in env.json_data:
        return None
    desat_map = env.json_data["blocks"].get("desaturated", {})
    clean = canon_name.split("/")[-1].split(":")[-1]
    col = desat_map.get(clean) or desat_map.get(canon_name)
    if col and len(col) >= 3:
        alpha = col[3] if len(col) > 3 else 1.0
        return [float(col[0]), float(col[1]), float(col[2]), float(alpha)]
    return None


def build_condition_flags(canon_name: str, texture_path: Path) -> dict[str, bool]:
    """Constructs condition flags reusing MCprep's checklist and block properties."""
    clean_canon = canon_name.split("/")[-1].split(":")[-1]
    flags: dict[str, bool] = {
        "emit": checklist(clean_canon, "emit"),
        "solid": checklist(clean_canon, "solid"),
        "reflective": checklist(clean_canon, "reflective"),
        "metallic": checklist(clean_canon, "metallic"),
        "glass": checklist(clean_canon, "glass"),
        "water": checklist(clean_canon, "water"),
        "backface_culling": checklist(clean_canon, "backface_culling"),
        "desaturated": checklist(clean_canon, "desaturated"),
        "biomeColor": False,
    }
    return flags


def evaluate_condition_token(
    token: str,
    texture_id: str,
    passes: dict[str, Path],
    flags: dict[str, bool],
) -> bool:
    """Evaluates a single condition token against passes and checklist flags."""
    token = token.strip()
    if not token:
        return True

    if token.startswith("!"):
        return not evaluate_condition_token(token[1:], texture_id, passes, flags)

    if token == "@texture@":
        return "diffuse" in passes

    if token == "@biomeColor@":
        return bool(flags.get("biomeColor", False))

    if token.startswith("@") and token.endswith("@"):
        flag_name = token[1:-1]
        return bool(flags.get(flag_name, False))

    if token.endswith(".cutout"):
        return flags.get("solid", False)
    if token.endswith(".a"):
        return not flags.get("solid", False)

    resolved_id = token.replace("@texture@", texture_id)
    if resolved_id.endswith("_emission") or resolved_id.endswith("_e"):
        return "emission" in passes or flags.get("emit", False)
    if resolved_id.endswith("_normal") or resolved_id.endswith("_n"):
        return "normal" in passes
    if resolved_id.endswith("_specular") or resolved_id.endswith("_s"):
        return "specular" in passes

    return resolved_id in passes


def evaluate_condition(
    condition: str,
    texture_id: str,
    passes: dict[str, Path],
    flags: dict[str, bool],
) -> bool:
    """Evaluates a compound condition string combining tokens with '&&'."""
    condition = condition.strip()
    if not condition:
        return True

    for token in condition.split("&&"):
        if not evaluate_condition_token(token, texture_id, passes, flags):
            return False
    return True


def resolve_attribute_value(
    value: AttributeValue | None,
    texture_id: str,
    diffuse_path: Path | None,
    passes: dict[str, Path] | None = None,
) -> AttributeValue | None:
    """Replaces @texture@ and related pass placeholders with texture paths."""
    if isinstance(value, str):
        if passes:
            if "emission" in passes and "@texture@_emission" in value:
                value = value.replace("@texture@_emission", str(passes["emission"]))
            if "emission" in passes and "@texture@_e" in value:
                value = value.replace("@texture@_e", str(passes["emission"]))
            if "normal" in passes and "@texture@_normal" in value:
                value = value.replace("@texture@_normal", str(passes["normal"]))
            if "normal" in passes and "@texture@_n" in value:
                value = value.replace("@texture@_n", str(passes["normal"]))
            if "specular" in passes and "@texture@_specular" in value:
                value = value.replace("@texture@_specular", str(passes["specular"]))
            if "specular" in passes and "@texture@_s" in value:
                value = value.replace("@texture@_s", str(passes["specular"]))
        replacement = str(diffuse_path) if diffuse_path is not None else texture_id
        return value.replace("@texture@", replacement)
    return value


def resolve_connection_reference(
    connection: str | None,
    resolved_nodes: dict[str, MiExNode],
) -> str | None:
    """Resolves dynamic ${node.attribute} connection references."""
    if not connection or not (connection.startswith("${") and connection.endswith("}")):
        return connection

    ref = connection[2:-1]
    ref_parts = ref.split(".", 1)
    if len(ref_parts) != 2:
        return connection

    ref_node_name, ref_attr_name = ref_parts
    ref_node = resolved_nodes.get(ref_node_name)
    if not ref_node:
        return connection

    ref_attr = ref_node.attributes.get(ref_attr_name)
    if not ref_attr or not ref_attr.connection:
        return connection

    return ref_attr.connection


def auto_generate_miex_material(
    material_name: str,
    texture_paths: dict[str, Path] | Path,
    templates: list[MiExTemplate],
    flags: dict[str, bool] | None = None,
    extra_flags: dict[str, bool] | None = None,
) -> MiExMaterial | None:
    """Auto-generates a unified MiEx material using declarative template conditionals and fill-ins."""
    if isinstance(texture_paths, Path):
        passes = collect_texture_passes(texture_paths)
    else:
        passes = dict(texture_paths)

    diffuse_path = passes.get("diffuse")

    # Strip namespace prefix before canonical name lookup
    mat_clean = material_name
    if mat_clean.startswith("minecraft:block/"):
        mat_clean = mat_clean[len("minecraft:block/"):]
    elif mat_clean.startswith("minecraft:"):
        mat_clean = mat_clean[len("minecraft:"):]

    # Determine canonical block name using MCprep's canonical name mapping
    generic_stems = {"terrain", "texture", "textures", "block", "blocks", "atlas", "diffuse", "image", "world"}
    mat_gen = util.nameGeneralize(mat_clean)
    canon_name, _ = get_mc_canonical_name(mat_gen)

    # Fallback: if material name was generic (e.g. "Material", "mat"), derive from diffuse image stem
    if canon_name.lower().startswith("material") or canon_name.lower().startswith("mat"):
        if diffuse_path and diffuse_path.stem.lower() not in generic_stems:
            diff_gen = util.nameGeneralize(diffuse_path.stem)
            tex_canon, _ = get_mc_canonical_name(diff_gen)
            if tex_canon and tex_canon.lower() not in generic_stems:
                canon_name = tex_canon

    clean_canon = canon_name.split("/")[-1].split(":")[-1]
    texture_id = f"minecraft:block/{clean_canon}"
    bare_name = clean_canon

    condition_flags = build_condition_flags(clean_canon, diffuse_path or Path(material_name))
    passed_flags = flags if flags is not None else extra_flags
    if passed_flags:
        condition_flags.update(passed_flags)

    # Find matching template using MiEx declarative priority matching
    template = find_matching_template(texture_id, templates)
    if template is None or template.name == "base":
        cand = find_matching_template(bare_name, templates)
        if cand and cand.name != "base":
            template = cand
    if template is None or template.name == "base":
        cand = find_matching_template(canon_name, templates)
        if cand and cand.name != "base":
            template = cand

    if template is None:
        template = find_matching_template("*", templates)
    if template is None:
        return None

    # If foliage template was matched for a block that isn't desaturated (e.g. flowers),
    # and vertex colors aren't present, fall back to base template so flowers aren't tinted
    if template.name == "foliage" and not condition_flags.get("biomeColor", False):
        if not checklist(clean_canon, "desaturated"):
            base_tpl = find_matching_template("*", templates)
            if base_tpl:
                template = base_tpl

    resolved_nodes: dict[str, MiExNode] = {}

    for condition, nodes in template.network.items():
        if not evaluate_condition(condition, texture_id, passes, condition_flags):
            continue

        for node_name, node in nodes.items():
            if node_name not in resolved_nodes:
                resolved_nodes[node_name] = MiExNode(
                    name=node.name,
                    node_type=node.node_type,
                    attributes={},
                )

            current_node = resolved_nodes[node_name]
            if node.node_type:
                current_node.node_type = node.node_type

            for attr_name, attr in node.attributes.items():
                conn = resolve_connection_reference(attr.connection, resolved_nodes)
                resolved_val = resolve_attribute_value(attr.value, texture_id, diffuse_path, passes)

                # MiEx fill-in: resolve biome color from MCprep JSON when vertex colors are not active
                if node_name == "MIX_COLOR" and attr_name == "B" and not conn:
                    if not condition_flags.get("biomeColor", False):
                        biome_col = get_mcprep_biome_color(clean_canon) or get_mcprep_biome_color(canon_name)
                        if biome_col:
                            resolved_val = biome_col

                current_node.attributes[attr_name] = MiExAttribute(
                    name=attr.name,
                    attr_type=attr.attr_type,
                    value=resolved_val,
                    connection=conn,
                    expression=attr.expression,
                )

    terminals: dict[str, str] = {}
    for k, v in template.shading_group.items():
        clean_k = k[5:] if k.startswith("json:") else k
        terminals[clean_k] = str(v)

    return MiExMaterial(
        name=material_name,
        terminals=terminals,
        network=resolved_nodes,
    )
