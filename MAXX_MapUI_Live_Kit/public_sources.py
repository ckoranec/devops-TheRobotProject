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
