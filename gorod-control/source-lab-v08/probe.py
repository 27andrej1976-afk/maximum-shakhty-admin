"""Bounded public-source audit. No authentication, credentials, or production writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse, urljoin
import importlib.util
import json
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'source-lab-v08'/'report'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'scripts'))
import collect_water as baseline
from rss_water import feed_messages

SOURCES=[
 ('ursv_website','https://rovodokanal.ru/emergency-alerts/'),
 ('ursv_www','https://www.rovodokanal.ru/emergency-alerts/'),
 ('ursv_example','https://rovodokanal.ru/emergency-alerts/1591'),
 ('ursv_max','https://max.ru/id6167110467_gos'),
 ('power_max','https://max.ru/id6163089292_biz'),
 ('city_max','https://max.ru/shakhtygorod'),
 ('city_website','https://shakhty.donland.ru/'),
 ('power_planned','https://donenergo.ru/grafik-otklyucheniy/61/1/'),
 ('water_telegram_archive','https://t.me/s/shakhtinskiy'),
 ('city_telegram','https://t.me/s/admshakhty'),
 ('water_repost_rostov','https://newsrostov.ru/rss.xml'),
 ('water_repost_don','https://news-don.ru/rss.xml'),
 ('mchs_rss','https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss')
]
class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title='';self.in_title=False;self.links=[];self.times=[];self.meta={}
    def handle_starttag(self,tag,attrs):
        at=dict(attrs)
        if tag=='title':self.in_title=True
        if tag=='a' and at.get('href'):self.links.append(at['href'])
        if tag=='time' and at.get('datetime'):self.times.append(at['datetime'])
        if tag=='meta' and at.get('content'):
            self.meta[at.get('property') or at.get('name') or '']=at['content']
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,s):
        if self.in_title:self.title+=s

def probe(item):
    ident,url=item
    now=datetime.now(timezone.utc).isoformat()
    info={'id':ident,'url':url,'checkedAt':now,'tlsVerification':True}
    begin=time.monotonic()
    try:
        req=Request(url,headers={'User-Agent':'CityControl-SourceAudit/0.8 (public municipal notices; no login)','Accept':'text/html,application/xml,text/xml;q=0.9,*/*;q=0.5'})
        with urlopen(req,timeout=14) as resp:
            body=resp.read(7000001)
            info.update(httpStatus=resp.status,finalUrl=resp.url,contentType=resp.headers.get('Content-Type',''))
        if len(body)>7000000:raise ValueError('Response limit exceeded')
        info['bytes']=len(body);info['sha256']=sha256(body).hexdigest()
        (OUT/(ident+'.raw')).write_bytes(body)
        html=body.decode('utf-8','replace')
        scan=Scan();scan.feed(html)
        info.update(title=scan.title.strip(),publishedTimes=scan.times[-25:])
        domain=urlparse(url).hostname
        links=list(dict.fromkeys(urljoin(url,x) for x in scan.links))
        info['publicationLinks']=[l for l in links if re.search(r'/emergency-alerts/\d+|/news/\d+|/rss(?:/|$)|/feed(?:/|$)',l)][:25]
        if ident.endswith('_max'):
            channel=urlparse(url).path.strip('/')
            post_links=[l for l in links if re.fullmatch(r'https://max\.ru/'+re.escape(channel)+r'/[A-Za-z0-9_-]{6,}',l)]
            info['postLinks']=post_links[:30]
            info['result']='public_feed_found' if post_links else 'public_profile_only'
            info['warning']='HTTP 200 on a channel profile is not proof of access to its messages'
        elif ident in ('water_telegram_archive','city_telegram'):
            ch='shakhtinskiy' if ident=='water_telegram_archive' else 'admshakhty'
            posts=baseline.parse_html(html,ch)
            info['posts']=len(posts)
            info['lastPostAt']=max((p['publishedAt'] for p in posts),default=None)
            info['result']='public_messages' if posts else 'no_parseable_messages'
            (OUT/(ident+'.json')).write_text(json.dumps(posts,ensure_ascii=False,indent=2),encoding='utf-8')
        elif ident.startswith('water_repost_'):
            tree=ET.fromstring(body)
            rawitems=tree.findall('.//item')
            posts=feed_messages(body,domain)
            info.update(posts=len(rawitems),waterPosts=len(posts),result='rss_read')
            (OUT/(ident+'.json')).write_text(json.dumps(posts,ensure_ascii=False,indent=2),encoding='utf-8')
        elif ident=='mchs_rss':
            tree=ET.fromstring(body)
            info.update(posts=len(tree.findall('.//item')),result='official_rss_read')
        else:
            info['result']='page_read_needs_parser' if info['publicationLinks'] else 'page_read_not_feed'
    except HTTPError as exc:
        info.update(httpStatus=exc.code,result='http_error',error=str(exc))
    except Exception as exc:
        info.update(result='unavailable',error=str(exc)[:350])
    info['durationSeconds']=round(time.monotonic()-begin,2)
    print('SOURCE_AUDIT',json.dumps(info,ensure_ascii=False),flush=True)
    return info

def main():
    with ThreadPoolExecutor(max_workers=3) as workers:
        checks=list(workers.map(probe,SOURCES))
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'isolated':True,'sources':checks,
      'productionUnchanged':True,'maxBotAccess':'Not attempted: no authorized channel admin bot/token supplied'}
    (OUT/'sources.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    fixtures=[]
    for key in ('water_telegram_archive','water_repost_rostov','water_repost_don'):
        file=OUT/(key+'.json')
        if file.exists():
            for post in json.loads(file.read_text(encoding='utf-8')):
                fixtures.append(dict(post,auditSource=key))
    (OUT/'real_posts.json').write_text(json.dumps(fixtures,ensure_ascii=False,indent=2),encoding='utf-8')
    # Only public project files; no .git, credentials, personal addresses or APK signing keys.
    work=OUT/'baseline';work.mkdir(exist_ok=True)
    for folder in ('scripts','map-v07'):
        if (ROOT/folder).exists():
            shutil.copytree(ROOT/folder,work/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)
    shutil.copy2(ROOT/'index.html',work/'index.html')
    shutil.copytree(ROOT/'data',work/'data',dirs_exist_ok=True)
    print('SOURCE_AUDIT_FINISHED',len(checks),'sources',len(fixtures),'real published posts',flush=True)
if __name__=='__main__':main()
