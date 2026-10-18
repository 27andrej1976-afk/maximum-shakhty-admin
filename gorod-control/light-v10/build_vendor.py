"""Download fixed-version open-source map libraries into app assets; no API keys."""
from pathlib import Path
from urllib.request import Request,urlopen
import hashlib,json
BASE=Path(__file__).parent/'vendor'
ASSETS={
 'maplibre-gl.js':('https://cdn.jsdelivr.net/npm/maplibre-gl@5.13.0/dist/maplibre-gl.js',200000),
 'maplibre-gl.css':('https://cdn.jsdelivr.net/npm/maplibre-gl@5.13.0/dist/maplibre-gl.css',1000),
 'leaflet-maplibre-gl.js':('https://cdn.jsdelivr.net/npm/@maplibre/maplibre-gl-leaflet@0.0.22/leaflet-maplibre-gl.js',4000),
 'maplibre-LICENSE.txt':('https://cdn.jsdelivr.net/npm/maplibre-gl@5.13.0/LICENSE.txt',500),
 'leaflet-maplibre-LICENSE.txt':('https://cdn.jsdelivr.net/npm/@maplibre/maplibre-gl-leaflet@0.0.22/LICENSE',100)
}
def main():
 BASE.mkdir(parents=True,exist_ok=True)
 report={}
 for name,(url,minimum) in ASSETS.items():
  request=Request(url,headers={'User-Agent':'Shakhty-CityControl/1.0 (software verification)','Accept':'*/*'})
  with urlopen(request,timeout=30) as stream:
   if stream.status!=200:raise RuntimeError(f'{name}: HTTP {stream.status}')
   raw=stream.read(10000000)
  if len(raw)<minimum or len(raw)>8000000:raise RuntimeError(f'{name}: suspicious length {len(raw)}')
  if name.endswith('.js') and b'maplibre' not in raw.lower():raise RuntimeError('Vendor mismatch '+name)
  if name.endswith('.css') and b'maplibre' not in raw.lower():raise RuntimeError('CSS mismatch '+name)
  (BASE/name).write_bytes(raw)
  report[name]={'url':url,'length':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
  print('VENDOR',name,len(raw),report[name]['sha256'],flush=True)
 (BASE/'SHA256S.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__':main()
