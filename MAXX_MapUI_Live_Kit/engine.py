"""Shek's integration area: GIS graph, route planning and shared robot simulator.
Only Python's standard library is required. All locations/closures/crowds used
for deliveries are demonstrations; this module never commands a real robot.
"""
from pathlib import Path
import heapq
import json
import math
import time
from datetime import datetime, timezone
from crowd_model import (effective_weight, prepare_points, density_at,
                         sample_polyline, edge_exposure, travel_seconds, validate_point)

ROOT = Path(__file__).resolve().parent
ALLOWED = {'footway', 'pedestrian', 'path', 'cycleway'}
SPEED_MPS = 1.2  # Demonstration assumption, not a campus-approved operating speed.


def meters(a, b):
    """Local planar distance; coordinates consistently use [longitude, latitude]."""
    return math.hypot((a[0]-b[0])*111320*math.cos(math.radians((a[1]+b[1])/2)),
                      (a[1]-b[1])*111320)


def edge_key(a, b):
    return '|'.join(sorted((a, b)))


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def crowd_weight(point, now):
    """Reuse the supplied model: intensity × confidence × exponential freshness."""
    return effective_weight(point, now)


class Campus:
    def __init__(self, data_dir=None):
        data_dir = Path(data_dir) if data_dir else ROOT/'data'
        raw = json.loads((data_dir/'gmu_map_16OCT26.json').read_text(encoding='utf-8'))
        self.nodes, self.adj, self.edges = {}, {}, {}
        self.rejected_ways = 0
        for way in raw['elements']:
            tags = way.get('tags', {})
            if way['type'] != 'way' or tags.get('highway') not in ALLOWED:
                continue
            # Access restrictions are hard exclusions, not small crowd penalties.
            if any(tags.get(k) in {'no', 'private'} for k in ('access', 'foot')):
                self.rejected_ways += 1
                continue
            if tags.get('area') == 'yes':
                continue  # A polygon boundary is not automatically a traversable route.
            for nid, pt in zip(way['nodes'], way['geometry']):
                nid = str(nid)
                self.nodes[nid] = [pt['lon'], pt['lat']]
                self.adj.setdefault(nid, {})
            ids = list(map(str, way['nodes']))
            for a, b in zip(ids, ids[1:]):
                length = meters(self.nodes[a], self.nodes[b])
                if a == b or length <= 0:
                    continue
                key = edge_key(a, b)
                self.edges[key] = {'a': a, 'b': b, 'meters': length,
                                   'name': tags.get('name', 'Unnamed walkway'),
                                   'way_id': str(way['id'])}
                # Two-way walking graph for this simulation. Direction/robot rules
                # must be independently reviewed before physical navigation.
                self.adj[a][b] = self.adj[b][a] = key
        self.base = min(self.nodes, key=lambda n: meters(self.nodes[n], [-77.3080074,38.8312819]))
        component, pending = {self.base}, [self.base]
        while pending:
            for n in self.adj[pending.pop()]:
                if n not in component:
                    component.add(n)
                    pending.append(n)
        self.component = component
        targets = [[-77.2946725,38.8296635],[-77.3068,38.8325],[-77.3047,38.8290],
                   [-77.3070,38.8287],[-77.3030,38.8310],[-77.3090,38.8330]]
        used = {self.base}
        self.stops = []
        for i, xy in enumerate(targets):
            node = min(component-used, key=lambda n: meters(self.nodes[n], xy))
            used.add(node)
            self.stops.append({'id': str(i+1), 'node': node,
                'name': f'Demo delivery {i+1}', 'coordinates': self.nodes[node],
                'requested_coordinates': xy, 'snap_meters': round(meters(self.nodes[node],xy),1),
                'mode': 'simulated', 'note': 'Graph stop; entrance and delivery permission unverified'})
        self.layers = json.loads((data_dir/'campus-layers.geojson').read_text(encoding='utf-8'))
        # Real supplemental OSM outlines are independent of robot connectivity.
        # If absent, report the missing category instead of inventing buildings.
        building_file = data_dir/'buildings.geojson'
        self.buildings = (json.loads(building_file.read_text(encoding='utf-8'))['features']
                          if building_file.exists() else [])
        for edge in self.edges.values():
            a,b = self.nodes[edge['a']], self.nodes[edge['b']]
            edge['samples'] = sample_polyline([(a[1],a[0]),(b[1],b[0])])

    def score(self, xy, crowds, now):
        prepared = prepare_points(crowds, now, now+.001)
        return density_at(xy[1], xy[0], prepared)

    def duration(self, a, b, crowds, now, prepared=None):
        """Length-weighted exposure along the edge; no extra cost at nodes."""
        edge = self.edges[self.adj[a][b]]
        if prepared is None:
            prepared = prepare_points(crowds, now, now+.001)
        exposure = edge_exposure(edge['samples'], prepared)
        return travel_seconds(edge['meters'], SPEED_MPS, exposure)

    def route(self, start, goal, blocked=(), crowds=(), now=None):
        """Dijkstra minimizes estimated seconds; blocked edges are never relaxed."""
        now = time.time() if now is None else now
        prepared = prepare_points(crowds, now, now+.001)
        best, previous, queue = {start:0}, {}, [(0,start)]
        while queue:
            cost, a = heapq.heappop(queue)
            if cost != best[a]:
                continue
            if a == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return list(reversed(path))
            for b,key in self.adj[a].items():
                if key in blocked:
                    continue
                candidate = cost + self.duration(a,b,crowds,now,prepared)
                if candidate < best.get(b,math.inf):
                    best[b],previous[b] = candidate,a
                    heapq.heappush(queue,(candidate,b))
        return None


