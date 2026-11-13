"""Conservative source templates -> GAR-bound proposals, never guessed locations.

Unsupported text, missing/ambiguous settlement/street, image-only addresses and
unmatched restorations stay pending. Boilerplate about future restoration is
not a confirmation. Gazetteer and original post hashes are mandatory.
"""
import gzip
import json
import re
from collections import defaultdict
from datetime import timedelta, timezone
from pathlib import Path
from core import utc

LABELS={'water':'Вода','power':'Свет','mchs':'МЧС'}
PREFIX=r'(?:\bг\.?|\bгород|\bп\.?|\bпос\.?|\bпоселок|\bх\.?|\bхутор|\bст-ца|\bст\.?|\bстаница|\bс\.?|\bсело|\bрп\.?)\s*'
STREET=re.compile(r'(?<!\w)(ул(?:ица)?|просп(?:ект)?|пр-т|пр\.т|пер(?:еулок)?|бул(?:ьвар)?|пл(?:ощадь)?|шоссе|проезд|пр-д)(?:\.\s*|\s+)',re.I)
TYPES={'ул':'ул.','улица':'ул.','просп':'пр-кт','проспект':'пр-кт','пр-т':'пр-кт','пр.т':'пр-кт',
       'пер':'пер.','переулок':'пер.','бул':'б-р','бульвар':'б-р','пл':'пл.','площадь':'пл.',
       'шоссе':'ш.','проезд':'проезд','пр-д':'проезд'}


def norm(text):
    return re.sub(r'[^а-яa-z0-9]+',' ',str(text).lower().replace('ё','е')).strip()


def evidence(post):
    if post.get('text','').strip():return post['text'],post['publishedAt'],False
    if post.get('forwarded'):
        for item in post.get('linkedContent',[]):
            if item.get('kind')=='FORWARD' and item.get('text','').strip():
                return item['text'],item.get('publishedAt') or post['publishedAt'],True
    return '',post['publishedAt'],False


