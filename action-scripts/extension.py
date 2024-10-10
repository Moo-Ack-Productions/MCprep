import os
from bpy_addon_build.api import BabContext
from lib_bpybuild_ext import BLENDER_MANIFEST, compat, get_manifest_data, verify
import subprocess
from pathlib import Path

EXTENSION_BL_INFO_PATCH = Path(__file__).parent.joinpath("build-patches/extension-bl_info.diff")

def pre_build(ctx: BabContext) -> None:
    print("Applying Extension Patches")
    _ = subprocess.run(["git", "apply", str(EXTENSION_BL_INFO_PATCH)], cwd=ctx.current_path.parent)

def main(ctx: BabContext) -> None:
    print("Setting up the Blender Manifest")
    os.rename(Path(ctx.current_path, "_blender_manifest.toml"), Path(ctx.current_path,"blender_manifest.toml"))
    print("Performing validation of extension")
    manifest_path = Path(ctx.current_path, BLENDER_MANIFEST)
    manifest_data = get_manifest_data(manifest_path)
    verify.verify_manifest(manifest_data, manifest_path)
    compat.check_for_compat_issues(ctx.current_path, ctx.builtin_config.addon_folder)

def clean_up(ctx: BabContext) -> None:
    print("Cleaning up patches")
    _ = subprocess.run(["git", "apply", "-R", str(EXTENSION_BL_INFO_PATCH)], cwd=ctx.current_path.parent)
