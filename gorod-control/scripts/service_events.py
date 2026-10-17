"""Parsers for geoscoped electricity and MCHS notices. No location sent to feeds.

Do NOT guess real geographic scope from a region's name or a nearby city.
User location is matched only on-device. All source links are public references.
"""
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from rss_water import html_text

MSK = timezone(timedelta(hours=3))
RSS_CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'
YANDEX_TEXT = '{http://news.yandex.ru}full-text'
MCHS_PREFIX = 'https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/'
ADDRESS_START = re.compile(r'^(?:ул(?:ица)?\.?|пер(?:еулок)?\.?|просп(?:ект)?\.?|пр-?кт|пр-?т|проезд|пр-д|пл(?:ощадь)?\.?|пос(?:елок)?\.?)\s+\S+', re.I)
POWER_RELEVANT = re.compile(r'технологическ\w*\s+нарушен|аварийн\w*\s+отключен|планов\w*\s+отключен|восстановлен\w*\s+электроснабжен|электроснабжен\w*\s+восстановлен', re.I)
CITY = re.compile(r'\b(?:г\.?\s*)?шахты\b', re.I)
SOURCE_DONENERGO = re.compile(r'источник\s*:?.{0,130}донэнерго|канал\s+в\s+(?:макс|max).{0,100}донэнерго',re.I|re.S)
EXTREME = re.compile(r'экстренн\w*\s+предупрежден|штормов\w*\s+предупрежден|опасност\w*\s+(?:бпла|ракетн\w*)|чрезвычайн\w*\s+ситуац',re.I)
REGIONAL_EXPLICIT = re.compile(r'по\s+всей\s+территории\s+Ростовской\s+области|на\s+всей\s+территории\s+Ростовской\s+области|во\s+всех\s+муниципальн\w*\s+образован',re.I)
MONTHS={s:i+1 for i,s in enumerate('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split())}

def parse_date(s):
    try:
        d=parsedate_to_datetime(s)
        return d if d.tzinfo is not None else d.replace(tzinfo=MSK)
    except (ValueError, TypeError, IndexError):return None

def short(text,limit=410):
    return re.sub(r'\s+',' ',text or '').strip()[:limit]

def make_id(prefix,text):
    return prefix+'-'+hashlib.sha256(text.encode('utf-8')).hexdigest()[:18]

def affected_power(text):
    """Parse street lists after 'в границах' or 'потребителей'. Unrelated text is not an address."""
    m=re.search(r'(?:в\s+границах|частичн\w*\s+отключени\w*\s+потребителей|отключени\w*\s+потребителей)\s*[:：]\s*(.+)',text,re.I|re.S)
    if not m:
        # Older official outage format often says 'частичному отключению потребителей:'
        m=re.search(r'(?:отключению\s+потребителей)\s*[:：]\s*(.+)',text,re.I|re.S)
    if not m:return []
    zone=re.split(r'(?:\n|(?:\s+)?Ориентировочн|(?:\s+)?Напоминаем|(?:\s+)?Источник\s*:)',m.group(1),maxsplit=1,flags=re.I)[0]
    zone=zone.replace(';',',')
    areas={}
    for part in zone.split(','):
        item=part.strip(' \n\t.,;*')
        if not ADDRESS_START.match(item):continue
        # only a typified street or lane is safe to match against a home
        item=re.sub(r'\s*[\u2013\u2014]\s*', '-',item)
        item=re.sub(r'\s+и\s+прилегающ.*$','',item,flags=re.I)
        item=item.rstrip(' .')
        if len(item)>110:continue
        # Make "просп." compatible with both Javascript and Android canonical street normalizers.
        item=re.sub(r'^просп\.\s+', 'проспект ',item,flags=re.I)
        house=re.match(r'^(.*?)\s+(?:д\.\s*)?(\d+[а-яa-z]?(?:-\d+[а-яa-z]?)?)$',item,re.I)
        if house:
            street=house.group(1)
            houses=[house.group(2).lower()]
        else:street=item;houses=[]
        key=street.lower().replace('ё','е')
        if key not in areas:areas[key]={'street':street,'houses':[]}
        areas[key]['houses']=list(dict.fromkeys(areas[key]['houses']+houses))
    return list(areas.values())[:120]

def classify_power(text):
    t=text.lower()
    if re.search(r'\b(?:электроснабжение\s+восстановлено|восстановлено\s+электроснабжение|подача\s+электроэнергии\s+восстановлена|восстановлена\s+подача\s+электроэнергии)\b',t):return 'resolved'
    if re.search(r'планов\w*\s+отключен|запланирован\w*\s+работ',t):return 'planned'
    if re.search(r'технологическ\w*\s+нарушен|аварийн\w*\s+отключен|отключени\w*\s+потребителей',t):return 'emergency'
    return None

def incident_time(text,published):
    """Explicit incident hh:mm on publication date, else the actual publication time."""
    d=published.astimezone(MSK)
    m=re.search(r'\bв\s+([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\s+произошл',text,re.I)
    if not m:return d
    stamp=d.replace(hour=int(m[1]),minute=int(m[2]),second=0,microsecond=0)
    if stamp>d+timedelta(hours=2):stamp-=timedelta(days=1)
    return stamp

def power_posts(xml_data,domain,now=None):
    """Only public reposts explicitly identifying Donenergo as the original source."""
    now=now or datetime.now(timezone.utc)
    root=ET.fromstring(xml_data)
    out=[]
    for item in root.findall('.//item'):
        title=item.findtext('title','') or ''
        content=item.findtext(RSS_CONTENT,'') or ''
        link=item.findtext('link','') or ''
        if not link.startswith('https://'+domain+'/') or not content:continue
        text=(title+'\n'+html_text(content)).strip()
        if not CITY.search(text[:500]) or not POWER_RELEVANT.search(text):continue
        if not SOURCE_DONENERGO.search(text):continue
        published=parse_date(item.findtext('pubDate',''))
        if not published or not -timedelta(minutes=30) < now-published < timedelta(days=14):continue
        kind=classify_power(text)
        if not kind:continue
        affected=affected_power(text)
        if not affected:continue
        start=incident_time(text,published)
        end=None
        hours=re.search(r'ориентировочн[а-я\s]{0,75}в\s+течение\s+(\d{1,2})\s+час',text,re.I)
        if hours:end=start+timedelta(hours=int(hours[1]))
        if kind=='emergency' and now-published>timedelta(hours=48):continue
        if kind=='planned' and not (timedelta(days=-1)<=start-now<=timedelta(days=14)):continue
        if kind=='resolved':continue
        if end and end<now-timedelta(hours=24):continue
        status='unconfirmed' if end and end<now else 'active'
        token=make_id('power',start.isoformat()+'|'+','.join(sorted(a['street'] for a in affected)))
        out.append({'id':token,'category':'power','kind':kind,'status':status,
            'source':'Донэнерго — перепечатка','sourceId':'power_repost',
            'origin':'attributed_repost','publishedAt':published.isoformat(),'url':link,
            'title':'Плановое отключение электричества' if kind=='planned' else 'Аварийное отключение электричества',
            'description':short(text),'affected':affected,'point':None,
            'start':start.isoformat(),'end':end.isoformat() if end else None,
            'precision':'street','confidence':'secondary'})
    return out

def _risky_mchs_scope(body):
    """True only where Shakhty is expressly listed in the risk's geographic extent."""
    text=re.sub(r'\s+',' ',body)
    # A warning for just several other districts must not be sent to Shakhty.
    if REGIONAL_EXPLICIT.search(text):return 'region'
    if not CITY.search(text):return None
    # In a forecast Shakhty must be in the relevant risk list, not merely a footer.
    if 'пожароопасност' in text.lower():
        m=re.search(r'высокая\s+пожароопасность\s*\(4\s*класс\)[^:]{0,150}:\s*(.{0,440})',text,re.I)
        if m and CITY.search(m.group(1)):return 'city'
        m=re.search(r'чрезвычайная\s+пожароопасность\s*\(5\s*класс\)[^:]{0,150}:\s*(.{0,440})',text,re.I)
        if m and CITY.search(m.group(1)):return 'city'
        return None
    # For other city-only dangerous notices explicit g. Shakhty required.
    if re.search(r'\b(?:г|город)\.?\s*Шахты\b',text,re.I):return 'city'
    return None

def forecast_target_date(title,published):
    m=re.search(r'\bна\s+([0-3]?\d)\s+('+'|'.join(MONTHS)+r')\s+(20\d{2})\s*года',title,re.I)
    if not m:return published.astimezone(MSK)
    try:return datetime(int(m[3]),MONTHS[m[2].lower()],int(m[1]),tzinfo=MSK)
    except ValueError:return published.astimezone(MSK)

def mchs_posts(xml_data,now=None):
    """Only risk warnings explicitly covering Shakhty or all municipalities."""
    now=now or datetime.now(timezone.utc)
    root=ET.fromstring(xml_data)
    out=[]
    for item in root.findall('.//item'):
        title=item.findtext('title','') or ''
        link=item.findtext('link','') or ''
        if not link.startswith(MCHS_PREFIX):continue
        published=parse_date(item.findtext('pubDate',''))
        if not published or not -timedelta(minutes=30) < now-published < timedelta(days=4):continue
        body=html_text(item.findtext(YANDEX_TEXT,'') or '')
        if not body or len(body)<80:continue
        is_forecast='ежедневный прогноз чс' in title.lower()
        is_warning=bool(EXTREME.search(title))
        if not (is_forecast or is_warning):continue
        scope=_risky_mchs_scope(body)
        if not scope:continue
        date=forecast_target_date(title,published)
        if is_forecast:
            if not re.search(r'высокая\s+пожароопасность\s*\(4\s*класс\)',body,re.I):
                continue
            end=date.replace(hour=23,minute=59)
            start=date.replace(hour=0,minute=0)
            if end<now:continue
            headline='МЧС: высокая пожароопасность (4 класс) в Шахтах'
            priority='info'
        else:
            start=published.astimezone(MSK)
            end=start+timedelta(hours=48)
            if end<now:continue
            headline='Предупреждение МЧС, затрагивающее '+('Ростовскую область' if scope=='region' else 'Шахты')
            priority='high'
        out.append({'id':make_id('mchs',link),'category':'mchs','kind':'warning',
            'source':'МЧС Ростовской области','sourceId':'mchs','scope':scope,
            'status':'active','priority':priority,'publishedAt':published.isoformat(),'url':link,
            'title':headline,'description':short(body,510),
            'start':start.isoformat(),'end':end.isoformat(),
            'affected':[],'point':None,'precision':'city' if scope=='city' else 'region',
            'confidence':'official'})
    return out
