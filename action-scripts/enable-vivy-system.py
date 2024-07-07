from bpy_addon_build.api import BabContext
import subprocess
from pathlib import Path

VIVY_PATCH = Path(__file__).parent.joinpath("build-patches/enable-vivy.diff")

def pre_build(ctx: BabContext) -> None:
    print("Applying Vivy Patches")
    _ = subprocess.run(["git", "apply", str(VIVY_PATCH)], cwd=ctx.current_path.parent)

def pre_build(ctx: BabContext) -> None:
    print("Cleaning up patches")
    _ = subprocess.run(["git", "apply", "-R", str(VIVY_PATCH)], cwd=ctx.current_path.parent)
