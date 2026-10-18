"""Keyless modern map interactive smoke tests. No synthetic events published."""
import json,subprocess,tempfile,threading,functools,http.server,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'light-map-test-report';OUT.mkdir(exist_ok=True)
now=datetime.now(timezone.utc)
def stamp(hours):return (now+timedelta(hours=hours)).isoformat()
demo_event={
 "id":"ci-fixture-light-water","category":"water","kind":"planned","status":"active","sourceId":"repost_rostov",
 "source":"Управление развития систем водоснабжения","origin":"verified_repost","title":"Проверка карты: вода",
 "description":"Только автоматическая тестовая фикстура.","start":stamp(2),"end":stamp(5),"publishedAt":stamp(-1),
 "url":"https://rovodokanal.ru/emergency-alerts/1591","point":{"lat":47.7088,"lon":40.2149},
 "affected":[{"street":"ул Советская","houses":["11"]}]
}
feed={"schema":2,"checkedAt":stamp(0),"sources":[{"id":"repost_rostov","status":"ok","lastPostAt":stamp(-1),"posts":1,"url":"https://newsrostov.ru/rss.xml"}],"events":[demo_event]}
home={"lat":47.7086,"lon":40.2146,"street":"ул Советская","house":"11","label":"Тестовый дом, Шахты","method":"address"}
server=http.server.ThreadingHTTPServer(('127.0.0.1',18766),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
base='http://127.0.0.1:18766/gorod-control/'
checks=[]
def check(cond,label):
 if not cond:raise AssertionError(label)
 checks.append(label);print('CHECK:',label,flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 ctx=browser.new_context(viewport={'width':393,'height':852},device_scale_factor=1,is_mobile=True,has_touch=True)
 p=ctx.new_page();errors=[];tiles=[]
 p.on('pageerror',lambda e:errors.append(str(e)))
 p.on('response',lambda r:tiles.append((r.status,r.url)) if 'tiles.openfreemap.org' in r.url else None)
 p.add_init_script('localStorage.setItem("gorod_control_home_v1",'+json.dumps(json.dumps(home,ensure_ascii=False))+');')
 p.route('**/data/water.json*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(feed,ensure_ascii=False)))
 p.goto(base,wait_until='domcontentloaded')
 p.wait_for_selector('#cityNearButton',timeout=15000)
 p.wait_for_function('CityMapV07.inspect().allIds.includes("ci-fixture-light-water")',timeout=15000)
 check(p.locator('img.city-coat').evaluate('e=>e.complete&&e.naturalWidth>0'),'official crest still renders')
 check(p.evaluate('CityMapV07.inspect().mode')=='near','saved home still controls default scope')
 check(p.locator('#cityNearButton').count()==1 and p.locator('#cityAllButton').count()==1,'original home and city mode buttons retained')
 p.locator('#cityAllButton').click()
 check(p.evaluate('CityMapV07.inspect().mode')=='city','citywide browsing retained')
 check(p.locator('article[data-event-id="ci-fixture-light-water"]').count()==1,'city notice appears')
 p.locator('article[data-event-id="ci-fixture-light-water"] button.cm-detail-button').click()
 check('Проверка карты: вода' in p.locator('#cityEventTitle').inner_text(),'clicking event opens original incident details')
 p.locator('#cityEventClose').click()
 try:
  p.wait_for_function("CityMapV07.inspect().basemap==='bright'",timeout=30000)
  check(True,'real OpenFreeMap Bright renderer loaded')
 except Exception as exc:
  (OUT/'failure-network.json').write_text(json.dumps({'state':p.evaluate('CityMapV07.inspect()'),'tiles':tiles[-35:],'errors':errors[-20:]},indent=2,ensure_ascii=False))
  p.screenshot(path=str(OUT/'network-fallback.png'),full_page=True)
  raise
 check(bool(p.locator('canvas.maplibregl-canvas').count()),'real WebGL vector map canvas present')
 check(any(status==200 for status,url in tiles if '/styles/bright/' in url),'actual style and map assets retrieved')
 p.screenshot(path=str(OUT/'bright-mobile.png'),full_page=True)
 check('0.7' not in p.locator('.version').inner_text(),'map version and bright design updated')
 ctx.close()
 fallback=browser.new_context(viewport={'width':393,'height':852},device_scale_factor=1,is_mobile=True,has_touch=True)
 q=fallback.new_page();qerrors=[]
 q.on('pageerror',lambda e:qerrors.append(str(e)))
 q.route('**/light-v10/vendor/maplibre-gl.js',lambda r:r.abort())
 q.route('**/data/water.json*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(feed,ensure_ascii=False)))
 q.add_init_script('localStorage.setItem("gorod_control_home_v1",'+json.dumps(json.dumps(home,ensure_ascii=False))+');')
 q.goto(base,wait_until='domcontentloaded')
 q.wait_for_selector('#cityAllButton',timeout=15000)
 check(q.evaluate("CityMapV07.inspect().basemap")=='fallback','no WebGL library gracefully falls back to classic OSM')
 q.locator('#cityAllButton').click()
 check(q.evaluate("CityMapV07.inspect().mode")=='city','city mode also works during fallback')
 check(q.locator('article[data-event-id="ci-fixture-light-water"]').count()==1,'incident retained when vector map unavailable')
 q.screenshot(path=str(OUT/'osm-fallback-mobile.png'),full_page=True)
 fallback.close();browser.close()
server.shutdown()
(OUT/'checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'vectorHTTP':tiles[-24:],'pageErrors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print('LIGHT MAP CHECKS PASSED:',len(checks),flush=True)
