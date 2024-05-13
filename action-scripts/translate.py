from typing import Optional
from translate_scripts import build_pot, build_trans_dict, compile_po_to_mo
from bpy_addon_build.api import BabContext, BpyError
import sys

def pre_build(ctx: BabContext) -> Optional[BpyError]:
    sys.stdout.reconfigure(encoding='utf-8')
    return build_pot.pre_build(ctx)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Go through each module, and 
    # run its main function, while checking 
    # for a return value
    modules = [compile_po_to_mo, build_trans_dict]
    for mod in modules:
        res = mod.main()
        if res:
            continue 
        return res

if __name__ == "__main__":
    main()
