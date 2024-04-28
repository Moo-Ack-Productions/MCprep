def main() -> None:
    print("Dev build, adding mcprep_dev.txt...")
    with open("mcprep_dev.txt", "w") as f:
        f.write("This file is used to enable debugging mode in MCprep, you can ignore this")

if __name__ == "__main__":
    main()
