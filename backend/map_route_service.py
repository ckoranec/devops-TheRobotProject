"""Mission adapter reusing the team's repaired Graph, Edge and Dijkstra.

Road-inclusive routes are explicitly simulation previews, not robot permissions.
No requests, database access, server startup, or hardware commands occur here.
"""
from pathlib import Path
import hashlib
import json
import math
from backend.dijkstra_json import Graph, Edge, haversine, dijkstra

PICKUP = (38.8313333, -77.3079884)
DESTINATION = (38.8299577, -77.2951851)
PICKUP_NAME = 'Horizon Hall, 4475 Aquia Creek Lane'
DESTINATION_NAME = '4504 Overcup Court'
FOOTWAYS = {'footway', 'path', 'pedestrian'}
PREVIEW_ROADS = {'service', 'residential', 'living_street'}


def valid_point(point):
    return (len(point) == 2 and all(isinstance(x, (int, float)) and
            not isinstance(x, bool) and math.isfinite(x) for x in point)
            and -90 <= point[0] <= 90 and -180 <= point[1] <= 180)


def build_delivery_graph(source, preview_roads=False):
    """Retain every OSM geometry node for accurate endpoint snapping.

    Shared OSM IDs create connections. Nearby/unconnected paths are never joined.
    Explicit pedestrian direction is respected; motor-vehicle direction does not
    establish pedestrian/robot policy. All preview roads need operating review.
    """
    data = json.loads(Path(source).read_text(encoding='utf-8-sig'))
    if data.get('remark') or not isinstance(data.get('elements'), list):
        raise ValueError('Incomplete map source')
    allowed = FOOTWAYS | (PREVIEW_ROADS if preview_roads else set())
    positions = {}
    identities = set()
    for element in data['elements']:
        key = (element.get('type'), element.get('id'))
        if key in identities:
            raise ValueError('Duplicate OSM identity')
        identities.add(key)
        if element.get('type') == 'node':
            point = (element.get('lat'), element.get('lon'))
            if not valid_point(point):
                raise ValueError('Invalid node coordinates')
            positions[str(element['id'])] = point
    selected = []
    for way in data['elements']:
        if way.get('type') != 'way':
            continue
        tags = way.get('tags', {})
        if (tags.get('highway') not in allowed
                or tags.get('access') in {'no','private'}
                or tags.get('foot') in {'no','private'}
                or tags.get('closed') == 'yes'
                or tags.get('construction')
                or tags.get('area') == 'yes'):
            continue
        refs = [str(x) for x in way.get('nodes', [])]
        if len(refs) < 2:
            continue
        if 'geometry' in way:
            if len(refs) != len(way['geometry']):
                raise ValueError('Way geometry length mismatch')
            for ref, item in zip(refs, way['geometry']):
                point = (item.get('lat'), item.get('lon'))
                if not valid_point(point):
                    raise ValueError('Invalid inline coordinates')
                if ref in positions and haversine(*positions[ref], *point) > .1:
                    raise ValueError('Conflicting coordinates for a shared OSM node')
                positions[ref] = point
        if any(ref not in positions for ref in refs):
            raise ValueError('Missing way node coordinates')
        selected.append((way, refs))

    graph = Graph()
    way_tags = {}
    for way, refs in selected:
        identity = str(way['id'])
        tags = way['tags']
        way_tags[identity] = tags
        for ref in refs:
            graph.add_node(ref, *positions[ref])
        direction = str(tags.get('oneway:foot', 'no')).lower()
        for a, b in zip(refs, refs[1:]):
            pa, pb = positions[a], positions[b]
            cost = haversine(*pa, *pb)
            if a == b or cost <= .001:
                continue
            if direction not in {'-1','reverse'}:
                graph.adj[a].append(Edge(b, cost, [pa,pb], identity, tags['highway']))
            if direction not in {'yes','1','true'}:
                graph.adj[b].append(Edge(a, cost, [pb,pa], identity, tags['highway']))
    if not graph.nodes:
        raise ValueError('No eligible routing nodes')
    return graph, way_tags


