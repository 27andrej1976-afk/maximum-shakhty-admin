"""Build offline street reference points from public OSM place polygons + GAR.

Build-time only: osmium/shapely. No public geocoding requests, credentials,
contributor metadata, guessed nearest-town assignment or house coordinates.
"""
import argparse,gzip,hashlib,json,re
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import osmium
from shapely import wkb
from shapely.geometry import LineString,Point,mapping
from shapely.strtree import STRtree
from parse_publications import load_index,norm

KINDS={'улица':'ул.','ул':'ул.','переулок':'пер.','пер':'пер.','проспект':'пр-кт','просп':'пр-кт','пр-т':'пр-кт',
       'бульвар':'б-р','площадь':'пл.','шоссе':'ш.','проезд':'проезд','тупик':'туп.'}

def street_aliases(name):
    clean=norm(name);words=clean.split()
    if words and words[0] in {'им','имени'}:words=words[1:]
    keys={clean,' '.join(words)}
    if len(words)==2 and all(w.isalpha() for w in words):keys|={words[-1],words[0][0]+' '+words[-1]}
    return keys

def compatible_names(a,b):
    def words(name):
        parts=norm(name).split()
        return parts[1:] if parts and parts[0] in {'им','имени'} else parts
    left,right=words(a),words(b)
    if len(left)==2 and len(right)==2 and all(p.isalpha() for p in left+right):
        return left[1]==right[1] and (left[0]==right[0] or len(left[0])==1 and right[0].startswith(left[0]) or len(right[0])==1 and left[0].startswith(right[0]))
    return len(left)==1 or len(right)==1 or left==right

def street_parts(name):
    words=norm(name).split();kind=None
    if not words:return None,''
    if words[0] in KINDS:kind=KINDS[words.pop(0)]
    elif words[-1] in KINDS:kind=KINDS[words.pop()]
    return kind,' '.join(words)

class Extract(osmium.SimpleHandler):
    def __init__(self,names):
        super().__init__();self.names=names;self.factory=osmium.geom.WKBFactory();self.region=None;self.places=[];self.roads=[]
    def area(self,a):
        tags=dict(a.tags);name=tags.get('name:ru',tags.get('name',''));regional=tags.get('ISO3166-2')=='RU-ROS'
        if not regional and not (tags.get('place') in {'city','town','village','hamlet','isolated_dwelling'} and norm(name) in self.names):return
        try:geom=wkb.loads(self.factory.create_multipolygon(a),hex=True)
        except (RuntimeError,ValueError):return
        if not geom.is_valid or geom.is_empty:return
        if regional:self.region=geom;return
        self.places.append({'name':name,'district':tags.get('addr:district',''),'shape':geom,
            'osmId':a.orig_id(),'osmKind':'way' if a.from_way() else 'relation'})
    def way(self,w):
        name=w.tags.get('name:ru',w.tags.get('name',''))
        if not name or w.tags.get('highway') not in {'residential','living_street','pedestrian','unclassified','tertiary','tertiary_link','secondary','secondary_link','primary','primary_link','trunk','trunk_link','service'}:return
        try:coords=[(n.lon,n.lat) for n in w.nodes]
        except osmium.InvalidLocationError:return
        if len(coords)<2 or not any(38.1<x<44.4 and 45.8<y<50.4 for x,y in coords):return
        self.roads.append((w.id,name,LineString(coords)))

