# importing libraries

import requests
import json
import os
import sys
import time
from datetime import datetime

# servers to query
servers = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

# Bounding box manually selected in Overpass Turbo
south = 38.823527
west = -77.331347
north = 38.836566
east = -77.292338

# Retrieve roads, pathways, barriers, and construction data within the GMU bounding box
# Include geometry coordinates for use by the robot's pathfinding algorithm

query = f"""
[out:json][timeout:120];
(
    way["highway"]({south},{west},{north},{east});
    node["barrier"]({south},{west},{north},{east});
    way["barrier"]({south},{west},{north},{east});
    node["construction"]({south},{west},{north},{east});
    way["construction"]({south},{west},{north},{east});
    way["landuse"="construction"]({south},{west},{north},{east});
    node["access"="no"]({south},{west},{north},{east});
    way["access"="no"]({south},{west},{north},{east});
);
out geom;
"""


headers = {"User-Agent": "MAXXRobotProject-MapPrototype/0.1"}

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Unique file name to prevent overwriting of previous json map
filename = f"gmu_map_{timestamp}.json"
temp_filename = "gmu_map.tmp"

def main():
    print("Starting GMU map update...")
    print("Preparing to contact Overpass servers...")

    # Allow three rounds of requests to recover from temp failures
    success = False
    max_attempts = 3

    # Retry server list until valid map data retrieved or attempts exhausted
    for attempt in range(max_attempts):
        print(f"Starting attempt {attempt + 1} of {max_attempts}")

        for url in servers:
            print(f"Trying server: {url}")

            try:
                response = requests.post(
                    url,
                    data={"data": query},
                    headers=headers,
                    timeout=120
                )
                # Display HTTP response status before validating the returned map data
                print(response.status_code)

                if response.ok:
                    data = response.json()

                    if "elements" not in data or "remark" in data:
                        print("Unexpected or incomplete API result.")
                        continue

                    for element in data["elements"]:
                        tags = element.get("tags", {})

                        if "note" in tags:
                            print(element["id"], tags["note"])

                    way_count = 0

                    for element in data["elements"]:
                        if element.get("type") == "way":
                            way_count += 1

                    if way_count == 0:
                        print("No ways found. Trying the next server.")
                        continue

                    print(f"Found {way_count} ways.")

                    incomplete_ways = 0

                    for element in data["elements"]:
                        if element.get("type") == "way":
                            nodes = element.get("nodes", [])
                            geometry = element.get("geometry", [])

                            if not nodes or not geometry or len(nodes) != len(geometry):
                                incomplete_ways += 1

                            elif any(

                                    not isinstance(point, dict)

                                    or not isinstance(point.get("lat"), (int, float))

                                    or not isinstance(point.get("lon"), (int, float))

                                    for point in geometry

                            ):
                                incomplete_ways += 1
                                print(f"Way {element['id']} contains invalid geometry coordinates.")
                                print("Invalid geometry:", geometry)
                                print("Way tags:", element.get("tags", {}))

                    print(f"Ways with incomplete geometry: {incomplete_ways}")

                    if incomplete_ways > 0:
                        print("Map data is incomplete. Trying another server.")
                        continue

                    try:
                        # Save a timestamped copy to preserve previous map versions
                        with open(filename, "w", encoding="utf-8") as file:
                            json.dump(data, file, indent=2)

                        # Write the updated map to a temp file before replacing the active map
                        with open(temp_filename, "w", encoding="utf-8") as file:
                            json.dump(data, file, indent=2)

                        # Replace the active map only after the temp map is fully written
                        # Keep the filename consistent for the robot's navigation algorithm
                        os.replace(temp_filename, "gmu_map.json")

                        print("Both map files saved successfully!")
                        success = True
                        break

                    except OSError as error:
                        print(f"Could not write {filename}: {error}")
                        break

                else:
                    print(f"Server returned HTTP {response.status_code}. Trying next server.")
                    continue

            except (requests.exceptions.RequestException, ValueError) as error:
                print(f"Request failed: {error}")
        if success:
            break

        if attempt < max_attempts - 1:
            print("No useable map saved. Waiting 30 seconds before retrying...")
            time.sleep(30)

    if not success:
        print("No usable map file was saved.")
        sys.exit(1)

    print("File location:", os.path.abspath(filename))
    print("File exists:", os.path.exists(filename))

main()