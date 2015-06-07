TO INSTALL MCprep
======

[Go to the releases page and download the addon](https://github.com/TheDuckCow/MCprep/releases), it should remain a zip folder. In blender, go to preferences, then the addons tab, and at the bottom of the window install from file. Select the .zip file. **NOTE:** _Blender may not automatically enable the addon. If the MCprep addon is not already shown in the window after installing, search for it at left and then ensure the checkbox is enabled. Save user preferences to keep it enabled next time blender opens._

CREDIT
======
While this addon is released as open source software, the assets are being released as [Creative Commons Attributions, CC-BY](https://creativecommons.org/licenses/by/3.0/us/). If you use MeshSwap, **please credit the creators** by [linking to this page](https://github.com/TheDuckCow/MCprep) wherever your project may appear.

Models developed by [Patrick W. Crawford](https://twitter.com/TheDuckCow) and [SilverC16](https://twitter.com/SilverC16).

If you like the addon, [please consider donating](http://bit.ly/donate2TheDuckCow) for the continued quality development! [Share this addon](https://twitter.com/intent/tweet?text=Make+easier+Minecraft+renders+using+the+MCprep+addon+bit.ly/MCprep+by+@TheDuckCow) so others can benefit from it!

About MCprep
======

This is a blender python addon to increase workflow for creating Minecraft renders and animations, by automatically setting up better materials, importing library models and groups, and setting up proxy characters for animation and default animations for regular features like grass and leaves on imported 3D minecraft worlds. This addon assumes you have already imported the minecraft world. While the script should work for any world importer, it has been tested and developed based on the jmc2obj minecraft world to obj file converted.

The forum WIP thread for the development of this addon is found below, though now also out of date:
http://www.blenderartists.org/forum/showthread.php?316151-ADDON-WIP-MCprep-for-Minecraft-Workflow

This addon is made to work with an asset library directory, from which models and groups are linked or imported from. This library blend file is included, but does not have all types of blocks generated yet. This will be improved in the future.

This script is now compatible for both pre-2.71 (tested down to 2.69) and for 2.72+ official builds, up to blender 2.74.

Demo Usage
======

[Video demo of the addon:](https://www.youtube.com/watch?v=Nax7iuCTovk)

[![Alt text](/referenceThumnail.png?raw=true "Video Preview")](https://www.youtube.com/watch?v=Nax7iuCTovk)

Older video demos:
- [Cycles Materials Upate (most recent)](https://www.youtube.com/watch?v=MRuPRnfdzfI)
- https://www.facebook.com/photo.php?v=737273036339269&l=2318416360725689976
- https://www.youtube.com/watch?v=Swz6T4Zzfek

How to use this addon
======

**Setup materials:**
- **Purpose:** To automatically setup better, crisp materials for rendering Minecraft, low resolution textures. It works for both Blender internal as well as cycles. It will even selectively turn 'shiny' materials into reflecting materials accordingly as well as 'bright' materials into emitting materials. Currently, the list of these materials is hardcoded in.
- **Step 1:** Export your world to an OBJ or other general 3D formats. I use jmc2obj, but Mineways or other such formats should be fine as well.
- **Step 2:** Import the world into blender (e.g. via file > import > obj, or whatever according format)
- **Step 3:** Select all, or select the objects that have the material you want to fix. Materials can be all separate objects or the same object, it does not matter.
- **Step 4:** Under the MCprep panl, press "Prep Materials".

**Meshswap:**
- **Purpose:** To automatically swap in extra assets such as 3D grass, light emitting torches and lamps, and so forth. Note that all the objects to be swapped in are in the blend file part of this download. Also note that swapping is done based on the name of the material. If you are unsure why your object is not swapping in, check the material name matches the counterpart object/material in the meshSwap.blend file. Note it can search for both appendable objects as well as groups, containing particles and so forth. Modifiers on the mesh in the original file will be brought over, so notice for example how the tall grass when replaced will be "pre-simulated" as it has displacement modifiers setup already with animation.
- **Step 0:** Set the MeshSwap blend path to the "mcprep_meshSwap.blend" or custom blend file, and make sure the world export has blocks of size 1m (100cm).
- **Step 1:** Select the objects that you wish to be meshSwapped. Swappable objects are determined *automatically* based on the contents of the blend file selected above. If an object is not found or swappable, it will just be skipped - no harm done by "overselecting" (so select all objects to make sure everything that can be swapped gets swapped!)
- **Step 2:** Press Mesh Swap (there will be a small delay, meshswapping large areas such as fields of grass may take awhile).

To add your own objects to meshswap (or groupswap):
- **Step 1:** Check your imported world object and see the name of the material for the object you want to setup. You might think it is "glass plane", but if the importer names the material "glass_plane", you need to note this name down for step 3.
- **Step 2:** Model you object in the mcprep_meshSwap.blend file, or append it.
- **Step 3:** Rename your object to exactly match the previously noted material name. If you want to have a group swappable, then name the group to match the name above.  
  * So the MATERIAL name found in the 3D imported world should match the OBJECT name of the model in the meshswap file to work  
  * Note if both a group and an object have matching names, the script will prefer the group and meswap that over the object.  
- **Step 4:** Add necessary properties to special blocks as needed. See the meshSwap file included for examples, but the properties to add are:  
  * "varaince": Objects with this property when meshswapped will have some x/y variance added. If the property is set to 1, it will also have (only negative) z variance. If it is set to 0, it will only have xy variance. For instance, tall_grass is given a value of 1 so some grass is shorter than others, but flowers are given a value of 0 so they always have the same height but still have some variance in placement.
  * "edgeFloat": objects like vines, ladders, and lillypads which float off the edge of other blocks.  
  * "tochlike": objects that can have rotations like a torch on a wall. Objects with this property will be determined to be either on top of a block or placed on the side of another block according to the mesh.
  * **Note:** there is no UI for adding properties to a group, so if you want to add a property to a group (say a torch which has a pre-animated light and particle system, as the included blend file does) you must go into the python consol and add the property like so:  <code>bpy.data.groups['groupName']['propertyName'] = 1</code>  (the value only matters for the variance property)
  * **Example:** <code>bpy.data.groups['torch']['torchlike'] = 1</code> will add the torchlike property to the torch group, allowing it to have correct rotaitons when meshSwapped in.


Known Bugs
======
- SOMETIMES UNDO (control/command z) MAY CRASH AFTER MESHSWAPPING, recommended to save before using to be safe but generally is fine.
- Currently assumes that the block size is 1x1x1, note that by default Mineways has a block size 0.1x0.1x0.1, please set it to 1m or 100cm on export or use the upscale function.
- **Both mineways and jmc2obj oddities:**
  - Redstone items like repeaters, dust, and so forth generally don't swap properly, and is a much more difficult problem to solve.
  - Rails: for jmc2obj, all rails should at least be placed in the correct position, but not necessarily rotated correctly.
  - Some materials such as fire are pre-setup with animated image sequences (yay!), but blender cannot pack image sequences into a blend file. If aniamted textures go missing (e.g. after moving a blend file around), reconnect them back to the according folder/file, such as /textures/fire/fire_0001.png. Note this should not be a problem if the default meshwap path/file is used, provided the addon is not uninstalled.
- **Mineways specific meshswap oddities:**
  - Mineways, unlike jmc2obj, replaces the face of a solid block with the object attached to it. For example, ladders and redstone dust when meshswapped will leave a hole in the block they were attached to. There is essentially nothing I can do about that.
  - In Mineways, many blocks simply cannot be meshswapped because of the way the exporter will group multiple objects (for example, all the flowers) into one material. For the time being, there is nothing I can do to resolve this.
  - lilypads end up rotated and in block next to where they should be
  - Torhes: all work fine, expect for one direction of a torch placed on a way (will be placed in the correct air space but oriented as if it were placed on top of a block and not on the side of one)


Future Plans
======
- Create a "solidify pixels" operator, where single-faced planes are converted into properly subdivided and extruded 3D planes according to the active texture, removing transparent areas accordingly. Should be able to apply to arbitrary objects
- Continue adding mroe blocks for meshswapping
- Add the ability to shift-A add objects in the library like other objects, not just via meshswapping
- Create a "match external material" operator, where all materials in the set of selected objects are checked against an external library, and if any have matching names, the external material will overwrite the local one. This would allow one to quickly cycles between different styles, e.g. texture packs.
- Create a "Spawn Rig" button, working for both linked rigs as well as appended rigs. Have built-in, self included rigs for animating and the option to install additional rigs. Involve the community on this one!


Additional Help
======

If you have troubles getting this addon to work, please contact me at support@TheDuckCow.com or [on twitter](https://twitter.com/TheDuckCow), and I will do my best to respond promptly to your questions. This addon is still heavily under construction, so check back for updates (you can reference the version number and take last modified). Your feedback helps stabilize the addon and make it work better for everyone else!

Moo-Ack!