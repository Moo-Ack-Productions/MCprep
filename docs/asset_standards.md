MCprep thrives on the contribution of rigs from the community. However, to maintain a feel of consistency and usability, we set a number of standards when accepting a rig. 

In the past, the MCprep team (mostly @TheDuckCow) have accepted rigs and created manual changes to fix any of the QA issues found below. Going forward, due to volume and where time could be better spent, we are more likely to ask asset contributors to address these issues themselves, and hence this detail page outlining those expectations.

All contributors are welcomed and encouraged, but we do recommend you have a baseline level of experience in the areas of modeling, UV, and rigging to ensure quality submissions. However, any feedback given will always be constructive if any standards below are not met.

_Anything unclear? Report [an issue](https://github.com/Moo-Ack-Productions/MCprep/issues/)!_


## Mob + Entity standards checklist

Treat the below steps as a checklist in a way to audit your own rig.

- The most important QA test: use "install rig" in MCprep, and then test importing
   - There should be no errors, and materials should work, and the armature and everything should be there with no unexpected parented objects or "extras" coming in (e.g. custom bone shapes popping into the scene)
   - Do this test in BOTH blender 2.80 and the latest stable release (e.g. 3.6 as on August 2023). 
   - Make sure the rig still looks correct when posed or animated from all sides.
- The blend file must be last saved in blender 2.80 OR have version partitioning across all versions of blender 2.80+
  - This is important as we support 2.80+, so all rigs need to adhere to that
  - You can check the last version saved by opening the given blend file, going to the Script tab, and then typing this command into the Interactive Python Console: `bpy.data.version`, it should print out something like the screenshot below
  - Not sure what rig partitioning means? Take this as an example, and hopefully it clarifies:
    - `Warden - DigDanAnimates pre2.80.0.blend` Will be used by anything _before_ blender 2.80 (in other words, we'll be deleting this file soon!)
    - `Warden - DigDanAnimates pre3.0.0.blend` Will be used by anything _before_ blender 3.0 (e.g. 2.80, 2.93)
    - `Warden - DigDanAnimates.blend` Will be used by blender 3.0 and higher (due to no other "pre#.#.# being higher than 3.0.0)
  - We should aim to NOT partition rigs by version as much as possible, as it bloats download size and becomes even more to maintain. But sometimes, we can't avoid it.
- The rig must be self contained. That means textures are packed (File > External Data > Pack Resources)
   - This is to negate the issue of relative vs absolute paths, which just become a pain
   - Best practice is still to run "relpaths" beforehand, to avoid having any user's paths hard coded into the file, which is more of a privacy thing than anything.
- Extra unused data should be purged, to minimize bloat
- All rigs should be defined in their own top level collection. All other collections in the file not related to the rig must be removed
  - If a rig itself has multiple nested collections, that's ok - the top level collection just needs to have "MCprep" in the name, e.g. "Warden MCprep" will be what gets listed in the UI list, and it won't list any sub collections or other collections in the file. The warden rig is again an example of this. But prefer to just have a single collection where possible.
- Custom bone shapes are ok and in fact encouraged, just don't put them in the rig scene. If you want to put them into their own collection, either give it the name MCskip OR make sure the primary collection (s) have the text MCprep in it, so that the 
- The root-most bone of the rig must:
  1. Exist. Ie one central bone that everything is parented to, so if you move this everything, including control-only panels, also move
  2. Be named one of: `["main", "root", "base", "master"]`; case does not matter, though convention is to primarily use ROOT in all uppercase.
- _All bones_ should be named, no name.001's or anything like that.
  - Furthermore, left/right bones should be named as per the blender guidelines. [See here](https://docs.blender.org/manual/en/latest/animation/armatures/bones/editing/naming.html), which helps ensure animation tools will work like flip pose left/right.
- _All meshes_ should be named as well. No cube.001's, give them representation names
- The rig must be a reasonably faithful representation of a Vanilla mob or entity
  - No custom mobs that aren't in game (yet)
  - No highly detailed or stylized looks that would differ from the rest of the library, e.g. generally there shouldn't be beveling
  - Some extra details that accentuate and make high fidelity animations possible are OK. Examples include: Knees and elbows that bend (but it should still look vanilla if they don't bend), extra face controls or facial details (in the case of player rigs)
- Drivers are ok, but shouldn't be excessive - and minimize the use of python expression drivers where possible
  - Drivers add a lot of overhead, especially if you have many of one mob type in a scene. 
  - Simple drivers, such as "SUM position" used to translate a control panel to bone transforms are fine - but they should NOT be python expressions, rather they should be SUM of [variable transform channels], as these run much quicker.
- A fun note: The default position of the rig should show off its flaire! Ie, the saved pose _should_ be posted.
  - MCprep has controls for clearing the post on import. Meanwhile, having a posed starting point helps show off what the rig can do.
- If relevant, the rig can have a single default animation. There should _not_ be more than one animation though, since it wouldn't be obvious and would clutter the file during subsequent imports
  - The bat is an example of this, with a simple flying pattern. The Enchanting table is also an example (although that is a "block" and not an entity or rig)
- Technically, rigs can have a single python script named after the same blend file that are used to draw custom interfaces
  - But this is strongly not encouraged, as we cannot guarantee maintaining these ad hoc scripts. Much preferred to have drivers in the system itself, so that we don't have to rely on the user finding a custom panel or anything like that
  - However, this feature of having python script loading will be kept, as it is very useful for users who have their own custom rigs they like to install and use.


## Other asset contributions

QA will be done on a case by case basis. This would apply to meshswap mesh contributions, geometry node weather effects, and anything else not mentioned.