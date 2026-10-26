"""Visible map features derived from the supplied public OSM snapshot.

Delivery targets are attached to named real buildings and snapped to connected
walkway nodes. They are software-robot destinations, not surveyed entrances or
observed customer orders. Restrictions retain their actual OSM tag values.
"""
import json
from engine import ROOT,meters

DELIVERIES=['Hanover Hall','Brunswick Hall','Essex Hall','Grayson Hall','Carroll Hall','Dominion Hall']


def configure_public_places(campus):
    buildings={f['properties']['name']:f for f in campus.buildings}
    required=['Southside Dining']+DELIVERIES
    missing=[name for name in required if name not in buildings]
    if missing:raise ValueError('Named OSM buildings missing; review source coverage: '+', '.join(missing))
    used=set();places=[]
    for name in required:
        feature=buildings[name]
        ring=feature['geometry']['coordinates'][0]
        # Select a graph node nearest the ACTUAL polygon boundary, rather than
        # guessing an entrance from its building centroid or drawing a shortcut.
        node=min(campus.component-used,key=lambda n:(min(meters(campus.nodes[n],p) for p in ring),int(n)))
        anchor=min(ring,key=lambda p:meters(campus.nodes[node],p))
        offset=meters(campus.nodes[node],anchor)
        if offset>40:raise ValueError(f'{name}: nearest connected path is {offset:.1f}m away; review map data')
        used.add(node)
        places.append({'name':name,'node':node,'coordinates':campus.nodes[node],
            'requested_coordinates':anchor,'snap_meters':round(offset,1),
            'osm_building_id':feature['properties']['osm_id'],'source':'OpenStreetMap building geometry + connected path node',
            'mode':'planned_building_delivery','note':'Building-associated software delivery target; exact entrance not surveyed'})
    campus.base=places[0]['node'];campus.base_place=places[0]
    campus.stops=[{**p,'id':str(i)} for i,p in enumerate(places[1:],1)]


def add_access_restrictions(campus,data_dir):
    raw=json.loads((data_dir/'gmu_map_16OCT26.json').read_text(encoding='utf-8'))
    existing={f['properties'].get('osm_id') for f in campus.layers['features'] if f['properties'].get('layer')=='restricted'}
    for way in raw['elements']:
        tags=way.get('tags',{})
        rules={k:tags[k] for k in ('access','foot','vehicle','motor_vehicle') if k in tags}
        restricted=tags.get('access') in {'no','private','delivery','official','destination','permit','customers'} or tags.get('foot') in {'no','private'}
        if not restricted or str(way['id']) in existing or not way.get('geometry'):continue
        campus.layers['features'].append({'type':'Feature','properties':{'layer':'restricted','osm_id':str(way['id']),
            'name':tags.get('name','Access-tag restriction'),'access_tags':rules,
            'meaning':'Published access limitation; not an asserted current construction closure',
            'source':'OpenStreetMap snapshot'},'geometry':{'type':'LineString','coordinates':[[p['lon'],p['lat']] for p in way['geometry']]}})
    # Walkway tooltips also expose actual vehicle/foot tags without confusing
    # motor_vehicle=no with a closed pedestrian walkway.
    by_id={str(w['id']):w.get('tags',{}) for w in raw['elements']}
    for feature in campus.layers['features']:
        tags=by_id.get(str(feature['properties'].get('osm_id')), {})
        feature['properties']['access_tags']={k:tags[k] for k in ('access','foot','vehicle','motor_vehicle') if k in tags}
