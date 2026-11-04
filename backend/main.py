import json
import os
import sys
 
# gmu_map_api.py lives one folder up from backend/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gmu_map_api
from map_compare import compare_maps
from notify import notify
 
 
def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
 
 
def main():
    active = gmu_map_api.active_filename
 
    # Read the old map before gmu_map_api overwrites it
    saved = load(active) if os.path.exists(active) else None
 
    # Download and save the new map (exits on failure)
    gmu_map_api.main()
    fresh = load(active)
 
    if not saved:
        print("First run: saved this map as the starting point. Nothing to compare yet.")
        return
 
    changes = compare_maps(fresh, saved)
    print("Changes:", changes)
    notify(changes, fresh, saved)
    print("Done.")
 
 
if __name__ == "__main__":
    main()