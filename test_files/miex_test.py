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

import json
from pathlib import Path
import tempfile
import unittest

import bpy

from MCprep_addon.materials.miex_generator import (
    auto_generate_miex_material,
    find_matching_template,
    matches_selection,
    resolve_connection_reference,
)
from MCprep_addon.materials.miex_parser import (
    BlenderCompactNodeInfo,
    MaterialsFileJSON,
    MiExAttribute,
    MiExNode,
    MiExTemplate,
    TemplateJSON,
    format_compact_node_type,
    parse_compact_node_type,
    parse_materials_json,
    parse_template,
    resolve_includes,
)
from MCprep_addon.materials.miex_prep import (
    apply_miex_material,
    find_materials_json,
    find_texture_in_pack,
    get_available_template_packs,
    get_default_templates,
    load_templates_from_dir,
    prep_single_material,
)


class MiExParserTest(unittest.TestCase):
    """Tests for MiEx template parsing and BlenderCompact syntax."""

    def test_compact_node_type_parsing(self):
        """Tests parsing of JSON:BlenderCompact-X.Y-NodeName, JSON:NodeName, dropped prefix, and USD nodes."""
        info = parse_compact_node_type("JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled")
        self.assertEqual(info.node_name, "ShaderNodeBsdfPrincipled")
        self.assertEqual(info.version, (5, 1))
        self.assertTrue(info.has_json_prefix)
        self.assertEqual(str(info), "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled")

        # Dropped JSON: prefix as in generated materials JSON
        info_dropped = parse_compact_node_type("BlenderCompact-5.1-ShaderNodeBsdfPrincipled")
        self.assertEqual(info_dropped.node_name, "ShaderNodeBsdfPrincipled")
        self.assertEqual(info_dropped.version, (5, 1))
        self.assertFalse(info_dropped.has_json_prefix)

        info_plain_json = parse_compact_node_type("JSON:ShaderNodeBsdfPrincipled")
        self.assertEqual(info_plain_json.node_name, "ShaderNodeBsdfPrincipled")
        self.assertIsNone(info_plain_json.version)
        self.assertTrue(info_plain_json.has_json_prefix)
        self.assertEqual(str(info_plain_json), "JSON:ShaderNodeBsdfPrincipled")

        info_usd = parse_compact_node_type("UsdPreviewSurface")
        self.assertEqual(info_usd.node_name, "UsdPreviewSurface")
        self.assertIsNone(info_usd.version)
        self.assertFalse(info_usd.has_json_prefix)
        self.assertEqual(str(info_usd), "UsdPreviewSurface")

    def test_compact_node_type_rejection(self):
        """Ensures malformed BlenderCompact syntax raises ValueError."""
        invalid_types = [
            "JSON:BlenderCompact-abc-Node",    # non-numeric version
            "JSON:BlenderCompact-5.1",         # missing node name
        ]
        for invalid in invalid_types:
            with self.assertRaises(ValueError):
                parse_compact_node_type(invalid)

    def test_format_compact_node_type(self):
        """Tests formatting into JSON:BlenderCompact-X.Y-NodeName."""
        formatted = format_compact_node_type("ShaderNodeBsdfPrincipled", version=(5, 1))
        self.assertEqual(formatted, "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled")

        formatted_plain = format_compact_node_type("ShaderNodeBsdfPrincipled", version=None)
        self.assertEqual(formatted_plain, "JSON:ShaderNodeBsdfPrincipled")

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
        texture_paths = {"diffuse": Path("textures/block/stone.png")}
        mat = auto_generate_miex_material(
            material_name="stone",
            texture_paths=texture_paths,
            templates=self.templates,
        )
        self.assertIsNotNone(mat)
        self.assertEqual(mat.name, "stone")
        self.assertEqual(mat.terminals["surface"], "MAT.BSDF")
        self.assertIn("MAT", mat.network)
        self.assertIn("FILE", mat.network)
        self.assertEqual(
            mat.network["FILE"].attributes["image"].value,
            "textures/block/stone.png",
        )

    def test_auto_generate_emissive_material(self):
        """Tests conditional inclusion of emission branch when emission pass exists."""
        texture_paths = {
            "diffuse": Path("textures/block/furnace_front_on.png"),
            "emission": Path("textures/block/furnace_front_on_e.png"),
        }
        mat = auto_generate_miex_material(
            material_name="furnace_front_on",
            texture_paths=texture_paths,
            templates=self.templates,
        )
        self.assertIsNotNone(mat)
        self.assertIn("TEX_EMIT", mat.network)
        self.assertEqual(
            mat.network["TEX_EMIT"].attributes["image"].value,
            "textures/block/furnace_front_on_e.png",
        )
        self.assertEqual(mat.network["MAT"].attributes["Emission Strength"].value, 1.0)


