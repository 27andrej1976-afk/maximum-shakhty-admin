"""Inspect MCHS RSS item fields and the official article body without retaining personal data."""
import urllib.request,xml.etree.ElementTree as ET,re,html
base='https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss'
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=12) as r:return r.read(2_000_000).decode('utf-8','replace')
try:
 root=ET.fromstring(get(base))
 for item in root.findall('.//item')[:5]:
  title=item.findtext('title','')
  desc=item.findtext('description','')
  link=item.findtext('link','')
  keys=[(tag.tag,len(tag.text or '')) for tag in item]
  print('MCHS_ITEM',title,'LINK',link,'DESCLEN',len(desc),'DESCRIPTION',desc[:1000].replace('\n',' '),'FIELDS',keys,flush=True)
  if 'Экстренное предупреждение' in title or 'прогноз ЧС' in title:
   h=get(link)
   print('MCHS_ARTICLE',link,'length',len(h),'occurrences',[(m.start(),h[m.start()-140:m.start()+350].replace('\n',' ')) for m in list(re.finditer('пожароопасность|Шахты|ОРЛОВСК',h,re.I))[:4]],flush=True)
except Exception as exc:print('MCHS_SAMPLE_ERROR',str(exc)[:180])