class Simulation:
    def __init__(self, campus, clock=time.monotonic, wall=time.time):
        self.campus, self.clock, self.wall = campus, clock, wall
        self.revision = 0
        self.configure('1','clear',1)

    def configure(self, stop_id, scenario, rate):
        """A new scenario intentionally resets to base. All viewers share this run."""
        if scenario not in {'clear','closure','sealed','crowd','return-closure'}:
            raise ValueError('Unknown scenario')
        if rate not in (1,10):
            raise ValueError('Rate must be 1 or 10')
        stop = next((s for s in self.campus.stops if s['id']==str(stop_id)),None)
        if stop is None:
            raise ValueError('Unknown delivery')
        self.stop, self.scenario, self.rate = stop, scenario, rate
        self.blocked, self.return_blocked, self.crowds = set(), set(), []
        now = self.wall()
        baseline = self.campus.route(self.campus.base,stop['node'])
        if scenario == 'sealed':
            self.blocked = set(self.campus.adj[stop['node']].values())
        elif scenario == 'closure':
            # Prefer an edge whose removal still leaves an alternative route.
            keys = [edge_key(a,b) for a,b in zip(baseline,baseline[1:])]
            for key in keys[len(keys)//3:] + keys[:len(keys)//3]:
                self.blocked = {key}
                if self.campus.route(self.campus.base,stop['node'],self.blocked):
                    break
        elif scenario == 'crowd':
            # Three synthetic sources show overlapping intensity and confidence.
            xy = self.campus.nodes[baseline[len(baseline)//2]]
            for i,offset,intensity,confidence in [(1,0,.95,.8),(2,.0005,.8,.6),(3,-.0004,.4,.5)]:
                self.crowds.append(validate_point({
                    'id':f'class-change-demo-{i}', 'name':f'Simulated crowd source {i}',
                    'kind':'class' if i==1 else 'event', 'data_mode':'simulated',
                    'lat':xy[1]+offset, 'lon':xy[0]+offset, 'radius_m':100,
                    'weight':intensity, 'confidence':confidence, 'half_life_minutes':60,
                    'starts_at':iso(now-1), 'ends_at':iso(now+3600),
                    'updated_at':iso(now), 'source':'SIMULATED class-change/event scenario'}))
        self.path = self.campus.route(self.campus.base,stop['node'],self.blocked,self.crowds,now)
        self.outbound = self.path or []
        self.return_blocked = set(self.blocked)
        self.return_path = list(reversed(self.outbound))
        self.return_kind = 'exact retrace'
        if scenario == 'return-closure':
            # A known closure applies to the return planning snapshot only. Pick
            # a reversed edge that can be avoided, without resetting mid-trip.
            keys = [edge_key(a,b) for a,b in zip(self.outbound,self.outbound[1:])]
            for key in keys[len(keys)//3:] + keys[:len(keys)//3]:
                self.return_blocked = {key}
                alternative = self.campus.route(stop['node'],self.campus.base,
                                                 self.return_blocked,self.crowds,now)
                if alternative:
                    self.return_path = alternative
                    self.return_kind = 'rerouted return'
                    break
            else:
                self.return_path = []
                self.return_kind = 'unavailable return'
        assert all(edge_key(a,b) not in self.return_blocked
                   for a,b in zip(self.return_path,self.return_path[1:]))
        self.trip = self.outbound + self.return_path[1:] if self.outbound and self.return_path else []
        self.weighted_points = prepare_points(self.crowds,now,now+.001)
        self.weighted_nodes = []
        for node,xy in self.campus.nodes.items():
            score = density_at(xy[1],xy[0],self.weighted_points)
            if score > .001:
                self.weighted_nodes.append({'node_id':node,'coordinates':xy,'score':round(score,6)})
        self.planned_at = iso(now)
        self.segment_seconds, self.segment_meters = [], []
        for a,b in zip(self.trip,self.trip[1:]):
            self.segment_seconds.append(self.campus.duration(a,b,self.crowds,now))
            self.segment_meters.append(self.campus.edges[edge_key(a,b)]['meters'])
        self.out_seconds = sum(self.segment_seconds[:max(0,len(self.outbound)-1)])
        self.total_seconds = sum(self.segment_seconds)
        self.elapsed = 0.0
        self.running = False
        self.last = self.clock()
        self.revision += 1
        return self.snapshot()

    def tick(self):
        now = self.clock()
        if self.running:
            self.elapsed = min(self.total_seconds,self.elapsed+(now-self.last)*self.rate)
            if self.elapsed >= self.total_seconds:
                self.running = False
        self.last = now

    def action(self, action):
        if action not in {'start','pause','reset'}:
            raise ValueError('Unknown action')
        self.tick()
        if action == 'start' and self.trip and self.elapsed < self.total_seconds:
            self.running = True
        elif action == 'pause':
            self.running = False
        elif action == 'reset':
            self.elapsed, self.running = 0.0, False
        return self.snapshot()

    def snapshot(self):
        self.tick()
        xy = self.campus.nodes[self.campus.base]
        elapsed, traveled = self.elapsed, 0.0
        for i,seconds in enumerate(self.segment_seconds):
            if elapsed >= seconds:
                elapsed -= seconds
                traveled += self.segment_meters[i]
                xy = self.campus.nodes[self.trip[i+1]]
            else:
                a,b = self.campus.nodes[self.trip[i]],self.campus.nodes[self.trip[i+1]]
                fraction = elapsed/seconds
                xy = [a[0]+fraction*(b[0]-a[0]),a[1]+fraction*(b[1]-a[1])]
                traveled += self.segment_meters[i]*fraction
                break
        phase = 'unavailable' if not self.trip else ('complete' if self.elapsed>=self.total_seconds else
                 ('outbound' if self.elapsed<self.out_seconds else 'returning'))
        remaining = (self.out_seconds if phase=='outbound' else self.total_seconds)-self.elapsed
        # In 10x mode ETA is explicitly wall/demo time. Model travel seconds are
        # supplied separately so the speed-up cannot be mistaken for robot speed.
        eta = max(0,remaining)/self.rate if self.trip else None
        return {'robot_id':'SIM-01','mode':'simulated','coordinates':xy,
            'timestamp':datetime.fromtimestamp(self.wall(),timezone.utc).isoformat(),
            'running':self.running,'phase':phase,'revision':self.revision,
            'stop':self.stop,'scenario':self.scenario,'rate':self.rate,
            'eta_seconds':eta,'eta_travel_seconds':max(0,remaining) if self.trip else None,
            'eta_target':'delivery' if phase=='outbound' else 'base',
            'traveled_meters':round(traveled,1),'total_meters':round(sum(self.segment_meters),1),
            'outbound_seconds':self.out_seconds,'total_seconds':self.total_seconds,
            'outbound':[self.campus.nodes[n] for n in self.outbound],
            'return_route':[self.campus.nodes[n] for n in self.return_path],
            'return_kind':self.return_kind, 'planned_at':self.planned_at,
            'weighted_points':self.weighted_points,'weighted_nodes':self.weighted_nodes,
            'forecast_return_blocked':[{'id':k,'coordinates':[self.campus.nodes[self.campus.edges[k]['a']],
                         self.campus.nodes[self.campus.edges[k]['b']]]} for k in sorted(self.return_blocked-self.blocked)],
            'blocked':[{'id':k,'coordinates':[self.campus.nodes[self.campus.edges[k]['a']],
                         self.campus.nodes[self.campus.edges[k]['b']]]} for k in sorted(self.blocked)],
            'crowds':self.crowds,'message':'No valid route; robot stays at base.' if not self.trip else
                f'Outbound avoids current closures; {self.return_kind} avoids return closures. Graph check only.'}
