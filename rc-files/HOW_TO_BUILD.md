Step 1. Run `download_resources.sh` to add the necesary asset files

Step 2. Apply all patches in the `patches` folder. Here's an example for the `rc-bl_info` patch
```sh
git apply rc-files/patches/rc-bl_info.patch
```

Step 3. Use Bpy-Build to build MCprep like normal
