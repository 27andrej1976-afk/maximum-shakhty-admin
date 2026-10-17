"""Small tested refinements applied in the feature build before publication."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent

def patch(path,old,new):
    text=path.read_text(encoding='utf-8')
    if new in text:return
    if old not in text:raise RuntimeError('Missing refinement anchor in '+str(path)+': '+old[:80])
    path.write_text(text.replace(old,new),encoding='utf-8')

geo=FOLDER/'geometry.py'
text=geo.read_text(encoding='utf-8')
start=text.index("    query='[out:json][timeout:30];")
end=text.index('\n    errors=[]',start)
query="""    query=('[out:json][timeout:30];rel(47.55,39.98,47.95,40.50)'
           '[\"boundary\"=\"administrative\"][\"name\"~\"Шахты\",i]->.b;'
           '.b out tags;.b map_to_area->.city;'
           'way(area.city)[\"highway\"][\"name\"~'+json.dumps(pattern,ensure_ascii=False)+',i];out geom;')"""
text=text[:start]+query+text[end:]
text=text.replace("            return result['elements'],endpoint", "            boundaries=[(x.get('id'),x.get('tags',{}).get('name')) for x in result['elements'] if x.get('type')=='relation']\n            print('MAP municipal boundary',boundaries,'provider',endpoint)\n            if not boundaries:raise RuntimeError('Named Shakhty municipal boundary absent')\n            return result['elements'],endpoint")
geo.write_text(text,encoding='utf-8')
js=FOLDER/'city-map.js'
patch(js,"let mounted=false,lastDetail=null,previousFocus=null;", "let mounted=false,lastDetail=null,previousFocus=null;\nlet geometryLoading=false,geometryStamp=null;")
helper="""function loadGeometry(){
  const stamp=api.state.checkedAt||'initial';
  if(geometryLoading||geometryStamp===stamp)return;
  geometryLoading=true;geometryStamp=stamp;
  fetch('./data/map-geometry.json?_='+Date.now(),{cache:'no-store'})
    .then(r=>{if(!r.ok)throw Error('geometry');return r.json();})
    .then(data=>{if(data&&data.schema===1&&data.events&&typeof data.events==='object')geo=data;})
    .catch(()=>{})
    .finally(()=>{geometryLoading=false;refresh();});
}
function refresh(){
  if(!mounted)return;
  loadGeometry();"""
patch(js,"function refresh(){\n  if(!mounted)return;",helper)
txt=js.read_text(encoding='utf-8')
start=txt.index("  fetch('./data/map-geometry.json',{cache:'no-cache'})")
end=txt.index("\n}\nroot.CityMapV07=",start)
txt=txt[:start]+txt[end:]
js.write_text(txt,encoding='utf-8')
test=FOLDER/'test_browser.py'
patch(test,"page.route('**/data/map-geometry.json',", "page.route('**/data/map-geometry.json*',")
patch(test,"    page.wait_for_function('CityMapV07.inspect().mapped===1')", "    page.wait_for_function('CityMapV07.inspect().mapped===1')")
patch(test,"    livepage.screenshot(path=str(REPORT/'mobile-live-top.png'))", "    livepage.wait_for_timeout(3000)\n    livepage.evaluate('window.scrollTo(0,0)')\n    livepage.screenshot(path=str(REPORT/'mobile-live-top.png'))")
patch(test,"desktop.wait_for_timeout(800)","desktop.wait_for_timeout(4800)")
# Incident deadlines are always displayed in the city's timezone, not the developer runner's UTC.
index=ROOT/'gorod-control'/'index.html'
patch(index,"{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}", "{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Moscow'}")
print('CITY MAP refinements installed')
