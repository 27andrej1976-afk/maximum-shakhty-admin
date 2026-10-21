"""Real installed WebView regression: zoom must not change scope or discard pins."""
from datetime import datetime,timezone,timedelta
evaluate("window.zoomFeed=window.CityControlNativeFeed;window.CityControlNativeFeed=()=>{};window.zoomFetch=window.fetch;true")
evaluate("""(() => {
 (window.panTestMarkers||[]).forEach(marker=>marker.remove());
 window.fetch=(url,opts)=>String(url).includes('nominatim.openstreetmap.org/search')?
 Promise.resolve({ok:true,json:async()=>[{lat:'47.7086',lon:'40.2146',address:{road:'Тестовая улица',house_number:'12'}}]}):zoomFetch(url,opts);
 document.querySelector('#addressButton').click();
 document.querySelector('#addressInput').value='ул. Тестовая, 12';
 document.querySelector('#saveAddressButton').click();
})()""")
for _ in range(30):
 if evaluate("!document.querySelector('#addressDialog').open"):break
 time.sleep(.2)
check(evaluate("JSON.parse(localStorage.getItem('gorod_control_home_v1')).house==='12'"),'Zoom test uses a saved synthetic home')
evaluate('window.fetch=window.zoomFetch;true')
zoom_now=datetime.now(timezone.utc)
zoom_events=[]
for index,(category,source,origin,url) in enumerate([
 ('water','repost_don','municipal_repost','https://news-don.ru/society/zoom-test'),
 ('power','power_direct','official_site','https://donenergo.ru/grafik-otklyucheniy/61/1/'),
 ('gas','gas_city','official_city_post','https://t.me/admshakhty/1')]):
 zoom_events.append({'id':'zoom-'+category,'category':category,'sourceId':source,'origin':origin,'url':url,
  'kind':'emergency','status':'active','title':'Локальная проверка масштаба '+category,'description':'Только тест эмулятора',
  'start':zoom_now.isoformat(),'publishedAt':zoom_now.isoformat(),'end':(zoom_now+timedelta(hours=2)).isoformat(),
  'affected':[{'street':'ул Тестовая' if index==0 else 'пер Другой','houses':['12']}],
  'point':{'lat':47.7086+index*.0002,'lon':40.2146+index*.0002}})
zoom_feed={'schema':2,'checkedAt':zoom_now.isoformat(),'events':zoom_events,
 'sources':[{'id':source,'status':'ok','checkedAt':zoom_now.isoformat()} for source in ['repost_don','power_direct','gas_city']]}
evaluate('zoomFeed('+json.dumps(zoom_feed,ensure_ascii=False)+')')
zoom_home=evaluate("localStorage.getItem('gorod_control_home_v1')")
def zoom_state():
 return evaluate("({mode:CityMapV07.inspect().mode,category:CityMapV07.inspect().category,ids:CityMapV07.inspect().ids.slice().sort(),pins:document.querySelectorAll('.cm-marker').length})")
for scope,button in [('near','cityNearButton'),('city','cityAllButton')]:
 evaluate("document.querySelector('#"+button+"').click();document.querySelector('[data-category=all]').click()")
 expected=zoom_state()
 for zoom in [13,12,14,15,17,13,14]:
  evaluate('CityMapV07.getMap().setZoom('+str(zoom)+',{animate:false});true')
  check(zoom_state()==expected,'Installed '+scope+' mode preserves event IDs and markers at zoom '+str(zoom))
 if scope=='city':check(expected['pins']==3,'Installed city map draws water, power and gas pins')
for category in ['water','power','gas','all']:
 evaluate("document.querySelector('[data-category="+category+"]').click()")
 expected=zoom_state()
 evaluate("CityMapV07.getMap().setZoom(13,{animate:false});CityMapV07.getMap().setZoom(15,{animate:false});CityMapV07.refresh();true")
 check(zoom_state()==expected,'Category '+category+' survives zoom and refresh')
check(evaluate("localStorage.getItem('gorod_control_home_v1')")==zoom_home,'Zoom never changes saved home')
# A real two-finger gesture through the actual Leaflet 13 -> 14 transition.
evaluate("CityMapV07.getMap().setView([47.7086,40.2146],13,{animate:false});document.querySelector('#map').scrollIntoView({block:'center'});true")
expected=zoom_state()
box=evaluate("(()=>{const r=document.querySelector('#map').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
x,y=box['x'],box['y']
touch([(x-30,y),(x+30,y)],'touchStart')
for i in range(1,11):
 touch([(x-30-i*5,y),(x+30+i*5,y)],'touchMove');time.sleep(.03)
touch([],'touchEnd');time.sleep(1)
check(evaluate('CityMapV07.getMap().getZoom()')>=14,'Two-finger zoom crosses the previous failure threshold')
check(zoom_state()==expected,'Water, power and gas survive real pinch zoom near home')
check(evaluate("(()=>{const r=document.querySelector('#map').getBoundingClientRect();return [...document.querySelectorAll('.cm-marker')].every(el=>{const m=el.getBoundingClientRect();return m.right>r.left&&m.left<r.right&&m.bottom>r.top&&m.top<r.bottom&&getComputedStyle(el).display!=='none'&&getComputedStyle(el).visibility!=='hidden'})})()"),'All three nearby marker icons remain visibly inside the map after pinch')
evaluate('window.CityControlNativeFeed=window.zoomFeed;true')
print('ANDROID_ZOOM_SCOPE_PASS',flush=True)
