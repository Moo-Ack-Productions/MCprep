### Utilities (util.py)

**apply_colorspace(node, color_enum)**

Apply colorspace on a node (eg: Image Texture) with cross version compability

**nameGeneralize(name)**

Return the base name of a datablock without any number extension.

**materialsFromObj(obj_list)**

Returns a list of materials from object list.

**bAppendLink(directory, name, toLink, active_layer=True)**

`directory` a path to xyz.blend/Type, where Type is: Collection, Group, Material.

`name` asset name

`toLink` bool

Returns true if successful, false if not

**obj_copy(base, context=None, vertex_groups=True, modifiers=True)**

`base` object need to be duplicate must be valid

`context` use the active context

`vertex_groups` copy the vertex groups

`modifiers` copy the modifiers

Returns that new copy object.

**min_bv(version, \*, inclusive=True)**

 

 If `inclusive` is 

 true returns true if the result of current Blender is equal to `version`,

 false returns false unless current Blender is higher than `version`

 

**bv28()**

 Check for version is 2.8, sees `min_bv()`

**bv30()**

 Check for version is 3.0, sees `min_bv()`

 

**is_atlas_export(context)**

Check if the selected objects are valid for textureswap/animated texture. Due to Mineways has a big texture atlas option.

Returns a bool. If false, the UI will show a warning and link to doc

  about using the right settings.

** face_on_edge(faceloc)**

  Check if a face is on the boundary between two blocks in local coordinates

  Returns a bool.

**ramdomizeMeshsawp(swap, variations)**

Randomization for model imports, add extra statements for exta cases (eg: torch -> torch.1)

`swap` a string of a block

`variations` a integer seed

	

**duplicatedDatablock(name)**

Returns true if datablock is a duplicate or not, e.g. ending in .00#

	

**loadTexture(texture)**

Returns a texture. Load a texture from its path once, reusing existing texture if present.

  

**remap_users(old, new)** (D2.78)



Remap user datablock 

**get_objects_conext(context)**

	

Returns list of objects, either from view layer or scene for 2.8

	

**open_program(executable)**

Open external program from path 

returns 0 if success else string "Error"

	

**open_folder_crossplatform(folder)**

Open folder crossplatform return a bool if open successful

  

**addGroupInstance(group_name, loc, select=True)**

Create a collection instance object. Returns that object.

**load_mcprep_json()**

Load in the json file. Returns a bool if successful

```

    {

			"blocks": {

				"reflective": [],

				"water": [],

				"solid": [],

				"emit": [],

				"desaturated": [],

				"animated": [],

				"block_mapping_mc": {},

				"block_mapping_jmc": {},

				"block_mapping_mineways": {},

				"canon_mapping_block": {}

			},

			"mob_skip_prep": [],

			"make_real": []
}

```

**ui_scale()**

  Returns the UI Scale

**uv_select(obj, action='TOGGLE')**

Select all UV verts of an object on 1 uv layer.

`action` (Optional) SELECT, DESELECT, TOGGLE.

**move_to_collection(obj, collection)** (2.8+)

Move object out of collects into sepcify collection.

**get_or_create_viewlayer(context: Context, collection_name: str)** (2.8+)

Returns or creates collection in the active context view layer for a given name.

	

**natural_sort(elements)**

Returns a sorted list 

**make_annotations(cls):

Add annotation attribute to class fields to avoid Blender 2.8 warnings

**layout_split(layout, factor=0.0, align=False)**

	
Split UI for 2.8+ and below compability

	

**get_user_preferences(context=None)**

	

Returns user preferences for 2.8+ and below compability else None

	

**get_preferences(context=None)**

	

Returns user preferences compability in more friendly way. See `get_user_preferences()`

	

**set_active_object(context, obj)**

	

Set the active object with 2.8+ and below compability

	

**select_get(obj)**

	

Returns a bool of object is selected with multiversion compability

	

**select_set(obj, state)**

Set bool selection `state` of object with multiversion compability

	

**hide_viewport(obj, state)**

Set the object viewport hide `state` with multiversion compability

	

**collections()**

	

Returns a list of collection 

	

**viewport_textured(context=None)**

	

Returns if viewport solid is textured else None 

	

**get_cuser_location(context=None)**

Returns the location vector of the 3D cursor else `(0,0,0)``

	

**set_cuser_location(loc, context=None)**

	

Set the location vector of the 3D cursor

	

**instance_collection(obj)**

	

Get the collection of instance collection object

	

**obj_link_scene(obj, context=None)**

	

Links object to scene or scene master collection

	

**obj_unlink_remove(obj, remove, context=None)**

	

Unlink an object from the scene, and remove the datablock if `remove` is true 

	

**users_collection(obj)**

	
Returns the collections of an object

	

**matmul(v1, v2, v3=None)**

Return multiplciation of matrix and/or vectors in cross compatible way. v1 @ v2 

	

**scene_update(context=None)**

	

Update scene, despgraph in cross compatible way

	

**move_assets_to_excluded_layer(context, collections)**

Move collections not to rendered to an excluded collection if not exist, create

	