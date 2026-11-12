#!/usr/bin/env bash
# Run inside the emulator action, while the emulator is still available.
set -u
cd gorod-control/region-v2/android
# Only the disposable CI emulator: stop the launcher left in an ANR state on
# some cold boots. Do not dismiss app errors; the test asserts our own package
# is actually the focused visible window before accepting its screenshot.
adb shell am force-stop com.google.android.apps.nexuslauncher
# Repeat a public street test coordinate through the emulator's system GPS.
# This tests the Android/WebView bridge, not a user's phone or real location.
don_geo_point=$(python3 - <<'PYPOINT'
import json
f=json.load(open('app/src/debug/assets/web/qa/real-feed.json'))
a=next(a for e in f['events'] if e['category']=='water' for a in e['addresses'] if a.get('geometryVerified'))
print(str(a['lon'])+' '+str(a['lat']))
PYPOINT
)
adb shell settings put secure location_mode 3
(for don_i in $(seq 1 120); do adb emu geo fix $don_geo_point >/dev/null; sleep 2; done) &
don_geo_pid=$!
trap 'kill "$don_geo_pid" 2>/dev/null || true' EXIT
don_test_result=0
gradle --no-daemon :app:connectedDebugAndroidTest || don_test_result=$?
mkdir -p /tmp/don-android-results
if ! adb pull /sdcard/Download/don-preview.png /tmp/don-android-results/; then
  echo 'Android screenshot could not be retrieved'
  don_test_result=1
fi
for don_proof in don-real-water-map don-real-water-card don-real-near-system-gps; do
  if ! adb pull "/sdcard/Download/$don_proof.png" /tmp/don-android-results/; then don_test_result=1; fi
done
# Preserve a failed viewport diagnosis as well; it never replaces a required proof.
for don_failed in map events; do
  adb pull "/sdcard/Download/don-scroll-failure-$don_failed.png" /tmp/don-android-results/ 2>/dev/null || true
done
exit "$don_test_result"
