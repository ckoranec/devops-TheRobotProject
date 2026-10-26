# Complete application source - MapUI Visual Update 2

Each heading is the exact editor file path relative to the kit root. Run commands in Terminal. Actual datasets and vendored Leaflet are bundled as files.

## Install.ps1

```powershell
# Optional repository installation. A standalone extracted copy already runs.
param([Parameter(Mandatory=$true)][string]$Repository)
$ErrorActionPreference = 'Stop'
$RepoPath = (Resolve-Path -LiteralPath $Repository).Path
if (-not (Test-Path -LiteralPath (Join-Path $RepoPath '.git'))) {
    throw 'Choose the root of your existing Git repository.'
}
$Branch = & git -C $RepoPath branch --show-current
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the repository branch.' }
if ($Branch -ne 'MapUI') {
    throw 'This optional installer requires the MapUI branch. Review local work before switching.'
}
$Remote = & git -C $RepoPath remote get-url origin
if ($LASTEXITCODE -ne 0 -or $Remote -notmatch '[:/]ckoranec/devops-TheRobotProject(\.git)?$') {
    throw 'Origin must be ckoranec/devops-TheRobotProject.'
}
$Destination = Join-Path $RepoPath 'MAXX_MapUI_Live_Kit'
if (Test-Path -LiteralPath $Destination) {
    throw 'Destination exists. Preserve and compare it; nothing has been overwritten.'
}
# Copy only into a NEW folder. Never modify team map/backend files or run Git writes.
New-Item -ItemType Directory -Path $Destination | Out-Null
Get-ChildItem -LiteralPath $PSScriptRoot -Force | Where-Object {
    $_.Name -notin @('__pycache__', '.venv', '.idea', 'runtime')
} | Copy-Item -Destination $Destination -Recurse
Write-Host "Added demo kit to: $Destination"
Write-Host 'Run server.py from that folder. No commit, push, merge or deployment was performed.'
```

## START_PHONE_DEMO.cmd

```bat
@echo off
cd /d "%~dp0"
echo Connect phones to the same trusted Wi-Fi, then use the laptop IPv4 address.
ipconfig
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py --host 0.0.0.0
) else (
  python server.py --host 0.0.0.0
)
pause
```

## START_SIMULATION.cmd

```bat
@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py --mode simulation --port 8004
) else (
  python server.py --mode simulation --port 8004
)
pause
```

## START_WINDOWS.cmd

```bat
@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
pause
```

## crowd_model.py

```python
"""Weighted crowd points -> spatial field -> route-edge time costs.

These are transparent demonstration heuristics, NOT calibrated pedestrian counts.
Routing nodes retain position/identity. We do not add a second cost at the nodes.
"""
import math
from datetime import datetime

METERS_PER_DEGREE = 111320.0


def timestamp(value):
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("A crowd timestamp needs Z or an explicit UTC offset.")
    return date.timestamp()


def distance_m(lat1, lon1, lat2, lon2):
    """Campus-scale metric approximation, matching the team's distance convention."""
    x = (lon2 - lon1) * METERS_PER_DEGREE * math.cos(math.radians((lat1 + lat2) / 2))
    y = (lat2 - lat1) * METERS_PER_DEGREE
    return math.hypot(x, y)


def validate_point(raw):
    """Normalize one JSON/CSV record; reject ambiguous or nonfinite inputs early."""
    if not isinstance(raw, dict):
        raise ValueError("Each crowd point must be a JSON object or CSV row.")
    # Publish only known public-safe schema fields, not arbitrary extra CSV/JSON
    # columns a source owner may have included. Names/source still need review.
    allowed = ("id", "name", "source", "kind", "data_mode", "lat", "lon", "radius_m",
               "weight", "confidence", "half_life_minutes", "starts_at", "ends_at", "updated_at")
    point = {key: raw.get(key) for key in allowed}
    for name in ("id", "name", "source"):
        if not isinstance(point.get(name), str) or not point[name].strip():
            raise ValueError("Crowd point requires " + name)
    point["id"] = str(point["id"])
    if point.get("kind") not in {"class", "event", "manual"}:
        raise ValueError("Crowd kind must be class, event or manual.")
    if point.get("data_mode") not in {"simulated", "predicted", "observed"}:
        raise ValueError("Crowd data_mode must describe its source, not imply live observation.")
    for field in ("lat", "lon", "radius_m", "weight", "confidence", "half_life_minutes"):
        point[field] = float(point[field])
        if not math.isfinite(point[field]):
            raise ValueError("Crowd numbers must be finite: " + field)
    if not (-90 <= point["lat"] <= 90 and -180 <= point["lon"] <= 180):
        raise ValueError("Crowd coordinates are outside the geographic range.")
    if not (1 <= point["radius_m"] <= 500 and 0 <= point["weight"] <= 1 and
            0 <= point["confidence"] <= 1 and 1 <= point["half_life_minutes"] <= 10080):
        raise ValueError("Radius, weight, confidence or half-life is outside its allowed range.")
    if timestamp(point["ends_at"]) <= timestamp(point["starts_at"]):
        raise ValueError("Crowd end must follow start.")
    timestamp(point["updated_at"])
    return point


def effective_weight(point, at):
    """Weight fades with age, and applies only inside the stated active window.

    A future updated_at has age zero (clock skew is visible in original metadata).
    It does not increase confidence above one or activate an inactive point.
    """
    if not timestamp(point["starts_at"]) <= at < timestamp(point["ends_at"]):
        return 0.0
    age_seconds = max(0.0, at - timestamp(point["updated_at"]))
    freshness = 2 ** (-age_seconds / (point["half_life_minutes"] * 60))
    return point["weight"] * point["confidence"] * freshness


def prepare_points(points, start, end):
    """Peak influence overlapping a planning window, conservative within that window.

    For a point that starts during the window, evaluate at its start. Because its
    freshness decays monotonically, this is its maximum during the overlap.
    """
    prepared = []
    for point in points:
        at = max(start, timestamp(point["starts_at"]))
        if at >= min(end, timestamp(point["ends_at"])):
            continue
        weight = effective_weight(point, at)
        if weight > 0:
            prepared.append({**point, "effective_weight": weight})
    return prepared


def density_at(lat, lon, prepared):
    """Bounded relative crowd index, 0..1, with quadratic distance falloff.

    Combine overlaps as 1 - product(1 - contribution). This saturates at one.
    It is an engineering score, not a probability or a people-per-square-meter unit.
    Duplicate record IDs are rejected by the importer before this is called.
    """
    remaining = 1.0
    for point in prepared:
        d = distance_m(lat, lon, point["lat"], point["lon"])
        kernel = max(0.0, 1.0 - d / point["radius_m"]) ** 2
        remaining *= 1.0 - point["effective_weight"] * kernel
    return min(1.0, max(0.0, 1.0 - remaining))


def sample_polyline(coords, spacing_m=10):
    """Return length-weighted segment MIDPOINTS; catch crowds between routing nodes.

    The input is [(latitude, longitude), ...]. Each sample represents a short
    stretch of the original walkway. No extra nodes are inserted in the team graph.
    """
    samples = []
    for a, b in zip(coords, coords[1:]):
        length = distance_m(*a, *b)
        if length <= 0:
            continue
        count = max(1, math.ceil(length / spacing_m))
        for i in range(count):
            fraction = (i + 0.5) / count
            samples.append((a[0] + fraction * (b[0] - a[0]),
                            a[1] + fraction * (b[1] - a[1]), length / count))
    return samples


def edge_exposure(samples, prepared):
    length = sum(part_length for _, _, part_length in samples)
    if not prepared or length <= 0:
        return 0.0
    return sum(density_at(lat, lon, prepared) * part_length
               for lat, lon, part_length in samples) / length


def travel_seconds(length_m, speed_mps, exposure):
    if speed_mps <= 0 or not 0 <= exposure <= 1:
        raise ValueError("Speed must be positive and exposure must be 0..1.")
    # A fully exposed edge takes four times its uncongested demonstration time.
    # This coefficient is tunable and requires calibration before real-world use.
    return length_m / speed_mps * (1 + 3 * exposure)
```

## engine.py

```python
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
```

## fetch_buildings.py

```python
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
```

## lessons/01_hello.py

```python
"""Lesson 1: run a Python editor file; this does not start the web server."""
# print writes a message to the Run/Terminal output, not onto a web page.
print('MAXX Bytes — David and Shek')
# A dictionary groups named fields, like one incoming telemetry record.
position = {'robot_id': 'SIM-01', 'longitude': -77.308, 'latitude': 38.831}
print(position)
```

## lessons/02_eta.py

```python
"""Lesson 2: distinguish meters, model seconds and demo playback seconds."""
# Units matter: meters divided by meters/second produces seconds.
distance_m = 120
speed_mps = 1.2
travel_seconds = distance_m / speed_mps
# An accelerated clock shortens presentation time, not the modeled route.
playback_rate = 10
print('Model travel seconds:', travel_seconds)  # 100 seconds
print('10x presentation seconds:', travel_seconds / playback_rate)  # 10 seconds
```

## lessons/03_weighted_point.py

```python
"""Lesson 3: use the SAME crowd model as the running application."""
import sys
from pathlib import Path
# Running a lesson directly puts lessons/ on the import path. Add its parent.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crowd_model import validate_point, timestamp, effective_weight

# These fixed dates make the exercise reproducible on any day.
point = validate_point({
    'id': 'practice-1', 'name': 'Practice entrance', 'source': 'SIMULATION',
    'kind': 'class', 'data_mode': 'simulated',
    'lat': 38.831, 'lon': -77.307, 'radius_m': 100,
    'weight': 0.8, 'confidence': 0.5, 'half_life_minutes': 60,
    'starts_at': '2026-10-27T09:00:00Z', 'ends_at': '2026-10-27T13:00:00Z',
    'updated_at': '2026-10-27T10:00:00Z',
})
now = timestamp('2026-10-27T10:00:00Z')
# Intensity .8 times confidence .5 gives .4 at update time.
print('Initial effective weight:', effective_weight(point, now))
# Freshness halves after one half-life: .4 becomes .2.
print('One hour later:', effective_weight(point, now + 3600))
```

## lessons/04_route_check.py

```python
"""Lesson 4: route validity is a graph check, not a visual guess."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Campus, Simulation, edge_key

campus = Campus()  # Read the bundled team graph and building snapshot.
robot = Simulation(campus)
state = robot.configure('2', 'closure', 1)
# zip pairs adjacent route nodes. Every pair must avoid a closed edge.
valid = all(edge_key(a, b) not in robot.blocked
            for a, b in zip(robot.outbound, robot.outbound[1:]))
print('Outbound avoids closure:', valid)
print('Return kind:', state['return_kind'])
print('Round-trip meters:', state['total_meters'])
```

## lessons/05_public_sources.py

```python
"""Read actual cached source metadata; never submit fictional observations."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from public_sources import PublicSources

# This reads successful prior source responses. For a real network refresh run
# python refresh_sources.py from Terminal; that command may take a few seconds.
cache=Path(__file__).resolve().parents[1]/'data/public-cache'
for name,item in PublicSources(cache).snapshot().items():
    print(name, 'fresh:', item['fresh'], 'source:', item['url'])
    print('Successful fetch:', item.get('fetched_at'), 'error:', item.get('error'))
    if name=='events':
        for event in item.get('data') or []:
            print(event['title'],event['starts_at'],event['location'])
```

## live_state.py

