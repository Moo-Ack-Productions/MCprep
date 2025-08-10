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

from os import name
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import auto, Enum

from ...conf import env
from . import vivy_v2_json_struct as vjs

# Constants for JSON keys
VIVY_VERSION					= "version"
VIVY_AUTHORING_SOFTWARE			= "authoring_software"

# Material declarations
VIVY_MATERIAL_DECLARATIONS					= "material_declarations"
VIVY_MATERIAL_DECLARATIONS_DESC					= "desc"
VIVY_MATERIAL_DECLARATIONS_PASSES				= "passes"
VIVY_MATERIAL_DECLARATIONS_PASSES_DIFFUSE			= "diffuse"
VIVY_MATERIAL_DECLARATIONS_PASSES_SPECULAR			= "specular"
VIVY_MATERIAL_DECLARATIONS_PASSES_NORMAL			= "normal"
VIVY_MATERIAL_DECLARATIONS_PASSES_INHERIT			= "inherit"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS			= "refinements"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_EMISSIVE		= "emissive"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_REFLECTIVE	= "reflective"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_METALLIC		= "metallic"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_GLASS		= "glass"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_FALLBACK_S	= "fallback_s"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_FALLBACK_N	= "fallback_n"
VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_FALLBACK		= "fallback"
VIVY_MATERIAL_DECLARATIONS_PARENT					= "parent"

# Material definitions
VIVY_MATERIAL_DEFINITIONS					=	"material_definitions"
VIVY_MATERIAL_DEFINITIONS_NODE_TYPE				= "node_type"
VIVY_MATERIAL_DEFINITIONS_CONNECTIONS			= "connections"
VIVY_MATERIAL_DEFINITIONS_OUTPUTS				= "outputs"

# This defines how many time in a chain
# can passes be inherited. The limit is
# just to make sure people don't go crazy
# and cause the system to run out of memory
PASS_RESOLVER_DEPTH_LIMIT = 10

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

# Dummy class to represent inherited stuff,
# will be replaced at runtime when parents
# are checked
class VivyInherit:
	pass

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
class VivyParent:
	parent_name: str
	relation: str

@dataclass
class VivyMaterialDeclaration:
	desc: str 
	passes: VivyPasses
	refinements: Optional[VivyRefinements]
	parent: Optional[List[VivyParent]]

@dataclass
class VivyDefinitionNode:
	node_name: str
	node_type: str
	connections: Dict[str, str]
	outputs: List[str]

@dataclass
class VivyMaterialDefinition:
	nodes: List[VivyDefinitionNode]

# Error handling
class VivyCompErrorType(Enum):
	INVALID_VALUE = auto()
	CANT_INHERIT = auto()
	PASS_DEPTH_LIMIT = auto()

	# For stuff that shouldn't
	# happen unless there's a
	# bug somewhere
	WTF_ERROR = auto()

@dataclass
class VivyCompError:
	msg: str
	err_type: VivyCompErrorType

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

def data_vivy_material(mat: str) -> Union[Tuple[VivyMaterialDeclaration, VivyMaterialDefinition], VivyCompError]:
	"""Get Vivy material data from a given material name.
	This will give both the declaration and the definiton.
	
	Params:
		mat: str - Vivy material name

	Returns:
		VivyMaterial - Vivy material data for mat
	"""
	json_material_declaration, json_material_definition = json_vivy_material(mat)
	json_passes = json_vivy_passes(mat)
	json_refinements = json_vivy_refinements(mat)
	json_parent = json_vivy_parent(mat)
	
	data_parent = None
	if json_parent:
		data_parent = data_vivy_parent(json_parent)

	data_pass = data_vivy_passes(json_passes)
	if isinstance(data_pass, VivyCompError):
		return data_pass
	elif isinstance(data_pass, VivyInherit):
		if not data_parent:
			return VivyCompError(
				msg="Must have a parent in order to inherit passes!",
				err_type=VivyCompErrorType.CANT_INHERIT
			)
		data_pass = data_vivy_resolve_parent_passes(data_parent)
		if isinstance(data_pass, VivyCompError):
			return data_pass
		
	data_refinements = None
	if json_refinements:
		data_refinements = data_vivy_refinements(json_refinements)

	data_declaration = VivyMaterialDeclaration(
		desc=json_material_declaration[VIVY_MATERIAL_DECLARATIONS_DESC],
		passes=data_pass,
		refinements=data_refinements,
		parent=data_parent
	)
	
	data_nodes: List[VivyDefinitionNode] = []
	for node_name, node_struct in json_material_definition:
		data_nodes.append(data_vivy_node_definition(node_name, node_struct))

	data_definition = VivyMaterialDefinition(nodes=data_nodes)

	return (data_declaration, data_definition)

