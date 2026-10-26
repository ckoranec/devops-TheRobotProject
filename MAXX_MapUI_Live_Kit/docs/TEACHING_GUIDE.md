# Learn it by typing: editor versus terminal

The current-world app is supplied in full. Earlier lessons 1-4 teach the core model; they do not send fictitious records to live APIs. First run it, then use these short lessons to understand it. Practice in a **copy** of the extracted kit so an unfinished edit cannot interrupt the demonstration.

## Where each kind of code goes

| What you see | Where to put it | How to run it |
|---|---|---|
| Python: `print(...)`, `def ...`, `import ...` | A `.py` file in the PyCharm editor | Right-click file → Run, or `python filename.py` in Terminal |
| PowerShell: `python ...`, `git ...`, `Set-Location ...` | PyCharm's Terminal tab, with PowerShell selected | Paste the command and press Enter |
| HTML: `<div>`, `<button>` | `web/index.html` in editor | Start Python server, open browser and reload |
| CSS: `body { ... }` | `web/style.css` in editor | Reload browser; Ctrl+F5 if cached |
| JavaScript: `fetch(...)`, `L.map(...)` | `web/app.js` in editor | Browser runs it after loading the page |
| JSON / GeoJSON | The corresponding `.json`/`.geojson` file in editor | Python or JavaScript reads it; do not run it as a program |

Do not paste the Markdown backticks or terminal prompts into the editor. Python indentation belongs to the program: preserve it. Every code block in CODE_REFERENCE.md is labeled with its destination file and can be copied without line-number cleanup.

## Lesson 1 — Make a Python file

In PyCharm open the kit folder, right-click `lessons` → New → Python File. To type from scratch, name your file `my_01_hello.py` so you keep the supplied answer file intact. Type the contents of `lessons/01_hello.py`, which are also in CODE_REFERENCE.md. Save with Ctrl+S.

In Terminal, with the kit directory as the current folder, enter:

```powershell
python lessons/my_01_hello.py
```

Press Enter. Expected output: the project name followed by a dictionary with robot ID and coordinates. Explain it aloud: “This is a record representing a position; it is not moving a real robot.”

If using the supplied file instead, run `python lessons/01_hello.py`. You do not need to install anything.

## Lesson 2 — Calculate ETA with units

Type `lessons/02_eta.py` into `lessons/my_02_eta.py`. Run `python lessons/my_02_eta.py` and press Enter. Expected outputs are 100 model seconds and 10 presentation seconds. Change the distance from 120 to 240; both should double. Explain why a 10× clock does not mean the model robot is approved to drive ten times faster.

## Lesson 3 — Explain weights and freshness

Type `lessons/03_weighted_point.py` into your own copy. Run it from Terminal. Expected weights: 0.4 initially and 0.2 after an hour. Change only confidence from 0.5 to 1.0; the results become 0.8 and 0.4. Restore your practice copy if needed.

`validate_point` checks required fields and numeric ranges. `timestamp` rejects missing time zones. `effective_weight` applies the time window and freshness. This is the supplied crowd model, not a separate teaching approximation. Dates in this exercise are fixed so its answer remains reproducible.

Explain it: “The weight is an intensity estimate adjusted by trust and age. It is not a measured student count. Distance influence is calculated separately.”

## Lesson 4 — Check a real graph route

Study/type `lessons/04_route_check.py`. Run `python lessons/04_route_check.py`. It reads local data, constructs a closure scenario, and checks each adjacent route edge. Expected: `Outbound avoids closure: True`, then the return kind and a distance. The test does not claim the route is physically approved.

Try `robot.configure('2', 'sealed', 1)`. In the full app that scenario gives no trip and disables Start. An `all(...)` check over an empty list is true in Python; therefore a **complete** availability check also requires a nonempty path. The app and automated tests check both. This is a useful reason to test failure states, not just happy paths.

## Lesson 5 — Read and explain the full engine

Open `engine.py`. Follow these units in order:

1. `meters` and `edge_key`: coordinate units and stable segment identity.
2. `Campus.__init__`: read team ways, preserve shared node identity, reject unsuitable categories, select connected demonstration stops.
3. `Campus.duration`: sample crowd exposure along each segment and convert meters to seconds once.
4. `Campus.route`: Dijkstra relaxes unblocked edges, then reconstructs the path.
5. `Simulation.configure`: create the selected scenario and plan both legs before movement.
6. `tick`, `action`, `snapshot`: elapsed-time progression, pause/reset and position/ETA response.

You may retype one function at a time into a practice copy. Restore it from CODE_REFERENCE.md if indentation or spelling becomes confusing. Run the test suite after every change to routing or time progression.

## Lesson 6 — Understand the server

Open `server.py`. `make_handler` shares the simulation and a lock among requests. GET reads state; POST changes state. The static root is only `web/`, so Python source and operator data are not exposed as web downloads. The familiar map URL is an alias to `web/index.html`; no original map file is replaced.

Terminal commands to run your practice copy are the same as the current-world app:

```powershell
python server.py
```

Press Enter. Leave it running. Open the map in the browser. Use a second terminal for tests or API inspection. Use Ctrl+C in the server terminal to stop it before editing/restarting Python code. Browser reload applies frontend edits; Python edits need a server restart.

## Lesson 7 — David's browser code

Read `web/index.html`, then `web/style.css`, then `web/app.js`. The HTML names elements, CSS arranges them, and JavaScript updates their content. `$()` selects an element by ID. `request` handles HTTP and a timeout. `show` updates existing layers instead of rebuilding the map.

Safe exercise: change the introductory paragraph in HTML, save, and reload. Next change a color in CSS. Restore your practice copy afterward. Do not paste those changes into Terminal.

`heat-field.js` calculates the same crowd field as Python. `heat-layer.js` samples it on a canvas. Source and routing-node marker overlays are explanations; turning them off does not change route costs.

## Lesson 8 — Shek's telemetry handoff

Read `/api/state` while the software robot moves. Find coordinates, timestamp, mode, phase and ETA. The frontend's polling cadence controls how often it reads positions. The backend clock controls movement. A future real-source adapter should replace the simulator without changing those meanings. Keep `mode: observed` separate from simulated or predicted positions.

## Before presenting

Use DEMO_CHECKLIST.md. Both partners should be able to explain one successful route, one blocked route, one unavailable trip and how confidence/freshness affect heat. Run tests in the complete kit, then rehearse using its untouched code.

## Lesson 9 - Follow a real source end to end

Type `lessons/05_public_sources.py` into a practice file. Run it with `python lessons/05_public_sources.py` and press Enter. It reads the existing real-source cache and prints source URL, freshness and published records. It does not manufacture data or submit observations.

Then read `public_sources.py`: `refresh` performs actual HTTP GET requests; `parse_projects` and `parse_events` reject unexpected schemas; `snapshot` preserves source age and errors. `world.py` turns an event into a **prediction** rather than labeling it a measured crowd.

Explain it: “The source gives us a real event time and location. We choose a transparent low-confidence crowd heuristic. The robot follows our software route; it is not reporting physical GPS.”

## Lesson 10 - Explain failure honestly

Stop the server and start the separate synthetic mode for practice blockages. Do not use the live staff report form to add invented observations. Source-failure tests are in `tests/test_public_sources.py`; run the suite rather than editing the system clock or falsifying the feed. The same map can be tested with software fixtures without calling them real events.

## Lesson 11 - MapUI submission

Use the current FULL_GUIDE.md Git commands for MapUI. The historical human-only instructions under simulation_reference are preserved as reference and are not the destination for this update.
