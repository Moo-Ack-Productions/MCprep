
MCprep Addon
======
[![Discord](https://badgen.net/badge/icon/discord?icon=discord&label)](https://discord.gg/mb8hBUC)
[![MCprep License](https://img.shields.io/github/license/TheDuckCow/MCprep)](https://www.gnu.org/licenses/gpl-3.0)
![MCprep Stars](https://img.shields.io/github/stars/TheDuckCow/MCprep)
[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/TheDuckCow/MCprep/blob/master/CONTRIBUTING.md)

MCprep is an addon dedicated to speeding up the workflow of Minecraft animators in Blender by automatically fixing up materials and providing other tools such as mob spawing, effects spawning, etc. 

## Installing MCprep
### Click the link below and download the .zip file (re-zip if auto-unzipped into a folder necessary), install into blender (2.80 through 4.0 supported)

**Note: To use MCprep with assets, you must have a valid, legal copy of Minecraft to comply with Mojang's terms of service. No support is provided for anyone using MCprep without a valid Minecraft license** Versions of MCprep without the assets are not bound to this requirement

[![Install MCprep](/visuals/mcprep_download.png)](https://theduckcow.com/dev/blender/mcprep-download/)

*By downloading and installing, you agree to the following [privacy policy](https://theduckcow.com/privacy-policy).* **[Watch this video](https://www.youtube.com/watch?v=i6Ne07-eIyI) on how to install if running into troubles.**


It should remain a zip folder. In blender, go to preferences, then the addons tab, and at the bottom of the window install from file. Select the .zip file. **NOTE:** _Blender may not automatically enable the addon. If the MCprep addon is not already shown in the window after installing, search for it at left and then ensure the check box is enabled._ **Save user preferences** to keep it enabled next time blender opens.

*Again, please download from the link above or the releases page, __not__ by clicking `download zip` button above.*

![Installed MCprep 2.8](/visuals/install_28.png?raw=true)

**If you like the addon, [please consider donating](http://bit.ly/donate2TheDuckCow) for the continued quality development! [Share this addon](https://twitter.com/intent/tweet?text=Make+easier+Minecraft+renders+using+the+MCprep+addon+bit.ly/MCprep+by+@TheDuckCow) so others can benefit from it! Or help by [taking this quick survey](http://bit.ly/MCprepSurvey)!**


Learn how to use MCprep
======

*[Short, 1-minute videos showcasing how to use Blender+MCprep features](https://bit.ly/MCprepTutorials)*

[![Tutorial playlist](https://img.youtube.com/vi/62fVXVAO13A/0.jpg)](https://bit.ly/MCprepTutorials)

*[Additional Playlist of MCprep videos/demos](https://www.youtube.com/playlist?list=PL8X_CzUEVBfaajwyguIj_utPXO4tEOr7a)*


About MCprep
======

This is a blender python addon to improve and automate many aspects of creating Minecraft renders and animations. It can help you improt world's exported from Minecraft, set up better materials, importing mobs and items, and set up proxy characters for animation, and even includes default animations for common blocks/mobs like tall grass, torches, and mobs like the bat or blaze. This addon assumes you have already exported a Minecraft world to an OBJ file. While the script should work for any world importer, it has been tested and developed based on the jmc2obj and Mineways tools for exporting Minecraft worlds to obj files.

This addon is made to work with an asset library directory, from which models and groups are linked or imported from. This library blend file is included, but does not have all types of blocks generated yet. This will be improved in the future.

This addon is compatible officially down to 2.72 official builds, and up to blender 3.00. Not all features are available in all versions, try to use the latest available blender. *Run into any problems? [Submit bugs/issues here](https://github.com/TheDuckCow/MCprep/issues).*


Feature list
======

| World Imports   |      Description      |
|----------|:-------------:|
| Prep Materials | Improves materials from world imports, and allows one-click switching from cycles & blender internal materials. *Note, this does not* create *materials, only modifies existing ones.* |
| Swap Texture Pack | *Initial support only for jmc2obj world exports.* Using a valid Minecraft resource pack, you can now completely replace the textures of the imported world with another pack - you can even changed individual blocks at a time. |
| Animate textures | *Initial support only for jmc2obj world exports.* With a valid (or the MCprep default) resource pack selected, you can replace still images with their animated versions. Works great to put motion back into lava, water, portals and other blocks for any kind of resource pack. |
| Combine materials/images | Consolidates duplicate materials and images down to the smallest number of unique datablocks. *Note: combine images is only available on blender 2.78+* |
| Improve UI | A shortcut to quickly improve viewport settings for Minecraft sets. Sets textured solid mode & turns off mipmaps |
| Mesh Swap | Allows you to replace simple models from 3D exported worlds with more intricate 3D models |
| Scale UV Faces | Allows you to scale all UV faces of a mesh about their origin. Must be in edit mode of a mesh. |
| Select Alpha Faces | Allows you to select or delete mesh faces that are transparent in the applied image texture. Must be in edit mode of a mesh. |
| Sync Materials | Search for the `materials.blend` file within the active texture pack, and for any matching materials found in this file, import and overwrite the current file's version of that same material. Found under the World Exporter > Advanced section or in prep materials popup. |


| World Tools   |      Description      |
|----------|:-------------:|
| Create MC World | Operator which allows user to create either a static or dynamic sky. Options exist to also add clouds, remove existing sun lamps, and define how the Sun/Moon is imported (either as a shader, mesh, or neither). If a dynamic sky is created, a time-control slider will also be displayed below. |
| Prep World | This operator makes several updates to either Blender Internal, Cycles, or Eevee scenes that are optimal and in most cases will notably improve render times (particularly for cycles) and increase overall aesthetic. |


| Skin Swapper   |      Description      |
|----------|:-------------:|
| Apply [skin] | Applies the currently list-selected skin to the actively selected rigs. |
| Skin from file | Loads in a skin texture from file and applies to the actively selected rigs. *Note: Also gets added to skin list* |
| Skin from username | Downloads a skin based on a play name and applies to the actively selected rigs. *Note: Also gets added to skin list* |
| + sign | Install a custom skin into the list without applying to a rig |

*Note: only 1.8 skin layouts are supported at this time, in the future an auto-conversion feature will likely be implemented*


| Spawner   |      Description      |
|----------|:-------------:|
| Spawn: [rig] | Based on the actively selected rig, from an according spawning rig category, add the mob/character into the scene. These are fully rigged characters. Using the plus sign, you can even install your own rigs (rig must be part of a group). For quicker mapping, you can even set an entire folder and it will auto-create subcategories of rigs based on folders. |
| Spawn: meshswap block | Place a block from the meshswap file into the 3D scene. Currently is limited to only having meshswap groups (e.g. torches and fire) and not objects (e.g. not supporting grass and flowers yet).|
| Spawn: items | Convert any image icon into a 3D mesh, with faces per each pixel and transparent faces already removed. Defaults to loading Minecraft items.|



| Material Library   |      Description      |
|----------|:-------------:|
| Load material | Generate the selected material and apply it to the selected material slot of the active object. Follows convention of the active resource pack and general Prep Materials operator. |


### Spawner mobs included in the current version of MCprep
![included-mobs](/visuals/MCprep_mobs_included.png?raw=true)


CREDIT
======
While this addon is released as open source software under the GNU GPL license, the assets are being released as [Creative Commons Attributions, CC-BY](https://creativecommons.org/licenses/by/3.0/us/). If you use MeshSwap, **please credit the creators** by linking to this page wherever your project may appear: [http://github.com/TheDuckCow/MCprep](https://github.com/TheDuckCow/MCprep). In addition, different parts of MCprep are under different GPL compatible licenses (see `LICENSE-3RD-PARTY.txt`).

Meshswap Block models developed by [Patrick W. Crawford](https://twitter.com/TheDuckCow), [SilverC16](http://youtube.com/user/silverC16), and [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse).


| Player Rigs   |      Creator      |
|----------|:-------------:|
| Fancy Feet Player |  [Patrick W. Crawford](http://www.youtube.com/TheDuckCow) ([Rig link](http://bit.ly/MinecraftRig)) |
| Fancy Feet Slim Player | Modified by [Jeremy Putnam](http://www.blendswap.com/user/lorddon) (MCprep exclusive) |
| Fancy Feet Armor Player | Modified by [zNightlord](https://twitter.com/znightTrung) (MCprep exclusive) |
| Simple Player (modified) | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Simple Slim Player (modified) | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) + TheDuckCow (MCprep exclusive) |
| Shapekey Player | Derived from [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home), shapekeys and animation by [Patrick W. Crawford](http://www.youtube.com/TheDuckCow) (MCprep exclusive) |
| Story Mode Rig | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) (No direct link yet) |
| VMcomix Steve (rounded) | [VMcomix](https://www.youtube.com/user/VMComix) ([Rig link](http://vmcomix.blogspot.com/)) |


| Passive Rigs   |      Creator      |
|----------|:-------------:|
| Allay | [zNightlord](https://twitter.com/znightTrung) |
| Axolotl | [Breadcrumb](https://www.youtube.com/channel/UCT1_5td4SWg67fhElGz1S4A) |
| Bat | [Patrick W. Crawford](http://www.youtube.com/TheDuckCow) (MCprep exclusive) |
| Cat | [TRPHB Animation](https://youtube.com/c/TRPHBAnimation) |
| Cod fish | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Chicken | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) (No direct link yet) |
| Cow | [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse) ([Rig link](http://rymdnisse.net/downloads/minecraft-blender-rig.html)) |
| Dolphin | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Fox | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Frog | [zNightlord](https://twitter.com/znightTrung) |
| Glow squid | [TRPHB Animation](https://youtube.com/c/TRPHBAnimation) |
| Goat | [TRPHB Animation](https://youtube.com/c/TRPHBAnimation) |
| Mooshroom (red/brown) | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Parrot | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Pig | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) (No direct link yet) |
| Panda | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Pufferfish| [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Rabbit | [HissingCreeper](https://www.youtube.com/channel/UCHV3_5kFI93fFOl6KbmhkQA) (No direct link yet) |
| Salmon | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Sheep | [HissingCreeper](https://www.youtube.com/channel/UCHV3_5kFI93fFOl6KbmhkQA) (No direct link yet) |
| Squid | [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse) ([Rig link](http://rymdnisse.net/downloads/minecraft-blender-rig.html)) |
| Tropical Fish | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Cod fish | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Turtle | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |


| Hostile Rigs   |      Creator      |
|----------|:-------------:|
| Bee | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Blaze | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) (No direct link yet) |
| Cave Spider | [Austin Prescott](https://youtu.be/0xA4-yMr2KY) |
| Creeper | [Patrick W. Crawford](http://www.youtube.com/TheDuckCow) (MCprep exclusive) |
| Drowned | [thefunnypie2 + HissingCreeper](https://github.com/TheDuckCow/MCprep/issues/160#issuecomment-931923101) |
| Eldar Guardian | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Ender Dragon | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Enderman | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) ([Rig link](http://www.blendswap.com/blends/view/79750)) |
| Endermite | [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse) ([Rig link](http://rymdnisse.net/downloads/minecraft-blender-rig.html)) |
| Evoker | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Ghast | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) (No direct link yet) |
| Guardian | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) ([Rig link](http://www.blendswap.com/blends/view/79729)) |
| Hoglin | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Husk | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Magma Cube | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Piglin | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Pillager | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Polar bear | [PixelFrosty](https://twitter.com/Pixel_Frosty) ([Demo/download](https://www.youtube.com/watch?v=kbt5HWjafBk))|
| Phantom | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Ravager | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Shulker | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) ([Rig link](http://www.blendswap.com/blends/view/79729)) |
| Silverfish | [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse) ([Rig link](http://rymdnisse.net/downloads/minecraft-blender-rig.html)) |
| Skeleton | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) ([Rig link, outdated](http://www.blendswap.com/blends/view/79495)) |
| Slime | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads))  |
| Spider | [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse) ([Rig link](http://rymdnisse.net/downloads/minecraft-blender-rig.html)) |
| Stray | [thefunnypie2 + Trainguy9512](https://github.com/TheDuckCow/MCprep/issues/160#issuecomment-931923101) |
| Strider | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Vindicator | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Warden | [DigDanAnimates](https://twitter.com/DigDanAnimates) |
| Witch | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Wither | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Wither Skeleton | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Vindicator | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Zoglin | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Zombie | [HissingCreeper](https://www.youtube.com/channel/UCHV3_5kFI93fFOl6KbmhkQA) (No direct link yet) |
| Zombie Pigman | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Zombie Villager | [thefunnypie2 + HissingCreeper](https://github.com/TheDuckCow/MCprep/issues/160#issuecomment-931923101) |
| Zombified Piglin | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |



| Friendly/Utility Rigs   |      Creator      |
|----------|:-------------:|
| Horse | [Patrick W. Crawford](http://www.youtube.com/TheDuckCow) ([Rig link](http://www.blendswap.com/blends/view/73064)) |
| Iron Golem | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) ([Rig link](http://www.blendswap.com/blends/view/79455)) |
| Llama | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Ocelot | [HissingCreeper](https://www.youtube.com/channel/UCHV3_5kFI93fFOl6KbmhkQA) (No direct link yet) |
| Simple Villager (Dynamic skin) | [Th3pooka](https://twitter.com/Th3Pooka) |
| Snow Golem | [Nils Söderman (rymdnisse)](http://youtube.com/rymdnisse) ([Rig link](http://rymdnisse.net/downloads/minecraft-blender-rig.html)) |
| Villager | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Wandering Trader | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Wolf | [Trainguy9512](https://www.youtube.com/channel/UCktn-etC2h25hMTk1tIz7IQ) ([Rig link, outdated](http://www.blendswap.com/blends/view/79628)) |


| Entities   |      Creator      |
|----------|:-------------:|
| Arrow | [TRPHB Animation](https://www.youtube.com/c/TRPHBAnimation/) |
| Boat | [TRPHB Animation](https://www.youtube.com/c/TRPHBAnimation/) |
| Bow | [TRPHB Animation](https://www.youtube.com/c/TRPHBAnimation/) |
| Crossbow | [TRPHB Animation](https://www.youtube.com/c/TRPHBAnimation/) |
| Minecart | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| Shield | [Ageofherosmedia](https://github.com/TheDuckCow/MCprep/issues/245#issuecomment-998745223) |
| Spyglass | [Banana-Blu](https://github.com/Banana-Blu) |


| Effects   |      Creator      |
|----------|:-------------:|
| Geo node effects | [Th3pooka](https://twitter.com/Th3Pooka) |
| TNT effects (both) | [TheDuckCow](http://www.youtube.com/TheDuckCow) |
| Rain + Snow particles | [TheDuckCow](http://www.youtube.com/TheDuckCow) |


| Meshswap Blocks | Creator |
|----------|:-------------:|
| Campfire | [BoxScape Studios](https://sites.google.com/view/boxscape-studios/home) ([Pack link](https://sites.google.com/view/boxscape-studios/downloads)) |
| All others | [TheDuckCow](http://www.youtube.com/TheDuckCow) |


If you use any of these rigs in your animation, give credit to the according creator or by directly referring back to this readme file which contains all the credits. *Models have been slightly modified to function best and consistently with the MCprep addon.*


Thank you to all the contributors to this project! It will continue to grow and cover more assets in the near future.



How to use this addon
======


### Prep materials:
- **Purpose:** To automatically setup better, crisp materials for rendering Minecraft, low resolution textures. It works for both Blender internal as well as cycles, and more recently the cycles Principled shader. It will even selectively turn 'shiny' materials into reflecting materials, as well as 'bright' materials into emitting materials. Currently, the list of these materials is hard-coded into a json file, with names matching the material names for both jmc2obj and Mineways. You can modify this file for your own needs, but largely should be fine with the default, and will be updated (overwritten) as new updates are added.
- **Step 1:** Export your world to an OBJ or other general 3D formats. I use jmc2obj, but Mineways or other such formats should be fine as well.
- **Step 2:** Import the world into blender (e.g. via file > import > obj, or whatever according format)
- **Step 3:** Select all, or select the objects that have the material you want to fix. Materials can be all separate objects or the same object, it does not matter.
- **Step 4:** Under the MCprep panel, press "Prep Materials".
- **Step 5:** Change settings (optional, defaults are good!) and press ok - and wait a moment while the addon does the rest! Settings

*Settings popup for prep materials.*

![Prep material settings](/visuals/prepMaterialsSettings.png?raw=true)

Setting options:
  - **Use principled shader:** Cycles only and 2.79 and up, use the more physically accurate Principled shader node. If disabled, it will default back to previous material setups. The principled shader is, however, preferred.
  - **Use reflections:** Add extra settings to make material more reflective. For Blender Internal, enable reflections. For cycles materials, increase reflection alpha so that even fully transparent sections of image (e.g. in glass) will show some reflections.
  - **Animate textures:** See the section below, this performs the same operation after prepping materials, with the default behavior of "save to next to current source image", which is likely in the texture pack itself
  - **Find missing images:** Look to replace any missing images with their counterparts in the active resource pack, which by default is vanilla Minecraft textures as ship with MCprep
  - **Use extra maps:** If extra passes like normal and specular maps are available with the selected resource pack, load them into the material (note: the default MCprep texture pack will not have these passes)
  - **Improve UI:** Does not impact existing materials, but just sets the viewport to a nice minimum default to see the result of prepping materials - but always checked rendered mode to see how they truly look in the end
  - **Combine materials:** This will go through the entire blend file and attempt to merge together same-named materials (e.g. grass and grass.001 and grass.002 will all be consolidated down into one shared material, though something like grass-edit would be left alone)
  - **Sync materials:** Look for any matching material names (after casting to Minecraft canonical names) in the materials.blend file (if presnet) under the active resource pack. If found, replace this local material with that from the materials.blend file.


### Swap texture pack
- **Purpose:** Replace the images in a blend file with those from another Minecraft resource pack. Operates on selected objects and their respective materials, so you can mix and match different resource packs on a per-material basis this way.
- **Step 1:** Select all materials you wish to swap texture packs for
- **Step 2:** Prep materials on these objects if you haven't already (prepping a second time will do no harm); not doing this could have mixed results.
- **Step 3:** Press on the swap texture pack button in the 3D view > MCprep tab > World Imports panel
- **Step 4:** In this popup, the folder will default to the MCprep resource pack (ie default Vanilla Minecraft); navigate to an *extracted* zip folder of a valid resource pack. You can select any sub-folder, but to be safe, select the folder level such that the  the "pack.png" and "assets" sub-folder are visible as rows.
- **Step 5:** Decide if you want to enable/disable pulling in extra passes (e.g. normal and specular, if they exist) and whether to animate textures upon swapping. Both of these tickboxes, on by default, are in the left-hand sidebar.

Using Mineways? Use the following world export settings to use this feature:
![Mineways exporter settings](/visuals/mineways-settings.png?raw=true)

Note: Use tiles for exporting to create individual files per block instead of one combined texture file. This is what allows swap texturepack and animate textures to work.


### Meshswap:
- **Purpose:** To automatically swap in extra assets such as 3D grass, light emitting torches and lamps, and so forth. Note that all the objects to be swapped in are in the blend file part of this download. Also note that swapping is done based on the name of the material. If you are unsure why your object is not swapping in, check the material name matches the counterpart object/material in the meshSwap.blend file. Note it can search for both append-able objects as well as groups, containing particles and so forth. Modifiers on the mesh in the original file will be brought over, so notice for example how the tall grass when replaced will be "pre-simulated" as it has displacement modifiers setup already with animation.
- **Step 0:** By default this is already done for you; set the MeshSwap blend path to the "mcprep_meshSwap.blend" or custom blend file, and make sure the world export has blocks of size 1m (100cm).
- **Step 1:** Select the objects that you wish to be meshSwapped. Swappable objects are determined *automatically* based on the contents of the blend file selected above. If an object is not found or swappable, it will just be skipped - no harm done by "over selecting" (so select all objects to make sure everything that can be swapped gets swapped!)
- **Step 2:** Press Mesh Swap (there will be a small delay, meshswapping large areas such as fields of grass may take awhile).

*Setup your Mineways worlds in this fashion for best results.*

![Mineways exporter settings](/visuals/mineways-settings.png?raw=true)

*Setup your jmc2obj worlds in this fashion for best results.*

![jmc2obj exporter settings](/visuals/jmc2obj-settings.png?raw=true)

*Note: You can now also directly add meshswap blocks into the scene from the shift-A menu or the spawner:meshswap panel.*

To add your own objects to meshswap (or groupswap):

- **Step 1:** Check your imported world object and see the name of the material for the object you want to setup. You might think it is "glass plane", but if the importer names the material "glass_plane", you need to note this name down for step 3.
- **Step 2:** Model you object in the mcprep_meshSwap.blend file, or append it.
- **Step 3:** Rename your object to exactly match the previously noted material name. If you want to have a group swappable, then name the group to match the name above.
  * So the MATERIAL name found in the 3D imported world should match the OBJECT name of the model in the meshswap file to work
  * Note if both a group and an object have matching names, the script will prefer the group and meshswap that over the object.
- **Step 4:** Add necessary properties to special blocks as needed. See the meshSwap file included for examples, but the properties to add are:
  * "variance": Objects with this property when meshswapped will have some x/y variance added. If the property is set to 1, it will also have (only negative) z variance. If it is set to 0, it will only have xy variance. For instance, tall_grass is given a value of 1 so some grass is shorter than others, but flowers are given a value of 0 so they always have the same height but still have some variance in placement.
  * "edgeFloat": objects like vines, ladders, and lillypads which float off the edge of other blocks.
  * "torchlike": objects that can have rotations like a torch on a wall. Objects with this property will be determined to be either on top of a block or placed on the side of another block according to the mesh.
  * **Note:** there is no UI for adding properties to a group, so if you want to add a property to a group (say a torch which has a pre-animated light and particle system, as the included blend file does) you must go into the python console and add the property like so:  <code>bpy.data.groups['groupName']['propertyName'] = 1</code>  (the value only matters for the variance property)
  * **Example:** <code>bpy.data.groups['torch']['torchlike'] = 1</code> will add the torchlike property to the torch group, allowing it to have correct rotations when meshSwapped in.


### Animate textures:
- **Purpose:** Replace still images with animated sequences, for livelier materials! This operator runs over all materials of all selected objects. For each *image pass* found within each material, it will attempt to replace the still image with the tiled counterpart in the active texture pack. Minecraft resource packs store animated textures in the form of long, vertical images. Blender internal and cycles work best when reading image sequences as separated files, so this function actually "exports" the image sequence from a single tiled image into a subfolder with one image per frame, and then assigns this to the image block in blender. Any tiled image is eligible to be animated this way, even if not normally an animated sequence in vanilla Minecraft.

- **Step 0:** Prep materials first, if you haven't already; not required, but helpful.
- **Step 1:** Select the materials you want to animate. Try this on water, lava, and portals! Note, there is no harm in "over-selecting"; if you press animate textures on materials that cannot be animated (i.e. no tiled images to pull in), it will just skip over it.
- **Step 2:** From the popup, decide how and where you want the save the generated image sequence.
  - "Next to current source image": This will export the sequence to a subfolder in the same directory as the current, existing image
  - "Inside MCprep texture pack": This will export the sequence to a subfolder in active texture pack selected
  - "Next to this blend file": This will export the sequence to a Textures folder placed next to the current saved blend file.
  - Be careful when moving your blend file to other locations or other computers! Even if you use "pack images", image sequences **do not get packed** in the blender file. You must manually copy this folder to wherever you plan to render/open the file. For this purpose, such as render farms or multi-computer rendering, be sure to always set save location as "Next to this blend file" (preferred) or "Next to current source image".
- **Step 3:** If you have been running into issues, consider ticking the "clear cache" box (this will remove any previous or partially exported image sequences)
- **Step 3:** Press okay, and wait! Some notes:
  - If you have a high-resolution texture pack selected, this could take some time. Blender will be unresponsive while this processes.
  - This should only be slow the first time you animate textures, thereafter (with the same save-location selection) it will skip re-exporting and directly load the existing image sequence for each matching material.
  - You can view progress in the console (on Windows, go to top bar >Windows > Toggle console)

*Animate textures can be found under the World Imports - Advanced panel; or tick the box on prep materials.*
![Animate textures button](/visuals/animateTextures.png?raw=true)

Using Mineways? Use the following world export settings to use this feature (key: use tiles):
![Mineways exporter settings](/visuals/mineways-settings.png?raw=true)


### Scale UV Faces:
- **Purpose:** To take a UV map and scale all of the individual UV faces about their own origins, similar to "Individual origins" transformation available in the 3D view for scaling, but is not available for connected faces in the UV editing window. This would be used if you are experiencing "bleeding" of a texture around the edges of a face, sometimes an artifact of how Blender treats low resolution images, or as a quick way to fix loosely-done UV unwrapping.
- **Step 1:** Select a mesh that already has a material and texture applied
- **Step 2:** Go into edit mode on this mesh
- **Step 3:** Press the Scale UV Face button from either location:
  - 3D View > Toolshelf (left, press t) > MCprep Tab > World Imports
  - Image Viewer > Toolshelf (left, press t) > Tools tab > Transform Panel, MCprep section
- **Step 4:** Adjust the scale factor in the redo last (or F6) window, defaults to 0.75


### Select Alpha Faces:
- **Purpose:** To quickly select, or delete, all faces that fall on transparent pixels of the corresponding applied image for the active mesh. Useful if you want to speed up renders by not having to render transparent faces, or avoid other related issues. **Note**: The current implementation works well for "grid" unwrapped objects where the UV map has clear rows and columns aligned to the image axis, however it will still work to *some extent* with any unwrapped face UV shape over any image.
- **Step 1:** Select a mesh that already has a material and texture applied
- **Step 2:** Go into edit mode on this mesh
- **Step 3:** Press the Select Alpha Faces button from either location:
  - 3D View > Toolshelf (left, press t) > MCprep Tab > World Imports
  - Image Viewer > Toolshelf (left, press t) > Tools tab > Transform Panel, MCprep section
- **Step 4:** Adjust the properties in the redo last window, or by pressing F6
  - Delete faces: If checked, this will automatically delete the selected faces (setting will be saved for the current blender session)
  - Threshold: From 0-1, consider the face as transparent if the average of the image pixels falling within the given face is below this threshold.


### Create MC Sky:
- **Purpose:** This operator provides options to add both simple and advanced, shader-driven skies to your worlds. There are two primary types of skies you can add. Works for Eevee, Cycles, and Blender Internal (no shader-driven option for adding sky/moon for Blender Internal)
- Adds a basic day-sky texture. Works for both cycles and blender internal, and creates a better starting point than the default gray world background. No option yet for setting other times of day.
- The optional settings:
  - **Dynamic World**: This is an advanced node shader setup designed for both Cycles and Eevee. It allows for driving the sky colors and brightness based on the time of day, as driven by a time property which will appear in the panel after adding a dynamic world. This allows you to create day, morning, night, and sunrise/sunset scenes with ease, and furthermore even lets you freely animate the time such that you can create your own timelapse sequences. Dynamic skies also import sun lamps, and either shader-based or mesh-based sun/moon. You can even somewhat easily hack the shader to insert HDRs in place of the procedural blended sky colors, and have the shader automatically and smoothly blend between these images. As you change the time, the sun and moon (if enabled) and physical sun lamp follow the time of day in sync. Variants of the Dynamic World include:
    - **With Shader sun/moon**: This unique feature allows you to have a sun and moon that will appear in the scene but at a distance of infinity, without having to change your camera render distance limit!
    - **With mesh sun/moon**: The mesh is imported from a source library, and place into the scene around the origin of the scene. Note that, of course, your sun/moon objects exist in the scene like any other object, and so you make want to scale them out to limit the effect of parallax effects relative to the camera, and likewise update your camera’s render distance if you do scale out the distance of the sun/moon meshes from the camera.
    - **No sun or moon** imported/setup
  - **Static World**: This is a simpler shader setup and does not offer the ability to animate the time of day, but still is better than the default gray background! Best fit for a midday scene. Options include:
    - With mesh sun/moon: Same description as in the section above.
    - No sun or moon mesh imported
  - Import cloud mesh
  - Remove existing sun lamps (as dynamic and static sky will import their own sun lamps, you may want to use this to remove existing ones)


### Prep World:
- **Purpose:** This button found in the World Tools panel will assign nicer default world settings for rendering and animation, for both Blender Internal and Cycles.
- Note: Previously this operator added simple sky materials, now it is focused on only render settings. Use "Create MC World" above to initial world settings.
- Optimizes/improves render settings (cycles):
  - Turns off reflective and refractive caustics (will increase speed over default)
  - Increases light sampling threshold to a better balance (will increase speed over default)
  - Sets max bounces to 8 (blender default is 12, and generally this number can typically be lowered further)
  - Turns on Simplify and sets Simplify AO to level 2 for viewport and render (this will save on average 20-30% on render times with minimal impact; for much faster rendering, you can even set this lower to a level of 1, but be mindful of how shadows and reflections around objects with texture transparencies behave).
- Improves render settings (blender internal):
  - Turns on AO with multiple of 0.1 (may cause renders to be slower, but generally nicer looking)
  - Turns on environment global illumination (color inherited from sky settings). This may slow down renders, but they will be generally nicer and prevents any “pitch black” scenes.
  - Turns on ray tracing and shadows (may cause renders to be slower, but generally nicer looking)
  - If there is a sun in the scene, it will turn on “use sky blend” which will make the rotation of the sun lamp affect the sky color / sun glow position.


### Sync Materials
- **Purpose:** Quickly load in previously set up materials found in the active resource pack's `materials.blend`, and replace corresponding materials on selected objects. Found under the World Exporter > Advanced section, or in prep materials popup.
- **Step 1:** Select an object with materials you want to sync
- **Step 1:** Press Sync Materials. This will only affect materials on the selected objects. If nothing was matched to the `materials.blend` file,

To edit the materials.blend file for syncing:

- **Step 1:** Open the materials.blend file in the active resource pack, or create the file if adding it to another resource pack. This file should be placed in the root folder of the resource pack, i.e. next to the `pack.png` file and `assets` folder.
- **Step 2:** Technically optional but recommended: add a new cube for your material for quick previewing. Reset the UV layout in edit mode so each face takes up the whole texture.
- **Step 3:** Apply a material to this new object, either by:
  1) Appending from an existing file where you already created this material
  2) Usse the `Load Materials` panel to load the default MCprep material. Strongly suggested you change the resource pack (under advanced) to be `//` to tell blender to use the local director as the resource pack, so that it doesn't reference images outside the resource pack.
- **Step 3:** Edit the material shader nodes. ONLY the material itself will be synced.


### Skin Swapping:
- **Purpose:** To provide quick and easy skin changing on rigs and characters already in your blender scene.
- **Step 1:** Select your rig (or rigs) that you want to change the skin for. It works best if you select all of the objects of your rig (e.g. head, torso, legs etc) but it will work even if you only selected the armature (in that case, results are only visible in rendered view)
- **Step 2:** Select a skin from the skin file list under the tool menu: 3D view > MCprep tab > Skin Swapper Panel > UI List of skins, left click to select/highlight a skin
  - *Don't see the skin you want?* Click "skin from file" to select one from your machine, or "skin from username" to download and apply a Minecraft user's skin, or go into advanced to Add Skin for future use without immediately applying it.
- **Step 3:** Press the button that says "Apply [skin name]"
- **Step 4:** You're done! If the user interface appears to not update, be sure to **check rendered view** (shift+z). Also note the default behavior is to make a *new* material. This way, if you had other characters with the same skin that you don't want changed, those are left alone. You can turn this off in the redo last menu or via F6.
  - There are some redo-last options to control how skin swapping is done, changing any of these settings will undo and redo the skin swap with the newly applied setting.
  - If you untick the box to "swap all images", then the operaetor will only swap images of any image texture nodes with the name "MCPREP_SKIN_SWAP" or "MCPREP_diffuse" and leave others alone.


### Load Material:
- **Purpose:** To quickly load/generate Minecraft materials, without having to first import a world obj. Follows convention of the active resource pack and general Prep Materials operator.
- **Step 2:** Select an object and go into the Properties > Material tab (this feature is NOT in the MCprep panel).
- **Step 2:** Load materials. Runs automatically when changing resource pack
- **Step 3:** Select the material you want to load with left click. You can scroll to find the desired material, or expand the search bar inside the bottom of the UI list box.
- **Step 4:** Select load - the material will *replace* the material in the current material slot.


### Mob Spawner:
- **Purpose:** To provide quick, one-click importing/linking of quality Minecraft mob and player rigs in blender.
- **Step 0:** By default this is already done for you; make sure the mob spawner path is a directory with valid blend files setup for linking (addon preferences > MCprep). After installing MCprep for the first time, this path will already be setup and valid pointing to the included rigs with this release, as defined in the credits section above. This rigs are place in the addon's local directory provided by blender and will not be placed anywhere else on the user's machine. Deleting the addon also deletes these rigs (careful if you're library linking!)
- **Step 1:** Either go to MCprep tab > spawner > click on Mob, or go to the shift-a menu: MCprep > mob spawner > [mob name] to instantly append or link in a rig.
- **Step 2:** Check the redo last menu (or press F6) for additional settings:
  - Relocation: Change where the spawned rig appears.
    - Cursor (default): Place the rig at the cursor's location
    - Origin: Move the rig to the origin
    - Offset root: Move the rig to the origin, but offset the root bone to the cursor's location (note: doesn't work with all rigs correctly right now, will be improved in the future)
  - Library Link mob: If disabled, the group is appended (the groups is not kept so it can be appended multiple times). If enabled, the rig will be linked in and armatures auto-proxied.
    - Be careful! If the blend file moves, the libraries will likely get broken unless a custom rigs folder is used with a local-relative path.
  - Clear pose: clear to pose to rest. If false, the initial pose will be that found in the rig's source blend file. **Note:** some rigs have animations already setup, setting clear pose will also automatically clear any default animations.
  - Prep materials: this will automatically run the prep materials function, noting this will regenerate cycles materials if cycles is the active render engine.

*Mob Spawner Redo-last/F6 Options*
![Meshswap options](/visuals/spawnOptions.png?raw=true)

#### To add your own rigs to the Mob Spawner:

- **Step 1:** Make your rig, or download one you want to use!
- **Step 2:** Make sure all elements of the rig, ie all armatures, body parts, and extra objects, are added to a single group (select and press control+g) inside your rig file. The name of this group is what will appear under the shift-a menu, and typically matches the name of the file if there is just one rig per blend file.
- **Step 3:** Optional but useful, rename the root/main bone of the rig to one of [MAIN, root, base], used for relocation. Additionally, make the armature for animation named [name].arma where [name] exactly matches the name of the group. This is used for auto-proxying of the armature and relocation methods.
- **Step 4:** Optional, if you have a custom script for the rig, save it as an external file whose name matches the blend file exactly, but with .py instead of .blend, place this in the same folder as the blend file.
  - Additionally, to auto import an icon with this rig, create a folder next tot he blend file called "icons" and create a file with the name that exactly matches the name of the rig's *group name*, e.g. Group name "Zombie Pigman" could have the icon file "zombie pigman.png" (not how this is not case-sensitive, but it is space-sensitive)
- **Step 5:** Either from Blender Preferences > Addon > MCprep preferences panel > "Install file for mob spawning" or from the MCprep 3D view tab, go to spawner > mob > menu "Install new mob". From there, use the file browser to select the blend file and install it! This copies the file to the current mob folder, by default inside the MCprep addon.
- **Alternative:** To specify a different, custom folder in a location of your choosing for mob spawning, simply change the "Mob spawner folder" path in the MCprep mob spawner advanced section (this setting is saved to blend file), or save a new default in the addon's preferences (becomes the default for all new blend scenes).
- Note: all groups inside installed blend files will appear for mob spawning. After installing a blend file, you do *not* need to save user preferences to use it in future blender sessions.

#### Using multiple collections in your rig?

Be aware of this behavior to ensure only one collection appears in the rig spawner (use one or the other):
- Option 1: Add "mcprep" to the name of your top-level collection to be imported
- Option 2: Add "mcskip" to *all* collections that should NOT be listed.


*Sometimes you may need to reload a rig cache, click this button if the correct rigs aren't appearing - or if you've just added new rigs to the folder outside of blender*

![Reload rig cache](/visuals/reloadRigCache.png?raw=true)



### Block Spawning

Generate blocks from vanilla or other resource packs, or even from mods or other sources. **NOTE!** This is a newer part of MCprep, and because it is completely generalized, it's rather unstable. There are any known issues where blocks do not generate correctly, so bear this in mind ([see here](https://github.com/TheDuckCow/MCprep/issues/267)).


#### Spawn resource pack blocks
- **Purpose:** To be able to generate blocks defined by json files from the active resource pack
- **Step 1:** Go into Spawners, click the triangle next to Block (model) spawner.
- **Step 2:** Click a row to make active, you can search for a block by clicking the other smaller triangle icon inside the scroll view
- **Step 3:** Press "Place: {block name}"


#### Spawn blocks from json
- **Purpose:** To be able to generate blocks defined by json files
- **Step 1:** Go into Spawners, click the triangle next to Block (model) spawner
- **Step 2:** Press "Import model (.json)" to popup the filebrowser
- **Step 2:** Navigate to a .json file on your system
- **Step 2:** With the single json file selected, press "Import Model"


### Item Spawner:
- **Purpose:** To be able to quickly generate 3D Minecraft items from images.
- **Step 0:** By default this is already done for you; in advanced settings, point the folder to a valid Minecraft resource pack (with an items folder), or directly select the folder containing individual images per item.
- **Step 1:** Navigate to the spawner panel and select items; press load if needed
- **Step 2:** Select the item in the UI list, you can press the little plus at the bottom to open a free text search to hep bring up what you want
- **Step 3:** Press the Place: {item} button below
- **Step 4:** Modify redo last settings as needed (also accessible by pressing F6 after spawning). Options include:
  - Maximum number of pixels: Will scale the image down if number of pixels exceeds this (unlikely for Minecraft resource packs)
  - Thickness: If above 0, will add a solidify modifier with this level of thickness; can always be adjusted or removed later
  - Alpha Threshold: At this level or lower of alpha values (0.0-1.0), delete the face from the resulting mesh.
  - Use transparent pixels: If enabled, will setup the material so that transparent pixels will appear transparent in the render, otherwise will be solid.



### Effects Spawner:
Quickly bring effects into your scene.

#### Effects types
There are four different kinds of effects that MCprep supports:

- **Geo node**: Load wide area effects driven by Geo Nodes (Blender 3.0+ only). These have the benefit of being deterministic, meaning no simulation occurs, and can follow the camera. This means no matter how fast your camera moves, you won't run into particles like snow not having fallen yet.
- **Particle**: Wide area effects like snow and rain, parented to the camera to simulate weather.
- **Collection**: Load pre-animated effects saved in collections (Blender 2.8+ only). Animations (both direct and indirect, such as particle systems) are automatically offset based on the current frame, making this much more useful that appending and trying to manually offset when it plays. Each imported combo collection+frame gets its own collection added and excluded, for reuse.
- **Image Sequence**: Load a target image sequence from a resource pack folder and import into blender inside a collection where each image is setup as a mesh plane. The animation can be sped up or slowed down at the time of import.
- **Particle Planes**: This does not show up in the UI scroll list. Instead, this is an operator button that when pressed adds a particle system based from a cut up version of a selected input image, and offset to the current timeline frame.

#### Adding your own effects

**Purpose:** Learn how to add your own effects to extend MCprep for your case.
- **Geo node effects:** Simply add another blend file with your geo node setup into the MCprep resources folder: MCprep_resources/effects/geonodes
   - If you have a reusable node group where different parameters of the same group make different effects happen (e.g. calm rain vs windy rain), you can define a json file which matches exactly the blend file name, containing a mapping of settings to the node group in question. This will override all geo nodes that will be listed in MCprep. See the existing node group as an example. This is NOT required ot simply have a single geo node effect show up.
   - Node groups are automatically parented to the active camera in the scene and meant to "follow" the view
- **Particle effects:** Simply add new particle systems to the same or new blend files in the MCprep resources folder: MCprep_resources/effects/particle.
   - Your default emitter should have a size of 40x40m, so that MCprep can automatically maintain the same according density of particles. This size also helps ensure there is sufficient coverage no matter which direction the camera points or turns.
- **Collection effects:** Simply add new effects to new blend files in the MCprep resources folder: MCprep_resources/effects/collection. The animations are assumed to start at frame one, and offset accordingly when spawned in a scene later.
- **Image sequence effects:** These are read from the active resource pack's effects folder. Simply place your image sequence of files there and it should load in automatically. Alternatively, point the active resource pack to the parent of another effects resource pack folder (the active resource pack must be pointing to the top level of the resource pack still in order to recognize the folder for image sequence spawning)

See the tutorial here for more details: https://www.youtube.com/watch?v=8xy4nZaneQU

### Entity Spawner:
- **Purpose:** To provide quick, one-click importing of pre-rigged entities that are not mobs or blocks
- **Step 1:** Navigate to the spawner panel and expand Entity Spawner
- **Step 2:** Click a row to select it
- **Step 3:** Spawn arrow!

Under advanced settings, you can change your target entity file to point to another blend file, as well as force reload entities.


### Meshswap block Spawner:
- **Purpose:** To provide quick, one-click importing of meshswap 3D blocks and groups.
- **Step 0:** By default this is already done for you; make sure the meshswap file path is a directory with valid blend files setup for appending (addon preferences > MCprep). When installed, this path will already be setup and valid pointing to the included blocks with this release.
- **Step 1:** Navigate to the spawner panel and expand Meshswap Spawner
- **Step 2:** Select a row to spawn
- **Step 3:** Press "Place {block}"
- **Step 4:** Modify redo last settings as needed (also accessible by pressing F6 after spawning). Options include:
  - Meshswap block: You can change here which block you wanted to add
  - Location: Set the location where the block is placed
  - Append layer: layer to append contents of the group to; default is layer 20, setting to 0 will use the currently active layer(s) as the layers for the group
  - Prep materials: run prep materials on the imported objects, particularly useful if using cycles
  - Snapping dropdown: Snap the placed block to a rounded coordinate. Optional offset by 0.5 as well
  - Make real: Instance the groups so they are made real, thus allowing you to individually modify the objects within the group. Note: this may clear any pre-applied animation.


### Cycles Optimizer
- **Purpose:** To optimize Cycles render settings without sacrificing much quality
- **Step 1:** Navigate to the World Imports panel and find the "Cycles Optimizer" panel
- **Step 2:** Select the features you want to use
- **Step 3:** Hit the "Optimize Scene" button (It is recommended to do this twice. Once when prepping materials and once before rendering your final render)

**Warning**: There is a section called unsafe features which contains options that may cause render issues. These features can being massive performance boosts but it's not recommended to use them unless you know what you're doing. Unsafe options include:

- **Automatic Scrambling Distance:** Improves GPU performance but can cause artifacts. As such, if the optimizer reaches a scrambling multiplier of 0.7+, MCprep will automatically disable it. Please enable this before rendering your final render to reduce the chances of having artifacts:
    
- **Preview Scrambling:** Enabled by default if you enable `Automatic Scrambling Distance`. This can cause a lot of flickering in rendered view (which is how Automatic Scrambling Distance works in the first place).

![Optimizer panel](/visuals/optimizer-panel-settings.png?raw=true)


#### Cycles Optimizer Node Settings

*NOTE: the Cycles Optimizer is deprecated and will be removed in MCprep 3.6*

The Cycles optimizer also comes with it some special node names to control how it interprets certain nodes. They are the following:
- `MCPREP_HOMOGENOUS_VOLUME`: if applied to a Volume Scatter, Volume Absorption, or Principled Volume node, it is treated as a homogeneous volume 
- `MCPREP_NOT_HOMOGENOUS_VOLUME`: if applied to a Volume Scatter, Volume Absorption, or Principled Volume node, it is not treated as a homogeneous volume 

To use these settings, simply click on the node you want to edit, press N, and then edit the Name of the node

**Important:** Make sure you edit the **Name** of the node, not the **Label**
![Using optimizer node settings](/visuals/optimizer-node-settings.png?raw=true)

Known Bugs
======
See all [known current bugs here](https://github.com/TheDuckCow/MCprep/issues?q=is%3Aissue+is%3Aopen+label%3Abug)


Future Plans
======
Future development plans are now recorded and updated as milestones and enhancement issues on GitHub. Check [those out here](https://github.com/TheDuckCow/MCprep/milestones)


Additional Help
======

If you have troubles getting this addon to work, please contact me at support[at]TheDuckCow.com or [on twitter](https://twitter.com/TheDuckCow), and I will do my best to respond promptly to your questions. This addon is always being updated, but there may be some time between releases, so check back for updates (you can reference the version number and take last modified). Your feedback helps stabilize the addon and make it work better for everyone else!

Moo-Ack!
