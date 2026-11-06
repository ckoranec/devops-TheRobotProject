import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
 
from dijkstra_json_blockage import (dijkstra_equation, flat_distance,
                                    load_walk_graph, nearest_routing_node)
from SIM_route import INTERVAL_S, SPEED_MPS, simulate


# Two routes A->D: short one via B (blocked by a gate), long one via C.
#   A(0,0) - B(0,.002) - D(0,.004)      <- B is a barrier node, removed
#   A      - C(.002,.002) - D           <- detour
def _map(tmp_path):
    n = lambda i, lat, lon, tags=None: {"type": "node", "id": i, "lat": lat, "lon": lon, **({"tags": tags} if tags else {})}
    way = lambda i, ids: {"type": "way", "id": i, "nodes": ids, "tags": {"highway": "footway"}}
    data = {"elements": [
        n(1, 39.0, -77.000), n(2, 39.0, -76.998, {"barrier": "gate", "foot": "no"}),
        n(3, 39.0, -76.996), n(4, 39.002, -76.998),
        way(10, [1, 2, 3]), way(11, [1, 4, 3]),
    ]}
    p = tmp_path / "gnu_map.json"
    p.write_text(json.dumps(data))
    return str(p)
 
def _route(tmp_path):
    graph, blocked = load_walk_graph(_map(tmp_path))
    graph.remove_nodes(blocked)
    s, _ = nearest_routing_node(graph, 39.0, -77.000)
    g, _ = nearest_routing_node(graph, 39.0, -76.996)
    return dijkstra_equation(graph, s, g)
 
def test_route_avoids_blocked_node(tmp_path):
    meters, nodes, line = _route(tmp_path)
    assert "2" not in nodes
    assert (39.002, -76.998) in line  # took the detour
 
def test_total_time_equals_distance_over_speed(tmp_path):
    meters, _, line = _route(tmp_path)
    updates, total = simulate(line)
    assert abs(total - meters) < 0.01
    assert abs(updates[-1]["t"] - meters / SPEED_MPS) < 0.001
 
def test_positions_follow_path_and_speed(tmp_path):
    _, _, line = _route(tmp_path)
    updates, _ = simulate(line)
    def dist_to_polyline(lat, lon):
        best = 1e9
        for (a, b) in zip(line, line[1:]):
            # project in local metres
            ky = 111320.0; kx = ky * math.cos(math.radians(lat))
            ax, ay = (a[1]-lon)*kx, (a[0]-lat)*ky
            bx, by = (b[1]-lon)*kx, (b[0]-lat)*ky
            dx, dy = bx-ax, by-ay
            t = 0 if dx == dy == 0 else max(0, min(1, -(ax*dx+ay*dy)/(dx*dx+dy*dy)))
            best = min(best, math.hypot(ax+t*dx, ay+t*dy))
        return best
    assert all(dist_to_polyline(u["lat"], u["lon"]) < 0.05 for u in updates)
    assert (updates[0]["lat"], updates[0]["lon"]) == tuple(round(x, 7) for x in line[0])
    assert (updates[-1]["lat"], updates[-1]["lon"]) == tuple(round(x, 7) for x in line[-1])
    steps = [flat_distance(a["lat"], a["lon"], b["lat"], b["lon"])
             for a, b in zip(updates, updates[1:-1])]
    # a path across a corner is shorter than the original path, never longer
    assert all(s <= SPEED_MPS * INTERVAL_S + 0.05 for s in steps)
    assert sorted(steps)[len(steps) // 2] > SPEED_MPS * INTERVAL_S - 0.01