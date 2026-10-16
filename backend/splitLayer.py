import json
import sys

LAYER_NAMES = ["node", "way"]
WAY_TYPE_KEY = "highway"           # tag used to tell ways apart
NO_TYPE_LABEL = "(no highway tag)"


# Load json file and check validitaty 
def load_data(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: file not found: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: file is not valid JSON: {e}")
 
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        sys.exit("ERROR: no 'elements' list found. Is this Overpass JSON?")
    
    #check if timeout/ memory caused a incomplete file 
    if data.get("remark"):
        print("WARNING: Overpass remark:", data["remark"])
 
    return data["elements"]

#check if JSON elements are correctly formated and useable 
def find_problem(el):
    if not isinstance(el, dict):
        return "element is not an object"
    if el.get("type") not in LAYER_NAMES:
        return f"unexpected type: {el.get('type')!r}"
    if not isinstance(el.get("id"), int):
        return "missing or invalid id"
 
    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return "node missing lat/lon"
    else:  # way
        refs = el.get("nodes")
        if not isinstance(refs, list) or len(refs) < 2:
            return "way has fewer than 2 node ids"
    return None

# seperate and split layers into type (way, node)
def split_into_layers(elements):
    layers = {name: [] for name in LAYER_NAMES}
    broken = []
 
    for el in elements:
        problem = find_problem(el)
        if problem:
            broken.append(problem)
        else:
            layers[el["type"]].append(el)
    return layers, broken

#split ways into sub types 
def split_ways_by_type(ways):
    way_types = {}
    for w in ways:
        sub_type = w.get("tags", {}).get(WAY_TYPE_KEY, NO_TYPE_LABEL)
        way_types.setdefault(sub_type, []).append(w)
    return way_types

#check if anything is empty and get report of counts 
def report(layers, way_types, broken, total):
    healthy = True
 
    if total == 0:
        print("ERROR: file has no elements at all.")
        return False
 
    print("Layer counts")
    for name in LAYER_NAMES:
        count = len(layers[name])
        print(f"  {name:<6} {count}" + ("   <-- EMPTY" if count == 0 else ""))
        if count == 0:
            healthy = False
    print(f"  broken {len(broken)}")
 
    print(f"\nWay sub-types (by '{WAY_TYPE_KEY}' tag): {len(way_types)} types")
    # biggest first
    for sub_type, ways in sorted(way_types.items(), key=lambda kv: -len(kv[1])):
        print(f"  {sub_type:<20} {len(ways)}")
    if NO_TYPE_LABEL in way_types:
        print(f"  NOTE: {len(way_types[NO_TYPE_LABEL])} way(s) have no "
              f"'{WAY_TYPE_KEY}' tag")
 
    if broken:
        healthy = False
        print("\nBroken elements:")
        for msg in sorted(set(broken)):
            print(f"  - {broken.count(msg)} x {msg}")
 
    return healthy

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python prepare_data.py <file.json>")
 
    elements = load_data(sys.argv[1])
    layers, broken = split_into_layers(elements)
    way_types = split_ways_by_type(layers["way"])
    healthy = report(layers, way_types, broken, total=len(elements))
 
    print("\nRESULT:", "OK" if healthy else "PROBLEMS FOUND")
    sys.exit(0 if healthy else 1)
 
 
if __name__ == "__main__":
    main()