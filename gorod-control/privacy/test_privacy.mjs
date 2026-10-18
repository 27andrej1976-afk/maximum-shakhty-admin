import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const root='gorod-control/';
for(const file of ['index.html','compact-v11/index.html']){
 const s=readFileSync(root+file,'utf8');
 assert.ok(s.includes('function setupPrivacyControls()'),file+': privacy control present');
 assert.ok(s.includes("localStorage.removeItem(KEY)"),file+': WebView address deletion');
 assert.ok(s.includes("citycontrol://delete-home"),file+': native address deletion');
 assert.ok(!s.includes('fonts.googleapis.com'),file+': no external Google Font');
 assert.ok(s.includes("nominatim.openstreetmap.org"),file+': geocoder remains disclosed, not claimed removed');
}
const java=readFileSync(root+'android/app/src/main/java/ru/citycontrol/shakhty/MainActivity.java','utf8');
assert.ok(java.includes('"delete-home".equals(target.getHost())'));
assert.ok(java.includes('request.isForMainFrame() && isTrustedPage(view.getUrl())'));
assert.ok(java.includes('.remove("street").remove("house").apply()'));
assert.ok(java.includes('No saved home: never keep a stale copy'));
console.log('PASS privacy branch static checks: both interfaces and Android home deletion; no remote Google Fonts');
