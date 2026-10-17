"""Direct official Donenergo schedule. Verified TLS, no news mirrors or credentials."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request,urlopen
import hashlib,json,re,ssl,time
URL='https://donenergo.ru/grafik-otklyucheniy/61/1/'
MSK=timezone(timedelta(hours=3))
class Table(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.rows=[];self.row=None;self.cell=None;self.depth=0
 def handle_starttag(self,t,a):
  if t=='table':self.depth+=1
  if self.depth and t=='tr':self.row=[]
  if self.depth and t=='td':self.cell=[]
  if self.cell is not None and t in ('br','p','div'):self.cell.append('\n')
 def handle_data(self,d):
  if self.cell is not None:self.cell.append(d)
 def handle_endtag(self,t):
  if t=='td' and self.cell is not None:
   if self.row is not None:self.row.append(''.join(self.cell).strip())
   self.cell=None
  if t=='tr' and self.row:self.rows.append(self.row);self.row=None
  if t=='table':self.depth=max(0,self.depth-1)
def clean(x):return re.sub(r'\s+',' ',x).strip()
def stamp(d,t):
 date=datetime.strptime(d.strip(),'%d.%m.%y' if len(d.strip().split('.')[-1])==2 else '%d.%m.%Y')
 m=re.fullmatch(r'(\d{1,2})\s*[:=.]\s*(\d{2})',t.strip())
 if not m:raise ValueError('Unrecognised time')
 return date.replace(hour=int(m[1]),minute=int(m[2]),tzinfo=MSK)
def addresses(raw):
 areas=[];issues=[]
 for part in re.split(r';|\n',raw):
  part=clean(part).strip(' .;,')
  if not part:continue
  m=re.fullmatch(r'(ул\.?|улица|пер\.?|переулок|просп\.?|проспект|пр-кт|пр-т|проезд|пр-д)\s*(.+)',part,re.I)
  if not m:issues.append(part);continue
  typ=m[1].lower();typ='проспект' if typ in ('просп','просп.','пр-кт','пр-т') else typ
  n=re.fullmatch(r'(.*?)\s*(\d+[а-яa-z]?(?:/\d+[а-яa-z]?)?(?:\s*[-–]\s*\d+[а-яa-z]?)?(?:\s*,\s*\d+[а-яa-z]?(?:/\d+[а-яa-z]?)?(?:\s*[-–]\s*\d+[а-яa-z]?)?)*)',m[2],re.I)
  houses=[];invalid=[]
  if n:
   name=n[1].strip(' ,.')
   for v in n[2].split(','):
    v=re.sub(r'\s+','',v).replace('–','-').lower();r=re.fullmatch(r'(\d+)-(\d+)',v)
    if r and int(r[1])>int(r[2]):invalid.append(v)
    else:houses.append(v)
  else:name=m[2].strip(' .,;')
  if not name:issues.append(part);continue
  area={'street':typ+' '+name,'houses':houses}
  if invalid:
   area.update(housesUncertain=True,invalidHouses=invalid);issues.append(part+' — обратный диапазон в первоисточнике, нужна сверка')
  areas.append(area)
 return areas,issues

def parse(html,now=None):
 now=now or datetime.now(timezone.utc);table=Table();table.feed(html)
 events=[];notes=[];rejected=[];read=0
 for row in table.rows:
  if len(row)!=9 or not re.fullmatch(r'(?:г\.?\s*)?Шахты',clean(row[1]),re.I):continue
  read+=1
  if not row[2]:
   if 'заявок' in row[7].lower() and 'нет' in row[7].lower():notes.append(clean(row[7]))
   continue
  try:start,end=stamp(row[3],row[5]),stamp(row[4],row[6])
  except Exception:rejected.append({'row':row[0],'reason':'Нераспознанные дата/время'});continue
  if end<start:rejected.append({'row':row[0],'reason':'Конец раньше начала'});continue
  if end<now-timedelta(hours=24) or start>now+timedelta(days=14):continue
  impact,issues=addresses(row[2])
  if not impact:rejected.append({'row':row[0],'reason':'Не распознаны адреса'});continue
  evidence='\n'.join([row[1],row[2],row[3]+' '+row[5]+' — '+row[4]+' '+row[6],row[7],row[8]])
  ident=hashlib.sha256((start.isoformat()+'|'+row[2]+'|'+row[7]).encode()).hexdigest()[:18]
  events.append({'id':'power-direct-'+ident,'category':'power','kind':'planned',
   'status':'unconfirmed' if end<now else 'active','sourceId':'power_direct',
   'source':'Донэнерго · официальный график ШМЭС','origin':'official_site','url':URL,'officialUrl':URL,
   'publishedAt':None,'observedAt':now.isoformat(),'start':start.isoformat(),'end':end.isoformat(),
   'startBasis':'explicit','endBasis':'scheduled','title':'Плановое отключение электричества',
   'description':clean(row[7]),'fullText':evidence,'affected':impact,'unmappedAreaText':issues,
   'requiresReview':bool(issues),'point':None,'precision':'street'})
 if not read:raise ValueError('Официальная таблица Шахт отсутствует или формат изменился')
 return {'events':events,'rowsRead':read,'noPlannedWorkNotices':notes,'rejectedRows':rejected}

def tls_context():
 pem=Path(__file__).with_name('globalsign-intermediate.pem')
 if not pem.exists():
  with urlopen('https://secure.globalsign.com/cacert/gsgccr46alphasslca2025.crt',timeout=12) as r:der=r.read(200000)
  if hashlib.sha1(der).hexdigest()!='e7ae6d3bb265b204b7ea3d732edec0799ab22488':raise ValueError('GlobalSign certificate fingerprint mismatch')
  pem.write_text(ssl.DER_cert_to_PEM_cert(der))
 ctx=ssl.create_default_context();ctx.load_verify_locations(cafile=str(pem))
 if hasattr(ssl,'VERIFY_X509_PARTIAL_CHAIN'):ctx.verify_flags&=~ssl.VERIFY_X509_PARTIAL_CHAIN
 assert ctx.check_hostname and ctx.verify_mode==ssl.CERT_REQUIRED
 return ctx

def collect(now=None):
 now=now or datetime.now(timezone.utc);began=time.monotonic()
 for attempt in range(2):
  try:
   with urlopen(Request(URL,headers={'User-Agent':'CityControlShakhty/0.9 public schedule reader'}),context=tls_context(),timeout=14) as r:
    if r.status!=200:raise ValueError('HTTP '+str(r.status))
    body=r.read(2000001)
    if len(body)>2000000:raise ValueError('Response too large')
   parsed=parse(body.decode('utf-8'),now)
   src={'id':'power_direct','status':'ok','transport':'direct_https','url':URL,'checkedAt':now.isoformat(),
    'lastPostAt':None,'posts':parsed['rowsRead'],'matchingPosts':len(parsed['events']),
    'note':'Прямой официальный график ШМЭС. Отсутствие плановых работ не исключает аварии.',
    'noPlannedWorkNotices':parsed['noPlannedWorkNotices'],'tlsVerified':True,
    'contentSha256':hashlib.sha256(body).hexdigest(),'durationSeconds':round(time.monotonic()-began,2)}
   return parsed['events'],src
  except Exception as e:
   err=str(e)[:220]
   if attempt==0:time.sleep(1)
 return [],{'id':'power_direct','status':'error','url':URL,'checkedAt':now.isoformat(),'posts':0,
  'note':'Не удалось прочитать официальный график: '+err,'tlsVerified':True}
if __name__=='__main__':
 events,source=collect();print(json.dumps({'source':source,'events':events},ensure_ascii=False,indent=2))
