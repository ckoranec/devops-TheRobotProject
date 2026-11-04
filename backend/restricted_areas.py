"""Restricted area avoidance (starter for the Restricted Area Avoidance card).

Run from backend/:
  python restricted_areas.py --export   writes html/data/restricted_areas.geojson from gmu_map.json
  python restricted_areas.py            loads that file and shows which routing nodes each zone blocks

Done:
  - find_candidate_zones(): pulls every access=no/private and construction feature
    out of gmu_map.json as a starting list for the team to review
  - export_zones() / load_zones(): the restricted areas file (GeoJSON, name + reason
    + sample flag for each zone), so the overlay page can show it as its own layer
  - point_in_polygon() and nodes_in_zones(): which routing nodes fall inside a zone

TODO (Colin), matching the card's checklists:
  Plan
    [ ] Agree the zone list with the team. --export gives every candidate (20 right
        now, mostly unnamed private roads). Trim html/data/restricted_areas.geojson
        to the agreed zones, give each a name and reason, keep "sample": true for now.
    [ ] Decide what an alert looks like (a clear message naming the zone and why).
  Build
    [ ] Avoidance: edges_crossing_zones(), then block those edges and the nodes from
        nodes_in_zones() before dijkstra_equation(). Agree with Satchi where this goes.
    [ ] Alert: check_endpoints() for a start/destination inside a zone, and a clear
        alert naming the zone when no route exists without entering one.
  Verify
    [ ] 3 saved test routes: one that used to cross a zone and now goes around, one
        with a destination inside a zone, one with no safe route.
    [ ] Show each result on a map: zones in red, route on top.
    [ ] route_violations(): script that confirms no test route touches any zone.
    [ ] Campus policy rules, ticked against the test results.
    [ ] Code review by a teammate, plus a short readme on adding or changing a zone.
"""
import argparse
import json
from pathlib import Path

from dijkstra_json_blockage import load_walk_graph

ROOT = Path(__file__).resolve().parent.parent
MAP_FILE = ROOT / "gmu_map.json"
ZONES_FILE = ROOT / "html" / "data" / "restricted_areas.geojson"

RESTRICTED_ACCESS = {"no", "private"} #access/foot values that mean the robot may not enter
FOOT_ALLOWED = {"yes", "designated", "permissive"} #foot values that let pedestrians through even when access says no


def restriction_reason(tags: dict) -> str | None: #Why a feature is restricted, or None if it isn't
    if tags.get("landuse") == "construction" or "construction" in tags:
        return "construction"
    #The robot moves like a pedestrian, so foot overrides access (access=no usually means no cars)
    if tags.get("foot") in FOOT_ALLOWED:
        return None
    if tags.get("foot") in RESTRICTED_ACCESS:
        return f"foot={tags['foot']}"
    if tags.get("access") in RESTRICTED_ACCESS:
        return f"access={tags['access']}"
    return None


def find_candidate_zones(map_path: Path = MAP_FILE) -> list[dict]:
    zones = []
    with open(map_path, encoding="utf-8") as fh:
        data = json.load(fh)

    for elem in data["elements"]:
        tags = elem.get("tags", {})
        reason = restriction_reason(tags)
        if reason is None:
            continue
        if elem["type"] == "node": #A single blocked point, e.g. a lift gate with foot=no
            zones.append({
                "id": str(elem["id"]),
                "name": tags.get("name", tags.get("barrier", "Unnamed point")),
                "reason": reason,
                "sample": True,
                "closed": False,
                "points": [(elem["lat"], elem["lon"])],
                "nodes": [str(elem["id"])],
            })
            continue
        if elem["type"] != "way" or "geometry" not in elem:
            continue
        points = [(pt["lat"], pt["lon"]) for pt in elem["geometry"]]
        closed = len(points) >= 4 and elem["nodes"][0] == elem["nodes"][-1] #Closed way = an area, open way = a line
        zones.append({
            "id": str(elem["id"]),
            "name": tags.get("name", "Unnamed area"),
            "reason": reason,
            "sample": True, #Stays true until the team agrees the list
            "closed": closed,
            "points": points, #(lat, lon) outline or line
            "nodes": [str(n) for n in elem["nodes"]], #OSM node IDs on the outline or line
        })
    return zones