class MiExGeneratedMaterialTest(unittest.TestCase):
    """Tests parsing of exported MiEx _materials.json files."""

    def test_parse_exported_materials_json(self):
        """Tests parsing exported _materials.json with dropped JSON:/json: prefixes and terminals."""
        data: MaterialsFileJSON = {
            "stone": {
                "terminals": {
                    "surface": "MAT.BSDF",
                },
                "network": {
                    "MAT": {
                        "type": "BlenderCompact-5.1-ShaderNodeBsdfPrincipled",
                        "attributes": {
                            "Base Color": {"type": "Color", "connection": "FILE.Color"},
                            "Roughness": {"type": "Float", "value": 0.7},
                        },
                    },
                    "FILE": {
                        "type": "BlenderCompact-5.1-ShaderNodeTexImage",
                        "attributes": {
                            "image": {"type": "asset", "value": "textures/block/stone.png"},
                        },
                    },
                },
            },
            "glowstone": {
                "terminals": {
                    "json:surface": "MAT.BSDF",
                },
                "network": {
                    "MAT": {
                        "type": "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled",
                        "attributes": {
                            "Emission Strength": {"type": "Float", "value": 1.0},
                        },
                    },
                },
            },
        }

        materials = parse_materials_json(data)
        self.assertIn("stone", materials)
        self.assertIn("glowstone", materials)

        stone_mat = materials["stone"]
        self.assertEqual(stone_mat.name, "stone")
        self.assertEqual(stone_mat.terminals["surface"], "MAT.BSDF")
        self.assertIn("MAT", stone_mat.network)
        self.assertIn("FILE", stone_mat.network)
        mat_node = stone_mat.network["MAT"]
        self.assertEqual(mat_node.node_type, "BlenderCompact-5.1-ShaderNodeBsdfPrincipled")
        self.assertEqual(mat_node.attributes["Roughness"].value, 0.7)
        self.assertEqual(mat_node.attributes["Base Color"].connection, "FILE.Color")

        glowstone_mat = materials["glowstone"]
        self.assertEqual(glowstone_mat.name, "glowstone")
        self.assertEqual(glowstone_mat.terminals["surface"], "MAT.BSDF")
        self.assertIn("MAT", glowstone_mat.network)


