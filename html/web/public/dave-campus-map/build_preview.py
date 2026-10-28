"""Build/check a reproducible local GIS preview; never edit the shared router."""
import argparse  # Read build/check/download options from the terminal.
import hashlib  # Fingerprint bytes so filenames alone cannot imply freshness.
import importlib.util  # Load the existing backend as a read-only dependency.
import json  # Write GeoJSON and a small provenance manifest.
import os  # Replace an output only after the complete staged build succeeds.
import sys  # Register the imported module for its dataclass definitions.
import tempfile  # Stage generated outputs in a private temporary directory.
import xml.etree.ElementTree as ET  # Parse the public OSM building download.
from datetime import datetime, timezone  # Record an unambiguous build time.
from pathlib import Path  # Use portable paths.
from urllib.request import Request, urlopen  # Download only when explicitly requested.
from export_layers import convert, position, read_json  # Reuse tested validation/conversion.

HERE = Path(__file__).resolve().parent  # This script's frontend directory.
ROOT = HERE.parents[3]  # dave-campus-map → public → web → html → repository.
OUTPUTS = ('campus-layers.geojson', 'route-preview.geojson')  # Only these generated files are published.
MANIFEST = HERE/'preview-manifest.json'  # Commit this last, after both outputs exist.


def digest(path):  # Hash the actual file contents, not timestamps.
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()  # Return stable SHA-256 hex.


def within_root(path):  # Keep manifest URLs inside this checkout.
    result = Path(path).resolve()  # Resolve parent components and symlinks.
    if not result.is_relative_to(ROOT):  # An outside file cannot be fetched by the preview server.
        raise ValueError('Input must be inside the repository: ' + str(result))  # Explain the boundary.
    return result  # Return the normalized path.


def check():  # A check never rewrites generated output.
    manifest = read_json(MANIFEST)  # Missing manifest means a build is required.
    if manifest.get('crowd_sources_enabled') is not False:  # Require an explicitly crowd-free build.
        raise ValueError('Rebuild this preview with crowd sources disabled')  # Do not accept an older ambiguous manifest.
    for entry in manifest['inputs'] + manifest['outputs']:  # Check dependencies and generated files.
        path = within_root(ROOT/entry['path'])  # Normalize the recorded repository path.
        if digest(path) != entry['sha256']:  # Detect changed map, code, config or output.
            raise ValueError('STALE preview: ' + entry['path'] + '; rebuild it')  # Reject a misleading saved route.
    return manifest  # Let tests and the command report current counts.


def fetch_buildings(target):  # Supplemental data acquisition is separate from the team's highway query.
    url = 'https://api.openstreetmap.org/api/0.6/map?bbox=-77.314,38.825,-77.292,38.836'  # Campus/Overcup coverage, not all Fairfax.
    if target.exists():  # Do not destroy an input another teammate may have reviewed.
        raise FileExistsError('Building input exists; preserve it and deliberately choose a new snapshot')  # Require review before replacement.
    with urlopen(Request(url, headers={'User-Agent': 'MAXX-Map-Preview-Review/1.0'}), timeout=35) as response:  # Identify the application and bound the wait.
        body = response.read(30_000_001)  # Bound memory and detect oversized responses.
    if len(body) > 30_000_000:  # Do not accept a truncated map.
        raise ValueError('Building response exceeded 30 MB')  # Leave current files unchanged.
    xml = ET.fromstring(body)  # Parse the complete response before writing anything.
    nodes = {n.attrib['id']: position([float(n.attrib['lon']), float(n.attrib['lat'])]) for n in xml.findall('node')}  # Index real OSM coordinates.
    features = []  # Collect simple closed building ways only.
    for way in xml.findall('way'):  # Multipolygon relations require a future reviewed adapter.
        tags = {t.attrib['k']: t.attrib['v'] for t in way.findall('tag')}  # Read each way's tags.
        if tags.get('building') in {None, 'no'}:  # Ignore highways/nonbuildings in this supplemental source.
            continue  # Do not duplicate the canonical routing map.
        refs = [n.attrib['ref'] for n in way.findall('nd')]  # Keep the published ring order.
        if len(refs) < 4 or refs[0] != refs[-1] or any(n not in nodes for n in refs):  # Require a complete closed outline.
            continue  # Coverage limitations are reported below rather than fabricated.
        features.append({  # Preserve each real OSM outline's identity and geometry.
            'type': 'Feature',  # Standard GeoJSON feature envelope.
            'properties': {  # Keep only metadata used by the display/provenance.
                'name': tags.get('name', 'Building'),  # Use the published name if present.
                'osm_id': way.attrib['id'],  # Keep the stable map-object identifier.
                'source': url,  # Record the actual acquisition endpoint.
            },  # End metadata.
            'geometry': {  # Represent this simple closed building way.
                'type': 'Polygon',  # This adapter does not invent multipolygon relations.
                'coordinates': [[nodes[n] for n in refs]],  # Preserve the ordered outer ring.
            },  # End shape.
        })  # End this building feature.
    if not features:  # An empty or blocked download is not a successful building update.
        raise ValueError('No usable building outlines returned')  # Preserve the previous input.
    data = {  # Record the snapshot's source, time and limits alongside its shapes.
        'type': 'FeatureCollection',  # Standard supplemental input envelope.
        'source': url,  # Exact API request used for the download.
        'retrieved_at': datetime.now(timezone.utc).isoformat(),  # Retrieval time is not physical-obstacle measurement time.
        'coverage': 'Simple closed OSM ways in bbox; relations not converted',  # Do not imply universal building coverage.
        'features': features,  # The actual downloaded outlines.
    }  # End the downloaded dataset.
    target.parent.mkdir(parents=True, exist_ok=True)  # Create only the ignored local-input directory.
    with target.open('x', encoding='utf-8') as stream:  # Preserve any concurrently created input.
        json.dump(data, stream)  # Save compact data outside the reviewable code changes.
    print('Downloaded building outlines:', len(features))  # Report actual, time-dependent count.


