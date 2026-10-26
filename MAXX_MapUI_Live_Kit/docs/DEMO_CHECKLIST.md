# David and Shek - current-world software robot sign-off

## Before the October 27 demonstration

- [ ] Extract kit; open it in PyCharm; run tests.
- [ ] Stop old port-8000 server; start this kit.
- [ ] Confirm projects and events show CONNECTED, with successful fetch times.
- [ ] Explain: robot motion is software; public geometry/projects/event times are actual source data; event crowds are predictions.
- [ ] Pick one shared control operator.

## Five-minute rehearsal

1. David: show real paths/buildings, six numbered building targets, Southside Dining base and eight tagged access restrictions and the verified source panel; zoom/pan.
2. Shek: select delivery 2, Apply, 1x or declared 10x, Start; compare 10-second and 1-second reads.
3. David: show ETA, Pause/resume, and view/layer choices surviving refresh.
4. Both: inspect actual published project polygons. Enable optional Construction-area avoidance. Explain why projects are not automatically confirmed sidewalk closures.
5. Both: inspect the real Johnson Center event and its time window. Heat must remain absent outside that window unless there are actual current crowd reports.
6. Shek: explain source-change pause/reset and unavailable-trip behavior. Use the separate simulation mode for reproducible synthetic blockages, never insert fake staff observations into live mode.

## Actual observations, if you are on campus

- [ ] Reporter selects their actual location/source; no fake GPS claim.
- [ ] A genuinely observed closure is submitted, timestamped and used in routing.
- [ ] Explicit clearance is submitted only after the obstacle actually clears.
- [ ] A real crowd observation uses a stable ID; updating it does not duplicate it.
- [ ] No personal observation files are staged in Git.

## Device evidence

| Device / OS / browser | Pan & zoom | Layers | ETA & motion | Portrait/landscape | Tester / result |
|---|---|---|---|---|---|
| iPhone / Safari | pending | pending | pending | pending | |
| Android / Chrome | pending | pending | pending | pending | |
| Windows browser | pending | pending | pending | n/a | |

## Defect log

| ID | Device/source/scenario | Expected | Actual | Owner | Fix / retest |
|---|---|---|---|---|---|
| D-001 | | | | | |

## Submission

- [ ] Target branch is MapUI; original map/team backend remain intact.
- [ ] Review staged changes and tests before commit/push.
- [ ] No runtime reports, tokens or private location data staged.
- [ ] Card wording distinguishes connected public inputs, predictions and software movement.

- [ ] Red restricted-entry icon matches map and legend; popups expose actual source tags.
- [ ] Purple outward and orange dashed return are both visible.
- [ ] Layout keeps the team’s heading/instruction/map order, with new controls below.
