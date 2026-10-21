from __future__ import annotations

import argparse
import heapq
import json
import math
from dataclasses import dataclass, field


ALLOWED = {"footway", "path", "pedestrian", "service", "residential", "tertiary", "cycleway", "secondary", "unclassified", "tertiary_link", "primary", "primary_link"} #Walk tags that match red dotted lines on map

METERS_PER_DEG_LAT = 111_320.0

def flat_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat_scale = METERS_PER_DEG_LAT
    lon_scale = METERS_PER_DEG_LAT * math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * lon_scale
    dy = (lat2 - lat1) * lat_scale
    return math.hypot(dx, dy)


@dataclass
class Edge: #Line between nodes
    to: str #Destination node
    cost: float #Distance between nodes (m)
    coords: list[tuple[float, float]] #List of coordinate pairs
    way_id: str #JSON ID
    highway: str #Walk tag


@dataclass
class Graph: #Full graph of nodes and edges
    nodes: dict[str, tuple[float, float]] = field(default_factory = dict) #Dictionary mapping JSON IDs (str) to coordinate positions (tuple)
       
    adj: dict[str, list[Edge]] = field(default_factory = dict) #Adjacency dictionary mapping JSON IDs to list of edges connecting to it (list)
       

    def add_node(self, node_id: str, lat: float, lon: float): #Record position and check for adj
        self.nodes[node_id] = (lat, lon) #Set current latitude/longitude position to current JSON ID
        self.adj.setdefault(node_id, []) #Check connecting edges for current node

    def add_undirected(self, a: str, b: str, cost: float, coords_a_to_b: list[tuple[float, float]], way_id: str, highway: str,):
        if (a == b) or (cost <= 0): #a and b are both the same node or distance is none/negative
            return
        self.adj[a].append(Edge(b, cost, coords_a_to_b, way_id, highway)) #Stores connection between a and b twice to account for two-way direction
        self.adj[b].append(Edge(a, cost, list(reversed(coords_a_to_b)), way_id, highway))


def load_walk_graph(json_path: str):
    coords: dict[str, tuple[float, float]] = {} #JSON ID and coordinate position
    ways: list[tuple[str, str, list[str]]] = [] #

    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    for elem in data["elements"]:
        if elem["type"] == "node":
            coords[str(elem["id"])] = (elem["lat"], elem["lon"])
        elif elem["type"] == "way":
            # Overpass "out geom" puts coordinates on the way, not on node elements.
            if "geometry" in elem:
                for nid, pt in zip(elem["nodes"], elem["geometry"]):
                    coords[str(nid)] = (pt["lat"], pt["lon"])
            tags = elem.get("tags", {})
            highway = tags.get("highway")
            if highway in ALLOWED:
                refs = [str(n) for n in elem["nodes"]]
                ways.append((str(elem["id"]), highway, refs))

    membership: dict[str, int] = {}
    for _way_id, _highway, refs in ways:
        for ref in set(refs):
            membership[ref] = membership.get(ref, 0) + 1

    routing: set[str] = set()
    for way_id, highway, refs in ways:
        if len(refs) < 2:
            continue
        routing.add(refs[0])
        routing.add(refs[-1])
        for ref in refs:
            if membership.get(ref, 0) >= 2:
                routing.add(ref)

    graph = Graph()
    for ref in routing:
        lat, lon = coords[ref]
        graph.add_node(ref, lat, lon)

    for way_id, highway, refs in ways:
        last = refs[0]
        shape: list[tuple[float, float]] = [coords[last]]
        cost = 0.0
        for ref in refs[1:]:
            lat, lon = coords[ref]
            prev = shape[-1]
            cost += flat_distance(prev[0], prev[1], lat, lon)
            shape.append((lat, lon))
            if ref in routing and ref != last:
                graph.add_undirected(last, ref, cost, shape, way_id, highway)
                last = ref
                shape = [(lat, lon)]
                cost = 0.0
    return graph


def nearest_routing_node(
    graph: Graph, lat: float, lon: float):
    best_id = None
    best = float("inf")
    for node_id, (nlat, nlon) in graph.nodes.items():
        d = flat_distance(lat, lon, nlat, nlon)
        if d < best:
            best = d
            best_id = node_id
    if best_id is None:
        raise ValueError("graph has no routing nodes")
    return best_id, best


def dijkstra_equation(
    graph: Graph, start: str, goal: str):
    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, tuple[str, Edge]] = {}
    heap: list[tuple[float, str]] = [(0.0, start)]
    settled: set[str] = set()

    while heap:
        cost, node = heapq.heappop(heap)
        if node in settled:
            continue
        settled.add(node)
        if node == goal:
            break
        for edge in graph.adj[node]:
            if edge.to in settled:
                continue
            nxt = cost + edge.cost
            if nxt < dist.get(edge.to, float("inf")):
                dist[edge.to] = nxt
                prev[edge.to] = (node, edge)
                heapq.heappush(heap, (nxt, edge.to))

    if goal not in dist:
        return None

    # Walk predecessors back to the start, then reverse.
    nodes = [goal]
    line: list[tuple[float, float]] = []
    cursor = goal
    while cursor != start:
        parent, edge = prev[cursor]
        # edge.coords runs parent -> cursor, so prepend in reverse.
        line = edge.coords[:-1] + line
        nodes.append(parent)
        cursor = parent
    line.append(graph.nodes[goal])
    nodes.reverse()
    return dist[goal], nodes, line


def line_to_geojson(line: list[tuple[float, float]], meters: float, start: str, goal: str):
    return {
        "type": "Feature",
        "properties": {
            "length_m": round(meters, 1),
            "start_node": start,
            "goal_node": goal,
            "allowed": sorted(ALLOWED),
        },
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in line],
        },
    }


def dijkstra():
    parser = argparse.ArgumentParser(description="Dijkstra on JSON red-dotted footways")
    parser.add_argument("json")
    parser.add_argument("start_lat", type=float)
    parser.add_argument("start_lon", type=float)
    parser.add_argument("goal_lat", type=float)
    parser.add_argument("goal_lon", type=float)
    parser.add_argument("--out", default="routejson.geojson")
    args = parser.parse_args()

    graph = load_walk_graph(args.json)
    start, start_snap = nearest_routing_node(graph, args.start_lat, args.start_lon)
    goal, goal_snap = nearest_routing_node(graph, args.goal_lat, args.goal_lon)
    result = dijkstra_equation(graph, start, goal)
    if result is None:
        raise SystemExit(
            "no path: snapped start and goal are in different components "
            f"(start snap {start_snap:.1f} m, goal snap {goal_snap:.1f} m). "
            "A nearby click can land on a disconnected footway fragment."
        )

    meters, nodes, line = result
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(line_to_geojson(line, meters, start, goal), fh)
    print(f"routing nodes: {len(graph.nodes)}") #Change to something else, maybe raise instead of print
    print(f"snapped start {start}  -> goal {goal} ")
    print(f"path nodes: {len(nodes)}")
    print(f"length: {meters:.1f} m")
    print(f"wrote {args.out}")

if __name__ == "__main__":
    dijkstra()
