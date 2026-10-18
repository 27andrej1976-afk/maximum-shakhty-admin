"""Browser UI checks: no bottom branding, accessible copyright near map, no country flags."""
import json,threading,functools,http.server,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'clean-map-test-report'
OUT.mkdir(exist_ok=True)
NOW=datetime.now(timezone.utc)
def moment(h=0):return (NOW+timedelta(hours=h)).isoformat()
fixture={
 'schema':2,'checkedAt':moment(),'sources':[
    {'id':'repost_rostov','status':'ok','lastPostAt':moment(-1),'posts':1,'url':'https://newsrostov.ru/rss.xml'}],
 'events':[{'id':'test-map-clean','category':'water','kind':'emergency','status':'active',
    'origin':'verified_repost','source':'УРСВ — перепечатка',
    'title':'ТЕСТ: авария воды','description':'Проверка интерактивного окна. Не реальное происшествие.',
    'start':moment(-1),'end':moment(4),'publishedAt':moment(-1),
    'url':'https://newsrostov.ru/society/test-only','officialUrl':'https://rovodokanal.ru/emergency-alerts/999999',
    'point':{'lat':47.7086,'lon':40.2146},'affected':[{'street':'ул Советская','houses':['11']}]}]
}
home={'lat':47.7086,'lon':40.2146,'street':'ул Советская','house':'11','label':'Тестовая точка, Шахты','method':'address'}
server=http.server.ThreadingHTTPServer(('127.0.0.1',18772),
    functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
checks=[]
def check(test,title):
 if not test:raise AssertionError(title)
 checks.append(title);print('CLEAN CHECK',title,flush=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 for scenario in ('bright','fallback'):
  ctx=browser.new_context(viewport={'width':393,'height':852},is_mobile=True,has_touch=True)
  page=ctx.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.add_init_script('localStorage.setItem("gorod_control_home_v1",'+json.dumps(json.dumps(home,ensure_ascii=False))+');')
  page.route('**/data/water.json*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(fixture,ensure_ascii=False)))
  if scenario=='fallback':
   page.route('**/light-v10/vendor/maplibre-gl.js',lambda r:r.abort())
  page.goto('http://127.0.0.1:18772/gorod-control/',wait_until='domcontentloaded')
  page.wait_for_selector('#cityAllButton',timeout=18000)
  page.wait_for_function('CityMapV07.inspect().allIds.includes("test-map-clean")',timeout=18000)
  credit=page.locator('.cm-map-source-credit')
  check(credit.is_visible(),scenario+': required map copyright visible next to heading')
  check(credit.locator('a[href="https://www.openstreetmap.org/copyright"]').count()==1,
        scenario+': visible original OpenStreetMap copyright link')
  check(page.locator('#map .leaflet-control-attribution').count()==0,
        scenario+': no Leaflet/OSM footer on map')
  check('Leaflet' not in credit.inner_text(),scenario+': no Leaflet word in displayed credit')
  if scenario=='bright':
   page.wait_for_function("CityMapV07.inspect().basemap==='bright'",timeout=30000)
   check(credit.locator('#mapCreditTiles').is_visible(), 'bright: OpenMapTiles copyright visibly credited')
   flags=page.evaluate("""() => {
     const gl=CityMapV07.getVectorMap();
     gl.addLayer({id:'test-country-flag',type:'symbol',source:'openmaptiles',
       'source-layer':'place',layout:{'icon-image':'flag_test'}});
     const removed=CityMapV07.hideCountryFlags(gl);
     const hidden=gl.getLayoutProperty('test-country-flag','visibility')==='none';
     gl.removeLayer('test-country-flag');
     return {removed,hidden};
   }""")
   check(flags['hidden'] and flags['removed']>=1,'bright: country flag icon layer is hidden')
   check(page.locator('#map canvas.maplibregl-canvas').count()>0,'bright: vector renderer visible')
  else:
   check(not credit.locator('#mapCreditTiles').is_visible(),'fallback: only OSM credit shown')
   check(page.evaluate("CityMapV07.inspect().basemap")=='fallback',
        'fallback: keyless classic map still available')
  for old_footer in ['#map .maplibregl-ctrl-attrib','#map .leaflet-control-attribution']:
   nodes=page.locator(old_footer)
   if nodes.count():
    check(nodes.evaluate_all("els=>els.every(el=>getComputedStyle(el).display==='none')"),
          scenario+': '+old_footer+' is hidden in map because credit moved above')
  page.locator('#cityAllButton').click()
  check(page.evaluate("CityMapV07.inspect().mode==='city'"),scenario+': citywide mode works')
  events=page.locator('article[data-event-id="test-map-clean"]')
  check(events.count()==1,scenario+': real-format map test card retained')
  events.locator('button.cm-detail-button').click()
  check('ТЕСТ: авария воды' in page.locator('#cityEventTitle').inner_text(),
        scenario+': existing incident detail dialog works')
  page.locator('#cityEventClose').click()
  check(page.locator('img.city-coat').evaluate('el=>el.complete&&el.naturalWidth>0'),scenario+': Shakhty coat retained')
  page.screenshot(path=str(OUT/(scenario+'-without-footer-mobile.png')),full_page=True)
  check(not errors,scenario+': no Javascript errors: '+str(errors[:2]))
  ctx.close()
 browser.close()
server.shutdown()
(OUT/'checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
print('CLEAN MAP CHECKS PASSED',len(checks),flush=True)
