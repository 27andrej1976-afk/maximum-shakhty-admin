/* Compact city-first presentation only: does not alter sources, GPS, events, map, notifications. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
function text(t,s){const e=document.createElement(t);e.textContent=s;return e;}
function wrapper(cls){const e=document.createElement('div');e.className=cls;return e;}
function details(id,title,group){
 const d=document.createElement('details');d.id=id;d.className='compact-fold';
 const s=document.createElement('summary');const titleSpan=text('span',title);
 const right=text('span','▾');right.className='compact-caret';
 s.append(titleSpan,right);d.append(s);group.append(d);return d;
}
function move(node,parent){if(node&&parent)parent.append(node);}
function showSection(d,target){
 if(d)d.open=true;
 if(target)target.scrollIntoView({behavior:'smooth',block:'start'});
}
function init(){
 if(!window.CityMapV07||$('compactNav'))return;
 const app=document.querySelector('main.main');
 const left=app?.querySelector('.left-panel'),right=app?.querySelector('.right-panel');
 if(!app||!left||!right)return;
 const intro=left.querySelector('.intro'),address=left.querySelector('.control-card'),overview=$('overviewCard');
 const toolbar=left.querySelector('.toolbar'),heading=left.querySelector('.events-heading');
 const filters=left.querySelector('.filters'),eventList=$('eventList'),notice=left.querySelector('.notification-card');
 const mapCard=right.querySelector('.map-card'),source=right.querySelector('.sources');
 if(!intro||!address||!overview||!toolbar||!heading||!filters||!eventList||!notice||!mapCard||!source)return;

 app.classList.add('compact-main');
 // Move EXISTING elements; do not duplicate event controls or data. Existing ID references remain stable.
 const introTitle=intro.querySelector('h1');
 const headline=wrapper('compact-headline');
 headline.append(text('span','Шахты · события рядом с вами'));
 if(introTitle)headline.append(introTitle);
 const metrics=wrapper('compact-metrics');
 function metric(id,initial,label,cls){
   const card=wrapper('compact-metric '+cls);
   const number=text('b',initial);number.id=id;
   card.append(number,text('small',label));metrics.append(card);
 }
 metric('compactAllCount','—','Событий в городе','compact-blue');
 metric('compactMapCount','—','На карте','compact-green');
 metric('compactLocalCount','—','У моего дома','compact-amber');

 app.append(headline,metrics,address,overview,toolbar,mapCard,notice);
 const local=details('compactLocalFold','Предупреждения по моему адресу',app);
 move(heading,local);move(filters,local);move(eventList,local);
 const services=details('compactSourcesFold','Проверенные публикации и источники',app);
 move(source,services);
 const settings=details('compactSettingsFold','Дополнительные настройки',app);
 const radius=address.querySelector('.radius');
 const hint=$('addressHint'),demo=$('demoButton');
 if(radius)settings.append(radius);
 if(hint)settings.append(hint);
 if(demo){const demoBox=wrapper('compact-demo-wrapper');demoBox.append(text('p','Учебные события используются только для проверки интерфейса. Они не являются реальными авариями.'));demoBox.append(demo);settings.append(demoBox);}
 const foot=document.querySelector('.site-footer');
 if(foot)foot.classList.add('compact-legal');

 // Keep existing mode switch and map event filters operable. Hide verbose lists, not their data.
 const map=$('map'),mapFilter=mapCard.querySelector('.cm-filters');
 if(map&&mapFilter)map.parentNode.insertBefore(mapFilter,map);
 const scope=$('cityMapScope'),counts=$('cityMapCounts'),deck=$('cityMapEvents'),quality=$('cityMapQuality');
 if(scope&&counts&&deck&&quality){
   const fold=details('compactCityFold','Все городские события · подробный список',mapCard);
   fold.append(scope,counts,deck,quality);
 }
 const caption=mapCard.querySelector('.map-caption');
 if(caption)caption.classList.add('compact-map-caption');
 const modeBar=mapCard.querySelector('.cm-modes');
 if(modeBar)modeBar.classList.add('compact-mode-bar');

 // Navbar: actual destinations, no nonfunctional decorative controls.
 const nav=document.createElement('nav');nav.id='compactNav';nav.className='compact-nav';
 nav.setAttribute('aria-label','Навигация');
 function navItem(icon,label,fn){
   const b=document.createElement('button');b.type='button';
   b.append(text('span',icon),text('small',label));
   b.addEventListener('click',()=>{
     for(const x of nav.querySelectorAll('button'))x.classList.toggle('selected',x===b);
     fn();
   });
   nav.append(b);return b;
 }
 const homeItem=navItem('⌂','Главная',()=>window.scrollTo({top:0,behavior:'smooth'}));
 homeItem.classList.add('selected');
 navItem('▣','Карта',()=>mapCard.scrollIntoView({behavior:'smooth',block:'start'}));
 navItem('♧','Оповещения',()=>showSection(local,local));
 navItem('☷','Ещё',()=>showSection(services,services));
 document.body.append(nav);

 // Fresh event counts read from the real existing map state, not samples.
 const update=()=>{
   try{
     const state=window.CityMapV07.inspect();
     $('compactAllCount').textContent=String(state.allIds.length);
     const detail=$('cityMapCounts')?.textContent||'';
     const pins=detail.match(/(\d+)\s+с привязкой/);
     $('compactMapCount').textContent=pins?pins[1]:String(state.mapped);
     $('compactLocalCount').textContent=$('eventsCount')?.textContent||'0';
     const localSummary=local.querySelector('summary>span');
     if(localSummary)localSummary.textContent='Предупреждения по моему адресу · '+($('eventsCount')?.textContent||'0');
   }catch(_){}
 };
 const obs=new MutationObserver(update);
 for(const node of [$('eventsCount'),$('cityMapCounts'),$('cityMapScope')])if(node)obs.observe(node,{childList:true,subtree:true,characterData:true});
 update();
 // Scroll changes must not change saved home or active notice category.
 window.setTimeout(()=>window.CityMapV07.getMap()?.invalidateSize?.(),140);
 window.setTimeout(()=>window.CityMapV07.getMap()?.invalidateSize?.(),1100);
 left.remove();right.remove();
}
window.addEventListener('DOMContentLoaded',init);
})();