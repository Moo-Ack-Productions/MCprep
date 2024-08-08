IGNORE_FILTERS = ["**/mcprep_addon_tracker.json"]

def main():
    from pathlib import Path
    for i in IGNORE_FILTERS:
        for p in Path(".").glob(i):
            p.unlink()
            print(f"Ignore Filter: Deleted {p}! Please remove it from the addon directory")
