"""Local app contract test, not a real-device GPS/push test. No production writes."""
import functools,http.server,json,threading,shutil
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
import water_verified as v
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'report'
WEB=OUT/'stand';WEB.mkdir(exist_ok=True)
SITE=WEB/'gorod-control'
shutil.copytree(OUT/'baseline',SITE,dirs_exist_ok=True)
raw=json.loads((OUT/'real_posts.json').read_text(encoding='utf-8'))
clock=datetime.fromisoformat('2026-10-18T00:20:00+03:00')
feed=v.build_feed(raw,clock)
original=json.loads((SITE/'data/water.json').read_text(encoding='utf-8'))
feed['sources']=original['sources']
(SITE/'data/water.json').write_text(json.dumps(feed,ensure_ascii=False),encoding='utf-8')
geo=json.loads((SITE/'data/map-geometry.json').read_text(encoding='utf-8'))
base_events={e['id']:e for e in original['events']}
for event in feed['events']:
    if event['id'] not in geo.get('events',{}):continue
    old=base_events.get(event['id'])
    if not old or v.coverage_key(old['affected'])!=v.coverage_key(event['affected']):continue
    entry=geo['events'][event['id']]
    # Reuse geometry only for canonically identical road types, names and houses.
    entry['affectedKey']=json.dumps([[a['street'],a.get('houses',[])] for a in event['affected']],ensure_ascii=False,separators=(',',':'))
    entry['fullText']=event['text']
(SITE/'data/map-geometry.json').write_text(json.dumps(geo,ensure_ascii=False),encoding='utf-8')
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(WEB)))
threading.Thread(target=server.serve_forever,daemon=True).start()
URL='http://127.0.0.1:'+str(server.server_port)+'/gorod-control/'
checks=[]
def check(condition,label):
    if not condition:raise AssertionError(label)
    checks.append(label)
try:
    with sync_playwright() as p:
        browser=p.chromium.launch()
        ctx=browser.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True,service_workers='block')
        def route(r):
            if r.request.url.startswith('http://127.0.0.1:'):r.continue_()
            else:r.abort()
        ctx.route('**/*',route)
        page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.clock.install(time=clock)
        home={'lat':47.70,'lon':40.20,'street':'ул. Советская','house':'11','label':'ТЕСТ: ул. Советская, 11, Шахты','method':'address'}
        page.add_init_script('localStorage.setItem("gorod_control_home_v1",'+json.dumps(json.dumps(home,ensure_ascii=False))+');')
        page.goto(URL,wait_until='domcontentloaded')
        page.wait_for_function('window.CityMapV07 && CityMapV07.inspect().allIds.length===1',timeout=15000)
        saved=page.evaluate('localStorage.getItem("gorod_control_home_v1")')
        check(page.evaluate('CityMapV07.inspect().ids.length')==0,'Unrelated synthetic address has no water match')
        page.locator('#cityAllButton').click()
        page.wait_for_function('CityMapV07.inspect().mapped===1',timeout=10000)
        check(page.evaluate('CityMapV07.inspect().allIds')==['water-oursv-1591'],'Historical samples excluded and duplicate reprints merged')
        check(page.locator('.cm-marker').count()==5,'Five existing public street markers preserved without fabricated coordinates')
        check(page.evaluate('localStorage.getItem("gorod_control_home_v1")')==saved,'City browsing preserves saved address')
        page.locator('[data-event-id="water-oursv-1591"] .cm-detail-button').click()
        page.wait_for_function('document.querySelector("#cityEventDetail").open')
        details=page.locator('#cityEventBody').inner_text()
        check('18:00' in details,'Published repair estimate visible')
        check('Подтверждения восстановления нет' in details,'Expired repair estimate does not mean repaired')
        check(page.locator('#cityEventBody a[href="https://rovodokanal.ru/emergency-alerts/1591"]').count()==1,'Official document link preserved')
        check('пер Шишкина' in details and 'Кадровая' in details,'Affected roads shown in details')
        check(not errors,'No JavaScript runtime errors')
        page.screenshot(path=str(OUT/'candidate-detail-test.png'))
        ctx.close();browser.close()
finally:
    server.shutdown()
    # Test-site copy is not published or shipped as a replacement application.
    shutil.rmtree(WEB,ignore_errors=True)
(OUT/'browser-checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'testClock':clock.isoformat(),'limitations':'Isolated Chromium, fixed replay clock, blocked external requests and a synthetic control point. Not phone GPS, live push or full map-tile testing.'},ensure_ascii=False,indent=2),encoding='utf-8')
print('CANDIDATE_BROWSER_CHECKS_PASSED',len(checks))
