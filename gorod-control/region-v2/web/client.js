/* Shared feed/matching policy. Also executable in Node for deterministic checks. */
(function(root){'use strict';
const categories=['water','power','mchs'];
function safeMax(value){try{const u=new URL(value);return u.protocol==='https:'&&u.hostname==='max.ru'&&!u.username&&!u.password?u.href:null}catch{return null}}
function validFeed(f){
const stamp=x=>typeof x==='string'&&Number.isFinite(Date.parse(x)),str=x=>typeof x==='string';
return !!(f&&f.schemaVersion===1&&f.mode==='max-only'&&f.regionId==='RU-ROS'&&['test','production'].includes(f.dataMode)&&stamp(f.generatedAt)&&Array.isArray(f.events)&&Array.isArray(f.municipalities)&&Array.isArray(f.pendingPublications)
&&f.municipalities.every(m=>m&&str(m.id)&&str(m.name)&&categories.every(c=>m.health?.[c]&&['read','unavailable','unconfigured','partial'].includes(m.health[c].state)&&str(m.health[c].message)&&(m.health[c].lastSuccessAt==null||stamp(m.health[c].lastSuccessAt))))
&&f.events.every(e=>e&&str(e.id)&&str(e.title)&&categories.includes(e.category)&&safeMax(e.url)&&stamp(e.publishedAt)&&stamp(e.expiresAt)&&['municipality','region'].includes(e.scope)&&(e.scope==='region'?e.category==='mchs':str(e.municipalityId))&&Array.isArray(e.addresses)&&e.addresses.every(a=>a&&str(a.id)&&str(a.label)))
&&f.pendingPublications.every(p=>p&&str(p.id)&&stamp(p.publishedAt)&&str(p.text)&&str(p.message)&&safeMax(p.url)));
}
function distance(a,b){const rad=x=>x*Math.PI/180;const dlat=rad(b.lat-a.lat),dlon=rad(b.lon-a.lon);return 6371*2*Math.asin(Math.min(1,Math.sqrt(Math.sin(dlat/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(b.lat))*Math.sin(dlon/2)**2)))}
function point(a){return a?.geometryVerified===true&&Number.isFinite(a.lat)&&Number.isFinite(a.lon)&&Math.abs(a.lat)<=90&&Math.abs(a.lon)<=180}
function streetLines(a){const g=a?.streetGeometry,lines=g?.coordinates;if(a?.streetGeometryVerified!==true||g?.type!=='MultiLineString'||!Array.isArray(lines)||!lines.length||lines.length>256)return [];let count=0;for(const line of lines){if(!Array.isArray(line)||line.length<2)return [];for(const c of line){if(++count>4096||!Array.isArray(c)||c.length!==2||!c.every(Number.isFinite)||c[0]<38.1||c[0]>44.4||c[1]<45.8||c[1]>50.4)return []}}return lines}
function visible(e,now=Date.now()){return !!(e&&!e.requiresReview&&categories.includes(e.category)&&safeMax(e.url)&&Number.isFinite(Date.parse(e.expiresAt))&&Date.parse(e.expiresAt)>now&&Date.parse(e.publishedAt)<=now+5*60e3&&!['resolved','cancelled'].includes(e.status))}
function nearby(e,home,radius){return e.scope==='region'||!!(home&&(e.addresses||[]).some(a=>point(a)&&distance(home,a)<=radius))}
function select(f,{city='',category='all',scope='region',home=null,radius=1},now=Date.now()){return (f?.events||[]).filter(e=>visible(e,now)&&(category==='all'||category===e.category)&&(e.scope==='region'||!city||city===e.municipalityId)&&(scope!=='near'||nearby(e,home,radius)))}
function attention(f,category='all',now=Date.now()){return (f?.pendingPublications||[]).filter(p=>!p.partiallyAccepted&&(category==='all'||p.category===category)&&Date.parse(p.publishedAt)<=now&&now-Date.parse(p.publishedAt)<=36*3600e3).slice(0,5)}
function health(f,city,offline,now=Date.now()){
const states={};const stale=!f||now-Date.parse(f.generatedAt)>15*60e3||Date.parse(f.generatedAt)>now+5*60e3;
for(const category of categories){const relevant=(f?.municipalities||[]).filter(m=>!city||m.id===city).map(m=>m.health?.[category]).filter(Boolean);let state='unconfigured',message='Охват этой категории для выбранной территории пока не подтверждён';
if(relevant.length){state=relevant.every(s=>s.state==='read')?'read':relevant.every(s=>s.state==='unconfigured')?'unconfigured':relevant.every(s=>s.state==='unavailable')?'unavailable':'partial';message=city?relevant[0].message:'Областной охват неполный; состояние отдельных территорий различается'}
if(!city&&state==='read'&&f?.coverage!=='full')state='partial';
if(offline||stale){state='unavailable';message=offline?'Нет связи с сервером. Показаны сохранённые сведения':'Сводка давно не обновлялась. Текущее состояние источников не подтверждено'}
const stamps=relevant.map(s=>s.lastSuccessAt).filter(Boolean).sort((a,b)=>Date.parse(a)-Date.parse(b));states[category]={state,message,lastSuccessAt:stamps[0]||null};}
return states}
const api={categories,safeMax,validFeed,distance,point,streetLines,visible,nearby,select,attention,health};root.DonClient=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
