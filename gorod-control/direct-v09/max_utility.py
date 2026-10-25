"""Addressed public MAX notices. No general city news or guessed coverage."""
import re
from datetime import datetime, timedelta
from power_direct import addresses
from service_events import CITY, classify_power, incident_time
from collect_water import schedule
from secondary_water import split_notices

URLS={'max_water':'https://max.ru/id6167110467_gos','max_city':'https://max.ru/shakhtygorod','max_power':'https://max.ru/id6163089292_biz'}

def trusted(post):
    return post.get('origin')=='official_max' and post.get('sourceId') in URLS and post.get('url')==URLS[post['sourceId']]

def water_posts(posts):
    out=[]
    for p in posts:
        if not trusted(p) or p['sourceId'] not in ('max_city','max_water'):continue
        text=p['text']
        # The URSV channel covers many towns. Require an explicit Shakhty branch/city.
        if p['sourceId']=='max_water' and not re.search(r'\bШахты\b|\bШахтинск[а-я]*\b|\bФШ\s+ГУП\b',text,re.I):continue
        if not re.search(r'водоснабж|водовод|водопровод|подач[а-я]*\s+вод',text,re.I):continue
        if not re.search(r'сниж\w*\s+давлен|отключ\w*\s+вод|водоснабжение\s+(?:восстановлено|приостановлено)|подача воды возобновлена|работы\s+(?:продлены|завершены)',text,re.I):continue
        sections=split_notices(text)
        for i,section in enumerate(sections):
            out.append({**p,'id':p['id']+('/'+str(i) if len(sections)>1 else ''),'text':section})
    return out

def power_areas(text):
    m=re.search(r'(?:в\s+границах|отключени[ею]\s+потребителей|по следующим (?:улицам|адресам))\s*:\s*(.+)',text,re.I|re.S)
    if not m:return [],['Адресный охват не указан']
    block=re.split(r'Ориентировочн|Напоминаем|Приносим|Источник|#',m[1],maxsplit=1,flags=re.I)[0].strip(' \n*')
    parts=[]
    for part in re.split(r'[,;\n]',block):
        part=part.strip(' .•▫️*')
        if not part:continue
        if parts and re.fullmatch(r'\d+[а-я]?(?:/\d+)?(?:\s*[-–]\s*\d+[а-я]?)?',part,re.I):parts[-1]+=', '+part
        else:parts.append(part)
    cleaned=[]
    for part in parts:
        part=re.sub(r'^пр\.\s*','проспект ',part,flags=re.I)
        part=re.sub(r'^(пр-т|пр-кт)\.\s*',r'\1 ',part,flags=re.I)
        cleaned.append(part)
    found,issues=addresses(';'.join(cleaned))
    return found,issues

def power_posts(posts,now):
    out=[]
    for p in posts:
        if not trusted(p) or not CITY.search(p['text'][:500]):continue
        text=p['text'];kind=classify_power(text)
        if kind not in ('emergency','planned','resolved'):continue
        published=datetime.fromisoformat(p['publishedAt'])
        if not timedelta(0)<=now-published<timedelta(days=16):continue
        impact,issues=power_areas(text)
        if not impact:continue
        if kind=='planned':
            start,end=schedule(text,published,kind)
            if not start:continue
            start=datetime.fromisoformat(start);end=datetime.fromisoformat(end) if end else None
        else:
            start=incident_time(text,published);end=None
            duration=re.search(r'ориентировочн[^\n]{0,100}в течение\s+(?:(\d{1,2})\s*час\w*\s*)?(?:(\d{1,2})\s*минут\w*)?',text,re.I)
            if duration and (duration[1] or duration[2]):
                end=start+timedelta(hours=int(duration[1] or 0),minutes=int(duration[2] or 0))
        if (end or start)+timedelta(hours=36)<=now or start>now+timedelta(days=14):continue
        out.append({'id':p['id']+'-power','category':'power','kind':'emergency' if kind=='resolved' else kind,
          'status':'resolved' if kind=='resolved' else 'active','sourceId':p['sourceId'],'source':p['source'],
          'origin':'official_max','url':p['url'],'officialUrl':p['url'],'publishedAt':p['publishedAt'],
          'start':start.isoformat(),'end':end.isoformat() if end else None,'endBasis':'estimated' if end else 'unknown',
          'title':'Плановое отключение электричества' if kind=='planned' else 'Аварийное отключение электричества',
          'description':re.sub(r'\s+',' ',text)[:440],'fullText':text,'affected':impact,
          'unmappedAreaText':issues,'requiresReview':bool(issues),'point':None,'precision':'street'})
    return out