```python
"""Live LOCAL staff reports. No generated coordinates, crowds or closures.

A fresh HTTP response is not necessarily a fresh observation. Preserve both
observation and receipt times, reject older positions and stop showing ETA when
position data is stale. Operator reports remain on this laptop.
"""
import json
import math
import os
import time
import threading
from functools import wraps
from pathlib import Path
from engine import meters, edge_key, iso
from crowd_model import validate_point, prepare_points, density_at, timestamp

POSITION_TTL = 30
SNAP_LIMIT_M = 30


def number(value, low, high, name):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be finite and within {low}..{high}')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f'{name} requires 1..200 characters')
    return value.strip()


def coordinates(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Coordinates must be [longitude, latitude]')
    return [number(value[0], -180, 180, 'longitude'), number(value[1], -90, 90, 'latitude')]


def synchronized(method):
    """Serialize readers/writers so a phone report cannot race route calculation."""
    @wraps(method)
    def wrapped(self,*args,**kwargs):
        with self.lock:
            return method(self,*args,**kwargs)
    return wrapped


class LiveState:
    def __init__(self, campus, path=None, clock=time.time):
        self.lock=threading.RLock()
        self.campus, self.path, self.clock = campus, Path(path) if path else None, clock
        self.data = {'position': None, 'places': {}, 'closures': {}, 'crowds': {}, 'revision': 0}
        if self.path and self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
        # Refuse stale graph identities rather than silently route from different places.
        if any(p['node'] not in campus.component for p in self.data['places'].values()):
            raise ValueError('Saved places are outside this map graph; preserve runtime file and reverify places with the original map.')
        if any(k not in campus.edges for r in self.data['closures'].values() for k in r['edge_ids']):
            raise ValueError('Saved closures use another map graph; review reports before changing snapshots.')
        # Data ages by original timestamps after restart; startup is not a new observation.

    @synchronized
    def save(self):
        self.data['revision'] += 1
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
            os.replace(temp, self.path)  # One atomic snapshot rather than partial JSON.

    def nearest(self, xy):
        node = min(self.campus.component, key=lambda n: meters(self.campus.nodes[n], xy))
        return node, meters(self.campus.nodes[node], xy)

    @synchronized
    def place(self, record):
        """Staff verifies actual pickup/delivery places; no demo stops auto-promoted."""
        slot = str(record['slot'])
        if slot not in {'base', '1', '2', '3', '4', '5', '6'}:
            raise ValueError('Place slot must be base or 1..6')
        if record.get('verified') is not True:
            raise ValueError('Confirm that the actual place and access were checked')
        xy = coordinates(record['coordinates'])
        node, offset = self.nearest(xy)
        if offset > SNAP_LIMIT_M:
            raise ValueError(f'Place is {offset:.1f}m from connected paths; max 30m. Verify location/data.')
        if any(p['node'] == node for key,p in self.data['places'].items() if key != slot):
            raise ValueError('Choose a distinct graph location for each place')
        self.data['places'][slot] = {'slot':slot,'name':text(record['name'],'Place name'),
            'coordinates':xy,'node':node,'snap_meters':round(offset,1),
            'source':text(record['source'],'Reporter/source'),'verified_at':iso(self.clock()),
            'mode':'staff_verified'}
        self.save()

    @synchronized
    def position(self, record):
        now = self.clock()
        observed = timestamp(record['observed_at'])
        if not now-300 <= observed <= now+5:
            raise ValueError('Position time is too old or ahead of the server clock')
        old = self.data['position']
        if old and observed <= timestamp(old['observed_at']):
            raise ValueError('Duplicate/older position rejected; do not overwrite newer observations')
        xy = coordinates(record['coordinates'])
        # A staff map click is a live report, not GPS or physical robot telemetry.
        self.data['position'] = {'coordinates':xy,'observed_at':iso(observed),
            'received_at':iso(now),'source':text(record['source'],'Reporter/source'),
            'subject':'STAFF-TEST-01','mode':'staff_reported',
            'method':'manual_map_report','accuracy_m':None}
        self.save()

    @synchronized
    def closure(self, record):
        identity = text(record['id'],'Closure ID')
        status = record['status']
        if status not in {'confirmed','cleared'}:
            raise ValueError('Closure status must be confirmed or cleared')
        edges = record['edge_ids']
        if not isinstance(edges,list) or not edges or len(edges)>50 or any(k not in self.campus.edges for k in edges):
            raise ValueError('Select 1..50 known graph segments')
        previous = self.data['closures'].get(identity)
        if previous and set(previous['edge_ids']) != set(edges):
            raise ValueError('A closure ID cannot silently change segments; create a new ID')
        self.data['closures'][identity] = {'id':identity,'status':status,'edge_ids':edges,
            'source':text(record['source'],'Reporter/source'),'observed_at':iso(self.clock()),
            'review_at':iso(self.clock()+3600),'mode':'staff_reported'}
        # Review expiry does NOT reopen an obstacle; explicit clearance is needed.
        self.save()

    @synchronized
    def crowd(self, record):
        now=self.clock()
        xy=coordinates(record['coordinates'])
        point=validate_point({'id':record['id'],'name':record['name'],
            'source':text(record['source'],'Reporter/source'),'kind':'manual','data_mode':'observed',
            'lat':xy[1],'lon':xy[0],'weight':record['weight'],'confidence':record['confidence'],
            'radius_m':record['radius_m'],'half_life_minutes':5,
            'starts_at':iso(now),'ends_at':iso(now+300),'updated_at':iso(now)})
        previous=self.data['crowds'].get(point['id'])
        if previous and previous['source']!=point['source']:
            raise ValueError('Crowd ID belongs to another source; use your own stable observation ID')
        self.data['crowds'][point['id']]=point
        self.save()

    def route_record(self, start, goal, blocked, crowds, now):
        nodes=self.campus.route(start,goal,blocked,crowds,now)
        if not nodes:
            return None
        duration=sum(self.campus.duration(a,b,crowds,now) for a,b in zip(nodes,nodes[1:]))
        distance=sum(self.campus.edges[edge_key(a,b)]['meters'] for a,b in zip(nodes,nodes[1:]))
        return {'coordinates':[self.campus.nodes[n] for n in nodes],
                'seconds':round(duration,1),'meters':round(distance,1),'nodes':nodes}

    @synchronized
    def snapshot(self):
        now=self.clock()
        places=self.data['places'];base=places.get('base')
        reports=list(self.data['closures'].values())
        blocked={edge for report in reports if report['status']=='confirmed' for edge in report['edge_ids']}
        # Evaluate expiry/freshness from source times, never the API response time.
        crowds=list(self.data['crowds'].values())
        points=prepare_points(crowds,now,now+.001)
        position=self.data['position'];age=max(0,now-timestamp(position['observed_at'])) if position else None
        fresh=age is not None and age<=POSITION_TTL
        current_node,offset=self.nearest(position['coordinates']) if position else (None,None)
        routes=[]
        for slot in map(str,range(1,7)):
            stop=places.get(slot)
            r={'id':slot,'name':stop['name'] if stop else 'Unconfigured destination '+slot,
               'status':'unavailable','reason':'Staff must verify base and this delivery place.'}
            if base and stop:
                outward=self.route_record(base['node'],stop['node'],blocked,crowds,now)
                back=self.route_record(stop['node'],base['node'],blocked,crowds,now)
                if outward and back:
                    # Validate exact reversal under the CURRENT known-closure snapshot.
                    reverse=outward['nodes'][::-1]
                    if all(edge_key(a,b) not in blocked for a,b in zip(reverse,reverse[1:])):
                        back={'coordinates':outward['coordinates'][::-1],
                              'seconds':outward['seconds'],'meters':outward['meters'],'nodes':reverse}
                    r.update(status='available',reason='Graph route against current known reports; coverage incomplete.',
                        outbound={k:v for k,v in outward.items() if k!='nodes'},
                        return_route={k:v for k,v in back.items() if k!='nodes'},return_kind='current exact retrace')
                else:r['reason']='No complete round trip through permitted, unblocked graph segments.'
            routes.append(r)
        return {'mode':'live_staff_reporting','generated_at':iso(now),'revision':self.data['revision'],
            'position':position,'position_age_seconds':age,'position_fresh':fresh,
            'position_snap_meters':round(offset,1) if offset is not None else None,
            'places':places,'routes':routes,'weighted_points':points,
            'weighted_nodes':[{'node_id':n,'coordinates':xy,'score':round(density_at(xy[1],xy[0],points),6)}
                for n,xy in self.campus.nodes.items() if points and density_at(xy[1],xy[0],points)>.001],
            'closures':[{**r,'review_overdue':now>timestamp(r['review_at'])} for r in reports],
            'blocked':[{'id':k,'coordinates':[self.campus.nodes[self.campus.edges[k]['a']],self.campus.nodes[self.campus.edges[k]['b']]]} for k in sorted(blocked)],
            'crowd_coverage':'current staff observations only' if points else 'unknown: no current crowd observations',
            'closure_coverage':'staff reports only; no complete-campus feed connected',
            'hardware':'not connected; subject is a staff field-test participant',
            'eta_available':fresh and offset<=SNAP_LIMIT_M if position else False,
            'current_node':current_node if fresh and offset<=SNAP_LIMIT_M else None}

    @synchronized
    def trip(self, slot, leg, state=None):
        """Estimated route from the LAST ACTUAL report. Never move it by a timer."""
        if str(slot) not in set(map(str,range(1,7))) or leg not in {'outbound','return'}:
            raise ValueError('Choose destination 1..6 and outbound/return')
        state=self.snapshot() if state is None else state;places=state['places']
        target=places.get(str(slot) if leg=='outbound' else 'base')
        if not state['eta_available'] or not target:
            return {'status':'unavailable','reason':'Need a fresh on-path position and verified destination','eta_seconds':None}
        blocked={r['id'] for r in state['blocked']}
        route=self.route_record(state['current_node'],target['node'],blocked,list(self.data['crowds'].values()),self.clock())
        if not route:
            return {'status':'unavailable','reason':'No valid route from reported position','eta_seconds':None}
        return {'status':'available','eta_seconds':route['seconds'],'coordinates':route['coordinates'],
                'meters':route['meters'],'position_observed_at':state['position']['observed_at'],
                'note':'Model estimate from staff map report; no invented countdown or robot motion.'}
```

## map_features.py

```python
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
```

## public_sources.py

```python
"""Verified public Mason sources -> normalized records -> source-age/status.

The project polygon schema does not assert walkway closures. Events assert
schedule/location, never measured attendance. No credentials or private schedules.
"""
import calendar
import hashlib
import json
import re
import threading
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from engine import iso

PROJECT_LAYER='https://services1.arcgis.com/knq5Ad7sB7AS2ev7/arcgis/rest/services/Project_Polygons/FeatureServer/6'
EVENT_URL='https://communication.gmu.edu/events/18428.ics'
PROJECT_URL=PROJECT_LAYER+'/query?'+urlencode({'where':"Website_Status='Public'",'outFields':'OBJECTID,Project,Project_Phase,Campus,Construction_Start,Construction_End','outSR':'4326','f':'geojson','resultRecordCount':1000})


def eastern_epoch(value):
    """This verified feed declares America/New_York in its VTIMEZONE section.

    The provider emits floating local DTSTART/DTEND. Use that declared calendar
    timezone; never the laptop timezone. Fixed post-2007 US DST rules avoid a
    Windows tzdata installation. Ambiguous fall-back-hour entries are rejected.
    """
    if value.endswith('Z'):
        return datetime.strptime(value,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp()
    d=datetime.strptime(value,'%Y%m%dT%H%M%S')
    march=calendar.monthcalendar(d.year,3);nov=calendar.monthcalendar(d.year,11)
    spring=[w[calendar.SUNDAY] for w in march if w[calendar.SUNDAY]][1]
    fall=[w[calendar.SUNDAY] for w in nov if w[calendar.SUNDAY]][0]
    start=datetime(d.year,3,spring,2);end=datetime(d.year,11,fall,2)
    if end-timedelta(hours=1)<=d<end or start<=d<start+timedelta(hours=1):
        raise ValueError('Ambiguous/nonexistent DST transition time; request explicit UTC event time')
    return d.replace(tzinfo=timezone(timedelta(hours=-4 if start<=d<end else -5))).timestamp()


def parse_events(body):
    lines=re.sub(r'\r?\n[ \t]','',body.decode('utf-8-sig')).splitlines()
    if 'BEGIN:VCALENDAR' not in lines or 'TZID:America/New_York' not in lines:
        raise ValueError('Expected the verified Eastern-time iCalendar schema')
    records=[];current=None
    for line in lines:
        if line=='BEGIN:VEVENT':current={}
        elif line=='END:VEVENT':
            if current:
                if 'RRULE' in current:raise ValueError('Recurring ICS needs expansion; not silently supported')
                if current.get('STATUS')!='CANCELLED':
                    start=eastern_epoch(current['DTSTART']);end=eastern_epoch(current['DTEND'])
                    if end<=start:raise ValueError('Event end precedes start')
                    records.append({'id':current['UID'],'title':current['SUMMARY'],
                        'location':current.get('LOCATION','').replace('\\,',','),'starts_at':iso(start),
                        'ends_at':iso(end),'source':EVENT_URL,'kind':'published_schedule'})
            current=None
        elif current is not None and ':' in line:
            key,value=line.split(':',1)
            if ';' in key and key.split(';')[0] in {'DTSTART','DTEND'} and 'TZID=America/New_York' not in key:
                raise ValueError('Unsupported calendar timezone')
            current[key.split(';')[0]]=value
    if not records and 'BEGIN:VEVENT' not in lines:raise ValueError('Unexpected empty event feed')
    return records


def parse_projects(body):
    d=json.loads(body)
    if d.get('error') or d.get('exceededTransferLimit') or not isinstance(d.get('features'),list):
        raise ValueError('Project source error/truncated result; retain last good data')
    return {'type':'FeatureCollection','features':[{'type':'Feature','geometry':f['geometry'],
        'properties':{k:f['properties'].get(k) for k in ['OBJECTID','Project','Project_Phase','Campus','Construction_Start','Construction_End']}}
        for f in d['features'] if f.get('geometry')]}


class PublicSources:
    def __init__(self,path):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.items={};self.stop=threading.Event()
        for name in ('projects','events'):
            p=self.path/(name+'.json')
            if p.exists():self.items[name]=json.loads(p.read_text())
    def refresh(self):
        for name,url,parser in [('projects',PROJECT_URL,parse_projects),('events',EVENT_URL,parse_events)]:
            try:
                with urlopen(Request(url,headers={'User-Agent':'MAXX-MapUI-Learning/2.0'}),timeout=20) as r:body=r.read(4_000_001)
                if len(body)>4_000_000:raise ValueError('Source exceeds local prototype size limit')
                data=parser(body)
                item={'url':url,'fetched_at':iso(time.time()),'error':None,'data':data}
                with self.lock:
                    self.items[name]=item
                    target=self.path/(name+'.json');temp=target.with_suffix('.tmp')
                    temp.write_text(json.dumps(item),encoding='utf-8');temp.replace(target)
            except (OSError,ValueError,KeyError,TypeError) as e:
                with self.lock:
                    self.items[name]={**self.items.get(name,{'data':None,'url':url,'fetched_at':None}),
                                      'error':str(e),'failed_at':iso(time.time())}
    def start(self):
        def loop():
            while not self.stop.is_set():
                self.refresh();self.stop.wait(900 if all(x.get('fresh') for x in self.snapshot().values()) else 60)  # Source polling every 15min, UI reads every 1/10s.
        threading.Thread(target=loop,daemon=True).start()
    def snapshot(self):
        with self.lock:items=json.loads(json.dumps(self.items))
        for item in items.values():
            fetched=item.get('fetched_at');age=time.time()-datetime.fromisoformat(fetched).timestamp() if fetched else None
            item['age_seconds']=age;item['fresh']=age is not None and age<=3600 and not item.get('error')
        return items


def point_in_ring(point,ring):
    x,y=point;inside=False
    for a,b in zip(ring,ring[1:]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def inside(point,geometry):
    polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry.get('coordinates',[]) if geometry['type']=='MultiPolygon' else []
    return any(point_in_ring(point,rings[0]) and not any(point_in_ring(point,h) for h in rings[1:]) for rings in polygons)


def project_edges(campus,features):
    """Conservative optional project-area avoidance, NOT claimed confirmed closures.

    Sampling at <=2m reduces missed narrow footprints; it is a planning heuristic,
    not certified exact polygon/edge intersection. Holes are respected.
    """
    import math
    active=[f for f in features if f['properties'].get('Project_Phase')=='Construction']
    result=set()
    for key,edge in campus.edges.items():
        a,b=campus.nodes[edge['a']],campus.nodes[edge['b']]
        count=max(1,math.ceil(edge['meters']/2))
        if any(inside([a[0]+t/count*(b[0]-a[0]),a[1]+t/count*(b[1]-a[1])],f['geometry'])
               for t in range(count+1) for f in active):result.add(key)
    return result
```

## refresh_osm.py

```python
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
```

## refresh_sources.py

```python
"""One public-source refresh for diagnosis. The server also refreshes every 15min."""
from pathlib import Path
from public_sources import PublicSources
s=PublicSources(Path(__file__).resolve().parent/'data/public-cache')
s.refresh()
for name,item in s.snapshot().items():
    print(name, 'CONNECTED' if item['fresh'] else 'UNAVAILABLE', item.get('fetched_at'), item.get('error'))
```

## server.py

