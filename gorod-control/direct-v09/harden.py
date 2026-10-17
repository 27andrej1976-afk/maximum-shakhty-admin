from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'android/app/src/main/assets/web'
J=ROOT/'android/app/src/main/java/ru/citycontrol/shakhty'
def replace(s,a,b):
 if a not in s:raise RuntimeError('Missing hardening anchor: '+a[:130])
 return s.replace(a,b,1)
def main():
 p=A/'index.html';s=p.read_text()
 s=replace(s,"return !!s&&s.status==='ok'&&Number.isFinite(age)&&age>=-120000&&age<4*3600000;","return !!s&&['ok','cached'].includes(s.status)&&Number.isFinite(age)&&age>=-120000&&age<(s.status==='cached'?24:4)*3600000;")
 s=replace(s,"st?.status==='stale'?'Нет новых публикаций · источник устарел':","st?.status==='cached'?'Сохранённая официальная сводка · '+(st.note||'повторная проверка недоступна'):st?.status==='stale'?'Нет новых публикаций · источник устарел':")
 s=replace(s,"return ['ok','partial'].includes(by.ursv_device?.status)&&", "return ['ok','partial'].includes(by.ursv_device?.status)&&Date.now()-Date.parse(by.ursv_device.checkedAt||'')<4*3600000&&")
 s=replace(s,"if(e.category==='water')return e.origin==='verified_repost'&&(freshSource(by.repost_rostov)||freshSource(by.repost_don))||e.source==='Администрация города Шахты'&&freshSource(by.city);", "if(e.category==='water')return e.origin==='verified_repost'&&/^https:\/\/rovodokanal\\.ru\/emergency-alerts\/\\d+$/.test(e.officialUrl||'')&&(freshSource(by.repost_rostov)||freshSource(by.repost_don))||e.source==='Администрация города Шахты'&&url.startsWith('https://t.me/admshakhty/')&&freshSource(by.city);")
 s=replace(s,"if(e.category==='power')return e.origin==='official_city_post'&&freshSource(by.power_city)||e.origin==='attributed_repost'&&(freshSource(by.power_repost_don)||freshSource(by.power_repost_rostov));", "if(e.category==='power')return e.origin==='official_city_post'&&url.startsWith('https://t.me/admshakhty/')&&freshSource(by.power_city)||e.origin==='attributed_repost'&&(url.startsWith('https://news-don.ru/')&&freshSource(by.power_repost_don)||url.startsWith('https://newsrostov.ru/')&&freshSource(by.power_repost_rostov));")
 s=replace(s,"if(e.category==='gas')return e.origin==='official_city_post'&&freshSource(by.gas_city);","if(e.category==='gas')return e.origin==='official_city_post'&&url.startsWith('https://t.me/admshakhty/')&&freshSource(by.gas_city);")
 p.write_text(s)
 p=A/'map-v07/city-map.js';s=p.read_text();s=replace(s,"function sourceText(e){","function sourceText(e){\n  if(e.cachedEvidence)return (e.source||'Служба')+' · сохранённая официальная сводка, повторная проверка временно недоступна';")
 p.write_text(s)
 p=J/'DirectClient.java';s=p.read_text();s=replace(s,'now.toEpochMilli()-checked>4*3600000L','now.toEpochMilli()-checked>(s.optString("status").equals("cached")?24:4)*3600000L');p.write_text(s)
 print('CACHE HARDENING: last successful source time preserved; no notifications from cached/ambiguous evidence')
if __name__=='__main__':main()
