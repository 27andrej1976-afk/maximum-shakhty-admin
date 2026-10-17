from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime,timezone
import ssl,re,json,time,subprocess
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.sync_api import sync_playwright
OUT=Path('direct-report');OUT.mkdir(exist_ok=True)
CA='https://secure.globalsign.com/cacert/gsgccr46alphasslca2025.crt'
with urlopen(CA,timeout=15) as r:raw=r.read(200000)
cert=x509.load_der_x509_certificate(raw)
pem=cert.public_bytes(serialization.Encoding.PEM)
(OUT/'globalsign-intermediate.pem').write_bytes(pem)
ctx=ssl.create_default_context();ctx.load_verify_locations(cadata=pem.decode())
records=[]
for suffix in ('61/1/','61/2/'):
 url='https://donenergo.ru/grafik-otklyucheniy/'+suffix
 for attempt in range(2):
  rec={'url':url,'checkedAt':datetime.now(timezone.utc).isoformat(),'attempt':attempt+1}
  try:
   with urlopen(Request(url,headers={'User-Agent':'CityControl/0.9 (official public planned outages)'}),context=ctx,timeout=15) as r:
    body=r.read(2500000);rec.update(status=r.status,bytes=len(body))
   (OUT/('power-'+suffix.replace('/','-')+str(attempt)+'.html')).write_bytes(body)
   print('VERIFIED_TLS_POWER',rec,flush=True)
  except Exception as e:rec['error']=str(e)
  records.append(rec)
  time.sleep(2)
(OUT/'verified-power.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
with sync_playwright() as p:
 b=p.chromium.launch();page=b.new_page()
 page.goto('https://donenergo.ru/grafik-otklyucheniy/61/1/',wait_until='domcontentloaded',timeout=25000)
 (OUT/'power-plan-browser.html').write_text(page.content())
 (OUT/'power-plan-browser.txt').write_text(page.locator('body').inner_text())
 (OUT/'power-plan-links.json').write_text(json.dumps(page.locator('a[href]').evaluate_all('(as)=>as.map(a=>({text:a.textContent,url:a.href}))'),ensure_ascii=False))
 b.close()
