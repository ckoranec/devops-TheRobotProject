"""Small offline tests for source consistency and generated-preview freshness."""
import ast  # Demonstrate exactly what four opening quotes do.
import importlib.util  # Load a temporary copy of the builder safely.
import json  # Create tiny clearly synthetic fixtures.
import subprocess  # Verify runtime imports in a fresh Python process.
import sys  # Use the current interpreter for the runtime check.
import shutil  # Copy the unchanged backend into each isolated test checkout.
import tempfile  # Avoid modifying any real project outputs.
import unittest  # Run with Python's built-in test runner.
from pathlib import Path  # Work on Windows and Linux.
from export_layers import convert  # Test the actual converter rather than a duplicate.

HERE = Path(__file__).resolve().parent  # Locate the reviewed preview code.
ROOT = HERE.parents[3]  # Locate the existing shared backend.


class PreviewTests(unittest.TestCase):  # Group related correctness checks.
    def setUp(self):  # Give every test its own tiny checkout.
        self.temp = tempfile.TemporaryDirectory()  # Automatically clean up fixtures.
        self.root = Path(self.temp.name)  # This is never the user's repository.
        self.folder = self.root/'html/web/public/dave-campus-map'  # Preserve the production folder depth.
        self.folder.mkdir(parents=True)  # Create only the fixture directories.
        (self.root/'backend').mkdir()  # Provide the unchanged router dependency.
        shutil.copy2(ROOT/'backend/dijkstra_json.py', self.root/'backend/dijkstra_json.py')  # Test the checked-out team backend.
        for name in ('build_preview.py', 'export_layers.py'):  # Make hashes refer to files inside the fixture root.
            shutil.copy2(HERE/name, self.folder/name)  # Do not alter the originals.
        way = {'type': 'way', 'id': 1, 'nodes': [1, 2], 'tags': {'highway': 'footway'}, 'geometry': [{'lon': -77.3, 'lat': 38.83}, {'lon': -77.299, 'lat': 38.83}]}  # Explicit synthetic connected path.
        self.map = {'elements': [way]}  # Use the same schema as the canonical map.
        ring = [[-77.3, 38.83], [-77.3, 38.83001], [-77.29999, 38.83], [-77.3, 38.83]]  # Closed synthetic building ring.
        buildings = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': 'TEST building', 'source': 'synthetic unit fixture'}, 'geometry': {'type': 'Polygon', 'coordinates': [ring]}}]}  # Never label a fixture as live OSM.
        delivery = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'id': 'TEST', 'properties': {'name': 'TEST target', 'source': 'synthetic unit fixture'}, 'geometry': {'type': 'Point', 'coordinates': [-77.299, 38.83]}}]}  # Explicit input proves delivery is not inferred.
        config = {'map': '../../../../gmu_map.json', 'buildings': 'buildings.json', 'delivery': 'delivery.json', 'start': [-77.3, 38.83], 'destination_id': 'TEST', 'max_snap_m': 30}  # One source for layers and route.
        for path, data in [(self.root/'gmu_map.json', self.map), (self.folder/'buildings.json', buildings), (self.folder/'delivery.json', delivery), (self.folder/'preview-config.json', config)]:  # Write only small fixtures.
            path.write_text(json.dumps(data), encoding='utf-8')  # Deterministic local inputs.
        spec = importlib.util.spec_from_file_location('fixture_preview_builder', self.folder/'build_preview.py')  # Resolve this fixture's paths.
        self.builder = importlib.util.module_from_spec(spec)  # Create its isolated module.
        spec.loader.exec_module(self.builder)  # Importing must not publish anything.

    def tearDown(self):  # Restore no files, because real files were never changed.
        self.temp.cleanup()  # Remove the temporary checkout.

    def test_highway_only_data_does_not_invent_buildings_or_delivery(self):  # Distinguish missing coverage from data fabrication.
        result = convert(self.map, 'gmu_map.json')  # Convert just the highway fixture.
        self.assertEqual(result['counts'], {'walkways': 1, 'buildings': 0, 'delivery': 0, 'restricted': 0})  # Report honest zeros.

    def test_build_has_all_inputs_and_same_map_dependency(self):  # Verify the positive path.
        manifest = self.builder.build()  # Generate both artifacts together.
        self.assertEqual(manifest['counts']['buildings'], 1)  # The supplied outline is exported.
        self.assertEqual(manifest['counts']['delivery'], 1)  # The explicit target is exported.
        self.assertIs(manifest['crowd_sources_enabled'], False)  # Verify the explicit no-crowd mode.
        self.assertEqual(manifest['map'], 'gmu_map.json')  # The canonical filename is visible.
        self.assertEqual(self.builder.check(), manifest)  # Fresh bytes pass the read-only check.

    def test_changed_map_rejects_old_route(self):  # A saved route cannot silently follow an old map.
        self.builder.build()  # Establish a complete original preview.
        with (self.root/'gmu_map.json').open('a') as stream:  # Change the source without regenerating.
            stream.write(' ')  # Even a byte-level change is detected.
        with self.assertRaisesRegex(ValueError, 'STALE'):  # Require a helpful failure.
            self.builder.check()  # Do not rewrite anything during a check.

    def test_changed_backend_rejects_old_route(self):  # Algorithm/policy edits also require regeneration.
        self.builder.build()  # Establish a fresh preview.
        with (self.root/'backend/dijkstra_json.py').open('a') as stream:  # Modify only the fixture backend.
            stream.write('\n# fixture change\n')  # Do not change Shek's or another teammate's actual file.
        with self.assertRaisesRegex(ValueError, 'STALE'):  # Fingerprints must include backend code.
            self.builder.check()  # Old route becomes unusable until rebuilt.

    def test_changed_output_rejects_manifest(self):  # A hand-edited output must not pass provenance checks.
        self.builder.build()  # Publish an original output set.
        (self.folder/'route-preview.geojson').write_text('{}')  # Corrupt the fixture route only.
        with self.assertRaisesRegex(ValueError, 'STALE'):  # Detect output mismatch.
            self.builder.check()  # Do not serve it as current.

    def test_existing_output_requires_explicit_replace(self):  # Preserve the boss's non-overwrite safeguard.
        self.builder.build()  # Create output once.
        original = (self.folder/'route-preview.geojson').read_bytes()  # Record the saved result.
        with self.assertRaises(FileExistsError):  # A plain build cannot overwrite it.
            self.builder.build()  # No replace flag.
        self.assertEqual((self.folder/'route-preview.geojson').read_bytes(), original)  # The file survived unchanged.
        self.builder.build(replace=True)  # A deliberate rebuild is allowed.

    def test_missing_target_preserves_outputs(self):  # A missing business input is not a guessed route.
        self.builder.build()  # Keep a previously usable preview.
        original = (self.folder/'route-preview.geojson').read_bytes()  # Remember its bytes.
        (self.folder/'delivery.json').write_text('{"type":"FeatureCollection","features":[]}')  # Remove fixture targets.
        with self.assertRaises(ValueError):  # The new build must fail.
            self.builder.build(replace=True)  # Even replace cannot bypass input validation.
        self.assertEqual((self.folder/'route-preview.geojson').read_bytes(), original)  # Do not publish a half-build.

    def test_invalid_delivery_coordinate_rejected(self):  # Keep defensive geographic validation.
        with self.assertRaises(ValueError):  # Infinity is not a location.
            convert(self.map, 'gmu_map.json', delivery={'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': 'TEST', 'source': 'fixture'}, 'geometry': {'type': 'Point', 'coordinates': [float('inf'), 38.83]}}]})  # Test the public conversion boundary.

    def test_fresh_build_does_not_load_crowd_pipeline(self):  # Check the actual entry point in a separate process.
        script = str(self.folder/'build_preview.py')  # Run this test checkout's complete builder.
        code = (  # Supply the current interpreter a small runtime probe.
            'import runpy,sys;'  # Import only standard-library tools.
            'sys.path.insert(0,sys.argv[1]);'  # Find the fixture exporter beside the builder.
            'script=sys.argv[2];sys.argv=[script,"--replace"];'  # Select an explicit local rebuild.
            'runpy.run_path(script,run_name="__main__");'  # Execute the real builder entry point.
            'assert not ({"crowd_model","public_sources","world","live_state"} & set(sys.modules))'  # Reject the known crowd/live pipeline.
        )  # End the probe, which never launches a live server.
        result = subprocess.run([sys.executable, '-c', code, str(self.folder), script], capture_output=True, text=True)  # Preserve error text for debugging.
        self.assertEqual(result.returncode, 0, result.stderr)  # A crowd import or build failure must fail the test.

    def test_four_quotes_leave_a_literal_quote(self):  # Answer the reviewer's Python syntax question precisely.
        source = '\"\"\"\"Read the team map.\"\"\"'  # Reproduce four opening quotes and three closing quotes.
        self.assertEqual(ast.get_docstring(ast.parse(source)), '\"Read the team map.')  # It is valid, but the leading quote is part of the docstring.


if __name__ == '__main__':  # Let a teammate run this file directly too.
    unittest.main()  # Report failures with standard unittest output.
