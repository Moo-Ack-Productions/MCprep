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

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..conf import env

# Constants for JSON keys
VIVY_VERSION					= "version"
VIVY_MATERIALS					= "materials"
VIVY_MATERIALS_BASE_MATERIAL		= "base_material"
VIVY_MATERIALS_DESC					= "desc"
VIVY_MATERIALS_PASSES				= "passes"
VIVY_MATERIALS_PASSES_DIFFUSE			= "diffuse"
VIVY_MATERIALS_PASSES_SPECULAR			= "specular"
VIVY_MATERIALS_PASSES_NORMAL			= "normal"
VIVY_MATERIALS_REFINEMENTS			= "refinements"
VIVY_MATERIALS_REFINEMENTS_EMISSIVE		= "emissive"
VIVY_MATERIALS_REFINEMENTS_REFLECTIVE	= "reflective"
VIVY_MATERIALS_REFINEMENTS_METALLIC		= "metallic"
VIVY_MATERIALS_REFINEMENTS_GLASS		= "glass"
VIVY_MATERIALS_REFINEMENTS_FALLBACK_S	= "fallback_s"
VIVY_MATERIALS_REFINEMENTS_FALLBACK_N	= "fallback_n"
VIVY_MATERIALS_REFINEMENTS_FALLBACK		= "fallback"
VIVY_MAPPING					= "mapping"
VIVY_MAPPING_MATERIAL				= "material"
VIVY_MAPPING_REFINEMENT			= "refinement"

# Data classes
class Fallback(Enum):
	FALLBACK_S = "fallback_s"
	FALLBACK_N = "fallback_n"
	FALLBACK = "fallback"

@dataclass
class VivyPasses:
	diffuse: str 
	specular: Optional[str]
	normal: Optional[str]

@dataclass
class VivyRefinements:
	emissive: Optional[str]
	reflective: Optional[str]
	metallic: Optional[str]
	glass: Optional[str]
	fallback_n: Optional[str]
	fallback_s: Optional[str]
	fallback: Optional[str]

@dataclass
class VivyMaterial:
	base_material: str 
	desc: str 
	passes: VivyPasses
	refinements: Optional[VivyRefinements]

@dataclass
class VivyMapping:
	material: VivyMaterial
	refinement: Optional[str]

# Helper functions
# 
# Functions are named based on 
# what they return, and how they
# return it. For instance, a function
# with the json prefix means it returns
# the direct JSON values
#
# In addition, the data versions of each
# function are located next to their json
# counterparts, and above

def data_vivy_material(mat: str) -> VivyMaterial:
	"""Get Vivy material data from a given material name.
	
	Params:
		mat: str - Vivy material name

	Returns:
		VivyMaterial - Vivy material data for mat
	"""
	json_material = json_vivy_material(mat)
	json_passes = json_vivy_passes(mat)
	json_refinements = json_vivy_refinements(mat)
	return VivyMaterial(
		base_material=json_material[VIVY_MATERIALS_BASE_MATERIAL],
		desc=json_material[VIVY_MATERIALS_DESC],
		passes=VivyPasses(
			diffuse=json_passes[VIVY_MATERIALS_PASSES_DIFFUSE],
			specular=json_passes[VIVY_MATERIALS_PASSES_SPECULAR] if VIVY_MATERIALS_PASSES_SPECULAR in json_passes else None,
			normal=json_passes[VIVY_MATERIALS_PASSES_NORMAL] if VIVY_MATERIALS_PASSES_NORMAL in json_passes else None
		),
		refinements=None if not json_refinements else VivyRefinements(
			emissive=json_refinements[VIVY_MATERIALS_REFINEMENTS_EMISSIVE] if VIVY_MATERIALS_REFINEMENTS_EMISSIVE in json_refinements else None,
			reflective=json_refinements[VIVY_MATERIALS_REFINEMENTS_REFLECTIVE] if VIVY_MATERIALS_REFINEMENTS_REFLECTIVE in json_refinements else None,
			metallic=json_refinements[VIVY_MATERIALS_REFINEMENTS_METALLIC] if VIVY_MATERIALS_REFINEMENTS_METALLIC in json_refinements else None,
			glass=json_refinements[VIVY_MATERIALS_REFINEMENTS_GLASS] if VIVY_MATERIALS_REFINEMENTS_GLASS in json_refinements else None,
			fallback_s=json_refinements[VIVY_MATERIALS_REFINEMENTS_FALLBACK_S] if VIVY_MATERIALS_REFINEMENTS_FALLBACK_S in json_refinements else None,
			fallback_n=json_refinements[VIVY_MATERIALS_REFINEMENTS_FALLBACK_N] if VIVY_MATERIALS_REFINEMENTS_FALLBACK_N in json_refinements else None,
			fallback=json_refinements[VIVY_MATERIALS_REFINEMENTS_FALLBACK] if VIVY_MATERIALS_REFINEMENTS_FALLBACK in json_refinements else None
		)
	)

def json_vivy_material(mat: str) -> Dict:
	"""Return a Vivy material dictionary given a material name.

	This should not be used directly unless absolutely needed.
	
	Params:
		mat: str - Vivy material name

	Returns:
		Dict - Vivy material dictionary
	"""
	return env.vivy_material_json[VIVY_MATERIALS][mat]

def json_vivy_passes(mat: str) -> Dict:
	"""Return a set of passes of a given Vivy material
	
	This should not be used directly unless absolutely needed.
	
	Params:
	""	mat: str - Vivy material name

	Returns:
		Dict - Passes
	"""
	return json_vivy_material(mat)[VIVY_MATERIALS_PASSES]

def json_vivy_refinements(mat: str) -> Optional[Dict]:
	"""Return a set of refinements of a given Vivy material
	
	This should not be used directly unless absolutely needed.
	
	Params:
		mat: str - Vivy material name

	Returns:
		Dict - Refinements, if present
		None
	"""
	json_material = json_vivy_material(mat)
	return json_material[VIVY_MATERIALS_REFINEMENTS] if VIVY_MATERIALS_REFINEMENTS in json_material else None

def data_vivy_mappings(mat: str) -> List[VivyMapping]:
	"""Returns mapping data for a given Blender material

	Params:
		mat: str - Blender material name

	Returns:
		List[VivyMapping] - List of material mappings
	"""
	json_mappings = json_vivy_mappings(mat)
	
	data_mappings: List[VivyMapping] = []
	for mapping in json_mappings:
		data_mappings.append(VivyMapping(
								material=data_vivy_material(mapping[VIVY_MAPPING_MATERIAL]),
								refinement=mapping[VIVY_MAPPING_REFINEMENT] if VIVY_MAPPING_REFINEMENT in mapping else None
							))
	return data_mappings

def json_vivy_mappings(mat: str) -> List[Dict]:
	"""Returns all mappings for a given Blender material
		
	This should not be used directly unless absolutely needed.
	
	Params:
		mat: str - Blender material name

	Returns:
		List[Dict] - List of material mappings
	"""
	return env.vivy_material_json[VIVY_MAPPING][mat]

def json_vivy_version() -> int:
	"""Returns the version of the Vivy JSON format used by the library

	Returns:
		int - Vivy JSON format version
	"""
	return env.vivy_material_json[VIVY_VERSION]
