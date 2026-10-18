"""Verify test APK launches and bright city map UI works in actual Android WebView."""
import subprocess, time, json, urllib.request, hashlib, atexit
from pathlib import Path
OUT=Path('compact-android-test-report');OUT.mkdir(exist_ok=True)
APK=Path('gorod-control/android/app/build/outputs/apk/debug/app-debug.apk')
PACKAGE='ru.citycontrol.shakhty.compact'
results=[]
def cmd(*args,timeout=50):
    r=subprocess.run(['adb',*args],text=True,capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError('adb '+str(args)+' '+r.stderr[-1200:])
    return r.stdout.strip()
def ok(b,s):
    if not b:raise AssertionError(s)
    results.append(s);print('ANDROID CHECK:',s,flush=True)
def record():
    (OUT/'checks.json').write_text(json.dumps({'checks':results,'apkSha256':hashlib.sha256(APK.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
    try:
        with (OUT/'installed-bright-app.png').open('wb') as file:subprocess.run(['adb','exec-out','screencap','-p'],stdout=file,check=False,timeout=20)
    except Exception:pass
atexit.register(record)
ok('Success' in cmd('install','-r',str(APK)), 'light APK installs on Android')
cmd('shell','am','force-stop',PACKAGE)
out=cmd('shell','am','start','-W','-n',PACKAGE+'/ru.citycontrol.shakhty.MainActivity')
ok('Status: ok' in out, 'native activity opens successfully')
pid=''
for _ in range(20):
    pid=cmd('shell','pidof',PACKAGE) if subprocess.run(['adb','shell','pidof',PACKAGE],capture_output=True).returncode==0 else ''
    if pid:break
    time.sleep(1)
ok(bool(pid),'Android process stays alive')
cmd('forward','tcp:9225','localabstract:webview_devtools_remote_'+pid.split()[0])
for _ in range(35):
    try:
        with urllib.request.urlopen('http://127.0.0.1:9225/json/list',timeout=2) as response:
            targets=json.load(response)
        target=next(t for t in targets if t.get('type')=='page')
        break
    except Exception:time.sleep(1)
else:raise RuntimeError('WebView remote debugging not ready')
import websocket
ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=20,suppress_origin=True)
serial=0
def evaluate(expr):
    global serial
    serial+=1;rid=serial
    ws.send(json.dumps({'id':rid,'method':'Runtime.evaluate','params':{'expression':expr,'returnByValue':True,'awaitPromise':True}}))
    for _ in range(100):
        frame=json.loads(ws.recv())
        if frame.get('id')==rid:
            if frame.get('error'):raise RuntimeError(str(frame['error']))
            payload=frame.get('result',{})
            if payload.get('exceptionDetails'):raise RuntimeError(str(payload['exceptionDetails']))
            return payload.get('result',{}).get('value')
    raise RuntimeError('Webview evaluation timed out')
for _ in range(45):
    if evaluate("!!(window.CityMapV07&&document.querySelector('#cityAllButton'))"):break
    time.sleep(1)
else:raise RuntimeError('City map UI did not initialize in Android')
ok(evaluate("document.querySelector('img.city-coat').naturalWidth>0"),'Shakhty city coat displays')
ok(evaluate("document.querySelector('.version').textContent.includes('КОМПАКТ')"),'compact version shown in APK')
ok(evaluate("!!document.querySelector('#map')"),'map container present')
ok(evaluate("CityMapV07.inspect().basemap==='bright'||CityMapV07.inspect().basemap==='fallback'"),'vector or safe OSM fallback active')
evaluate("document.querySelector('#cityAllButton').click()")
ok(evaluate("CityMapV07.inspect().mode==='city'"),'citywide zoom mode works in Android')
ok(evaluate("!!document.querySelector('#compactNav')"),'functional compact navigation available')
ok(evaluate("document.querySelector('#compactCityFold') && !document.querySelector('#compactCityFold').open"),'long city list collapsed by default')
ok(evaluate("document.querySelector('#compactSourcesFold') && !document.querySelector('#compactSourcesFold').open"),'source list collapsed by default')
ok(evaluate("!!document.querySelector('#geoButton') && !!document.querySelector('#checkButton')"),'original GPS and refresh controls retained')
ok(evaluate("!!document.querySelector('.cm-map-source-credit')"),'map copyright links retained')
evaluate("document.querySelector('#compactNav button:nth-child(3)').click()")
ok(evaluate("document.querySelector('#compactLocalFold').open"),'notification navigation expands local events')
ws.close()
print('ANDROID COMPACT CHECKS PASSED',len(results),flush=True)
