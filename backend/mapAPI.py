import os
import requests
import json

URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "MAXXRobotProject-MapPrototype/0.1"}
OUTFILE = "html/data/gmu_map.json"

QUERY = """
[out:json][timeout:25];
way["highway"](38.830,-77.310,38.831,-77.309);
out geom;
"""

def fetch():
    try:
        response = requests.post(URL, data={"data": QUERY}, headers=HEADERS, timeout=60)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("Server timed out - try again!")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Server returned an error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Could not connect to the server: {e}")
        return None

    # Validate that it's valid JSON
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Response was not valid JSON.")
        return None

    if "elements" not in data:
        print("Unexpected JSON structure (no 'elements' key).")
        return None

    remark = data.get("remark")
    if remark:
        print(f"Overpass warning: {remark}")

    return data

def save(data):
    try:
        with open(OUTFILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Wrote JSON data to {os.path.abspath(OUTFILE)}")
    except OSError as e:
        print(f"Could not write {OUTFILE}: {e}")

if __name__ == "__main__":
    data = fetch()
    if data:
        save(data)