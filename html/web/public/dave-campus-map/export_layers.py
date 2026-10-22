""""Read the team's campus map and create a separate frontend export."""

import json
from pathlib import Path


def main():
    """Load source data, categorize features, and save our new export."""

    # __file__ is the location of this Python file.
    # parent gives its containing folder: dave-campus-map.
    lesson_folder = Path(__file__).resolve().parent

    # From this script's location, parents[4] reaches the repository root.
    repository_folder = Path(__file__).resolve().parents[4]

    # This existing team file is read only by our program.
    # Its spelling and capitalization must match the actual filename.
    source = repository_folder / "gmu_map_16OCT26.json"

    # Save our frontend export beside our own HTML and JavaScript.
    destination = lesson_folder / "campus-layers.geojson"

    # Preserve any export that already exists.
    if destination.exists():
        raise FileExistsError(
            f"Export already exists: {destination}. "
            "Inspect it before choosing a new output filename."
        )

    # Convert the source JSON text into Python dictionaries and lists.
    with source.open(encoding="utf-8") as file:
        data = json.load(file)

    # Stop with a helpful error if the expected element list is missing.
    if not isinstance(data.get("elements"), list):
        raise ValueError("Expected an 'elements' list in the source JSON.")

    # Map each node ID to its geographic position.
    # GeoJSON stores positions as [longitude, latitude].
    coordinates = {}

    for element in data["elements"]:
        if element["type"] == "node":
            coordinates[str(element["id"])] = [
                element["lon"],
                element["lat"],
            ]

    # These categories are for display, not robot-navigation approval.
    walkway_types = {
        "footway",
        "path",
        "pedestrian",
        "steps",
        "cycleway",
    }

    # Accumulate the GeoJSON features that our frontend will display.
    features = []

    def add_feature(element, category, geometry):
        """Add one shape with its display category and source details."""
        features.append({
            "type": "Feature",
            "properties": {
                "layer": category,
                "name": element.get("tags", {}).get("name", category),
                "osm_id": str(element["id"]),
                "source": source.name,
            },
            "geometry": geometry,
        })

    for element in data["elements"]:
        # This lesson converts OSM ways into lines or building polygons.
        if element["type"] != "way":
            continue

        tags = element.get("tags", {})

        # Some Overpass exports include coordinates directly on each way.
        if "geometry" in element:
            line = [
                [point["lon"], point["lat"]]
                for point in element["geometry"]
            ]
        else:
            # Other exports identify coordinates through separate nodes.
            references = [
                str(node)
                for node in element.get("nodes", [])
            ]

            if not references or any(
                node not in coordinates for node in references
            ):
                raise ValueError(
                    f"Missing coordinates for way {element['id']}"
                )

            line = [coordinates[node] for node in references]

        # A geographic line requires at least two positions.
        if len(line) < 2:
            continue

        geometry = {
            "type": "LineString",
            "coordinates": line,
        }

        if tags.get("highway") in walkway_types:
            add_feature(element, "walkways", geometry)

        # Access restrictions can overlap a walkway.
        # Keep them in a separate layer so viewers can toggle them.
        if (
            tags.get("access") in {"no", "private"}
            or tags.get("foot") == "no"
        ):
            add_feature(element, "restricted", geometry)

        # A simple building outline needs a closed coordinate ring.
        # First and last positions must match.
        if tags.get("building") not in {None, "no"}:
            if len(line) >= 4 and line[0] == line[-1]:
                add_feature(element, "buildings", {
                    "type": "Polygon",
                    "coordinates": [line],
                })

    # A FeatureCollection groups the exported shapes into one document.
    collection = {
        "type": "FeatureCollection",
        "source": source.name,
        "attribution": "OpenStreetMap contributors",
        "features": features,
    }

    # "x" creates a new file and refuses to overwrite an existing file.
    with destination.open("x", encoding="utf-8") as file:
        json.dump(collection, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"Created {destination}")

    # Report actual counts. Missing datasets remain empty.
    # This exporter does not invent delivery locations.
    for category in ("walkways", "buildings", "delivery", "restricted"):
        count = sum(
            feature["properties"]["layer"] == category
            for feature in features
        )
        print(f"{category}: {count}")


# Execute main only when this file is run as a program.
if __name__ == "__main__":
    main()