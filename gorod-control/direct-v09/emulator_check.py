import subprocess,time,json,re,urllib.request,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path('android-device-report');OUT.mkdir(exist_ok=True)
APK=Path('gorod-control/direct-v09/downloads/GorodPodKontrolem-0.9.0-test.apk')
PKG='ru.citycontrol.shakhty.beta'
checks=[]
def adb(*args,check=True):return subprocess.run(['adb',*args],capture_output=True,text=True,check=check,timeout=45).stdout.strip()
def yes(b,s):
 if not b:raise AssertionError(s)
 checks.append(s)
adb('logcat','-c');result=adb('install','-r',str(APK));yes('Success' in result,'APK installs on Android')
for permission in ('ACCESS_FINE_LOCATION','ACCESS_COARSE_LOCATION','POST_NOTIFICATIONS'):
 adb('shell','pm','grant',PKG,'android.permission.'+permission,check=False)
adb('emu','geo','fix','40.2146','47.7086',check=False)
launched=adb('shell','am','start','-W','-n',PKG+'/ru.citycontrol.shakhty.MainActivity')
yes('Status: ok' in launched,'native Activity starts')
pid=''
for i in range(30):
 pid=adb('shell','pidof',PKG,check=False)
 if pid:break
 time.sleep(1)
yes(bool(pid),'Android process remains running')
adb('forward','tcp:9222','localabstract:webview_devtools_remote_'+pid.split()[0])
for i in range(30):
 try:
  with urllib.request.urlopen('http://127.0.0.1:9222/json/version',timeout=2) as r:info=json.load(r)
  break
 except Exception:time.sleep(1)
with sync_playwright() as p:
 browser=p.chromium.connect_over_cdp('http://127.0.0.1:9222')
 pages=[page for ctx in browser.contexts for page in ctx.pages]
 yes(bool(pages),'real Android WebView available')
 page=pages[0];page.wait_for_selector('#cityAllButton',timeout=35000)
 yes('0.9' in page.locator('.version').inner_text(),'bundled updated UI renders inside Android')
 page.wait_for_function('window.CityMapV07 && CityMapV07.inspect().allIds.some(id=>id.startsWith("power-direct-"))',timeout=60000)
 yes(True,'native background fetch delivers real direct electricity events to WebView')
 yes(page.locator('img.city-coat').evaluate('(e)=>e.complete&&e.naturalWidth>0'),'crest loaded from APK assets')
 # Actual Javascript -> Android navigation bridge -> HTTP -> JSON -> WebView callback.
 page.wait_for_function('!document.querySelector("#checkButton").disabled',timeout=90000)
 direct=page.locator('#directStatus').inner_text();yes('УРСВ' in direct or 'воды' in direct,'native original-source result is visible')
 yes('не подтверждено' in direct or 'получены' in direct,'no connection claim before actual response')
 page.screenshot(path=str(OUT/'android-top.png'))
 page.locator('#cityAllButton').click();page.wait_for_function('CityMapV07.inspect().mode==="city"')
 yes(page.locator('[data-event-id^="power-direct-"]').count()>0,'citywide event cards work on installed Android app')
 page.locator('[data-event-id^="power-direct-"] .cm-detail-button').first.click()
 yes(page.locator('#cityEventDetail').evaluate('(e)=>e.open'),'touch opens real incident card on Android')
 yes('Донэнерго' in page.locator('#cityEventBody').inner_text(),'original service attribution in native WebView')
 page.screenshot(path=str(OUT/'android-detail.png'))
 page.locator('#cityEventClose').click()
 # Test notification is labelled as a test, not a fictitious real emergency.
 page.locator('#notifyButton').click();time.sleep(2)
 notifications=adb('shell','dumpsys','notification','--noredact',check=False)
 yes('ТЕСТ: уведомления работают' in notifications,'native test notification is actually posted')
 (OUT/'notification-test.txt').write_text('\n'.join(x for x in notifications.splitlines() if 'ТЕСТ:' in x or PKG in x),encoding='utf-8')
 (OUT/'source-result.txt').write_text(direct,encoding='utf-8')
 browser.close()
log=adb('logcat','-d','-t','1000',check=False)
(OUT/'logcat.txt').write_text(log,encoding='utf-8')
yes(not ('FATAL EXCEPTION' in log and 'Process: '+PKG in log),'no Android fatal exception')
report={'apkSha256':hashlib.sha256(APK.read_bytes()).hexdigest(),'device':adb('shell','getprop','ro.build.version.release'),
 'passed':len(checks),'checks':checks,'physicalPhoneTest':False,'gpsFixTest':False,'sourceResult':direct}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('INSTALLED ANDROID CHECKS PASSED',len(checks))