def build(replace=False):  # One command regenerates BOTH layers and route from the same inputs.
    config_path = HERE/'preview-config.json'  # Keep source selection explicit and reviewable.
    config = read_json(config_path)  # Read only after the user intentionally runs a build.
    source = within_root(HERE/config['map'])  # Canonical default is repository gmu_map.json, with no dated fallback.
    buildings_path = within_root(HERE/config['buildings'])  # Explicit supplemental building dataset.
    deliveries_path = within_root(HERE/config['delivery'])  # Explicit business/planning targets.
    delivery = read_json(deliveries_path)  # Do not infer orders from roads or buildings.
    matches = [f for f in delivery['features'] if f.get('id') == config['destination_id']]  # Select exactly one declared target.
    if len(matches) != 1:  # Missing or duplicate target IDs make intent ambiguous.
        raise ValueError('destination_id must match exactly one delivery feature')  # Refuse to guess.
    layers = convert(read_json(source), source.name, read_json(buildings_path), delivery)  # Create all display categories.
    if not layers['counts']['buildings'] or not layers['counts']['delivery']:  # This review explicitly requires both inputs.
        raise ValueError('Supply buildings and delivery inputs before publishing the preview')  # No false completion with empty layers.
    backend = ROOT/'backend/dijkstra_json.py'  # Read the team's implementation without modifying it.
    spec = importlib.util.spec_from_file_location('team_preview_dijkstra', backend)  # Avoid importing another module with the same name.
    module = importlib.util.module_from_spec(spec)  # Create its module namespace.
    sys.modules[spec.name] = module  # Required by the backend's dataclass annotations.
    spec.loader.exec_module(module)  # __main__ guard prevents running its CLI.
    graph = module.load_walk_graph(str(source))  # Use the SAME canonical map as the layers.
    start_xy = position(config['start'])  # Validate the requested origin.
    goal_xy = position(matches[0]['geometry']['coordinates'])  # Use the explicit destination point.
    start, start_offset = module.nearest_routing_node(graph, start_xy[1], start_xy[0])  # Backend expects latitude first.
    goal, goal_offset = module.nearest_routing_node(graph, goal_xy[1], goal_xy[0])  # Record snapping instead of hiding it.
    if max(start_offset, goal_offset) > config['max_snap_m']:  # Do not attach a distant address by a straight connector.
        raise ValueError('Endpoint snap exceeds configured limit; inspect map coverage/entrances')  # Require data review.
    result = module.dijkstra_equation(graph, start, goal)  # Reuse the original algorithm exactly.
    if result is None or len(result[2]) < 2:  # A disconnected or zero-length trip is not a delivery route.
        raise ValueError('No connected nonzero route; previous outputs were preserved')  # Never draw a straight substitute.
    distance, nodes, line = result  # Backend returns meters, routing nodes and shaped geometry.
    route = module.line_to_geojson(line, distance, start, goal)  # Preserve every walkway/street shape vertex.
    route['properties'].update(  # Explain endpoints and the unchanged router's scope.
        crowd_sources_enabled=False,  # This distance-only preview does not ingest or weight crowd data.
        start_snap_m=round(start_offset, 1),  # Distance from requested origin to routing node.
        goal_snap_m=round(goal_offset, 1),  # Distance from target to routing node.
        status='saved graph candidate; access/closures not validated by this backend',  # Do not claim physical readiness.
    )  # End extra route metadata.
    dependencies = [source, buildings_path, deliveries_path, config_path, backend, HERE/'export_layers.py', Path(__file__).resolve()]  # Any changed dependency invalidates the saved result.
    inputs = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': digest(p)} for p in dependencies]  # Store exact provenance.
    if not replace and any((HERE/name).exists() for name in OUTPUTS + ('preview-manifest.json',)):  # Preserve old outputs unless replacement is explicit.
        raise FileExistsError('Generated output exists; review it, then use --replace')  # No automatic overwrite on a plain build.
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:  # Stage the complete build on the same filesystem.
        stage = Path(temporary)  # Use portable Path operations inside the staging directory.
        for name, data in zip(OUTPUTS, (layers, route)):  # Prepare both outputs before publishing either.
            with (stage/name).open('x', encoding='utf-8') as stream:  # Keep exclusive creation for staged files.
                json.dump(data, stream, allow_nan=False)  # Reject nonfinite output values.
        outputs = [{'path': (HERE/name).relative_to(ROOT).as_posix(), 'sha256': digest(stage/name)} for name in OUTPUTS]  # Fingerprint the staged results.
        manifest = {  # Build a small machine-readable provenance record.
            'schema': 1,  # Let the renderer reject unsupported future formats.
            'crowd_sources_enabled': False,  # No event/class/counter ingestion or heat-map jobs run here.
            'generated_at': datetime.now(timezone.utc).isoformat(),  # Actual build completion time.
            'map': source.relative_to(ROOT).as_posix(),  # Clearly identify the canonical input.
            'counts': layers['counts'],  # Report real exported category counts.
            'inputs': inputs,  # Fingerprint all routing/conversion dependencies.
            'outputs': outputs,  # Fingerprint the two generated artifacts.
        }  # End provenance record.
        with (stage/'preview-manifest.json').open('x', encoding='utf-8') as stream:  # Create the completion marker in staging.
            json.dump(manifest, stream)  # Store no credentials or customer contact details.
        for name in OUTPUTS + ('preview-manifest.json',):  # Publish the manifest LAST to expose interrupted/mixed builds.
            os.replace(stage/name, HERE/name)  # Explicit --replace permits replacing generated artifacts only.
    return check()  # Immediately confirm the published files match their dependencies.


