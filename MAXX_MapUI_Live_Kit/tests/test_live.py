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
