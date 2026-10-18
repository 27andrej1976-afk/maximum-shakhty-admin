"""Browser regression: verify raster/vector pixels and Leaflet marker positions follow pans.
Run from repository root: python gorod-control/map-v07/test_pan_browser.py
Requires: pip install playwright && playwright install chromium
No Android packages are assembled and no production files are modified.
"""
from __future__ import annotations
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
import json

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO.parent
class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *args):
        pass

def snapshot(page):
    return page.evaluate("""() => {
      const map = CityMapV07.getMap(), gl = CityMapV07.getVectorMap();
      if (!map || !gl) throw new Error('Vector style not active');
      const c = map.getCenter(), v = gl.getCenter(), spot = L.latLng(47.7086,40.2146);
      const p = map.latLngToContainerPoint(spot), q = gl.project([spot.lng,spot.lat]);
      const a = map.getContainer().getBoundingClientRect(),
            b = gl.getContainer().getBoundingClientRect();
      return {
        center: [c.lat,c.lng], glCenter: [v.lat,v.lng],
        pixelDelta: [Math.abs(a.left+p.x-b.left-q.x),Math.abs(a.top+p.y-b.top-q.y)],
        styleLoaded: gl.isStyleLoaded()
      };
    }""")

def test(page, name, url):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function("() => !!window.CityMapV07?.getMap?.()", timeout=25000)
    page.wait_for_function("() => window.CityMapV07?.getVectorMap?.()?.isStyleLoaded?.() === true", timeout=35000)
    page.locator("#map").scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    first = snapshot(page)
    box = page.locator("#map").bounding_box()
    assert box, name + ": no visible map"
    x = box["x"] + box["width"] * 0.58
    y = box["y"] + box["height"] * 0.48
    page.mouse.move(x,y)
    page.mouse.down()
    page.mouse.move(x - min(100,box["width"]*.25),y + 65,steps=12)
    page.mouse.up()
    page.wait_for_timeout(1000)
    after = snapshot(page)
    center_shift = max(abs(a-b) for a,b in zip(first["center"],after["center"]))
    gl_shift = max(abs(a-b) for a,b in zip(first["glCenter"],after["glCenter"]))
    distance = max(abs(a-b) for a,b in zip(after["center"],after["glCenter"]))
    print(json.dumps({"variant":name, "before":first, "after":after,
                      "leafletShift":center_shift, "vectorShift":gl_shift,
                      "syncErrorDegrees":distance},ensure_ascii=False),flush=True)
    assert center_shift > .00025, name + ": Leaflet did not respond to the drag"
    assert gl_shift > .00025, name + ": GL basemap did not move after Leaflet drag"
    assert distance < .0001, name + ": Leaflet and vector GL centers disagree"
    assert max(after["pixelDelta"]) < 5, name + ": GL basemap and Leaflet markers are visually offset"
    assert max(first["pixelDelta"]) < 5, name + ": initial GL/Leaflet pixel alignment broken"

def main():
    httpd = ThreadingHTTPServer(("127.0.0.1",0),QuietHandler)
    Thread(target=httpd.serve_forever,daemon=True).start()
    base=f"http://127.0.0.1:{httpd.server_address[1]}/gorod-control/"
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=[
            "--no-sandbox","--enable-webgl","--use-gl=angle",
            "--use-angle=swiftshader","--enable-unsafe-swiftshader",
            "--disable-dev-shm-usage"
        ])
        try:
            for name, suffix in [("Classic","index.html"),("Compact","compact-v11/index.html")]:
                context=browser.new_context(viewport={"width":393,"height":852},
                                            is_mobile=True,has_touch=True,device_scale_factor=1)
                page=context.new_page()
                try:
                    test(page,name,base+suffix)
                except Exception:
                    path=ROOT/f"map-pan-failure-{name.lower()}.png"
                    try: page.screenshot(path=str(path),full_page=True,timeout=12000)
                    except Exception: pass
                    raise
                finally:
                    context.close()
        finally:
            browser.close()
            httpd.shutdown()
    print("PASS Classic + Compact: vector and Leaflet map pan together")

if __name__ == "__main__":
    main()
