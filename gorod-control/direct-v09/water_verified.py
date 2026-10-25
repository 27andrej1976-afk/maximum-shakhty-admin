"""Evidence-preserving water notice normalizer. Candidate only: no network/writes.
Historical replay data must never be published as current incidents.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re,json
from pathlib import Path
from typing import Any
MSK=timezone(timedelta(hours=3))
MONTHS={s:i+1 for i,s in enumerate('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split())}
KINDS=[('ул',r'улица|ул\.?'),('пер',r'переулок|пер\.?'),('проспект',r'проспект|пр-кт|пр-т|просп\.?|пр\.'),('проезд',r'проезд|пр-д'),('пл',r'площадь|пл\.?'),('бул',r'бульвар|бул\.?'),('пос',r'пос[её]лок|пос\.?'),('мкр',r'микрорайон|мкр\.?')]
HOUSE=r'\d+[а-яa-z]?(?:/\d+[а-яa-z]?)?(?:\s*[-–]\s*\d+[а-яa-z]?)?'
NUMDATE=re.compile(r'(?<!\d)([0-3]?\d)[./]([01]?\d)[./](20\d{2})(?!\d)')
WORDDATE=re.compile(r'(?<!\d)([0-3]?\d)\s+('+'|'.join(MONTHS)+r')(?:\s+(20\d{2}))?',re.I)
TIME=r'([01]?\d|2[0-3])\s*[:.\-]\s*([0-5]\d)(?!\d)'
STRIP=' \t\r\n▫▪•-–✔✅🔹🔸🗺️'
try:STREET_ALIASES=json.loads(Path(__file__).with_name('street-name-index.json').read_text(encoding='utf-8')).get('aliases',{})
except (OSError,ValueError):STREET_ALIASES={}


def clean(text):
    return re.sub(r'\s+',' ',str(text or '').replace('\xa0',' ').replace('\ufe0f','')).strip()

def classify(text):
    t=clean(text).lower()
    if re.search(r'работы\s+завершены\b',t) and not re.search(r'работы\s+(?:ещ[её]\s+)?не\s+завершены',t):return 'resolved'
    if re.search(r'(?<!будет )(?<!не )\bводоснабжение\s+восстановлено\b|\bподача воды возобновлена\b',t):return 'resolved'
    if re.search(r'работы\s+продлены|срок[и]?\s+[^.]{0,25}продл|переносится|перенесены',t):return 'extension'
    if re.search(r'планов\w*\s+(?:работ|отключен)|запланирован|профилактическ|будет\s+(?:снижен|приостановлен|отключен)',t):return 'planned'
    if re.search(r'снижение\s+давления|снижено\s+давление|отключение\s+вод|аварийн|водоснабжение\s+приостановлено',t):return 'emergency'
    return None

def road(raw,implied=None):
    text=clean(raw).strip(STRIP+' ,;.')
    text=re.sub(r'^(?:г\.?\s*Шахты|Шахты)\s*,?\s*','',text,flags=re.I)
    text=re.sub(r'\s+и\s+прилегающ.*$','',text,flags=re.I)
    match=re.search(r'(?:,?\s+(?:д(?:ом)?\.?\s*)|,\s*|\s+)('+HOUSE+r'(?:\s*,\s*'+HOUSE+r')*)$',text,re.I)
    houses=[]
    if match:
        houses=[re.sub(r'\s+','',s).lower().replace('–','-') for s in match[1].split(',')]
        text=text[:match.start()].strip(' ,;.')
    for name,pattern in KINDS:
        m=re.fullmatch(r'(?:'+pattern+r')(?:\s+|(?<=\.))(.+)',text,re.I)
        if not m:m=re.fullmatch(r'(.+?)\s+(?:'+pattern+r')',text,re.I)
        if m:
            value=m[1].strip(' ,;.')
            if value and len(value)<100:return {'street':name+' '+value,'houses':houses}
    canonical=STREET_ALIASES.get(text.lower().replace('ё','е'))
    if canonical and canonical!=text:return {'street':canonical,'houses':houses}
    if implied and text and len(text)<70:return {'street':implied+' '+text,'houses':houses}
    return None

def road_key(raw):
    r=road(raw)
    return clean(r['street'] if r else raw).lower().replace('ё','е')

def extract_areas(text):
    result=[];unknown=[];zones=[];active=False;settlements=False
    for raw in text.splitlines():
        line=raw.strip(STRIP)
        if re.match(r'^(?:С\s+нестабильным\s+водоснабжением\s+)?Адрес(?:а|ы)?\s*:',line,re.I):
            active=True;line=line.split(':',1)[1].strip()
            if not line:continue
        elif re.search(r'водоснабжение\s+поселков\s*:',line,re.I):
            settlements=True;continue
        elif re.search(r'(?:в направлении(?: улиц)?|в следующих направлениях|по следующим улицам|по адресам)\s*:',line,re.I):
            active=True;line=re.split(r'(?:в направлении(?: улиц)?|в следующих направлениях|по следующим улицам|по адресам)\s*:',line,maxsplit=1,flags=re.I)[1].strip()
            if not line:continue
        if not active and not settlements:continue
        if re.match(r'^(?:ℹ|🔗|🔧|Подробност|Подробнее|Ориентировоч|По завершени|Просим|Подвоз|Организован|Телефон|Источник|Причина)',line,re.I):break
        if not line:continue
        line=re.sub(r'^(?:г\.?\s*Шахты|Шахты)\s*,?\s*','',line,flags=re.I)
        implied=None
        if settlements:
            parts=re.split(r'\s+и\s+улиц\s*:\s*',line,maxsplit=1,flags=re.I)
            zone=parts[0].strip(' .,')
            if zone:
                partial=bool(re.search(r'часть|район',zone,re.I))
                name=re.sub(r'^(?:часть\s+)?(?:поселка|пос\.)\s+','',zone,flags=re.I)
                zones.append({'name':name,'scope':'settlement','partial':partial})
            if len(parts)==1:continue
            line=parts[1];implied='ул';active=True;settlements=False
        if re.search(r'прилегающ',line,re.I):unknown.append('Прилегающие улицы не перечислены полностью')
        def bracket(m):
            parsed=road(m[1])
            if parsed:result.append(parsed)
            else:unknown.append(m[1])
            return ''
        line=re.sub(r'\(([^()]*)\)',bracket,line)
        line=re.sub(r'\s+и\s+прилегающ.*$','',line,flags=re.I)
        tokens=[s.strip(' .,;') for s in line.split(',') if s.strip(' .,;')]
        joined=[]
        for token in tokens:
            if joined and re.fullmatch(r'(?:д(?:ом)?\.?\s*)?'+HOUSE,token,re.I):joined[-1]+=', '+token
            else:joined.append(token)
        for entry in joined:
            if re.search(r'ГКОУ|лесхоз|школ[аы]|интернат|Дом[а]? Культуры',entry,re.I):
                if entry:unknown.append(entry)
                continue
            parsed=road(entry,implied)
            if parsed:result.append(parsed)
            else:unknown.append(entry)
    merged={}
    for item in result:
        key=road_key(item['street'])
        if key not in merged:merged[key]=dict(item,houses=list(item['houses']))
        elif not merged[key]['houses'] or not item['houses']:merged[key]['houses']=[]
        else:merged[key]['houses']=sorted(set(merged[key]['houses']+item['houses']))
    return {'affected':list(merged.values()),'zones':zones,'unmappedAreaText':list(dict.fromkeys(unknown))}

def parse_affected(text):return extract_areas(text)['affected']

def dates(text,published):
    out=[]
    for m in NUMDATE.finditer(text):
        try:out.append((m.start(),m.end(),datetime(int(m[3]),int(m[2]),int(m[1]),tzinfo=MSK)))
        except ValueError:continue
    for m in WORDDATE.finditer(text):
        year=int(m[3]) if m[3] else published.astimezone(MSK).year
        try:
            d=datetime(year,MONTHS[m[2].lower()],int(m[1]),tzinfo=MSK)
            if not m[3] and (d-published.astimezone(MSK)).days < -300:d=d.replace(year=year+1)
            out.append((m.start(),m.end(),d))
        except ValueError:continue
    return sorted(out)

def adjacent_after(text,position,ds):
    for a,b,d in ds:
        if a>=position and a-position<=20:
            gap=text[position:a]
            if re.fullmatch(r'[\s.,]*(?:(?:час\.?|часов|часа)\s*)?[\s.,]*',gap,re.I):return d
    return None

def schedule(text,published,kind):
    ds=dates(text,published)
    start_m=re.search(r'\bс\s+'+TIME,text,re.I)
    end_m=re.search(r'(?:\bдо\s+|ориентировочн[^\n]{0,90}?(?:завершения|окончания)[^\d\n]{0,18})'+TIME,text,re.I)
    base=published.astimezone(MSK).replace(hour=0,minute=0,second=0,microsecond=0)
    start=None;end=None
    if start_m:
        following=adjacent_after(text,start_m.end(),ds)
        preceding=[d for a,b,d in ds if b<=start_m.start() and start_m.start()-b<=80]
        day=following or (preceding[-1] if preceding else (ds[0][2] if ds else base))
        start=day.replace(hour=int(start_m[1]),minute=int(start_m[2]),second=0,microsecond=0)
    elif kind=='planned' and ds:start=ds[0][2]
    elif kind in ('emergency',None):start=published.astimezone(MSK)
    if end_m:
        explicit=adjacent_after(text,end_m.end(),ds)
        day=explicit or (start.replace(hour=0,minute=0,second=0,microsecond=0) if start else (ds[-1][2] if ds else base))
        end=day.replace(hour=int(end_m[1]),minute=int(end_m[2]),second=0,microsecond=0)
        if start and end<start and explicit is None:end+=timedelta(days=1)
        if start and end<start:return start.isoformat(),None
    return start.isoformat() if start else None,end.isoformat() if end else None

def work_site(text):
    m=re.search(r'по\s+адресу\s*:?\s*([^\n]+)',text,re.I)
    if not m:return None
    chunk=re.split(r'\s+с\s+'+TIME+r'|\s+завершен|\s+работы\s+продлен',m[1],maxsplit=1,flags=re.I)[0]
    chunk=re.split(r'\s+(?:снижено|снижена|нестабильное|проводятся)\b',chunk,maxsplit=1,flags=re.I)[0]
    chunk=re.sub(r'\s*,\s*',' ',chunk).strip(' .')
    parsed=road(chunk)
    if parsed:return road_key(parsed['street'])+'|'+','.join(parsed['houses'])
    return 'неуточн:'+clean(chunk).lower()

def normalize(post):
    p=deepcopy(post);text=p['text'];kind=classify(text)
    pub=datetime.fromisoformat(p['publishedAt'])
    if pub.tzinfo is None:raise ValueError('Publication timezone required')
    area=extract_areas(text);start,end=schedule(text,pub,kind)
    official=p.get('officialUrl')
    if not official:
        m=re.search(r'https://(?:www\.)?rovodokanal\.ru/emergency-alerts/\d+',text)
        official=m[0] if m else None
    m=re.search(r'\b[Вв]\s+'+TIME+r'\s*(?:час\.?\s*)?([0-3]?\d[./][01]?\d[./]20\d{2})',text)
    resolved=None
    if kind=='resolved' and m:
        dd=dates(m[3],pub)
        if dd:resolved=dd[0][2].replace(hour=int(m[1]),minute=int(m[2])).isoformat()
    out={'id':p['id'],'publishedAt':p['publishedAt'],'kind':kind,'start':start,'end':end,
      'startBasis':'explicit' if re.search(r'\bс\s+'+TIME,text,re.I) else ('date_only' if kind=='planned' and start else 'publication' if start else 'unknown'),
      'endBasis':'estimated' if end else 'unknown','resolvedAt':resolved,'workSite':work_site(text),
      'url':p['url'],'officialUrl':official,'source':p.get('source','Шахтинский водоканал'),
      'origin':p.get('origin','official_archive'),'text':text,'textSha256':sha256(text.encode()).hexdigest(),**area}
    for key in ('observedAt','editedAt','sourceId','mirror'):
        if p.get(key):out[key]=p[key]
    out['reviewRequired']=bool(area['zones'] or area['unmappedAreaText'] or not area['affected'])
    out['requiresReview']=out['reviewRequired']
    return out

def coverage_key(areas):
    return tuple(sorted((road_key(a['street']),tuple(sorted(a.get('houses',[])))) for a in areas))

def covers(initial,finished):
    if not initial or not finished:return False
    r={road_key(x['street']):set(x.get('houses') or []) for x in finished}
    for a in initial:
        key=road_key(a['street']);nums=set(a.get('houses') or [])
        if key not in r:return False
        if not nums and r[key]:return False
        if nums and r[key] and not nums.issubset(r[key]):return False
    return True

def build_feed(posts,now):
    unique={};duplicates=0;revision_conflicts=[]
    for p in posts:
        stamp=datetime.fromisoformat(p['publishedAt'])
        if stamp>now:continue
        n=normalize(p);key=(n['id'],n['textSha256'])
        if key in unique:
            duplicates+=1;unique[key].setdefault('additionalSources',[]).append(p['url'])
        else:unique[key]=n
    versions={}
    for item in unique.values():versions.setdefault(item['id'],[]).append(item)
    eligible=[]
    for ident,items in versions.items():
        if len(items)==1:eligible.extend(items);continue
        stamps=[i.get('observedAt') or i.get('editedAt') for i in items]
        if all(stamps) and len(set(stamps))==len(stamps):
            latest=max(items,key=lambda i:datetime.fromisoformat(i.get('observedAt') or i['editedAt']))
            latest['supersededHashes']=[i['textSha256'] for i in items if i is not latest];eligible.append(latest)
        else:revision_conflicts.append({'noticeId':ident,'versionCount':len(items),'reason':'Разные тексты одного сообщения без времени редактирования; требуется сверка'})
    notices=sorted(eligible,key=lambda p:datetime.fromisoformat(p['publishedAt']))
    incidents=[];unlinked=[]
    for n in notices:
        if not n['kind']:continue
        pub=datetime.fromisoformat(n['publishedAt'])
        candidates=[e for e in incidents if e['status']!='resolved' and timedelta(0)<=pub-datetime.fromisoformat(e['publishedAt'])<timedelta(hours=72)]
        same_site=[e for e in candidates if e.get('workSite') and e['workSite']==n['workSite']]
        if n['kind']=='extension':
            if len(same_site)==1:
                e=same_site[0]
                if n['end']:e['end']=n['end']
                if n['start']:e['start']=n['start']
                e['revision']+=1;e['evidence'].append(n['url']);e['updates'].append(n['id']);e['lastUpdateAt']=n['publishedAt'];continue
            unlinked.append({'noticeId':n['id'],'reason':'Продление нельзя однозначно связать с аварией'});continue
        if n['kind']=='resolved':
            matches=[e for e in same_site if not n['affected'] or covers(e['affected'],n['affected'])]
            if len(matches)==1:
                e=matches[0];e['status']='resolved';e['resolvedAt']=n['resolvedAt'];e['evidence'].append(n['url']);e['updates'].append(n['id'])
            else:
                possible=[e['id'] for e in candidates if covers(e['affected'],n['affected'])]
                unlinked.append({'noticeId':n['id'],'reason':'Завершение требует сверки места ремонта/охвата','possibleIncidentIds':possible})
            continue
        signature=lambda x:(x['kind'],x['start'],x['end'],x['workSite'],coverage_key(x['affected']))
        matches=[e for e in incidents if e['status']!='resolved' and e['startBasis']=='explicit'
                 and n['startBasis']=='explicit' and n['end'] and n['workSite']
                 and not n['workSite'].startswith('неуточн:') and not n['reviewRequired']
                 and not e['reviewRequired'] and signature(e)==signature(n)]
        if len(matches)==1:
            e=matches[0];duplicates+=1
            e['evidence']=list(dict.fromkeys(e['evidence']+[n['url']]))
            e['updates'].append(n['id'])
            rank={'verified_repost':3,'municipal_repost':2,'media_report':1}
            if rank.get(n['origin'],4)>rank.get(e['origin'],4):
                for field in ('url','officialUrl','source','sourceId','origin','text','textSha256','publishedAt'):
                    if field in n:e[field]=n[field]
            continue
        e=deepcopy(n);e['noticeId']=n['id'];e['id']='water-'+n['id'].replace('/','-')
        e.update(category='water',status='active',revision=1,evidence=[n['url']]+n.get('additionalSources',[]),updates=[n['id']])
        e['point']=None;e['precision']='street' if n['affected'] else 'unresolved'
        e['description']=clean(n['text'])[:440];e['title']='Плановые работы: вода' if n['kind']=='planned' else 'Ограничение водоснабжения'
        incidents.append(e)
    live=[]
    for e in incidents:
        if e['status']=='resolved':continue
        start=datetime.fromisoformat(e['start']) if e['start'] else None
        end=datetime.fromisoformat(e['end']) if e['end'] else None
        pub=datetime.fromisoformat(e['publishedAt'])
        if end and end<now-timedelta(hours=36):continue
        if not end and now-pub>=timedelta(hours=36):continue
        if e['kind']=='planned' and start and start>now+timedelta(days=14):continue
        if end and end<now:e['status']='unconfirmed'
        live.append(e)
    return {'schema':2,'checkedAt':now.isoformat(),'events':live,'incidents':incidents,'notices':notices,'unlinked':unlinked,'duplicatePublications':duplicates,'revisionConflicts':revision_conflicts,'candidateOnly':True}
