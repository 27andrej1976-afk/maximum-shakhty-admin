"""Android emulator smoke test for both competing City Control APK variants."""
import os,sys,subprocess,time,json,urllib.request,atexit,hashlib
from pathlib import Path
variant=os.environ.get('CITY_VARIANT','normal')
assert variant in ('normal','compact')
PKG='ru.citycontrol.shakhty.'+('normalreport' if variant=='normal' else 'compactreport')
APK=Path('gorod-control/android/app/build/outputs/apk/debug/app-debug.apk')
OUT=Path('two-apks-android-report')/variant
OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def adb(*args,check=True):
 p=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=65)
 if check and p.returncode:raise RuntimeError('ADB '+str(args)+': '+p.stderr[-900:])
 return p.stdout.strip()
def check(cond,message):
 if not cond:raise AssertionError(message)
 checks.append(message)
 print('ANDROID_REPORTS_OK',variant,message,flush=True)
def finish():
 (OUT/'checks.json').write_text(json.dumps({'variant':variant,'package':PKG,'checks':checks,'sha256':hashlib.sha256(APK.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
 try:
  with (OUT/'screen.png').open('wb') as f:subprocess.run(['adb','exec-out','screencap','-p'],stdout=f,timeout=25)
 except Exception:pass
atexit.register(finish)
check('Success' in adb('install','-r',str(APK)),'APK installed')
check('Status: ok' in adb('shell','am','start','-W','-n',PKG+'/ru.citycontrol.shakhty.MainActivity'),'Activity started')
for _ in range(25):
 pid=adb('shell','pidof',PKG,check=False)
 if pid:break
 time.sleep(1)
check(bool(pid),'Application process stays running')
adb('forward','tcp:9323','localabstract:webview_devtools_remote_'+pid.split()[0])
for _ in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:9323/json/list',timeout=3) as r:pages=json.load(r)
  target=next(page for page in pages if page.get('type')=='page')
  break
 except Exception:time.sleep(1)
else:raise RuntimeError('WebView inspector unavailable')
import websocket
ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=20,suppress_origin=True)
seq=0
def evaluate(expression):
 global seq
 seq+=1;identity=seq
 ws.send(json.dumps({'id':identity,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':True}}))
 for _ in range(250):
  d=json.loads(ws.recv())
  if d.get('id')==identity:
   payload=d.get('result',{})
   if d.get('error') or payload.get('exceptionDetails'):raise RuntimeError(str(d.get('error') or payload['exceptionDetails']))
   return payload.get('result',{}).get('value')
 raise TimeoutError(expression)
for i in range(90):
 try:
  if evaluate("!!window.CityMapV07 && !!document.querySelector('#reportIssueButton')"):break
  if i%15==0:
   diagnostic=evaluate("JSON.stringify({ready:document.readyState,url:location.href,body:document.body?.textContent?.slice(0,180),cityMap:!!window.CityMapV07,reportButton:!!document.querySelector('#reportIssueButton')})")
   print('ANDROID_STARTUP_DIAGNOSTIC',variant,diagnostic,flush=True)
 except Exception as exc:
  if i%15==0:print('ANDROID_STARTUP_WAIT',variant,str(exc)[:220],flush=True)
 time.sleep(1)
else:raise AssertionError('Report button or existing city map did not initialize after 90s')
check(evaluate("document.querySelector('img.city-coat').naturalWidth>0"),'Real city coat remains visible')
check(evaluate("document.querySelector('#reportIssueButton').href==='https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/official-intake-v14/'"),'Official report form linked correctly')
check(evaluate("!!document.querySelector('#geoButton') && !!document.querySelector('#checkButton')"),'GPS and manual refresh controls preserved')
check(evaluate("!!document.querySelector('#cityAllButton')"),'Citywide map control remains')
evaluate("document.querySelector('#cityAllButton').click()")
check(evaluate("CityMapV07.inspect().mode==='city'"),'Citywide mode functions')
check(evaluate("!!document.querySelector('.cm-map-source-credit')"),'Legal map copyright credit preserved')
check(evaluate("!document.querySelector('#map .leaflet-control-attribution')"),'No old Leaflet attribution')
if variant=='compact':
 check(evaluate("!!document.querySelector('#compactNav')"),'Compact bottom navigation available')
 check(evaluate("!!document.querySelector('#compactSourcesFold')&&!document.querySelector('#compactSourcesFold').open"),'Compact source details collapsed')
else:
 check(evaluate("!document.querySelector('#compactNav')"),'Original UI remains original')
check(evaluate("CityMapV07.getMap().dragging.enabled()"),'Leaflet map gestures are enabled')
before=evaluate("JSON.stringify([CityMapV07.getMap().getCenter().lat,CityMapV07.getMap().getCenter().lng])")
evaluate("CityMapV07.getMap().panBy([85,50],{animate:false});true")
time.sleep(1.2)
after=evaluate("JSON.stringify([CityMapV07.getMap().getCenter().lat,CityMapV07.getMap().getCenter().lng])")
check(before!=after,'Leaflet map moves when panned inside Android WebView')
vector=evaluate("!!CityMapV07.getVectorMap()")
if vector:
 # If the bright vector map is active, both engines must agree after a pan.
 check(evaluate("""(function(){
 const l=CityMapV07.getMap(),g=CityMapV07.getVectorMap(),a=l.getCenter(),b=g.getCenter();
 return Math.abs(a.lat-b.lat)<0.0001 && Math.abs(a.lng-b.lng)<0.0001;
 })()"""),'Leaflet and MapLibre centers remain synchronized in Android WebView')
else:
 print('ANDROID_NOTE',variant,'OSM fallback active; MapLibre browser-pan regression tested separately',flush=True)
ws.close()
print('ANDROID_REPORTS_TEST_PASSED',variant,len(checks),flush=True)
