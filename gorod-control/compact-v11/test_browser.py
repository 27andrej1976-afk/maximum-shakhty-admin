"""Interactive compact v1.1 browser integration, with purely synthetic test events."""
import json,threading,functools,http.server
from pathlib import Path
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'compact-browser-report';OUT.mkdir(exist_ok=True)
now=datetime.now(timezone.utc)
def date(hours=0):return (now+timedelta(hours=hours)).isoformat()
home={'lat':47.7086,'lon':40.2146,'street':'ул Советская','house':'11',
      'label':'ул. Советская, 11, Шахты','method':'address'}
event={'id':'fixture-compact-water','category':'water','kind':'emergency',
       'status':'active','sourceId':'repost_rostov','origin':'verified_repost',
       'source':'УРСВ (проверочная фикстура)','title':'ТЕСТ: сообщение водоканала',
       'description':'Только тест, не реальная авария.',
       'start':date(-1),'end':date(4),'publishedAt':date(-1),
       'url':'https://newsrostov.ru/only-test','officialUrl':'https://rovodokanal.ru/emergency-alerts/1591',
       'point':{'lat':47.7086,'lon':40.2146},
       'affected':[{'street':'ул Советская','houses':['11']}]}
feed={'schema':2,'checkedAt':date(),'sources':[{
 'id':'repost_rostov','status':'ok','lastPostAt':date(-1),'posts':1,'checkedAt':date(),
 'url':'https://newsrostov.ru/rss.xml'}],'events':[event]}
server=http.server.ThreadingHTTPServer(('127.0.0.1',18877),
    functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
checks=[]
def check(yes,desc):
 if not yes:raise AssertionError(desc)
 checks.append(desc);print('COMPACT CHECK:',desc,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 for viewport,tag in [({'width':393,'height':852},'mobile'),({'width':710,'height':1000},'tablet')]:
  context=browser.new_context(viewport=viewport,is_mobile=(tag=='mobile'),has_touch=(tag=='mobile'))
  page=context.new_page();jsErrors=[]
  page.on('pageerror',lambda err:jsErrors.append(str(err)))
  page.add_init_script('localStorage.setItem("gorod_control_home_v1",'+json.dumps(json.dumps(home,ensure_ascii=False))+');')
  page.route('**/data/water.json*',lambda route:route.fulfill(status=200,content_type='application/json',
   body=json.dumps(feed,ensure_ascii=False)))
  page.goto('http://127.0.0.1:18877/gorod-control/compact-v11/',wait_until='domcontentloaded')
  page.wait_for_selector('#compactNav',timeout=25000)
  page.wait_for_function("CityMapV07.inspect().allIds.includes('fixture-compact-water')",timeout=25000)
  page.wait_for_function("document.querySelector('#compactAllCount').textContent==='1'",timeout=12000)
  check(page.locator('.compact-metrics').is_visible(),tag+': compact live metrics shown')
  check(page.locator('#compactAllCount').inner_text()=='1',tag+': actual notice count, no fake totals')
  check(page.locator('#addressValue').inner_text().startswith('ул. Советская'),tag+': existing local home survives')
  check(page.locator('img.city-coat').evaluate('(img)=>img.complete && img.naturalWidth>0'),tag+': original Shakhty coat kept')
  check(page.locator('#compactCityFold').count()==1 and not page.locator('#compactCityFold').evaluate('(e)=>e.open'),
        tag+': long city event list collapsed by default')
  check(page.locator('#compactLocalFold').count()==1 and not page.locator('#compactLocalFold').evaluate('(e)=>e.open'),
        tag+': detailed local notices collapsed by default')
  check(page.locator('#compactSourcesFold').count()==1 and not page.locator('#compactSourcesFold').evaluate('(e)=>e.open'),
        tag+': source list collapsed by default')
  check(page.locator('#map .leaflet-control-attribution').count()==0,tag+': no Leaflet attribution footer returns')
  page.locator('#cityAllButton').click()
  check(page.evaluate("CityMapV07.inspect().mode")=='city',tag+': citywide map button works')
  page.locator('#compactCityFold summary').click()
  check(page.locator('#cityMapEvents [data-event-id="fixture-compact-water"]').count()==1,
       tag+': genuine event still appears when expanded')
  page.locator('#cityMapEvents [data-event-id="fixture-compact-water"] button.cm-detail-button').click()
  check('ТЕСТ: сообщение водоканала' in page.locator('#cityEventTitle').inner_text(),
       tag+': event detail opens with preserved source info')
  page.locator('#cityEventClose').click()
  page.locator('#compactNav button').nth(2).click()
  check(page.locator('#compactLocalFold').evaluate('(e)=>e.open'),
       tag+': bottom notifications nav opens correct content')
  page.locator('#compactNav button').nth(3).click()
  check(page.locator('#compactSourcesFold').evaluate('(e)=>e.open'),
       tag+': bottom more nav opens verified publications')
  check(page.locator('#sourcesGrid .source').count()>2,tag+': source link cards remain functional')
  check(page.locator('#checkButton').count()==1 and page.locator('#geoButton').count()==1,
       tag+': existing refresh and GPS controls preserved')
  check(not jsErrors,tag+': no uncaught JS error '+str(jsErrors[:2]))
  page.screenshot(path=str(OUT/(tag+'-compact-preview.png')),full_page=True)
  context.close()
 browser.close()
server.shutdown()
(OUT/'checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2))
print('COMPACT BROWSER CHECKS PASSED',len(checks),flush=True)
