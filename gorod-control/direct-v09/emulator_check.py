import subprocess,time,json,urllib.request,hashlib,atexit,sys
from pathlib import Path
subprocess.run([sys.executable,'-m','pip','install','--quiet','websocket-client'],check=True)
import websocket
OUT=Path('android-device-report');OUT.mkdir(exist_ok=True)
APK=Path('gorod-control/direct-v09/downloads/GorodPodKontrolem-0.9.0-test.apk');PKG='ru.citycontrol.shakhty.beta'
checks=[];report={'apkSha256':hashlib.sha256(APK.read_bytes()).hexdigest(),'physicalPhoneTest':False,'gpsFixTest':False}
def adb(*args,check=True):return subprocess.run(['adb',*args],capture_output=True,text=True,check=check,timeout=45).stdout.strip()
def capture(name):
 with (OUT/name).open('wb') as out:subprocess.run(['adb','exec-out','screencap','-p'],stdout=out,check=False,timeout=20)
def finish():
 report.update(passed=len(checks),checks=checks)
 (OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 try:(OUT/'logcat.txt').write_text(adb('logcat','-d','-t','1200',check=False),encoding='utf-8');capture('android-final.png')
 except Exception:pass
atexit.register(finish)
def yes(b,s):
 if not b:raise AssertionError(s)
 checks.append(s);print('ANDROID_CHECK',s,flush=True)
adb('logcat','-c');yes('Success' in adb('install','-r',str(APK)),'APK installs on Android')
for permission in ('ACCESS_COARSE_LOCATION','ACCESS_FINE_LOCATION','POST_NOTIFICATIONS'):adb('shell','pm','grant',PKG,'android.permission.'+permission,check=False)
adb('shell','cmd','location','set-location-enabled','true',check=False);adb('emu','geo','fix','40.2146','47.7086',check=False)
yes('Status: ok' in adb('shell','am','start','-W','-n',PKG+'/ru.citycontrol.shakhty.MainActivity'),'native Activity starts')
time.sleep(3);pid=adb('shell','pidof',PKG,check=False);yes(bool(pid),'Android process remains running')
adb('forward','tcp:9222','localabstract:webview_devtools_remote_'+pid.split()[0])
for i in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:9222/json/list',timeout=2) as r:targets=json.load(r)
  target=next(t for t in targets if t.get('type')=='page');break
 except Exception:time.sleep(1)
ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=15,suppress_origin=True);serial=0
def evaluate(expression):
 global serial
 serial+=1;ident=serial
 ws.send(json.dumps({'id':ident,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True,'awaitPromise':True}}))
 while True:
  r=json.loads(ws.recv())
  if r.get('id')==ident:
   if r.get('error') or r.get('result',{}).get('exceptionDetails'):raise RuntimeError(str(r))
   return r.get('result',{}).get('result',{}).get('value')
def wait(expression,seconds=60):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  try:
   if evaluate(expression):return
  except Exception:pass
  time.sleep(1)
 raise TimeoutError(expression)
def text(selector):return evaluate('document.querySelector('+json.dumps(selector)+')?.innerText') or ''
def click(selector):evaluate('document.querySelector('+json.dumps(selector)+').click()')
wait('!!document.querySelector("#cityAllButton")');yes('0.9' in text('.version'),'bundled updated UI renders inside Android')
wait('window.CityMapV07 && CityMapV07.inspect().allIds.some(id=>id.startsWith("power-direct-"))')
yes(True,'native source bridge delivers real official electricity events to WebView')
yes(evaluate('document.querySelector("img.city-coat").naturalWidth>0'),'crest loaded from APK assets')
wait('!document.querySelector("#checkButton").disabled',90)
direct=text('#directStatus');report['sourceResult']=direct;yes('не подтверждено' in direct or 'получены' in direct,'actual original-source response displayed honestly')
capture('android-top.png')
click('#cityAllButton');wait('CityMapV07.inspect().mode==="city"')
yes(evaluate('document.querySelectorAll("[data-event-id^=power-direct-]").length>0'),'citywide direct notices visible on installed APK')
click('[data-event-id^="power-direct-"] .cm-detail-button');yes(evaluate('document.querySelector("#cityEventDetail").open'),'incident details open in Android')
yes('Донэнерго' in text('#cityEventBody'),'original service attribution is present');capture('android-detail.png');click('#cityEventClose')
click('#notifyButton');time.sleep(2)
notifications=adb('shell','dumpsys','notification','--noredact',check=False)
yes('ТЕСТ: уведомления работают' in notifications,'native test notification is posted')
(OUT/'notification-test.txt').write_text('\n'.join(x for x in notifications.splitlines() if 'ТЕСТ:' in x or PKG in x),encoding='utf-8')
# Test real native GPS bridge with explicit emulator coordinates, not the user's location.
click('#geoButton');adb('emu','geo','fix','40.2146','47.7086',check=False)
wait('(()=>{try{const h=JSON.parse(localStorage.getItem("gorod_control_home_v1"));return h&&Math.abs(h.lat-47.7086)<0.02&&Math.abs(h.lon-40.2146)<0.02}catch(e){return false}})()',55)
yes(True,'native GPS bridge saves the injected emulator point');report['gpsFixTest']='emulator coordinate injection only'
ws.close()
log=adb('logcat','-d','-t','1200',check=False);yes(not('FATAL EXCEPTION' in log and 'Process: '+PKG in log),'no Android fatal exception')
report['device']=adb('shell','getprop','ro.build.version.release');report['completed']=True
print('INSTALLED ANDROID CHECKS PASSED',len(checks))