def main():  # Keep imports side-effect free for tests.
    parser = argparse.ArgumentParser(description=__doc__)  # Explain the command to teammates.
    parser.add_argument('--check', action='store_true')  # Read-only freshness validation.
    parser.add_argument('--replace', action='store_true')  # Explicit permission to regenerate existing outputs.
    parser.add_argument('--fetch-buildings', action='store_true')  # Optional actual public building acquisition.
    args = parser.parse_args()  # Parse the command line once.
    if args.check and (args.replace or args.fetch_buildings):  # A read-only check must not trigger mutations/downloads.
        parser.error('--check cannot be combined with build/download options')  # Explain misuse clearly.
    try:  # Convert expected data/network/file failures into a clear terminal message.
        if args.fetch_buildings:  # Download only after the user explicitly asks.
            fetch_buildings(within_root(HERE/read_json(HERE/'preview-config.json')['buildings']))  # Preserve existing snapshots.
        manifest = check() if args.check else build(args.replace)  # Use one entry point for verification or regeneration.
        print('CURRENT preview:', manifest['map'], manifest['counts'])  # Report the exact source and real counts.
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:  # Catch expected input failures, not every programming exception.
        parser.exit(2, 'Preview build/check failed: ' + str(error) + '\n')  # Keep failure nonzero and understandable.


if __name__ == '__main__':  # Importing this module must not start a download/build.
    main()  # Run only from the user's terminal command.
