from translate_scripts import build_pot, build_trans_dict, compile_po_to_mo
from bpy_addon_build.api import BabContext

def pre_build(ctx: BabContext) -> None:
    build_pot.pre_build(ctx)

def main():
    compile_po_to_mo.main()
    build_trans_dict.main()

if __name__ == "__main__":
    main()
