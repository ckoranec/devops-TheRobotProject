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
