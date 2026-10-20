"""Public KVU RSS. Media reports remain explicitly secondary evidence."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from rss_water import ENCODED, SHACHTY, html_text
URL='https://kvu.su/utilities/rss.xml'

def split_notices(text):
    # An article may concatenate several independent outages. Split only at a
    # new repair paragraph following an already explicit completion time.
    sections=[];current=[];finished=False
    for line in text.splitlines():
        if finished and re.search(r'аварийн\w*\s*[-–]?\s*ремонт',line,re.I):
            sections.append('\n'.join(current));current=[];finished=False
        current.append(line)
        if re.search(r'ориентировочн.*(?:окончания|завершения)',line,re.I):finished=True
    if current:sections.append('\n'.join(current))
    return sections

def feed_messages(raw):
    root=ET.fromstring(raw)
    if root.tag!='rss' or root.find('channel') is None:raise ValueError('Expected RSS channel')
    result=[]
    for item in root.findall('./channel/item')[:100]:
        title=item.findtext('title') or '';url=item.findtext('link') or ''
        text=html_text(item.findtext(ENCODED) or item.findtext('{http://turbo.yandex.ru}content') or '')
        if not url.startswith('https://kvu.su/utilities/') or not SHACHTY.search(title):continue
        if not re.search(r'отключ\w*.*вод|не будет воды|снижен\w*.*давлен',title,re.I):continue
        try:
            published=parsedate_to_datetime(item.findtext('pubDate') or '')
            if published.tzinfo is None:continue
        except (ValueError,TypeError):continue
        for index,section in enumerate(split_notices(text)):
            if not re.search(r'ремонтн\w*\s+работ|ремонт\w*.*трубопровод',section,re.I):continue
            if not re.search(r'(?:по адресам|в направлении(?: улиц)?|в следующих направлениях)\s*:',section,re.I):continue
            if not re.search(r'(?:до\s+|(?:окончания|завершения)[^\n\d]{0,25})\d{1,2}[:.\-]\d{2}',section,re.I):continue
            result.append({'id':'kvu/'+sha256(url.encode()).hexdigest()[:20]+'/'+str(index),
                'publishedAt':published.isoformat(),'text':section,'url':url,'origin':'media_report',
                'source':'КВУ — публикация СМИ','sourceId':'water_kvu'})
    return result

def collect(now=None):
    now=now or datetime.now(timezone.utc)
    state={'id':'water_kvu','url':URL,'checkedAt':now.isoformat(),'coverage':'partial'}
    try:
        with urlopen(Request(URL,headers={'User-Agent':'CityControlShakhty/1.0 public RSS'}),timeout=20) as response:
            raw=response.read(7_000_001)
        if len(raw)>7_000_000:raise ValueError('RSS exceeds size limit')
        posts=feed_messages(raw)
        valid=[p for p in posts if timedelta(0)<=now-datetime.fromisoformat(p['publishedAt'])<timedelta(days=15)]
        state.update(status='ok',readStatus='ok',posts=len(ET.fromstring(raw).findall('./channel/item')),
                     matchingPosts=len(valid),lastPostAt=max((p['publishedAt'] for p in posts),default=None),
                     note='Публикации СМИ об отключениях воды; не прямая лента водоканала')
        return valid,state
    except Exception as exc:
        state.update(status='error',posts=0,note='Не удалось прочитать RSS КВУ: '+str(exc)[:120])
        return [],state
