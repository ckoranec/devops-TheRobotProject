# Reproducible campus overlay preview

## Scope and cleanup

This is the original gis-layers.html overlay/saved-route page. It runs no
crowd ingestion, event/class predictions, people counters, heat-map jobs or
software-robot simulation. Its manifest explicitly records
crowd_sources_enabled=false.

The team removed MAXX_MapUI_Live_Kit in MapUI commit8147e1e. This change does
not recreate that folder. It also removes the obsolete root launchers:
overcup_demo.py, download_overcup_network.py, inspect_route_connection.py
and inspect_route_data.py. Campus.route and Simulation were definitions
inside the removed kit, not separate files to delete from the shared backend.

Shared backend/dijkstra_json.py, gis-layers.html, campus-layers.js,
gmu_map_api_v2_16OCT26.py and gmu_map.json remain unchanged.

## Inputs and ownership

- Canonical routing/display input: repository-root gmu_map.json, declared
  in preview-config.json. A missing input is an error, not a dated fallback.
- Buildings: explicit supplemental .local-inputs/buildings.geojson snapshot.
  The shared highway-only acquisition query supplies no building outlines.
- Targets: delivery-points.geojson. The Overcup point is planned; its entrance
  and permissions are not verified and it is not an observed customer order.
- David maintains this adapter/builder. The team should confirm ownership of
  upstream data coverage and operational verification of delivery targets.

The optional building downloader converts only simple closed OSM building
ways in the specified bbox. It records source, retrieval time and coverage;
it does not claim universal building coverage or live obstacle observations.

## Reproduce from the repository root

First build, with a genuine building download:

```powershell
python .\html\web\public\dave-campus-map\build_preview.py --fetch-buildings --replace
```

Later builds preserve/reuse that input:

```powershell
python .\html\web\public\dave-campus-map\build_preview.py --replace
```

The downloader refuses to overwrite an existing input. Preserve an older
snapshot deliberately before refreshing. If fetching fails, obtain a reviewed
building FeatureCollection; never substitute fabricated campus outlines.

Check freshness and run the10 offline tests:

```powershell
python .\html\web\public\dave-campus-map\build_preview.py --check
python -m unittest discover -s .\html\web\public\dave-campus-map -p test_preview.py -v
```

Serve the repository root locally:

```powershell
python -m http.server 8004 --bind 127.0.0.1
```

Open http://127.0.0.1:8004/html/web/public/dave-campus-map/gis-layers.html
and press Ctrl+F5. Localhost/HTTPS is required for browser fingerprints.
Leaflet's existing CDN and map tiles still need internet. Keep the root
server local; it is not a public production deployment.

## Freshness and generated artifacts

The builder reads the same map for layers and the original shared Dijkstra.
It fingerprints map/config/input/code dependencies and both generated outputs.
It stages the complete result, publishes the manifest last and rejects mixed
or stale files. The browser withholds a stale route. Cache bypass alone does
not rerun Dijkstra. If a check fails, regard all displayed preview layers as
stale even though the unchanged layer renderer may have already drawn them.

campus-layers.geojson, route-preview.geojson, preview-manifest.json and
.local-inputs/ are generated/local artifacts. They are not tracked; build them
before viewing a new checkout. --replace affects only generated output.

The shared Dijkstra is unchanged, distance-weighted and undirected. This
preview does not add closure/crowd/permission-aware routing or motor commands.
A snapped node is not a verified last-meter connection. The separate moving
world.html interface was part of the removed kit and is not provided here.

Review only the small source/config/test/README changes and explicit obsolete
file removals. Personal ZIPs, teaching copies, PDFs and IDE/venv files are not
part of the submission. Preserve shared history; do not force-push it.
