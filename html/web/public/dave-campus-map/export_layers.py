"""Convert explicit map/building/delivery inputs into display GeoJSON."""
import argparse  # Parse terminal options instead of hiding a dated filename.
import json  # Read and write the team's JSON/GeoJSON data.
import math  # Reject NaN and infinity before exporting coordinates.
from pathlib import Path  # Resolve paths consistently on Windows and Linux.


def position(value):  # Validate a GeoJSON longitude/latitude position.
    if not isinstance(value, (list, tuple)) or len(value) != 2:  # Require one pair.
        raise ValueError('Position must be [longitude, latitude]')  # Explain bad data.
    lon, lat = value  # GeoJSON uses longitude first.
    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in value):  # Reject nonnumbers.
        raise ValueError('Coordinates must be finite numbers')  # Avoid silent coercion.
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:  # Check geographic ranges.
        raise ValueError('Coordinate outside WGS84 ranges')  # Reject reversed/bad values.
    return [lon, lat]  # Return a JSON-compatible pair.


def read_json(path):  # Keep file reading in one small reusable function.
    return json.loads(Path(path).read_text(encoding='utf-8'))  # Decode UTF-8 JSON.


def collection_features(data, category):  # Validate supplemental GeoJSON inputs.
    if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):  # Require the expected schema.
        raise ValueError(category + ' input must be a FeatureCollection')  # Stop on wrong formats.
    result = []  # Collect validated display features.
    for feature in data['features']:  # Visit each supplied feature once.
        if feature.get('type') != 'Feature' or not isinstance(feature.get('geometry'), dict):  # Require a real GeoJSON feature.
            raise ValueError(category + ' contains an invalid feature')  # Avoid interpreting a partial record.
        geometry = feature['geometry']  # Read its geographic shape.
        if category == 'delivery':  # Delivery targets are explicit business input.
            if geometry['type'] != 'Point':  # Do not infer delivery areas from highways.
                raise ValueError('Delivery geometry must be Point')  # Explain schema mismatch.
            geometry = {'type': 'Point', 'coordinates': position(geometry['coordinates'])}  # Validate location.
        else:  # This small exporter supports simple building polygons.
            if geometry['type'] != 'Polygon':  # Relations/MultiPolygons need a separate reviewed adapter.
                raise ValueError('Building geometry must be Polygon')  # Do not drop unsupported geometry silently.
            rings = [[position(p) for p in ring] for ring in geometry['coordinates']]  # Validate all rings.
            if not rings or any(len(r) < 4 or r[0] != r[-1] for r in rings):  # A ring must be closed.
                raise ValueError('Building ring must be closed with at least four positions')  # Reject invalid outlines.
            geometry = {'type': 'Polygon', 'coordinates': rings}  # Preserve supplied holes.
        properties = dict(feature.get('properties') or {})  # Copy metadata, never modify the input.
        if not properties.get('name') or not properties.get('source'):  # Require traceable labels.
            raise ValueError(category + ' requires name and source properties')  # Name the missing contract.
        properties['layer'] = category  # Match the existing frontend category names.
        result.append({'type': 'Feature', 'properties': properties, 'geometry': geometry})  # Add the validated feature.
    return result  # Empty inputs remain honestly empty.


