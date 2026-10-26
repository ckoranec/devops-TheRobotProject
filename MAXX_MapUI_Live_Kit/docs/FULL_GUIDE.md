# MAXX MapUI: classic map with current-world inputs

Prepared October 26, 2026. Partners: David and Shek. Demonstration: October 27. Git target: **MapUI**, replacing the earlier human-only submission target for this version.

## 1. What you are building

A software robot follows a route on current downloaded OSM campus geometry. The backend periodically reads real published campus project and event sources. It turns those records into map overlays and carefully labeled planning inputs. The frontend shows robot movement, ETA, data provenance, condition age, route availability and switches.

The customer can pan and zoom and view ETA on desktop or a responsive phone layout. Position display reads every 10 seconds, or every 1 second when selected. Both choices show the same shared software robot. Refresh speed does not turn a model position into GPS.

| Component | Actual source and status | How it affects the map |
|---|---|---|
| Paths/buildings | OSM map API snapshot, retrieved October 26; 145 real building outlines | Geometry and graph; optional online background tiles |
| Construction projects | Public feature layer used by Mason's official Construction page | Published project polygons; optional conservative avoidance of Construction-phase areas |
| Events | Verified Communication Department iCalendar feed for event 18428 | Actual time/location record; low-confidence crowd prediction only during that window |
| Specific walkway closures | Actual operator reports, with reporter/time and explicit clearance | Hard exclusions for affected graph segments |
| Observed crowds | Actual operator reports, intensity/confidence/radius and five-minute expiry | Weighted spatial field and edge travel costs |
| Robot location | Your shared software robot engine | Computed movement along its planned graph route; no physical GPS claim |
| Delivery stops | Six planned graph targets; optional separately verified actual places | Software test destinations; not asserted real customer orders |

The public event integration is intentionally narrow: one verified event feed, not the entire university calendar. It currently describes tomorrow's Communication Career Forum at the Johnson Center, 8:30 AM-12:30 PM Eastern. No actual crowd counter, full class timetable, or complete real-time campus closure service was verified. The source panel says this explicitly.

Shek owns the software-robot/position-feed integration opportunity and is credited for the route-as-robot concept. David owns the map interaction, ETA presentation and mobile acceptance review.

## 2. Start the local working map

Extract the ZIP. Open `MAXX_MapUI_Live_Kit` as a project in PyCharm. Select an existing Python 3.10+ interpreter. No third-party Python packages are needed to RUN the supplied app; the PDF is already generated.

Open Terminal at the bottom. Commands go into Terminal; Python/HTML/CSS/JavaScript source goes into editor files. Enter these commands one at a time and press Enter:

```powershell
python --version
dir
python server.py
```

`dir` should show `server.py`, `world.py`, `public_sources.py`, `data` and `web`. If Python is not recognized, use `py -3`. Stop the old port-8000 server with Ctrl+C in its own terminal before starting this one.

