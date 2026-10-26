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
