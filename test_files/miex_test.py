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

import unittest

from MCprep_addon.materials.miex_generator import (
    auto_generate_miex_material,
    find_matching_template,
    matches_selection,
    resolve_connection_reference,
)
from MCprep_addon.materials.miex_parser import (
    BlenderCompactNodeInfo,
    MiExAttribute,
    MiExNode,
    MiExTemplate,
    TemplateJSON,
    format_compact_node_type,
    parse_compact_node_type,
    parse_template,
    resolve_includes,
)


class MiExParserTest(unittest.TestCase):
    """Tests for MiEx template parsing and BlenderCompact syntax."""

    def test_compact_node_type_parsing(self):
        """Tests strict parsing of JSON:BlenderCompact-X.Y-NodeName."""
        info = parse_compact_node_type("JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled")
        self.assertEqual(info.node_name, "ShaderNodeBsdfPrincipled")
        self.assertEqual(info.version, (5, 1))
        self.assertEqual(str(info), "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled")

        info_45 = parse_compact_node_type("JSON:BlenderCompact-4.5-ShaderNodeTexImage")
        self.assertEqual(info_45.node_name, "ShaderNodeTexImage")
        self.assertEqual(info_45.version, (4, 5))

    def test_compact_node_type_rejection(self):
        """Ensures non-BlenderCompact or missing JSON: prefix raises ValueError."""
        invalid_types = [
            "BlenderCompact-5.1-ShaderNodeBsdfPrincipled",  # missing JSON:
            "JSON:ShaderNodeBsdfPrincipled",                # missing BlenderCompact
            "ShaderNodeBsdfPrincipled",                     # plain Blender node
            "UsdPreviewSurface",                            # USD node
            "JSON:BlenderCompact-abc-Node",                 # invalid version
        ]
        for invalid in invalid_types:
            with self.assertRaises(ValueError):
                parse_compact_node_type(invalid)

    def test_format_compact_node_type(self):
        """Tests formatting into JSON:BlenderCompact-X.Y-NodeName."""
        formatted = format_compact_node_type("ShaderNodeBsdfPrincipled", version=(5, 1))
        self.assertEqual(formatted, "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled")

    def test_template_include_inheritance(self):
        """Tests template parsing and include inheritance."""
        base_json: TemplateJSON = {
            "priority": 0,
            "selection": ["*"],
            "shadingGroup": {"surface": "MAT.BSDF"},
            "network": {
                "@texture@": {
                    "MAT": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled",
                        "attributes": {
                            "Base Color": {"type": "Color", "connection": "FILE.Color"},
                            "Roughness": {"type": "Float", "value": 0.7},
                        },
                    },
                    "FILE": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeTexImage",
                        "attributes": {
                            "image": {"type": "asset", "value": "@texture@"},
                        },
                    },
                },
            },
        }

        emission_json: TemplateJSON = {
            "priority": 5,
            "selection": ["minecraft:block/glowstone"],
            "include": ["base"],
            "shadingGroup": {"json:surface": "MAT.BSDF"},
            "network": {
                "@texture@": {
                    "MAT": {
                        "attributes": {
                            "Emission Strength": {"type": "Float", "value": 1.0},
                        },
                    },
                },
            },
        }

        base_tpl = parse_template(base_json, name="base")
        emission_tpl = parse_template(emission_json, name="emission")

        resolved = resolve_includes(emission_tpl, {"base": base_tpl})
        self.assertEqual(resolved.priority, 5)
        self.assertEqual(resolved.selection, ["minecraft:block/glowstone"])
        self.assertEqual(resolved.shading_group["surface"], "MAT.BSDF")
        self.assertEqual(resolved.shading_group["json:surface"], "MAT.BSDF")

        nodes = resolved.network["@texture@"]
        self.assertIn("FILE", nodes)
        self.assertIn("MAT", nodes)
        self.assertEqual(nodes["MAT"].attributes["Roughness"].value, 0.7)
        self.assertEqual(nodes["MAT"].attributes["Emission Strength"].value, 1.0)


