"""Idempotent template processing with persistent evidence and visible fallbacks."""
import json
from parse_publications import Templates,load_index
from events import Ledger
from core import utc

VERSION='source-templates-gar-v1'


def process(store,catalog,index,now,*,geometry=None):
    templates=Templates(index)
    geometry=geometry or {}
    ledger=Ledger(store,catalog)
    store.db.executescript('''
      CREATE TABLE IF NOT EXISTS post_dispositions(channel TEXT,id TEXT,hash TEXT,kind TEXT,reason TEXT,PRIMARY KEY(channel,id,hash));
      CREATE TABLE IF NOT EXISTS observed_coverage(channel TEXT,locality TEXT,PRIMARY KEY(channel,locality));
    ''')
    for cid,city in store.db.execute('SELECT channel,locality FROM observed_coverage'):
        if cid in store.channels and city in templates.cities:
            source=store.channels[cid];source['municipalities']=list(set(source.get('municipalities',[]))|{city})
    rows=list(store.db.execute('SELECT channel,id,hash,payload FROM posts ORDER BY json_extract(payload,\'$.publishedAt\'),id'))
    stats={'incidents':0,'restorations':0,'pending':0,'information':0,'unchanged':0}
    for cid,mid,digest,raw in rows:
        source=store.channels[cid]
        if not source.get('enabled') or not source.get('identity_verified'):continue
        post=json.loads(raw)
        if utc(post['publishedAt'])>utc(now):continue
        # Existing reviews are immutable; edits retain the old incident as
        # unconfirmed and place the changed evidence back in the review queue.
        review_id=VERSION+':'+cid+':'+mid+':'+digest[:16]
        if store.db.execute('SELECT 1 FROM review_log WHERE id=?',(review_id,)).fetchone():
            stats['unchanged']+=1;continue
        plan=templates.propose(post,source)
        kind=plan['state'];reason=plan['reason']
        if kind in {'incident','restoration'}:
            city=plan.get('city');city_id=city['id'] if city else None
            if city:
                source['municipalities']=list(set(source.get('municipalities',[]))|{city_id})
                store.db.execute('INSERT OR IGNORE INTO observed_coverage VALUES(?,?)',(cid,city_id));store.db.commit()
            aids=[]
            for address in plan['addresses']:
                address=dict(address)
                geo=geometry.get(address['id'])
                if geo:address.update(geo)
                ledger.addresses[address['id']]=address;aids.append(address['id'])
            event_id=cid+':'+mid+(':'+city_id if city_id else ':region')
            record={'reviewId':review_id,'sourceId':cid,'messageId':mid,'sourceHash':digest,
                    'category':plan['category'],'type':kind,'municipalityId':city_id,
                    'scope':plan.get('scope','municipality'),'addressIds':aids,'parserVersion':VERSION}
            if kind=='incident':
                if store.db.execute('SELECT 1 FROM reviewed_events WHERE id=?',(event_id,)).fetchone():
                    kind='pending';reason='CHANGED_INCIDENT_REQUIRES_REVIEW'
                else:
                    record.update(eventId=event_id,title=plan['title'],description=plan['text'][:4000],
                        start=plan['start'],end=plan['end'],unresolvedAddresses=plan['unresolvedAddresses'],
                        addressMatchPrecision='house-range-unverified' if any(any(ch.isdigit() for ch in a['sourceAddress']) for a in plan['addresses']) else 'street')
            else:
                # Exact source/category/city/address set, newer explicit text,
                # only one unresolved incident. No broad street-only guessing.
                candidates=[]
                for event_row in store.db.execute('SELECT payload FROM reviewed_events'):
                    event=json.loads(event_row[0])
                    if (event['sourceId']==cid and event['category']==plan['category']
                            and event['municipalityId']==city_id and set(event['addressIds'])==set(aids)
                            and event.get('addressMatchPrecision','street')=='street'
                            and not event.get('unresolvedAddresses') and not plan['unresolvedAddresses']
                            and utc(event['publishedAt'])<=utc(post['publishedAt'])):
                        # Never treat a house/range-specific restoration as a
                        # confirmation for a whole street. That needs a house ledger.
                        if any(any(ch.isdigit() for ch in a['sourceAddress']) for a in plan['addresses']):continue
                        if store.db.execute("SELECT 1 FROM review_log WHERE json_extract(payload,'$.targetEventId')=?",(event['eventId'],)).fetchone():continue
                        candidates.append(event['eventId'])
                if len(candidates)==1:record['targetEventId']=candidates[0]
                else:kind='pending';reason='AMBIGUOUS_OR_UNMATCHED_RESTORATION'
            if kind in {'incident','restoration'}:
                ledger.apply([record],now);stats['incidents' if kind=='incident' else 'restorations']+=1
        if kind in {'pending','information'}:stats[kind]+=1
        with store.db:store.db.execute('INSERT OR REPLACE INTO post_dispositions VALUES(?,?,?,?,?)',
            (cid,mid,digest,kind,reason))
    # Keep accepted address evidence across restarts independently of geometry API.
    catalog['addresses']=list(ledger.addresses.values())
    return ledger,stats
