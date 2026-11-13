"""Load the versioned offline public street reference catalogue, not house pins."""
import gzip,json,math
from pathlib import Path

NAME='osm-streets-20261112.json.gz'

def load_offline_points(path,index):
    path=Path(path)
    if not path.is_file():return {}
    if path.stat().st_size>8*1024*1024:raise ValueError('Offline geometry compressed size limit')
    raw=gzip.decompress(path.read_bytes())
    if len(raw)>32*1024*1024:raise ValueError('Offline geometry size limit')
    data=json.loads(raw);ids={s['id'] for s in index['streets']}
    if data.get('schemaVersion')!=1 or data.get('regionId')!='RU-ROS' or data.get('license')!='ODbL-1.0':raise ValueError('Unverified offline geometry catalogue')
    points=data.get('points',{})
    for aid,p in points.items():
        if (aid not in ids or p.get('geometryVerified') is not True or p.get('locationPrecision')!='street'
                or any(type(p.get(k)) not in (float,int) or not math.isfinite(p[k]) for k in ['lat','lon'])
                or not (45.8<=p['lat']<=50.4 and 38.1<=p['lon']<=44.4)
                or not p.get('geometryEvidenceUrl','').startswith('https://www.openstreetmap.org/way/')
                or not p.get('geometryBoundaryEvidenceUrl','').startswith('https://www.openstreetmap.org/')):
            raise ValueError('Invalid offline street geometry evidence')
    return points