class MiExGeneratorTest(unittest.TestCase):
    """Tests for auto-generating MiEx materials from texture paths."""

    def setUp(self):
        base_json: TemplateJSON = {
            "priority": 0,
            "selection": ["*"],
            "shadingGroup": {"surface": "MAT.BSDF"},
            "network": {
                "@texture@": {
                    "MAT": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled",
                        "attributes": {
                            "Base Color": {"type": "Color", "connection": "FILE.Color"},
                            "Roughness": {"type": "Float", "value": 0.7},
                        },
                    },
                    "FILE": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeTexImage",
                        "attributes": {
                            "image": {"type": "asset", "value": "@texture@"},
                        },
                    },
                },
                "@texture@_emission": {
                    "TEX_EMIT": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeTexImage",
                        "attributes": {
                            "image": {"type": "asset", "value": "@texture@_emission"},
                        },
                    },
                    "MAT": {
                        "attributes": {
                            "Emission Color": {"type": "Color", "connection": "TEX_EMIT.Color"},
                            "Emission Strength": {"type": "Float", "value": 1.0},
                        },
                    },
                },
            },
        }

        glass_json: TemplateJSON = {
            "priority": 10,
            "selection": ["minecraft:block/glass*", "glass"],
            "shadingGroup": {"surface": "GLASS.BSDF"},
            "network": {
                "@texture@": {
                    "GLASS": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeBsdfGlass",
                        "attributes": {
                            "Roughness": {"type": "Float", "value": 0.0},
                        },
                    },
                },
            },
        }

        self.templates = [
            parse_template(base_json, name="base"),
            parse_template(glass_json, name="glass"),
        ]

    def test_matches_selection(self):
        """Tests selection pattern matching with namespaces and bare names."""
        self.assertTrue(matches_selection("minecraft:block/dirt", "*"))
        self.assertTrue(matches_selection("minecraft:block/glass", "minecraft:block/glass*"))
        self.assertTrue(matches_selection("dirt", "minecraft:block/dirt"))
        self.assertFalse(matches_selection("minecraft:block/stone", "minecraft:block/glass*"))

    def test_find_matching_template_priority(self):
        """Ensures highest priority template is selected."""
        tpl = find_matching_template("minecraft:block/glass", self.templates)
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.name, "glass")

        tpl_dirt = find_matching_template("minecraft:block/dirt", self.templates)
        self.assertIsNotNone(tpl_dirt)
        self.assertEqual(tpl_dirt.name, "base")

    def test_connection_reference_resolution(self):
        """Tests dynamic ${node.attribute} reference resolution."""
        node_a = MiExNode(
            name="FILE",
            node_type="JSON:BlenderCompact-5.1-ShaderNodeTexImage",
            attributes={"Color": MiExAttribute(name="Color", connection="SRC.Color")},
        )
        nodes = {"FILE": node_a}

        conn = resolve_connection_reference("${FILE.Color}", nodes)
        self.assertEqual(conn, "SRC.Color")

        unrelated = resolve_connection_reference("NORMAL.Normal", nodes)
        self.assertEqual(unrelated, "NORMAL.Normal")

    def test_auto_generate_base_material(self):
        """Tests auto-generating MiEx material for standard texture."""
        texture_paths = {"diffuse": "textures/block/stone.png"}
        mat = auto_generate_miex_material(
            material_name="stone",
            texture_paths=texture_paths,
            templates=self.templates,
        )
        self.assertIsNotNone(mat)
        self.assertEqual(mat.name, "stone")
        self.assertEqual(mat.shading_group["surface"], "MAT.BSDF")
        self.assertIn("MAT", mat.nodes)
        self.assertIn("FILE", mat.nodes)
        self.assertEqual(
            mat.nodes["FILE"].attributes["image"].value,
            "textures/block/stone.png",
        )

    def test_auto_generate_emissive_material(self):
        """Tests conditional inclusion of emission branch when emission pass exists."""
        texture_paths = {
            "diffuse": "textures/block/furnace_front_on.png",
            "emission": "textures/block/furnace_front_on_e.png",
        }
        mat = auto_generate_miex_material(
            material_name="furnace_front_on",
            texture_paths=texture_paths,
            templates=self.templates,
        )
        self.assertIsNotNone(mat)
        self.assertIn("TEX_EMIT", mat.nodes)
        self.assertEqual(mat.nodes["MAT"].attributes["Emission Strength"].value, 1.0)


if __name__ == "__main__":
    import sys
    unittest.main(argv=[sys.argv[0]])
