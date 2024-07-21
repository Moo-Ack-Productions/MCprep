from bpy_addon_build.api import BabContext
import subprocess
from pathlib import Path
import urllib.request
import hashlib

DEBUG_MODE_PATCH = Path(__file__).parent.joinpath("build-patches/debug-mode.diff")


# debugpy library from Microsoft, downloaded from Pypi
#
# https://github.com/microsoft/debugpy
DEBUGPY_WIN = "https://files.pythonhosted.org/packages/23/b1/3fc28ba2921234e3fad4a421dcb3185c38066eab0f92702c0d88ce891381/debugpy-1.8.2-cp311-cp311-win_amd64.whl"
DEBUGPY_LINUX = "https://files.pythonhosted.org/packages/4f/d6/04ae52227ab7c1d43b729d5ae75ebd592df56c55d4e4dfa30ba173096b0f/debugpy-1.8.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
DEBUGPY_OSX = "https://files.pythonhosted.org/packages/2b/ba/d06289b7c6194117fcecc88c24dee405b1c14b8e318e7bdf513eb78c3278/debugpy-1.8.2-cp311-cp311-macosx_11_0_universal2.whl"

DEBUGPY_HASH_WIN = "d3408fddd76414034c02880e891ea434e9a9cf3a69842098ef92f6e809d09afa"
DEBUGPY_HASH_LINUX = "acdf39855f65c48ac9667b2801234fc64d46778021efac2de7e50907ab90c634"
DEBUGPY_HASH_OSX = "8a13417ccd5978a642e91fb79b871baded925d4fadd4dfafec1928196292aa0a"

def validate_hash(file: str, hash: str):
    with open(file, "rb") as file:
        read_file = file.read()
    hasher = hashlib.sha256()
    hasher.update(read_file)
    assert hasher.hexdigest() == hash

def pre_build(ctx: BabContext) -> None:
    print("Debug Mode: Applying Patches")
    _ = subprocess.run(["git", "apply", str(DEBUG_MODE_PATCH)], cwd=ctx.current_path.parent)

def main(ctx: BabContext) -> None:
    print("Debug Mode: Adding debugpy wheels")
    _ = urllib.request.urlretrieve(DEBUGPY_WIN, f"{ctx.current_path}/wheels/debugpy-1.8.2-cp311-cp311-win_amd64.whl")
    _ = urllib.request.urlretrieve(DEBUGPY_LINUX, f"{ctx.current_path}/wheels/debugpy-1.8.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl")
    _ = urllib.request.urlretrieve(DEBUGPY_OSX, f"{ctx.current_path}/wheels/debugpy-1.8.2-cp311-cp311-macosx_11_0_universal2.whl")

    validate_hash(f"{ctx.current_path}/wheels/debugpy-1.8.2-cp311-cp311-win_amd64.whl", DEBUGPY_HASH_WIN)
    validate_hash(f"{ctx.current_path}/wheels/debugpy-1.8.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", DEBUGPY_HASH_LINUX)
    validate_hash(f"{ctx.current_path}/wheels/debugpy-1.8.2-cp311-cp311-macosx_11_0_universal2.whl", DEBUGPY_HASH_OSX)
    
    print("Debug Mode: Applying Patches")
    _ = subprocess.run(["git", "apply", str(DEBUG_MODE_PATCH)], cwd=ctx.current_path.parent)

def clean_up(ctx: BabContext) -> None:
    print("Debug Mode: Cleaning Up")
    _ = subprocess.run(["git", "apply", "-R", str(DEBUG_MODE_PATCH)], cwd=ctx.current_path.parent)
