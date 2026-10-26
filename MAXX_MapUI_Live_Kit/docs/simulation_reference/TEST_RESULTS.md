# Verification - October 26, 2026

## Completed in this build environment

- **25 Python tests passed** using the bundled datasets, with no external feed required. These include all six outbound/exact-return plans, closures avoided on both legs, sealed destinations that cannot start, all six forecast-return reroutes, motion interpolation, pause/resume, ETA and accelerated time, bounded node scores without extra node charges, actual building polygon structure, HTTP/API contracts, and the nine supplied crowd-model tests.
- Four numeric field cases matched between Python `density_at` and JavaScript `DaveHeatField.densityAt` within `1e-10`.
- The two bundled team files matched their pinned Git blob identities. The source manifest records their SHA-256 hashes and commit.
- Headless Chromium browser checks passed: page load, motion, pause, closure and forecast-return labels, unavailable route/ETA, three weighted source markers and a nonempty node overlay, layer/zoom persistence, shared server state, and visible connection-loss warning. No JavaScript page errors were observed.
- Measured position polling interval in a local browser: **10,051 ms** with the 10-second option. The 1-second option also updated movement during the test. This is polling, not a hard real-time guarantee.
- Desktop viewport 1365 x 1000 and phone-width viewport 390 x 844 rendered without horizontal page overflow.
- The printable guide was rendered and visually reviewed. It contains the implementation plan, typing lessons, data dictionary and partner checklist; complete code is supplied separately in CODE_REFERENCE.md and runnable source files.

## Still requires your local sign-off

- Run tests and launchers on your Windows/PyCharm setup.
- Connect an actual iPhone/Safari and Android/Chrome to the laptop over the same network. Phone-width Chromium emulation is not proof of physical iOS/Android compatibility.
- Confirm team acceptance of the map/source, demo stop locations, and the simulated-robot concept/ownership.
- Verify physical routes/entrances and any operating permissions before a real robot uses them.

The building file contains **145 real OSM simple building polygons** in the documented central-campus bounding box. It is supplemental snapshot data, not complete surveyed campus coverage. All six delivery stops, robot movement, crowds and closures are simulated. No hardware connection, live campus feed, deployment, repository push or partner message is claimed.