def snap(graph, point, limit=35):
    node, distance = min(((node, haversine(*point, *ll))
                          for node,ll in graph.nodes.items()), key=lambda item:item[1])
    if distance > limit:
        raise ValueError(f'Endpoint is {distance:.1f} m from the network; limit {limit} m')
    return node, distance


def make_mission(source, pickup=PICKUP, destination=DESTINATION):
    if not valid_point(pickup) or not valid_point(destination):
        raise ValueError('Invalid requested endpoints')
    graph, way_tags = build_delivery_graph(source, preview_roads=True)
    start, start_snap = snap(graph, pickup)
    goal, goal_snap = snap(graph, destination)
    if start == goal:
        raise ValueError('Mission endpoints snap to the same node')
    outbound = dijkstra(graph, start, goal)
    inbound = dijkstra(graph, goal, start)
    if outbound is None or inbound is None:
        raise ValueError('No connected out-and-return route. No straight connectors added.')

    features = []
    review = set()
    for leg, result in [('outbound',outbound),('return',inbound)]:
        meters, nodes, line = result
        if not line or len(line) < 2:
            raise ValueError('Empty mission geometry')
        # Record the selected edge's source tags for review.
        for a,b in zip(nodes,nodes[1:]):
            edge = min((e for e in graph.adj[a] if e.to==b), key=lambda e:e.cost)
            if way_tags[edge.way_id].get('highway') in PREVIEW_ROADS:
                review.add(edge.way_id)
        features.append({'type':'Feature','properties':{'leg':leg,'length_m':meters},
                         'geometry':{'type':'LineString','coordinates':[[lon,lat] for lat,lon in line]}})
    mission = {
        'type':'FeatureCollection','features':features,
        'metadata':{
            'schema':'max-byte-mission-v1','simulated':True,
            'robot_navigation_approved':False,
            'source':Path(source).name,
            'map_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),
            'pickup':list(pickup),'pickup_name':PICKUP_NAME if tuple(pickup)==PICKUP else 'Selected pickup',
            'destination':list(destination),'destination_name':DESTINATION_NAME if tuple(destination)==DESTINATION else 'Selected destination',
            'start_node':start,'goal_node':goal,
            'pickup_snap_m':start_snap,'destination_snap_m':goal_snap,
            'outbound_m':outbound[0],'return_m':inbound[0],
            'total_m':outbound[0]+inbound[0],
            'road_ways_requiring_review':[{'id':key,'tags':way_tags[key]} for key in sorted(review)],
            'limitations':['Simulation only; robot road access not established.',
                           'Restricted polygons and barriers need independent validation.',
                           'Route ends at snapped map nodes, not a verified building entrance.']
        }
    }
    return mission, graph, way_tags


def main():
    import argparse
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser(description='Compute a simulated out-and-return mission with team Dijkstra')
    parser.add_argument('--source', default='gmu_map_16OCT26.json')
    parser.add_argument('--request', help='Optional endpoint request exported from the map planner')
    args = parser.parse_args()
    pickup, destination = PICKUP, DESTINATION
    if args.request:
        request = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
        if request.get('map_sha256') != hashlib.sha256(Path(args.source).read_bytes()).hexdigest():
            raise SystemExit('Source map changed; refresh/rebuild the planner first.')
        pickup, destination = request.get('pickup', []), request.get('destination', [])
    mission, _, _ = make_mission(args.source, pickup, destination)
    folder = Path('route-candidates')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True, exist_ok=False)
    target = folder/'mission-route.json'
    target.write_text(json.dumps(mission,indent=2,allow_nan=False),encoding='utf-8')
    print('Dijkstra mission candidate:', target)
    print('Outbound meters:',round(mission['metadata']['outbound_m'],1))
    print('Round trip meters:',round(mission['metadata']['total_m'],1))
    print('Simulated only; active website mission is unchanged by this verification command.')


if __name__ == '__main__':
    main()
