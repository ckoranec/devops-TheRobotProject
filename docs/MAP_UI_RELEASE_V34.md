# MAXX Bytes V34 — customer navigation, checkout and map presentation

## Implemented in this release

- Shared MAXX Bytes heading and ordered navigation on all 14 public HTML pages: Home, Login, My coupons, Menu, Order, Track Delivery, About MAXX Bytes, Contact Us.
- Relative same-origin links work on localhost and production. Saved/purchase mission context follows shared order and tracking links; explicit links to another saved mission retain that mission.
- Delivery preview and the three numbered order steps are actual links.
- Compact checkout form and totals, with visible loading, validation, error and completion states. Remove nested transaction scrollers and unused identity fields. A completed demo purchase exposes its own mission link; repeated clicks cannot create duplicate submissions. Network retries keep the same idempotency key.
- Real Login/Create account controls use the existing account API. Remove simulated 2FA/recovery success from login.html.
- Classic/Customize hide the game legend and expose a compact green Snack Chase invitation. Snack Chase shows the dollar-emoji reward explanation, 24 accessories, RGB picker and 12 map effects. Existing SVG artwork is reused.
- MapAPI and tracking remain identical entry pages. Map layout engine, mission routing, delivery/game mechanics, frame sizing, route colors, robot sizes, telemetry and source GIS are retained.
- Deployment covers 44 allowed public files, plus the private API from the approved commit. Reuse installed matching dependencies; wait for Nginx API readiness; preserve private accounts and rollback on failed verification.

## Validation during preparation

- DOM interaction checks: demo success, totals, repeated clicks, stable retry keys, backend failure, signed-out state and production-disabled checkout.
- Real Python API integration: register/login -> save mission -> execute checkout UI -> obtain purchase-specific mission -> start eligible game.
- All 14 headers have the requested order and valid file targets. Preview badge and numbered step links exist.
- 24 accessories, 12 effects, RGB picker, shared robot redraw, mode-specific legend and reward boxes.
- Real account endpoint sequence, registration error handling and external-redirect rejection.
- Isolated deployment activation, transient 404 readiness, existing dependency reuse and forced-failure rollback.

## Acceptance still required

Run the existing full local suite and inspect desktop/mobile layouts on port 8000 before approval. In particular, verify the checkout card fits your normal desktop viewport, the map frames retain the accepted proportions, and both MapAPI/tracking show the same controls after Ctrl+F5. Short or mobile viewports use normal document scrolling instead of clipping content.

Production demo checkout remains disabled by the existing production policy. Real payment confirmation and dispatch are not implemented by this UI release; the production page states this and disables completion. Local demo checkout takes no payment and dispatches no food.

Latest confirmed source baseline: 3d887a94dec6828c33efd7ce1b8b3022b51ba446 pushed to DevOps. Supplied V33 production log rolled back after Nginx /api/release returned 404. No later successful production record was supplied when preparing V34.
