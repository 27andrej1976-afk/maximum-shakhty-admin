#!/usr/bin/env bash
# Run inside the emulator action, while the emulator is still available.
set -u
cd gorod-control/region-v2/android
# Only the disposable CI emulator: stop the launcher left in an ANR state on
# some cold boots. Do not dismiss app errors; the test asserts our own package
# is actually the focused visible window before accepting its screenshot.
adb shell am force-stop com.google.android.apps.nexuslauncher
don_test_result=0
gradle --no-daemon :app:connectedDebugAndroidTest || don_test_result=$?
mkdir -p /tmp/don-android-results
if ! adb pull /sdcard/Download/don-preview.png /tmp/don-android-results/; then
  echo 'Android screenshot could not be retrieved'
  don_test_result=1
fi
exit "$don_test_result"
