import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const root='gorod-control/';
for(const file of ['index.html','compact-v11/index.html']){
 const s=readFileSync(root+file,'utf8');
 assert.ok(s.includes('function setupPrivacyControls()'),file+': privacy control present');
 assert.ok(s.includes("localStorage.removeItem(KEY)"),file+': WebView address deletion');
 assert.ok(s.includes("citycontrol://delete-home"),file+': native address deletion');
 assert.ok(!s.includes('fonts.googleapis.com'),file+': no external Google Font');
 assert.ok(s.includes('saveAddressLocallyButton'),file+': offline local address path');
 assert.ok(s.includes("method:'manual-map'"),file+': map-center user-selected coordinates');
 assert.ok(s.includes("const lookup=window.confirm("),file+': opt-in GPS reverse geocoding');
 assert.ok(s.includes("const consent=window.confirm("),file+': opt-in precise address geocoding');
 assert.ok(s.includes("nominatim.openstreetmap.org"),file+': geocoder remains disclosed, not claimed removed');
}
const java=readFileSync(root+'android/app/src/main/java/ru/citycontrol/shakhty/MainActivity.java','utf8');
assert.ok(java.includes('"delete-home".equals(target.getHost())'));
assert.ok(java.includes('request.isForMainFrame() && isTrustedPage(view.getUrl())'));
assert.ok(java.includes('.remove("street").remove("house").apply()'));
assert.ok(java.includes('No saved home: never keep a stale copy'));

const manifest=readFileSync(root+'android/app/src/main/AndroidManifest.xml','utf8');
assert.match(manifest,/android:allowBackup="false"/);
assert.ok(!manifest.includes('android.permission.READ_CONTACTS'));
assert.ok(!manifest.includes('android.permission.READ_EXTERNAL_STORAGE'));
const worker=readFileSync(root+'android/app/src/main/java/ru/citycontrol/shakhty/WaterMonitorJobService.java','utf8');
assert.ok(worker.includes('gorod-control/data/water.json'));
assert.ok(worker.includes('getSharedPreferences("city-control-home",MODE_PRIVATE)'));
assert.ok(!worker.includes('nominatim.openstreetmap.org'));
const map=readFileSync(root+'map-v07/city-map.js','utf8');
assert.ok(map.includes('https://tiles.openfreemap.org/styles/bright'));
assert.ok(map.includes('https://tile.openstreetmap.org/{z}/{x}/{y}.png'));

console.log('PASS privacy branch static checks: both interfaces and Android home deletion; no remote Google Fonts');
