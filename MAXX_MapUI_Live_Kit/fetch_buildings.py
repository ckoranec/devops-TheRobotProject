"""Fetch central-campus simple OSM building ways into a NEW GeoJSON file.

Run: python fetch_buildings.py --out data/buildings-new.geojson
The snapshot bundled with the kit means this is optional, not a demo prerequisite.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

# Small central-campus bbox keeps the API request bounded. This does not claim
# complete GMU coverage or handle OSM multipolygon building relations.
SOURCE = 'https://api.openstreetmap.org/api/0.6/map?bbox=-77.312,38.827,-77.299,38.835'


def convert_osm_xml(body):
    """Resolve node references into polygon coordinates; never invent outlines."""
    root = ET.fromstring(body)
    nodes = {n.attrib['id']: [float(n.attrib['lon']), float(n.attrib['lat'])]
             for n in root.findall('node')}
    features = []
    for way in root.findall('way'):
        tags = {t.attrib['k']: t.attrib['v'] for t in way.findall('tag')}
        if tags.get('building') in (None, 'no'):
            continue
        refs = [n.attrib['ref'] for n in way.findall('nd')]
        # GeoJSON polygon rings need a closed boundary with at least four positions.
        if len(refs) < 4 or refs[0] != refs[-1] or any(n not in nodes for n in refs):
            continue
        features.append({'type': 'Feature', 'properties': {
            'layer': 'buildings', 'osm_id': way.attrib['id'],
            'name': tags.get('name', 'OSM building ' + way.attrib['id']),
            'source': 'OpenStreetMap map API', 'data_mode': 'snapshot'},
            'geometry': {'type': 'Polygon', 'coordinates': [[nodes[n] for n in refs]]}})
    return features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Output exists. Choose a new filename; existing data is preserved.')
    try:
        request = Request(SOURCE, headers={'User-Agent': 'MAXX-Campus-Learning/1.0'})
        with urlopen(request, timeout=30) as response:
            features = convert_osm_xml(response.read())
        if not features:
            raise ValueError('No usable closed building polygons returned')
        result = {'type': 'FeatureCollection', 'features': features,
                  'attribution': '© OpenStreetMap contributors, ODbL',
                  'license_url': 'https://www.openstreetmap.org/copyright',
                  'metadata': {'source_url': SOURCE,
                    'downloaded_utc': datetime.now(timezone.utc).isoformat(),
                    'coverage': 'Central-campus simple building ways only; multipolygon relations omitted.'}}
        # Exclusive creation avoids destroying a reviewed working snapshot.
        with args.out.open('x', encoding='utf-8') as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        print(f'Saved {len(features)} OSM building outlines to {args.out}')
    except (OSError, ValueError, ET.ParseError) as error:
        raise SystemExit(f'Download failed: {error}. Keep the bundled working snapshot.')


if __name__ == '__main__':
    main()
