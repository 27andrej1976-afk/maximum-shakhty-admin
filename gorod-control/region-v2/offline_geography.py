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
    for p in points.values():
        if p.get("streetGeometryVerified") and not valid_street_geometry(p):raise ValueError("Invalid offline street line geometry")
    return points


def valid_street_geometry(point):
    if point.get('streetGeometryVerified') is not True:return False
    shape=point.get('streetGeometry',{})
    if shape.get('type')!='MultiLineString':return False
    lines=shape.get('coordinates')
    if not isinstance(lines,list) or not 1<=len(lines)<=256:return False
    count=0
    for line in lines:
        if not isinstance(line,list) or len(line)<2:return False
        for c in line:
            count+=1
            if (count>4096 or not isinstance(c,list) or len(c)!=2
                or any(type(n) not in (int,float) or not math.isfinite(n) for n in c)
                or not(38.1<=c[0]<=44.4 and 45.8<=c[1]<=50.4)):return False
    return True
