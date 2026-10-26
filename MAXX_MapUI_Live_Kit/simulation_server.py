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
