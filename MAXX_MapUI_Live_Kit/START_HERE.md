# MAXX MapUI - software robot with current real-world inputs

Updated October 26, 2026. **Visual Update 2 - classic map layout.** Target branch: **MapUI**.

**What is live:** backend refreshes actual public Mason project polygons and a verified university event iCalendar source. It accepts actual staff-reported closures and crowd observations. The software robot moves on real OSM paths and uses these inputs for route planning. **The robot itself is software, not physical GPS.** Event-based crowd intensity is a prediction, not measured attendance.

## Start on Windows / PyCharm

1. Extract the ZIP. Open the inner `MAXX_MapUI_Live_Kit` folder in PyCharm.
2. Stop the old port-8000 server with **Ctrl+C** in its terminal.
3. Double-click `START_WINDOWS.cmd`, or run the following from the kit's PyCharm Terminal, then press **Enter**:

```powershell
python server.py
```

Keep that terminal open. Python 3.10+ is required; no pip/npm packages, accounts or API keys are needed for the verified public sources. If `python` is not found, try `py -3 server.py`.

Open [your updated classic-layout map](http://127.0.0.1:8000/world.html), then press **Ctrl+F5**. If `localhost` still shows the old saved-route page, use the exact `127.0.0.1` link above. The included server provides this page; a plain static `http.server` does not run the backend.

## Demonstrate current public inputs

1. Scroll to **Verified public inputs**. Wait for **projects CONNECTED** and **events CONNECTED**. Public data refreshes every 15 minutes on a background thread; position display can refresh every 10 seconds or 1 second.
2. Choose a numbered building delivery, current published inputs, 1x or explicitly labeled 10x playback. Apply, then Start. Zoom/pan, Pause/resume, and inspect ETA. Motion is calculated by your software robot, not reported GPS.
3. Open the map layer control. Toggle real paths, buildings, published project areas, deliveries, routes, heat and node scores.
4. Select **Also avoid Construction-phase project areas**, then Apply. Orange project areas influence conservative routing. These are not asserted confirmed sidewalk closures. Unavailable trips stay at base.
5. The connected event source currently covers the **2026 Communication Career Forum**, Johnson Center, October 27, 8:30 AM-12:30 PM Eastern. Its influence activates only during that published window. No heat outside the window is correct. Do not change your system clock or invent crowds for the demo.
6. Open [actual field reports](http://localhost:8000/live.html). Use the operator key printed in the server terminal to report a genuinely observed path closure or crowd condition. Never submit practice reports as actual observations. Conditions changes pause and reset the software trip for review; click Start after reviewing the new route.

Synthetic blockage/crowd scenarios remain available separately: double-click `START_SIMULATION.cmd`, then open [simulation on port 8004](http://localhost:8004/). Its original code and lessons are preserved. Simulation is not substituted if a public source fails.

## Phones

Stop the server. Double-click `START_PHONE_DEMO.cmd`, or run:

```powershell
python server.py --host 0.0.0.0
```

Press Enter. In another terminal run `ipconfig`. Connect phones to the same trusted Wi-Fi; open `http://LAPTOP-IP:8000/` using your laptop's actual IPv4 address. Phone `localhost` refers to the phone. If Windows prompts, allow Python on the private network for this local test; do not disable the firewall or expose the server to the internet.

The operator key authorizes actual report writes; ordinary viewers need no key. It changes on server restart. Report data stays in Git-ignored `runtime/`. Physical iPhone/Safari and Android/Chrome testing is still your acceptance step.

## Check and learn

In a second terminal at the kit root, paste and press Enter:

```powershell
python -m unittest discover -s tests -v
```

Read `docs/FULL_GUIDE.pdf` or `docs/FULL_GUIDE.md`. Type the short lessons from `docs/TEACHING_GUIDE.md` into your own practice files before changing the complete app. `docs/CODE_REFERENCE.md` contains all application source. `docs/DATA_DICTIONARY.md` and `docs/DEMO_CHECKLIST.md` explain sources, units and sign-off. `docs/SOURCE_REGISTER.md` records what was verified and what is not connected.

No public feed supplies this unfinished physical robot's GPS, measured student counts, or a complete current sidewalk-closure inventory. Those are distinct inputs. The connected feeds and their exact coverage remain visible; missing data is not relabeled as live.

No repository push, deployment, physical robot control or partner message is performed by the kit.

## Visual Update 2 - what you should see

The heading/instructions/map order matches the team's old page. The OSM background is ON by default. Main layer switches stay open at the top-right; the return route is orange/dashed over the purple outbound route. New controls are below the map.

Expected counts from this source snapshot: **145 buildings, 885 walkways, six delivery points and eight access-tag restrictions**. The eight restrictions are actual `access=delivery` or `access=official` OSM features, not eight asserted current closures. Their red restricted-entry symbol is identical on the map and in the key; click for exact tags.

Base: **Southside Dining**. Targets: **Hanover Hall, Brunswick Hall, Essex Hall, Grayson Hall, Carroll Hall, Dominion Hall**. Coordinates are actual OSM footprint vertices linked to connected path nodes. These are planned software delivery locations, not surveyed entrances or real customer orders.

Use the bottom-left map control for weighted heat, routing-node scores, source details and project areas. Heat uses the same weights/cost model as before. It appears only for active input windows. No current heat is not a measured claim that the campus is empty.

To verify the right server after patching, open `http://127.0.0.1:8000/api/version`; it must show **MapUI Visual Update 2**.

## Already installed? Apply the one-file fix

Download MAXX_MapUI_Visual_Fix.ps1 beside this kit, stop the kit server with Ctrl+C, and run it from PyCharm Terminal with the repository path described in PATCH_INSTRUCTIONS.md. It backs up the previous kit outside Git and preserves local map/source data and runtime reports. Restart the server afterward. The normal Install.ps1 is for a new destination and deliberately refuses an existing kit.
