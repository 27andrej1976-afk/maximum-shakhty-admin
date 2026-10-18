"""Make map chrome minimal: top visible licensing, no Leaflet footer, no national flag sprite layers."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'map-v07/city-map.js'
CSS=ROOT/'map-v07/city-map.css'
INDEX=ROOT/'index.html'
def replace(s,a,b):
 if a not in s:raise ValueError('Patch anchor not found: '+a[:125])
 return s.replace(a,b,1)

def main():
 s=JS.read_text(encoding='utf-8')
 assert 'function removeCountryFlagSymbols' not in s
 s=replace(s,
 "function setupBrightBasemap(leafletMap){",
 r"""function removeCountryFlagSymbols(gl) {
  if (!gl?.getStyle||!gl?.setLayoutProperty)return 0;
  let hidden=0;
  for(const layer of gl.getStyle().layers||[]){
    if(layer.type!=='symbol')continue;
    const icon=layer.layout?.['icon-image'];
    if(!/(?:^|[_\s-])(?:flags?|national[-_]flag)(?:$|[_\s-])/i.test(layer.id)&&
       !(icon!=null&&/flags?|national[-_]flag/i.test(JSON.stringify(icon))))continue;
    try{gl.setLayoutProperty(layer.id,'visibility','none');hidden++;}catch(_ignored){}
  }
  return hidden;
}
function setMapCreditType(kind){
  const tileCredit=$('mapCreditTiles');
  if(tileCredit)tileCredit.hidden=kind!=='bright';
}
function setupBrightBasemap(leafletMap){""")
 s=replace(s,
 """  const credits='<a href="https://openfreemap.org/">OpenFreeMap</a> · © <a href="https://openmaptiles.org/">OpenMapTiles</a> · <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';""",
 """  // Required copyright credits are displayed above the map; no provider footer within the map.""" )
 s=replace(s,
 """    attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19""",
 """    maxZoom:19""")
 s=replace(s,
 """  activeBase='fallback';
  const badge=$('mapStyleInfo');""",
 """  activeBase='fallback';
  setMapCreditType('fallback');
  const badge=$('mapStyleInfo');""")
 s=replace(s,
 """    finished=true;activeBase='fallback';vectorBase=null;""",
 """    finished=true;activeBase='fallback';vectorBase=null;setMapCreditType('fallback');""")
 s=replace(s,
 """    const russian=()=>{try{useRussianMapLabels(gl);}catch(_ignored){}};""",
 """    const russian=()=>{try{useRussianMapLabels(gl);removeCountryFlagSymbols(gl);}catch(_ignored){}};""")
 s=replace(s,
 """      leafletMap.attributionControl.addAttribution(credits);
      finished=true;activeBase='bright';vectorBase=modern;note('Светлая карта · OpenFreeMap');""",
 """      finished=true;activeBase='bright';vectorBase=modern;setMapCreditType('bright');note('Светлая карта · OpenFreeMap');""")
 s=replace(s,
 """  if(!cardNode||!toolbar)return;
  const modes=el('div','cm-modes');""",
 """  if(!cardNode||!toolbar)return;
  // Source credit remains visible beside the map and links to original licenses.
  // Only the default Leaflet/footer wording is removed, not the copyright notice.
  const credit=el('div','cm-map-source-credit');credit.id='mapCredit';
  const osm=el('a','','© OpenStreetMap');
  osm.href='https://www.openstreetmap.org/copyright';
  osm.rel='noopener noreferrer';osm.target='_blank';
  const tiles=el('a','','© OpenMapTiles');
  tiles.id='mapCreditTiles';tiles.hidden=true;
  tiles.href='https://openmaptiles.org/';tiles.rel='noopener noreferrer';tiles.target='_blank';
  credit.append(osm,tiles);
  toolbar.firstElementChild.append(credit);
  const modes=el('div','cm-modes');""")
 s=replace(s,
 """    map=root.L.map('map',{zoomControl:false}).setView([h.lat,h.lon],api.state.home?14:12);api.state.map=map;""",
 """    map=root.L.map('map',{zoomControl:false,attributionControl:false}).setView([h.lat,h.lon],api.state.home?14:12);api.state.map=map;""")
 s=replace(s,
 """  getMap:()=>map,getVectorMap:()=>vectorBase?.getMaplibreMap()};""",
 """  getMap:()=>map,getVectorMap:()=>vectorBase?.getMaplibreMap(),hideCountryFlags:removeCountryFlagSymbols};""")
 JS.write_text(s,encoding='utf-8')
 css=CSS.read_text(encoding='utf-8')
 css+="""\n/* Attribution is shown above the map, rather than inside its bottom-right corner.
   Do not remove the mandatory OpenStreetMap / OpenMapTiles credit. */
.cm-map-source-credit{display:flex;align-items:center;flex-wrap:wrap;gap:5px 11px;margin-top:7px;line-height:1.45;font-size:10px;font-weight:650}
.cm-map-source-credit a{color:#65788b;text-decoration:none;border-bottom:1px dotted #9caeba}
.cm-map-source-credit a:hover,.cm-map-source-credit a:focus-visible{color:#0b8574;border-color:currentColor}
.cm-map-source-credit a[hidden]{display:none!important}
#map .leaflet-control-attribution,#map .maplibregl-ctrl-attrib{display:none!important}
@media(max-width:760px){.cm-map-source-credit{font-size:9.5px;line-height:1.5;gap:4px 9px}}
"""
 CSS.write_text(css,encoding='utf-8')
 index=INDEX.read_text(encoding='utf-8')
 index=replace(index,'./map-v07/city-map.js?v=1.0.1-light','./map-v07/city-map.js?v=1.0.2-clean')
 index=replace(index,'./map-v07/city-map.css?v=1.0.0-light','./map-v07/city-map.css?v=1.0.2-clean')
 INDEX.write_text(index,encoding='utf-8')
 print('Map bottom provider footer removed. Compact linked top credits retained. Country flag sprite layers disabled.')
if __name__=='__main__':main()
