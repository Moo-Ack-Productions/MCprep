# Common Error messages and what they mean
## OBJ not exported with the correct settings for textureswap
This means the OBJ was exported with incorrect UVs, most commonly UVs for a texture atlas (a giant image with all textures) rather than individual textures. In Mineways, this can be solved by selecting the "Export tiles for textures to directory textures"/"Export individual textures to directory tex" option when exporting, depending on the version. In later versions of Mineways, this should be the default option.

### Why not simply fix the UVs?
That's a massive pain in the butt to program, not to mention it causes more issues