```python
"""Local live staff-report map. Run: python server.py

Simulation remains separately available with --mode simulation --port 8004.
The default never synthesizes robot locations or fills missing observations.
"""
import argparse
import json
import secrets
import threading
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from engine import Campus,ROOT
from live_state import LiveState
from simulation_server import make_handler  # Preserve the previous demo's tests/API.


def live_handler(campus,live,operator_key):
    lock=live.lock
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,directory=str(ROOT/'web'),**kwargs)
        def end_headers(self):
            self.send_header('Cache-Control','no-store');super().end_headers()
        def reply(self,status,data):
            body=json.dumps(data).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            path=urlsplit(self.path).path;query=parse_qs(urlsplit(self.path).query)
            try:
                if path=='/api/live/state':
                    with lock:
                        state=live.snapshot()
                        # Trip ETA uses the same actual observation/condition snapshot.
                        state['trip']=live.trip(query.get('stop',['1'])[0],query.get('leg',['outbound'])[0],state)
                    return self.reply(200,state)
                if path=='/api/live/layers':
                    return self.reply(200,{'type':'FeatureCollection','features':campus.layers['features']+campus.buildings})
                if path=='/api/live/graph':
                    return self.reply(200,[{'id':k,'coordinates':[campus.nodes[e['a']],campus.nodes[e['b']]],'name':e['name']} for k,e in campus.edges.items()])
                if path=='/api/live/config':
                    manifest=ROOT/'data/osm-current/SOURCE.json'
                    return self.reply(200,{'mode':'live_staff_reporting','position_ttl_seconds':30,
                        'source':json.loads(manifest.read_text()) if manifest.exists() else {'status':'bundled baseline snapshot; not refreshed'},
                        'hardware':'not connected','events':'no approved machine feed connected',
                        'mapui_commit':'e88c2cc23ef9ddc495056151b1379eb7b3b1df71'})
            except (ValueError,KeyError,TypeError) as e:return self.reply(400,{'error':str(e)})
            if path in ('/','/index.html','/html/web/public/dave-campus-map/gis-layers.html'):
                self.path='/live.html'
            super().do_GET()
        def do_POST(self):
            if not secrets.compare_digest(self.headers.get('X-Operator-Key',''),operator_key):
                return self.reply(403,{'error':'Enter the operator key printed in the server terminal'})
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):
                return self.reply(403,{'error':'Use this map origin'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:raise ValueError('Expected a small JSON report')
                record=json.loads(self.rfile.read(size))
                if not isinstance(record,dict):raise ValueError('Expected a JSON object')
                operations={'/api/live/position':live.position,'/api/live/place':live.place,
                    '/api/live/closure':live.closure,'/api/live/crowd':live.crowd}
                if self.path not in operations:return self.reply(404,{'error':'Unknown endpoint'})
                with lock:operations[self.path](record)
                return self.reply(200,{'accepted':True,'note':'Staff report saved with provenance, not hardware telemetry'})
            except (ValueError,TypeError,KeyError) as e:return self.reply(400,{'error':str(e)})
        def list_directory(self,path):self.send_error(403,'Open the map, not a directory listing')
    return Handler


def world_handler(campus,world,reports,key):
    """Same-origin data for software robot and optional actual staff observations."""
    Base=live_handler(campus,reports,key)
    lock=reports.lock
    class Handler(Base):
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/version':return self.reply(200,{'build':'MapUI Visual Update 2','page':'/world.html'})
            if path=='/api/state':
                with lock:return self.reply(200,world.snapshot())
            if path=='/api/layers':return self.reply(200,{'type':'FeatureCollection','features':campus.layers['features']+campus.buildings})
            if path=='/api/config':return self.reply(200,{'stops':campus.stops,'base':campus.nodes[campus.base],'base_place':getattr(campus,'base_place',{}),'source':'OSM API snapshot plus current official Mason project/event sources','building_note':str(len(campus.buildings))+' real OSM outlines. Delivery stops remain planned software-robot targets.'})
            if path in ('/','/index.html','/html/web/public/dave-campus-map/gis-layers.html'):
                self.path='/world.html'
            super().do_GET()
        def do_POST(self):
            if self.path not in {'/api/configure','/api/action'}:return super().do_POST()
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):return self.reply(403,{'error':'Use the same origin'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096:raise ValueError('Expected small JSON command')
                data=json.loads(self.rfile.read(size))
                with lock:
                    result=world.configure(str(data['stop']),data['scenario'],int(data['rate'])) if self.path=='/api/configure' else world.action(data['action'])
                self.reply(200,result)
            except (ValueError,TypeError,KeyError) as e:self.reply(400,{'error':str(e)})
    return Handler


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--mode',choices=['live','reports','simulation'],default='live')
    args=parser.parse_args()
    if args.mode=='simulation':
        from engine import Simulation
        campus=Campus();handler=make_handler(campus,Simulation(campus))
        print('SIMULATION MODE. Generated positions and scenarios only.',flush=True)
    else:
        current=ROOT/'data/osm-current'
        campus=Campus(current if current.exists() else None)
        from map_features import configure_public_places,add_access_restrictions
        add_access_restrictions(campus,current if current.exists() else ROOT/'data')
        if args.mode=='live':configure_public_places(campus)
        live=LiveState(campus,ROOT/'runtime/live-reports.json')
        key=secrets.token_urlsafe(18)
        print('Actual staff reports accepted separately. No physical robot hardware connection.',flush=True)
        print('Operator key (share only with field reporters): '+key,flush=True)
        if args.mode=='reports':
            handler=live_handler(campus,live,key)
        else:
            from public_sources import PublicSources
            from world import WorldRobot
            sources=PublicSources(ROOT/'data/public-cache');sources.start()
            world=WorldRobot(campus,sources,live)
            handler=world_handler(campus,world,live,key)
            print('SOFTWARE ROBOT + PUBLIC WORLD INPUTS. Motion is computed; real GPS is not claimed.',flush=True)
    # Bind BEFORE announcing success; an occupied port must produce a clear failure.
    server=ThreadingHTTPServer((args.host,args.port),handler)
    print(f'Open http://127.0.0.1:{args.port}/world.html' if args.mode=='live' else f'Open http://127.0.0.1:{args.port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
```

## simulation_server.py

```python
"""Run: python server.py. Serves only web assets plus explicitly named API data."""
import argparse
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from engine import Campus, Simulation, ROOT

PREFIX = '/html/web/public/dave-campus-map/demo/'


def make_handler(campus, simulation):
    lock = threading.Lock()
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT/'web'), **kwargs)

        def end_headers(self):
            self.send_header('Cache-Control','no-store')
            super().end_headers()

        def reply(self, code, value):
            body = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/state':
                with lock:
                    return self.reply(200,simulation.snapshot())
            if path == '/api/layers':
                return self.reply(200,{'type':'FeatureCollection','features':
                    campus.layers['features']+campus.buildings})
            if path == '/api/config':
                return self.reply(200,{'stops':campus.stops,'base':campus.nodes[campus.base],
                    'source':'Team OSM snapshot gmu_map_16OCT26.json; fetched 2026-10-26',
                    'source_commit':'e88c2cc23ef9ddc495056151b1379eb7b3b1df71',
                    'counts':{'routing_nodes':len(campus.nodes),'routing_edges':len(campus.edges)},
                    'building_note':f'{len(campus.buildings)} supplemental OSM building outlines; team export supplied none.'})
            # Alias the user's familiar URL only in this standalone server.
            # No file in their repository is overwritten.
            if path in ('/','/html/web/public/dave-campus-map/gis-layers.html'):
                self.path = '/index.html'
            elif path.startswith(PREFIX):
                self.path = '/'+path[len(PREFIX):]
            super().do_GET()

        def do_POST(self):
            # Local demo state is shared by all phones. No permissive CORS.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://'+self.headers.get('Host',''):
                return self.reply(403,{'error':'Use the same origin as the demo page'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096:
                    raise ValueError('Expected a small JSON request')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict):
                    raise ValueError('Expected an object')
                with lock:
                    if self.path == '/api/configure':
                        state = simulation.configure(str(body['stop']),body['scenario'],int(body['rate']))
                    elif self.path == '/api/action':
                        state = simulation.action(body['action'])
                    else:
                        return self.reply(404,{'error':'Unknown endpoint'})
                self.reply(200,state)
            except (ValueError,KeyError,TypeError) as exc:
                self.reply(400,{'error':str(exc)})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    args = parser.parse_args()
    campus = Campus()
    server = ThreadingHTTPServer((args.host,args.port),make_handler(campus,Simulation(campus)))
    print(f'MAXX local simulation: http://localhost:{args.port}/html/web/public/dave-campus-map/gis-layers.html')
    print('Shared controls: changing scenario resets every viewer to base. Ctrl+C stops server.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
```

## tests/test_crowd_model.py

```python
"""Small, explainable weighted-field tests. No team repository is needed here."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import copy
import unittest
from crowd_model import (timestamp, validate_point, effective_weight, prepare_points,
                         density_at, sample_polyline, edge_exposure, travel_seconds)


def example():
    return validate_point({"id": "one", "name": "Training entrance", "kind": "class",
        "lat": 38.831, "lon": -77.307, "radius_m": 100, "weight": 0.8,
        "confidence": 0.5, "half_life_minutes": 60,
        "starts_at": "2026-10-26T09:00:00Z", "ends_at": "2026-10-26T13:00:00Z",
        "updated_at": "2026-10-26T10:00:00Z", "source": "SIMULATION",
        "data_mode": "simulated"})


class WeightedFieldChecks(unittest.TestCase):
    def setUp(self):
        self.point = example()
        self.now = timestamp("2026-10-26T10:00:00Z")

    def test_weight_times_confidence(self):
        self.assertAlmostEqual(effective_weight(self.point, self.now), 0.4)

    def test_freshness_halves_after_one_half_life(self):
        self.assertAlmostEqual(effective_weight(self.point, self.now + 3600), 0.2)

    def test_inactive_and_ended_points_have_zero_weight(self):
        self.assertEqual(effective_weight(self.point, self.now - 7200), 0)
        self.assertEqual(effective_weight(self.point, self.now + 10800), 0)

    def test_quadratic_distance_falloff_and_boundary(self):
        points = prepare_points([self.point], self.now, self.now + 1)
        self.assertAlmostEqual(density_at(38.831, -77.307, points), 0.4)
        self.assertAlmostEqual(density_at(38.831 + 50 / 111320, -77.307, points), 0.1)
        self.assertAlmostEqual(density_at(38.831 + 100 / 111320, -77.307, points), 0, places=9)

    def test_overlaps_saturate_without_exceeding_one(self):
        other = {**self.point, "id": "two"}
        points = prepare_points([self.point, other], self.now, self.now + 1)
        self.assertAlmostEqual(density_at(38.831, -77.307, points), 0.64)

    def test_midpoint_crowd_affects_long_edge(self):
        # Endpoints are outside a 20m radius, but the walkway passes through it.
        point = {**self.point, "radius_m": 20}
        points = prepare_points([point], self.now, self.now + 1)
        samples = sample_polyline([(38.830, -77.307), (38.832, -77.307)])
        self.assertGreater(edge_exposure(samples, points), 0)

    def test_more_exposure_never_reduces_travel_time(self):
        self.assertEqual(travel_seconds(100, 2, 0), 50)
        self.assertEqual(travel_seconds(100, 2, 1), 200)
        self.assertGreater(travel_seconds(100, 2, 0.8), travel_seconds(100, 2, 0.2))

    def test_bad_numbers_and_unzoned_times_are_rejected(self):
        self.assertNotIn("private_notes", validate_point({**self.point, "private_notes": "Do not publish this extra column"}))
        for field, value in [("weight", 2), ("confidence", -1), ("lat", float("nan")), ("half_life_minutes", 0)]:
            with self.assertRaises(ValueError):
                validate_point({**self.point, field: value})
        with self.assertRaises(ValueError):
            timestamp("2026-10-26T10:00:00")

    def test_forecast_window_includes_a_later_start(self):
        later = {**self.point, "starts_at": "2026-10-26T11:00:00Z"}
        self.assertEqual(prepare_points([later], self.now, self.now + 60), [])
        self.assertEqual(len(prepare_points([later], self.now, self.now + 7200)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

## tests/test_demo.py

```python
"""Meaningful route, simulation and HTTP checks; no network or extra packages."""
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Campus, Simulation, edge_key, crowd_weight, meters, iso
from server import make_handler

class Clock:
    def __init__(self): self.value=1000.0
    def __call__(self): return self.value
    def advance(self,t): self.value+=t

