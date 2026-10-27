"""Inspect the map dataset without changing it."""

import json
from pathlib import Path

# Locate the current map data inside our project.
project = Path(__file__).resolve().parent
data_file = (
    project / "MAXX_MapUI_Live_Kit" / "data"
    / "osm-current" / "gmu_map_16OCT26.json"
)

# Load JSON into Python dictionaries and lists.
with data_file.open(encoding="utf-8") as file:
    osm = json.load(file)

# Gather coordinates and find relevant named features.
points = []
for element in osm["elements"]:
    if element["type"] == "node":
        points.append((element["lat"], element["lon"]))

    for point in element.get("geometry", []):
        points.append((point["lat"], point["lon"]))

    name = element.get("tags", {}).get("name", "")
    if "horizon" in name.lower() or "overcup" in name.lower():
        print("Found:", element["type"], element["id"], name)

# Show the dataset boundaries.
if points:
    latitudes, longitudes = zip(*points)
    print("Latitude:", min(latitudes), "to", max(latitudes))
    print("Longitude:", min(longitudes), "to", max(longitudes))
else:
    print("No coordinates found.")

print("Inspection complete.")

# Convert our two street addresses into candidate coordinates.
from urllib.parse import urlencode
from urllib.request import urlopen

addresses = {
    "Start — Horizon Hall":
        "4475 Aquia Creek Lane, Fairfax, VA 22030",
    "Destination — Overcup Court":
        "4504 Overcup Court, Fairfax, VA 22032",
}

for label, address in addresses.items():
    print("\nLooking up:", label, flush=True)

    # Encode spaces and punctuation safely for the web request.
    query = urlencode({
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = (
        "https://geocoding.geo.census.gov/geocoder/"
        "locations/onelineaddress?" + query
    )

    try:
        # Wait at most 20 seconds for each address lookup.
        with urlopen(url, timeout=20) as response:
            result = json.load(response)

        matches = result["result"]["addressMatches"]

        if not matches:
            print("No match returned; location needs another source.")

        # Show every match so we can check the returned address.
        for match in matches:
            coordinates = match["coordinates"]
            print("Matched address:", match["matchedAddress"])
            print("Latitude:", coordinates["y"])
            print("Longitude:", coordinates["x"])

    except Exception as error:
        # Report a failed lookup instead of inventing coordinates.
        print("Lookup failed:", error)