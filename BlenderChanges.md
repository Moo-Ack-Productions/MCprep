This list contains all deprecations and removals in every Blender version starting with Blender 3.0. Since Blender 4.0's breaking changes invoked the want for a list of all deprecations and changes, this list is public for addon developers to use.

Note that not all deprecations are listed, just the ones that may affect MCprep or changes that developers should be aware of in general, so please refer to the wiki entries for each version for more information.

_For Developers_: The use of any deprecated feature is an automatic bug. Such features should be wrapped around if statements for backwards compatibility if absolutely necesary in older versions.

_For MCprep maintainers_: Any use of a deprecated feature in a pull request should be questioned. If the feature is needed in older versions, then remind developers to use `min_bv`, `bv28` ([Deprecated in MCprep 3.5](https://github.com/TheDuckCow/MCprep/pull/401)), or `bv30`, whichever is more appropriate.

# [Blender 3.0](https://wiki.blender.org/wiki/Reference/Release_Notes/3.0/Python_API)
## Deprecations
None that concern MCprep.

## Breaking Changes
- Rigs made in Blender 3.0 are no longer compatible with older versions of Blender. 
    - A workaround would be to convert the rigs to FBX, then import in an older version of Blender.

# [Blender 3.1](https://wiki.blender.org/wiki/Reference/Release_Notes/3.1/Python_API)
## Deprecations
None that affect MCprep

## Breaking Changes
- Python 3.10 [no longer converts floats to integers](https://github.com/python/cpython/issues/82180). Code should therefore be checked and updated as needed

# [Blender 3.2](https://wiki.blender.org/wiki/Reference/Release_Notes/3.2/Python_API)
## Deprecations
- Passing context to operators has been deprecated. **Removed in Blender 4.0**
    - The Blender release notes give the following example for reference:
    ```py
    # Deprecated API
    bpy.ops.object.delete({"selected_objects": objects_to_delete})

    # New API
    with context.temp_override(selected_objects=objects_to_delete):
        bpy.ops.object.delete()
    ```

## Breaking Changes
- `frame_still_start` and `frame_still_end` have been removed. The release notes suggest using a negative value for `frame_offset_start` and `frame_offset_end`

# [Blender 3.3](https://wiki.blender.org/wiki/Reference/Release_Notes/3.3/Python_API)
## Deprecations
- Conext menu entries should be appended to `UI_MT_button_context_menu`.
    - The Blender release notes give the following example for reference: 
    ```py
    ### Old API ###
    class WM_MT_button_context(Menu):
        bl_label = "Unused"

        def draw(self, context):
            layout = self.layout
            layout.separator()
            layout.operator("some.operator")

    def register():
        bpy.utils.register_class(WM_MT_button_context)

    def unregister():
        bpy.utils.unregister_class(WM_MT_button_context)

    ### New API ###
    # Important! `UI_MT_button_context_menu` *must not* be manually registered.
    def draw_menu(self, context):
        layout = self.layout
        layout.separator()
        layout.operator("some.operator")

    def register():
        bpy.types.UI_MT_button_context_menu.append(draw_menu)

    def unregister():
        bpy.types.UI_MT_button_context_menu.remove(draw_menu)
    ```

## Breaking Changes
- `frame_start`, `frame_offset_start`, and `frame_offset_end` are now floating point.

# [Blender 3.4](https://wiki.blender.org/wiki/Reference/Release_Notes/3.4/Python_API)
## Deprecations
None that concern MCprep.

## Breaking Changes
- The internal data structure for meshes has been changed significantly
    - The old API remains and doesn't seem to be deprecated, but it will be slower then using the new API
- Nodes for new materials get their names translated
    - The solution is to not refer to nodes by their names
- MixRGB has since been replaced with a new general Mix node. The wiki does not mention if the node name has been changed.

# [Blender 3.5](https://wiki.blender.org/wiki/Reference/Release_Notes/3.5/Python_API)
## Breaking Changes
- Registering classes that have the same names as built-in types raises an error
- The internal mesh data structure has gone through more changes.
    - `MeshUVLoop` is deprecated. **Removed in Blender 4.0**
        - `data` remains emulated, but with a performance penalty

# [Blender 3.6](https://wiki.blender.org/wiki/Reference/Release_Notes/3.6/Python_API)
Nothing that concerns MCprep

# [Blender 4.0 (IN DEVELOPMENT)](https://wiki.blender.org/wiki/Reference/Release_Notes/4.0/Python_API)
## Deprecated
Nothing that concerned MCprep for now.

## Breaking Changes
- Glossy BSDF and Anisotrophic BSDF nodes have been merged. 
    - The node's Python name is `ShaderNodeBsdfAnisotropic`
- `MeshUVLoop` removed
- Passing context into operators removed
- Principled BSDF has been completely rewritten, including sockets
    - Subsurface -> Subsurface Weight
    - Subsurface Color removed, use Base Color instead
    - Specular -> Specular IOR Level
    - Specular Tint changed from float to color
    - Transmission -> Transmission Weight
    - Coat -> Coat Weight
    - Sheen -> Sheen Weight
    - Emission -> Emission Color