class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c=Campus()
    def setUp(self):
        self.clock=Clock();self.s=Simulation(self.c,self.clock,lambda:2000+self.clock.value)
    def test_all_six_clear_and_exact_return(self):
        for stop in self.c.stops:
            s=self.s.configure(stop['id'],'clear',1)
            self.assertGreater(len(s['outbound']),1)
            self.assertEqual(s['return_route'],s['outbound'][::-1])
            self.assertEqual(s['outbound'][0],self.c.nodes[self.c.base])
            self.assertEqual(s['outbound'][-1],stop['coordinates'])
    def test_all_six_closures_avoid_both_directions(self):
        for stop in self.c.stops:
            self.s.configure(stop['id'],'closure',1)
            self.assertTrue(self.s.outbound)
            self.assertTrue(self.s.blocked)
            for path in (self.s.outbound,self.s.return_path):
                self.assertTrue(all(edge_key(a,b) not in self.s.blocked for a,b in zip(path,path[1:])))
    def test_all_six_sealed_stay_at_base(self):
        for stop in self.c.stops:
            self.s.configure(stop['id'],'sealed',1);self.s.action('start');self.clock.advance(99)
            s=self.s.snapshot();self.assertEqual(s['phase'],'unavailable')
            self.assertIsNone(s['eta_seconds']);self.assertFalse(s['running'])
            self.assertEqual(s['coordinates'],self.c.nodes[self.c.base])
    def test_motion_stays_on_first_edge(self):
        self.s.action('start');t=self.s.segment_seconds[0]/2;self.clock.advance(t)
        p=self.s.snapshot()['coordinates'];a,b=[self.c.nodes[n] for n in self.s.trip[:2]]
        self.assertLess(meters(p,[(a[0]+b[0])/2,(a[1]+b[1])/2]),.01)
    def test_pause_freezes_and_resume_moves(self):
        self.s.action('start');self.clock.advance(1);a=self.s.action('pause')
        self.clock.advance(20);b=self.s.snapshot();self.assertEqual(a['coordinates'],b['coordinates'])
        self.s.action('start');self.clock.advance(1);self.assertNotEqual(b['coordinates'],self.s.snapshot()['coordinates'])
    def test_return_and_complete(self):
        self.s.action('start');self.clock.advance(self.s.out_seconds+.01)
        self.assertEqual(self.s.snapshot()['phase'],'returning')
        self.clock.advance(self.s.total_seconds)
        s=self.s.snapshot();self.assertEqual(s['phase'],'complete');self.assertFalse(s['running'])
        self.assertEqual(s['coordinates'],self.c.nodes[self.c.base]);self.assertEqual(s['eta_seconds'],0)
    def test_eta_decreases(self):
        a=self.s.action('start');self.clock.advance(2);b=self.s.snapshot()
        self.assertAlmostEqual(a['eta_seconds']-b['eta_seconds'],2)
    def test_ten_x_clock(self):
        self.s.configure('2','clear',10);a=self.s.action('start');self.clock.advance(1);b=self.s.snapshot()
        self.assertAlmostEqual(a['eta_travel_seconds']-b['eta_travel_seconds'],10)
        self.assertAlmostEqual(a['eta_seconds']-b['eta_seconds'],1)
    def test_scenario_resets_shared_trip(self):
        self.s.action('start');self.clock.advance(5);self.s.snapshot()
        s=self.s.configure('2','closure',1);self.assertEqual(s['traveled_meters'],0);self.assertFalse(s['running'])
    def test_bad_configuration(self):
        for args in [('99','clear',1),('1','unknown',1),('1','clear',15)]:
            with self.assertRaises(ValueError):self.s.configure(*args)
    def test_forecast_return_closure_reroutes_all_six(self):
        for stop in self.c.stops:
            state=self.s.configure(stop['id'],'return-closure',1)
            self.assertTrue(self.s.trip)
            self.assertEqual(state['return_kind'],'rerouted return')
            self.assertNotEqual(self.s.return_path,self.s.outbound[::-1])
            self.assertTrue(all(edge_key(a,b) not in self.s.return_blocked
                                for a,b in zip(self.s.return_path,self.s.return_path[1:])))
    def test_node_field_is_bounded_and_visual_only(self):
        s=self.s.configure('2','crowd',1)
        self.assertEqual(len(s['weighted_points']),3)
        self.assertTrue(s['weighted_nodes'])
        self.assertTrue(all(0<n['score']<=1 for n in s['weighted_nodes']))
        # The trip cost equals only its segment costs; no second node penalty.
        self.assertAlmostEqual(sum(self.s.segment_seconds),s['total_seconds'])
    def test_crowd_increases_cost(self):
        self.s.configure('2','crowd',1)
        p=self.s.crowds[0];self.assertGreater(self.c.score([p['lon'],p['lat']],[p],self.s.wall()),0)
        a,b=self.s.outbound[:2]
        # Entire chosen route cannot beat the unweighted shortest-travel-time lower bound.
        clear=self.c.route(self.c.base,self.s.stop['node'])
        clear_cost=sum(self.c.duration(a,b,[],self.s.wall()) for a,b in zip(clear,clear[1:]))
        self.assertGreaterEqual(self.s.out_seconds,clear_cost)
    def test_real_buildings_have_closed_valid_rings(self):
        self.assertEqual(len(self.c.buildings),145)
        self.assertTrue(any(f['properties']['name']=='Johnson Center' for f in self.c.buildings))
        for feature in self.c.buildings:
            self.assertEqual(feature['properties']['data_mode'],'snapshot')
            ring=feature['geometry']['coordinates'][0]
            self.assertGreaterEqual(len(ring),4)
            self.assertEqual(ring[0],ring[-1])
            self.assertTrue(all(-180<=x<=180 and -90<=y<=90 for x,y in ring))
    def test_graph_has_no_zero_segments(self):
        self.assertTrue(all(e['meters']>0 for e in self.c.edges.values()))
    def test_http_contract_and_static_alias(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.c,self.s))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            for path in ['/','/html/web/public/dave-campus-map/gis-layers.html','/app.js','/heat-field.js','/heat-layer.js','/vendor/leaflet.js','/vendor/images/layers.png','/style.css']:
                with urlopen(base+path) as r:
                    self.assertEqual(r.status,200);r.read()
            config=json.load(urlopen(base+'/api/config'));self.assertEqual(len(config['stops']),6)
            state=json.load(urlopen(base+'/api/state'));self.assertEqual(state['mode'],'simulated')
            req=Request(base+'/api/configure',data=json.dumps({'stop':'2','scenario':'sealed','rate':1}).encode(),headers={'Content-Type':'application/json'})
            self.assertEqual(json.load(urlopen(req))['phase'],'unavailable')
            with self.assertRaises(HTTPError) as caught:urlopen(base+'/engine.py')
            self.assertEqual(caught.exception.code,404)
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
```

## tests/test_live.py

```python
"""Actual-report plumbing tests use fixtures, NEVER real-world observation claims."""
import sys,json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Campus,ROOT,iso,edge_key
from live_state import LiveState
from server import live_handler

class Clock:
    def __init__(self):self.now=1800000000.0
    def __call__(self):return self.now

class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Campus(ROOT/'data/osm-current')
    def setUp(self):self.clock=Clock();self.live=LiveState(self.c,clock=self.clock)
    def populate(self):
        # Deterministic software fixtures are not shipped as live observations.
        nodes=[self.c.base]+[s['node'] for s in self.c.stops]
        for slot,node in zip(['base','1','2','3','4','5','6'],nodes):
            self.live.place({'slot':slot,'name':'FIXTURE '+slot,'source':'TEST ONLY','verified':True,'coordinates':self.c.nodes[node]})
    def report(self,node=None):
        self.live.position({'coordinates':self.c.nodes[node or self.c.base],'observed_at':iso(self.clock()),'source':'TEST ONLY'})
    def test_empty_is_unknown_not_fabricated(self):
        s=self.live.snapshot();self.assertIsNone(s['position']);self.assertEqual(s['weighted_points'],[])
        self.assertTrue(all(r['status']=='unavailable' for r in s['routes']))
        self.assertFalse(s['eta_available'])
    def test_six_current_round_trips_and_exact_returns(self):
        self.populate();s=self.live.snapshot()
        self.assertTrue(all(r['status']=='available' for r in s['routes']))
        for r in s['routes']:self.assertEqual(r['outbound']['coordinates'][::-1],r['return_route']['coordinates'])
    def test_actual_position_does_not_move_by_clock(self):
        self.report();before=self.live.snapshot()['position']['coordinates'];self.clock.now+=10
        self.assertEqual(before,self.live.snapshot()['position']['coordinates'])
    def test_stale_position_hides_eta(self):
        self.populate();self.report();self.assertEqual(self.live.trip('1','outbound')['status'],'available')
        self.clock.now+=31;self.assertIsNone(self.live.trip('1','outbound')['eta_seconds'])
    def test_old_and_future_position_rejected(self):
        self.report()
        for delta in (-1,60):
            with self.assertRaises(ValueError):self.live.position({'coordinates':self.c.nodes[self.c.base],'observed_at':iso(self.clock()+delta),'source':'TEST'})
    def test_off_graph_actual_report_preserved_but_eta_unavailable(self):
        self.live.position({'coordinates':[-77.0,38.0],'observed_at':iso(self.clock()),'source':'TEST ONLY'})
        self.assertFalse(self.live.snapshot()['eta_available'])
    def test_place_requires_verification_and_rejects_far_snap(self):
        with self.assertRaises(ValueError):self.live.place({'slot':'base','verified':False})
        with self.assertRaises(ValueError):self.live.place({'slot':'base','verified':True,'coordinates':[-77,38],'name':'TEST','source':'TEST'})
    def test_closure_does_not_expire_open(self):
        edge=next(iter(self.c.edges));self.live.closure({'id':'TEST','edge_ids':[edge],'source':'TEST','status':'confirmed'})
        self.clock.now+=7200;s=self.live.snapshot();self.assertTrue(s['closures'][0]['review_overdue']);self.assertEqual(s['blocked'][0]['id'],edge)
        self.live.closure({'id':'TEST','edge_ids':[edge],'source':'TEST','status':'cleared'});self.assertEqual(self.live.snapshot()['blocked'],[])
    def test_blocked_destination_has_no_complete_round_trip(self):
        self.populate();node=self.live.data['places']['1']['node'];edges=list(self.c.adj[node].values())
        self.live.closure({'id':'TEST','edge_ids':edges,'source':'TEST','status':'confirmed'})
        self.assertEqual(self.live.snapshot()['routes'][0]['status'],'unavailable')
    def test_current_closure_recalculates_route(self):
        self.populate();baseline=self.live.snapshot()['routes'][1]['outbound']['coordinates']
        from engine import Simulation
        fixture=Simulation(self.c);fixture.configure('2','closure',1)
        self.live.closure({'id':'TEST','edge_ids':list(fixture.blocked),'source':'TEST','status':'confirmed'})
        r=self.live.snapshot()['routes'][1];self.assertEqual(r['status'],'available');self.assertNotEqual(r['outbound']['coordinates'],baseline)
        blocked=set(fixture.blocked)
        for route in ('outbound','return_route'):
            coords=r[route]['coordinates'];lookup={tuple(xy):n for n,xy in self.c.nodes.items()}
            self.assertTrue(all(edge_key(lookup[tuple(a)],lookup[tuple(b)]) not in blocked for a,b in zip(coords,coords[1:])))
    def crowd(self):return {'id':'TEST-COUNT','name':'TEST ONLY','source':'TEST ONLY','coordinates':self.c.nodes[self.c.base],'weight':.8,'confidence':.5,'radius_m':100}
    def test_crowd_expires_and_reuse_replaces_not_doubles(self):
        self.live.crowd(self.crowd());self.live.crowd(self.crowd());s=self.live.snapshot()
        self.assertEqual(len(s['weighted_points']),1);self.assertAlmostEqual(s['weighted_points'][0]['effective_weight'],.4)
        self.clock.now+=301;self.assertEqual(self.live.snapshot()['weighted_points'],[])
    def test_duplicate_crowd_id_from_other_source_rejected(self):
        self.live.crowd(self.crowd())
        with self.assertRaises(ValueError):self.live.crowd({**self.crowd(),'source':'OTHER'})
    def test_persistence_preserves_observation_age(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'reports.json';s=LiveState(self.c,path,self.clock)
            s.position({'coordinates':self.c.nodes[self.c.base],'observed_at':iso(self.clock()),'source':'TEST'})
            self.clock.now+=40;restored=LiveState(self.c,path,self.clock)
            self.assertFalse(restored.snapshot()['position_fresh'])
    def test_http_auth_and_empty_live_contract(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),live_handler(self.c,self.live,'test-key'));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            s=json.load(urlopen(base+'/api/live/state'));self.assertEqual(s['mode'],'live_staff_reporting');self.assertIsNone(s['position'])
            payload=json.dumps({'coordinates':self.c.nodes[self.c.base],'observed_at':iso(self.clock()),'source':'TEST'}).encode()
            with self.assertRaises(HTTPError) as e:urlopen(Request(base+'/api/live/position',data=payload))
            self.assertEqual(e.exception.code,403)
            result=json.load(urlopen(Request(base+'/api/live/position',data=payload,headers={'X-Operator-Key':'test-key'})));self.assertTrue(result['accepted'])
            with self.assertRaises(HTTPError):urlopen(base+'/runtime/live-reports.json')
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
```

## tests/test_map_features.py

```python
"""Source-derived places and exact restriction-tag semantics; no invented points."""
import sys,unittest,subprocess,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Campus,ROOT
from map_features import configure_public_places,add_access_restrictions,DELIVERIES

class MapFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Campus(ROOT/'data/osm-current');configure_public_places(cls.c);add_access_restrictions(cls.c,ROOT/'data/osm-current')
    def test_named_real_building_base_and_six_targets(self):
        self.assertEqual(self.c.base_place['name'],'Southside Dining')
        self.assertEqual([s['name'] for s in self.c.stops],DELIVERIES)
        self.assertEqual(len({self.c.base}|{s['node'] for s in self.c.stops}),7)
    def test_all_six_round_trip_graph_routes(self):
        for s in self.c.stops:
            path=self.c.route(self.c.base,s['node']);self.assertTrue(path)
            self.assertEqual(self.c.route(s['node'],self.c.base),path[::-1])
    def test_coordinate_anchors_are_actual_osm_footprint_vertices(self):
        by_id={f['properties']['osm_id']:f for f in self.c.buildings}
        for p in [self.c.base_place]+self.c.stops:
            self.assertIn(p['requested_coordinates'],by_id[p['osm_building_id']]['geometry']['coordinates'][0])
            self.assertLessEqual(p['snap_meters'],40)
    def test_building_target_coordinates_are_stable_across_processes(self):
        code="import json;from engine import Campus,ROOT;from map_features import configure_public_places;c=Campus(ROOT/'data/osm-current');configure_public_places(c);print(json.dumps([c.base_place['coordinates']]+[p['coordinates'] for p in c.stops]))"
        values=[subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'PYTHONHASHSEED':seed},text=True) for seed in ('1','2')]
        self.assertEqual(values[0],values[1])
    def test_restrictions_show_real_access_tags_and_are_idempotent(self):
        r=[f for f in self.c.layers['features'] if f['properties']['layer']=='restricted']
        self.assertEqual(len(r),8)
        self.assertEqual({f['properties']['access_tags']['access'] for f in r},{'delivery','official'})
        add_access_restrictions(self.c,ROOT/'data/osm-current')
        self.assertEqual(sum(f['properties']['layer']=='restricted' for f in self.c.layers['features']),8)
    def test_vehicle_prohibition_is_not_falsely_called_closed_footway(self):
        candidates=[f for f in self.c.layers['features'] if f['properties'].get('access_tags',{}).get('motor_vehicle')=='no' and f['properties']['access_tags'].get('foot')=='yes']
        self.assertTrue(candidates)
        self.assertTrue(all(f['properties']['layer']=='walkways' for f in candidates))

if __name__=='__main__':unittest.main(verbosity=2)
```

## tests/test_public_sources.py

```python
"""Deterministic software checks. TEST records are never served as real reports."""
import sys,json,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Campus,ROOT,iso
from public_sources import parse_events,parse_projects,inside,project_edges,PublicSources
from live_state import LiveState
from world import WorldRobot

ICS=b'''BEGIN:VCALENDAR\r\nBEGIN:VTIMEZONE\r\nTZID:America/New_York\r\nEND:VTIMEZONE\r\nBEGIN:VEVENT\r\nUID:TEST\r\nDTSTART:20261027T083000\r\nDTEND:20261027T123000\r\nSUMMARY:TEST EVENT\r\nLOCATION:Johnson Center\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'''

class PublicSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=Campus(ROOT/'data/osm-current')
    def feed(self):
        now=iso(time.time());event=parse_events(ICS)
        return {'projects':{'fresh':True,'fetched_at':now,'data':{'type':'FeatureCollection','features':[]}},'events':{'fresh':True,'fetched_at':now,'data':event}}
    def test_ics_parses_publisher_timezone(self):
        e=parse_events(ICS)[0];self.assertEqual(e['starts_at'],'2026-10-27T12:30:00+00:00')
    def test_cancelled_event_is_not_a_crowd_prediction(self):
        self.assertEqual(parse_events(ICS.replace(b'UID:TEST',b'UID:TEST\r\nSTATUS:CANCELLED')),[])
    def test_recurrences_and_unknown_timezones_are_not_silently_guessed(self):
        for body in [ICS.replace(b'UID:TEST',b'UID:TEST\r\nRRULE:FREQ=DAILY'),ICS.replace(b'America/New_York',b'Europe/London')]:
            with self.assertRaises(ValueError):parse_events(body)
    def test_truncated_projects_are_rejected(self):
        with self.assertRaises(ValueError):parse_projects(json.dumps({'features':[],'exceededTransferLimit':True}).encode())
    def test_project_geometry_holes(self):
        geom={'type':'Polygon','coordinates':[[[0,0],[10,0],[10,10],[0,10],[0,0]],[[2,2],[4,2],[4,4],[2,4],[2,2]]]}
        self.assertTrue(inside([1,1],geom));self.assertFalse(inside([3,3],geom));self.assertFalse(inside([15,15],geom))
    def test_software_robot_has_no_synthetic_closure_scenario_in_current_data_mode(self):
        feeds=self.feed()
        class Sources:
            def snapshot(self):return feeds
        w=WorldRobot(self.c,Sources(),LiveState(self.c))
        self.assertEqual(w.snapshot()['mode'],'software_robot_with_public_world_inputs')
        self.assertEqual(w.snapshot()['blocked'],[])
        with self.assertRaises(ValueError):w.configure('2','closure',1)
    def test_source_failure_disables_live_start(self):
        feeds=self.feed()
        class Sources:
            def snapshot(self):return feeds
        w=WorldRobot(self.c,Sources(),LiveState(self.c));feeds['events']['fresh']=False
        with self.assertRaises(ValueError):w.action('start')
    def test_reported_closure_replans_and_pauses(self):
        feeds=self.feed()
        class Sources:
            def snapshot(self):return feeds
        reports=LiveState(self.c);w=WorldRobot(self.c,Sources(),reports)
        edge=next(iter(self.c.edges));reports.closure({'id':'TEST','edge_ids':[edge],'source':'TEST','status':'confirmed'})
        state=w.snapshot();self.assertFalse(state['running']);self.assertEqual(state['traveled_meters'],0)
        self.assertIn(edge,{e['id'] for e in state['blocked']})
    def test_real_events_are_predictions_not_observed_counts(self):
        feeds=self.feed();feeds['events']['data'][0].update(starts_at=iso(time.time()-60),ends_at=iso(time.time()+60))
        class Sources:
            def snapshot(self):return feeds
        w=WorldRobot(self.c,Sources(),LiveState(self.c));s=w.snapshot()
        self.assertTrue(s['weighted_points']);self.assertEqual(s['weighted_points'][0]['data_mode'],'predicted')
        self.assertEqual(s['weighted_points'][0]['confidence'],.3)
    def test_stale_cache_is_not_refreshed_by_loading_it(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'events.json';p.write_text(json.dumps({'data':[],'fetched_at':'2020-01-01T00:00:00+00:00','error':None}))
            self.assertFalse(PublicSources(d).snapshot()['events']['fresh'])

if __name__=='__main__':unittest.main(verbosity=2)
```

## web/app.js

```javascript
"use strict";
// DAVID: map controls, accessible status/ETA and responsive presentation.
// SHEK: fetchState() is the integration seam for a future real telemetry feed.
const $ = id => document.getElementById(id);
const map = L.map('campus-map', {tap:true}).setView([38.831,-77.307],16);
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}); // Optional: leave unchecked for a dependable offline demonstration.
L.control.scale({imperial:false}).addTo(map);
const colors = {walkways:'#15803d',buildings:'#2563eb',delivery:'#800030',restricted:'#dc2626'};
const groups = {};
const text = value => { const span=document.createElement('span');span.textContent=value;return span; };
for (const [key,color] of Object.entries(colors)) {
  groups[key] = L.geoJSON(null, {
    style:{color,weight:key==='walkways'?3:4,fillOpacity:.25},
    pointToLayer:(feature,ll)=>L.circleMarker(ll,{radius:7,color,fillOpacity:1}),
    onEachFeature:(feature,layer)=>{
      const p=feature.properties || {};
      const name = p.name && p.name!==key ? p.name : `Unnamed ${key==='walkways'?'walkway':key}`;
      const label = `${name}${p.osm_id?' · OSM '+p.osm_id:''}`;
      layer.bindPopup(text(label)).bindTooltip(text(label),{sticky:true});
    }
  }).addTo(map);
}
const outbound = L.polyline([],{color:'#7e22ce',weight:6}).addTo(map);
const returning = L.polyline([],{color:'#007c91',weight:3,dashArray:'7 9'}).addTo(map);
const closures = L.layerGroup().addTo(map);
const robot = L.circleMarker([38.831,-77.307],{radius:10,color:'#fff',weight:3,fillColor:'#111827',fillOpacity:1}).addTo(map);
robot.bindTooltip('SIM-01 · simulated robot');
let state=null, received=0, failed=false, busy=false, pollTimer, revision=-1;

