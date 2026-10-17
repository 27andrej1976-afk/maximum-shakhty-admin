"""One-time check of publicly readable municipal data sources."""
import re,urllib.request,urllib.error
from html.parser import HTMLParser
class HTMLScan(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.times=[]
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='a' and d.get('href'):self.links.append((d.get('title',''),d['href']))
  if t=='time' and d.get('datetime'):self.times.append(d['datetime'])
urls=[
 ('donenergo-tg','https://t.me/s/ao_donenergo'),
 ('mchs-tg','https://t.me/s/mchs_rostov'),
 ('mchs-web','https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya'),
 ('mchs-alert','https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/shtormovye-i-ekstrennye-preduprezhdeniya'),
 ('power-plan','https://donenergo.ru/grafik-otklyucheniy/61/1/'),
 ('power-plan-home','https://donenergo.ru/grafik-otklyucheniy/'),
 ('power-domain','https://donenergo.ru/'),
 ('gas-branch','https://www.rostovoblgaz.ru/compani/gro_shakhty/kontakty/'),
 ('gas-domain','https://www.rostovoblgaz.ru/'),
 ('gas-alt','https://rostovoblgaz.ru/'),
]
for name,url in urls:
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ShakhtyControlSourceProbe/0.6)'})
  with urllib.request.urlopen(req,timeout=10) as r:
   data=r.read(800_000);type_=r.headers.get('Content-Type','');final=r.url
  html=data.decode('utf-8','replace')
  parser=HTMLScan();parser.feed(html)
  links=[(l,h) for l,h in parser.links if re.search('rss|\\.xml|отключ|газ|мчс|оповещ|шахт|планов|авар',l+' '+h,re.I)]
  title=re.search(r'<title[^>]*>(.*?)</title>',html,re.S|re.I)
  found=re.findall('шахт|отключени|плановы|предупрежден|газоснабжен|rss',html,re.I)
  postids=re.findall(r'data-post="([^"]+)"',html)
  print('PROBE',name,'OK',len(data),'TYPE',type_,'URL',final,'TITLE',re.sub('<[^>]+>','',title.group(1)[:120]) if title else 'none','MATCHES',len(found),'POSTS',postids[:3],postids[-2:],'TIMES',sorted(parser.times)[-2:],'LINKS',links[:10],flush=True)
 except Exception as e:
  print('PROBE',name,'ERROR',str(e)[:180],flush=True)
