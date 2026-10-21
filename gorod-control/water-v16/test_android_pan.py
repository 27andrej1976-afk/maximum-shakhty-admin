"""Executed in android_test.py's inspected WebView; offline vector fixture, real touch input."""
# Use the installed adapter and map, but a deterministic style with no external tiles.
evaluate("""(() => {
 const map=CityMapV07.getMap();
 // Replace the base layer: two relative GL containers would stack vertically.
 map.eachLayer(layer=>{if(layer instanceof L.MaplibreGL || layer instanceof L.GridLayer)map.removeLayer(layer);});
 document.querySelector('#map').scrollIntoView({block:'center'});
 map.invalidateSize({animate:false});
 map.setView([47.7086,40.2146],14,{animate:false});
 window.panTestLayer=L.maplibreGL({style:{version:8,sources:{},layers:[
   {id:'background',type:'background',paint:{'background-color':'#e6eee8'}}]}}).addTo(map);
 window.panTestMarkers=[L.marker([47.7086,40.2146],{icon:L.divIcon({className:'cm-marker',html:'<div class="cm-pin">💧</div>',iconSize:[38,38],iconAnchor:[19,19]})}).addTo(map),
 L.marker([47.71,40.217],{icon:L.divIcon({className:'cm-marker',html:'<div class="cm-pin">♨</div>',iconSize:[38,38],iconAnchor:[19,19]})}).addTo(map)];
})()""")
for _ in range(30):
 if evaluate('panTestLayer.getMaplibreMap().isStyleLoaded()'):break
 time.sleep(.5)
check(evaluate('panTestLayer.getMaplibreMap().isStyleLoaded()'),'Installed vector renderer loads offline test style')
def snapshot():
 return evaluate("""(() => {
 const m=CityMapV07.getMap(),g=panTestLayer.getMaplibreMap(), a=m.getContainer().getBoundingClientRect(),b=g.getContainer().getBoundingClientRect();
 const c=m.getCenter(),v=g.getCenter();
 return {center:[c.lat,c.lng],glCenter:[v.lat,v.lng],zoom:m.getZoom(),glZoom:g.getZoom(),
 errors:panTestMarkers.map(marker=>{
  const ll=marker.getLatLng(),p=m.latLngToContainerPoint(ll),q=g.project([ll.lng,ll.lat]);
  const icon=marker.getElement().getBoundingClientRect();
  return Math.max(Math.abs(a.left+p.x-b.left-q.x),Math.abs(a.top+p.y-b.top-q.y),Math.abs(icon.left+19-a.left-p.x),Math.abs(icon.top+19-a.top-p.y));
 }),box:{x:a.x,y:a.y,w:a.width,h:a.height}};
})()""")
def touch(points,kind):
 global seq
 seq+=1; identity=seq
 ws.send(json.dumps({'id':identity,'method':'Input.dispatchTouchEvent','params':{'type':kind,'touchPoints':[{'x':x,'y':y,'id':i} for i,(x,y) in enumerate(points)]}}))
 while True:
  d=json.loads(ws.recv())
  if d.get('id')==identity:
   if d.get('error'):raise RuntimeError(str(d['error']))
   break
print('ANDROID_PAN_INITIAL',json.dumps(snapshot()),flush=True)
check(max(snapshot()['errors'])<5,'Initial vector and marker pixel alignment')
for direction in (1,-1):
 before=snapshot();b=before['box'];x=b['x']+b['w']*.5;y=b['y']+b['h']*.48
 touch([(x,y)],'touchStart')
 for i in range(1,13):
  touch([(x+direction*70*i/12,y+direction*35*i/12)],'touchMove');time.sleep(.025)
 touch([],'touchEnd');time.sleep(1)
 after=snapshot()
 print('ANDROID_PAN_AFTER',json.dumps(after),flush=True)
 check(max(abs(a-b) for a,b in zip(before['center'],after['center']))>.0001,'Touch swipe moves map '+str(direction))
 check(max(abs(a-b) for a,b in zip(after['center'],after['glCenter']))<.0001,'Vector and marker centers agree after swipe '+str(direction))
 check(max(after['errors'])<5,'Water and gas marker pixels stay aligned after swipe '+str(direction))
b=snapshot()['box'];x=b['x']+b['w']*.5;y=b['y']+b['h']*.5
before=snapshot()
touch([(x-35,y),(x+35,y)],'touchStart')
for i in range(1,11):
 touch([(x-35-i*4,y),(x+35+i*4,y)],'touchMove');time.sleep(.03)
touch([],'touchEnd');time.sleep(1)
after=snapshot()
check(after['zoom']>before['zoom'],'Two-finger pinch changes zoom')
check(abs(after['glZoom']-(after['zoom']-1))<.01 and max(after['errors'])<5,'Vector and water/gas markers aligned after pinch')
evaluate("CityMapV07.getMap().setZoom(13,{animate:false});true")
time.sleep(.5)
check(max(snapshot()['errors'])<5,'Programmatic zoom preserves alignment')
evaluate("document.querySelector('#map').style.height='280px';CityMapV07.getMap().invalidateSize({animate:false});true")
time.sleep(1)
check(max(snapshot()['errors'])<5,'Map resize preserves alignment')
print('ANDROID_PAN_SNAPSHOT',json.dumps(snapshot()),flush=True)