// Retain the supplied matching field model and canvas renderer. Weighted
// nodes explain the field visually; visibility does not add any routing costs.
const heat=new WeightedHeatLayer().addTo(map);
const nodes=L.layerGroup(),sources=L.layerGroup();
L.control.layers({'Offline GIS background':L.layerGroup().addTo(map),'Online OpenStreetMap tiles':tiles},{
  'Walkways (team data)':groups.walkways,'Buildings (OSM outlines)':groups.buildings,
  'Delivery points (SIMULATED)':groups.delivery,'Access restrictions (team data)':groups.restricted,
  'Outbound route':outbound,'Return route':returning,'Demo closures':closures,'Weighted crowd heat (predicted)':heat,'Robot SIM-01':robot,'Routing-node crowd scores':nodes,'Weighted crowd sources':sources
},{collapsed:true}).addTo(map);
// Pan/zoom choices persist; polling never replaces the map or its layer control.
const latlngs = coords => coords.map(([x,y])=>[y,x]);
function fitRoute(){
  const points=state?.outbound.length?latlngs(state.outbound):[robot.getLatLng()];
  map.fitBounds(L.latLngBounds(points).pad(.2),{maxZoom:17});
}
function show(s){
  state=s;received=Date.now();failed=false;
  $('phase').textContent=(s.running?'Moving · ':'Paused · ')+s.phase;
  if(s.phase==='complete')$('phase').textContent='Complete · back at base';
  if(s.phase==='unavailable')$('phase').textContent='No valid route';
  $('eta-label').textContent=`ETA to ${s.eta_target} · ${s.rate}× demo clock`;
  const seconds=Math.ceil(s.eta_seconds || 0);
  $('eta').textContent=s.eta_seconds===null?'Unavailable':s.phase==='complete'?'Arrived':
    `${Math.floor(seconds/60)}m ${seconds%60}s${!s.running?' (paused)':''}`;
  $('distance').textContent=`${s.traveled_meters} / ${s.total_meters} m`;
  $('notice').classList.toggle('error',s.phase==='unavailable');
  $('notice').textContent=`SIMULATION · ${s.message} ${s.rate===10?'10× playback; ETA is accelerated demo time.':''}`;
  robot.setLatLng([s.coordinates[1],s.coordinates[0]]);
  if($('follow').checked) map.panTo(robot.getLatLng());
  if(s.revision!==revision) {
    revision=s.revision;
    outbound.setLatLngs(latlngs(s.outbound));returning.setLatLngs(latlngs(s.return_route));
    closures.clearLayers();nodes.clearLayers();sources.clearLayers();
    for(const b of s.blocked)L.polyline(latlngs(b.coordinates),{color:'#f00',weight:10}).bindPopup(text('SIMULATED blocked segment')).addTo(closures);
    for(const b of (s.forecast_return_blocked || []))L.polyline(latlngs(b.coordinates),{color:'#d97706',weight:9,dashArray:'4 5'}).bindPopup(text('SIMULATED forecast closure on return leg')).addTo(closures);
    for(const n of s.weighted_nodes)L.circleMarker([n.coordinates[1],n.coordinates[0]],{radius:4,color:`hsl(${120*(1-n.score)},90%,35%)`,fillOpacity:.8}).bindPopup(text(`Routing node ${n.node_id} · crowd score ${n.score} · NO separate node cost`)).addTo(nodes);
    for(const p of s.weighted_points)L.circleMarker([p.lat,p.lon],{radius:7,color:'#9a3412',fillOpacity:.7}).bindPopup(text(`${p.name} · intensity ${p.weight} × confidence ${p.confidence} · effective ${p.effective_weight.toFixed(3)} · source ${p.source} · updated ${p.updated_at} · ${p.half_life_minutes} min freshness half-life`)).addTo(sources);
    heat.setPoints(s.weighted_points);
    $('stop').value=s.stop.id;$('scenario').value=s.scenario;$('rate').value=String(s.rate);
  }
  // Heat stays at the scenario's planning snapshot so it agrees with route costs.
  $('start').disabled=!s.outbound.length || s.phase==='complete';
}
async function request(url,body){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
  try{
    const response=await fetch(url,{cache:'no-store',signal:controller.signal,
      ...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    const result=await response.json();if(!response.ok)throw new Error(result.error || response.status);return result;
  } finally {clearTimeout(timeout);}
}
function error(e){failed=true;$('notice').classList.add('error');$('notice').textContent='Connection failed — last displayed position may be stale. '+e.message;}
async function fetchState(){
  if(busy)return;busy=true;
  try{show(await request('/api/state'));}catch(e){error(e);}finally{busy=false;}
}
function schedule(){clearTimeout(pollTimer);pollTimer=setTimeout(async()=>{await fetchState();schedule();},Number($('poll').value));}
$('poll').onchange=async()=>{await fetchState();schedule();};
$('fit').onclick=fitRoute;
for(const action of ['start','pause','reset']) $(''+action).onclick=async()=>{
  try{show(await request('/api/action',{action}));schedule();}catch(e){error(e);}
};
$('apply').onclick=async()=>{
  $('apply').disabled=true;
  try{show(await request('/api/configure',{stop:$('stop').value,scenario:$('scenario').value,rate:Number($('rate').value)}));fitRoute();schedule();}
  catch(e){error(e);}finally{$('apply').disabled=false;}
};
setInterval(()=>{
  if(!received)return;
  const age=Math.floor((Date.now()-received)/1000),stale=failed||age>Math.max(15,Number($('poll').value)/1000*2.5);
  $('age').textContent=`${age}s ago${stale?' · STALE':''}`;
},500);
(async()=>{
  try{
    const [config,layers]=await Promise.all([request('/api/config'),request('/api/layers')]);
    const counts={walkways:0,buildings:0,delivery:0,restricted:0};
    for(const f of layers.features){const k=f.properties?.layer;if(groups[k]){groups[k].addData(f);counts[k]++;}}
    for(const stop of config.stops){
      const option=document.createElement('option');option.value=stop.id;option.textContent=stop.name;$('stop').appendChild(option);
      groups.delivery.addData({type:'Feature',properties:{name:stop.name+' · SIMULATED graph stop'},geometry:{type:'Point',coordinates:stop.coordinates}});counts.delivery++;
    }
    L.circleMarker([config.base[1],config.base[0]],{radius:8,color:'#172b3a',fillOpacity:1}).bindTooltip('Demo base · unverified pickup location').addTo(map);
    $('counts').textContent=Object.entries(counts).map(([k,v])=>`${k}: ${v}`).join(' | ');
    $('source').textContent=config.source+'. '+config.building_note;
    await fetchState();if(!state)throw new Error('No initial state');fitRoute();
    for(const id of ['stop','apply','pause','reset','fit'])$(id).disabled=false;
    schedule();
  }catch(e){error(e);}
})();
```

## web/heat-field.js

```javascript
"use strict";

// Pure functions shared by the canvas renderer and cross-language verification.
// effective_weight is calculated by Python at the snapshot time; the browser
// does not independently age a snapshot and silently disagree with its backend.
(function (root) {
  function distanceMeters(lat1, lon1, lat2, lon2) {
    const x = (lon2 - lon1) * 111320 * Math.cos((lat1 + lat2) / 2 * Math.PI / 180);
    const y = (lat2 - lat1) * 111320;
    return Math.hypot(x, y);
  }
  function densityAt(lat, lon, points) {
    let remaining = 1;
    for (const point of points) {
      const distance = distanceMeters(lat, lon, point.lat, point.lon);
      const kernel = Math.max(0, 1 - distance / point.radius_m) ** 2;
      remaining *= 1 - point.effective_weight * kernel;
    }
    return Math.min(1, Math.max(0, 1 - remaining));
  }
  root.DaveHeatField = {distanceMeters, densityAt};
  if (typeof module !== "undefined") module.exports = root.DaveHeatField;
})(globalThis);
```

## web/heat-layer.js

```javascript
"use strict";

// A small Leaflet canvas layer, built here so no extra heat-map plugin is needed.
// It evaluates the same weighted field as Python at each 12-pixel grid midpoint.
// This is a sampled visual representation, not surveyed counts or exact boundaries.
const WeightedHeatLayer = L.Layer.extend({
  initialize: function () { this.points = []; },
  onAdd: function (map) {
    this.map = map;
    let pane = map.getPane("weightedHeatPane");
    if (!pane) { pane = map.createPane("weightedHeatPane"); pane.style.zIndex = 350; }
    this.canvas = L.DomUtil.create("canvas", "weighted-heat-canvas", pane);
    this.canvas.style.pointerEvents = "none";
    map.on("moveend zoomend resize", this.draw, this);
    map.on("movestart zoomstart", this.hide, this);
    this.draw();
  },
  onRemove: function (map) {
    map.off("moveend zoomend resize", this.draw, this);
    map.off("movestart zoomstart", this.hide, this);
    this.canvas.remove(); this.canvas = null; this.map = null;
  },
  hide: function () { if (this.canvas) this.canvas.style.visibility = "hidden"; },
  setPoints: function (points) { this.points = points; this.draw(); return this; },
  draw: function () {
    if (!this.map || !this.canvas) return;
    const size = this.map.getSize();
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(size.x * ratio);
    this.canvas.height = Math.round(size.y * ratio);
    this.canvas.style.width = size.x + "px";
    this.canvas.style.height = size.y + "px";
    L.DomUtil.setPosition(this.canvas, this.map.containerPointToLayerPoint([0, 0]));
    const ctx = this.canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);
    const step = 12;
    for (let y = 0; y < size.y; y += step) {
      for (let x = 0; x < size.x; x += step) {
        const position = this.map.containerPointToLatLng([x + step / 2, y + step / 2]);
        const value = DaveHeatField.densityAt(position.lat, position.lng, this.points);
        if (value < 0.005) continue;
        // Green -> yellow -> red uses the SAME fixed 0..1 scale on every refresh.
        // Do not renormalize every frame: that would make quiet and busy days look alike.
        const hue = 120 * (1 - value);
        ctx.fillStyle = "hsla(" + hue + ", 95%, 46%, " + (0.15 + 0.5 * value) + ")";
        ctx.fillRect(x, y, step + 0.5, step + 0.5);
      }
    }
    this.canvas.style.visibility = "visible";
  }
});
```

## web/index.html

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAXX Bytes Campus GIS Layers · Robot Demo</title>
<link rel="stylesheet" href="/vendor/leaflet.css"><link rel="stylesheet" href="/style.css">
</head><body>
<!-- DAVID: semantic headings and controls; the browser reads this structure. -->
<header><p class="eyebrow">DAVID + SHEK · LOCAL DEMONSTRATION</p><h1>MAXX Bytes Campus GIS Layers</h1>
<p>Track a simulated delivery. Zoom, pan, and switch campus layers on or off.</p></header>
<section class="panel" aria-label="Demonstration controls">
<div class="controls"><label>Delivery<select id="stop" disabled></select></label>
<label>Conditions<select id="scenario"><option value="clear">Clear walkways</option><option value="closure">Block a route segment</option><option value="return-closure">Forecast closure on return leg</option><option value="sealed">Block all destination access</option><option value="crowd">Predicted crowd / heat map</option></select></label>
<label>Demo clock<select id="rate"><option value="1">1× real time</option><option value="10">10× accelerated demonstration</option></select></label>
<button id="apply" disabled>Apply &amp; reset to base</button></div>
<p class="small">Scenario changes reset the shared trip for all viewers. Delivery stops, movement, closures and crowds are simulated. Blue outlines are supplemental OpenStreetMap buildings.</p>
<div class="controls"><button id="start" disabled>Start / resume</button><button id="pause" disabled>Pause</button><button id="reset" disabled>Reset trip</button>
<label>Position updates<select id="poll"><option value="10000">Every 10 seconds</option><option value="1000">Every 1 second (near-live)</option></select></label>
<label class="check"><input id="follow" type="checkbox"> Follow robot</label><button id="fit" disabled>Fit route</button></div>
</section>
<!-- JavaScript replaces these status values without recreating the map. -->
<section class="metrics" aria-label="Robot status">
<div><span>Status</span><strong id="phase">Loading…</strong></div><div><span id="eta-label">ETA to delivery</span><strong id="eta">—</strong></div>
<div><span>Trip distance traveled</span><strong id="distance">—</strong></div><div><span>Latest position received</span><strong id="age">—</strong></div>
</section>
<p id="notice" role="status" aria-live="polite">Connecting to the local simulation server…</p>
<div id="campus-map" aria-label="Interactive George Mason University campus map"></div>
<p class="legend"><span class="green">● Walkways</span><span class="blue">● OSM buildings</span><span class="maroon">● Demo delivery points</span><span class="red">● Access restrictions / closures</span><span class="purple">● Outbound</span><span class="teal">┄ Return route (exact or rerouted)</span><span>● Robot SIM-01</span></p>
<footer><p>Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · ODbL.</p><p id="counts"></p><p id="source"></p><p>Local OSM overlays work without internet. Optional background map tiles need internet. Heat shows predicted demonstration intensity, not measured student counts. Routes and ETA are model estimates, not approval for physical navigation.</p><p>David: zoom, pan, ETA and mobile review. Shek: simulated GIS position feed and future telemetry adapter; route-as-robot concept credited to Shek.</p></footer>
<!-- Local Leaflet loads before our field renderer and page controller. -->
<script src="/vendor/leaflet.js"></script><script src="/heat-field.js"></script><script src="/heat-layer.js"></script><script src="/app.js"></script>
</body></html>
```

## web/live.html

```html
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MAXX Bytes · MapUI live field reports</title><link rel="stylesheet" href="/vendor/leaflet.css"><link rel="stylesheet" href="/style.css"></head><body>
<header><p class="eyebrow">DAVID + SHEK · MAPUI · LIVE LOCAL STAFF REPORTS</p><h1>MAXX Bytes Campus GIS Layers</h1><p>Actual staff-reported observations, with source and age. Robot hardware is not connected.</p></header>
<section class="panel"><div class="controls"><label>Delivery<select id="destination"></select></label><label>Trip leg<select id="leg"><option value="outbound">To delivery</option><option value="return">Return to base</option></select></label><label>Read updates<select id="cadence"><option value="10000">Every 10 seconds</option><option value="1000">Every 1 second</option></select></label><label class="check"><input id="follow" type="checkbox">Follow reported location</label><button id="fit">Fit campus</button></div></section>
<section class="metrics"><div><span>Actual report status</span><strong id="location-status">No position received</strong></div><div><span>ETA from actual report</span><strong id="eta">Unavailable</strong></div><div><span>Observation age</span><strong id="age">Unknown</strong></div><div><span>Data coverage</span><strong id="coverage">Staff reports only</strong></div></section>
<p id="notice" role="status">Loading actual map snapshot; waiting for staff observations.</p>
<div id="campus-map" aria-label="Interactive campus map with live staff observations"></div>
<p id="source" class="small"></p><p class="legend"><span class="green">● Paths</span><span class="blue">● OSM buildings</span><span class="maroon">● Verified deliveries</span><span class="red">● Reported closures</span><span class="purple">● Route from last actual report</span><span class="teal">┄ Current planned return</span></p>
<details class="panel" open><summary><strong>Field reporter — send an actual observation</strong></summary><p>Enter the operator key from the server terminal. Click the map at the actual location, choose a report type, then submit. Do not enter practice reports in live mode.</p>
<div class="controls"><label>Operator key<input id="key" type="password" autocomplete="off"></label><label>Reporter / source<input id="reporter" placeholder="Your name or approved source"></label><label>Report type<select id="kind"><option value="position">Actual participant location</option><option value="place">Verified pickup / delivery place</option><option value="closure">Actual blocked path</option><option value="crowd">Observed crowd rating</option></select></label><label>Place slot<select id="slot"><option value="base">Pickup / base</option></select></label><label>Place / crowd name<input id="name" placeholder="Actual place or observation"></label></div>
<div class="controls"><label>Crowd observation ID (reuse to update)<input id="observation-id" placeholder="e.g. fenwick-north-count"></label><label>Crowd intensity estimate (0–1)<input id="weight" type="number" min="0" max="1" step=".05" value="0.5"></label><label>Confidence (0–1)<input id="confidence" type="number" min="0" max="1" step=".05" value="0.75"></label><label>Influence radius, meters<input id="radius" type="number" min="1" max="500" value="50"></label><label class="check"><input id="verified" type="checkbox">I checked this actual observation/place</label><button id="submit">Submit selected actual report</button></div>
<p id="selection">Click the map to choose the actual location.</p><p class="small">Path closure reports select the nearest routable segment within 20m of your click. Closure segments remain blocked until explicitly cleared. Crowd reports expire after 5 minutes. Location is stale after 30 seconds.</p>
<div class="controls"><label>Existing active closure<select id="closure-id"></select></label><button id="clear">Confirm selected closure has cleared</button></div><p id="report-result" role="status"></p></details>
<section class="panel"><h2>Six outbound / return checks</h2><p>Staff must verify the base and all six distinct destinations. A modeled route is not proof of complete closure coverage or physical robot permission.</p><div id="routes"></div></section>
<footer><p>Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · ODbL. Geometry is an API snapshot, not real-time obstacle sensing. <a href="https://construction.gmu.edu/">Mason construction notices</a> · <a href="https://brand.gmu.edu/events/internal-clients/scheduling">25Live scheduling</a>.</p><p>David: zoom/pan, ETA, mobile UI. Shek: live position reporting and future hardware adapter; route-as-simulated-robot concept retained in the separate simulation mode.</p></footer>
<script src="/vendor/leaflet.js"></script><script src="/heat-field.js"></script><script src="/heat-layer.js"></script><script src="/live.js"></script></body></html>
```

## web/live.js

```javascript
"use strict";
// DAVID: persistent map and source/age/ETA UI. SHEK: live-report API adapter.
// No timer generates coordinates or decrements an ETA without a new observation.
const el=id=>document.getElementById(id);
const liveMap=L.map('campus-map').setView([38.831,-77.307],16);
const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'});
const groups={},plain=value=>{const s=document.createElement('span');s.textContent=value;return s;};
for(const [kind,color] of Object.entries({walkways:'#15803d',buildings:'#2563eb',restricted:'#dc2626'})){
 groups[kind]=L.geoJSON(null,{style:{color,weight:3,fillOpacity:.25},onEachFeature:(f,l)=>{l.bindTooltip(plain(f.properties.name+' · OSM '+f.properties.osm_id),{sticky:true});}}).addTo(liveMap);
}
const places=L.layerGroup().addTo(liveMap),closures=L.layerGroup().addTo(liveMap),sourceMarkers=L.layerGroup(),nodeMarkers=L.layerGroup();
const outbound=L.polyline([],{color:'#7e22ce',weight:6}).addTo(liveMap),returning=L.polyline([],{color:'#007c91',dashArray:'7 8',weight:3}).addTo(liveMap);
const heat=new WeightedHeatLayer().addTo(liveMap),positionLayer=L.layerGroup().addTo(liveMap);
let positionMarker=null,chosen=null,chosenMarker=null,graph=[],state=null,pollTimer=null,loading=false;
const reverse=xy=>[xy[1],xy[0]];
L.control.layers({'Offline GIS':L.layerGroup().addTo(liveMap),'Online OSM tiles':tiles},{'Paths':groups.walkways,'Buildings':groups.buildings,'OSM access restrictions':groups.restricted,'Verified delivery places':places,'Staff-reported closures':closures,'Actual reported position':positionLayer,'Estimated route':outbound,'Planned return':returning,'Current crowd heat':heat,'Crowd report details':sourceMarkers,'Routing-node crowd scores':nodeMarkers},{collapsed:true}).addTo(liveMap);
for(let i=1;i<=6;i++)for(const id of ['destination','slot']){const o=document.createElement('option');o.value=String(i);o.textContent='Delivery '+i;el(id).appendChild(o);}
L.control.scale({imperial:false}).addTo(liveMap);
async function request(url,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
 try{
  const r=await fetch(url,{signal:controller.signal,cache:'no-store',...(body?{method:'POST',headers:{'Content-Type':'application/json','X-Operator-Key':el('key').value},body:JSON.stringify(body)}:{})});
  const x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x;
 }finally{clearTimeout(timer);}
}
function draw(s){
 state=s;el('notice').classList.toggle('error',!s.position_fresh);
 el('notice').textContent=s.closure_coverage+'. Crowd coverage: '+s.crowd_coverage+'. No hardware telemetry.';
 el('location-status').textContent=!s.position?'No position received':s.position_fresh?'Staff report · '+s.position.source:'STALE staff report';
 el('coverage').textContent=s.crowd_coverage;
 el('eta').textContent=s.trip.eta_seconds==null?'Unavailable':Math.ceil(s.trip.eta_seconds/60)+' min · model estimate';
 outbound.setLatLngs(s.trip.status==='available'?s.trip.coordinates.map(reverse):[]);
 const trip=s.routes.find(r=>r.id===el('destination').value);
 returning.setLatLngs(trip?.status==='available'?trip.return_route.coordinates.map(reverse):[]);
 if(s.position){
  const ll=reverse(s.position.coordinates);
  if(!positionMarker)positionMarker=L.circleMarker(ll,{radius:9,fillOpacity:1}).addTo(positionLayer);
  positionMarker.setLatLng(ll).setStyle({color:s.position_fresh?'#172b3a':'#777'});
  positionMarker.bindPopup(plain('STAFF-TEST-01 · '+s.position.source+' · observed '+s.position.observed_at+' · map-reported, not GPS'));
  if(el('follow').checked)liveMap.panTo(ll);
 }
 places.clearLayers();for(const p of Object.values(s.places))L.circleMarker(reverse(p.coordinates),{radius:7,color:p.slot==='base'?'#172b3a':'#800030',fillOpacity:1}).bindTooltip(plain(p.name+' · verified by '+p.source+' · snap '+p.snap_meters+'m')).addTo(places);
 closures.clearLayers();for(const b of s.blocked)L.polyline(b.coordinates.map(reverse),{color:'#f00',weight:9}).bindPopup(plain('Staff-reported closure '+b.id)).addTo(closures);
 sourceMarkers.clearLayers();for(const p of s.weighted_points)L.circleMarker([p.lat,p.lon],{radius:7,color:'#9a3412'}).bindPopup(plain(p.name+' · '+p.source+' · intensity '+p.weight+' × confidence '+p.confidence+' · updated '+p.updated_at)).addTo(sourceMarkers);
 nodeMarkers.clearLayers();for(const n of s.weighted_nodes)L.circleMarker(reverse(n.coordinates),{radius:4,color:`hsl(${120*(1-n.score)},90%,35%)`}).bindPopup(plain('Node '+n.node_id+' · score '+n.score+' · no additional node charge')).addTo(nodeMarkers);
 heat.setPoints(s.weighted_points);
 const previous=el('closure-id').value;el('closure-id').replaceChildren();
 for(const c of s.closures.filter(c=>c.status==='confirmed')){const o=document.createElement('option');o.value=c.id;o.textContent=c.id+' · '+c.source+(c.review_overdue?' · REVIEW OVERDUE':'');el('closure-id').appendChild(o);}
 if([...el('closure-id').options].some(o=>o.value===previous))el('closure-id').value=previous;
 el('routes').replaceChildren();for(const r of s.routes){const p=document.createElement('p');p.textContent=r.id+'. '+r.name+' — '+r.status+' — '+(r.status==='available'?r.outbound.meters+'m outward / '+r.return_route.meters+'m return. '+r.reason:r.reason);el('routes').appendChild(p);}
}
async function refresh(){if(loading)return;loading=true;try{draw(await request('/api/live/state?stop='+el('destination').value+'&leg='+el('leg').value));}catch(e){el('notice').classList.add('error');el('notice').textContent='Connection failed; observations may be stale. '+e.message;el('eta').textContent='Unavailable';outbound.setLatLngs([]);}finally{loading=false;}}
function schedule(){clearTimeout(pollTimer);pollTimer=setTimeout(async()=>{await refresh();schedule();},Number(el('cadence').value));}
for(const id of ['cadence','destination','leg'])el(id).onchange=async()=>{await refresh();schedule();};
// Pick a graph segment by geometric proximity, not by invented OSM identifiers.
function segmentDistance(point,line){
 const p=liveMap.project(reverse(point),18),a=liveMap.project(reverse(line[0]),18),b=liveMap.project(reverse(line[1]),18);
 const dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/(dx*dx+dy*dy||1)));
 return liveMap.distance(reverse(point),liveMap.unproject(L.point(a.x+t*dx,a.y+t*dy),18));
}
liveMap.on('click',e=>{chosen=[e.latlng.lng,e.latlng.lat];if(chosenMarker)chosenMarker.setLatLng(e.latlng);else chosenMarker=L.circleMarker(e.latlng,{radius:6,color:'#111',dashArray:'2 2'}).addTo(liveMap);el('selection').textContent='Selected longitude/latitude: '+chosen.join(', ');});
el('submit').onclick=async()=>{
 try{
  if(!chosen)throw Error('Click the actual location on the map first');
  if(!el('verified').checked)throw Error('Confirm this is an actual observation/place, not practice data');
  const common={coordinates:chosen,source:el('reporter').value};let endpoint,body;
  switch(el('kind').value){
   case 'position':endpoint='position';body={...common,observed_at:new Date().toISOString()};break;
   case 'place':endpoint='place';body={...common,slot:el('slot').value,name:el('name').value,verified:true};break;
   case 'crowd':endpoint='crowd';body={...common,id:el('observation-id').value,name:el('name').value,weight:Number(el('weight').value),confidence:Number(el('confidence').value),radius_m:Number(el('radius').value)};break;
   case 'closure':{
    endpoint='closure';let nearest=null,d=Infinity;for(const edge of graph){const value=segmentDistance(chosen,edge.coordinates);if(value<d){nearest=edge;d=value;}}
    if(d>20)throw Error('Click within 20m of the actual blocked walkway segment');
    body={id:'closure-'+Date.now(),status:'confirmed',edge_ids:[nearest.id],source:common.source};break;
   }
  }
  await request('/api/live/'+endpoint,body);el('report-result').textContent='Actual staff report accepted at '+new Date().toLocaleTimeString();el('verified').checked=false;await refresh();
 }catch(e){el('report-result').textContent=e.message;}
};
el('clear').onclick=async()=>{try{if(!el('verified').checked)throw Error('Confirm you observed that the closure has cleared');const c=state.closures.find(x=>x.id===el('closure-id').value);if(!c)throw Error('Choose an active closure');await request('/api/live/closure',{...c,status:'cleared',source:el('reporter').value});el('report-result').textContent='Explicit clearance recorded';await refresh();}catch(e){el('report-result').textContent=e.message;}};
el('fit').onclick=()=>liveMap.setView([38.831,-77.307],16);
setInterval(()=>{if(!state?.position)return;const age=Math.max(0,(Date.now()-Date.parse(state.position.observed_at))/1000);el('age').textContent=Math.floor(age)+'s'+(age>30?' · STALE':'');if(age>30){el('eta').textContent='Unavailable · stale position';outbound.setLatLngs([]);positionMarker?.setStyle({color:'#777'});}},500);
(async()=>{try{const [config,layers,edges]=await Promise.all([request('/api/live/config'),request('/api/live/layers'),request('/api/live/graph')]);graph=edges;for(const f of layers.features)groups[f.properties.layer]?.addData(f);el('source').textContent='OSM snapshot retrieved '+(config.source.retrieved_at||'previously')+' · '+(config.source.building_count||'bundled')+' building outlines. Geometry is not a live obstacle feed.';await refresh();schedule();}catch(e){el('notice').textContent='Startup failed: '+e.message;}})();
```

## web/style.css

```css
/* DAVID: responsive layout and readable touch controls. No routing logic lives in CSS. */
*{box-sizing:border-box}body{font-family:Arial,sans-serif;margin:20px;color:#172b3a;background:#f2f6f8;line-height:1.45}h1{font-size:clamp(1.55rem,3.5vw,2.1rem);margin:4px 0 12px}.eyebrow{font-size:.73rem;letter-spacing:.12em;color:#456175;font-weight:700}header p{margin:8px 0}.panel{background:white;border:1px solid #cdd9e0;border-radius:8px;padding:14px;margin:16px 0}.controls{display:flex;align-items:end;gap:12px;flex-wrap:wrap}label{font-size:.82rem;display:flex;flex-direction:column;gap:4px}button,select{font:inherit;font-size:.95rem;min-height:44px;padding:8px 11px;border:1px solid #9db1bd;border-radius:5px;background:white;color:#172b3a}button{cursor:pointer;font-weight:600}button:hover{background:#e9f2f8}button:disabled{opacity:.5;cursor:default}#start,#apply{background:#172b3a;color:white}.check{flex-direction:row;align-items:center;min-height:44px}.check input{height:20px;width:20px}.small{font-size:.8rem;color:#4d6371}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.metrics div{padding:12px;background:white;border:1px solid #d6e0e6;border-radius:6px}.metrics span{display:block;font-size:.75rem;color:#526a79}.metrics strong{display:block;margin-top:5px;font-size:1rem}#notice{padding:10px;border-left:4px solid #15803d;background:#e9f5ed;font-size:.9rem}#notice.error{border-color:#bd2424;background:#ffeded}#campus-map{height:65vh;min-height:350px;border:2px solid #172b3a;border-radius:8px;background:#e6ece8}.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:.82rem}.green{color:#15803d}.blue{color:#2563eb}.maroon{color:#800030}.red{color:#bd2424}.purple{color:#7e22ce}.teal{color:#007c91}footer{font-size:.82rem;color:#405a69}input[type=checkbox]{accent-color:#172b3a}.leaflet-control-layers{max-width:220px}.leaflet-control-layers label{font-size:12px}.leaflet-control-layers input{min-width:16px;min-height:16px}.leaflet-tooltip{white-space:normal;max-width:220px}.heat-canvas{pointer-events:none}.leaflet-control-attribution{font-size:10px}@media(max-width:600px){body{margin:12px}.metrics{grid-template-columns:1fr 1fr}.controls{gap:8px}.controls>label:not(.check){flex:1 1 145px}.controls select{width:100%}#campus-map{height:60vh;min-height:360px}.panel{padding:10px}.leaflet-control-layers{max-width:155px}footer{overflow-wrap:anywhere}}
/* Operator inputs use the same readable touch target as the map controls. */
input:not([type=checkbox]){font:inherit;min-height:44px;padding:8px;border:1px solid #9db1bd;border-radius:5px;max-width:100%}details summary{cursor:pointer;min-height:40px}#routes{font-size:.85rem}#report-result{font-weight:bold}input[type=number]{width:145px}
/* Classic map view: the team's map-first layout and exact shared key symbols. */
.classic-map-page h1{margin:20px 0 24px;font-size:clamp(1.65rem,3vw,2rem)}
.classic-map-page #campus-map{height:65vh;min-height:350px}
.classic-map-page #route-status{margin:8px 0 20px}
.classic-map-page .legend{align-items:center;gap:12px 18px;margin:10px 0 15px}
.classic-map-page .legend>span{display:inline-flex;align-items:center;gap:6px;color:#172b3a}
.key-line{display:inline-block;width:28px;height:0;border-top:4px solid;vertical-align:middle}
.walkway-key{border-color:#15803d}.outbound-key{border-color:#7e22ce}.return-key{border-color:#f97316;border-top-style:dashed}
.building-key{display:inline-block;width:18px;height:14px;border:2px solid #2563eb;background:rgba(37,99,235,.25);vertical-align:middle}
.delivery-symbol,.base-symbol{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#800030;color:#fff;font:700 12px Arial;border:2px solid white;box-shadow:0 0 0 1px #800030;font-style:normal;vertical-align:middle}
.base-symbol{background:#172b3a;box-shadow:0 0 0 1px #172b3a}
.restriction-symbol{display:inline-block;position:relative;width:18px;height:18px;border-radius:50%;background:#dc2626;border:1px solid #a60f18;box-sizing:border-box;vertical-align:middle;font-style:normal}
.restriction-symbol:after{content:"";position:absolute;left:3px;right:3px;top:7px;height:3px;background:white;border-radius:1px}
.map-point-icon{background:transparent!important;border:0!important}
.restriction-map-icon .restriction-symbol{box-shadow:0 0 0 2px white}
.classic-map-page .leaflet-control-layers{max-width:270px}
.classic-map-page .leaflet-control-layers label{display:block;font-size:13px;line-height:1.6}
.classic-map-page .leaflet-control-layers-overlays label>span{vertical-align:middle}
.classic-map-page .leaflet-control-layers-overlays input{margin-right:5px}
.classic-map-page .controls+.controls{margin-top:12px}
.classic-map-page .delivery-name{font-size:11px;font-weight:600;border:0;box-shadow:none;background:rgba(255,255,255,.88)}
@media(max-width:600px){.classic-map-page h1{margin:16px 0}.classic-map-page #campus-map{height:65vh;min-height:390px}.classic-map-page .leaflet-control-layers{max-width:190px}.classic-map-page .leaflet-control-layers label{font-size:11px}.classic-map-page .delivery-name{font-size:10px;max-width:95px}}
```

## web/world.html

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MAXX Bytes Campus GIS Layers</title><link rel="stylesheet" href="/vendor/leaflet.css"><link rel="stylesheet" href="/style.css"></head>
<body class="classic-map-page">
<!-- Keep the team's familiar order: route status, heading, instructions, map. -->
<p id="route-status" role="status">Loading software robot route and public campus layers…</p>
<h1>MAXX Bytes Campus GIS Layers</h1>
<p>Use the map checkboxes to show or hide each category.</p>
<div id="campus-map" aria-label="Interactive George Mason University campus map"></div>
<p id="counts" role="status">Loading campus layers…</p>
<p id="delivery-list" class="small"></p>
<div class="legend" aria-label="Map key">
<span><i class="key-line walkway-key"></i> Walkways</span>
<span><i class="building-key"></i> Buildings</span>
<span><i class="delivery-symbol">1</i> Delivery target</span>
<span><i class="base-symbol">B</i> Southside Dining base</span>
<span><i class="restriction-symbol" aria-hidden="true"></i> OSM access-tag restriction</span>
<span><i class="key-line outbound-key"></i> Outbound</span>
<span><i class="key-line return-key"></i> Return to base</span>
</div>
<p id="source" class="small"></p>
<!-- New controls sit BELOW the map, preserving the old map-first layout. -->
<section class="panel" aria-label="Software robot controls"><div class="controls">
<label>Delivery<select id="stop" disabled></select></label>
<label>Conditions<select id="scenario"><option value="clear">Published inputs + reported closures</option><option value="avoid-projects">Also avoid Construction-phase project areas</option></select></label>
<label>Playback<select id="rate"><option value="1">1× real time</option><option value="10">10× accelerated demonstration</option></select></label>
<button id="apply" disabled>Apply &amp; reset to base</button></div>
<div class="controls"><button id="start" disabled>Start / resume</button><button id="pause" disabled>Pause</button><button id="reset" disabled>Reset trip</button>
<label>Position updates<select id="poll"><option value="10000">Every 10 seconds</option><option value="1000">Every 1 second</option></select></label>
<label class="check"><input id="follow" type="checkbox">Follow robot</label><button id="fit" disabled>Fit route</button><button id="fit-campus">Campus view</button></div></section>
<section class="metrics" aria-label="Robot status"><div><span>Status</span><strong id="phase">Loading…</strong></div><div><span id="eta-label">ETA to delivery</span><strong id="eta">—</strong></div><div><span>Trip distance</span><strong id="distance">—</strong></div><div><span>Latest state received</span><strong id="age">—</strong></div></section>
<p id="notice" role="status" aria-live="polite">Connecting to public inputs…</p>
<details class="panel"><summary><strong>Weighted heat, live public inputs and source details</strong></summary><p>The bottom-left map control switches heat, node scores, project areas and background tiles. Heat represents active real event predictions or actual staff observations; an empty field means no active mapped input, not a measured empty campus.</p><div id="public-sources"></div><p><a href="/live.html">Actual staff report panel</a> — add a genuinely observed closure or crowd condition using the operator key in the server terminal.</p></details>
<footer><p>Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · ODbL. Software robot movement is computed. Building-associated delivery targets use public OSM footprint/path coordinates; they are not surveyed entrances or observed customer orders.</p><p>David: map interaction, ETA and mobile review. Shek: software robot, source integration and the route-as-robot concept.</p></footer>
<script src="/vendor/leaflet.js"></script><script src="/heat-field.js"></script><script src="/heat-layer.js"></script><script src="/world.js"></script></body></html>
```

## web/world.js

```javascript
"use strict";
// DAVID: map controls, accessible status/ETA and responsive presentation.
// SHEK: fetchState() is the integration seam for a future real telemetry feed.
const $ = id => document.getElementById(id);
const map = L.map('campus-map', {tap:true}).setView([38.831,-77.307],16);
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}).addTo(map); // Match the team's familiar OSM background; offline GIS is still available.
L.control.scale({imperial:false}).addTo(map);
const colors = {walkways:'#15803d',buildings:'#2563eb',delivery:'#800030',restricted:'#dc2626'};
const groups = {};
const text = value => { const span=document.createElement('span');span.textContent=value;return span; };
for (const [key,color] of Object.entries(colors)) {
  groups[key] = L.geoJSON(null, {
    style:{color,weight:key==='walkways'?4:key==='restricted'?4:3,fillOpacity:.25,...(key==='restricted'?{dashArray:'6 4'}:{})},
    pointToLayer:(feature,ll)=>L.circleMarker(ll,{radius:7,color,fillOpacity:1}),
    onEachFeature:(feature,layer)=>{
      const p=feature.properties || {};
      const name = p.name && p.name!==key ? p.name : `Unnamed ${key==='walkways'?'walkway':key}`;
      const rules=Object.entries(p.access_tags||{}).map(([k,v])=>k+'='+v).join(', ');
      const label = `${name}${p.osm_id?' · OSM '+p.osm_id:''}${rules?' · '+rules:''}`;
      layer.bindPopup(text(label)).bindTooltip(text(label),{sticky:true});
    }
  }).addTo(map);
}
const outbound = L.polyline([],{color:'#7e22ce',weight:7}).addTo(map);
const returning = L.polyline([],{color:'#f97316',weight:4,dashArray:'10 10',opacity:1}).addTo(map);
const closures = L.layerGroup().addTo(map);
const restrictionSymbols=L.layerGroup().addTo(map);
const projectAreas=L.geoJSON(null,{style:f=>({color:f.properties.Project_Phase==='Construction'?'#c2410c':'#64748b',weight:2,fillOpacity:.1}),onEachFeature:(f,l)=>l.bindPopup(text(f.properties.Project+' · '+f.properties.Project_Phase+' · published project area, not a confirmed walkway closure'))}); // Project areas are optional; keep the classic background unobscured.
const robot = L.circleMarker([38.831,-77.307],{radius:10,color:'#fff',weight:3,fillColor:'#111827',fillOpacity:1}).addTo(map);
robot.bindTooltip('SIM-01 · software robot');
let state=null, received=0, failed=false, busy=false, pollTimer, revision=-1;

