"""Optional GAR-ID geocoder. Prepared, not connected without the owner's key.

Only the public incident street GUID goes to the fixed official endpoint.
Never user GPS, freeform personal addresses, token URL parameters or clean API.
"""
from datetime import datetime,timezone
import json,math,re
from pathlib import Path
import urllib.request
from geography import GeometryCache

ENDPOINT='https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/address'

def verify_dadata(data,address,city):
    found=[]
    for item in data.get('suggestions',[]):
        d=item.get('data',{})
        if (d.get('country_iso_code')!='RU' or d.get('region_iso_code')!='RU-ROS'
                or d.get('street_fias_id')!=address['streetId'] or d.get('fias_id')!=address['streetId']
                or city['id'] not in {d.get('city_fias_id'),d.get('settlement_fias_id')}
                or str(d.get('fias_level'))!='7' or str(d.get('qc_geo'))!='2'
                or str(d.get('fias_actuality_state'))!='0'):continue
        try:lat,lon=float(d['geo_lat']),float(d['geo_lon'])
        except (TypeError,ValueError,KeyError):continue
        if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):continue
        found.append((lat,lon))
    if len(set(found))!=1:return None
    lat,lon=found[0]
    return {'lat':lat,'lon':lon,'geometryVerified':True,'locationPrecision':'street',
        'geometryProvider':'DaData by exact GAR street ID','geometryEvidenceUrl':'https://dadata.ru/api/find-address/',
        'geometryNotice':'Ориентир на улице, не точные границы отключения',
        'geometryCheckedAt':datetime.now(timezone.utc).isoformat()}

class DadataGeometryCache(GeometryCache):
    def __init__(self,path,token_file):
        p=Path(token_file)
        if p.stat().st_mode&0o077:raise ValueError('Geometry token file must be private')
        self._token=p.read_text().strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,256}',self._token):raise ValueError('Invalid geometry token format')
        super().__init__(path,endpoint=ENDPOINT)
    def lookup(self,address,city):
        req=urllib.request.Request(ENDPOINT,data=json.dumps({'query':address['streetId'],'count':1}).encode(),
            headers={'Content-Type':'application/json','Accept':'application/json',
                'Authorization':'Token '+self._token,'User-Agent':'DonControl/0.1 (public GAR street verification)'},method='POST')
        with urllib.request.urlopen(req,timeout=10) as response:
            raw=response.read(500001)
            if len(raw)>500000:raise ValueError('Geometry reply too large')
            return verify_dadata(json.loads(raw),address,city)
