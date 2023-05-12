import os
import shutil
import sys
from pathlib import Path
from typing import List

# Config stuff
BUILD_NAME: str = "MCprep_addon"

# Internals
SCRIPT_PATH: Path = Path(__file__).resolve().parents[0]
BUILD_DIRECTORY: Path = SCRIPT_PATH / Path("build")
INTERMIDIATE_PATH: Path = BUILD_DIRECTORY / Path("inter")
ADDON_DIRECTORY: Path = SCRIPT_PATH / Path("MCprep_addon")
BLENDER_INSTALLS: Path = SCRIPT_PATH / Path("blender_installs.txt")
DEBUG_FILE: Path = Path("mcprep_dev.txt")
BUILT_ZIP: Path = BUILD_DIRECTORY / Path(BUILD_NAME + ".zip")


def main():
    blender_installs: List[Path] = []
    debug_mode: bool = False

    # Check arguments to see what mode to run the compiler in
    if len(sys.argv) <= 1:
        pass
    elif sys.argv[1] == "-d" or sys.argv[1] == "--debug":
        debug_mode = True
    else:
        print("Not a valid option!")
        return

    # Check if the developer blender_installs.txt
    if not BLENDER_INSTALLS.exists():
        print("You need a blender_installs.txt file!")
        return

    # If this happens, I've lost all hope for hummanity
    if BLENDER_INSTALLS.is_dir():
        print("blender_installs.txt needs to be a text file!")
        return

    # Read in file paths and return an error if there's no paths
    with open(BLENDER_INSTALLS, "r") as f:
        for line in f:
            blender_installs.append(Path(line.rstrip()))
    if not len(blender_installs):
        print("No autopopulation of Blender install paths for now!")
        return

    # Check if the addon folder exists
    if not ADDON_DIRECTORY.exists():
        print("Addon folder does not exist!")
        return

    # Create build directory so we don't get errors
    if not BUILD_DIRECTORY.exists():
        BUILD_DIRECTORY.mkdir()

    # Remove the built zip so we don't get errors
    if BUILT_ZIP.exists():
        os.remove(BUILT_ZIP)

    # Call flake8 to perform a check on the code
    os.system(f"flake8 --extend-ignore W191 {str(ADDON_DIRECTORY)}")

    # Create archive and move it to the build directory since shutil makes
    # the archive in the current working directory
    shutil.make_archive(str(
        BUILD_DIRECTORY / BUILD_NAME
    ), "zip", ADDON_DIRECTORY)

    # Add the debug file
    # TODO: We could add file injection at this point
    # for flexibility
    if debug_mode:
        # Create the intermediate folder
        if not INTERMIDIATE_PATH.exists():
            INTERMIDIATE_PATH.mkdir()
        # Remove if it already exists
        else:
            shutil.rmtree(INTERMIDIATE_PATH)

        # Unpack and remove the zip
        shutil.unpack_archive(BUILT_ZIP, INTERMIDIATE_PATH)
        os.remove(BUILT_ZIP)

        # Create dev file in intermediate path
        with open(INTERMIDIATE_PATH / DEBUG_FILE, "w") as f:
            f.write("This is the MCprep Dev File created by mcprep-build!")

        # Rebuild
        shutil.make_archive(str(
            BUILD_DIRECTORY / BUILD_NAME
        ), "zip", INTERMIDIATE_PATH)

    # Install addon
    for path in blender_installs:
        if not path.exists():
            print(
                f"Path {str(path)} in blender_installs.txt doesn't exist, skipping..."
            )

        edited_path: Path = path / Path(BUILD_NAME)
        if not edited_path.exists():
            edited_path.mkdir()
        else:
            shutil.rmtree(edited_path)
        shutil.unpack_archive(BUILT_ZIP, edited_path)


if __name__ == "__main__":
    main()
