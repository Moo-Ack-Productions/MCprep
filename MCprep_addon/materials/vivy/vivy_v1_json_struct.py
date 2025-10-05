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

# This exists in order to make developer experience better,
# by explicitly declaring the structure of the JSON file
#
# Unlike the dataclasses used by Vivy, these are completely
# unsimplified, and solely exist for type checking purposes

import sys
from typing import Dict, List

# We want to use the standard library if we can,
# but for support in older Blender versions, we bundle
# an older version of typing_extensions, which backports
# older Python modules
if sys.version_info >= (3, 11):
	from typing import TypedDict, NotRequired
elif sys.version_info >= (3, 8) and sys.version_info < (3, 11):
	from typing import TypedDict
	from ...lib.typing_extensions import NotRequired
else:
	from ...lib.typing_extensions import TypedDict, NotRequired

class VivyPasses(TypedDict):
	diffuse: str
	normal: NotRequired[str]
	specular: NotRequired[str]

class VivyRefinements(TypedDict):
	emissive: NotRequired[str]
	reflection: NotRequired[str]
	metallic: NotRequired[str]
	glass: NotRequired[str]
	fallback_s: NotRequired[str]
	fallback_n: NotRequired[str]
	fallback: NotRequired[str]

class VivyMaterial(TypedDict):
	base_material: str
	desc: str
	passes: VivyPasses
	refinements: NotRequired[VivyRefinements]

class VivyMapping(TypedDict):
	material: str
	refinement: NotRequired[str]

class VivyJSON(TypedDict):
	version: int
	materials: Dict[str, VivyMaterial]
	mapping: Dict[str, List[VivyMapping]]
