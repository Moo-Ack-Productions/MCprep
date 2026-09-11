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

"""MiEx material template parser.

Parses MiEx material templates from JSON according to the MiEx specification:
https://github.com/BramStoutProductions/MiEx/wiki/13.-Material-Templates

Supports:
- Priority, selection pattern lists, and include inheritance
- Shading group terminal mappings (e.g. surface, json:surface)
- Conditional network parts (evaluated top-to-bottom)
- Attribute definitions (type, value, connection, expression)
- Strict BlenderCompact-X.Y-PythonNodeName syntax with JSON: prefix
"""

from dataclasses import dataclass, field
import json
from pathlib import Path

from typing import TypedDict

# Concrete type for attribute values in material templates
AttributeValue = float | int | str | bool | list[float] | list[int] | list[str]


class AttributeJSON(TypedDict, total=False):
    """Structure of an attribute in template JSON."""
    type: str
    value: AttributeValue
    connection: str
    expression: str


class NodeJSON(TypedDict, total=False):
    """Structure of a shading node in template JSON."""
    type: str
    attributes: dict[str, AttributeJSON]


class TemplateJSON(TypedDict, total=False):
    """Structure of a material template in JSON."""
    priority: int
    selection: list[str]
    include: list[str]
    shadingGroup: dict[str, str]
    network: dict[str, dict[str, NodeJSON]]


@dataclass
class BlenderCompactNodeInfo:
    """Represents node identity with BlenderCompact version syntax."""
    node_name: str
    version: tuple[int, int]

    def __str__(self) -> str:
        """Returns the formatted MiEx node type string."""
        return f"JSON:BlenderCompact-{self.version[0]}.{self.version[1]}-{self.node_name}"


def parse_compact_node_type(type_str: str) -> BlenderCompactNodeInfo:
    """Parses node type string using string operations.
    
    Strictly requires the format: 'JSON:BlenderCompact-X.Y-PythonNodeName'.
    Raises ValueError if the syntax is not strictly adhered to.
    """
    prefix = "JSON:BlenderCompact-"
    if not type_str.startswith(prefix):
        raise ValueError(
            f"Invalid MiEx node type '{type_str}': must strictly follow 'JSON:BlenderCompact-X.Y-NodeName'"
        )

    remainder = type_str[len(prefix):]
    parts = remainder.split("-", 1)
    if len(parts) != 2:
        raise ValueError(
            f"Invalid MiEx node type '{type_str}': expected version and node name separated by '-'"
        )

    version_str, node_name = parts
    v_parts = version_str.split(".", 1)
    if len(v_parts) != 2 or not (v_parts[0].isdigit() and v_parts[1].isdigit()):
        raise ValueError(
            f"Invalid MiEx node version in '{type_str}': expected X.Y with numeric components"
        )

    version = (int(v_parts[0]), int(v_parts[1]))
    return BlenderCompactNodeInfo(node_name=node_name, version=version)


def format_compact_node_type(
    node_name: str,
    version: tuple[int, int] = (5, 1),
) -> str:
    """Formats a python node name into JSON:BlenderCompact-X.Y-PythonNodeName."""
    return str(BlenderCompactNodeInfo(node_name=node_name, version=version))


@dataclass
class MiExAttribute:
    """An attribute of a shading node in a MiEx material template."""
    name: str
    attr_type: str = ""
    value: AttributeValue | None = None
    connection: str | None = None
    expression: str | None = None

    @classmethod
    def from_dict(cls, name: str, data: AttributeJSON) -> "MiExAttribute":
        attr_type = str(data.get("type", ""))
        val = data.get("value")
        raw_val: AttributeValue | None = None
        if isinstance(val, (float, int, str, bool, list)):
            raw_val = val

        conn = data.get("connection")
        raw_conn = str(conn) if isinstance(conn, str) else None

        expr = data.get("expression")
        raw_expr = str(expr) if isinstance(expr, str) else None

        return cls(
            name=name,
            attr_type=attr_type,
            value=raw_val,
            connection=raw_conn,
            expression=raw_expr,
        )


