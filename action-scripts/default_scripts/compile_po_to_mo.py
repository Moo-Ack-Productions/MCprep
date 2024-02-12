# Copyright (c) 2024 Mahid Sheikh. All Rights Reserved.
#
# This compiles all PO files in MCprep_resources/Languages
# to MO files that are used as a fallback for Python gettext.

from pathlib import Path
import polib

def main() -> None:
    print("Building MO files...")
    languages = Path("MCprep_resources/Languages") 

    if not languages.exists() or not languages.is_dir():
        print("Invalid directory for translations! Exiting...")
    
    for locale in languages.iterdir():
        if not locale.is_dir():
            continue
        file = Path(locale, "LC_MESSAGES", "mcprep.po")
        if not file.exists():
            print(file, "does not exist!")
        
        po = polib.pofile(str(file))
        po.save_as_mofile(str(file.parent.joinpath("mcprep.mo")))

if __name__ == "__main__":
    main()
