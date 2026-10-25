"""Retain verified water notices to the original end/start/publication + 36 hours."""
from copy import deepcopy
from power_retention import deadline,stamp,areas
URLS={'max_water':'https://max.ru/id6167110467_gos','max_city':'https://max.ru/shakhtygorod'}
def source_id(e):
 if e.get('category')!='water':return None
 url=e.get('url','');sid=e.get('sourceId');origin=e.get('origin')
 if origin=='official_max' and sid in URLS and url==URLS[sid]:return sid
 if origin=='media_report' and sid=='water_kvu' and url.startswith('https://kvu.su/utilities/'):return sid
 if origin in ('verified_repost','municipal_repost'):
  for prefix,ident in [('https://news-don.ru/','repost_don'),('https://newsrostov.ru/','repost_rostov')]:
   if url.startswith(prefix) and sid in (None,ident):return ident
 if e.get('source')=='Администрация города Шахты' and url.startswith('https://t.me/admshakhty/'):return 'city'
 return None

def merge(current,previous,sources,now):
 states={s['id']:s for s in sources};saved={e['id']:deepcopy(e) for e in previous if source_id(e) and e.get('id')};fresh=set()
 for item in current:
  sid=source_id(item);state=states.get(sid,{})
  if not sid or not item.get('id') or not (state.get('status')=='ok' or state.get('readStatus')=='ok'):continue
  if saved.get(item['id'],{}).get('status') in ('resolved','cancelled','canceled') and item.get('status') not in ('resolved','cancelled','canceled'):continue
  e=deepcopy(item);e['lastConfirmedAt']=state.get('checkedAt') or now.isoformat();saved[e['id']]=e;fresh.add(e['id'])
 restorations=[e for e in saved.values() if e.get('status')=='resolved']
 for r in restorations:
  when=stamp(r.get('resolvedAt')) or stamp(r.get('publishedAt'))
  if not when or when>now:continue
  matches=[]
  for e in saved.values():
   start=stamp(e.get('start')) or stamp(e.get('publishedAt'))
   if e.get('status') in ('resolved','cancelled','canceled') or not start or start>when:continue
   site=r.get('workSite') and r.get('workSite')==e.get('workSite')
   coverage=areas(r) and areas(r)==areas(e)
   if (site and (not areas(r) or coverage)) or (not r.get('workSite') and coverage):matches.append(e)
  if len(matches)==1:
   matches[0].update(status='resolved',resolvedAt=when.isoformat(),resolutionUrl=r['url'])
 out=[]
 for e in saved.values():
  until=deadline(e)
  if not until or now>=until:continue
  e['retainUntil']=until.isoformat();e['retained']=e['id'] not in fresh
  if e.get('status') not in ('resolved','cancelled','canceled'):
   end=stamp(e.get('end'))
   if e['retained'] or end and end<now:e['status']='unconfirmed'
  out.append(e)
 return out