class MiExPrepTest(unittest.TestCase):
    """Tests for applying MiEx materials to Blender materials and operators."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.preferences.addon_enable(module="MCprep_addon")

    def setUp(self):
        """Clears scene and data between each test"""
        bpy.ops.wm.read_homefile(app_template="", use_empty=True)

    def test_get_default_templates(self):
        """Tests built-in default templates creation and include resolution."""
        templates = get_default_templates()
        self.assertEqual(len(templates), 8)
        names = [t.name for t in templates]
        self.assertIn("base", names)
        self.assertIn("emission", names)
        self.assertIn("glass", names)
        self.assertIn("metallic", names)
        self.assertIn("reflective", names)
        self.assertIn("foliage", names)
        self.assertIn("water", names)
        self.assertIn("lava", names)
        # Ensure descending priority order
        priorities = [t.priority for t in templates]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_load_templates_from_dir(self):
        """Tests loading templates from a folder."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tpl_a = {
                "priority": 1,
                "selection": ["*"],
                "shadingGroup": {"surface": "MAT.BSDF"},
                "network": {
                    "": {
                        "MAT": {
                            "type": "JSON:BlenderCompact-5.1-ShaderNodeBsdfPrincipled",
                            "attributes": {"Roughness": {"type": "Float", "value": 0.5}},
                        }
                    }
                },
            }
            tpl_b = {
                "priority": 10,
                "selection": ["*glass*"],
                "include": ["tpl_a"],
                "network": {
                    "": {
                        "MAT": {
                            "attributes": {"Transmission Weight": {"type": "Float", "value": 1.0}},
                        }
                    }
                },
            }
            with (tmp_path / "tpl_a.json").open("w", encoding="utf-8") as f:
                json.dump(tpl_a, f)
            with (tmp_path / "tpl_b.json").open("w", encoding="utf-8") as f:
                json.dump(tpl_b, f)

            loaded = load_templates_from_dir(tmp_path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].name, "tpl_b")
            self.assertEqual(loaded[0].priority, 10)
            self.assertIn("MAT", loaded[0].network[""])
            self.assertEqual(loaded[0].network[""]["MAT"].attributes["Roughness"].value, 0.5)
            self.assertEqual(loaded[0].network[""]["MAT"].attributes["Transmission Weight"].value, 1.0)

    def test_apply_miex_material(self):
        """Tests constructing Blender node tree from MiExMaterial."""
        mat = bpy.data.materials.new(name="test_miex_apply")
        mat_data: MaterialsFileJSON = {
            "test_miex_apply": {
                "terminals": {
                    "surface": "MAT.BSDF",
                },
                "network": {
                    "MAT": {
                        "type": "BlenderCompact-5.1-ShaderNodeBsdfPrincipled",
                        "attributes": {
                            "Base Color": {"type": "Color", "connection": "FILE.Color"},
                            "Roughness": {"type": "Float", "value": 0.42},
                        },
                    },
                    "FILE": {
                        "type": "BlenderCompact-5.1-ShaderNodeTexImage",
                        "attributes": {
                            "interpolation": {"type": "string", "value": "Closest"},
                        },
                    },
                },
            }
        }
        parsed_dict = parse_materials_json(mat_data)
        miex_mat = parsed_dict["test_miex_apply"]

        apply_miex_material(mat, miex_mat)

        self.assertTrue(mat.use_nodes)
        nodes = mat.node_tree.nodes
        self.assertIn("Material Output", nodes)
        self.assertIn("MAT", nodes)
        self.assertIn("FILE", nodes)

        mat_node = nodes["MAT"]
        self.assertAlmostEqual(mat_node.inputs["Roughness"].default_value, 0.42, places=3)

        file_node = nodes["FILE"]
        self.assertEqual(file_node.interpolation, "Closest")

        # Verify links
        links = mat.node_tree.links
        out_node = nodes["Material Output"]

        # Link from FILE.Color to MAT.Base Color
        has_file_link = any(
            l.from_node == file_node and l.from_socket.name == "Color" and
            l.to_node == mat_node and l.to_socket.name == "Base Color"
            for l in links
        )
        self.assertTrue(has_file_link)

        # Link from MAT.BSDF to Material Output.Surface
        has_surf_link = any(
            l.from_node == mat_node and l.from_socket.name == "BSDF" and
            l.to_node == out_node and l.to_socket.name == "Surface"
            for l in links
        )
        self.assertTrue(has_surf_link)

    def test_foliage_generation_and_apply(self):
        """Tests that foliage materials generate ShaderNodeMix and apply tint multiplier."""
        templates = get_default_templates()
        mat_miex = auto_generate_miex_material(
            material_name="minecraft:block/oak_leaves",
            texture_paths={"diffuse": Path("textures/block/oak_leaves.png")},
            templates=templates,
        )
        self.assertIsNotNone(mat_miex)
        self.assertIn("MIX_COLOR", mat_miex.network)
        mix_miex = mat_miex.network["MIX_COLOR"]
        self.assertEqual(mix_miex.attributes["data_type"].value, "RGBA")
        self.assertEqual(mix_miex.attributes["blend_type"].value, "MULTIPLY")
        self.assertEqual(mix_miex.attributes["Factor"].value, 1.0)
        self.assertEqual(mix_miex.attributes["A"].connection, "FILE.Color")
        self.assertEqual(mat_miex.network["MAT"].attributes["Base Color"].connection, "MIX_COLOR.Result")

        # Apply to a Blender material
        mat = bpy.data.materials.new(name="test_oak_leaves")
        apply_miex_material(mat, mat_miex)

        nodes = mat.node_tree.nodes
        self.assertIn("MIX_COLOR", nodes)
        mix_node = nodes["MIX_COLOR"]
        self.assertEqual(mix_node.bl_idname, "ShaderNodeMix")
        self.assertEqual(mix_node.data_type, "RGBA")
        self.assertEqual(mix_node.blend_type, "MULTIPLY")
        self.assertAlmostEqual(mix_node.inputs["Factor"].default_value, 1.0, places=3)

        # Check links
        file_node = nodes["FILE"]
        mat_node = nodes["MAT"]
        links = mat.node_tree.links
        has_mix_in = any(
            l.from_node == file_node and l.to_node == mix_node and l.to_socket.name == "A"
            for l in links
        )
        self.assertTrue(has_mix_in)

        has_mix_out = any(
            l.from_node == mix_node and l.from_socket.name == "Result" and
            l.to_node == mat_node and l.to_socket.name == "Base Color"
            for l in links
        )
        self.assertTrue(has_mix_out)

    def test_template_isolation_no_leaked_emission(self):
        """Tests that child templates do not leak emission onto base/stone materials."""
        templates = get_default_templates()
        stone_miex = auto_generate_miex_material(
            material_name="minecraft:block/stone",
            texture_paths={"diffuse": Path("textures/block/stone.png")},
            templates=templates,
        )
        self.assertIsNotNone(stone_miex)
        # Stone should not have emission attributes
        mat_attrs = stone_miex.network["MAT"].attributes
        self.assertNotIn("Emission Color", mat_attrs)

        stone_mat = bpy.data.materials.new(name="test_stone_no_emit")
        apply_miex_material(stone_mat, stone_miex)
        stone_bsdf = stone_mat.node_tree.nodes["MAT"]
        self.assertEqual(stone_bsdf.inputs["Emission Strength"].default_value, 0.0)

        # But glowstone should have emission
        glow_miex = auto_generate_miex_material(
            material_name="minecraft:block/glowstone",
            texture_paths={"diffuse": Path("textures/block/glowstone.png")},
            templates=templates,
        )
        self.assertIsNotNone(glow_miex)
        glow_attrs = glow_miex.network["MAT"].attributes
        self.assertIn("Emission Color", glow_attrs)
        self.assertEqual(glow_attrs["Emission Strength"].value, 1.0)


    def test_prep_operator_execution(self):
        """Tests the MCPREP_OT_miex_prep_materials operator."""
        mesh = bpy.data.meshes.new("TestOpMesh")
        obj = bpy.data.objects.new("TestOpObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        mat = bpy.data.materials.new(name="minecraft:block/stone")
        obj.data.materials.append(mat)

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        res = bpy.ops.mcprep.miex_prep_materials()
        self.assertEqual(res, {'FINISHED'})
        self.assertTrue(mat.get("MCPREP_MIEX_PREPPED", False))
        self.assertIn("Material Output", mat.node_tree.nodes)
        self.assertIn("MAT", mat.node_tree.nodes)

    def test_swap_texture_pack_operator(self):
        """Tests the MCPREP_OT_miex_swap_texture_pack operator."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pack_dir = Path(tmp_dir)
            block_dir = pack_dir / "assets" / "minecraft" / "textures" / "block"
            block_dir.mkdir(parents=True, exist_ok=True)
            stone_file = block_dir / "stone.png"

            img = bpy.data.images.new("temp_stone", width=16, height=16)
            img.filepath_raw = str(stone_file)
            img.file_format = "PNG"
            img.save()

            mesh = bpy.data.meshes.new("TestSwapMesh")
            obj = bpy.data.objects.new("TestSwapObj", mesh)
            bpy.context.scene.collection.objects.link(obj)

            mat = bpy.data.materials.new(name="minecraft:block/stone")
            obj.data.materials.append(mat)

            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)

            res = bpy.ops.mcprep.miex_swap_texture_pack(filepath=str(pack_dir))
            self.assertEqual(res, {'FINISHED'})
            self.assertTrue(mat.get("MCPREP_MIEX_PREPPED", False))
            self.assertTrue(mat.get("texture_swapped", False))
            self.assertIn("FILE", mat.node_tree.nodes)
            self.assertIsNotNone(mat.node_tree.nodes["FILE"].image)

    def test_get_template_packs(self):
        """Tests that all template packs can be discovered and loaded."""
        packs = get_available_template_packs()
        self.assertIn("simple", packs)
        self.assertIn("specular", packs)
        self.assertIn("seus", packs)

        for pack in ("simple", "specular", "seus"):
            templates = get_default_templates(pack)
            self.assertEqual(len(templates), 8)
            names = [t.name for t in templates]
            self.assertIn("base", names)
            self.assertIn("emission", names)
            self.assertIn("foliage", names)
            self.assertIn("glass", names)
            self.assertIn("lava", names)
            self.assertIn("metallic", names)
            self.assertIn("reflective", names)
            self.assertIn("water", names)

    def test_specular_pack_generation_and_apply(self):
        """Tests specular pack generates RGBCurve inverted normal and Invert roughness."""
        templates = get_default_templates("specular")
        mat_miex = auto_generate_miex_material(
            material_name="minecraft:block/cobblestone",
            texture_paths={
                "diffuse": Path("textures/block/cobblestone.png"),
                "normal": Path("textures/block/cobblestone_n.png"),
                "specular": Path("textures/block/cobblestone_s.png"),
            },
            templates=templates,
        )
        self.assertIsNotNone(mat_miex)
        self.assertIn("NORM_CURVE", mat_miex.network)
        self.assertIn("NORM_MAP", mat_miex.network)
        self.assertIn("SPEC_INV", mat_miex.network)

        mat = bpy.data.materials.new(name="test_cobble_spec")
        apply_miex_material(mat, mat_miex)

        nodes = mat.node_tree.nodes
        self.assertIn("NORM_CURVE", nodes)
        self.assertIn("NORM_MAP", nodes)
        self.assertIn("SPEC_INV", nodes)
        self.assertIn("TEX_SPEC", nodes)
        self.assertIn("TEX_NORM", nodes)

        # Check that curve 1 is inverted (green channel inversion)
        curve_node = nodes["NORM_CURVE"]
        curve_g = curve_node.mapping.curves[1]
        self.assertAlmostEqual(curve_g.points[0].location[1], 1.0, places=3)
        self.assertAlmostEqual(curve_g.points[1].location[1], 0.0, places=3)

        # Check links
        links = mat.node_tree.links
        norm_map_node = nodes["NORM_MAP"]
        bsdf_node = nodes["MAT"]
        spec_inv_node = nodes["SPEC_INV"]
        tex_spec_node = nodes["TEX_SPEC"]

        # NORM_MAP.Normal -> MAT.Normal
        has_norm_link = any(
            l.from_node == norm_map_node and l.from_socket.name == "Normal" and
            l.to_node == bsdf_node and l.to_socket.name == "Normal"
            for l in links
        )
        self.assertTrue(has_norm_link)

        # SPEC_INV.Color -> MAT.Roughness
        has_rough_link = any(
            l.from_node == spec_inv_node and l.to_node == bsdf_node and l.to_socket.name == "Roughness"
            for l in links
        )
        self.assertTrue(has_rough_link)

        # TEX_SPEC.Color -> MAT.Specular IOR Level / Specular
        spec_sock_name = "Specular IOR Level" if "Specular IOR Level" in bsdf_node.inputs else "Specular"
        has_spec_link = any(
            l.from_node == tex_spec_node and l.to_node == bsdf_node and l.to_socket.name == spec_sock_name
            for l in links
        )
        self.assertTrue(has_spec_link)

    def test_seus_pack_generation_and_apply(self):
        """Tests SEUS pack generates SeparateColor and connects R->Invert->Roughness, G->Metallic, B->Emission."""
        templates = get_default_templates("seus")
        mat_miex = auto_generate_miex_material(
            material_name="minecraft:block/iron_block",
            texture_paths={
                "diffuse": Path("textures/block/iron_block.png"),
                "normal": Path("textures/block/iron_block_n.png"),
                "specular": Path("textures/block/iron_block_s.png"),
            },
            templates=templates,
        )
        self.assertIsNotNone(mat_miex)
        self.assertIn("SEP_COLOR", mat_miex.network)
        self.assertIn("SPEC_INV", mat_miex.network)
        self.assertIn("NORM_CURVE", mat_miex.network)

        mat = bpy.data.materials.new(name="test_iron_seus")
        apply_miex_material(mat, mat_miex)

        nodes = mat.node_tree.nodes
        self.assertIn("SEP_COLOR", nodes)
        self.assertIn("SPEC_INV", nodes)
        self.assertIn("NORM_CURVE", nodes)

        sep_node = nodes["SEP_COLOR"]
        spec_inv_node = nodes["SPEC_INV"]
        bsdf_node = nodes["MAT"]
        file_node = nodes["FILE"]
        links = mat.node_tree.links

        # Check Red -> Invert -> Roughness
        has_red_to_inv = any(
            l.from_node == sep_node and l.from_socket.name in ("Red", "R") and
            l.to_node == spec_inv_node
            for l in links
        )
        self.assertTrue(has_red_to_inv)

        has_inv_to_rough = any(
            l.from_node == spec_inv_node and l.to_node == bsdf_node and l.to_socket.name == "Roughness"
            for l in links
        )
        self.assertTrue(has_inv_to_rough)

        # Check Green -> Metallic
        has_green_to_met = any(
            l.from_node == sep_node and l.from_socket.name in ("Green", "G") and
            l.to_node == bsdf_node and l.to_socket.name == "Metallic"
            for l in links
        )
        self.assertTrue(has_green_to_met)

        # Check Blue -> Emission Strength
        has_blue_to_emit = any(
            l.from_node == sep_node and l.from_socket.name in ("Blue", "B") and
            l.to_node == bsdf_node and l.to_socket.name == "Emission Strength"
            for l in links
        )
        self.assertTrue(has_blue_to_emit)

        # Check FILE.Color -> Emission Color
        has_file_to_emit_col = any(
            l.from_node == file_node and l.to_node == bsdf_node and l.to_socket.name == "Emission Color"
            for l in links
        )
        self.assertTrue(has_file_to_emit_col)

    def test_prep_operator_with_pack_formats(self):
        """Tests the MCPREP_OT_miex_prep_materials operator with specular and seus formats."""
        mesh = bpy.data.meshes.new("TestOpPackMesh")
        obj = bpy.data.objects.new("TestOpPackObj", mesh)
        bpy.context.scene.collection.objects.link(obj)

        mat = bpy.data.materials.new(name="minecraft:block/stone")
        obj.data.materials.append(mat)

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        res_spec = bpy.ops.mcprep.miex_prep_materials(pack_format="specular")
        self.assertEqual(res_spec, {'FINISHED'})

        res_seus = bpy.ops.mcprep.miex_prep_materials(pack_format="seus")
        self.assertEqual(res_seus, {'FINISHED'})

    def test_miex_ui_properties_and_helpers(self):
        """Tests scene properties and helper operators for MiEx UI."""
        scene = bpy.context.scene
        self.assertTrue(hasattr(scene, "mcprep_miex_pack_format"))
        self.assertTrue(hasattr(scene, "mcprep_miex_templates_path"))

        scene.mcprep_miex_pack_format = "seus"
        self.assertEqual(scene.mcprep_miex_pack_format, "seus")

        scene.mcprep_miex_templates_path = "/custom/templates"
        self.assertEqual(scene.mcprep_miex_templates_path, "/custom/templates")

        res_reset = bpy.ops.mcprep.miex_reset_templates_path()
        self.assertEqual(res_reset, {'FINISHED'})
        self.assertEqual(scene.mcprep_miex_templates_path, "")


if __name__ == "__main__":
    import sys
    unittest.main(argv=[sys.argv[0]])
