"""Create a keyless Yandex-like bright basemap using OpenFreeMap, with Leaflet OSM fallback."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'index.html'
JS=ROOT/'map-v07/city-map.js'
CSS=ROOT/'map-v07/city-map.css'
def patch(s,old,new):
    if old not in s: raise RuntimeError("Missing anchor: "+old[:90])
    return s.replace(old,new,1)
def main():
    index=INDEX.read_text(encoding='utf-8')
    js=JS.read_text(encoding='utf-8')
    css=CSS.read_text(encoding='utf-8')
    if "function setupBrightBasemap" in js:
        print('Modern map already present, skipping patch')
        return
    index=patch(index,'<link rel="stylesheet" href="./map-v07/vendor/leaflet.css" />',
        '<link rel="stylesheet" href="./map-v07/vendor/leaflet.css" />\n'
        '  <link rel="stylesheet" href="./light-v10/vendor/maplibre-gl.css" />')
    index=patch(index,'<script src="./map-v07/vendor/leaflet.js"></script>',
        '<script src="./map-v07/vendor/leaflet.js"></script>\n'
        '<script src="./light-v10/vendor/maplibre-gl.js"></script>\n'
        '<script src="./light-v10/vendor/leaflet-maplibre-gl.js"></script>')
    index=patch(index,'./map-v07/city-map.js?v=0.7.0','./map-v07/city-map.js?v=1.0.0-light')
    index=patch(index,'./map-v07/city-map.css?v=0.7.0','./map-v07/city-map.css?v=1.0.0-light')
    index=patch(index,'КАРТА v0.7','КАРТА · СВЕТЛАЯ')
    marker='function configure(options){api=options;}'
    func=r"""let activeBase='fallback',vectorBase=null;
function setupBrightBasemap(leafletMap){
  const credits='<a href="https://openfreemap.org/">OpenFreeMap</a> · © <a href="https://openmaptiles.org/">OpenMapTiles</a> · <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  const osm=root.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19
  }).addTo(leafletMap);
  activeBase='fallback';
  const badge=$('mapStyleInfo');
  const note=message=>{if(badge)badge.textContent=message;};
  note('Светлая карта загружается…');
  if(!root.maplibregl||!root.L.maplibreGL){
    note('Открыта резервная карта');return;
  }
  let modern,gl,finished=false,failures=0;
  const giveUp=()=>{
    if(finished)return;
    finished=true;activeBase='fallback';vectorBase=null;
    if(modern&&leafletMap.hasLayer(modern))leafletMap.removeLayer(modern);
    note('Резервная карта');
  };
  try{
    modern=root.L.maplibreGL({style:'https://tiles.openfreemap.org/styles/bright'});
    modern.addTo(leafletMap);
    gl=modern.getMaplibreMap();
    if(!gl||typeof gl.on!=='function'){giveUp();return;}
    gl.on('idle',()=>{
      if(finished)return;
      if(!gl.isStyleLoaded||!gl.isStyleLoaded())return;
      if(leafletMap.hasLayer(osm))leafletMap.removeLayer(osm);
      leafletMap.attributionControl.addAttribution(credits);
      finished=true;activeBase='bright';vectorBase=modern;note('Светлая карта · OpenFreeMap');
    });
    gl.on('error',()=>{failures++;if(failures>=5)giveUp();});
    setTimeout(()=>{if(!finished)giveUp();},16000);
  }catch(error){giveUp();}
}
"""
    js=patch(js,marker,func+'\n'+marker)
    original="""    root.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19}).addTo(map);"""
    js=patch(js,original,'    setupBrightBasemap(map);')
    js=patch(js,"  const hint=el('p','cm-hint');hint.id='cityMapHint';modes.after(hint);",
             "  const provider=el('span','cm-provider','Светлая карта загружается…');provider.id='mapStyleInfo';modes.append(provider);\n"
             "  const hint=el('p','cm-hint');hint.id='cityMapHint';modes.after(hint);")
    js=patch(js,'zoom:map?.getZoom(),mapped:',"zoom:map?.getZoom(),basemap:activeBase,mapped:")
    css+="\n/* Bright urban atlas: keep warm, softly saturated fallback tiles and readable markers. */\n"
    css+=".leaflet-tile-pane img.leaflet-tile{filter:brightness(1.065) saturate(.80) contrast(.97)}\n"
    css+=".cm-provider{font-size:9px;color:#657b8d;font-weight:700;white-space:nowrap;margin-left:auto}\n"
    css+=".leaflet-control-attribution{background:#ffffffed!important;color:#495866!important}\n"
    css+=".leaflet-control-attribution a{color:#346889!important}\n"
    INDEX.write_text(index,encoding='utf-8')
    JS.write_text(js,encoding='utf-8')
    CSS.write_text(css,encoding='utf-8')
    assert 'function setupBrightBasemap' in JS.read_text()
    assert './light-v10/vendor/maplibre-gl.js' in INDEX.read_text()
    print('Keyless bright map applied; existing map, home location and notification logic preserved')
if __name__=='__main__':main()
