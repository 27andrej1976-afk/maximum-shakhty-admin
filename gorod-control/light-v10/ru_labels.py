"""Fix OpenFreeMap Bright city labels to prefer Russian names, preserve house numbers and road shields."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'map-v07/city-map.js'
def main():
 s=PATH.read_text(encoding='utf-8')
 marker="function setupBrightBasemap(leafletMap){"
 assert marker in s
 if 'function useRussianMapLabels' in s:
  print('RU labels already installed');return
 code=r"""function useRussianMapLabels(gl){
  if(!gl||!gl.getStyle||!gl.setLayoutProperty)return 0;
  let localized=0;
  for(const layer of gl.getStyle().layers||[]){
    if(layer.type!=='symbol'||layer.layout?.['text-field']==null)continue;
    if(/housenumber|house_number|shield|route|highway_ref|junction/i.test(layer.id))continue;
    const text=JSON.stringify(layer.layout['text-field']);
    if(!/name(?::|_|"|')/i.test(text))continue;
    try{
      gl.setLayoutProperty(layer.id,'text-field',[
        'coalesce',['get','name:ru'],['get','name_ru'],['get','name']
      ]);
      localized++;
    }catch(_ignored){}
  }
  return localized;
}
"""
 s=s.replace(marker,code+'\n'+marker,1)
 needle="    gl=modern.getMaplibreMap();\n    if(!gl||typeof gl.on!=='function'){giveUp();return;}"
 replacement="""    gl=modern.getMaplibreMap();
    if(!gl||typeof gl.on!=='function'){giveUp();return;}
    const russian=()=>{try{useRussianMapLabels(gl);}catch(_ignored){}};
    gl.on('style.load',russian);
    if(gl.isStyleLoaded?.())russian();"""
 assert needle in s, 'Map initialization anchor not found'
 s=s.replace(needle,replacement,1)
 s=s.replace("  getMap:()=>map};","  getMap:()=>map,getVectorMap:()=>vectorBase?.getMaplibreMap()};",1)
 PATH.write_text(s,encoding='utf-8')
 print('RU label support ready; name:ru -> name_ru -> original name')
if __name__=='__main__':main()