def export_zones(zones: list[dict], out_path: Path = ZONES_FILE) -> None:
    features = []
    for zone in zones:
        coords = [[lon, lat] for lat, lon in zone["points"]] #GeoJSON is [lon, lat]
        if zone["closed"]:
            geometry = {"type": "Polygon", "coordinates": [coords]}
        elif len(coords) == 1:
            geometry = {"type": "Point", "coordinates": coords[0]}
        else:
            geometry = {"type": "LineString", "coordinates": coords}
        features.append({
            "type": "Feature",
            "properties": {k: zone[k] for k in ("id", "name", "reason", "sample", "nodes")},
            "geometry": geometry,
        })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, indent=2)


def load_zones(zones_path: Path = ZONES_FILE) -> list[dict]:
    with open(zones_path, encoding="utf-8") as fh:
        data = json.load(fh)
    zones = []
    for feature in data["features"]:
        props = feature["properties"]
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            coords = geometry["coordinates"][0]
        elif geometry["type"] == "Point":
            coords = [geometry["coordinates"]]
        else:
            coords = geometry["coordinates"]
        zones.append({
            "id": props["id"],
            "name": props.get("name", "Unnamed area"),
            "reason": props.get("reason", "unknown"),
            "sample": props.get("sample", True),
            "closed": geometry["type"] == "Polygon",
            "points": [(lat, lon) for lon, lat in coords],
            "nodes": props.get("nodes", []),
        })
    return zones


def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    #Ray casting: count how many edges a line going east from the point crosses. Odd = inside.
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if (lat_i > lat) != (lat_j > lat):
            cross_lon = lon_i + (lat - lat_i) * (lon_j - lon_i) / (lat_j - lat_i)
            if lon < cross_lon:
                inside = not inside
        j = i
    return inside


def nodes_in_zones(graph, zones: list[dict]) -> dict[str, dict]:
    #Map of node ID -> the zone that blocks it
    blocked: dict[str, dict] = {}
    for zone in zones:
        if zone["closed"]:
            for node_id, (lat, lon) in graph.nodes.items():
                if point_in_polygon(lat, lon, zone["points"]):
                    blocked[node_id] = zone
        #Restricted lines (e.g. a private road) block their own nodes
        for node_id in zone["nodes"]:
            if node_id in graph.nodes:
                blocked[node_id] = zone
    return blocked


def edges_crossing_zones(graph, zones: list[dict]):
    #TODO (Colin): return edges whose shape passes through a zone even though
    #neither end node is inside it. Hint: check each point in edge.coords with
    #point_in_polygon(), then think about whether that is enough.
    raise NotImplementedError


def check_endpoints(start: tuple[float, float], goal: tuple[float, float], zones: list[dict]) -> list[str]:
    #TODO (Colin): return alert messages if the start or destination is inside a
    #zone, e.g. "Destination is inside Student Apartment Construction Zone (construction)".
    raise NotImplementedError


def route_violations(line: list[tuple[float, float]], zones: list[dict]) -> list[dict]:
    #TODO (Colin): return the zones a finished route touches. Use this in the
    #Verify tests to prove no route ever enters a zone.
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="Restricted area avoidance")
    parser.add_argument("--export", action="store_true", help="write candidate zones from gmu_map.json to the zones file")
    args = parser.parse_args()

    if args.export:
        zones = find_candidate_zones()
        export_zones(zones)
        print(f"wrote {len(zones)} candidate zones to {ZONES_FILE}")
        return

    graph, _barriers = load_walk_graph(str(MAP_FILE))
    zones = load_zones()
    blocked = nodes_in_zones(graph, zones)
    points = sum(len(z["points"]) == 1 for z in zones)
    areas = sum(z["closed"] for z in zones)
    print(f"zones: {len(zones)} ({areas} areas, {len(zones) - areas - points} lines, {points} points)")
    print(f"routing nodes blocked: {len(blocked)} of {len(graph.nodes)}")
    for zone in zones:
        count = sum(1 for z in blocked.values() if z is zone)
        sample = " (sample)" if zone["sample"] else ""
        print(f"  {zone['id']:>12}  {zone['reason']:<14} {count:>3} nodes  {zone['name']}{sample}")


if __name__ == "__main__":
    main()
