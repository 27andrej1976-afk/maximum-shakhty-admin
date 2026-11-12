"""Evidence-backed regional event ledger; no invented addresses or coordinates.

A source parser/operator supplies reviewed records with the exact original-post
hash. Unsupported posts remain pending. This is NOT a general Russian NLP parser.
"""
import json
import re
from collections import Counter
from datetime import timedelta
from core import CATEGORIES, utc, covers
from health import snapshot


class Ledger:
    def __init__(self, store, catalog):
        self.store = store
        if catalog.get('regionId') != 'RU-ROS':
            raise ValueError('Wrong regional catalog')
        self.catalog = catalog
        self.cities = {x['id']: x for x in catalog.get('municipalities', []) if x.get('verified')}
        self.addresses = {x['id']: x for x in catalog.get('addresses', []) if x.get('verified')}
        self.store.db.executescript('''
            CREATE TABLE IF NOT EXISTS reviewed_events(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE IF NOT EXISTS review_log(id TEXT PRIMARY KEY,payload TEXT);
        ''')

    def apply(self, records, now):
        """Validate the entire review batch before atomically applying it."""
        utc(now)
        validated = [self._validate(record, now) for record in records]
        with self.store.db:
            for record in validated:
                raw = json.dumps(record, ensure_ascii=False, sort_keys=True)
                previous = self.store.db.execute('SELECT payload FROM review_log WHERE id=?',
                                                  (record['reviewId'],)).fetchone()
                if previous:
                    if previous[0] != raw:
                        raise ValueError('Review ID cannot be reused for different evidence')
                    continue
                if record['type'] == 'incident':
                    if self.store.db.execute('SELECT 1 FROM reviewed_events WHERE id=?', (record['eventId'],)).fetchone():
                        raise ValueError('Incident ID already exists; submit an explicit amendment')
                    self.store.db.execute('INSERT INTO reviewed_events VALUES(?,?)',
                                          (record['eventId'], raw))
                elif record['type'] in {'restoration', 'cancellation'}:
                    row = self.store.db.execute('SELECT payload FROM reviewed_events WHERE id=?',
                                                (record['targetEventId'],)).fetchone()
                    if not row:
                        raise ValueError('Unknown restoration target')
                    incident = json.loads(row[0])
                    if (incident['category'] != record['category']
                            or incident['municipalityId'] != record['municipalityId']
                            or utc(record['publishedAt']) < utc(incident['publishedAt'])):
                        raise ValueError('Restoration category, city or chronology mismatch')
                    scope = set(record['addressIds'])
                    if record['type'] == 'cancellation':
                        if incident.get('scope') != 'region' or record.get('scope') != 'region' or incident['category'] != 'mchs':
                            raise ValueError('Only an explicit regional MCHS cancellation may close a regional warning')
                    elif not scope or not scope <= set(incident['addressIds']):
                        raise ValueError('Restoration must explicitly identify affected addresses')
                self.store.db.execute('INSERT INTO review_log VALUES(?,?)', (record['reviewId'], raw))

    def _validate(self, record, now):
        r = dict(record)
        for key in ['reviewId', 'sourceId', 'messageId', 'sourceHash', 'category', 'type']:
            if not isinstance(r.get(key), str) or not r[key]:
                raise ValueError('Missing review evidence')
        if r['category'] not in CATEGORIES or r['type'] not in {'incident', 'restoration', 'cancellation'}:
            raise ValueError('Unsupported review kind')
        source = self.store.channels.get(r['sourceId'], {})
        if (not source.get('identity_verified') or source.get('transport') != 'max'
                or r['category'] not in source.get('categories', [])):
            raise ValueError('Unverified MAX category')
        row = self.store.db.execute('SELECT hash,payload FROM posts WHERE channel=? AND id=?',
                                    (r['sourceId'], r['messageId'])).fetchone()
        if not row or r['sourceHash'] != row[0]:
            raise ValueError('Source changed or does not exist')
        post = json.loads(row[1])
        published = utc(post['publishedAt'])
        if published > utc(now):
            raise ValueError('Future publication cannot confirm an incident')
        r['publishedAt'] = post['publishedAt']
        r['url'] = source['url']  # never accept a guessed post URL from a parser
        city = r.get('municipalityId')
        r['municipalityId'] = city
        scope = r.get('scope', 'municipality')
        r['scope'] = scope
        address_ids = r.get('addressIds')
        if scope == 'region':
            if (r['category'] != 'mchs' or not source.get('regionCoverageVerified')
                    or city is not None or address_ids != [] or r['type'] == 'restoration'):
                raise ValueError('Regional warning scope not verified')
        else:
            if scope != 'municipality' or r['type'] == 'cancellation':
                raise ValueError('Invalid territorial scope')
            if city not in self.cities or city not in source.get('municipalities', []):
                raise ValueError('Unverified city coverage')
            if not isinstance(address_ids, list) or not address_ids or len(set(address_ids)) != len(address_ids):
                raise ValueError('Explicit unique addresses required')
            for aid in address_ids:
                a = self.addresses.get(aid, {})
                if a.get('municipalityId') != city or not a.get('streetId'):
                    raise ValueError('Unverified address or cross-city match')
        identifier = 'eventId' if r['type'] == 'incident' else 'targetEventId'
        if not isinstance(r.get(identifier), str) or not re.fullmatch(r'[\w:./-]{1,180}', r[identifier]):
            raise ValueError('Invalid event identifier')
        if r['type'] == 'incident':
            if not isinstance(r.get('title'), str) or not r['title'].strip() or len(r['title']) > 200:
                raise ValueError('Incident title required')
            r['description'] = str(r.get('description', ''))[:4000]
            if r.get('start'):
                utc(r['start'])
            if r.get('end'):
                utc(r['end'])
            if r.get('start') and r.get('end') and utc(r['end']) < utc(r['start']):
                raise ValueError('End precedes start')
            # Warnings with unknown expiry stay in the review queue; no invented 36h expiry.
            if r['category'] == 'mchs' and not r.get('end'):
                raise ValueError('MCHS expiry must be explicit; keep publication pending')
            unresolved=r.get('unresolvedAddresses', [])
            if not isinstance(unresolved,list) or len(unresolved)>200 or any(
                    not isinstance(x,str) or len(x)>500 for x in unresolved):
                raise ValueError('Invalid unresolved address list')
        # Only a fixed reviewed schema is stored/published, not arbitrary parser fields.
        keys = {'reviewId', 'sourceId', 'messageId', 'sourceHash', 'publishedAt', 'url',
                'category', 'type', 'municipalityId', 'addressIds', identifier,
                'title', 'description', 'start', 'end', 'scope', 'unresolvedAddresses', 'parserVersion', 'addressMatchPrecision'}
        return {k: v for k, v in r.items() if k in keys}

    def events(self, now):
        utc(now)
        result = []
        closures=[]
        for row in self.store.db.execute('SELECT payload FROM review_log'):
            r=json.loads(row[0])
            if r['type'] not in {'restoration','cancellation'}:continue
            current=self.store.db.execute('SELECT hash FROM posts WHERE channel=? AND id=?',
                (r['sourceId'],r['messageId'])).fetchone()
            if current and current[0]==r['sourceHash']:closures.append(r)
        for row in self.store.db.execute('SELECT payload FROM reviewed_events'):
            e = json.loads(row[0])
            anchor = e.get('end') or e.get('start') or e['publishedAt']
            expires = utc(e['end']) if e['category'] == 'mchs' else utc(anchor) + timedelta(hours=36)
            if utc(now) >= expires:
                continue
            if any(r['type'] == 'cancellation' and r['targetEventId'] == e['eventId']
                   and utc(r['publishedAt']) <= utc(now) for r in closures):
                continue
            removed = {aid for r in closures if r['targetEventId'] == e['eventId']
                       and utc(r['publishedAt']) <= utc(now) for aid in r['addressIds']}
            remaining = [aid for aid in e['addressIds'] if aid not in removed]
            if not remaining and e.get('scope') != 'region':
                continue
            current = self.store.db.execute('SELECT hash FROM posts WHERE channel=? AND id=?',
                                            (e['sourceId'], e['messageId'])).fetchone()
            changed = not current or current[0] != e['sourceHash']
            e = dict(e, id=e['eventId'], addressIds=remaining,
                     expiresAt=expires.isoformat(), sourceChanged=changed,
                     status='unconfirmed' if changed or e.get('end') and utc(e['end']) <= utc(now) else 'active')
            e['addresses'] = [dict(self.addresses[aid]) for aid in remaining]
            e['regionId'] = 'RU-ROS'
            e['partialRestoration'] = bool(removed)
            result.append(e)
        return sorted(result, key=lambda e: (e['publishedAt'], e['id']), reverse=True)

    def pending(self):
        reviewed = {(r['sourceId'], r['messageId'], r['sourceHash'])
                    for row in self.store.db.execute('SELECT payload FROM review_log')
                    for r in [json.loads(row[0])] if not r.get('unresolvedAddresses')}
        self.store.db.execute('''CREATE TABLE IF NOT EXISTS post_dispositions(
            channel TEXT,id TEXT,hash TEXT,kind TEXT,reason TEXT,PRIMARY KEY(channel,id,hash))''')
        informational={(r[0],r[1],r[2]) for r in self.store.db.execute(
            "SELECT channel,id,hash FROM post_dispositions WHERE kind='information'")}
        result = []
        for source in self.store.channels.values():
            for row in self.store.db.execute('SELECT id,hash,payload FROM posts WHERE channel=?', (source['id'],)):
                if (source['id'], row[0], row[1]) in reviewed|informational:
                    continue
                post = json.loads(row[2])
                text = post.get('text', '')
                if not text.strip() and post.get('forwarded'):
                    text = next((item.get('text', '') for item in post.get('linkedContent', [])
                                 if item.get('kind') == 'FORWARD' and item.get('text', '').strip()), '')
                result.append({'id': source['id'] + '/' + row[0], 'sourceId': source['id'],
                               'publishedAt': post['publishedAt'], 'url': source['url'],
                               'text': text[:2000], 'forwarded': post.get('forwarded', False),
                               'attachmentCount': post.get('attachmentCount', 0),
                               'message': 'Публикация ожидает разбора; адрес и влияние не подтверждены'})
        return result

    def feed(self, now):
        pending = self.pending()
        pending_by_source=Counter(p['sourceId'] for p in pending)
        cities = []
        for city in self.cities.values():
            counts = {category: sum(pending_by_source[s['id']]
                for s in self.store.channels.values() if s.get('enabled') and s.get('identity_verified')
                and covers(s,category,city['id']) and category in s.get('categories', []))
                for category in CATEGORIES}
            health = snapshot(self.store, city['id'], now, pending_counts=counts)
            cities.append({'id': city['id'], 'name': city.get('label',city['name']), 'health': health['categoryHealth']})
        return {'schemaVersion': 1, 'mode': 'max-only', 'regionId': 'RU-ROS',
                'dataMode': self.catalog.get('dataMode', 'production'),
                'generatedAt': now, 'coverage': 'partial' if cities else 'unknown',
                'municipalities': cities, 'events': self.events(now),
                'pendingPublications': sorted(pending,key=lambda p:(p['publishedAt'],p['id']),reverse=True)[:200],
                'pendingPublicationCount':len(pending), 'pendingListLimited':len(pending)>200,
                'notice': 'Отсутствие найденных публикаций не означает отсутствие аварий'}
