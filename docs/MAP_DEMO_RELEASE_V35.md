# MAXX Bytes map checklist — V35 demonstration checkout

Updated October 18, 2026. Same PyCharm workspace, DevOps only, localhost port 8000. Latest verified GitHub baseline: dfd216f5dda50cb04db8b073cebd0ba0e2d2f9b1 (V34). User screenshots show successful local V34 demo checkout and the public API health response status ok.

## Current release

- [x] Account authentication is required before a customer purchase can be recorded.
- [x] Server-priced simulated-payment review, explicit confirmation and cancel/back behavior implemented.
- [x] Successful simulation records $0 actually charged and atomically creates the purchase, coupon redemption if used and dispatch clock.
- [x] Automatic redirect to the purchase's Classic Map; other views remain the customer's choice.
- [x] Automatic 15 mph outbound and return simulation, retained progress after refresh and no purchase-clock rewind through Reset/Pause.
- [x] One game per purchase, original payment-start delivery deadline and account coupon wallet/redemption implemented.
- [x] Public demonstration mode enabled in the private WSGI entrypoint. No payment provider or hardware dispatch is connected.
- [x] Preparation validation: 67 API tests, real API/DOM checkout flow and robot-clock interaction tests passed.
- [ ] Run the full local project suite and inspect V35 on the user's screen.
- [ ] Approve the exact diff, commit/push DevOps and deploy that commit; verify the complete public demonstration flow.

**Release execution countdown: 2 acceptance stages — local review, then verified live release.**

## Retained completed presentation baseline

- [x] Classic, Customize and Snack Chase share the accepted map/connected side-panel layout.
- [x] Horizon Hall pickup/return, Overcup demonstration destination, Dijkstra route and matching route styling.
- [x] Matching delivery robots; smaller orange game robot at the destination; game-only natural street lanes.
- [x] Food motion and collection, keyboard/touch controls, default music and mute control.
- [x] 24 accessories, RGB color picker, 12 map effects and green reward invitations.
- [x] MAXX Bytes header and ordered navigation on all 14 public HTML pages; linked order steps and compact checkout.

## Stable master map package IDs

A package is accepted only after its remaining requirements have evidence. These rows distinguish implemented software from acceptance/source work; they do not erase completed work.

| ID | Work package | Implemented/evidenced | Remaining requirement |
|---|---|---|---|
| 1 | Customer-routing API | Dijkstra preview, units, snapping/connection checks and outbound/return GeoJSON tested | Verify authenticated route/ETA behavior live |
| 2 | Account-owned missions | Separate owner-scoped records, idempotent saves and isolation tests | Live save/refresh and second-account acceptance |
| 3 | Delivery-location interface | Known Overcup address, map/coordinate selection, confirmation and checkout links | General address-search coverage and responsive acceptance |
| 4 | Order-specific mission across maps | V35 demo purchase, automatic Classic start, shared robots/addresses/ETA and destination-derived streets | Run the complete V35 flow locally and live |
| 5 | Failure handling and safeguards | CSRF, ownership, snap/disconnected errors, throttling, payment retries and atomicity tests | Production session/HTTPS, error and load acceptance |
| 6 | GIS layers | Existing 625 roads, 1213 paths, 19 restrictions and shared layer controls | Validate additional buildings/entrances/closures/restricted geometry and provenance; partial uploaded data is not full coverage |
| 7 | Robot access and accuracy | Unsafe source-tag filtering and simulation warning | Team permissions, barriers/polygons/entrances, independent accuracy and reachability validation |
| 8 | Alternate and blocked routes | Existing graph routing foundation | Closure-aware alternatives, rerouting, updated ETA and no-route behavior |
| 9 | GIS update lifecycle | Candidate/backups and current source retained | Validated comparison, approved activation/rollback, cadence and staff alerts |
| 10 | Rewards and demonstration checkout | Server game checks, one attempt/coupon per purchase, wallet and one-use redemption; V35 simulated payment/dispatch | Live end-to-end acceptance, promotion terms and measured game balance |
| 11 | Mobile/accessibility/performance | Shared UI, touch/keyboard, reduced-motion effects and DOM checks | Android/iOS, short viewports, focus/contrast, audio, reconnect and multi-customer performance acceptance |
| 12 | Real GPS/telemetry | Explicitly labelled delivery simulation | Future hardware integration requires team telemetry contract and real-device validation |

**Scope correction:** the user requires a complete no-charge demonstration, not real payment processing. A live payment provider is no longer a prerequisite for accepting packages 4 and 10. V35 uses a server-owned demonstration wallet and never charges money. Real GPS remains a future hardware integration and is not claimed by the simulation.

The broader ledger still has 12 package IDs with at least one acceptance/integration item outstanding. Do not state ALL MAP ITEMS ARE COMPLETE until all requirements in the agreed scope are accepted. Record the actual pushed/deployed commit and live results after running the release; a prepared package alone is not deployment evidence.
