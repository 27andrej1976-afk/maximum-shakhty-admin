"""Diagnostic probes for official RSS and public reposts (no persistent user data)."""
import re, ssl, urllib.request, xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
class Scan(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='a' and d.get('href'):self.links.append(d['href'])
urls=[
 ('mchs-rss','https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss'),
 ('mchs-alert-rss','https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/shtormovye-i-ekstrennye-preduprezhdeniya/rss'),
 ('gas-press','https://www.rostovoblgaz.ru/press-center/news/'),
 ('power-plan-www','https://www.donenergo.ru/grafik-otklyucheniy/61/1/'),
 ('power-news-rss','https://newsrostov.ru/rss.xml'),
 ('power-news-don','https://news-don.ru/rss.xml')
]
for tag,url in urls:
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(request,timeout=12) as response:
   raw=response.read(3_000_000)
   ct=response.headers.get('Content-Type')
  txt=raw.decode('utf-8','replace')
  if ('rss' in tag):
   root=ET.fromstring(raw)
   items=root.findall('.//item')
   print('PROBE2',tag,'OK',ct,'items',len(items),'sample',[(i.findtext('pubDate',''),(i.findtext('title','') or '')[:110],i.findtext('link','')) for i in items[:5]])
   if 'power-news' in tag:
    matched=[]
    for i in items:
     body=' '.join(i.itertext())
     if re.search('г[.]?\\s*Шахты',body,re.I) and re.search('Донэнерго|технологическое нарушение|электроснабжен',body,re.I):
      matched.append((i.findtext('pubDate',''),(i.findtext('title','') or '')[:90],i.findtext('link',''),len(body),body[-220:]))
    print('POWER_MATCH',tag,'number',len(matched),'data',matched[:5])
  else:
   p=Scan();p.feed(txt)
   links=[x for x in p.links if any(w in x.lower() for w in ('press-center/news','отключ','gaz','rss','газ'))]
   print('PROBE2',tag,'OK',ct,'length',len(txt),'press_links',links[:20],'has2026oct','17.10.2026' in txt,'snippet',re.sub('<[^>]+>',' ',txt[30000:31000])[:280])
 except Exception as exc:
  print('PROBE2',tag,'ERROR',str(exc)[:220])
