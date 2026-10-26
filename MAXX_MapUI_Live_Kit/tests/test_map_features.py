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
