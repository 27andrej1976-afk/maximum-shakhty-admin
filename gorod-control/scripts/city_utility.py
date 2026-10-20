"""Official Shakhty administration as supplemental source for electricity/gas notices."""
import re
from datetime import datetime,timedelta,timezone
from urllib.request import Request,urlopen
from collect_water import parse_html,parse_affected,schedule
from service_events import affected_power,incident_time

CHANNEL='https://t.me/s/admshakhty'
CITY_POWER=re.compile(r'(?:отключени\w*\s+электроснабж|планов\w*\s+работ\w*\s+в\s+сетях\s+электроснабж|технологическ\w*\s+нарушени\w*\s+в\s+сети|отключени\w*\s+электроэнерг|отключени\w*\s+электричеств)',re.I)
CITY_GAS=re.compile(r'(?:отключени\w*\s+газоснабж|прекращен\w*\s+(?:подач\w*\s+)?газа|приостановлен\w*\s+газоснабж|подач\w*\s+газа\s+будет\s+(?:приостановлен|прекращен)|аварийн\w*\s+работ\w*\s+на\s+газопровод)',re.I)
STREET_START=re.compile(r'^\s*(?:[•*✔️▫️🔹-]\s*)?(?:ул\.?|улица|пер\.?|переулок|проспект|просп\.?|пр-кт|пр-т|проезд|пр-д|пл\.?|пос\.?)\s+\S+',re.I)
MSK=timezone(timedelta(hours=3))

def detect(text):
    lower=text.lower()
    if CITY_GAS.search(lower):return 'gas'
    if CITY_POWER.search(lower):return 'power'
    return None

def affected(text):
    found=parse_affected(text)
    if found:return found
    found=affected_power(text)
    if found:return found
    # Some municipal posts list streets as bullets after 'по следующим улицам:'
    lines=text.splitlines()
    blocks=[];record=False
    for line in lines:
        if re.search(r'(?:по\s+следующим\s+улицам|по\s+следующим\s+адресам|в\s+границах|под\s+отключени\w*)\s*:',line,re.I):
            record=True
            tail=line.split(':',1)[1].strip()
            if tail:blocks.append(tail)
            continue
        if record and (line.strip().startswith('#') or re.match(r'\s*(?:Приносим|Ориентировочн|Напоминаем|Телефон|Источник)',line,re.I)):break
        if record and STREET_START.match(line):blocks.append(line.strip())
    if not blocks:return []
    return parse_affected('Адреса:\n'+'\n'.join(blocks)+'\nПодробности')

def parse_posts(posts,now):
    events=[]
    for p in posts:
        cat=detect(p.get('text',''))
        if not cat:continue
        published=datetime.fromisoformat(p['publishedAt'])
        delta=now-published
        if delta<-timedelta(minutes=20) or delta>timedelta(days=14):continue
        text=p['text']
        areas=affected(text)
        if not areas:continue
        planned=bool(re.search(r'планов|запланирован|будет\s+произведен|будет\s+отключен',text,re.I))
        kind='planned' if planned else 'emergency'
        if kind=='planned':
            start,end=schedule(text,published,kind)
            if not start:continue
            begin=datetime.fromisoformat(start)
            if not -timedelta(days=1)<=begin-now<=timedelta(days=14):continue
        else:
            if delta>timedelta(hours=48):continue
            start=incident_time(text,published).isoformat()
            end=None
        events.append({'id':'city-'+cat+'-'+p['id'].split('/')[-1],
            'category':cat,'kind':kind,'status':'active',
            'title':('Плановое' if planned else 'Аварийное')+
              (' отключение газа' if cat=='gas' else ' отключение электроэнергии'),
            'source':'Администрация города Шахты','sourceId':cat+'_city',
            'origin':'official_city_post','description':re.sub(r'\s+',' ',text)[:440],
            'publishedAt':p['publishedAt'],'url':p['url'],'affected':areas,
            'start':start,'end':end,'point':None,'precision':'street'})
    return events

def collect_city(now):
    posts=[]
    seen=set()
    try:
        url=CHANNEL
        for page in range(4):
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=11) as r:
                data=r.read(1_500_000).decode('utf-8','replace')
            part=parse_html(data,'admshakhty')
            extra=[p for p in part if p['id'] not in seen]
            if not extra:break
            posts.extend(extra);seen.update(p['id'] for p in extra)
            oldest=min(datetime.fromisoformat(p['publishedAt']) for p in extra)
            if oldest<now-timedelta(days=16):break
            ids=[int(p['id'].split('/')[-1]) for p in part if p['id'].split('/')[-1].isdigit()]
            if not ids:break
            url=CHANNEL+'?before='+str(min(ids))
        recent=[p for p in posts if abs((now-datetime.fromisoformat(p['publishedAt'])).total_seconds())<16*86400]
        events=parse_posts(recent,now)
        latest=max((p['publishedAt'] for p in posts),default=None)
        states=[]
        for cat in ('power','gas'):
            n=len([e for e in events if e['category']==cat])
            states.append({'id':cat+'_city','status':'ok' if n else 'partial',
             'url':CHANNEL,'readStatus':'ok' if posts else 'error','coverage':'partial','posts':len(posts),'matchingPosts':n,
             'lastPostAt':latest if n else None,
             'note':'Официальный канал администрации Шахт; отбираются только адресные сообщения о '+('свете' if cat=='power' else 'газе')})
        return events,states
    except Exception as exc:
        return [],[{'id':cat+'_city','status':'error','url':CHANNEL,'posts':0,
             'note':'Сведения администрации недоступны: '+str(exc)[:105]} for cat in ('power','gas')]