def build(pbf,gar,output,report):
    index=load_index(gar);names=defaultdict(list);streets=defaultdict(list);aliases=defaultdict(list)
    for city in index['municipalities']:names[norm(city['name'])].append(city)
    for street in index['streets']:streets[(street['municipalityId'],norm(street['name']))].append(street)
    for street in index['streets']:
        for alias in street_aliases(street['name']):aliases[(street['municipalityId'],alias)].append(street)
    h=Extract(names);h.apply_file(str(pbf),locations=True,idx='flex_mem')
    if h.region is None:raise ValueError('Verified RU-ROS boundary missing from extract')
    places=[];ambiguous=0
    for place in h.places:
        geom=place['shape']
        if not h.region.covers(geom.representative_point()):continue
        choices=names[norm(place['name'])]
        if len(choices)>1:choices=[c for c in choices if any(norm(d) in norm(place['district']) for d in c.get('districts',[]))]
        if len(choices)!=1:ambiguous+=1;continue
        places.append(dict(place,city=choices[0]))
    if not places:raise ValueError('No unambiguous GAR-bound place polygons')
    tree=STRtree([p['shape'] for p in places]);candidates=defaultdict(list);ambiguous_roads=0
    for wid,name,line in h.roads:
        kind,clean=street_parts(name)
        for pi in tree.query(line):
            place=places[int(pi)];city=place['city'];matches=streets.get((city['id'],clean),[])
            if kind:matches=[s for s in matches if s['type']==kind]
            if not matches:
                options={s['id']:s for alias in street_aliases(clean) for s in aliases.get((city['id'],alias),[]) if (not kind or s['type']==kind) and compatible_names(clean,s['name'])}
                matches=list(options.values())
            if len(matches)!=1:continue
            clipped=line.intersection(place['shape'])
            if clipped.is_empty:continue
            pieces=list(clipped.geoms) if clipped.geom_type=='MultiLineString' else [clipped]
            pieces=[p for p in pieces if p.geom_type=='LineString' and p.length>0.00001]
            if not pieces:continue
            piece=max(pieces,key=lambda p:p.length);point=piece.interpolate(.5,normalized=True)
            # Nested places with different GAR IDs cannot silently borrow roads.
            owners={places[int(i)]['city']['id'] for i in tree.query(point) if places[int(i)]['shape'].covers(point)}
            if owners!={city['id']}:ambiguous_roads+=1;continue
            candidates[matches[0]['id']].append((piece.length,wid,point,place,matches[0]))
    with osmium.io.Reader(str(pbf)) as reader:stamp=reader.header().get('osmosis_replication_timestamp')
    sha=hashlib.sha256(Path(pbf).read_bytes()).hexdigest();checked=datetime.now(timezone.utc).isoformat();points={}
    for aid,rows in candidates.items():
        _,wid,point,place,street=max(rows,key=lambda r:(r[0],-r[1]))
        points[aid]={'lat':point.y,'lon':point.x,'geometryVerified':True,'locationPrecision':'street',
            'geometryEvidenceUrl':'https://www.openstreetmap.org/way/'+str(wid),
            'geometryBoundaryEvidenceUrl':'https://www.openstreetmap.org/'+place['osmKind']+'/'+str(place['osmId']),
            'geometryProvider':'OpenStreetMap regional offline extract + GAR','geometryCheckedAt':checked,
            'geometryDataAt':stamp,'geometryNotice':'Ориентир на улице, не точные границы отключения'}
    payload={'schemaVersion':1,'regionId':'RU-ROS','dataAt':stamp,'source':'https://download.geofabrik.de/russia/south-fed-district.html',
        'sourceSha256':sha,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','points':points}
    Path(output).write_bytes(gzip.compress(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    summary={'checkedAt':checked,'osmDataAt':stamp,'sourceSha256':sha,'garVersion':index['version'],
        'verifiedPlacePolygons':len(places),'ambiguousPlacesSkipped':ambiguous,'ambiguousRoadMembershipSkipped':ambiguous_roads,
        'streetReferencePoints':len(points),'coveredGarLocalities':len({r[0][3]['city']['id'] for r in candidates.values()}),
        'guessedNearestPlaceAssignments':0,'houseCoordinates':False,'fullRegionalCoverage':False}
    Path(report).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pbf',required=True);p.add_argument('--gar',required=True);p.add_argument('--output',required=True);p.add_argument('--report',required=True);a=p.parse_args();build(a.pbf,a.gar,a.output,a.report)
