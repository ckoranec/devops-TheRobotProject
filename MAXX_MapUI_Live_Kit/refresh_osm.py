"""Retrieve actual current OSM map data once; never claim a live obstacle feed.

Run with server stopped: python refresh_osm.py --out-dir data/osm-current
An existing output directory is preserved. Choose a new directory for comparisons.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
from urllib.request import Request,urlopen
from fetch_buildings import convert_osm_xml
SOURCE='https://api.openstreetmap.org/api/0.6/map?bbox=-77.312,38.827,-77.299,38.835'


def convert(body):
    root=ET.fromstring(body)
    nodes={n.attrib['id']:{'lat':float(n.attrib['lat']),'lon':float(n.attrib['lon'])} for n in root.findall('node')}
    ways=[];features=[]
    for w in root.findall('way'):
        tags={t.attrib['k']:t.attrib['v'] for t in w.findall('tag')}
        refs=[n.attrib['ref'] for n in w.findall('nd')]
        if not tags.get('highway') or len(refs)<2 or any(n not in nodes for n in refs):continue
        geometry=[nodes[n] for n in refs]
        ways.append({'type':'way','id':int(w.attrib['id']),'nodes':list(map(int,refs)),'geometry':geometry,'tags':tags})
        layer='walkways' if tags['highway'] in {'footway','path','pedestrian','cycleway','steps'} else None
        if any(tags.get(k) in {'no','private'} for k in ('access','foot')):layer='restricted'
        if layer:features.append({'type':'Feature','properties':{'layer':layer,'name':tags.get('name','Unnamed walkway'),'osm_id':w.attrib['id'],'source':SOURCE},'geometry':{'type':'LineString','coordinates':[[p['lon'],p['lat']] for p in geometry]}})
    return {'elements':ways}, {'type':'FeatureCollection','features':features}, {'type':'FeatureCollection','features':convert_osm_xml(body),'attribution':'OpenStreetMap contributors, ODbL'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out-dir',type=Path,required=True);args=parser.parse_args()
    if args.out_dir.exists():raise SystemExit('Output directory exists; preserve it and choose a new directory.')
    with urlopen(Request(SOURCE,headers={'User-Agent':'MAXX-MapUI-Learning/1.0'}),timeout=30) as response:body=response.read()
    raw,layers,buildings=convert(body)
    if not raw['elements'] or not buildings['features']:raise ValueError('Incomplete map response; nothing installed')
    args.out_dir.mkdir(parents=True)
    for name,data in [('gmu_map_16OCT26.json',raw),('campus-layers.geojson',layers),('buildings.geojson',buildings)]:
        (args.out_dir/name).write_text(json.dumps(data),encoding='utf-8')
    source={'url':SOURCE,'retrieved_at':datetime.now(timezone.utc).isoformat(),'kind':'OSM snapshot retrieved from API, not a live robot/closure/crowd feed','bbox':[-77.312,38.827,-77.299,38.835],'building_count':len(buildings['features']),'path_feature_count':len(layers['features']),'license':'ODbL; OpenStreetMap contributors','schema_note':'Raw normalized map uses the legacy filename for adapter compatibility; collection date is retrieved_at.'}
    (args.out_dir/'SOURCE.json').write_text(json.dumps(source,indent=2))
    print(json.dumps(source,indent=2))

if __name__=='__main__':main()
