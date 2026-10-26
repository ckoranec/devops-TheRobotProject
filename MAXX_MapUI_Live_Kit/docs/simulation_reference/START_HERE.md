# MAXX Bytes — David & Shek local demo kit

Prepared October 26, 2026 for the October 27 demonstration.

**This ZIP is a complete, standalone local demonstration. Extract it before running anything.** Python 3.10 or newer is the only prerequisite. No pip, npm, Node, database, API key, paid hosting or installation into the team's backend is required.

## 1. Start on your Windows laptop

1. Right-click the ZIP in Downloads → **Extract All**.
2. Open the extracted `MAXX_David_Shek_Demo` folder. You should see `server.py`, `engine.py`, `START_WINDOWS.cmd`, `web`, `data`, `tests` and `docs` together. Do not run from inside the ZIP viewer.
3. Stop your old port-8000 server with **Ctrl+C** in its terminal. Only one server can use port 8000.
4. Double-click **START_WINDOWS.cmd**. Keep its black terminal window open.
5. Open [the demo map](http://localhost:8000/html/web/public/dave-campus-map/gis-layers.html). Press **Ctrl+F5** to reload.

This familiar URL is an alias implemented by the included server. Your original `gis-layers.html` is not edited. The original static `python -m http.server` command cannot provide this demo's API.

**In PyCharm instead:** open the extracted folder as a project. Open Terminal. Confirm `server.py` appears when you enter `dir`, then paste and press **Enter**:

```powershell
python server.py
```

If `python` is not recognized, try `py -3 server.py`. If port 8000 is occupied and you cannot stop the old process, use `python server.py --port 8004`, then open [port 8004](http://localhost:8004/html/web/public/dave-campus-map/gis-layers.html).

## 2. Rehearse the demonstration

- Choose **Demo delivery 2**, **Clear walkways**, and **10× accelerated demonstration**. Click **Apply & reset to base**.
- Select **Every 1 second (near-live)**, then click **Start / resume**. The black robot moves along the route; distance and ETA change.
- Drag to pan; click +/−, use your mouse wheel, or pinch on a phone to zoom. **Follow robot** is optional and initially off.
- Click **Pause**. Position and ETA freeze. Click **Start / resume** to continue.
- Open the layers button in the map's top-right corner. Toggle walkways, blue OSM building outlines, maroon delivery points, restrictions, routes and heat.
- Select **Block a route segment**, click **Apply & reset to base**. A red closure appears and the purple route changes to avoid it. Scenario changes intentionally reset the trip.
- Select **Forecast closure on return leg**, click **Apply & reset to base**. The outbound path remains clear; an orange dashed closure changes the return path and the status says rerouted return.
- Select **Block all destination access**, click **Apply & reset to base**. Confirm **No valid route**, ETA **Unavailable**, and disabled Start.
- Select **Predicted crowd / heat map**, click **Apply & reset to base**. Colored heat shows simulated weighted crowd influence. In the layer control enable **Weighted crowd sources** and **Routing-node crowd scores**; click markers for their values.
- Return to clear conditions and show **Every 10 seconds** to demonstrate the card's required cadence. The 1-second choice is an enhancement, not a claim of live GPS.

At 10×, ETA means accelerated demonstration time; at 1× it means modeled travel time. The trip goes to the stop and immediately returns without a delivery dwell. Ordinary scenarios use the exact reversed path; the forecast return-closure scenario explicitly shows an alternative return.

## 3. Test a real phone

Stop the server with **Ctrl+C**. Double-click **START_PHONE_DEMO.cmd**, or run:

```powershell
python server.py --host 0.0.0.0
```

In a second terminal run `ipconfig`. Find your active Wi-Fi adapter's IPv4 address. Put the laptop and phones on the **same trusted Wi-Fi**. On each phone open `http://LAPTOP-IP:8000/` using that actual address. For example, if it is `192.168.1.25`, open `http://192.168.1.25:8000/`.

`localhost` on a phone refers to the phone, not your laptop. If Windows prompts, allow Python on your private network for this test. Do not disable the firewall. Campus guest networks may isolate devices; use a trusted hotspot if needed. This is a local demo server with shared controls; do not forward its port to the internet.

Test Safari on an iPhone and Chrome on Android. Both see the same simulated robot because state belongs to the server. UI choices such as polling cadence, layers and follow mode belong to each browser.

## 4. Read the teaching plan and run checks

Open **docs/FULL_GUIDE.pdf** for the printable plan, lessons and checklists. Read [docs/FULL_GUIDE.md](docs/FULL_GUIDE.md) for implementation lessons, roles, API contracts, source integration, Git steps and troubleshooting. [docs/CODE_REFERENCE.md](docs/CODE_REFERENCE.md) contains the commented code in one reading document. Use [docs/DEMO_CHECKLIST.md](docs/DEMO_CHECKLIST.md) and [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md) to separate completed automated checks from your device evidence.

From the extracted kit's terminal, paste and press **Enter**:

```powershell
python -m unittest discover -s tests -v
```

## What is real and what is simulated?

The team map snapshot contains 1,213 walkway features and 19 access-restriction features, **zero building outlines and zero delivery points**. It is pinned to the `human-only` commit documented in `data/SOURCE_MANIFEST.json`. This kit includes that data so tomorrow's demo does not depend on a new map download.

The kit bundles **145 actual OpenStreetMap building outlines** for the central-campus bounding box. They are simple closed building ways, not a complete or independently surveyed campus building dataset. Six maroon delivery stops are **clearly labeled demonstrations**, not approved entrances. All movement, closure and crowd data are simulated. The first stop targets the earlier destination area but is snapped to this demo's connected pedestrian graph; its exact snap offset is exposed in `/api/config`.

Offline GIS background is selected initially. Walkways, samples, routes, robot, layers and heat work offline. Choose **Online OpenStreetMap tiles** in the map control for the familiar street backdrop when internet is available.

Nothing has been pushed, merged, deployed, sent to partners, or installed on your laptop by creating this ZIP.

For editor-versus-terminal lessons, begin with **docs/TEACHING_GUIDE.md**. Type the short lesson files into your own practice copies before editing the full app.
