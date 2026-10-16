# importing libraries

import requests
import json
import os


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
way["highway"]({south},{west},{north},{east});
out geom;
"""
# coordinates of the area to query, area drawn manually in Overpass Turbo via bbox to include all of GMU's campus

headers = {"User-Agent": "MAXXRobotProject-MapPrototype/0.1"}

success = False

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
            incomplete_ways = 0

            for element in data["elements"]:
                if element["type"] == "way":
                    nodes = element["nodes"]
                    geometry = element.get("geometry", [])

                    if len(nodes) != len(geometry):
                        incomplete_ways += 1

            print(f"Ways with incomplete geometry: {incomplete_ways}")

            if incomplete_ways > 0:
                print("Map data is incomplete. Trying another server.")
                continue

            try:
                with open("gmu_map.json", "w", encoding="utf-8") as file:
                    json.dump(data, file, indent=2)

                print("Map data saved successfully!")
                success = True
                break

            except OSError as error:
                print(f"Could not write gmu_map.json: {error}")
                break

        elif response.status_code in (429, 406):
            print("Rate limited or refused. Retry later.")
            continue

        elif response.status_code in (400, 401, 403):
            print("Request rejected. Check query or permissions.")
            continue

        else:
            print(f"Server returned {response.status_code}")

    except (requests.exceptions.RequestException, ValueError) as error:
        print(f"Request failed: {error}")

if not success:
    print("No usable map file was saved.")

print("File location:", os.path.abspath("gmu_map.json"))
print("File exists:", os.path.exists("gmu_map.json"))