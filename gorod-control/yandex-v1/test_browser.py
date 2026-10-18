"""Deterministic browser smoke tests for isolated Yandex beta, with stub API not a real key."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from threading import Thread
from playwright.sync_api import sync_playwright
import json
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=HERE/'test-report';OUT.mkdir(exist_ok=True)
FAKE_JS=r"""
(function(){
 const make=(name)=>class {
  constructor(...args){this.name=name;this.args=args;this.children=[];this.element={setAttribute(){}};}
  addChild(x){this.children.push(x);return this;}
  removeChild(x){this.children=this.children.filter(t=>t!==x);return this;}
  setLocation(x){this.location=x;}
  update(x){this.props=x;}
 };
 const Map=make('YMap');
 window.ymaps3={
  ready:Promise.resolve(),YMap:Map,
  YMapDefaultSchemeLayer:make('scheme'),YMapDefaultFeaturesLayer:make('features'),
  YMapMarker:make('marker'),YMapFeature:make('feature'),YMapListener:make('listener')
 };
})();
"""
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*_): pass

srv=ThreadingHTTPServer(('127.0.0.1',18767),lambda *args,**kwargs:Handler(*args,directory=str(ROOT),**kwargs))
Thread(target=srv.serve_forever,daemon=True).start()
url='http://127.0.0.1:18767/gorod-control/yandex-v1/'
results={}
with sync_playwright() as p:
    browser=p.chromium.launch()
    ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page=ctx.new_page()
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.goto(url,wait_until='domcontentloaded')
    page.wait_for_selector('#cityAllButton',timeout=12000)
    assert page.locator('img.city-coat').evaluate('(e)=>e.complete&&e.naturalWidth>0')
    assert page.locator('.ym-city-key').count()==1
    assert page.evaluate('CityYandexV1.inspect().active') is False
    page.locator('#cityAllButton').click()
    assert page.evaluate('CityMapV07.inspect().mode')=='city'
    results['osmFallbackWithoutKey']='pass'
    page.screenshot(path=str(OUT/'preview-osm-mobile.png'),full_page=False)
    page.close();ctx.close()
    ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    page=ctx.new_page();errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.add_init_script("""localStorage.setItem('city-control-yandex-jsapi-v1','ONLY-TEST-KEY-DO-NOT-USE-IN-PRODUCTION-000001');""")
    page.route('https://api-maps.yandex.ru/v3/**',lambda route:route.fulfill(status=200,content_type='application/javascript',body=FAKE_JS))
    page.goto(url,wait_until='domcontentloaded')
    page.wait_for_function("window.CityYandexV1 && CityYandexV1.inspect().active",timeout=13000)
    page.wait_for_selector('#cityAllButton')
    assert page.locator('.ym-city-status').inner_text().startswith('Яндекс Карты активны')
    assert page.evaluate("typeof CityMapV07.getMap().setView")=='function'
    assert page.evaluate("CityMapV07.getMap().inner.children.length")>=3
    page.locator('#cityAllButton').click()
    assert page.evaluate("CityMapV07.inspect().mode")=='city'
    page.locator('#cityNearButton').click()
    assert page.evaluate("CityMapV07.inspect().mode")=='near'
    assert not errors,errors[:5]
    results['mockYandexSDKInteraction']='pass'
    page.screenshot(path=str(OUT/'preview-yandex-mock-mobile.png'),full_page=False)
    page.close();ctx.close()
    browser.close()
srv.shutdown()
(OUT/'checks.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
print('BETA YANDEX CHECKS PASSED:',results)
