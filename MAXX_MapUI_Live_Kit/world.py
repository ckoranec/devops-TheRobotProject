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
