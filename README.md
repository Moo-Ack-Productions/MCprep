MCprep
======

This is a blender python addon to increase workflow for creating Minecraft renders and animations, by automatically setting up better materials, importing library models and groups, and setting up proxy characters for animation and default animations for regular features like grass and leaves on imported 3D minecraft worlds. This addon assumes you have already imported the minecraft world. While the script should work for any world importer, it has been tested and developed based on the jmc2obj minecraft world to obj file converted.

The forum WIP thread for the development of this addon is found below, though now also out of date:
http://www.blenderartists.org/forum/showthread.php?316151-ADDON-WIP-MCprep-for-Minecraft-Workflow

This addon is made to work with an asset library directory, from which models and groups are linked or imported from. This library blend file is included, but does not have all types of blocks generated yet. This will be improved in the future.

This script is now compatible for both pre-2.71 (tested down to 2.69) and for 2.72+ official builds.

Demo Usage
======

[Video demo of the addon:](https://www.youtube.com/watch?v=Nax7iuCTovk)

[![Alt text](/referenceThumnail.png?raw=true "Video Preview")](https://www.youtube.com/watch?v=Nax7iuCTovk)

Older video demos:
- https://www.facebook.com/photo.php?v=737273036339269&l=2318416360725689976
- https://www.youtube.com/watch?v=Swz6T4Zzfek

How to use this addon
======

Setup materials:
- Purpose: To automatically setup better, crisp materials for rendering Minecraft, low resolution textures
- Step 1: Export your world to an OBJ or other general 3D formats. I use jmc2obj, but Mineways or other such formats should be fine as well.
- Step 2: Import the world into blender (e.g. via file > import > obj, or whatever according format)
- Step 3: Select all, or select the objects that have the material you want to fix. Materials can be all separate objects or the same object, it does not matter.
- Step 4: Under the MCprep panl, press "Prep Materials". Note that reflections and emit values are added to materials matching hard-coded names. In the future, it will also search for matching materials in the materials blend path and use this instead of the default setup hard-coded.

Meshswap:
- **Purpose:** To automatically swap in extra assets such as 3D grass, light emitting torches and lamps, and so forth. Note that all the objects to be swapped in are in the blend file part of this download. Also note that swapping is done based on the name of the material. If you are unsure why your object is not swapping in, check the material name matches the counterpart object/material in the meshSwap.blend file. Note it can search for both appendable objects as well as groups, containing particles and so forth. Modifiers on the mesh in the original file will be brought over, so notice for example how the tall grass when replaced will be "pre-simulated" as it has displacement modifiers setup already with animation.
- **Step 0:** Set the MeshSwap blend path to the "asset_meshSwap.blend" or custom blend file.
- **Step 1:** Select the objects that you wish to be meshSwapped. Swappable objects are determined *automatically* based on the contents of the blend file selected above. If an object is not found or swappable, it will just be skipped - no harm done by "overselecting" (so select all objects to make sure everything that can be swapped gets swapped!)
- **Step 2:** Press Mesh Swap.

To add your own objects to meshswap (or groupswap):
- **Step 1:** Check your imported world object and see the name of the material for the object you want to setup. You might think it is "glass plane", but if the importer names the material "glass_plane", you need to note this name down for step 3.
- **Step 2:** Model you object in the meshSwap.blend file, or append it.
- **Step 3:** Rename your object to exactly match the previously noted name. If you want to have a group swappable, then name the group to match the name above.
..* So the MATERIAL name as in the 3D imported world should match the OBJECT name of the model in the meshswap file to work
..* Note if both a group and an object have matching names, the script will prefer the group and meswap that over the object.
- **Step 4:** Add necessary properties to special blocks as needed. See the meshSwap file included for examples, but the properties to add are:
..* "varaince": Objects with this property when meshswapped will have some x/y variance added. If the property is set to 1, it will also have (only negative) z variance. If it is set to 0, it will only have xy variance.
..* "edgeFloat": objects like vines, ladders, and lillypads which float off the edge of other blocks. 
..* "tochlike": objects that can have rotations like a torch on a wall. Objects with this property will be determined to be either on top of a block or placed on the side of another block according to the mesh.
..* Note: there is no UI for adding properties to a group, so if you want to add a property to a group (say a torch which has a pre-animated light and particle system, as the included blend file does) you must go into python and add the property like so: bpy.groups['groupName']['propertyName'] = 1/0 (the value only matters for the variance property)
..* Example: bpy.groups['torch']['torchlike'] = 1 will add the torchlike property to the torch group, allowing it to have correct rotaitons when meshSwapped in.


Known Bugs
======
- SOMETIMES UNDO (control/command z) MAY CRASH AFTER MESHSWAPPING, recommended to save before using to be safe but generally is fine.
- Weird rotations of the set will cause meshswapping to not have the intended result. However, any scale or (global) translations goes!
- The local coordiantes (edit-mode) of the mesh *must* have it's geometry centered on whole integers. That is, the center of a block (not it's base or side) should have a coordiante of x=#.000, y=#.00, z=#.00; imported from jmc2obj will be fine!
- The Materials blend does nothing yet. Working on it! Ultiamtely will let you have a library of materials to swap in.


Additional Help
======

If you have troubles getting this addon to work, please contact me at TheDuckCow@live.com, and I will do my best to respond promptly to your questions. This addon is still heavily under construction, so check back for updates (you can reference the version number and take last modified). Your feedback helps stabilize the addon and work better for everyone else!

Moo-Ack!
