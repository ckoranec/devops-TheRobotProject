# MAX Byte map completion ledger

Baseline: DevOps/live 4b0958d09f8cb9a5b45d0c8a7213651511fd8904.
The approved three-mode layout, simulation, game, audio and V26 presentation are
preserved. Their deployed baseline passed 37 tests and 24 HTTP asset checks.

## Countdown rule
There are **12 remaining work packages**, each with acceptance criteria below.
A package is checked off only after its required automated checks, local browser
acceptance and approved deployment verification. Implementation or passing one
unit test does not by itself complete a package. External-data dependencies remain
open until verified. Report this ledger after each install/test/push/deploy stage.
Never state ALL MAP ITEMS ARE COMPLETE until all twelve are accepted and zero remain.

| ID | Remaining package | Acceptance requirement | Current status |
|---|---|---|---|
| 1 | Customer routing API | Team Dijkstra; valid outbound/return GeoJSON, units/ETA, local and deployed API checks | Implemented in phase 1; local acceptance/deployment pending |
| 2 | Account-owned missions | Separate stored missions, owner-only reads, retries without duplicates, no shared JSON writes | Implemented in phase 1; local acceptance/deployment pending |
| 3 | Delivery-location UI and address resolution | Pickup, address/select/map-pin confirmation, unsupported-address handling; agreed general address-search coverage | Known-address/map-pin UI implemented; geocoding and visual acceptance pending |
| 4 | Order and three-view integration | Authenticated order-to-mission binding; same mission in all views, robots, labels, ETA and game streets | Pending; existing tabs still load static mission |
| 5 | Failure handling and API safeguards | Invalid coordinates, excessive snap, disconnected/unavailable map, session/ownership/CSRF/rate limits verified locally and live | Automated checks implemented; local acceptance/deployment pending |
| 6 | Missing GIS layers | Verified buildings, entrances, restricted polygons and closures with provenance/counts and toggles | Pending source data |
| 7 | Robot access and GIS accuracy | Campus permission rules, barriers/polygons, entrance snapping, reachability matrix and independent point validation | Pending; routes remain simulations |
| 8 | Obstacles and alternate routes | Valid fallback routes, blocked-path rerouting, ETA updates and visible failure states | Pending |
| 9 | GIS updates/versioning/alerts | Stage/validate/diff, approval activation, rollback and staff alerts; agreed source/update schedule | Pending |
| 10 | Server game verification and real coupons | Authoritative ETA/results, abuse checks, one-use 15% coupon, account wallet, redemption and expiration | Pending; current prize remains preview only |
| 11 | Mobile/accessibility/performance acceptance | Android/iOS, keyboard/touch, reduced motion, contrast, slow/offline cases and play-balance evidence | Pending |
| 12 | Real GPS tracking | Team telemetry interface, authenticated order scope, 10s refresh/interpolation, stale/reconnect handling | Blocked on team interface; keep open |

**Remaining: 12. Accepted in this new ledger: 0.**
The first package implements foundations for 1, 2 and 5 plus part of 3. It does not
claim those are deployed or finish the whole master plan. Split a work package if
its scope changes; record the change so the countdown is not misleading.

## Same workspace and same port
Local project: C:\Users\noyes\PycharmProjects\devops-TheRobotProject
Branch: DevOps. Local website/API: http://127.0.0.1:8000.
The combined runner replaces python -m http.server on that same port. Existing
MapAPI.html/tracking.html/layout/game/audio/GIS are not rewritten by this phase.
