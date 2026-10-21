"""Deterministic frontend enhancement. Does not modify Android, user addresses or Alisa 2.0."""
from pathlib import Path
from urllib.request import Request,urlopen
import json,re,hashlib,struct

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parent
FOLDER=BASE/'map-v07'
CREST_NAME='Coat_of_arms_of_Shakhty.png'
CREST_SHA1='b0a7b61b41e455d7879c70ae3d13905851594a6a'

def download(url,path,expected=None):
    if path.exists() and (not expected or hashlib.sha1(path.read_bytes()).hexdigest()==expected):return
    request=Request(url,headers={'User-Agent':'CityControlShakhty/0.7 (city symbols; https://github.com/27andrej1976-afk/maximum-shakhty-admin)'})
    with urlopen(request,timeout=35) as response:data=response.read(1500000)
    if expected and hashlib.sha1(data).hexdigest()!=expected:raise RuntimeError('Unexpected asset digest: '+url)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

def assets():
    # Known Commons resource, unchanged pixels. Symbol ownership / attribution documented beside it.
    md5=hashlib.md5(CREST_NAME.encode()).hexdigest()
    url='https://upload.wikimedia.org/wikipedia/commons/'+md5[0]+'/'+md5[:2]+'/'+CREST_NAME
    download(url,FOLDER/'shakhty-coat.png',CREST_SHA1)
    data=(FOLDER/'shakhty-coat.png').read_bytes()
    if data[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',data[16:24])!=(165,220):raise RuntimeError('Unexpected city crest dimensions')
    for name in ['leaflet.js','leaflet.css']:
        download('https://unpkg.com/leaflet@1.9.4/dist/'+name,FOLDER/'vendor'/name)
    download('https://unpkg.com/leaflet@1.9.4/LICENSE',FOLDER/'vendor'/'LICENSE')
    (FOLDER/'ASSETS.md').write_text('''# Asset sources\n\nThe Shakhty coat of arms is reproduced without changing the image.\nResource: https://commons.wikimedia.org/wiki/File:Coat_of_arms_of_Shakhty.png\nVersion: 16 May 2019, 165 × 220 pixels. SHA-1: '''+CREST_SHA1+'''\nOfficial symbol description: City Duma decision 208, 29 February 2012, as amended.\nThe interface explicitly identifies itself as an independent prototype, not a municipal website.\nUse of the city symbol does not imply municipal approval of this application.\n\nLeaflet 1.9.4: https://leafletjs.com, BSD-2-Clause license included in vendor/LICENSE.\nMap tiles and affected road geometry: © OpenStreetMap contributors, ODbL.\nhttps://www.openstreetmap.org/copyright\n\nOnly public road names from published incident notices are submitted to Overpass.\nMaximum 12 newly needed road names per run in one query, cached for 90 days.\nNo home address, device coordinates or other personal data is sent by geometry.py.\n''',encoding='utf-8')

def patch():
    path=BASE/'app-template.txt';text=path.read_text(encoding='utf-8')
    if 'CityMapV07.configure' in text:return
    def replace(old,new):
        nonlocal text
        if text.count(old)!=1:raise RuntimeError('Ambiguous/missing patch marker: '+old[:90])
        text=text.replace(old,new)
    replace('<span class="brand-icon">✳</span>','<img class="brand-icon city-coat" src="./map-v07/shakhty-coat.png" width="44" height="58" alt="Герб города Шахты" />')
    text=re.sub(r'ПРОТОТИП v\d+\.\d+','КАРТА v0.7',text,count=1)
    replace('Аварии, отключения и плановые работы — только те, что могут касаться вас.',
            'У дома и по всему городу: опубликованные аварии, плановые работы и предупреждения.')
    replace('<div class="intro"><div class="eyebrow">',
            '<div class="intro"><p class="city-disclaimer">Шахты · независимый городской мониторинг</p><div class="eyebrow">')
    replace('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="" />',
            '<link rel="stylesheet" href="./map-v07/vendor/leaflet.css" /><link rel="stylesheet" href="./map-v07/city-map.css?v=0.7.0" />')
    replace('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>',
            '<script src="./map-v07/vendor/leaflet.js"></script><script src="./map-v07/city-map.js?v=0.7.0"></script>')
    start=text.index('function makeMap(){');end=text.index('function getMatches(){',start)
    text=text[:start]+'function makeMap(){window.CityMapV07.start();}\nfunction updateMap(){window.CityMapV07.refresh();}\n'+text[end:]
    configure='''window.CityMapV07.configure({state,city:CITY,logic:LGC,getHomeMatches:()=>getMatches(),\n  getRawEvents:()=>state.demo?demoEvents():state.events,fmt:fmtTime,toast});\n'''
    replace("window.addEventListener('DOMContentLoaded',initialise);",configure+"window.addEventListener('DOMContentLoaded',initialise);")
    text=text.replace('КАРТА РАЙОНА','ГОРОД И МОЙ РАЙОН')
    text=re.sub(r'<div class="map-caption">.*?</div>',
        '<div class="map-caption"><span>◎ Контрольная точка</span><span>Цветные линии: улицы из публикаций</span><span>Нажмите метку — подробности и сроки</span></div>',text,count=1)
    if 'CityControlNativeGPSResult' not in text or 'citycontrol://get-location' not in text:raise RuntimeError('GPS integration must not be removed')
    path.write_text(text,encoding='utf-8')
    workflow=ROOT/'.github/workflows/gorod-water.yml';w=workflow.read_text(encoding='utf-8')
    if 'map-v07/geometry.py' not in w:
        anchor='        run: python gorod-control/scripts/collect_services.py'
        if anchor not in w:raise RuntimeError('Collector integration marker missing')
        w=w.replace(anchor,anchor+'\n      - name: Map affected roads from public notices\n        run: python gorod-control/map-v07/geometry.py')
        w=w.replace('          cp gorod-control/data/water.json /tmp/city-control-water.json',
          '          cp gorod-control/data/water.json /tmp/city-control-water.json\n          cp gorod-control/data/map-geometry.json /tmp/city-control-map.json\n          cp gorod-control/data/street-geometry.json /tmp/city-control-streets.json')
        w=w.replace('            cp /tmp/city-control-water.json gorod-control/data/water.json',
          '            cp /tmp/city-control-water.json gorod-control/data/water.json\n            cp /tmp/city-control-map.json gorod-control/data/map-geometry.json\n            cp /tmp/city-control-streets.json gorod-control/data/street-geometry.json')
        w=w.replace('git add gorod-control/data/water.json','git add gorod-control/data/water.json gorod-control/data/map-geometry.json gorod-control/data/street-geometry.json')
        workflow.write_text(w,encoding='utf-8')
    print('CITY MAP applied; native APK and saved-address code retained')

if __name__=='__main__':
    assets();patch()
