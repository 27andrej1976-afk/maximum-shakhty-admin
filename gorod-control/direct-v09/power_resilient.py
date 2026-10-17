"""Last successful DIRECT source cache. A failed poll never becomes a successful current poll."""
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen
from copy import deepcopy
from power_direct import collect as network_collect
P=Path(__file__).parent
CACHE=P/'power-last-success.json'
# Immutable previously validated application snapshot, not a substitute source.
SEED='https://raw.githubusercontent.com/27andrej1976-afk/maximum-shakhty-admin/d3762239f1ce53b323dfe435a79cc502725ad8c1/gorod-control/direct-v09/feed.json'
def seed():
 if CACHE.exists():return
 candidate=None
 try:
  f=json.loads((P/'feed.json').read_text());s=next(x for x in f['sources'] if x['id']=='power_direct')
  if s['status']=='ok':candidate={'source':s,'events':[e for e in f['events'] if e.get('sourceId')=='power_direct']}
 except Exception:pass
 if candidate is None:
  try:
   with urlopen(SEED,timeout=8) as r:f=json.load(r)
   s=next(x for x in f['sources'] if x['id']=='power_direct')
   if s['status']=='ok' and s.get('tlsVerified'):candidate={'source':s,'events':[e for e in f['events'] if e.get('sourceId')=='power_direct']}
  except Exception:pass
 if candidate:CACHE.write_text(json.dumps(candidate,ensure_ascii=False,indent=2))
def collect(now=None):
 now=now or datetime.now(timezone.utc)
 events,source=network_collect(now)
 if source['status']=='ok':
  CACHE.write_text(json.dumps({'source':source,'events':events},ensure_ascii=False,indent=2));return events,source
 seed()
 try:
  old=json.loads(CACHE.read_text());s=deepcopy(old['source']);at=datetime.fromisoformat(s['checkedAt'])
  if not timedelta(0)<=now-at<timedelta(hours=24):return [],source
  s.update(status='cached',transport='direct_https_cache',lastAttemptAt=now.isoformat(),lastError=source.get('note'),
   note='Повторный запрос к Донэнерго не удался. Показана последняя успешная официальная сводка от '+at.astimezone(timezone(timedelta(hours=3))).strftime('%d.%m %H:%M')+'. Свежесть и изменения не подтверждены.')
  kept=[]
  for e in old['events']:
   if e.get('end') and datetime.fromisoformat(e['end'])<now-timedelta(hours=24):continue
   e=deepcopy(e);e['cachedEvidence']=True;e['requiresReview']=True
   e['description']=e.get('description','')+' Последняя успешная проверка источника: '+s['checkedAt']+'. Повторное чтение временно недоступно.'
   if e.get('end') and datetime.fromisoformat(e['end'])<now:e['status']='unconfirmed'
   kept.append(e)
  return kept,s
 except Exception:return [],source