def data_vivy_resolve_parent_passes(parent_data: List[VivyParent], depth: int = 1) -> Union[VivyPasses, VivyCompError]:
	"""Resolve the passes of a material's parent(s). This is for pass inheritance.

	Params:
		parent_data: List[VivyParent] - The parents of the material in question
		depth: int (default = 1) - The current depth, used to enforce a depth limit with recursion

	Returns:
		VivyPasses - The resolved passes
		VivyCompError - If an error occurs during pass resolution
	"""
	if depth == PASS_RESOLVER_DEPTH_LIMIT:
		return VivyCompError(
			msg="Reached the max depth limit for resolving passes",
			err_type=VivyCompErrorType.PASS_DEPTH_LIMIT
		)
	parent_passes: List[VivyPasses] = []
	for parent in parent_data:
		pass_json = json_vivy_passes(parent.parent_name)
		pass_data = data_vivy_passes(pass_json)

		if isinstance(pass_data, VivyCompError):
			return pass_data
		elif isinstance(pass_data, VivyInherit):
			parent_json = json_vivy_parent(parent.parent_name)
			if not parent_json:
				return VivyCompError(
					msg="Inheritance requires having a parent material",
					err_type=VivyCompErrorType.CANT_INHERIT
				)
			parent_data = data_vivy_parent(parent_json)
			final_pass = data_vivy_resolve_parent_passes(parent_data, depth + 1)
			if isinstance(final_pass, VivyCompError):
				return final_pass
			parent_passes.append(final_pass)
		else:
			parent_passes.append(pass_data)
	assert all(isinstance(p, VivyPasses) for p in parent_passes)
	parent_pass_set = set(parent_passes)

	if len(parent_pass_set) > 1:
		return VivyCompError(
			msg="Inheritance requires all parent materials to have the same passes",
			err_type=VivyCompErrorType.CANT_INHERIT
		)
	elif len(parent_pass_set) < 1:
		return VivyCompError(
			msg="This should not happen, please report to the MCprep GitHub!",
			err_type=VivyCompErrorType.WTF_ERROR
		)

	# If the set has a length
	# of 1, that means everything
	# in the list was the same, so
	# we can safely take the first
	# value
	return parent_passes[0]

def data_vivy_passes(pass_json: Union[vjs.VivyPasses, str]) -> Union[VivyPasses, VivyInherit, VivyCompError]:
	"""Given the JSON value for material_declarations.passes, return the
	data version

	Params:
		pass_json: Union[Dict, str] - Either the Vivy Pass JSON or the inherit keyword

	Returns:
		VivyPasses - Pass data
		VivyInherit - Dummy class for inheritance
		VivyCompError - Error
	"""
	if isinstance(pass_json, str) and pass_json == VIVY_MATERIAL_DECLARATIONS_PASSES_INHERIT:
		return VivyInherit()
	elif isinstance(pass_json, Dict):
		return VivyPasses(
			diffuse=pass_json[VIVY_MATERIAL_DECLARATIONS_PASSES_DIFFUSE],
			specular=pass_json.get(VIVY_MATERIAL_DECLARATIONS_PASSES_SPECULAR, None),
			normal=pass_json.get(VIVY_MATERIAL_DECLARATIONS_PASSES_NORMAL, None)
		)
	return VivyCompError(
		msg="material_declarations.passes must be either a dictionary with at least a diffuse pass, or the keyword inherit",
		err_type=VivyCompErrorType.INVALID_VALUE
	)

