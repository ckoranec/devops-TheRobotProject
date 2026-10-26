# David + Shek: October 27 presentation and sign-off

## Before the demo

- [ ] ZIP fully extracted, Python interpreter works.
- [ ] Original port-8000 server stopped; this kit's server running.
- [ ] `/api/config` returns six stops and the pinned source commit.
- [ ] Automated tests pass locally.
- [ ] Choose offline GIS background for a dependable baseline; enable online tiles only if available.
- [ ] Nominate one control operator: changes affect all viewers.
- [ ] Explain that movement, deliveries, closures and crowds are simulations; buildings are supplemental OSM outlines.

## Five-minute presentation

| Time | Driver | What to show / say |
|---|---|---|
| 0:00–0:40 | David | Show the campus overlay and source labels. Toggle walkways, blue OSM buildings, maroon sample deliveries and restrictions. |
| 0:40–1:15 | David | Drag/pan and zoom; show that a position update does not reset the view. |
| 1:15–2:00 | Shek | Clear delivery 2, 10× clock, 1-second updates; Start. Explain route-as-simulated-robot ownership. |
| 2:00–2:40 | David | Show ETA, distance and Pause/resume. Explain demo-clock ETA; show a phone watching the same trip if tested. |
| 2:40–3:20 | Shek | Apply route-segment blockage; show red closure and alternative route. Explain scenario resets to base. |
| 3:20–3:50 | Both | Seal destination; show No valid route, disabled Start and unavailable ETA. |
| 3:50–4:30 | Both | Apply crowd scenario; explain intensity × confidence × freshness and distance falloff. |
| 4:30–5:00 | Shek | Show required 10-second cadence, exact reverse return (or explicitly rerouted return), and identify final telemetry source as future integration. |

## David's physical-device evidence

Phone-sized browser automation is not physical device sign-off. Fill these rows with what you observe.

| Device / OS / browser | Pan & zoom | Layers | Moving position & ETA | Portrait/landscape | Result / tester / time |
|---|---|---|---|---|---|
| iPhone / ___ / Safari ___ | pending | pending | pending | pending | pending |
| Android model ___ / OS ___ / Chrome ___ | pending | pending | pending | pending | pending |
| Windows / browser ___ | pending | pending | pending | n/a | pending |

## Shek's telemetry and route evidence

- [ ] Record two received state timestamps approximately 10 seconds apart while moving.
- [ ] Switch to 1 second and observe increased update frequency.
- [ ] Pause stops progression; resume continues rather than restarting.
- [ ] Two viewers see the same shared trip.
- [ ] All six stops load; outbound and exact reverse return are available in clear conditions.
- [ ] Closure avoided in outbound AND return.
- [ ] Sealed destination never starts movement.
- [ ] End of trip is base, with zero ETA and complete status.
- [ ] Network/API loss produces a connection/stale warning.

## Defect log

| ID | Device / scenario | Expected | Actual | Owner | Fix / retest evidence |
|---|---|---|---|---|---|
| D-001 | | | | | |

## Suggested card result after observed local tests

“Local simulation demonstrates switchable campus GIS layers, zoom/pan, ETA, shared robot position at 10-second or 1-second cadence, and closure-aware routes; physical device results attached. Hardware telemetry, surveyed missing features and live campus conditions remain integration work.”

Only mark the iOS/Android acceptance criterion complete after device evidence is recorded. Share the ZIP manually with partners; this kit sends no messages or invitations.
