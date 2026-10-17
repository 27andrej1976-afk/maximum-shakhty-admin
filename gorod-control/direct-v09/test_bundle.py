import json,threading,functools,http.server,re,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright
D=Path(__file__).parent;ROOT=D.parent
ASSETS=ROOT/'android/app/src/main/assets/web'
OUT=Path('direct-report');OUT.mkdir(exist_ok=True)
feed=json.loads((D/'feed.json').read_text());geo=json.loads((D/'map-geometry.json').read_text())
checks=[]
def check(b,s):
 if not b:raise AssertionError(s)
 checks.append(s)
html=(ASSETS/'index.html').read_text()
for i,m in enumerate(re.finditer(r'<script(?:\s+[^>]*)?>(.*?)</script>',html,re.S)):
 if not m[1].strip():continue
 f=OUT/('inline-'+str(i)+'.js');f.write_text(m[1]);subprocess.run(['node','--check',str(f)],check=True)
server=http.server.ThreadingHTTPServer(('127.0.0.1',8767),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ASSETS)))
threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
 browser=p.chromium.launch()
 ctx=browser.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True)
 page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/direct-v09/feed.json*',lambda r:r.fulfill(content_type='application/json',body=json.dumps(feed,ensure_ascii=False)))
 page.route('**/direct-v09/map-geometry.json*',lambda r:r.fulfill(content_type='application/json',body=json.dumps(geo,ensure_ascii=False)))
 page.goto('http://127.0.0.1:8767/',wait_until='domcontentloaded')
 page.wait_for_selector('#cityAllButton')
 page.wait_for_function('window.CityMapV07 && CityMapV07.inspect().allIds.length>0',timeout=20000)
 check(page.locator('.version').inner_text()=='АПК 0.9 · ТЕСТ','correct APK UI version')
 check(page.locator('img.city-coat').evaluate('(e)=>e.complete&&e.naturalWidth>0'),'bundled official crest loads')
 check('УРСВ' in page.locator('#directStatus').inner_text(),'native direct water status visible before success')
 page.locator('#cityAllButton').click();page.wait_for_function('CityMapV07.inspect().mode==="city"')
 power=[e for e in feed['events'] if e.get('sourceId')=='power_direct']
 check(len(power)>0,'direct official electricity events exist, not artificial scenarios')
 first=power[0]
 check(first['id'] in page.evaluate('CityMapV07.inspect().ids'),'direct power event enters citywide map/list')
 page.locator('[data-event-id="'+first['id']+'"] .cm-detail-button').click()
 check(page.locator('#cityEventDetail').evaluate('(e)=>e.open'),'real direct notice detail opens')
 body=page.locator('#cityEventBody').inner_text()
 check('Донэнерго' in body,'detail identifies the primary company')
 check(page.locator('#cityEventBody a[href="https://donenergo.ru/grafik-otklyucheniy/61/1/"]').count()>0,'detail links to original schedule')
 check('Опубликовано' in body and 'не указано' in body.lower() or first.get('publishedAt') is None,'missing publication timestamp not fabricated')
 page.screenshot(path=str(OUT/'mobile-direct-detail.png'))
 page.locator('#cityEventClose').click()
 uncertain=[e for e in power if e.get('requiresReview')]
 if uncertain:
  page.locator('[data-event-id="'+uncertain[0]['id']+'"] .cm-detail-button').click()
  check('Требуется уточнение' in page.locator('#cityEventBody').inner_text(),'source typo is visibly marked, not corrected by guess')
  page.locator('#cityEventClose').click()
 check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'no horizontal overflow on phone')
 page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/'mobile-direct-top.png'))
 page.locator('.map-card').screenshot(path=str(OUT/'mobile-direct-city.png'))
 # Simulate actual native callback with a denied official source. Never changes published feed.
 denied=json.loads(json.dumps(feed));denied['sources'].append({'id':'ursv_device','status':'error','httpStatus':403,'checkedAt':datetime.now(timezone.utc).isoformat(),'note':'HTTP 403 — доступ из этой сети ограничен'})
 page.evaluate('(data)=>window.CityControlNativeFeed(data)',denied)
 check('не подтверждено' in page.locator('#directStatus').inner_text(),'blocked direct source is not green or claimed connected')
 check('403' in page.locator('#directStatus').inner_text(),'visible native-source diagnosis')
 check(first['id'] in page.evaluate('CityMapV07.inspect().allIds'),'one failed source cannot hide available primary power data')
 check(not errors,'no JavaScript runtime errors: '+str(errors))
 browser.close()
server.shutdown()
(OUT/'browser-checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'runtime':'Chromium mobile viewport; not physical Android GPS test'},ensure_ascii=False,indent=2))
print('BUNDLED MOBILE CHECKS PASSED',len(checks))
