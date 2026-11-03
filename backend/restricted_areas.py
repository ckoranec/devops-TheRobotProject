"""Restricted area avoidance (starter).

Finds restricted areas in gmu_map.json and the routing nodes inside them, so the
route finder can treat those nodes as blocked.

Done:
  - load_restricted_areas(): reads restricted areas and construction from the map
  - point_in_polygon(): checks if a point is inside an area
  - nodes_in_areas(): finds the graph nodes that fall inside any area

TODO (Colin):
  1. edges_crossing_areas(): a path can cut through an area without having a node
     inside it. Check each edge's shape against each area.
  2. route_violations(): given a finished route, list any areas it enters
     (name + reason), so the system can alert instead of silently failing.
  3. Use this in routing: block the nodes from nodes_in_areas() (and the edges
     from step 1) before running dijkstra_equation().
  4. Tests in backend/test_restricted_areas.py: a small fake map with one area,
     and a route that must go around it.
  5. Agree the list of restricted areas with the team (card's Plan item).
"""
import json

from dijkstra_json_blockage import load_walk_graph

RESTRICTED_ACCESS = {"no", "private"} #access/foot values that mean the robot may not enter


def restriction_reason(tags: dict) -> str | None: #Why a feature is restricted, or None if it isn't
    if tags.get("access") in RESTRICTED_ACCESS:
        return f"access={tags['access']}"
    if tags.get("foot") in RESTRICTED_ACCESS:
        return f"foot={tags['foot']}"
    if tags.get("landuse") == "construction" or "construction" in tags:
        return "construction"
    return None


def load_restricted_areas(json_path: str) -> list[dict]:
    areas = []
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    for elem in data["elements"]:
        if elem["type"] != "way" or "geometry" not in elem:
            continue
        tags = elem.get("tags", {})
        reason = restriction_reason(tags)
        if reason is None:
            continue
        points = [(pt["lat"], pt["lon"]) for pt in elem["geometry"]]
        closed = len(points) >= 4 and elem["nodes"][0] == elem["nodes"][-1] #Closed way = an area, open way = a line
        areas.append({
            "id": str(elem["id"]),
            "name": tags.get("name", "Unnamed area"),
            "reason": reason,
            "closed": closed,
            "points": points, #(lat, lon) outline
            "nodes": [str(n) for n in elem["nodes"]], #Node IDs on the outline or line
        })
    return areas


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


def nodes_in_areas(graph, areas: list[dict]) -> dict[str, dict]:
    #Map of node ID -> the area that blocks it
    blocked: dict[str, dict] = {}
    for area in areas:
        if area["closed"]:
            for node_id, (lat, lon) in graph.nodes.items():
                if point_in_polygon(lat, lon, area["points"]):
                    blocked[node_id] = area
        #Open restricted ways (e.g. a private path) block their own nodes
        for node_id in area["nodes"]:
            if node_id in graph.nodes:
                blocked[node_id] = area
    return blocked


def edges_crossing_areas(graph, areas: list[dict]):
    #TODO (Colin): return edges whose shape passes through an area even though
    #neither end node is inside it. Hint: check each point in edge.coords with
    #point_in_polygon(), then think about whether that is enough.
    raise NotImplementedError


def route_violations(line: list[tuple[float, float]], areas: list[dict]) -> list[dict]:
    #TODO (Colin): return the areas a finished route enters, so the system can
    #print a clear alert like "Route enters <name> (<reason>)".
    raise NotImplementedError


if __name__ == "__main__":
    graph, _barriers = load_walk_graph("../gmu_map.json")
    areas = load_restricted_areas("../gmu_map.json")
    blocked = nodes_in_areas(graph, areas)
    print(f"restricted areas: {len(areas)} ({sum(a['closed'] for a in areas)} closed, {sum(not a['closed'] for a in areas)} lines)")
    print(f"routing nodes blocked: {len(blocked)} of {len(graph.nodes)}")
    for area in areas:
        count = sum(1 for a in blocked.values() if a is area)
        print(f"  {area['id']:>12}  {area['reason']:<14} {count:>3} nodes  {area['name']}")
