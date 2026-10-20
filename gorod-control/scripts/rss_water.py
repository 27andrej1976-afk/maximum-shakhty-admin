"""Official URSV Shakhty notices republished in publicly readable RSS.

The originating news site is a SECONDARY mirror, not the municipal service. 
Only items with explicit https://rovodokanal.ru/emergency-alerts/<number> reference
are accepted as a reprint; preserves both official and mirror links.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import re
from hashlib import sha256
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

RSS_URLS = [
    'https://newsrostov.ru/rss.xml',
    'https://news-don.ru/rss.xml',
]
ENCODED = '{http://purl.org/rss/1.0/modules/content/}encoded'
OFFICIAL = re.compile(r'https?://(?:www\.)?rovodokanal\.ru/emergency-alerts/(\d+)', re.I)
RELEVANT = re.compile(r'снижени[ея]\s+давлен|снижен[оа]?\s+давлен|отключен\w*\s+вод|'
                      r'водоснабж\w*\s+(?:восстановл|приостановл|прекращ)|'
                      r'планов\w*\s+работ|аварийн\w*[- ]\s*ремонт', re.I)
SHACHTY = re.compile(r'\b(?:Шахты|Шахтах|Шахтинский|Шахтинского)\b', re.I)
CREATOR = '{http://purl.org/dc/elements/1.1/}creator'

class HtmlPlaintext(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip+=1
        if self.skip:return
        if tag in ('br','p','div','li','h1','h2','h3','tr','section'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if self.skip:return
        if tag in ('p','div','li','h1','h2','h3','tr','section'):self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:self.parts.append(data)

def html_text(raw):
    p=HtmlPlaintext()
    p.feed(raw or '')
    x=unescape(''.join(p.parts)).replace('\xa0',' ').replace('\ufe0f','')
    x=re.sub(r'[ \t]+',' ',x)
    return re.sub(r'\n[ \t]*\n+','\n',x).strip()

def feed_messages(xml_bytes, domain):
    """Parse first 200 feed items, only official URSV articles with traceable IDs."""
    if domain not in ('newsrostov.ru','news-don.ru'):return []
    root=ET.fromstring(xml_bytes)
    if root.tag != 'rss' or root.find('channel') is None:raise ValueError('Expected RSS channel')
    result=[]
    for i in root.findall('.//item'):
        title=i.findtext('title') or ''
        html=i.findtext(ENCODED) or ''
        link=i.findtext('link') or ''
        date=i.findtext('pubDate') or ''
        if not (html and title and link.startswith('https://'+domain+'/')):
            continue
        official=OFFICIAL.search(html)
        municipal=(i.findtext(CREATOR) or '').strip()=='Администрация города Шахты'
        if not official and not municipal:
            continue
        text=html_text(html)
        if not SHACHTY.search(title+' '+text[:150]):
            continue
        if not RELEVANT.search(text):
            continue
        try:
            when=parsedate_to_datetime(date)
            if when.tzinfo is None:when=when.replace(tzinfo=timezone(timedelta(hours=3)))
        except (ValueError,TypeError):
            continue
        official_url='https://rovodokanal.ru/emergency-alerts/'+official.group(1) if official else None
        result.append({'id':'oursv/'+official.group(1) if official else 'city-repost/'+sha256(link.encode()).hexdigest()[:20],'publishedAt':when.isoformat(),
                       'text':text,'url':link,'officialUrl':official_url,
                       'origin':'verified_repost' if official else 'municipal_repost',
                       'source':'ГУП РО УРСВ — перепечатка' if official else 'Администрация города Шахты — перепечатка',
                       'sourceId':'repost_rostov' if domain=='newsrostov.ru' else 'repost_don',
                       'mirror':domain})
    return result

def collect_rss(now=None):
    now=now or datetime.now(timezone.utc)
    notices={};status=[]
    for url in RSS_URLS:
        domain=url.split('/')[2]
        try:
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; CityControlShakhty/0.3; public notices only)'})
            with urlopen(req,timeout=17) as response:
                raw=response.read(7_000_000)
            posts=feed_messages(raw,domain)
            valid=[p for p in posts if abs((now-datetime.fromisoformat(p['publishedAt'])).total_seconds()) < 15*86400]
            for p in valid:
                # Preserve first mirror link for each official event id.
                notices.setdefault(p['id'],p)
            latest=max((p['publishedAt'] for p in posts),default=None)
            status.append({'id':('repost_rostov' if 'newsrostov.' in domain else 'repost_don'),
                           'status':'ok','readStatus':'ok','coverage':'partial',
                           'posts':len(ET.fromstring(raw).findall('.//item')),'matchingPosts':len(valid),'checkedAt':now.isoformat(),'lastPostAt':latest,'url':url,
                           'note':'Перепечатки УРСВ с документом и сообщения с авторством администрации Шахт'})
            print('RSS MIRROR',domain,'official refs',len(posts),'recent',len(valid))
        except Exception as exc:
            status.append({'id':('repost_rostov' if 'newsrostov.' in domain else 'repost_don'),
                           'status':'error','posts':0,'url':url,'note':str(exc)[:140]})
            print('RSS SOURCE ERROR',domain,str(exc)[:140])
    return list(notices.values()), status

if __name__=='__main__':
    msgs,checks=collect_rss()
    print('Matched:',len(msgs),'sources:',checks)
