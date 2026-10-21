"""Checks the installed Compact APK; fixtures never leave the emulator."""
from datetime import datetime,timezone,timedelta
# Freeze native deliveries while deterministic UI checks are in progress.
evaluate("window.auditFeed=window.CityControlNativeFeed;window.CityControlNativeFeed=()=>{};true")
now=datetime.now(timezone.utc)
stamp=now.isoformat()
sources=[{'id':s,'status':'ok','checkedAt':stamp} for s in ('water_kvu','repost_don','power_direct','gas_city')]
def event(ident,cat,origin,source,url,street='ул Тестовая'):
 return {'id':ident,'category':cat,'kind':'emergency','status':'active','sourceId':source,'origin':origin,
 'url':url,'title':'Контрольный пример '+cat,'description':'Локальная проверка',
 'start':stamp,'end':(now+timedelta(hours=2)).isoformat(),
 'affected':[{'street':street,'houses':['12']}],'point':None}
water=event('audit-water','water','municipal_repost','repost_don','https://news-don.ru/society/test')
power=event('audit-power','power','official_site','power_direct','https://donenergo.ru/grafik-otklyucheniy/61/1/')
gas=event('audit-gas','gas','official_city_post','gas_city','https://t.me/admshakhty/1')
feed={'schema':2,'checkedAt':stamp,'sources':sources,'events':[water,power,gas]}
def inject(data):evaluate('auditFeed('+json.dumps(data,ensure_ascii=False)+')')
inject(feed)
evaluate("document.querySelector('#cityAllButton').click()")
for cat,ident in [('water','audit-water'),('power','audit-power'),('gas','audit-gas')]:
 evaluate("document.querySelector('[data-category="+cat+"]').click()")
 check(evaluate("JSON.stringify(CityMapV07.inspect().ids)")==json.dumps([ident],separators=(',',':')),'Category filter '+cat+' isolates correct event')
evaluate("document.querySelector('[data-category=all]').click()")
check(len(evaluate("CityMapV07.inspect().ids"))==3,'All category filter restores all events')
# Old and failed sources cannot make current-looking events appear.
import copy
stale=copy.deepcopy(feed)
for s in stale['sources']:s['checkedAt']=(now-timedelta(hours=5)).isoformat()
inject(stale)
check(evaluate("CityMapV07.inspect().allIds.length")==0,'Stale source timestamps hide unverified events')
failed=copy.deepcopy(feed)
for s in failed['sources']:s['status']='error'
inject(failed)
check(evaluate("CityMapV07.inspect().allIds.length")==0,'Failed sources hide unverified events')
inject(feed)
# Open a real event card and check text is rendered safely.
evaluate("document.querySelector('[data-event-id=audit-water] .cm-detail-button').click()")
check(evaluate("document.querySelector('#cityEventDetail').open"),'Water event details open')
check(evaluate("document.querySelector('#cityEventBody').textContent.includes('перепечатка')"),'Water provenance is visible')
evaluate("document.querySelector('#cityEventClose').click()")
# Exercise manual address entry with a deterministic geocoder in the emulator only.
evaluate("""(() => {
 window.auditFetch=window.fetch;
 window.fetch=(url,opts)=>String(url).includes('nominatim.openstreetmap.org/search')?
 Promise.resolve({ok:true,json:async()=>[{lat:'47.7086',lon:'40.2146',address:{road:'Тестовая улица',house_number:'12'}}]}):auditFetch(url,opts);
 document.querySelector('#addressButton').click();
 document.querySelector('#addressInput').value='ул. Тестовая, 12';
 document.querySelector('#saveAddressButton').click();
})()""")
for _ in range(30):
 if evaluate("!!localStorage.getItem('gorod_control_home_v1')"):break
 time.sleep(.2)
home=evaluate("JSON.parse(localStorage.getItem('gorod_control_home_v1'))")
check(home.get('house')=='12' and home.get('method')=='address','Manual home address persists on device')
check(evaluate("!document.querySelector('#addressDialog').open"),'Address dialog closes after saving')
evaluate("window.fetch=window.auditFetch;true")
inject(feed)
check(evaluate("!document.querySelector('#checkButton').disabled"),'Refresh callback releases update button')
# Verify address logic used by the installed app, including street vs lane.
check(evaluate("CityLogic.matchImpact("+json.dumps(water,ensure_ascii=False)+","+json.dumps(home,ensure_ascii=False)+").relevant"),'Own house receives matching event')
different=copy.deepcopy(water);different['affected'][0]['houses']=['14']
check(not evaluate("CityLogic.matchImpact("+json.dumps(different,ensure_ascii=False)+","+json.dumps(home,ensure_ascii=False)+").relevant"),'Other house on same street is excluded')
different['affected'][0]={'street':'пер Тестовая','houses':['12']}
check(not evaluate("CityLogic.matchImpact("+json.dumps(different,ensure_ascii=False)+","+json.dumps(home,ensure_ascii=False)+").relevant"),'Street and lane are not confused')
check(evaluate("document.documentElement.scrollWidth<=innerWidth+1"),'Compact layout has no horizontal overflow')
evaluate("window.CityControlNativeFeed=window.auditFeed;true")
print('COMPACT_BEHAVIOUR_PASS',flush=True)
