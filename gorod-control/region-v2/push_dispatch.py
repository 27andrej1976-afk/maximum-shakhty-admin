"""Optional RuStore data-only topic dispatcher. No device GPS/token registry.

Disabled without a private configuration. First start records a baseline rather
than sending a backlog. Repeated event revisions are idempotent on the device.
"""
import hashlib
import json
import re
import sqlite3
from datetime import timedelta
from pathlib import Path
from urllib.request import Request,urlopen
from core import utc

TOPICS={'water':'don-water-v1','power':'don-power-v1','mchs':'don-mchs-v1'}

def eligible(event,now):
    return (event.get('category') in TOPICS and event.get('status')=='active'
        and not event.get('sourceChanged') and not event.get('requiresReview')
        and utc(event['publishedAt'])<=utc(now)<utc(event['expiresAt'])
        and re.fullmatch('[a-f0-9]{64}',event.get('sourceHash','')))

def revision(event):
    geometry=sorted((a['id'],a.get('geometryVerified'),a.get('lat'),a.get('lon')) for a in event.get('addresses',[]))
    return hashlib.sha256(json.dumps([event['sourceHash'],geometry],sort_keys=True).encode()).hexdigest()

class Dispatcher:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.executescript('CREATE TABLE IF NOT EXISTS push_meta(id INTEGER PRIMARY KEY);CREATE TABLE IF NOT EXISTS push_seen(id TEXT PRIMARY KEY,revision TEXT);CREATE TABLE IF NOT EXISTS push_queue(id TEXT PRIMARY KEY,revision TEXT,payload TEXT,created TEXT);')
    def close(self):self.db.close()
    def run(self,feed,now,send):
        if (feed.get('dataMode')!='production' or feed.get('verificationMode') or feed.get('regionId')!='RU-ROS'
            or not timedelta(minutes=-5)<=utc(now)-utc(feed['generatedAt'])<=timedelta(minutes=15)):return {'state':'stale','sent':0}
        active={e['id']:e for e in feed['events'] if eligible(e,now)}
        baseline=not self.db.execute('SELECT 1 FROM push_meta').fetchone()
        with self.db:
            for eid,event in active.items():
                rev=revision(event);previous=self.db.execute('SELECT revision FROM push_seen WHERE id=?',(eid,)).fetchone()
                if not baseline and (not previous or previous[0]!=rev):
                    # Public data only; the phone re-fetches current evidence and filters distance.
                    payload={'message':{'data':{'type':'don-event-v1','eventId':eid,'sourceHash':event['sourceHash'],'sentAt':now},'android':{'ttl':'300s'}}}
                    self.db.execute('INSERT OR REPLACE INTO push_queue VALUES(?,?,?,?)',(eid,rev,json.dumps(payload),now))
                self.db.execute('INSERT OR REPLACE INTO push_seen VALUES(?,?)',(eid,rev))
            self.db.execute('INSERT OR IGNORE INTO push_meta VALUES(1)')
        sent=0;errors=0
        for eid,rev,raw,created in list(self.db.execute('SELECT id,revision,payload,created FROM push_queue ORDER BY created LIMIT 20')):
            if eid not in active or revision(active[eid])!=rev or utc(now)-utc(created)>timedelta(minutes=5):
                with self.db:self.db.execute('DELETE FROM push_queue WHERE id=?',(eid,))
                continue
            try:send(TOPICS[active[eid]['category']],json.loads(raw))
            except Exception:errors+=1;continue
            with self.db:self.db.execute('DELETE FROM push_queue WHERE id=?',(eid,))
            sent+=1
        return {'state':'baseline' if baseline else 'error' if errors else 'submitted','sent':sent,'failed':errors,'deliveryVerified':False}

def dispatch(config,feed_path,state,now):
    project=config.get('pushProjectId');token_path=config.get('pushServiceTokenFile')
    if not project or not token_path:return {'state':'not_configured','deliveryVerified':False}
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',project):raise ValueError('Invalid project')
    token=Path(token_path).read_text().strip()
    if not token or '\n' in token:raise ValueError('Invalid private service token')
    def send(topic,payload):
        request=Request(f'https://vkpns-topics.rustore.ru/v1/projects/{project}/topics/{topic}/publish',
            data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token},method='POST')
        with urlopen(request,timeout=10) as response:
            if response.status!=200:raise ValueError('Push submission rejected')
            # HTTP success confirms API acceptance, never phone delivery.
            result=json.loads(response.read(8192))
            if result.get('errors') or result.get('error'):raise ValueError('Push API error')
    queue=Dispatcher(Path(state)/'push-delivery.sqlite')
    try:return queue.run(json.loads(Path(feed_path).read_text()),now,send)
    finally:queue.close()
