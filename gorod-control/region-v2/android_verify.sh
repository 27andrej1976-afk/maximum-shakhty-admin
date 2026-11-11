#!/usr/bin/env bash
# Run inside the emulator action, while the emulator is still available.
set -u
cd gorod-control/region-v2/android
don_test_result=0
gradle --no-daemon :app:connectedDebugAndroidTest || don_test_result=$?
mkdir -p /tmp/don-android-results
if ! adb pull /sdcard/Android/data/ru.citycontrol.don/files/don-preview.png /tmp/don-android-results/; then
  echo 'Android screenshot could not be retrieved'
  don_test_result=1
fi
exit "$don_test_result"
