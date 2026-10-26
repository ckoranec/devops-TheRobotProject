# Data dictionary

## Coordinates and identifiers

| Field | Meaning / units |
|---|---|
| `coordinates` | `[longitude, latitude]` in decimal degrees, WGS84; Leaflet helpers use reversed order |
| `node` / `node_id` | OSM node identity used to connect paths; crossing lines are not automatically connected |
| `way_id` / `osm_id` | Source OSM feature identifier |
| edge key | Sorted endpoint node IDs joined by `|`; this demo closes a graph segment |
| `requested_coordinates` | Original demonstration target, not a verified entrance |
| `snap_meters` | Distance from that target to the selected connected graph node |
| layer | `walkways`, `buildings`, `delivery` or `restricted` |

## Weighted crowd point schema (supplied model)

| Field | Type / range | Meaning |
|---|---|---|
| `id`, `name`, `source` | Nonempty strings | Record identity, display name, provenance |
| `kind` | `class`, `event`, `manual` | Source category |
| `data_mode` | `simulated`, `predicted`, `observed` | Truthful evidence classification |
| `lat`, `lon` | Finite geographic degrees | Point center |
| `radius_m` | 1–500 meters | Influence reaches zero at this radius |
| `weight` | 0–1 | Intensity estimate; this is the field name used for intensity |
| `confidence` | 0–1 | Trust factor applied to intensity |
| `half_life_minutes` | 1–10080 minutes | Freshness halves after this age |
| `starts_at`, `ends_at` | ISO 8601 with zone | Active interval, inclusive start and exclusive end |
| `updated_at` | ISO 8601 with zone | Source update time, used for freshness |
| `effective_weight` | Derived 0–1 | Intensity × confidence × freshness at planning time |

Kernel: `max(0, 1 - distance/radius)^2`. Combine contributions as `1 - product(1 - contribution)` so overlap remains bounded. This is a relative crowd index, not people per square meter or a probability. Sample each walkway at no more than 10-meter spacing; use length-weighted exposure for its time cost. There is no additional routing-node penalty.

## `/api/state`

| Field | Meaning |
|---|---|
| `robot_id`, `mode` | `SIM-01`, `simulated`; no real hardware dispatch |
| `timestamp` | UTC time state was generated, not a GPS observation time |
| `planned_at`, `revision` | Scenario planning timestamp and monotonically increasing configuration version |
| `running` | Whether the model clock is advancing |
| `phase` | `outbound`, `returning`, `complete`, `unavailable` |
| `rate` | 1 or 10; model seconds per wall second |
| `eta_seconds` | Remaining demo wall seconds to delivery or base; null when unavailable |
| `eta_travel_seconds` | Remaining unscaled model travel seconds |
| `eta_target` | `delivery` outbound, `base` on return/completion |
| `traveled_meters`, `total_meters` | Actual modeled trip distance, not cost units |
| `outbound_seconds`, `total_seconds` | Full unscaled model travel durations |
| `outbound`, `return_route` | Ordered arrays of longitude/latitude positions |
| `return_kind` | `exact retrace`, `rerouted return` or `unavailable return` |
| `blocked` | Active outbound closure segments, also considered for return |
| `forecast_return_blocked` | Additional segments closed only in the return planning snapshot |
| `crowds`, `weighted_points` | Raw scenario crowd records and planning-time prepared records |
| `weighted_nodes` | Node identity, coordinates and score for optional display; never a second routing cost |

## Units and limits

Base model speed is 1.2 m/s. Maximum crowd cost multiplier is four. These are demonstration assumptions, not legal or campus operating limits. The kit does not enforce a 20-minute service guarantee or blanket 15 mph. There is no delivery dwell. Return closures are explicit scenario snapshots; this is not continuous obstacle detection or a forecast feed.

## Current-world mode additions

| Field | Meaning |
|---|---|
| `mode` | `software_robot_with_public_world_inputs`; motion remains computed |
| `sources` | Per-source URL, successful fetch time, age, freshness and error |
| `projects` | Actual published project geometry and phase; not a confirmed closure list |
| `events` | Actual event UID/title/location/start/end/source; not measured attendance |
| `optional_project_avoidance` | Whether Construction-phase footprints are conservatively excluded |
| `project_excluded_edges` | Number of graph segments excluded by that optional planning policy |
| `crowd_note` | Explains predicted event influence and missing people-count/full-schedule feeds |
| `replan_notice` | Conditions changed; software trip paused/reset for review |

Current-world mode fetches sources at startup and every 900 seconds; inputs are stale after 3600 seconds or a failed latest fetch. UI position polling is a separate 1/10-second setting. Geometry refresh is explicit, not a claim of real-time map editing. Crowd timing and routing semantics are in the current guide; the older dictionary fields also describe preserved synthetic/report modes.

## Classic visual map additions

`base_place` and each stop contain the named OSM building ID, the original footprint vertex (`requested_coordinates`), the connected path coordinate and snap meters. `access_tags` preserves actual OSM tag keys/values. The restricted-entry marker is a display symbol for access limitations; confirmed dynamic closures remain separate. Return geometry is unchanged by its orange dashed styling.
