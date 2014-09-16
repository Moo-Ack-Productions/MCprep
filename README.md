MCprep
======

This is a blender python addon to increase workflow for creating Minecraft renders and animations, by automatically setting up better materials, importing library models and groups, and setting up proxy characters for animation and default animations for regular features like grass and leaves.

The forum WIP thread for the development of this addon is found below, though now also out of date:
http://www.blenderartists.org/forum/showthread.php?316151-ADDON-WIP-MCprep-for-Minecraft-Workflow

This addon is made to work with an asset library directory, from which models and groups are linked or imported from. A version of this library is being set up still for others to use.

Demo Usage
======

With a currently lacking usage documentation, the video will show what the intended results of this script are:
https://www.facebook.com/photo.php?v=737273036339269&l=2318416360725689976
(Older, shows more than grass)
https://www.youtube.com/watch?v=Swz6T4Zzfek

How to use this addon
======

Setup materials:
- Purpose: To automatically setup better, crisp materials for rendering Minecraft, low resolution textures
- Step 1: I use jmc2obj, but Mineways or other such formats should be fine as well
- Step 2: Import the world into blender (e.g. via import>obj)
- Step 3: Select all, or select the objects that have the material you want. Materials can be all separate objects on the same object, it does not matter
- Step 4: Under the MCprep panl, press "Prep Materials"

Meshswap:
- Purpose: To automatically swap in extra assets such as 3D grass, light emitting torches and lamps, and so forth. Note that all the objects to be swapped in are in the blend file part of this download. Also note that swapping is done based on the name of the material. If you are unsure why your object is not swapping in, check the material name matches the counterpart object/material in the meshSwap.blend file. Note it can search for both appendable objects as well as groups, containing particles and so forth. Modifiers on the mesh in the original file will be brought over, so notice for example how the tall grass when replaced will be "pre-simulated" as it has displacement modifiers setup already with animation.
- Step 1: Select the objects that can be meshSwapped. Note: I have not added direct functionality for adding more swappable object. Also note that if an object is not found or swappable, it will just be skipped - no harm done.
- Step 2: Press meshswap.

To add your own objects to meshswap (or groupswap):
- Step 0: Uninstall the MCprep addon if it is there already.
- Step 1: Check your imported world (e.g. , and see the name of the material for the object you want to setup. You might call it "glass plane", but the import might name the material "glass_plane", so you need to note that.
- Step 2: Model you object in the meshSwap.blend file, or append it.
- Step 3: Rename your object and your object's material to exactly match the previously noted name.
- Step 4: In the *code*, meshswap.py file, look for "def getListData():" on line 48 currently, a get funciton.
- Step 5: Add the exact name of your new object to the list "meshSwapList" (or "groupSwapList", if it is a group with that exact name to bring in particles/multiple objects, etc), use single quotes around it and commas between entires like the other entries of that list.
- Step 6: Reinstall the addon.


Known Bugs
======
- if multiple objects with same material mesh swapped in one go easy work around would be to auto join them together, but should be error'd...
- not all replacements for standard block replacements work, extra blocks appear
- sometimes cannot meshswap a second time if done once in a scene already, e.g. vine appears to be due to stale, or kept data between op runs.



Additional Help
======

If you have troubles getting this addon to work, please contact me at TheDuckCow@live.com, and I will do my best to respond promptly to your questions. This addon is still heavily under construction, so this description may be out of date or largely incomplete.

Moo-Ack!
