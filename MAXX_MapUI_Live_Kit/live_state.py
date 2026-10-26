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
