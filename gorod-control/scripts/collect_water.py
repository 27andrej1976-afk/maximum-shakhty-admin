#!/usr/bin/env python3
"""Verified public notices from Shakhty water utility's Telegram web page.
Only municipal public messages are processed; no user coordinates or home are uploaded.
"""
import json, re, sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE='https://t.me/s/shakhtinskiy'
OUTPUT=Path(__file__).resolve().parents[1]/'data'/'water.json'
MSK=timezone(timedelta(hours=3))
MARK=re.compile(r'^(?:🗺\s*)?адрес(?:а|ы)?\s*[:：]?\s*$',re.I)
STOP=re.compile(r'^(?:ℹ|🔗|🔧|⚠|📌|телефон|подвоз|подробнее|ориентировоч|работы завершен|причина)',re.I)
STREET=re.compile(r'^(?:(?:г\.?\s*шахты|шахты)\s*,?\s*)?(?P<pre>ул\.?|улица|пер\.?|переулок|проспект|пр-кт|пр-т|пр\.|пр-д|проезд|пл\.?|площадь|мкр\.?|посёлок|поселок)\s+(?P<rest>.+)$',re.I)
HOUSE=re.compile(r'^(.*?)\s+(?:д\.?\s*)?(\d+[а-яa-z]?(?:\s*[-–]\s*\d+[а-яa-z]?)?(?:\s*,\s*\d+[а-яa-z]?)*)\s*\.?$',re.I)
DATE=re.compile(r'\b([0-3]?\d)\s*[./]\s*([01]?\d)\s*[./]\s*(20\d{2})\b')
MONTHS={s:i+1 for i,s in enumerate('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split())}

class Page(HTMLParser):
    def __init__(self,channel='shakhtinskiy'):
        super().__init__(convert_charrefs=True)
        self.channel=channel
        self.result=[];self.d=0;self.t=0;self.parts=[];self.current=None
    def handle_starttag(self,tag,attrs):
        at=dict(attrs);classes=at.get('class','').split()
        if tag=='div' and 'tgme_widget_message_wrap' in classes and not self.d:
            self.current={'id':None,'time':None,'text':''};self.d=1;return
        if not self.current:return
        if tag=='div':
            self.d+=1
            if 'tgme_widget_message_text' in classes and not self.t:
                self.t=1;self.parts=[]
            elif self.t:self.t+=1
        elif tag=='time':self.current['time']=at.get('datetime') or self.current['time']
        elif tag=='br' and self.t:self.parts.append('\n')
        elif tag in ('p','blockquote','li') and self.t:self.parts.append('\n')
        if at.get('data-post') and not self.current['id']:self.current['id']=at['data-post']
    def handle_endtag(self,tag):
        if not self.current:return
        if tag=='div':
            if self.t:
                self.t-=1
                if not self.t:self.current['text']=''.join(self.parts)
            self.d-=1
            if not self.d:
                m=self.current
                if m['id'] and m['id'].startswith(self.channel+'/') and m['text'].strip() and m['time']:
                    self.result.append(m)
                self.current=None
        elif tag in ('p','blockquote','li') and self.t:self.parts.append('\n')
    def handle_data(self,data):
        if self.t:self.parts.append(data)

def parse_html(html,channel='shakhtinskiy'):
    parser=Page(channel);parser.feed(html);out=[]
    for p in parser.result:
        try:
            stamp=datetime.fromisoformat(p['time'].replace('Z','+00:00'))
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=MSK)
        except ValueError:continue
        text=re.sub(r'\n\s*\n+','\n',re.sub(r'[ \t]+',' ',p['text']).replace('\xa0',' ')).strip()
        out.append({'id':p['id'],'publishedAt':stamp.isoformat(),'text':text,'url':'https://t.me/'+p['id']})
    return out

def parse_affected(text):
    out={};section=False
    for raw in text.splitlines():
        line=raw.replace('\ufe0f','').strip(' \t\r▫▪•-–')
        if MARK.fullmatch(line):section=True;continue
        if not section and re.search(r'(?:в направлении(?: следующих улиц)?|по адресам|остан(?:овлено|овка) водоснабжения|без водоснабжения оста(?:ются|лись))\s*[:：]',line,flags=re.I):
            section=True
            tail=line.rsplit(':',1)[-1].strip()
            if not tail:continue
            line=tail
        if not section:continue
        if STOP.match(line):break
        if not line:continue
        for entry in re.split(r',\s*(?=(?:г\.?\s*шахты\s*,\s*)?(?:ул\.?|улица|пер\.?|переулок|пр-?кт|проспект|пр\.|пр-д)\s+)',line,flags=re.I):
            entry=re.sub(r'\s+и\s+прилегающ.*$','',entry,flags=re.I).strip(' ;,.')
            found=STREET.match(entry)
            if not found:continue
            tail=found['rest'];h=HOUSE.match(tail)
            if h:
                tail=h[1].rstrip(' ,.')
                numbers=[re.sub(r'\s+','',s).lower() for s in h[2].split(',')]
            else:numbers=[]
            name=found['pre']+' '+tail
            if len(name)>90:continue
            key=name.lower()
            if key not in out:out[key]={'street':name,'houses':[]}
            out[key]['houses']=sorted(set(out[key]['houses']+numbers))
    return list(out.values())[:100]

def classify(text):
    t=text.lower()
    if re.search(r'работы\s+завершен|водоснабжение\s+восстановлен|восстановлени[ея]\s+(?:давления|водоснабжения)|подача воды возобновлен',t):return 'resolved'
    if re.search(r'продлен|продлева|изменени[ея] сроков',t):return 'extension'
    if re.search(r'планов|запланирова|предстоящ|профилактическ',t):return 'planned'
    if re.search(r'отключени[ея]\s+вод|снижени[ея]\s+давлен|водоснабжение\s+приостановлен|ремонтн|аварийн',t):return 'emergency'
    return None

def schedule(text,published,kind):
    local=published.astimezone(MSK);days=[]
    for m in DATE.finditer(text):
        try:days.append(datetime(int(m[3]),int(m[2]),int(m[1]),tzinfo=MSK))
        except ValueError:pass
    pattern=r'\b([0-3]?\d)\s+('+'|'.join(MONTHS)+r')\s+(20\d{2})\b'
    for m in re.finditer(pattern,text,flags=re.I):
        try:days.append(datetime(int(m[3]),MONTHS[m[2].lower()],int(m[1]),tzinfo=MSK))
        except ValueError:pass
    short_months=r'\b([0-3]?\d)\s+('+'|'.join(MONTHS)+r')\b'
    for m in re.finditer(short_months,text,flags=re.I):
        for year in (local.year-1,local.year,local.year+1):
            try:
                d=datetime(year,MONTHS[m[2].lower()],int(m[1]),tzinfo=MSK)
                if -timedelta(days=1) <= d-local <= timedelta(days=40):days.append(d)
            except ValueError:pass
    if days:day=min(days,key=lambda d:abs((d-local).total_seconds()))
    elif kind=='planned':return None,None
    else:day=local
    start_match=re.search(r'\bс\s+([01]?\d|2[0-3])\s*[:.\-]\s*([0-5]\d)\b',text,flags=re.I)
    end_match=re.search(r'(?:ориентировочн[^\n]{0,90}?(?:завершения|окончания)|продлен[^\n]{0,25}?до|\bдо\b)\s*[^\d\n]{0,15}(\d{1,2})\s*[:.\-]\s*([0-5]\d)',text,flags=re.I)
    start=day.replace(hour=int(start_match[1]),minute=int(start_match[2])) if start_match else (day.replace(hour=0,minute=0) if kind=='planned' else local)
    end=day.replace(hour=int(end_match[1]),minute=int(end_match[2])) if end_match else None
    if end_match:
        explicit_end=re.search(r'\bдо\s+\d{1,2}\s*[:.\-]\s*\d{2}\s+([0-3]?\d)\s+('+'|'.join(MONTHS)+r')',text,flags=re.I)
        if explicit_end:
            try:
                e_day=datetime(day.year,MONTHS[explicit_end[2].lower()],int(explicit_end[1]),tzinfo=MSK)
                if e_day<day:e_day=e_day.replace(year=day.year+1)
                end=e_day.replace(hour=int(end_match[1]),minute=int(end_match[2]))
            except ValueError:pass
    if end and end<start:end+=timedelta(days=1)
    return start.isoformat(),end.isoformat() if end else None

def feed(messages,now=None):
    now=now or datetime.now(timezone.utc)
    messages=sorted(messages,key=lambda x:x['publishedAt'],reverse=True)
    recent=[];events=[]
    for m in messages:
        kind=classify(m['text'])
        if not kind:continue
        areas=parse_affected(m['text']);published=datetime.fromisoformat(m['publishedAt'])
        desc=re.sub(r'\s+',' ',m['text'])[:340]
        recent.append({'id':m['id'],'publishedAt':m['publishedAt'],'url':m['url'],'kind':kind,'affected':areas,'description':desc})
        if kind=='resolved' or not areas:continue
        start,end=schedule(m['text'],published,kind)
        if not start:continue
        if kind!='planned' and now-published>timedelta(hours=48):continue
        if kind=='planned' and not (-timedelta(days=1)<=datetime.fromisoformat(start)-now<=timedelta(days=14)):continue
        if kind!='planned' and end and datetime.fromisoformat(end)<now:continue
        events.append({'id':'water-'+m['id'].replace('/','-'),'kind':'planned' if kind=='planned' else 'emergency',
            'status':'active','category':'water','source':('Шахтинский водоканал' if m['id'].startswith('shakhtinskiy/') else 'Администрация города Шахты'),
            'title':'Плановые работы: вода' if kind=='planned' else 'Сообщение водоканала: вода',
            'description':desc,'start':start,'end':end,'point':None,'affected':areas,
            'url':m['url'],'publishedAt':m['publishedAt'],'precision':'street'})
    def streets(areas):
        return {re.sub(r'^(?:ул\.?|улица|пер\.?|переулок|проспект|пр-?кт|пр\.|пр-д)\s+','',x['street'],flags=re.I).lower().replace('ё','е') for x in areas}
    closed=[m for m in recent if m['kind']=='resolved']
    events=[e for e in events if not any(
        0<=(datetime.fromisoformat(c['publishedAt'])-datetime.fromisoformat(e['publishedAt'])).total_seconds()<259200
        and bool(streets(e['affected'])&streets(c['affected'])) for c in closed)]
    return {'schema':2,'checkedAt':now.isoformat(),'sources':[{
        'id':'water','status':'ok','posts':len(messages),'lastPostAt':messages[0]['publishedAt'] if messages else None,
        'url':SOURCE,'note':'Официальный публичный канал, автоматический сбор'}],
        'events':events,'recent':recent[:12]}

def main():
    now=datetime.now(timezone.utc)
    all_posts=[]
    states=[]
    for channel in ('shakhtinskiy','admshakhty'):
        url='https://t.me/s/'+channel
        try:
            req=Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})
            with urlopen(req,timeout=20) as resp:
                html=resp.read(2000000).decode('utf-8','replace')
            raw=parse_html(html,channel)
            if not raw:raise RuntimeError('No recognisable public messages')
            if channel=='admshakhty':
                seen={m['id'] for m in raw}
                for page_no in range(3):
                    numbers=[int(m['id'].split('/')[-1]) for m in raw if m['id'].split('/')[-1].isdigit()]
                    if not numbers:break
                    page_url=url+'?before='+str(min(numbers))
                    try:
                        with urlopen(Request(page_url,headers={'User-Agent':'Mozilla/5.0'}),timeout=12) as more_resp:
                            older=parse_html(more_resp.read(2000000).decode('utf-8','replace'),channel)
                    except Exception as page_error:
                        print('History unavailable:',page_no,str(page_error)[:70]);break
                    extra=[m for m in older if m['id'] not in seen]
                    if not extra:break
                    raw.extend(extra);seen.update(m['id'] for m in extra)
                    if min(datetime.fromisoformat(m['publishedAt']) for m in extra)<now-timedelta(days=20):break
            most_recent=max(datetime.fromisoformat(x['publishedAt']) for x in raw)
            days_old=(now-most_recent).total_seconds()/86400
            if channel=='admshakhty':
                relevant=[m for m in raw if re.search(r'водоснаб|водоканал|УРСВ|снижено давление|отключени[ея] воды',m['text'],re.I)]
            else:relevant=raw
            all_posts.extend(relevant)
            states.append({'id':'water' if channel=='shakhtinskiy' else 'city',
                'status':'ok' if -1<=days_old<7 else 'stale',
                'posts':len(raw),'matchingPosts':len(relevant),
                'lastPostAt':most_recent.isoformat(),'url':url,
                'note':('Публичные публикации водоканала' if channel=='shakhtinskiy' else 'Публичные публикации администрации Шахт')})
            print(channel,'read',len(raw),'last',most_recent.isoformat(),'water',len(relevant))
        except Exception as exc:
            print('SOURCE ERROR',channel,exc,file=sys.stderr)
            states.append({'id':'water' if channel=='shakhtinskiy' else 'city',
                           'status':'error','posts':0,'url':url,'note':str(exc)[:140]})
    if all_posts:
        result=feed(all_posts,now)
        result['sources']=states
    else:
        try:result=json.loads(OUTPUT.read_text(encoding='utf-8'))
        except Exception:result={'schema':2,'checkedAt':None,'events':[],'recent':[]}
        result['sources']=states
        result['fetchAttemptAt']=now.isoformat()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Filtered current water notices',len(result['events']))
    return 0

if __name__=='__main__':sys.exit(main())
