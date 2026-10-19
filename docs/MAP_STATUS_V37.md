# MAXX Bytes map checklist — evidence update

October 18, 2026. Stable package IDs preserved from MAP_CHECKLIST(5).md.

**12 packages remain open under the original acceptance rules.** This is an
acceptance count, not a count of packages lacking code. The older attachment's
claims that API deployment and purchase-scoped missions have not been built
are superseded by V33–V35 implementation and the supplied deployment logs.

Evidence: user's V35 run reports 104 passing tests, exact DevOps commit
f7db8e118ef32ad6da13a1072e56f3bed77cfb18 and successful private API deployment.
Read-only checks in this conversation confirmed that production reported that
commit, demo checkout enabled, and real payments disabled. The next DevOps
commit 5cccca7cbc44ff3ac2763718e8fe3b362985f4a1 contains the V36 asset repair.
This file does not certify authenticated browser tests or physical robot safety.

| Package | Implemented evidence | Still needed to close |
|---|---|---|
| 1. Routing API | Dijkstra API code and backend-capable deployment | Signed-in live route preview; verify geometry, distances and ETA for agreed destinations |
| 2. Account missions | Owner-scoped records and isolation tests in prior suite | Save → refresh → second-account isolation acceptance locally and live |
| 3. Delivery location | Known address, map/coordinate selection and save UI | General address coverage agreement; unsupported-address errors; fresh-customer acceptance |
| 4. Order mission integration | V35 simulated payment, purchase clock and automatic Classic journey | Refresh/reconnect across all views; real order/payment and physical delivery lifecycle |
| 5. API safeguards | Ownership, CSRF, throttling and checkout validation code/tests | Live session, error, rate-limit and customer-isolation acceptance |
| 6. GIS coverage | Existing paths, roads, stops, restrictions and junctions | Verified buildings, entrances, restricted polygons and closures with provenance; synchronized layer acceptance |
| 7. Robot access/accuracy | Simulation access filters and route warnings | Campus permissions, barrier/polygon checks, accessible handoffs, independent accuracy and reachability/timing matrix |
| 8. Rerouting | Baseline Dijkstra routing | Closure-aware alternatives, revised ETA, unreachable states and agreed crowd/traffic costs |
| 9. GIS lifecycle | Team ingestion/comparison tools exist | Staged dataset validation, comparison, approval, activation, rollback, source cadence and staff alerts |
| 10. Rewards | Server movement/collision/deadline, purchase coupon wallet and demo redemption | Live end-to-end reward/redemption acceptance; real-payment integration and promotion terms; game balance; final-two-minute award policy |
| 11. Mobile/accessibility/performance | Existing controls/layout plus V37 responsive landing implementation | Android/iOS, short screens, keyboard/touch, contrast, reduced motion, offline/reconnect, load and full customer-flow acceptance |
| 12. Real GPS | Simulation remains labeled | Team telemetry contract, authentication, order scope, 10-second updates, interpolation and stale/out-of-order/reconnect hardware checks |

## Next acceptance pass

1. Deploy V37 after the local diff and preview review. Record SHA and backup.
2. On local and live: create/sign in → select a featured meal → save location →
   confirm simulated payment → Classic → Customize → Snack Chase → wallet →
   next-order redemption. Refresh each stage and test a second account.
3. Record browser/device, expected behavior, observed behavior and failures.
4. Close only fully evidenced packages. Prioritize 1, 2 and 5 for acceptance;
   3 needs coverage decisions; 4 and 10 retain real-payment requirements.
5. Agree missing GIS data, robot operating permissions and the telemetry
   contract with the team, then implement packages 6–9 and 12 against those inputs.

V37 changes presentation and meal selection; it does not close a map package.
The current game awards completion before arrival. It does not enforce an
award window restricted to the final two minutes. That requirement remains open.
