"""Download a wider OSM network without replacing the working map."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

kit = Path(__file__).resolve().parent / "MAXX_MapUI_Live_Kit"
sys.path.insert(0, str(kit))

import refresh_osm
from engine import Campus, meters

# This rectangle includes Horizon Hall and the Overcup Court area.
bbox = "-77.314,38.824,-77.290,38.838"
source = "https://api.openstreetmap.org/api/0.6/map?bbox=" + bbox

# Reuse the kit's XML-to-GeoJSON conversion.
refresh_osm.SOURCE = source
print("Downloading wider map coverage...", flush=True)

request = Request(source, headers={"User-Agent": "MAXX-MapUI-Learning/1.0"})
with urlopen(request, timeout=45) as response:
    body = response.read()

raw, layers, buildings = refresh_osm.convert(body)
if not raw["elements"]:
    raise ValueError("Download contained no usable highway ways.")

# A unique folder preserves all existing datasets.
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
output = kit / "data" / ("overcup-" + stamp)
output.mkdir()

files = {
    "gmu_map_16OCT26.json": raw,
    "campus-layers.geojson": layers,
    "buildings.geojson": buildings,
    "SOURCE.json": {
        "url": source,
        "retrieved_at": stamp,
        "license": "OpenStreetMap contributors, ODbL",
        "note": "Downloaded map snapshot; not obstacle telemetry.",
    },
}
for name, content in files.items():
    (output / name).write_text(json.dumps(content), encoding="utf-8")

# Check the new network with the existing walkway-only router.
campus = Campus(output)
start_xy = [-77.30774144782609, 38.83143003478261]
goal_xy = [-77.295273904319, 38.830452983017]

start = min(campus.nodes, key=lambda n: meters(campus.nodes[n], start_xy))
goal = min(campus.nodes, key=lambda n: meters(campus.nodes[n], goal_xy))
route = campus.route(start, goal)

print("Saved:", output)
print("Start offset:", round(meters(campus.nodes[start], start_xy), 1), "m")
print("Destination offset:", round(meters(campus.nodes[goal], goal_xy), 1), "m")
print("Route nodes:", len(route) if route else "NO CONNECTED WALKWAY ROUTE")

# Explore a mixed walkway/road candidate in this process only.
# This does not edit engine.py or approve roads for robot operation.
import json
import engine

engine.ALLOWED = {
    "footway", "pedestrian", "path", "cycleway",
    "residential", "service",
}

# Use the fresh dataset we just downloaded.
folders = sorted((kit / "data").glob("overcup-*"))
campus = engine.Campus(folders[-1])

# Recalculate endpoint nodes using this expanded network.
start = min(
    campus.nodes,
    key=lambda n: meters(campus.nodes[n], start_xy),
)
goal = min(
    campus.nodes,
    key=lambda n: meters(campus.nodes[n], goal_xy),
)
route = campus.route(start, goal)

if route is None:
    print("No mixed-network candidate found in the fresh data.")
else:
    # GeoJSON requires coordinates in longitude, latitude order.
    candidate = {
        "type": "Feature",
        "properties": {
            "name": "Horizon Hall to Overcup Court",
            "status": "Mixed walkway/road candidate — review required",
            "destination_offset_m": round(
                meters(campus.nodes[goal], goal_xy), 1
            ),
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [campus.nodes[node] for node in route],
        },
    }

    output = Path(__file__).resolve().parent / "overcup_candidate.geojson"
    output.write_text(json.dumps(candidate, indent=2), encoding="utf-8")

    print("Mixed-network candidate:", len(route), "nodes")
    print("GeoJSON saved:", output)