def convert(data, source_name, buildings=None, delivery=None):  # Pure conversion is easy to test.
    elements = data.get('elements')  # The routing source is normalized Overpass JSON.
    if not isinstance(elements, list):  # Distinguish it from other JSON formats.
        raise ValueError('Map input requires an elements list')  # Fail visibly on wrong source format.
    nodes = {str(e['id']): position([e['lon'], e['lat']]) for e in elements if e['type'] == 'node'}  # Index standalone nodes.
    features = []  # Build the new output without changing team data.
    for element in elements:  # Convert each OSM way once.
        if element['type'] != 'way':  # Node-only objects are not line/polygon features.
            continue  # Supplemental delivery points are handled separately.
        tags = element.get('tags', {})  # Untagged ways have no category.
        try:  # Node-reference inputs must resolve every coordinate.
            line = ([position([p['lon'], p['lat']]) for p in element['geometry']] if 'geometry' in element
                    else [nodes[str(n)] for n in element.get('nodes', [])])  # Support inline geometry or node references.
        except KeyError as error:  # Do not hide a missing node behind an unexplained dictionary error.
            raise ValueError(f"Missing coordinate data for way {element['id']}") from error  # Identify the affected feature.
        if len(line) < 2:  # A display line requires at least two points.
            continue  # Do not export degenerate lines.
        properties = {'name': tags.get('name', 'Unnamed walkway'), 'osm_id': str(element['id']), 'source': source_name}  # Preserve identity.
        geometry = {'type': 'LineString', 'coordinates': line}  # Default way shape.
        categories = []  # A restriction may overlap a walkway.
        if tags.get('highway') in {'footway', 'path', 'pedestrian', 'steps', 'cycleway'}:  # Display categories are not routing approval.
            categories.append('walkways')  # The existing green layer accepts these lines.
        if tags.get('access') in {'no', 'private'} or tags.get('foot') in {'no', 'private'}:  # Preserve explicit access restrictions.
            categories.append('restricted')  # Keep restrictions independently switchable.
            properties['access_tags'] = {k: tags[k] for k in ('access', 'foot', 'vehicle', 'motor_vehicle') if k in tags}  # Explain the tag evidence.
        for category in categories:  # Add each applicable display category.
            features.append({'type': 'Feature', 'properties': {**properties, 'layer': category}, 'geometry': geometry})  # Make a separate feature.
        if tags.get('building') not in {None, 'no'}:  # Buildings can be supplied by a future expanded upstream query.
            building = {  # Wrap a raw building way for the same validation as supplements.
                'type': 'FeatureCollection',  # Declare the supported GeoJSON envelope.
                'features': [{  # This way contributes one outline.
                    'type': 'Feature',  # Declare the feature shape.
                    'properties': {**properties, 'name': tags.get('name', 'Building')},  # Preserve identity and a readable label.
                    'geometry': {'type': 'Polygon', 'coordinates': [line]},  # A closed ring is validated below.
                }],  # End the single-building feature list.
            }  # End the temporary validation envelope.
            features.extend(collection_features(building, 'buildings'))  # Reject open outlines instead of inventing closure.
    features.extend(collection_features(buildings, 'buildings') if buildings is not None else [])  # Optional explicit supplement.
    features.extend(collection_features(delivery, 'delivery') if delivery is not None else [])  # Explicit targets, never guessed from highways.
    keys = set()  # Detect repeated OSM building identities across two input sources.
    for feature in features:  # Review identity only, not rounded coordinate guesses.
        p = feature['properties']  # Read the feature's metadata.
        key = (p['layer'], p.get('osm_id'))  # Category keeps walkway/restriction overlap valid.
        if key[1] and key in keys:  # A building present twice should not be counted twice.
            raise ValueError('Duplicate OSM feature: ' + str(key))  # Require a deliberate data merge.
        keys.add(key)  # Remember the exported identity.
    counts = {k: sum(f['properties']['layer'] == k for f in features) for k in ('walkways', 'buildings', 'delivery', 'restricted')}  # Report actual categories.
    return {'type': 'FeatureCollection', 'source': source_name, 'attribution': 'OpenStreetMap contributors; ODbL', 'counts': counts, 'features': features}  # Keep the existing renderer's schema.


def main():  # Provide a standalone converter as well as the reviewed bundle builder.
    parser = argparse.ArgumentParser(description=__doc__)  # Show useful --help text.
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[4]/'gmu_map.json')  # One declared default; no dated fallback.
    parser.add_argument('--buildings', type=Path)  # Optional building FeatureCollection.
    parser.add_argument('--delivery', type=Path)  # Optional delivery FeatureCollection.
    parser.add_argument('--out', type=Path, required=True)  # Require an intentional destination.
    args = parser.parse_args()  # Read the terminal options.
    result = convert(read_json(args.source), args.source.name, read_json(args.buildings) if args.buildings else None, read_json(args.delivery) if args.delivery else None)  # Convert explicit inputs.
    with args.out.open('x', encoding='utf-8') as stream:  # Preserve existing files, including against a check/create race.
        json.dump(result, stream, ensure_ascii=False)  # Write compact generated data, not thousands of hand-reviewed lines.
    print(json.dumps(result['counts']))  # Missing data remains visible.


if __name__ == '__main__':  # Importing this module must not write output.
    main()  # Execute only when explicitly run in the terminal.
