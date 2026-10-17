"""Map published affected roads, not guessed fault coordinates. Public municipal data only.
One cached, bounded Overpass query per collection, only named streets from notices.
No user address or position is sent; results are ODbL OpenStreetMap data.
"""
import json, re, os, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode

BASE=Path(__file__).resolve().parents[1]
FEED=BASE/'data/water.json'
CACHE=BASE/'data/street-geometry.json'
OUTPUT=BASE/'data/map-geometry.json'
ENDPOINTS=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter']
TYPES=[('ул',['улица','ул.','ул']),('пер',['переулок','пер.','пер']),('просп',['проспект','просп.','пр-кт','пр-т']),('проезд',['проезд','пр-д']),('пл',['площадь','пл.']),('бул',['бульвар','бул.'])]

def road(raw):
    text=re.sub(r'\s+',' ',str(raw or '').lower().replace('ё','е')).strip(' .,;')
    text=re.sub(r'^(?:г\.?\s*шахты)\s*,?\s*','',text)
    for kind,variants in TYPES:
        for prefix in variants:
            if text.startswith(prefix+' '):return kind,text[len(prefix)+1:].strip()
            if text.endswith(' '+prefix):return kind,text[:-len(prefix)-1].strip()
    return None

def key(raw):
    match=road(raw)
    return ':'.join(match) if match else None

def read(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def shape(element):
    if element.get('type')!='way' or not element.get('tags',{}).get('highway'):return None
    points=[]
    for p in element.get('geometry',[]):
        try:
            lat,lon=float(p['lat']),float(p['lon'])
            if not(47.45<=lat<=48.0 and 39.85<=lon<=40.65):return None
            points.append([round(lat,7),round(lon,7)])
        except (KeyError,ValueError,TypeError):return None
    if len(points)<2:return None
    return {'osmId':element['id'],'line':points}

def variants(raw):
    found=road(raw)
    if not found:return []
    kind,name=found
    terms=next(v for k,v in TYPES if k==kind)
    return [v+' '+name for v in terms]+[name+' '+v for v in terms]

def fetch_roads(names):
    pattern='^('+'|'.join(re.escape(v) for n in names for v in variants(n))+')$'
    # Municipal boundary from OSM; no broad search that could pick an identically named road in another city.
    query=('[out:json][timeout:30];rel(47.55,39.98,47.95,40.50)'
           '["boundary"="administrative"]["name"~"Шахты",i]->.b;'
           '.b out tags;.b map_to_area->.city;'
           'way(area.city)["highway"]["name"~'+json.dumps(pattern,ensure_ascii=False)+',i];out geom;')
    errors=[]
    for endpoint in ENDPOINTS:
        try:
            req=Request(endpoint,data=urlencode({'data':query}).encode(),headers={
                'User-Agent':'CityControl-Shakhty/0.7 (+https://github.com/27andrej1976-afk/maximum-shakhty-admin)',
                'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'})
            with urlopen(req,timeout=40) as response:
                result=json.loads(response.read(2500000))
            if 'elements' not in result or result.get('remark'):raise RuntimeError(str(result.get('remark','Missing elements')))
            boundaries=[(x.get('id'),x.get('tags',{}).get('name')) for x in result['elements'] if x.get('type')=='relation']
            print('MAP municipal boundary',boundaries,'provider',endpoint)
            if not boundaries:raise RuntimeError('Named Shakhty municipal boundary absent')
            return result['elements'],endpoint
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc)[:150])
    raise RuntimeError('; '.join(errors))

def main():
    now=datetime.now(timezone.utc);timestamp=now.timestamp()
    data=read(FEED,{})
    cache=read(CACHE,{'schema':1,'roads':{}})
    if not isinstance(cache.get('roads'),dict):cache={'schema':1,'roads':{}}
    wanted={}
    for event in data.get('events',[]):
        if event.get('category')=='mchs' or event.get('status') in ('resolved','cancelled'):continue
        for a in event.get('affected',[]):
            k=key(a.get('street'))
            if k:wanted[k]=a['street']
    pending=[]
    for k,label in wanted.items():
        existing=cache['roads'].get(k,{})
        age=timestamp-existing.get('timestamp',0)
        if age>(90*86400 if existing.get('segments') else 86400):pending.append(label)
    pending=pending[:12]
    status='cached';error=None
    if pending:
        try:
            elements,endpoint=fetch_roads(pending)
            grouped={key(n):[] for n in pending}
            for item in elements:
                k=key(item.get('tags',{}).get('name'));s=shape(item)
                if k in grouped and s:grouped[k].append(s)
            for k,segments in grouped.items():
                cache['roads'][k]={'timestamp':timestamp,'segments':segments[:45],
                    'provider':'OpenStreetMap','api':endpoint,'note':'Улица из объявления. Не координаты аварии.'}
            status='updated'
            print('MAP GEOMETRY requested',len(pending),'roads; received',len(elements),'segments; matched',sum(bool(s) for s in grouped.values()))
        except Exception as exc:
            status='unavailable';error=str(exc)[:220]
            # Errors are cached briefly so a broken provider is not hammered every run.
            print('MAP GEOMETRY source unavailable:',error)
    public_text={}
    for msg in data.get('archive',[]):
        if msg.get('id'):public_text['water-'+msg['id'].replace('/','-')]=msg.get('text','')
    output={'schema':1,'generatedAt':now.isoformat(),'status':status,'source':'© OpenStreetMap contributors · ODbL',
            'sourceUrl':'https://www.openstreetmap.org/copyright','events':{}}
    if error:output['error']=error
    for event in data.get('events',[]):
        if event.get('category')=='mchs':continue
        features=[]
        for area in event.get('affected',[]):
            k=key(area.get('street'));cached=cache['roads'].get(k,{})
            segments=cached.get('segments',[])
            if not segments:continue
            # Marker is placed on a real point of the longest mapped street segment, labelled as such.
            longest=max(segments,key=lambda v:len(v['line']))['line'];mid=longest[len(longest)//2]
            features.append({'lat':mid[0],'lon':mid[1],'role':'street','label':area['street'],
                             'lines':[v['line'] for v in segments],
                             'osmWays':['https://www.openstreetmap.org/way/'+str(v['osmId']) for v in segments]})
        output['events'][event['id']]={'features':features,
            'affectedKey':json.dumps([[a.get('street'),a.get('houses') or []] for a in event.get('affected',[])],ensure_ascii=False,separators=(',',':')),
            'fullText':public_text.get(event['id'],event.get('fullText') or event.get('description') or ''),
            'note':'Подсвечены улицы, указанные в сообщении. Это не точные границы отключения и не координаты поломки.'}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('MAP catalog',len(output['events']),'events,',sum(bool(e['features']) for e in output['events'].values()),'with mapped streets')

if __name__=='__main__':main()