Open [the updated classic page](http://127.0.0.1:8000/world.html). The canonical path is also supported at `http://127.0.0.1:8000/html/web/public/dave-campus-map/gis-layers.html`. If localhost still shows the old saved-route page, use this explicit IPv4 address to reach the kit server. Keep the server terminal open. The original repository HTML is not overwritten: this Python server maps that URL to the supplied `web/world.html`.

If port 8000 remains occupied, use `python server.py --port 8004` and replace the URL's port with 8004. Do not kill an unknown process. A plain `python -m http.server` cannot provide this kit's backend APIs.

Wait for source connectivity. The server starts a background thread that refreshes actual public sources, initially on startup and then every 15 minutes (retrying after about a minute on a failed refresh). The UI's 1/10-second polling reads the robot and current source status; it does not repeatedly download source maps or events every second.

## 3. Backend-to-frontend data path

| File | Purpose |
|---|---|
| `server.py` | Same-origin APIs, mode selection, static files and operator authorization |
| `engine.py` | OSM graph, Dijkstra, time weights and shared software movement |
| `map_features.py` | Named OSM building-derived delivery targets and actual access-tag overlays |
| `world.py` | Combines public inputs and actual reports for the software robot |
| `public_sources.py` | Public HTTP requests, validation, normalization, source cache and refresh thread |
| `live_state.py` | Actual staff reports, verified places, stale data and persistence |
| `crowd_model.py` | Common weight/freshness/distance/edge-exposure model |
| `web/world.html`, `web/world.js` | Main software-robot UI and source-status panel |
| `web/live.html`, `web/live.js` | Optional actual staff-report interface |
| `web/heat-field.js`, `web/heat-layer.js` | Matching browser crowd-field and heat renderer |
| `simulation_server.py`, `web/index.html`, `web/app.js` | Preserved offline/synthetic demonstration |
| `refresh_osm.py`, `refresh_sources.py` | Explicit map refresh and source diagnosis |

The browser GETs `/api/config` and `/api/layers`, then `/api/state`. A state contains the computed robot position and routes, source statuses, published project polygons, event records, heat points and node scores. The browser mutates existing map layers rather than recreating the map, preserving pan/zoom and selected visibility. Visual Update 2 restores the old map-first layout: route status, heading, instruction, large map, counts/key, then new controls below. OpenStreetMap background tiles start enabled. Main checkboxes and route switches stay open at top-right; advanced heat and source overlays use the bottom-left control.

Backend conditions are authoritative for route costs. A visibility checkbox only hides a layer; it does not disable a safety exclusion or crowd cost. GeoJSON uses longitude first; Leaflet helpers use latitude first. Keep conversion at the rendering boundary.

## 4. What makes the inputs real

The source registry includes the official discovery page, underlying endpoint and observed result. Mason's Construction page directly links its ArcGIS experience; that experience identifies the Project_Polygons feature service. We queried its public read-only endpoint successfully. Only public map properties needed for routing/display are retained; contact, budget and unrelated details are excluded.

The project's schema has phase and footprint, but no assertion that every footprint is a currently closed sidewalk. Consequently the default shows project areas without mislabeling them. The optional avoidance setting conservatively removes segments sampled inside **Construction** phase polygons; Planning, Complete and Closeout are not automatically called blocked. This is an engineering policy, not an authoritative closure list.

The event `.ics` endpoint was retrieved successfully. The parser reads UID, summary, location and actual start/end. The feed declares Eastern time; the parser applies that declared zone rather than the laptop's local zone. Unsupported recurrence/timezone cases fail validation instead of silently guessing. Cancelled events are omitted.

The Johnson Center event location is matched to the named OSM building. Its crowd anchor is a building-derived center, not a surveyed entrance or measured crowd location. An 80-meter influence radius, intensity 0.5 and confidence 0.3 are transparent tunable heuristics. Neither attendance nor student count comes from the event feed. Outside the event's time window, its crowd influence is zero.

The generally advertised Today@Mason Trumba JSON/RSS endpoints returned errors during verification. They were not substituted with fictional events. A full calendar/registrar export still needs a verified accessible feed and appropriate permissions. Add future approved sources by normalizing them into the same validated event/crowd schema; no private individual schedules are included.

## 5. Source age, failures and replanning

`data/public-cache` preserves each last successful source response with its URL and fetch time. This is different from the publisher's update/observation time. The construction source may contain estimates like “Estimated 2026”; frequent polling cannot make such an estimate precise.

Sources are fresh for at most one hour and must have a successful latest request. An error remains visible. Last-known project polygons are retained for conservative exclusions, not silently removed to reopen a potential obstruction. Start in current-world mode is disabled if either verified public source is unavailable/stale. Use `START_SIMULATION.cmd` for a deliberately separate offline demonstration.

When meaningful source/report conditions change, the software trip pauses and resets to base for a newly planned review. The UI states that reset. It does not silently animate through a new closure or pretend the software position was observed. After review, click Start. Event time-window transitions also trigger re-evaluation; merely fetching identical normalized source data does not reset the trip.

The return plan is checked against current known conditions. If conditions change while the software robot is moving, the trip resets for review. Predicting unknown future closures, continuous physical obstacle avoidance and certified robot route safety are not claimed.

## 6. Movement, ETA and six round trips

Dijkstra minimizes nonnegative estimated travel seconds. The graph joins only shared source node IDs; visually crossing paths are not automatically connected. The pedestrian demonstration policy excludes steps, road classes, private/no-access footways and polygon areas. The display also includes eight actual OSM access-tag restrictions, with exact `access=delivery` or `access=official` values in popups. A red restricted-entry symbol is shared by map markers and the legend. These limitations are not automatically described as construction closures. `motor_vehicle=no` plus `foot=yes` stays a walkable displayed path, with the actual tags exposed in its tooltip. It is not a complete real-robot permission model: gates, slope, width, barriers, indoor access and campus authorization still require review.

The base is a public OSM footprint/path coordinate at Southside Dining. Six distinct software delivery targets are derived from OSM footprints for Hanover Hall, Brunswick Hall, Essex Hall, Grayson Hall, Carroll Hall and Dominion Hall. The nearest connected path node is selected against actual footprint vertices, with a 40-meter maximum reviewed snap. In this bundled snapshot all seven source anchors coincide with path nodes. Source building IDs and snap offsets are exposed in configuration. These are not surveyed entrances, six real orders, or a ranking of the largest dorms.

The software clock determines distance along route segments; UI polling never adds a movement step. Multiple phones therefore see the same robot, regardless of individual polling cadence. Pause freezes the model clock. Outbound ETA is time to delivery; returning ETA is time to base. No valid complete trip means unavailable, no movement and no invented straight line.

At 1x, ETA is modeled travel time. At 10x, it is explicitly accelerated presentation time. Speed assumptions are demonstration parameters, not a blanket 15 mph or a legal/campus operating limit. No 20-minute service guarantee or delivery dwell is enforced in this version.

Ordinary returns exactly retrace the outward route under the current known snapshot. The separate synthetic mode retains forecast-return blockage and alternative-return scenarios for reproducible testing. Actual newly reported closures affect the current-world route and trigger the review/reset policy.

## 7. Weighted crowds without double-counting

Each point records source, data mode, location, intensity (`weight`), confidence, freshness half-life, radius and active start/end. Source modes distinguish actual operator observations from event-based predictions and synthetic exercise data.

Effective weight is intensity x confidence x `2^(-age_minutes/half_life_minutes)`, only within the active window. Distance contribution falls quadratically to zero at the radius. Overlapping contributions combine as `1-product(1-contribution)`, bounded to 0-1.

Walkways are sampled at no more than 10-meter spacing. Edge exposure is the length-weighted mean field value; edge duration is length/base-speed x `(1+3*exposure)`. No extra node cost is added. Node scores are an optional explanation overlay. Duplicate observation IDs update their existing record rather than adding the same observation twice. Different-source duplicate IDs are rejected.

The heat renderer evaluates the same field at a 12-pixel grid and uses a fixed color scale. It is a sampled relative crowd index, not people per square meter. A schedule indicates a possible crowd; only a real count/sensor could supply measured attendance.

## 8. Actual staff reports and local persistence

Open [the report panel](http://localhost:8000/live.html). Enter the operator key printed in the terminal, your reporter/source name, and choose a report type. Click the actual location. Confirm you actually checked the observation/place, then submit.

- **Location:** describes STAFF-TEST-01, a field participant. It is a manual map report, not hardware GPS. It never moves by timer. After 30 seconds without another actual observation, its ETA becomes unavailable.
- **Place:** verify a base and up to six distinct real destinations; snaps over 30 meters are rejected. These verified places are separate from the software robot's planned demonstration stops.
- **Closure:** clicks choose a nearby graph segment. It remains blocked until explicit clearance, even after its one-hour review deadline. These reports influence the current-world software robot.
- **Crowd:** enter a stable observation ID, name, intensity, confidence and radius. Reuse the ID to update your observation. It expires after five minutes and affects the software robot's costs.

Reports persist atomically in `runtime/live-reports.json`, which is ignored by Git and excluded by the installer. Keys change on restart and are never embedded in the ZIP. Do not put actual field reports, personal locations or access tokens into source control. The local server is for trusted-network collaboration; it is not an internet production service.

## 9. Phones and physical-device sign-off

Run `python server.py --host 0.0.0.0`, press Enter, and keep that terminal open. In another terminal run `ipconfig`. Phones must use `http://LAPTOP-IP:8000/` on the same trusted Wi-Fi. Phone localhost is not the laptop. Private-network firewall permission may be needed; do not disable the firewall. Guest Wi-Fi may isolate clients; a trusted hotspot can be simpler.

No phone GPS permission is needed for the selected software-robot design. Actual phone GPS would require browser permission and a secure context; an ordinary laptop-IP HTTP address does not provide that. No phone locations are collected automatically.

Test Safari on a physical iPhone and Chrome on Android: pan/pinch, layer switches, ETA, follow mode, source status, portrait/landscape and connection loss. Emulated phone-width browser checks are useful but do not replace those device tests.

## 10. Test and troubleshoot

From the kit root in a second terminal:

```powershell
python -m unittest discover -s tests -v
```

Press Enter. Test records are fixtures and never presented as actual public observations. For a source diagnosis:

```powershell
python refresh_sources.py
```

Press Enter. Restart after a manual source refresh if an active run needs a clean review. The server otherwise refreshes periodically without external cron or an automation service.

For updated OSM geometry, stop the server and download into a NEW directory with `python refresh_osm.py --out-dir data/osm-next`. Compare that snapshot before changing the active `osm-current` directory. Geometry changes can invalidate saved place/closure identities; the app refuses mismatched reports rather than silently remapping them. Preserve the previous snapshot and reports for review.

| Symptom | Action |
|---|---|
| Old demonstration page | Stop old server; run this kit's server; Ctrl+F5 |
| API 404 | A static/old server is probably running |
| Start disabled | Check source status or unavailable trip; do not relabel stale inputs as live |
| No event heat today | Correct if outside the real event window; inspect source timestamps |
| No measured crowd display | No people-count sensor is connected; event heat is predicted |
| No building names in background | Enable optional online OSM tiles; local vector building tooltips still work |
| Robot jumps back to base | Source change triggered the explicit pause/reset review policy |
| Phone cannot connect | Check bind address, Wi-Fi, laptop IP and private-network firewall rule |
| Public source fails | Error is visible; retain cache and use separately labeled simulation for offline exercises |

## 11. MapUI installation and Git instructions

This version targets [MapUI](https://github.com/ckoranec/devops-TheRobotProject/tree/MapUI). The earlier human-only instructions are preserved only as historical simulation documentation. Do not push this update to human-only by mistake.

From your existing repository terminal inspect first:

```powershell
Set-Location 'C:\Users\noyes\PycharmProjects\MAXX-Map-Submission'
git status --short
git remote -v
git branch --show-current
```

Press Enter after each line. Preserve uncommitted work before changing branches. When the workspace is clean and origin is the expected repository:

```powershell
git fetch origin
git switch MapUI
git pull --ff-only origin MapUI
```

If MapUI is not a local branch yet, use `git switch --track origin/MapUI`. Stop if Git reports conflicts; never force-reset or force-push teammates' changes.

From the EXTRACTED kit's terminal run the optional installer:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -Repository 'C:\Users\noyes\PycharmProjects\MAXX-Map-Submission'
```

It verifies MapUI and origin, copies into one NEW `MAXX_MapUI_Live_Kit` directory, refuses an existing destination, and excludes actual runtime reports. It does not edit team backend files or the existing HTML. Run tests from the copied kit, launch it, and review its diff.

From repository root:

```powershell
git add -- MAXX_MapUI_Live_Kit
git diff --cached --stat
git diff --cached -- MAXX_MapUI_Live_Kit/server.py MAXX_MapUI_Live_Kit/world.py MAXX_MapUI_Live_Kit/public_sources.py
```

Have David and Shek approve the actual staged changes and tests. Only after that review, the submitting teammate can run:

```powershell
git commit -m "Add current-world campus inputs to MapUI software robot"
git push origin HEAD:MapUI
```

The kit does not perform a commit, push, merge, deployment or partner message automatically. Publishing static HTML alone would not run the Python source-refresh backend.

## 12. Learning and remaining integrations

Follow TEACHING_GUIDE.md to type short exercises into the PyCharm editor and run exact commands in Terminal. CODE_REFERENCE.md contains complete application code. DATA_DICTIONARY.md explains each field. DEMO_CHECKLIST.md records partner evidence.

Remaining real integrations are specifically: physical robot telemetry once hardware exists; full approved class/event feeds; measured crowds; authoritative complete closure data; verified entrances and operational permissions. These are not required to show the software robot consuming the two connected real sources now. They must not be presented as already measured or connected.

## Visual update and existing installation

Use the one-file MAXX_MapUI_Visual_Fix.ps1 for an existing kit. It creates a complete local backup under LocalAppData/MAXXMapBackups, updates the kit's code/docs, and preserves `data/` and `runtime/`. It performs no Git writes. Follow PATCH_INSTRUCTIONS.md for the exact command, restart and version endpoint check. Outbound stays purple; return is orange/dashed so both are visible even when they follow identical coordinates.