// Retain the supplied matching field model and canvas renderer. Weighted
// nodes explain the field visually; visibility does not add any routing costs.
const heat=new WeightedHeatLayer().addTo(map);
const nodes=L.layerGroup(),sources=L.layerGroup();
// HTML labels contain only trusted constant key symbols, never source HTML.
const restrictionGroup=L.layerGroup([groups.restricted,restrictionSymbols]).addTo(map);
L.control.layers(null,{
  '<span class="key-line walkway-key"></span> Walkways':groups.walkways,
  '<span class="building-key"></span> Buildings':groups.buildings,
  '<span class="delivery-symbol">1</span> Delivery points':groups.delivery,
  '<span class="restriction-symbol"></span> Restrictions (OSM access tags)':restrictionGroup
},{collapsed:false,position:'topright'}).addTo(map);
L.control.layers(null,{
  '<span class="key-line outbound-key"></span> Outbound route':outbound,
  '<span class="key-line return-key"></span> Return to base':returning
},{collapsed:false,position:'topright'}).addTo(map);
L.control.layers({'OpenStreetMap background':tiles,'Offline GIS background':L.layerGroup()},{
  'Weighted crowd heat (active inputs)':heat,'Routing-node crowd scores':nodes,
  'Crowd source details':sources,'Published project areas':projectAreas,
  'Reported closures / planning exclusions':closures,'Software robot':robot
},{collapsed:true,position:'bottomleft'}).addTo(map);
// Pan/zoom choices persist; polling never replaces the map or its layer control.
const latlngs = coords => coords.map(([x,y])=>[y,x]);
function fitRoute(){
  const points=state?.outbound.length?latlngs(state.outbound):[robot.getLatLng()];
  map.fitBounds(L.latLngBounds(points).pad(.2),{maxZoom:17});
}
function show(s){
  state=s;received=Date.now();failed=false;
  $('phase').textContent=(s.running?'Moving · ':'Paused · ')+s.phase;
  $('route-status').textContent='Software robot: '+s.phase+' · '+s.stop.name+' · '+s.total_meters+' m round trip · outbound purple / return orange dashed.';
  if(s.phase==='complete')$('phase').textContent='Complete · back at base';
  if(s.phase==='unavailable')$('phase').textContent='No valid route';
  $('eta-label').textContent=`ETA to ${s.eta_target} · ${s.rate}× demo clock`;
  const seconds=Math.ceil(s.eta_seconds || 0);
  $('eta').textContent=s.eta_seconds===null?'Unavailable':s.phase==='complete'?'Arrived':
    `${Math.floor(seconds/60)}m ${seconds%60}s${!s.running?' (paused)':''}`;
  $('distance').textContent=`${s.traveled_meters} / ${s.total_meters} m`;
  $('notice').classList.toggle('error',s.phase==='unavailable');
  $('notice').textContent=`${s.message} ${s.rate===10?'10× playback; ETA is accelerated demo time.':''}`;
  robot.setLatLng([s.coordinates[1],s.coordinates[0]]);
  if($('follow').checked) map.panTo(robot.getLatLng());
  if(s.revision!==revision) {
    revision=s.revision;
    outbound.setLatLngs(latlngs(s.outbound));returning.setLatLngs(latlngs(s.return_route));returning.bringToFront();
    outbound.bindTooltip(text('Outbound · '+s.stop.name+' · purple'));returning.bindTooltip(text('Return to Southside Dining · orange dashed'));
    closures.clearLayers();nodes.clearLayers();sources.clearLayers();
    for(const b of s.blocked)L.polyline(latlngs(b.coordinates),{color:'#f00',weight:10}).bindPopup(text('Reported closure or conservative planning exclusion; inspect source details')).addTo(closures);
    for(const b of (s.forecast_return_blocked || []))L.polyline(latlngs(b.coordinates),{color:'#d97706',weight:9,dashArray:'4 5'}).bindPopup(text('SIMULATED forecast closure on return leg')).addTo(closures);
    for(const n of s.weighted_nodes)L.circleMarker([n.coordinates[1],n.coordinates[0]],{radius:4,color:`hsl(${120*(1-n.score)},90%,35%)`,fillOpacity:.8}).bindPopup(text(`Routing node ${n.node_id} · crowd score ${n.score} · NO separate node cost`)).addTo(nodes);
    for(const p of s.weighted_points)L.circleMarker([p.lat,p.lon],{radius:7,color:'#9a3412',fillOpacity:.7}).bindPopup(text(`${p.name} · intensity ${p.weight} × confidence ${p.confidence} · effective ${p.effective_weight.toFixed(3)} · source ${p.source} · updated ${p.updated_at} · ${p.half_life_minutes} min freshness half-life`)).addTo(sources);
    heat.setPoints(s.weighted_points);
    projectAreas.clearLayers();if(s.projects)projectAreas.addData(s.projects);

    $('stop').value=s.stop.id;$('scenario').value=s.scenario;$('rate').value=String(s.rate);
  }
  const sourceBox=document.getElementById('public-sources');
  sourceBox.replaceChildren();
  for(const [name,source] of Object.entries(s.sources||{})){
    const p=document.createElement('p');p.textContent=name+': '+(source.fresh?'CONNECTED':'UNAVAILABLE / STALE')+' · fetched '+(source.fetched_at||'never')+(source.error?' · '+source.error:'');sourceBox.appendChild(p);
  }
  for(const event of (s.events||[])){const p=document.createElement('p');p.textContent=event.title+' · '+event.location+' · '+new Date(event.starts_at).toLocaleString('en-US',{timeZone:'America/New_York'})+' to '+new Date(event.ends_at).toLocaleString('en-US',{timeZone:'America/New_York'})+' Eastern'+' · published schedule, not measured crowd';sourceBox.appendChild(p);}
  const policy=document.createElement('p');policy.textContent='Conservative Construction-area avoidance: '+s.project_excluded_edges+' graph segments excluded. These published footprints are not a complete confirmed-closure inventory.';sourceBox.appendChild(policy);
  const active=document.createElement('p');active.textContent='Weighted heat: '+s.weighted_points.length+' active sources; '+s.weighted_nodes.length+' scored routing nodes. Future events appear only during their published time windows.';sourceBox.appendChild(active);
  const note=document.createElement('p');note.textContent=s.crowd_note||'';sourceBox.appendChild(note);
  // Heat stays at the scenario's planning snapshot so it agrees with route costs.
  $('start').disabled=!s.outbound.length || s.phase==='complete' || !['projects','events'].every(k=>s.sources?.[k]?.fresh);
}
async function request(url,body){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
  try{
    const response=await fetch(url,{cache:'no-store',signal:controller.signal,
      ...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    const result=await response.json();if(!response.ok)throw new Error(result.error || response.status);return result;
  } finally {clearTimeout(timeout);}
}
function error(e){failed=true;$('notice').classList.add('error');$('notice').textContent='Connection failed — last displayed position may be stale. '+e.message;}
async function fetchState(){
  if(busy)return;busy=true;
  try{show(await request('/api/state'));}catch(e){error(e);}finally{busy=false;}
}
function schedule(){clearTimeout(pollTimer);pollTimer=setTimeout(async()=>{await fetchState();schedule();},Number($('poll').value));}
$('poll').onchange=async()=>{await fetchState();schedule();};
$('fit').onclick=fitRoute;
$('fit-campus').onclick=()=>map.setView([38.831,-77.307],16);
for(const action of ['start','pause','reset']) $(''+action).onclick=async()=>{
  try{show(await request('/api/action',{action}));schedule();}catch(e){error(e);}
};
$('apply').onclick=async()=>{
  $('apply').disabled=true;
  try{show(await request('/api/configure',{stop:$('stop').value,scenario:$('scenario').value,rate:Number($('rate').value)}));fitRoute();schedule();}
  catch(e){error(e);}finally{$('apply').disabled=false;}
};
setInterval(()=>{
  if(!received)return;
  const age=Math.floor((Date.now()-received)/1000),stale=failed||age>Math.max(15,Number($('poll').value)/1000*2.5);
  $('age').textContent=`${age}s ago${stale?' · STALE':''}`;
},500);
(async()=>{
  try{
    const [config,layers]=await Promise.all([request('/api/config'),request('/api/layers')]);
    const counts={walkways:0,buildings:0,delivery:0,restricted:0};
    for(const f of layers.features){
      const k=f.properties?.layer;
      if(groups[k]){groups[k].addData(f);counts[k]++;}
      if(k==='restricted' && f.geometry.type==='LineString'){
        const coords=f.geometry.coordinates,xy=coords[Math.floor(coords.length/2)];
        L.marker([xy[1],xy[0]],{icon:L.divIcon({className:'map-point-icon restriction-map-icon',html:'<i class="restriction-symbol"></i>',iconSize:[18,18],iconAnchor:[9,9]})})
          .bindPopup(text('OSM '+f.properties.osm_id+' · '+Object.entries(f.properties.access_tags||{}).map(([k,v])=>k+'='+v).join(', ')+' · access limitation, not a verified construction closure')).addTo(restrictionSymbols);
      }
    }
    for(const stop of config.stops){
      const option=document.createElement('option');option.value=stop.id;option.textContent=stop.name;$('stop').appendChild(option);
      L.marker([stop.coordinates[1],stop.coordinates[0]],{icon:L.divIcon({className:'map-point-icon',html:'<span class="delivery-symbol">'+stop.id+'</span>',iconSize:[24,24],iconAnchor:[12,12]})})
        .bindTooltip(text(stop.id+' · '+stop.name),{permanent:false,direction:'right',className:'delivery-name',offset:[10,0]})
        .bindPopup(text(stop.name+' · OSM building '+stop.osm_building_id+' · path coordinates '+stop.coordinates.join(', ')+' · '+stop.snap_meters+'m from source footprint · planned software delivery target'))
        .addTo(groups.delivery);counts.delivery++;
    }
    L.marker([config.base[1],config.base[0]],{icon:L.divIcon({className:'map-point-icon',html:'<span class="base-symbol">B</span>',iconSize:[24,24],iconAnchor:[12,12]})}).bindTooltip(text('Base · '+(config.base_place?.name||'Southside Dining'))).addTo(map);
    $('counts').textContent=Object.entries(counts).map(([k,v])=>`${k}: ${v}`).join(' | ');
    $('source').textContent=config.source+'. '+config.building_note;
    $('delivery-list').textContent='Base: '+config.base_place.name+' · '+config.stops.map(p=>p.id+': '+p.name).join(' | ');
    await fetchState();if(!state)throw new Error('No initial state');map.setView([38.831,-77.307],16);
    for(const id of ['stop','apply','pause','reset','fit'])$(id).disabled=false;
    schedule();
  }catch(e){error(e);}
})();
```

## world.py

```python
"""Software robot driven by CURRENT public-world inputs, never physical GPS."""
import hashlib,json,time
from engine import Simulation,edge_key,iso
from crowd_model import validate_point,prepare_points,density_at
from public_sources import project_edges

class WorldRobot(Simulation):
    def __init__(self,campus,sources,reports):
        self.sources=sources;self.reports=reports;self.source_signature=None;self.context={}
        super().__init__(campus)
    def configure(self,stop_id,scenario,rate):
        if scenario not in {'clear','avoid-projects'}:raise ValueError('Use current data or conservative project-area avoidance; synthetic scenarios are in simulation mode')
        self._configuring=True
        super().configure(stop_id,'clear',rate)
        self.scenario=scenario
        feeds=self.sources.snapshot();now=time.time()
        project_item=feeds.get('projects',{});event_item=feeds.get('events',{})
        # Stale construction boundaries are retained for conservative exclusions,
        # never silently reopened. Status says whether refresh actually succeeded.
        projects=(project_item.get('data') or {}).get('features',[])
        events=event_item.get('data') or []
        manual=self.reports.snapshot()
        self.blocked={e['id'] for e in manual['blocked']}
        project_blocked=project_edges(self.campus,projects) if scenario=='avoid-projects' else set()
        self.blocked |= project_blocked
        self.crowds=list(self.reports.data['crowds'].values())
        # Resolve a PUBLISHED location to a known OSM building. No generic geocoder
        # guesses or invented entrances. Unmatched events remain listed, unmapped.
        building=next((f for f in self.campus.buildings if f['properties'].get('name')=='Johnson Center'),None)
        if building and event_item.get('fresh'):
            ring=building['geometry']['coordinates'][0];lon=sum(x[0] for x in ring[:-1])/(len(ring)-1);lat=sum(x[1] for x in ring[:-1])/(len(ring)-1)
            for event in events:
                if 'johnson center' in event['location'].lower():
                    self.crowds.append(validate_point({'id':event['id'],'name':event['title'],
                        'source':event['source'],'kind':'event','data_mode':'predicted','lat':lat,'lon':lon,
                        'radius_m':80,'weight':.5,'confidence':.3,'half_life_minutes':60,
                        'starts_at':event['starts_at'],'ends_at':event['ends_at'],'updated_at':event_item['fetched_at']}))
        self.outbound=self.campus.route(self.campus.base,self.stop['node'],self.blocked,self.crowds,now) or []
        self.return_path=self.outbound[::-1];self.return_blocked=set(self.blocked)
        self.trip=self.outbound+self.return_path[1:] if self.outbound else []
        self.path=self.outbound or None;self.return_kind='exact retrace under current input snapshot'
        self.segment_seconds=[self.campus.duration(a,b,self.crowds,now) for a,b in zip(self.trip,self.trip[1:])]
        self.segment_meters=[self.campus.edges[edge_key(a,b)]['meters'] for a,b in zip(self.trip,self.trip[1:])]
        self.out_seconds=sum(self.segment_seconds[:max(0,len(self.outbound)-1)]);self.total_seconds=sum(self.segment_seconds)
        self.weighted_points=prepare_points(self.crowds,now,now+.001)
        self.weighted_nodes=[{'node_id':n,'coordinates':xy,'score':density_at(xy[1],xy[0],self.weighted_points)} for n,xy in self.campus.nodes.items() if density_at(xy[1],xy[0],self.weighted_points)>.001]
        self.context={'projects':{'type':'FeatureCollection','features':projects},'events':events,
            'sources':{k:{a:b for a,b in v.items() if a!='data'} for k,v in feeds.items()},
            'optional_project_avoidance':scenario=='avoid-projects','project_excluded_edges':len(project_blocked),
            'crowd_note':'Event influence is a heuristic prediction; no live people counter or full class schedule feed is connected.'}
        self.source_signature=self.signature(feeds)
        self.elapsed=0;self.running=False;self.last=self.clock();self.planned_at=iso(now)
        self._configuring=False
        return self.snapshot(check_sources=False)
    def action(self,action):
        if action=='start' and not all(self.sources.snapshot().get(k,{}).get('fresh') for k in ('projects','events')):
            raise ValueError('Public sources are unavailable/stale. Wait for refresh or use the separately labeled simulation mode.')
        return super().action(action)
    def signature(self,feeds):
        from crowd_model import timestamp
        now=time.time()
        events=feeds.get('events',{}).get('data') or []
        windows=[(e['id'],timestamp(e['starts_at'])<=now<timestamp(e['ends_at'])) for e in events]
        return hashlib.sha256(json.dumps([[(k,v.get('data'),v.get('fresh')) for k,v in sorted(feeds.items())],[self.reports.data['closures'],self.reports.data['crowds']],windows],sort_keys=True).encode()).hexdigest()
    def snapshot(self,check_sources=True):
        if check_sources and not getattr(self,'_configuring',False) and self.source_signature is not None:
            feeds=self.sources.snapshot()
            if self.signature(feeds)!=self.source_signature:
                self.configure(self.stop['id'],self.scenario,self.rate)
                self.context['replan_notice']='Source/report conditions changed: trip paused and reset at base; review and Start again.'
        s=super().snapshot();s['mode']='software_robot_with_public_world_inputs';s.update(self.context)
        s['sources']={k:{a:b for a,b in v.items() if a!='data'} for k,v in self.sources.snapshot().items()}
        s['message']='SOFTWARE ROBOT · current published map/project/event inputs. Motion is computed, not physical GPS. '+self.context.get('replan_notice','')
        return s
```
