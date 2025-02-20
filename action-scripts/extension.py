import os
from bpy_addon_build.api import BabContext
from lib_bpybuild_ext import BLENDER_MANIFEST, compat, get_manifest_data, verify
from pathlib import Path


def main(ctx: BabContext) -> None:
    if not ctx.is_extension:
        return
    # Fix bl_info with string replacements because Blender
    # 4.2+ doesn't like extensions having bl_info
    #
    # Normally this would be a bad idea, but __init__.py
    # is so small and tiny that we likely won't run into
    # issues
    print("Patching bl_info")
    init_file = Path(ctx.current_path, "__init__.py")
    init_content = init_file.read_text()
    with open(init_file, 'w') as f:
        new_content = init_content.replace("bl_info", "BL_INFO")
        _ = f.write(new_content)

    print("Setting up the Blender Manifest")
    os.rename(Path(ctx.current_path, "_blender_manifest.toml"), Path(ctx.current_path,"blender_manifest.toml"))

    print("Performing validation of extension")
    manifest_path = Path(ctx.current_path, BLENDER_MANIFEST)
    manifest_data = get_manifest_data(manifest_path)
    verify.verify_manifest(manifest_data, manifest_path)
    compat.check_for_compat_issues(ctx.current_path, ctx.builtin_config.addon_folder)
