# Provenance and sample-data boundaries

The original team files are copied unchanged from `human-only`, pinned commit `e88c2cc23ef9ddc495056151b1379eb7b3b1df71`, fetched October 26, 2026. See SOURCE_MANIFEST.json for SHA-256 and Git blob identities. The filename identifies October 16, 2026 as the team's export name; this kit does not independently certify that collection date. Preserve OSM attribution and applicable ODbL requirements when redistributing or deriving databases.

Sources:

- [Team GIS folder](https://github.com/ckoranec/devops-TheRobotProject/tree/e88c2cc23ef9ddc495056151b1379eb7b3b1df71/html/web/public/dave-campus-map)
- [Original map JSON](https://github.com/ckoranec/devops-TheRobotProject/blob/e88c2cc23ef9ddc495056151b1379eb7b3b1df71/gmu_map_16OCT26.json)
- [OpenStreetMap attribution / database license](https://www.openstreetmap.org/copyright)
- [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)

`campus-layers.geojson` contains 1,213 walkway and 19 restriction features. There are no buildings or delivery points in this snapshot. `gmu_map_16OCT26.json` contains 1,838 ways with embedded node geometry, no building-tagged ways. It contains access tags used for demonstration exclusions; these are not a current campus closure feed.

`buildings.geojson` contains 145 real OSM building polygons fetched October 26, 2026 using the OpenStreetMap map API. It covers simple closed building ways for bbox `[-77.312, 38.827, -77.299, 38.835]` (west, south, east, north). Multipolygon relations are not imported, and buildings outside that central-campus region may be absent. The file includes its source URL, download time and license. It is a separate supplemental snapshot; no team source data was modified.

Six delivery points are graph nodes selected within the base's connected component; their targets are not verified building entrances. The first raw target is the previous saved-route destination; it can snap elsewhere under this demo's narrower allowed-walkway policy. The exact requested/snapped positions and offsets are exposed in `/api/config`.

To update buildings later, run `python fetch_buildings.py --out data/buildings-new.geojson`. It refuses existing outputs. Compare the new source and geometry before manually replacing the working snapshot in a practice copy. To use a campus GIS export instead, normalize WGS84 longitude/latitude GeoJSON and `properties.layer = "buildings"`, preserve source metadata, and rerun checks. New real delivery points need verified accessible entrances and a reasonable maximum graph snap distance.
