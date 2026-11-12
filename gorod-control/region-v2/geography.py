"""Cached, bounded lookup of public incident streets; never user GPS or homes.

Photon's public demo has no availability guarantee. Requests are sequential,
small and cached; failures leave address cards intact, without invented markers.
"""
from datetime import datetime,timezone,timedelta
import json
import math
import re
import sqlite3
import urllib.parse
import urllib.request
from parse_publications import norm

ENDPOINT='https://photon.komoot.io/api/'


def street_name(text):
    tokens=norm(text).split()
    kinds={'улица','переулок','проспект','бульвар','площадь','шоссе','проезд'}
    return ' '.join(x for x in tokens if x not in kinds)


def verify_geometry(data,address,city):
    matching=[]
    for feature in data.get('features',[]):
        p=feature.get('properties',{});g=feature.get('geometry',{})
        xy=g.get('coordinates',[])
        if (str(p.get('countrycode','')).upper()!='RU' or norm(p.get('state'))!='ростовская область'
                or norm(p.get('city'))!=norm(city['name']) or p.get('osm_key')!='highway'
                or street_name(p.get('name',''))!=norm(address['name'])
                or g.get('type')!='Point' or len(xy)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in xy)
                or not (-180<=xy[0]<=180 and -90<=xy[1]<=90)):
            continue
        if not isinstance(p.get('osm_id'),int) or p.get('osm_type') not in {'N','W','R'}:continue
        matching.append((p,xy))
    if not matching:return None
    p,xy=matching[0]
    kind={'N':'node','W':'way','R':'relation'}[p['osm_type']]
    return {'lat':xy[1],'lon':xy[0],'geometryVerified':True,'locationPrecision':'street',
            'geometryEvidenceUrl':'https://www.openstreetmap.org/'+kind+'/'+str(p['osm_id']),
            'geometryNotice':'Ориентир на улице, не точные границы отключения',
            'geometryProvider':'OpenStreetMap via Photon','geometryCheckedAt':datetime.now(timezone.utc).isoformat()}


class GeometryCache:
    def __init__(self,path,*,endpoint=ENDPOINT):
        self.db=sqlite3.connect(path);self.endpoint=endpoint;self.network_requests=0
        # Endpoint is server configuration, never a URL supplied by an app user.
        u=urllib.parse.urlsplit(endpoint)
        if u.scheme!='https' or u.username or u.password or u.query or u.fragment:raise ValueError('HTTPS geocoder endpoint required')
        self.db.execute('CREATE TABLE IF NOT EXISTS geometry(id TEXT PRIMARY KEY,checked TEXT,payload TEXT)')
    def values(self):
        return {r[0]:json.loads(r[1]) for r in self.db.execute('SELECT id,payload FROM geometry WHERE payload IS NOT NULL')}
    def resolve(self,address,city,now):
        row=self.db.execute('SELECT checked,payload FROM geometry WHERE id=?',(address['id'],)).fetchone()
        if row and (row[1] or datetime.fromisoformat(now)-datetime.fromisoformat(row[0])<timedelta(days=1)):
            return json.loads(row[1]) if row[1] else None
        q=address['label']+', '+city['name']+', Ростовская область, Россия'
        url=self.endpoint+'?'+urllib.parse.urlencode({'q':q,'limit':5,'countrycode':'RU'})
        found=None
        self.network_requests+=1
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'DonControl/0.1 (public utility street verification; Fefe-andrej@yandex.ru)'})
            with urllib.request.urlopen(req,timeout=10) as response:
                raw=response.read(500001)
                if len(raw)>500000:raise ValueError('Geometry reply too large')
                found=verify_geometry(json.loads(raw),address,city)
        except Exception:pass
        with self.db:self.db.execute('INSERT OR REPLACE INTO geometry VALUES(?,?,?)',
            (address['id'],now,json.dumps(found,ensure_ascii=False) if found else None))
        return found
    def resolve_missing(self,addresses,cities,now,*,request_budget):
        """Cached failures must not starve later streets in the queue."""
        start=self.network_requests;found={}
        for address in addresses:
            if address.get('geometryVerified') or address['id'] in found:continue
            if self.network_requests-start>=max(0,request_budget):break
            point=self.resolve(address,cities[address['municipalityId']],now)
            if point:found[address['id']]=point
        return found
    def close(self):self.db.close()
