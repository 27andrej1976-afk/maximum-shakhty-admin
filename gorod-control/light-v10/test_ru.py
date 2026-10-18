"""Verify OpenFreeMap labels use Cyrillic-preferred vector expressions on actual style."""
import json,functools,http.server,threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'light-map-ru-test-report';OUT.mkdir(exist_ok=True)
server=http.server.ThreadingHTTPServer(('127.0.0.1',18866),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as playwright:
 browser=playwright.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
 page=browser.new_page(viewport={'width':393,'height':852},is_mobile=True,has_touch=True)
 failures=[]
 page.on('pageerror',lambda e:failures.append(str(e)))
 page.goto('http://127.0.0.1:18866/gorod-control/',wait_until='domcontentloaded')
 page.wait_for_function("CityMapV07.inspect().basemap==='bright' && !!CityMapV07.getVectorMap()",timeout=30000)
 info=page.evaluate("""() => {
   const gl=CityMapV07.getVectorMap();
   const layers=gl.getStyle().layers.filter(l=>l.type==='symbol'&&l.layout?.['text-field']!=null);
   return {localized:layers.filter(l=>JSON.stringify(l.layout['text-field']).includes('name:ru')).map(l=>l.id),
     allLabels:layers.length,credits:document.querySelector('.leaflet-control-attribution')?.textContent||''};
 }""")
 assert len(info['localized'])>=4,info
 assert 'OpenMapTiles' in info['credits'],info
 assert page.locator('img.city-coat').evaluate("e=>e.complete && e.naturalWidth>0")
 page.locator('#cityAllButton').click()
 assert page.evaluate("CityMapV07.inspect().mode")=='city'
 assert not failures,failures
 page.screenshot(path=str(OUT/'bright-russian-mobile.png'),full_page=True)
 (OUT/'checks.json').write_text(json.dumps({'russianLabelLayers':info['localized'],'symbolLayers':info['allLabels'],'credits':info['credits'],'pageErrors':failures},ensure_ascii=False,indent=2))
 print('BRIGHT RUSSIAN MAP VERIFIED',len(info['localized']),'localized layers from',info['allLabels'],flush=True)
 browser.close()
server.shutdown()
