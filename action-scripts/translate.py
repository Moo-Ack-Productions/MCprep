from translate_scripts import build_pot, build_trans_dict, compile_po_to_mo

def main():
    build_pot.main()
    compile_po_to_mo.main()
    build_trans_dict.main()

if __name__ == "__main__":
    main()
