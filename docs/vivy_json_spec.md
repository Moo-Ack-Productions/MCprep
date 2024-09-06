# Vivy JSON Spec

This file defines the Vivy JSON spec for reference purposes.

A Vivy JSON file may be defined as follows
```json
{
  "materials": 
    {
      "PBR": {
	"base_material": "PBR", 
	"desc": "PBR material", 
	"passes": {
	  "diffuse": "Diffuse", 
	  "normal": "Normal", 
	  "specular": "Specular"
	}, 
      "refinements": {
	"emissive": "BPR_Emit", 
	"fallback": "Simple"
      }
    }, 
    "Simple": {
      "base_material": "Simple", 
      "desc": "Simple Material", 
      "passes": {
	"diffuse": "Diffuse"
      }
    }
  }, 

  "mapping": {
    "PBR": [{
	"material": "PBR"
      }], 
    "Simple": [
      { "material": "Simple" }, 
      { 
	"material": "PBR", 
	"refinement": "fallback"
      }
    ], 
    "BPR_Emit": [{
	"material": "PBR", 
	"refinement": "emissive"
      }]
  }
}
```

- `materials` - A dictionaty of Vivy materials. Each key represents the Vivy-side name of the material.
  - `base_material` - Blender-side name of the material
  - `desc` - Description of the material to show in the UI
  - `passes` - A dictionary of different pass types mapped to the node names of the image node containing the pass
    - `diffuse` - Diffuse pass
    - `specular` - Specular pass
    - `normal` - Normal pass
  - `refinements` - Specialized sub-materials to use with certain groupings. They're applied in the following order:
    - `emit` - Emissive materials
    - `reflective` - Reflective materials
    - `metallic` - Metallic materials
    - `glass` - Glass/transmissive materials
    - `fallback_s` - Fallback material to use when no specular pass is defined
    - `fallback_n` - Fallback material to use when no normal pass is defined
    - `fallback` - Fallback material if no extra passes are defined
- `mappings` - Mappings of Blender-side materials to lists containing mappings
  - `material` - Material of a given mapping
  - `refinement` - If defined, then the material being mapped to is a refinement of `material`. Otherwise, the material being mapped is `material`
