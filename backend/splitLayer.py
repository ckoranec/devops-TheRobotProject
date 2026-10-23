import json
import sys

LAYER_NAMES = ["way"]
WAY_TYPE_KEY = "highway"           # tag used to tell ways apart
NO_TYPE_LABEL = "(no highway tag)"

def geojson_to_elements(features):
    """Convert GeoJSON features into Overpass-style 'way' elements."""
    elements = []
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            elements.append(feat)          # find_problem will flag it
            continue

        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        gtype = geom.get("type")
        fid = feat.get("id", props.get("@id", props.get("id", i)))

        if gtype == "LineString":
            lines = [geom.get("coordinates")]
        elif gtype == "MultiLineString":
            lines = geom.get("coordinates") or []
        else:
            # Point, Polygon, null geometry, etc. -> flagged as unexpected type
            elements.append({"type": gtype, "id": fid})
            continue

        for line in lines:
            points = []
            for pt in line if isinstance(line, list) else []:
                if (isinstance(pt, list) and len(pt) >= 2
                        and all(isinstance(v, (int, float)) for v in pt[:2])):
                    points.append({"lat": pt[1], "lon": pt[0]})   # GeoJSON is [lon, lat]
                else:
                    points.append({})      # flagged as missing lat/lon
            elements.append({"type": "way", "id": fid,
                             "tags": props, "geometry": points})
    return elements

# Load json file and check validitaty 
def load_data(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit(f"ERROR: file not found: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: file is not valid JSON: {e}")

    if isinstance(data, dict) and isinstance(data.get("features"), list):
        print("Detected format: GeoJSON")
        return geojson_to_elements(data["features"])

    if isinstance(data, dict) and isinstance(data.get("elements"), list):
        print("Detected format: Overpass JSON")
        if data.get("remark"):
            print("WARNING: Overpass remark:", data["remark"])
        return data["elements"]

    sys.exit("ERROR: neither a GeoJSON FeatureCollection nor Overpass JSON.")

def find_problem(el):
    if not isinstance(el, dict):
        return "element is not an object"
    if el.get("type") not in LAYER_NAMES:
        return f"unexpected type: {el.get('type')!r}"
    if not isinstance(el.get("id"), (int, str)):       # str allowed for GeoJSON ids
        return "missing or invalid id"

    geom = el.get("geometry")
    if not isinstance(geom, list) or not geom:
        return "way has no coordinates"

    # Overpass ways carry node ids; GeoJSON ones don't, so only check if present
    if "nodes" in el:
        refs = el["nodes"]
        if not isinstance(refs, list) or len(refs) < 2:
            return "way has fewer than 2 node ids"
        if len(geom) != len(refs):
            return "way geometry does not match its node ids"
    elif len(geom) < 2:
        return "way has fewer than 2 points"

    for pt in geom:
        if (not isinstance(pt, dict)
                or not isinstance(pt.get("lat"), (int, float))
                or not isinstance(pt.get("lon"), (int, float))):
            return "way geometry point missing lat/lon"
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
        sys.exit("usage: python splitLayer.py <file.json>")
 
    elements = load_data(sys.argv[1])
    layers, broken = split_into_layers(elements)
    way_types = split_ways_by_type(layers["way"])
    healthy = report(layers, way_types, broken, total=len(elements))
 
    print("\nRESULT:", "OK" if healthy else "PROBLEMS FOUND")
    sys.exit(0 if healthy else 1)
 
 
if __name__ == "__main__":
    main()


