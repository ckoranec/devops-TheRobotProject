import requests
import json
import os

servers = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.maprva.org/api/interpreter"
]

query = "[out:json];(node(38.830,-77.310,38.831,-77.309);way(38.830,-77.310,38.831,-77.309););out body;"

headers = {"User-Agent": "MAXXRobotProject-MapPrototype/0.1"}

success = False

for url in servers:
    print(f"Trying server: {url}")

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