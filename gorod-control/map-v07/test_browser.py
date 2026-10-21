"""Browser integration tests using isolated synthetic routes; test notices never enter published data."""
import json,time,threading,functools,http.server,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'city-map-test-report'
REPORT.mkdir(exist_ok=True)
HOME={'lat':47.7086,'lon':40.2146,'street':'ул. Советская','house':'11','label':'ул. Советская, 11, Шахты','method':'address'}
now=datetime.now(timezone.utc)
def stamp(hours=0):return (now+timedelta(hours=hours)).isoformat()
far={'id':'test-far-water','category':'water','kind':'emergency','status':'active','origin':'verified_repost',
 'source':'ГУП РО УРСВ — перепечатка','title':'ТЕСТ: ремонт на другом конце города','description':'Учебная фикстура. Не настоящее происшествие.',
 'officialUrl':'https://rovodokanal.ru/emergency-alerts/999001','url':'https://newsrostov.ru/test-only',
 'start':stamp(-1),'end':stamp(2),'publishedAt':stamp(-1),'point':None,
 'affected':[{'street':'пер. Донской','houses':['78','80']}]}
unknown={'id':'test-no-map','category':'power','kind':'emergency','status':'active','origin':'attributed_repost',
 'source':'Донэнерго — перепечатка','title':'ТЕСТ: электричество — место уточняется',
 'description':'Тестовый источник не называет время восстановления.', 'url':'https://newsrostov.ru/test-only-2',
 'start':stamp(-1),'end':None,'publishedAt':stamp(-1),'point':None,'affected':[{'street':'ул. Учебная','houses':[]}]}
forecast={'id':'test-forecast','category':'mchs','sourceId':'mchs','kind':'warning','status':'active','scope':'city','priority':'info',
 'source':'МЧС Ростовской области','title':'ТЕСТ: городской прогноз','description':'Это учебный прогноз для проверки территориальных карточек.',
 'url':'https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/test-only',
 'start':stamp(1),'end':stamp(25),'publishedAt':stamp(-1),'affected':[],'point':None}
malicious={**far,'id':'test-xss','title':'<img src=x onerror=window.__injected=1>','end':None,'affected':[{'street':'пер. Другой','houses':[]}],
 'description':'<script>window.__injected=1</script>'}
expired={**far,'id':'test-resolved','status':'resolved'}
source_ids=['city','repost_rostov','repost_don','power_repost_rostov','power_repost_don','mchs']
feed={'schema':2,'checkedAt':stamp(),'sources':[{'id':i,'status':'ok','posts':5,'lastPostAt':stamp(-1)} for i in source_ids],
 'events':[far,unknown,forecast,malicious,expired]}
geometry={'schema':1,'events':{far['id']:{'features':[{'lat':47.77,'lon':40.26,'role':'street','label':'пер. Донской',
 'lines':[[[47.769,40.258],[47.77,40.26],[47.771,40.262]]]}],
 'affectedKey':json.dumps([[a['street'],a['houses']] for a in far['affected']],ensure_ascii=False,separators=(',',':')),
 'fullText':'Полный тестовый текст объявления; не реальное происшествие.'}}}
handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT))
server=http.server.ThreadingHTTPServer(('127.0.0.1',8765),handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
URL='http://127.0.0.1:8765/gorod-control/compact-v11/'
checks=[]
def check(value,label):
    if not value:raise AssertionError(label)
    checks.append(label)

def run():
  with sync_playwright() as pw:
    browser=pw.chromium.launch()
    context=browser.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True,device_scale_factor=1)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script('localStorage.setItem("gorod_control_home_v1",'+json.dumps(json.dumps(HOME,ensure_ascii=False))+');')
    page.route('**/data/water.json*',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(feed,ensure_ascii=False)))
    page.route('**/data/map-geometry.json*',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(geometry,ensure_ascii=False)))
    page.goto(URL,wait_until='domcontentloaded');page.wait_for_function('window.CityMapV07 && CityMapV07.inspect().allIds.length===4')
    page.wait_for_function('document.querySelector("img.city-coat").naturalWidth===165')
    saved=page.evaluate('localStorage.getItem("gorod_control_home_v1")')
    home_summary=page.locator('#overviewCard').inner_text()
    check(page.evaluate('CityMapV07.inspect().mode')=='near','Starts in the saved-home view')
    check('test-far-water' not in page.evaluate('CityMapV07.inspect().ids'),'Remote unrelated repair hidden near home')
    page.evaluate('CityMapV07.getMap().setZoom(12,{animate:false})')
    check(page.evaluate('CityMapV07.inspect().mode')=='near','Zooming out preserves selected nearby mode')
    page.locator('#cityAllButton').click()
    check('test-far-water' in page.evaluate('CityMapV07.inspect().ids'),'City button reveals the city incident')
    check('test-resolved' not in page.evaluate('CityMapV07.inspect().ids'),'Resolved notices do not masquerade as current incidents')
    check(page.locator('#overviewCard').inner_text()==home_summary,'City map does not change the personal home summary')
    check(page.evaluate('localStorage.getItem("gorod_control_home_v1")')==saved,'Browsing city never changes the saved home')
    page.evaluate('CityMapV07.getMap().setView([47.7086,40.2146],14,{animate:false})')
    check(page.evaluate('CityMapV07.inspect().mode')=='city','Zooming back to home preserves city mode')
    check('test-far-water' in page.evaluate('CityMapV07.inspect().ids'),'City event survives zoom near home')
    page.locator('#cityAllButton').click();page.wait_for_function('CityMapV07.inspect().mode==="city"')
    page.evaluate('CityMapV07.getMap().setZoom(15,{animate:false})')
    check(page.evaluate('CityMapV07.inspect().mode')=='city','Manual whole-city selection persists while inspecting an area')
    page.locator('#cityAllButton').click()
    page.wait_for_function('CityMapV07.inspect().mapped===1')
    check(page.locator('.cm-marker').count()==1,'Only an actual mapped street gets a marker, not forecasts or unlocated events')
    marker=page.locator('.cm-marker').first;marker.scroll_into_view_if_needed();marker.click()
    popup=page.locator('.cm-popup');popup.wait_for()
    check('Ожидаемое завершение' in popup.inner_text(),'Marker tap immediately shows the repair timing')
    popup.locator('button').click()
    check(page.locator('#cityEventDetail').evaluate('(el)=>el.open'),'Marker details open the accessible event sheet')
    check('78, 80' in page.locator('#cityEventBody').inner_text(),'Exact affected houses remain visible')
    check('Полный тестовый текст' in page.locator('#cityEventBody').inner_text(),'Full source text is present in the detail sheet')
    check('Точное место поломки не установлено' in page.locator('#cityEventBody').inner_text(),'Street geometry never claims to be exact fault coordinates')
    page.locator('#cityEventClose').click()
    page.locator('#compactCityFold').evaluate('(el)=>el.open=true')
    page.locator('[data-event-id="test-no-map"] .cm-detail-button').click()
    check('Срок не опубликован' in page.locator('#cityEventBody').inner_text(),'Missing restoration time is explicitly unknown')
    check('Случайная точка' in page.locator('#cityEventBody').inner_text(),'Unlocated incident is inspectable without a fabricated pin')
    page.locator('#cityEventClose').click()
    page.locator('#compactCityFold').evaluate('(el)=>el.open=true')
    page.locator('[data-event-id="test-xss"] .cm-detail-button').click()
    check(page.evaluate('window.__injected') is None,'Source HTML cannot inject scripts into a detail sheet')
    page.locator('#cityEventClose').click()
    page.locator('.cm-filters [data-category="mchs"]').click()
    check(page.evaluate('CityMapV07.inspect().ids')==['test-forecast'],'Category filter isolates city forecasts')
    check(page.locator('.cm-marker').count()==0,'Citywide forecast is not drawn as an arbitrary emergency point')
    page.locator('.cm-filters [data-category="all"]').click()
    page.evaluate('CityMapV07.getMap().setView([47.746,40.228],13,{animate:false})')
    position=page.evaluate('({center:CityMapV07.getMap().getCenter(),zoom:CityMapV07.getMap().getZoom()})')
    page.evaluate('CityMapV07.refresh()')
    check(position==page.evaluate('({center:CityMapV07.getMap().getCenter(),zoom:CityMapV07.getMap().getZoom()})'),'Refresh preserves city zoom and map position')
    check(page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),'Mobile layout has no horizontal overflow')
    check(not errors,'No browser JavaScript errors: '+str(errors))
    page.screenshot(path=str(REPORT/'mobile-test-scenarios.png'),full_page=True)
    page.locator('#compactCityFold').evaluate('(el)=>el.open=true')
    page.locator('[data-event-id="test-far-water"] .cm-detail-button').click()
    page.screenshot(path=str(REPORT/'mobile-detail-test.png'))
    context.close()
    # Verify real generated feed and crest, with no private saved home and no mocked incidents.
    live=browser.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True)
    livepage=live.new_page();livepage.goto(URL,wait_until='domcontentloaded')
    livepage.wait_for_selector('#cityAllButton');livepage.locator('#cityAllButton').click();livepage.wait_for_timeout(2000)
    check(livepage.locator('img.city-coat').evaluate('(el)=>el.complete&&el.naturalWidth===165'),'Coat of arms loads from a bundled asset')
    check(livepage.evaluate('CityMapV07.inspect().mode')=='city','City overview works without GPS or a saved home')
    livepage.wait_for_timeout(3000)
    livepage.evaluate('window.scrollTo(0,0)')
    livepage.screenshot(path=str(REPORT/'mobile-live-top.png'))
    livepage.locator('.map-card').screenshot(path=str(REPORT/'mobile-live-city.png'))
    live.close()
    desktop=browser.new_page(viewport={'width':1366,'height':900})
    desktop.goto(URL,wait_until='domcontentloaded');desktop.wait_for_selector('#cityAllButton');desktop.locator('#cityAllButton').click();desktop.wait_for_timeout(4800)
    check(desktop.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),'Desktop layout has no horizontal overflow')
    desktop.screenshot(path=str(REPORT/'desktop-live-city.png'),full_page=True)
    browser.close()
  (REPORT/'checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
  print('CITY MAP BROWSER CHECKS PASSED:',len(checks))
try:run()
finally:server.shutdown()
