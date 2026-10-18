"""Mission tests using the actual team's repaired Dijkstra implementation."""
from pathlib import Path
import json
import tempfile
import unittest
from backend import map_route_service as service

ROOT = Path.cwd()


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'map.json'

    def tearDown(self):
        self.temp.cleanup()

    def graph(self, tags=None, refs=None, points=None, **kwargs):
        data={'elements':[{'type':'way','id':1,'nodes':refs or [1,2,3],
              'geometry':[{'lat':p[0],'lon':p[1]} for p in (points or [(38.83,-77.31),(38.831,-77.31),(38.832,-77.31)])],
              'tags':{'highway':'footway',**(tags or {})}}]}
        self.path.write_text(json.dumps(data))
        return service.build_delivery_graph(self.path,**kwargs)[0]

    def test_preserves_intermediate_osm_nodes(self):
        self.assertEqual(len(self.graph().nodes),3)

    def test_uses_team_dijkstra_meter_costs(self):
        result=service.dijkstra(self.graph(),'1','3')
        self.assertTrue(220<result[0]<225)
        self.assertEqual(len(result[2]),3)

    def test_excludes_stairs(self):
        with self.assertRaises(ValueError):self.graph({'highway':'steps'})

    def test_excludes_private_access(self):
        with self.assertRaises(ValueError):self.graph({'access':'private'})

    def test_excludes_foot_prohibition(self):
        with self.assertRaises(ValueError):self.graph({'foot':'no'})

    def test_excludes_closed_way(self):
        with self.assertRaises(ValueError):self.graph({'closed':'yes'})

    def test_excludes_area_as_linear_path(self):
        with self.assertRaises(ValueError):self.graph({'area':'yes'})

    def test_road_preview_requires_explicit_policy(self):
        with self.assertRaises(ValueError):self.graph({'highway':'residential'})
        self.assertEqual(len(self.graph({'highway':'residential'},preview_roads=True).nodes),3)

    def test_excludes_main_carriageways(self):
        with self.assertRaises(ValueError):self.graph({'highway':'primary'},preview_roads=True)

    def test_pedestrian_one_way_is_respected(self):
        graph=self.graph({'oneway:foot':'yes'})
        self.assertIsNotNone(service.dijkstra(graph,'1','3'))
        self.assertIsNone(service.dijkstra(graph,'3','1'))

    def test_invalid_coordinates_rejected(self):
        with self.assertRaises(ValueError):self.graph(points=[(100,0),(0,0),(1,0)])

    def test_snap_uses_shape_node(self):
        graph=self.graph()
        node,distance=service.snap(graph,(38.831,-77.31))
        self.assertEqual(node,'2');self.assertEqual(distance,0)

    def test_distant_snap_rejected(self):
        with self.assertRaises(ValueError):service.snap(self.graph(),(0,0))

    def test_does_not_bridge_disconnected_paths(self):
        graph=self.graph()
        graph.add_node('other',38.84,-77.31)
        self.assertIsNone(service.dijkstra(graph,'1','other'))

    @unittest.skipUnless((ROOT/'gmu_map_16OCT26.json').is_file(),'Existing mission dataset required')
    def test_required_horizon_overcup_round_trip(self):
        mission,graph,tags=service.make_mission(ROOT/'gmu_map_16OCT26.json')
        m=mission['metadata']
        self.assertEqual(m['pickup'],list(service.PICKUP))
        self.assertEqual(m['destination'],list(service.DESTINATION))
        self.assertLess(m['pickup_snap_m'],35);self.assertLess(m['destination_snap_m'],35)
        self.assertFalse(m['robot_navigation_approved']);self.assertTrue(m['simulated'])
        self.assertGreater(m['outbound_m'],0)
        self.assertAlmostEqual(m['total_m'],m['outbound_m']+m['return_m'])
        outbound,inbound=mission['features']
        self.assertEqual(outbound['geometry']['coordinates'][-1],inbound['geometry']['coordinates'][0])
        self.assertEqual(outbound['geometry']['coordinates'][0],inbound['geometry']['coordinates'][-1])


if __name__=='__main__':
    unittest.main(verbosity=2)
