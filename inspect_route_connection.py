"""Check the larger dataset for a connected delivery route."""

import sys
from pathlib import Path

# Allow this script to import the map kit's existing Python modules.
kit = Path(__file__).resolve().parent / "MAXX_MapUI_Live_Kit"
sys.path.insert(0, str(kit))

from engine import Campus, meters

# Load the larger supplied dataset, without changing the running map.
campus = Campus()

# Find Horizon Hall using its actual OSM building outline.
building = next(
    feature for feature in campus.buildings
    if feature["properties"].get("name") == "Horizon Hall"
)

# Use the average footprint position as a candidate, not an entrance.
ring = building["geometry"]["coordinates"][0][:-1]
start_xy = [
    sum(point[0] for point in ring) / len(ring),
    sum(point[1] for point in ring) / len(ring),
]

# Census address match; coordinates here use longitude, latitude.
goal_xy = [-77.295273904319, 38.830452983017]

# Find the nearest walkway nodes without forcing connectivity.
start = min(
    campus.nodes,
    key=lambda node: meters(campus.nodes[node], start_xy),
)
goal = min(
    campus.nodes,
    key=lambda node: meters(campus.nodes[node], goal_xy),
)

print("Horizon candidate:", start_xy)
print("Overcup candidate:", goal_xy)
print("Start offset:", round(meters(campus.nodes[start], start_xy), 1), "m")
print("Destination offset:", round(meters(campus.nodes[goal], goal_xy), 1), "m")

# Run the existing Dijkstra router against those nodes.
route = campus.route(start, goal)

if route is None:
    print("NO CONNECTED WALKWAY ROUTE in this dataset.")
else:
    print("Connected route found:", len(route), "nodes")