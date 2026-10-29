# Compact reliability gates (1.9)

Do not remove these checks when changing feeds, maps, build preparation or source lists.

## Non-negotiable behavior

- A failed WebGL renderer must leave raster map, source refresh and manual address controls operational. Partial cleanup and delayed pan/zoom callbacks must be harmless.
- City/nearby choice is explicit. Zoom and pan must not change it or discard accepted markers. Geometry may position an accepted event, never create a new event.
- Direct/MAX and municipal feeds have independent clocks. A native refresh or rebuilt envelope is not proof that every source, or every event, was checked again.
- Bind each notice to its exact origin, allowed URL and matching source state. Generic legacy electricity `power_repost` is mapped only by the known mirror domain. Unknown archives/rumors do not become official notices.
- Preserve review flags; ambiguous address records must not produce automatic alerts or close another incident.
- A source failure or empty response is not restoration. Keep previously confirmed water/power only until original end/start/publication +36h, visibly unconfirmed. Never reset confirmation/expiry on refresh.
- Publish validated closure tombstones separately from visible events and consume them in both web and native clients. Validate trust/freshness before same-ID overwrite; match different-ID restorations only to a unique exact affected area/work site. Never resurrect a resolved record from an older active copy.
- An unknown cloud clock in a legacy native cache stays unknown. Direct phone reading remains HTTPS to URSV; no credentials, home address or GPS coordinates are sent to feed servers.

## Required checks

```sh
python -m unittest discover -s gorod-control/scripts -p 'test_*.py' -q
node gorod-control/scripts/test_frontend.mjs
node gorod-control/scripts/test_feed_policy.mjs
node gorod-control/map-v07/test_fallback.mjs
node gorod-control/map-v07/test_pan_sync.mjs
node gorod-control/map-v07/test_zoom_mode.mjs
node gorod-control/map-v07/test_fallback.mjs --browser
```

The build-only workflow also prepares the real compact bundle, compiles Android, verifies APK signature/package, installs on an API35 emulator, runs the existing GPS/layout/notification/scope/pan/zoom checks and forces WebGL failure **inside the installed WebView** before exercising refresh/address/markers again. APK upload must occur only after these checks pass.

`test_feed_policy.mjs` asserts the static compact page and Android template have identical acceptance logic. `test_native_feed_merge.py` compiles and runs pure Java merge regressions without Android/network. `test_feed_composition.py` includes the real October29 source divergence and producer→composition identity cases.

## Release boundary

1.9 is built on a separate repair branch with `contents: read`; its workflow does not push/merge/deploy `main`. Published website and server workflow changes require separate authorized publication. The APK independently combines the existing public baseline and direct feeds/maps, so it does not depend on that publication for the new fallback path. A fresh debug build may have a different signing certificate: compare certificate fingerprints, and never claim in-place upgrade compatibility without verification.

No changes to Alisa2.0 or a classic app are part of this repair.
