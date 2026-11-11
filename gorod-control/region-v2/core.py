"""Local regional MAX-only collection contracts. Not wired to the live app yet."""
import hashlib,json,sqlite3
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit
CATEGORIES={'water','power','mchs'}
def utc(s):
 d=datetime.fromisoformat(s)
 if d.tzinfo is None:raise ValueError('Timezone required')
 return d.astimezone(timezone.utc)
def covers(source,category,municipality):
 return municipality in source.get('municipalities',[]) or category=='mchs' and source.get('regionCoverageVerified') is True
class Store:
 def __init__(self,path,channels):
  self.channels={c['id']:deepcopy(c) for c in channels};self.db=sqlite3.connect(path)
  self.db.executescript('''CREATE TABLE IF NOT EXISTS posts(channel TEXT,id TEXT,hash TEXT,payload TEXT,PRIMARY KEY(channel,id));
  CREATE TABLE IF NOT EXISTS revisions(channel TEXT,id TEXT,hash TEXT,payload TEXT,PRIMARY KEY(channel,id,hash));
  CREATE TABLE IF NOT EXISTS health(channel TEXT PRIMARY KEY,success TEXT,attempt TEXT,error TEXT,gap INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS checkpoints(channel TEXT PRIMARY KEY,cursor TEXT);''')
 def ingest(self,cid,batch,cursor,now,*,complete=True,fail_before_commit=False):
  c=self.channels[cid];u=urlsplit(c['url'])
  if not c.get('enabled',True) or c.get('transport')!='max' or u.scheme!='https' or u.netloc!='max.ru' or not c.get('identity_verified'):raise ValueError('Unverified MAX channel')
  if not complete:raise ValueError('Do not advance a cursor across a gap')
  utc(now)
  with self.db:
   for p in batch:
    if str(p.get('channel_id'))!=str(c['chat_id']) or not str(p.get('id','')):raise ValueError('Wrong public channel')
    self._write_post(cid,p)
   self.db.execute('INSERT OR REPLACE INTO health VALUES(?,?,?,NULL,0)',(cid,now,now))
   self.db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?)',(cid,str(cursor)))
   if fail_before_commit:raise RuntimeError('Test rollback')
 def _write_post(self,cid,p):
  utc(p['publishedAt']);raw=json.dumps(p,ensure_ascii=False,sort_keys=True);h=hashlib.sha256(raw.encode()).hexdigest()
  self.db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?)',(cid,str(p['id']),h,raw))
  self.db.execute('INSERT OR REPLACE INTO posts VALUES(?,?,?,?)',(cid,str(p['id']),h,raw))
 def failure(self,cid,now,code='UNAVAILABLE',gap=False):
  if cid not in self.channels:raise ValueError('Unknown channel')
  utc(now)
  # Fixed public codes only; never serialize tokens or raw provider exceptions.
  if code not in {'UNAVAILABLE','TIMEOUT','AUTH_REQUIRED','GAP','IDENTITY_ERROR','FORMAT_ERROR','DEPENDENCY_ERROR'}:code='UNAVAILABLE'
  with self.db:
   self.db.execute('INSERT INTO health(channel,attempt,error,gap) VALUES(?,?,?,?) ON CONFLICT(channel) DO UPDATE SET attempt=excluded.attempt,error=excluded.error,gap=MAX(health.gap,excluded.gap)',(cid,now,code,int(gap)))
 def category_status(self,cat,municipality,now,max_age=timedelta(minutes=15)):
  if cat not in CATEGORIES:raise ValueError('Unknown category')
  enabled=[c for c in self.channels.values() if c.get('enabled',True) and c.get('identity_verified') and cat in c.get('categories',[]) and covers(c,cat,municipality)]
  if not enabled:return {'state':'unconfigured','message':'Охват этой категории для выбранной территории не подтверждён'}
  rows=[]
  for c in enabled:
   r=self.db.execute('SELECT success,attempt,error,gap FROM health WHERE channel=?',(c['id'],)).fetchone()
   healthy=bool(r and r[0] and not r[2] and not r[3] and timedelta(0)<=utc(now)-utc(r[0])<=max_age)
   rows.append(healthy)
  if all(rows):return {'state':'read','message':'Зарегистрированные каналы прочитаны; полнота публикаций не гарантируется'}
  return {'state':'partial' if any(rows) else 'unavailable','message':'Информация временно недоступна или неполна; последняя подтверждённая сводка сохранена'}
 def checkpoint(self,cid):
  r=self.db.execute('SELECT cursor FROM checkpoints WHERE channel=?',(cid,)).fetchone();return r[0] if r else None
 def posts(self,cid):return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM posts WHERE channel=?',(cid,))]
def same_address(a,b):
 # IDs must come from the verified address catalogue, not street strings alone.
 keys=('region_id','municipality_id','street_id')
 if not all(a.get(k) and a.get(k)==b.get(k) for k in keys):return False
 return not a.get('houses') or bool(set(a['houses']) & set(b.get('houses',[])))
def visible_event(e,now):
 if e.get('status') in {'resolved','cancelled','deleted'} or e.get('requiresReview'):return False
 if e.get('region_id')!='RU-ROS' or not e.get('municipality_id'):return False
 if e.get('category')=='mchs':return bool(e.get('end') and utc(now)<utc(e['end']))
 anchor=e.get('end') or e.get('start') or e.get('publishedAt')
 return bool(anchor and utc(now)<utc(anchor)+timedelta(hours=36))