@dataclass
class MiExNode:
    """A shading node defined in a MiEx network part."""
    name: str
    node_type: str = ""
    attributes: dict[str, MiExAttribute] = field(default_factory=dict)

    @property
    def compact_info(self) -> BlenderCompactNodeInfo:
        return parse_compact_node_type(self.node_type)

    @classmethod
    def from_dict(cls, name: str, data: NodeJSON) -> "MiExNode":
        node_type = str(data.get("type", ""))
        attributes: dict[str, MiExAttribute] = {}
        raw_attrs = data.get("attributes")
        if not isinstance(raw_attrs, dict):
            return cls(name=name, node_type=node_type, attributes=attributes)

        for attr_name, attr_data in raw_attrs.items():
            if not isinstance(attr_data, dict):
                continue
            attributes[attr_name] = MiExAttribute.from_dict(attr_name, attr_data)

        return cls(name=name, node_type=node_type, attributes=attributes)


@dataclass
class MiExTemplate:
    """Represents a parsed MiEx material template."""
    name: str = ""
    priority: int = 0
    selection: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    shading_group: dict[str, str] = field(default_factory=dict)
    # network maps condition string -> dict of node name -> MiExNode
    network: dict[str, dict[str, MiExNode]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: TemplateJSON, name: str = "") -> "MiExTemplate":
        priority_val = data.get("priority", 0)
        priority = int(priority_val) if isinstance(priority_val, (int, float)) else 0

        raw_selection = data.get("selection", [])
        selection = [str(x) for x in raw_selection] if isinstance(raw_selection, list) else []

        raw_include = data.get("include", [])
        include = [str(x) for x in raw_include] if isinstance(raw_include, list) else []

        raw_shading = data.get("shadingGroup", {})
        shading_group = (
            {str(k): str(v) for k, v in raw_shading.items()}
            if isinstance(raw_shading, dict)
            else {}
        )

        network: dict[str, dict[str, MiExNode]] = {}
        raw_net = data.get("network")
        if not isinstance(raw_net, dict):
            return cls(
                name=name,
                priority=priority,
                selection=selection,
                include=include,
                shading_group=shading_group,
                network=network,
            )

        for condition, nodes_dict in raw_net.items():
            if not isinstance(nodes_dict, dict):
                continue
            network_part: dict[str, MiExNode] = {}
            for node_name, node_data in nodes_dict.items():
                if not isinstance(node_data, dict):
                    continue
                network_part[node_name] = MiExNode.from_dict(node_name, node_data)
            network[condition] = network_part

        return cls(
            name=name,
            priority=priority,
            selection=selection,
            include=include,
            shading_group=shading_group,
            network=network,
        )


def parse_template(data: TemplateJSON, name: str = "") -> MiExTemplate:
    """Parses a dictionary representing a MiEx material template."""
    return MiExTemplate.from_dict(data, name=name)


def parse_template_file(filepath: Path | str) -> MiExTemplate:
    """Reads and parses a MiEx material template JSON file."""
    path = Path(filepath)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return parse_template(data, name=path.stem)


def resolve_includes(
    template: MiExTemplate,
    library: dict[str, MiExTemplate],
    visited: set[str] | None = None,
) -> MiExTemplate:
    """Resolves template inheritance according to the MiEx specification.
    
    Includes are resolved in order, merging shadingGroup and network parts.
    Later templates override earlier ones. Priority and selection are NOT inherited.
    """
    if visited is None:
        visited = set()

    if template.name:
        if template.name in visited:
            return template
        visited.add(template.name)

    merged_shading_group: dict[str, str] = {}
    merged_network: dict[str, dict[str, MiExNode]] = {}

    for inc_name in template.include:
        if inc_name == template.name:
            continue
        inc_tpl = library.get(inc_name)
        if inc_tpl is None:
            continue
        resolved_inc = resolve_includes(inc_tpl, library, visited.copy())
        merged_shading_group.update(resolved_inc.shading_group)
        for cond, nodes in resolved_inc.network.items():
            if cond not in merged_network:
                merged_network[cond] = {}
            for node_name, node in nodes.items():
                merged_network[cond][node_name] = node

    # Apply current template over includes
    merged_shading_group.update(template.shading_group)
    for cond, nodes in template.network.items():
        if cond not in merged_network:
            merged_network[cond] = {}
        for node_name, node in nodes.items():
            if node_name not in merged_network[cond]:
                merged_network[cond][node_name] = node
                continue

            existing = merged_network[cond][node_name]
            if node.node_type:
                existing.node_type = node.node_type
            for attr_name, attr in node.attributes.items():
                existing.attributes[attr_name] = attr

    return MiExTemplate(
        name=template.name,
        priority=template.priority,
        selection=list(template.selection),
        include=list(template.include),
        shading_group=merged_shading_group,
        network=merged_network,
    )
