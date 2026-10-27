"""Single outbound software-robot demo; mixed roads/walkways need review."""
import json
import secrets
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer

KIT = Path(__file__).resolve().parent / 'MAXX_MapUI_Live_Kit'
sys.path.insert(0, str(KIT))
import engine
from engine import Campus, edge_key, meters
from live_state import LiveState
from public_sources import PublicSources
from world import WorldRobot
from server import world_handler

# Model assumption for software playback, NOT a measured robot speed.
engine.SPEED_MPS = 2.5
engine.ALLOWED = {'footway', 'path', 'pedestrian', 'cycleway', 'service', 'residential'}
START = [-77.30774144782609, 38.83143003478261]
GOAL = [-77.295273904319, 38.830452983017]

def load_campus():
    # Prefer the downloaded network; retain the bundled network as a fallback.
    candidates = sorted((KIT/'data').glob('overcup-*'), reverse=True) + [KIT/'data']
    for folder in candidates:
        c = Campus(folder)
        a = min(c.nodes, key=lambda n: meters(c.nodes[n], START))
        b = min(c.nodes, key=lambda n: meters(c.nodes[n], GOAL))
        if c.route(a, b):
            c.base = a
            c.base_place = {'name': 'Horizon Hall', 'coordinates': c.nodes[a]}
            c.stops = [{'id': '1', 'name': '4504 Overcup Court', 'node': b,
                'coordinates': c.nodes[b], 'requested_coordinates': GOAL,
                'snap_meters': round(meters(c.nodes[b], GOAL), 1),
                'osm_building_id': 'address match; entrance unverified'}]
            from map_features import add_access_restrictions
            add_access_restrictions(c, folder)
            print('Routing dataset:', folder, flush=True)
            print('Destination offset:', c.stops[0]['snap_meters'], 'm', flush=True)
            return c
    raise RuntimeError('No connected mixed-network route; existing demo unchanged.')

class OneWayRobot(WorldRobot):
    def configure(self, stop_id, scenario, rate):
        # Reuse closures, event predictions and the existing weighted router.
        self.building = True
        try:
            super().configure('1', scenario, rate)
            self.return_path = []
            self.return_blocked = set(self.blocked)
            self.return_kind = 'no return journey'
            self.trip = list(self.outbound)
            count = max(0, len(self.trip)-1)
            self.segment_seconds = self.segment_seconds[:count]
            self.segment_meters = self.segment_meters[:count]
            self.total_seconds = self.out_seconds = sum(self.segment_seconds)
            self.alternative = []
            # Search for a distinct route that avoids a middle route segment.
            pairs = list(zip(self.outbound, self.outbound[1:]))
            middle = len(pairs)//2
            for a, b in pairs[middle:] + pairs[:middle]:
                alternate = self.campus.route(self.campus.base, self.stop['node'],
                    self.blocked | {edge_key(a, b)}, self.crowds)
                if alternate:
                    self.alternative = alternate
                    break
        finally:
            self.building = False
        return self.snapshot(check_sources=False)

    def snapshot(self, check_sources=True):
        if getattr(self, 'building', False):
            return super().snapshot(check_sources=False)
        s = super().snapshot(check_sources=check_sources)
        s['eta_target'] = '4504 Overcup Court'
        s['alternative_route'] = [self.campus.nodes[n] for n in self.alternative]
        s['message'] += (' Mixed walkway/street candidate; entrances and road permissions '
            'unverified. Software speed assumption: 2.5 m/s. ')
        s['message'] += ('20-minute model target met.' if self.total_seconds <= 1200
            and self.trip else '20-minute model target NOT met or no route.')
        return s

def main():
    campus = load_campus()
    # Separate report storage prevents mixing old six-stop observations.
    reports = LiveState(campus, KIT/'runtime/overcup-reports.json')
    sources = PublicSources(KIT/'data/public-cache')
    sources.start()
    robot = OneWayRobot(campus, sources, reports)
    key = secrets.token_urlsafe(18)
    Base = world_handler(campus, robot, reports, key)

    class Handler(Base):
        def do_GET(self):
            path = self.path.split('?')[0]
            if path == '/api/route.geojson':
                with reports.lock:
                    s = robot.snapshot()
                    features = [{'type': 'Feature', 'properties': {'route': label,
                        'status': 'mixed road/walkway candidate; review required'},
                        'geometry': {'type': 'LineString', 'coordinates': coords}}
                        for label, coords in [('preferred', s['outbound']),
                        ('alternative', s['alternative_route'])] if len(coords) >= 2]
                return self.reply(200, {'type': 'FeatureCollection', 'features': features})
            if path in ('/', '/world.html', '/world.js'):
                name = 'world.js' if path.endswith('.js') else 'world.html'
                content = (KIT/'web'/name).read_text(encoding='utf-8')
                if name.endswith('.js'):
                    content = content.replace('s.return_route', 's.alternative_route')
                    content = content.replace('Return to base', 'Alternative outbound route')
                    content = content.replace('Return to Southside Dining', 'Alternative outbound route')
                    content = content.replace('back at base', 'at delivery destination')
                    content = content.replace(' m round trip', ' m outbound')
                    content = content.replace('outbound purple / return orange dashed.',
                        'preferred purple / alternative orange dashed.')
                    content = content.replace('Base · ', 'Start · ')
                    content = content.replace('map.setView([38.831,-77.307],16);', 'fitRoute();')
                else:
                    content = content.replace('Southside Dining base', 'Horizon Hall start')
                    content = content.replace('Return to base', 'Alternative outbound route')
                    content = content.replace('Every 10 seconds</option>', 'Every 10 seconds</option>')
                body = content.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/javascript; charset=utf-8'
                    if name.endswith('.js') else 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    server = ThreadingHTTPServer(('127.0.0.1', 8012), Handler)
    print('Operator key (keep private):', key, flush=True)
    print('Open http://127.0.0.1:8012/world.html', flush=True)
    print('GeoJSON: http://127.0.0.1:8012/api/route.geojson', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
