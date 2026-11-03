import argparse
import copy
import csv
import json
import re
from datetime import date
from pathlib import Path
 
from dijkstra_json_blockage import (
    BLOCKED_NODES,
    dijkstra_equation,
    line_to_geojson,
    load_walk_graph,
    nearest_routing_node,
)
 
FIELDS = [
    "location",
    "in data",
    "connected",
    "route length",
    "failure reason",
    "distance (m)",
]
 
 
def check_location(full, blocked, blocked_ids, origin_node, dest, max_snap):
    """Return (csv_row, route_or_None). route = (meters, line, goal_node).
 
    Checks run in this order, and the first failure wins:
      BAD_DATA, NOT_NEAR_PATH, NO_ROUTE, RESTRICTED_AREA
    """
    row = {
        "location": dest.get("name", "?"),
        "in data": "no",
        "connected": "no",
        "route length": "",
        "failure reason": "",
        "distance (m)": "",
    }
 
    try:
        lat, lon = float(dest["lat"]), float(dest["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("out of range")
    except (KeyError, TypeError, ValueError):
        row["failure reason"] = "BAD_DATA"
        return row, None
 
    node, snap = nearest_routing_node(full, lat, lon)
    row["distance (m)"] = round(snap, 1)
    if snap > max_snap:
        row["failure reason"] = "NOT_NEAR_PATH"
        return row, None
    row["in data"] = "yes"
 
    # Route on the full graph first: if this fails, it is a data problem.
    if dijkstra_equation(full, origin_node, node) is None:
        row["failure reason"] = "NO_ROUTE"
        return row, None
    row["connected"] = "yes"
 
    # Then route with the blocked nodes removed: if this fails, the only
    # way there goes through a restricted area.
    if node in blocked_ids or origin_node in blocked_ids:
        row["failure reason"] = "RESTRICTED_AREA"
        return row, None
    result = dijkstra_equation(blocked, origin_node, node)
    if result is None:
        row["failure reason"] = "RESTRICTED_AREA"
        return row, None
 
    meters, _nodes, line = result
    row["route length"] = round(meters, 1)
    return row, (meters, line, node)
 
 
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", required=True, help="Overpass JSON map file")
    ap.add_argument("--locations", default="locations.csv")
    ap.add_argument("--origin", required=True, help="name of the origin row in the locations file")
    ap.add_argument("--max-snap", type=float, default=30.0, help="metres (default 30)")
    stamp = date.today().strftime("%d%b%y").upper() 
    ap.add_argument("--out", default=f"results/results_{stamp}.csv")
    args = ap.parse_args()
 
    full = load_walk_graph(args.map)  # map is loaded once
    blocked_ids = set(BLOCKED_NODES)
    blocked = copy.deepcopy(full)
    blocked.remove_nodes(blocked_ids)
 
    with open(args.locations, newline="", encoding="utf-8") as fh:
        locs = list(csv.DictReader(fh))
 
    origin_row = next((r for r in locs if r.get("name") == args.origin), None)
    if origin_row is None:
        raise SystemExit(f"origin {args.origin!r} not found in {args.locations}")
    origin_node, origin_snap = nearest_routing_node(
        full, float(origin_row["lat"]), float(origin_row["lon"])
    )
    if origin_snap > args.max_snap:
        raise SystemExit(f"origin is {origin_snap:.1f} m from the nearest path (limit {args.max_snap} m)")
 
    rows = []
    geo_dir = Path(args.geojson_dir) if args.geojson_dir else None
    if geo_dir:
        geo_dir.mkdir(parents=True, exist_ok=True)
 
    for dest in locs:
        if dest.get("name") == args.origin:
            continue
        row, route = check_location(full, blocked, blocked_ids, origin_node, dest, args.max_snap)
        rows.append(row)
        if route and geo_dir:
            meters, line, goal = route
            feature = line_to_geojson(line, meters, origin_node, goal)
            feature["properties"]["name"] = dest["name"]
            safe = re.sub(r"[^\w-]+", "_", dest["name"])
            (geo_dir / f"{safe}.geojson").write_text(json.dumps(feature), encoding="utf-8")
 
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
 
    delivered = sum(1 for r in rows if not r["failure reason"])
    tested = len(rows)
    pct = (100 * delivered / tested) if tested else 0.0
    summary = f"data file: {args.map} | delivered {delivered}/{tested} ({pct:.0f}%)"
    print(summary)
 
    meta = {
        "map file": args.map,
        "run date": date.today().isoformat(),
        "origin": args.origin,
        "max snap (m)": args.max_snap,
        "tested": tested,
        "delivered": delivered,
        "summary": summary,
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
 
 
if __name__ == "__main__":
    main()