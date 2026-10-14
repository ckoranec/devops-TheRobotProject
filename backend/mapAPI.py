import os
import requests
import xml.etree.ElementTree as ET

URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "MAXXRobotProject-MapPrototype/0.1"}
OUTFILE = "gmu_map.xml"

QUERY = """
[out:xml][timeout:25];
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

    # Validate that it's well-formed XML with the expected root
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        print("Response was not valid XML.")
        return None

    if root.tag != "osm":
        print("Unexpected XML structure (root is not <osm>).")
        return None

    remark = root.find("remark")
    if remark is not None:
        print(f"Overpass warning: {remark.text}")

    return response.content

def save(content):
    try:
        with open(OUTFILE, "wb") as f:
            f.write(content)
        print(f"Wrote {len(content)} bytes to {os.path.abspath(OUTFILE)}")
    except OSError as e:
        print(f"Could not write {OUTFILE}: {e}")

if __name__ == "__main__":
    content = fetch()
    if content:
        save(content)