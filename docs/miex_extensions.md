# MCprep MiEx Extensions

This document lists the custom condition tokens MCprep
adds on top of the base MiEx template specification.

While MCprep tries to stick to the upstream format as
much as possible, extensions are sometimes needed for
certain features. In general, the rules surrounding extensions
are:

- MiEx templates not using them must not break.
- No structure changes (e.g. no renaming sections in the JSON).
- Must be easily resolvable when exporting for MiEx compatibility.

## Condition Tokens

| Token | Description |
| :--- | :--- |
| `@emit@` | Evaluates true if the block is classified as light-emitting in MCprep and the `Emission` prep setting (`useEmission`) is enabled. |
| `@reflective@` | Evaluates true if the block has reflective properties (e.g. ice, polished blocks) and the `Reflections` prep setting (`useReflections`) is enabled. |
| `@metallic@` | Evaluates true if the block is metallic (e.g. iron, gold, copper) and `useReflections` is enabled. |
| `@solid@` | Evaluates true if the block is fully opaque, or if the `Make Solid` prep setting (`makeSolid`) is enabled. |
| `@glass@` | Evaluates true if the block is glass or stained glass. |
| `@water@` | Evaluates true if the block is water. |
| `@backface_culling@` | Evaluates true if the block specifies backface culling in MCprep checklists. |
| `@desaturated@` | Evaluates true if the foliage texture is grayscale and requires biome tinting. |
