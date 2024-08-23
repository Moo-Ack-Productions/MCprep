from bpy_addon_build.api import BabContext
import subprocess
from pathlib import Path

EXTENSION_BL_INFO_PATCH = Path(__file__).parent.joinpath("build-patches/extension-bl_info.diff")

def pre_build(ctx: BabContext) -> None:
    print("Applying Extension Patches")
    _ = subprocess.run(["git", "apply", str(EXTENSION_BL_INFO_PATCH)], cwd=ctx.current_path.parent)

def clean_up(ctx: BabContext) -> None:
    print("Cleaning up patches")
    _ = subprocess.run(["git", "apply", "-R", str(EXTENSION_BL_INFO_PATCH)], cwd=ctx.current_path.parent)