def data_vivy_parent(parent_json: Dict[str, str]) -> List[VivyParent]:
	"""Turn a parent JSON definition into a list of parents

	Params:
		parent_json: Dict[str, str] - The raw JSON defining the parents
	
	Returns:
		List[VivyParent] - List of parents
	"""
	parents = []
	for key, value in parent_json.items():
		parents.append(VivyParent(
			parent_name=key,
			relation=value
		))
	return parents

def data_vivy_refinements(refinement_json: vjs.VivyRefinements) -> VivyRefinements:
	"""Turn a refinement JSON into a dataclass

	Params:
		refinement_json: Dict[str, str] - The raw JSON defining the refinements
	
	Returns:
		VivyRefinements - Dataclass representing the refinements structure
	"""
	return VivyRefinements(
		emissive=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_EMISSIVE, None),
		reflective=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_REFLECTIVE, None),
		metallic=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_METALLIC, None),
		glass=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_GLASS, None),
		fallback_n=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_FALLBACK_N, None),
		fallback_s=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_FALLBACK_S, None),
		fallback=refinement_json.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS_FALLBACK, None)
	)

def data_vivy_node_definition(name: str, node_json: vjs.VivyNodeDefinition) -> VivyDefinitionNode:
	"""Turn a JSON node definition into a dataclass
	
	Params:
		name: str - The name of the node
		node_json: Dict - The raw JSON of the node

	Returns:
		VivyDefinitionNode - Dataclass representing the node
	"""

	return VivyDefinitionNode(
		node_name=name,
		node_type=node_json[VIVY_MATERIAL_DEFINITIONS_NODE_TYPE],
		connections=node_json[VIVY_MATERIAL_DEFINITIONS_CONNECTIONS],
		outputs=node_json[VIVY_MATERIAL_DEFINITIONS_OUTPUTS]
	)

def json_vivy_material(mat: str) -> Tuple[vjs.VivyMaterialDeclaration, Dict[str, List[vjs.VivyNodeDefinition]]]:
	"""Return a Vivy material dictionary given a material name.
	This gives a tuple of both the declarations and definitions

	This should not be used directly unless absolutely needed.
	
	Params:
		mat: str - Vivy material name

	Returns:
		Dict - Vivy material dictionary
	"""
	return env.vivy_material_json[VIVY_MATERIAL_DECLARATIONS][mat], env.vivy_material_json[VIVY_MATERIAL_DEFINITIONS][mat]

def json_vivy_passes(mat: str) -> Union[vjs.VivyPasses, str]:
	"""Return a set of passes of a given Vivy material
	
	This should not be used directly unless absolutely needed.
	
	Params:
	""	mat: str - Vivy material name

	Returns:
		Dict - Passes
	"""
	return json_vivy_material(mat)[0][VIVY_MATERIAL_DECLARATIONS_PASSES]

def json_vivy_refinements(mat: str) -> Optional[vjs.VivyRefinements]:
	"""Return a set of refinements of a given Vivy material
	
	This should not be used directly unless absolutely needed.
	
	Params:
		mat: str - Vivy material name

	Returns:
		Dict - Refinements, if present
		None
	"""
	json_material, _ = json_vivy_material(mat)
	return json_material.get(VIVY_MATERIAL_DECLARATIONS_REFINEMENTS, None)

def json_vivy_parent(mat: str) -> Optional[Dict[str, str]]:
	"""Returns the parents of a material, if they are defined
	
	Params:
		mat: str - Vivy material name

	Returns:
		Dict - Parents, if present
		None
	"""
	json_material, _ = json_vivy_material(mat)
	return json_material.get(VIVY_MATERIAL_DECLARATIONS_PARENT, None)

def json_vivy_version() -> int:
	"""Returns the version of the Vivy JSON format used by the library

	Returns:
		int - Vivy JSON format version
	"""
	return env.vivy_material_json[VIVY_VERSION]
