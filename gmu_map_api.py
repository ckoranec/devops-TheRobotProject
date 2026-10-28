# importing libraries

import requests
import json
import os
import sys

from datetime import datetime

# servers to query
servers = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.maprva.org/api/interpreter"
]

# Bounding box manually selected in Overpass Turbo
south = 38.823527
west = -77.331347
north = 38.836566
east = -77.292338

# Query highways within the selected area

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
# coordinates of the area to query, area drawn manually in Overpass Turbo via bbox to include all of GMU's campus

headers = {"User-Agent": "MAXXRobotProject-MapPrototype/0.1"}

success = False

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

filename = f"gmu_map_{timestamp}.json"
temp_filename = "gmu_map.tmp"

for url in servers:
    print(f"Trying server: {url}")
# starts a loop to query the servers
    try:
        response = requests.post(
            url,
            data={"data": query},
            headers=headers,
            timeout=120
        )

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

            print(f"Ways with incomplete geometry: {incomplete_ways}")

            if incomplete_ways > 0:
                print("Map data is incomplete. Trying another server.")
                continue

            try:
                with open(filename, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=2)

                with open(temp_filename, "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=2)

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

if not success:
    print("No usable map file was saved.")
    sys.exit(1)

print("File location:", os.path.abspath(filename))
print("File exists:", os.path.exists(filename))