class Templates:
    def __init__(self,index):
        self.index=index
        self.cities={c['id']:c for c in index['municipalities']}
        self.names=defaultdict(list);self.streets=defaultdict(list)
        for c in self.cities.values():self.names[norm(c['name'])].append(c)
        names=sorted(self.names,key=len,reverse=True)
        self.mention=re.compile(PREFIX+'('+ '|'.join(re.escape(n) for n in names)+r')(?![а-яa-z0-9])',re.I)
        for street in index['streets']:self.streets[street['municipalityId']].append(street)

    def city(self,text):
        clean=norm(text);found={}
        for hit in self.mention.finditer(clean):
            options=self.names[norm(hit.group(1))]
            if len(options)>1:
                options=[c for c in options if any(norm(d) in clean for d in c.get('districts',[]))]
            if len(options)==1:found[options[0]['id']]=options[0]
            else:return None
        return next(iter(found.values())) if len(found)==1 else None

    def addresses(self,body,city):
        hits=list(STREET.finditer(body));found={};unknown=[]
        for n,hit in enumerate(hits):
            tail=body[hit.end():hits[n+1].start() if n+1<len(hits) else len(body)]
            raw=re.split('[,;\\n]',tail)[0].strip(' .:—–-')
            candidate=norm(raw);typ=TYPES[hit.group(1).lower()]
            matching=[s for s in self.streets[city['id']] if s['type']==typ
                      and (candidate==norm(s['name']) or candidate.startswith(norm(s['name'])+' '))]
            if matching:
                longest=max(len(norm(s['name'])) for s in matching)
                matching=[s for s in matching if len(norm(s['name']))==longest]
            matched_name = None
            if len(matching)==1: matched_name=norm(matching[0]['name'])
            elif not matching:
                # Only a unique first-name initial or omitted first name,
                # within the already exact GAR locality and street type.
                aliases=[]
                for street in self.streets[city['id']]:
                    parts=norm(street['name']).split()
                    if street['type']!=typ or len(parts)!=2 or not all(x.isalpha() for x in parts):continue
                    for alias in (parts[1], parts[0][0]+' '+parts[1]):
                        if candidate==alias or candidate.startswith(alias+' '):aliases.append((street,alias))
                if len({street['id'] for street,alias in aliases})==1 and aliases:
                    matching=[aliases[0][0]];matched_name=max((a for st,a in aliases),key=len)
            if len(matching)!=1 or matched_name is None:
                unknown.append(hit.group(0)+raw);continue
            s=matching[0]
            house_tail=candidate[len(matched_name):].strip()
            # Geometry is independent of existence in GAR. Source house/range
            # remains text; a street point must never claim a verified house.
            found[s['id']]={'id':s['id'],'municipalityId':city['id'],'streetId':s['id'],
                'label':s['type']+' '+s['name'],'name':s['name'],'type':s['type'],
                'sourceAddress':hit.group(0)+raw,'houseRangeSpecified':bool(re.search(r'\d',house_tail)),'verified':True,'geometryVerified':False,
                'locationPrecision':'street','verification':'GAR '+self.index['version']}
        return list(found.values()),unknown

    def propose(self,post,source):
        text,content_time,forwarded=evidence(post)
        result={'state':'pending','reason':'UNSUPPORTED_FORMAT','text':text,'contentPublishedAt':content_time}
        if not text.strip():return dict(result,reason='ATTACHMENT_OR_EMPTY_TEXT')
        # A reposted old notice never becomes a fresh incident at wrapper time.
        if utc(content_time)>utc(post['publishedAt'])+timedelta(minutes=5):return dict(result,reason='INVALID_CONTENT_TIME')
        cat=next(iter(source['categories']))
        if cat=='mchs':
            months={'января':1,'февраля':2,'марта':3,'апреля':4,'мая':5,'июня':6,
                    'июля':7,'августа':8,'сентября':9,'октября':10,'ноября':11,'декабря':12}
            dates=re.findall(r'(?<!\d)(\d{1,2})\s+('+ '|'.join(months)+')',text.lower())
            if (source.get('regionCoverageVerified') and 'штормовое предупреждение' in text.lower()
                    and 'Ростовской области' in text and len(set(dates))==1):
                day,month=dates[0];pub=utc(content_time).astimezone(timezone(timedelta(hours=3)))
                try:start=pub.replace(month=months[month],day=int(day),hour=0,minute=0,second=0,microsecond=0)
                except ValueError:return dict(result,reason='INVALID_FORECAST_DATE')
                if timedelta(days=-1)<=start-pub<=timedelta(days=7):
                    return dict(result,state='incident',reason='DATED_REGIONAL_WEATHER_WARNING',category=cat,
                        city=None,scope='region',addresses=[],unresolvedAddresses=[],start=start.isoformat(),
                        end=(start+timedelta(days=1)).isoformat(),title='Штормовое предупреждение · Ростовская область')
            return dict(result,reason='MCHS_SCOPE_OR_OFFICIAL_EXPIRY_REVIEW')
        lower=text.lower().replace('ё','е')
        # Strict affirmative wording, not "будет возобновлено без предупреждения".
        restore=bool(re.search(r'(?:электроснабжение|водоснабжение|подача\s+воды)\s+(?:полностью\s+)?восстановлен[аоы]?\b|уведомляем\s+о\s+восстановлении\s+(?:холодного\s+)?водоснабжения',lower))
        outage=(cat=='power' and 'произошло технологическое нарушение' in lower and 'отключени' in lower
                or cat=='water' and 'отключение воды' in lower)
        if not restore and not outage:
            relevant=forwarded or re.search(r'отключ|водоснабж|электроснабж|подвоз[а-я]*\s+вод|порыв|ограничен|подач[аиу]\s+вод',lower)
            return dict(result,state='pending' if relevant else 'information',reason='NO_CURRENT_OUTAGE_TEMPLATE')
        city=self.city(text)
        if not city:return dict(result,reason='MISSING_OR_AMBIGUOUS_GAR_LOCALITY')
        if 'Адреса:' in text:
            body=text.split('Адреса:',1)[1];body=re.split(r'ℹ|🔗|⏱',body)[0]
        elif cat=='power':
            m=re.search(r'(?:в границах\s*:|в границах|потребителей по)\s*(.*?)(?:\n\s*\n|Ориентировочное)',text,re.I|re.S)
            if not m:return dict(result,reason='MISSING_AFFECTED_ADDRESS_BLOCK')
            body=m.group(1)
        else:return dict(result,reason='MISSING_AFFECTED_ADDRESS_BLOCK')
        addresses,unresolved=self.addresses(body,city)
        if not addresses:return dict(result,reason='UNRESOLVED_GAR_STREETS')
        start=utc(content_time)
        if cat=='power':
            t=re.search(r'\bв\s+(\d{1,2}):(\d{2})\s+произошло',text)
            if t:
                local=start.astimezone(timezone(timedelta(hours=3)))
                try:start=local.replace(hour=int(t[1]),minute=int(t[2]),second=0,microsecond=0)
                except ValueError:return dict(result,reason='INVALID_START_TIME')
                if start>utc(content_time)+timedelta(minutes=5):return dict(result,reason='START_AFTER_PUBLICATION')
        end=None
        t=re.search(r'в течение\s+(\d{1,2})\s+час',text,re.I)
        if t and 0<int(t[1])<=24:end=start+timedelta(hours=int(t[1]))
        else:
            t=re.search(r'Ориентировочное время завершения работ\s+(\d{1,2})[:-](\d{2})',text,re.I)
            if t:
                local=start.astimezone(timezone(timedelta(hours=3)))
                try:proposed=local.replace(hour=int(t[1]),minute=int(t[2]),second=0,microsecond=0)
                except ValueError:return dict(result,reason='INVALID_END_TIME')
                if proposed>=start:end=proposed
        # The public source's own text can be parsed; anonymous forwarded content
        # is kept but requires operator provenance confirmation before events.
        if forwarded:return dict(result,reason='FORWARDED_PROVENANCE_REVIEW',city=city,addresses=addresses)
        return dict(result,state='restoration' if restore else 'incident',reason='SOURCE_TEMPLATE_GAR_MATCH',category=cat,city=city,
                    addresses=addresses,unresolvedAddresses=unresolved,start=start.isoformat(),
                    end=end.isoformat() if end else None,title=LABELS[cat]+' · '+city['name'])


def load_index(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))
