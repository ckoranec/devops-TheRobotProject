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
