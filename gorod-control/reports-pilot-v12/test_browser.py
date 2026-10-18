"""Public-source routing and delivery honesty smoke tests. Nothing is sent to any authority."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from threading import Thread
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'civic-routing-test-report';OUT.mkdir(exist_ok=True)
srv=ThreadingHTTPServer(('127.0.0.1',18791),lambda *a,**kw:SimpleHTTPRequestHandler(*a,directory=str(ROOT),**kw))
Thread(target=srv.serve_forever,daemon=True).start()
passed=[]
def check(ok,s):
 if not ok:raise AssertionError(s)
 passed.append(s);print('ROUTING_CHECK',s,flush=True)
with sync_playwright() as p:
 browser=p.chromium.launch()
 ctx=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
 page=ctx.new_page()
 pageErrors=[];outbound=[]
 page.on('pageerror',lambda e:pageErrors.append(str(e)))
 page.on('request',lambda request:outbound.append(request.url) if not request.url.startswith('http://127.0.0.1:18791') else None)
 page.goto('http://127.0.0.1:18791/gorod-control/reports-pilot-v12/',wait_until='domcontentloaded')
 page.wait_for_function('window.CivicReportPilot')
 checks=[('Утечка воды','Шахтинский филиал ГУП РО «УРСВ»','tel:+78632855777'),
         ('Нет света','АО «Донэнерго»','tel:+78002220550'),
         ('Яма на дороге','Администрация города Шахты','https://www.gosuslugi.ru/')]
 for category,org,link in checks:
  page.locator('#category').select_option(label=category)
  check(org in page.locator('#recipient').inner_text(),category+': correct agency')
  page.locator('#address').fill('г. Шахты, ул. Советская, 11')
  page.locator('#description').fill('Учебная проверка маршрутизации сообщения без реальной доставки.')
  page.locator('#send').click()
  check('НЕ ДОСТАВЛЕНО' in page.locator('#receipt').inner_text(),category+': truthful delivery status')
  check(page.locator('#receipt a.primaryLink').get_attribute('href')==link,category+': verified channel')
  check('ОЖИДАЕТ ПОДАЧИ' in page.locator('#receipt').inner_text(),category+': no fake receipt number')
 check(page.evaluate('CivicReportPilot.inspect().draftCount')==3,'three separate local drafts')
 check(not outbound,'no external contacts or tracking sent from pilot')
 check(not pageErrors,'no JavaScript errors')
 page.screenshot(path=str(OUT/'three-agency-mobile.png'),full_page=True)
 ctx.close();browser.close()
srv.shutdown()
(OUT/'checks.json').write_text(json.dumps({'passed':len(passed),'checks':passed},ensure_ascii=False,indent=2))
print('CIVIC ROUTING TESTS PASSED',len(passed),flush=True)
