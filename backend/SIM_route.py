from __future__ import annotations
 
import json
 
from dijkstra_json_blockage import (
    dijkstra_equation,
    flat_distance,
    load_walk_graph,
    nearest_routing_node,
)

SPEED_MPS = 6.7   # 15 mph
INTERVAL_S = 1.0  # seconds between position updates

def simulate(line, speed=SPEED_MPS, interval=INTERVAL_S):
    seg = [flat_distance(*line[i], *line[i + 1]) for i in range(len(line) - 1)]
    total = sum(seg)
    total_time = total / speed
 
    def fix(t):
        d = min(t * speed, total)
        i = 0
        while i < len(seg) - 1 and d > seg[i]:
            d -= seg[i]
            i += 1
        if not seg:
            lat, lon = line[0]
        else:
            f = d / seg[i] if seg[i] else 0.0
            lat = line[i][0] + f * (line[i + 1][0] - line[i][0])
            lon = line[i][1] + f * (line[i + 1][1] - line[i][1])
        return {"t": round(t, 3), "lat": round(lat, 7), "lon": round(lon, 7)}
 
    updates = []
    k = 0
    while k * interval < total_time:
        updates.append(fix(k * interval))
        k += 1
    updates.append(fix(total_time))  # always end exactly at the goal
    return updates, total

def write_updates(line, out_path, speed=SPEED_MPS, interval=INTERVAL_S):
    updates, total = simulate(line, speed, interval)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({
            "speed_mps": speed,
            "interval_s": interval,
            "total_distance_m": round(total, 2),
            "total_time_s": round(total / speed, 3),
            "updates": updates,
        }, fh, indent=1)
    return updates, total


def run(map_path, start_latlon, goal_latlon, out_path="positions.json"):
    graph, blocked = load_walk_graph(map_path)
    graph.remove_nodes(blocked)
    start, start_snap = nearest_routing_node(graph, *start_latlon)
    goal, goal_snap = nearest_routing_node(graph, *goal_latlon)
    print(f"start -> node {start} (snapped {start_snap:.1f} m)")
    print(f"goal  -> node {goal} (snapped {goal_snap:.1f} m)")
    if start == goal:
        raise SystemExit("start and goal snapped to the same node; pick points farther apart")
    result = dijkstra_equation(graph, start, goal)
    if result is None:
        raise SystemExit("no path between snapped start and goal")
    _meters, _nodes, line = result
    updates, total = write_updates(line, out_path)
    print(f"{len(updates)} updates, {total:.1f} m, {total / SPEED_MPS:.1f} s -> {out_path}")

if __name__ == "__main__":
    start = (float(input("Start lat: ")), float(input("Start lon: ")))
    goal = (float(input("Goal lat: ")), float(input("Goal lon: ")))
    run("gmu_map.json", start, goal, "positions.json")