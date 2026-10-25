/* City map v0.7. City browsing never changes the user's saved home or notifications. */
(function(root){
'use strict';
let api=null,map=null,layer=null,homeLayer=null,homeKey='',mode='near',category='all',geo={events:{}};
let mounted=false,lastDetail=null,previousFocus=null;
let geometryLoading=false,geometryStamp=null;
const CITY_BOUNDS=[[47.61,40.075],[47.86,40.385]];
const colors={water:'#267bc8',power:'#b97812',gas:'#ce4e48',mchs:'#7563af',other:'#64758b'};
const icons={water:'💧',power:'⚡',gas:'♨',mchs:'⚠',other:'!'};
const names={water:'Вода',power:'Электричество',gas:'Газ',mchs:'МЧС',other:'Город'};
const $=id=>document.getElementById(id);
function el(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!=null)node.textContent=String(text);return node;}
function validPoint(p){return !!p&&p.lat!==null&&p.lon!==null&&Number.isFinite(Number(p.lat))&&Number.isFinite(Number(p.lon))&&Number(p.lat)>=47.45&&Number(p.lat)<=48.0&&Number(p.lon)>=39.85&&Number(p.lon)<=40.65;}
function isCurrent(e,now=Date.now()){
  if(!e||!e.id||['resolved','cancelled','canceled'].includes(e.status))return false;
  const end=Date.parse(e.end||''),start=Date.parse(e.start||''),pub=Date.parse(e.publishedAt||'');
  if(Number.isFinite(pub)&&pub>now+1800000)return false;
  if(e.category==='mchs')return Number.isFinite(end)&&end>=now;
  if(Number.isFinite(start)&&start>now+14*86400000)return false;
  if(e.category==='power'||e.category==='water')return now<Date.parse(e.end||e.start||e.publishedAt||e.observedAt||'')+36*3600000;
  if(Number.isFinite(end)&&end<now-24*3600000)return false;
  if(e.kind!=='planned'&&!Number.isFinite(end)&&Number.isFinite(pub)&&pub<now-48*3600000)return false;
  return true;
}
function allEvents(){
  if(!api)return [];
  const ids=new Map();
  for(const e of api.getRawEvents()||[])if(isCurrent(e))ids.set(e.id,e);
  return Array.from(ids.values()).sort((a,b)=>{
    const rank=e=>e.category==='mchs'?3:e.kind==='planned'?2:e.status==='unconfirmed'?1:0;
    return rank(a)-rank(b)||(Date.parse(b.publishedAt||b.start||'')||0)-(Date.parse(a.publishedAt||a.start||'')||0);
  });
}
function nearEvents(){const ids=new Set((api.getHomeMatches()||[]).map(x=>x.event.id));return allEvents().filter(e=>ids.has(e.id));}
function visible(){return (mode==='city'?allEvents():nearEvents()).filter(e=>category==='all'||e.category===category);}
function format(d){return d?api.fmt(d):'Не указано';}
function safeURL(raw){try{const u=new URL(raw);return u.protocol==='https:'?u.href:null;}catch(_){return null;}}
function statusText(e){
  if(e.category==='mchs')return e.priority==='high'?'Предупреждение МЧС':'Прогноз МЧС, не сообщение о происшествии';
  const end=Date.parse(e.end||'');
  if(e.status==='unconfirmed'||Number.isFinite(end)&&end<Date.now())return 'Завершение не подтверждено';
  if(e.kind==='planned')return Date.parse(e.start||'')>Date.now()?'Запланировано':'Плановые работы по объявлению';
  return 'Опубликовано сообщение об аварии';
}
function timing(e){
  if(e.category==='mchs')return e.end?'Действует до '+format(e.end):'Срок предупреждения не опубликован';
  if(!e.end)return 'Срок завершения не опубликован';
  return (Date.parse(e.end)<Date.now()?'Ожидалось завершение: ':'Ожидаемое завершение: ')+format(e.end);
}
function sourceText(e){
  if(e.origin==='municipal_repost')return 'Администрация Шахт · перепечатка';
  if(e.origin==='media_report')return 'КВУ · публикация СМИ, без прямого подтверждения УРСВ';
  if(e.origin==='verified_repost')return (e.source||'УРСВ')+' · перепечатка со ссылкой на документ';
  if(e.origin==='attributed_repost')return (e.source||'Коммунальная служба')+' · перепечатка, не прямая лента';
  return e.source||'Источник не указан';
}
function eventGeo(e){return geo.events&&geo.events[e.id]||{};}
function rows(e){
  if(e.category==='mchs')return [];
  if(validPoint(e.point))return [{lat:+e.point.lat,lon:+e.point.lon,role:'point',label:e.demo?'Учебная точка':(e.pointLabel||'Точка из полученных данных'),lines:[]}];
  const stored=eventGeo(e);
  // A mapping belongs to an immutable source address set, not merely a reused id.
  if(stored.affectedKey&&stored.affectedKey!==JSON.stringify((e.affected||[]).map(a=>[a.street,a.houses||[]])))return [];
  return (stored.features||[]).filter(validPoint);
}
function makeLink(text,url){const u=safeURL(url);if(!u)return null;const a=el('a','cm-source-link',text+' ↗');a.href=u;a.target='_blank';a.rel='noopener noreferrer';return a;}
function openDetails(e){
  const dialog=$('cityEventDetail');if(!dialog)return;
  lastDetail=e;previousFocus=document.activeElement;
  $('cityEventTitle').textContent=e.title||names[e.category]||'Сообщение';
  const body=$('cityEventBody');body.replaceChildren();
  body.append(el('p','cm-detail-kind',(e.demo?'ТЕСТ · ':'')+(names[e.category]||'Город')+' · '+statusText(e)));
  body.append(el('p','cm-detail-description',eventGeo(e).fullText||e.fullText||e.description||'Подробности не опубликованы.'));
  const grid=el('dl','cm-details');
  function field(label,value){grid.append(el('dt','',label),el('dd','',value));}
  field(e.category==='mchs'?'Период начинается':'Начало по объявлению',format(e.start));
  field(e.category==='mchs'?'Действует до':'Ожидаемое завершение',e.end?format(e.end):'Срок не опубликован');
  if(e.category!=='mchs'&&(e.status==='unconfirmed'||e.end&&Date.parse(e.end)<Date.now()))
    field('Важно','Объявленный срок прошёл. Подтверждения восстановления нет; это не доказательство, что авария продолжается.');
  field('Опубликовано',format(e.publishedAt));field('Получено при проверке',format(api.state.checkedAt));
  const features=rows(e);
  field('Расположение',e.category==='mchs'?'Предупреждение для города / области, без точечной аварии':
    features.length?features.some(r=>r.role==='street')?'На карте выделены улицы из объявления. Точное место поломки не установлено.':'Точка из полученных данных; точность зависит от первоисточника.':
    'Достоверные координаты не найдены. Случайная точка на карте не ставится.');
  if(e.category==='power'&&e.retained){field('Состояние данных','Последняя сохранённая публикация; восстановление не подтверждено');field('Последнее подтверждение источником',format(e.lastConfirmedAt));field('Сохранится до',format(e.retainUntil));}
  field('Источник',sourceText(e));body.append(grid);
  body.append(el('h3','cm-detail-subtitle','Затронутые адреса'));
  const areas=e.affected||[];
  if(areas.length){const list=el('ul','cm-addresses');for(const a of areas)list.append(el('li','',a.street+(a.houses&&a.houses.length?' · дома '+a.houses.join(', '):' · номера домов не перечислены')));body.append(list);}
  else body.append(el('p','cm-muted',e.category==='mchs'?'Территориальный прогноз. Это не перечень аварий по домам.':'В публикации нет списка затронутых домов.'));
  const links=el('div','cm-detail-links');
  for(const [label,url] of [['Открыть публикацию',e.url],['Официальный документ',e.officialUrl]]){const a=makeLink(label,url);if(a)links.append(a);}
  body.append(links,el('p','cm-muted','Сведения основаны на доступных публикациях служб. Сроки могут меняться, а сообщения публиковаться с задержкой.'));
  if(!dialog.open)dialog.showModal();
  $('cityEventClose').focus();
}
function closeDetails(){const d=$('cityEventDetail');if(d&&d.open)d.close();lastDetail=null;}
function detailButton(e,text){const button=el('button','cm-detail-button',text||'Что произошло и когда исправят');button.type='button';button.addEventListener('click',()=>openDetails(e));return button;}
function card(e){
  const item=el('article','cm-card');item.dataset.eventId=e.id;
  const head=el('div','cm-card-head');head.append(el('span','cm-category',icons[e.category]+' '+(names[e.category]||'Город')),el('span','cm-status',statusText(e)));
  item.append(head,el('h3','',e.title||'Коммунальное сообщение'),el('p','cm-time',timing(e)));
  const streets=(e.affected||[]).map(a=>a.street);
  if(streets.length)item.append(el('p','cm-address-summary',streets.slice(0,3).join(' · ')+(streets.length>3?' · ещё '+(streets.length-3):'')));
  const mapped=rows(e).length;
  if(!mapped&&e.category!=='mchs')item.append(el('p','cm-muted','Без точного места на карте'));
  if(e.category==='mchs')item.append(el('p','cm-muted','Город / область · не точечная авария'));
  const buttons=el('div','cm-card-actions');buttons.append(detailButton(e,'Подробности и сроки'));
  if(mapped){const locate=el('button','cm-locate','На карте');locate.type='button';locate.addEventListener('click',()=>{
    if(map){const p=rows(e)[0];map.setView([p.lat,p.lon],15,{animate:false});
      openDetails(e);$('map').scrollIntoView({behavior:'smooth',block:'center'});}
  });buttons.append(locate);}
  item.append(buttons);return item;
}
function popup(events,feature){
  const container=el('div','cm-popup');
  if(events.length===1){const e=events[0];container.append(el('strong','',icons[e.category]+' '+(e.title||'Сообщение')),
    el('p','',statusText(e)),el('p','cm-popup-time',timing(e)),
    el('p','cm-muted',feature.role==='street'?'Улица из объявления, не точное место аварии':feature.label),detailButton(e,'Открыть подробности'));}
  else {container.append(el('strong','',events.length+' сообщений в этом месте'));for(const e of events)container.append(detailButton(e,icons[e.category]+' '+e.title));}
  return container;
}
function paintMarkers(){
  if(!map||!layer)return;
  layer.clearLayers();const groups=new Map();
  for(const e of visible()){
    for(const feature of rows(e)){
      const color=colors[e.category]||colors.other;
      for(const raw of feature.lines||[]){
        const line=raw.filter(p=>Array.isArray(p)&&validPoint({lat:p[0],lon:p[1]}));
        if(line.length<2)continue;
        root.L.polyline(line,{color,weight:6,opacity:.63,dashArray:e.status==='unconfirmed'?'7 6':null}).addTo(layer)
          .bindPopup(popup([e],feature),{maxWidth:280}).on('mouseover',function(){this.setStyle({weight:8});}).on('mouseout',function(){this.setStyle({weight:6});});
      }
      const key=Number(feature.lat).toFixed(5)+','+Number(feature.lon).toFixed(5);
      if(!groups.has(key))groups.set(key,{feature,events:new Map()});
      groups.get(key).events.set(e.id,e);
    }
  }
  for(const {feature,events} of groups.values()){
    const list=Array.from(events.values()),e=list[0],color=colors[e.category]||colors.other;
    const iconNode=el('div','cm-pin');iconNode.style.background=color;iconNode.textContent=list.length>1?String(list.length):icons[e.category]||'!';
    const icon=root.L.divIcon({className:'cm-marker',html:iconNode.outerHTML,iconSize:[38,38],iconAnchor:[19,19]});
    root.L.marker([feature.lat,feature.lon],{icon,title:list.length>1?list.length+' сообщений':e.title,keyboard:true}).addTo(layer)
      .bindPopup(popup(list,feature),{maxWidth:280,minWidth:215});
  }
}
function renderDeck(){
  const items=visible(),pins=items.filter(e=>rows(e).length),unplaced=items.filter(e=>!rows(e).length&&e.category!=='mchs'),area=items.filter(e=>e.category==='mchs');
  $('cityNearButton').classList.toggle('selected',mode==='near');$('cityAllButton').classList.toggle('selected',mode==='city');
  $('cityNearButton').setAttribute('aria-pressed',String(mode==='near'));$('cityAllButton').setAttribute('aria-pressed',String(mode==='city'));
  $('cityMapScope').textContent=mode==='city'?'Весь город · '+allEvents().length+' сообщений':'Рядом с домом · '+nearEvents().length+' сообщений';
  $('cityMapCounts').textContent=pins.length+' с привязкой к карте · '+unplaced.length+' без точного места · '+area.length+' территориальных';
  $('cityMapHint').textContent=(mode==='city'?'Показаны доступные публикации по Шахтам, а не только возле вашего дома.':'Показаны сообщения для вашего адреса. Для остальных событий нажмите «Весь город».')+
    ' Цветные линии — улицы из объявления, не границы отключения.';
  const deck=$('cityMapEvents');deck.replaceChildren();
  if(!items.length)deck.append(el('p','cm-empty',mode==='city'?'В доступных данных нет событий выбранного типа. Это не подтверждение отсутствия происшествий.':
    api.state.home?'Для вашего адреса совпадений не найдено. В разделе «Весь город» могут быть другие сообщения.':'Выберите дом или откройте «Весь город»: этот режим работает без геолокации.'));
  else for(const e of items)deck.append(card(e));
  const quality=$('cityMapQuality');
  quality.textContent=api.state.demo?'ТЕСТ. Все события в этом режиме учебные.':
    'Доступные публикации, не полный перечень городских аварий. Проверка: '+format(api.state.checkedAt)+'.';
  $('mapName').textContent=mode==='city'?'Шахты · мониторинг города':api.state.home?.label||'Шахты · выберите дом';
  const pill=document.querySelector('.scale-pill');if(pill)pill.textContent=mode==='city'?'Весь город':'◎ 1 км';
}
function setMode(next,options={}){
  mode=next==='city'?'city':'near';
  if(map&&options.fit!==false){
    if(mode==='city'){
      const bounds=root.L.latLngBounds(CITY_BOUNDS);
      for(const e of allEvents())for(const p of rows(e))bounds.extend([p.lat,p.lon]);
      map.fitBounds(bounds,{padding:[20,20],maxZoom:12,animate:false});
    }else{
      const home=api.state.home||api.city;map.setView([home.lat,home.lon],14,{animate:false});
    }
  }
  renderDeck();paintMarkers();
}
function loadGeometry(){
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
  loadGeometry();
  const h=api.state.home||(api.state.demo?{...api.city,label:'Учебная контрольная точка'}:null);
  const key=h?h.lat+','+h.lon:'';
  if(map&&key!==homeKey){
    homeKey=key;homeLayer.clearLayers();
    if(h){root.L.circle([h.lat,h.lon],{radius:1000,color:'#139d84',fillColor:'#21b59c',fillOpacity:.065,weight:2,dashArray:'6 6'}).addTo(homeLayer);
      root.L.circleMarker([h.lat,h.lon],{radius:9,color:'#fff',weight:3,fillColor:'#0cac8d',fillOpacity:1}).addTo(homeLayer).bindTooltip('Контрольная точка');}
    if(mode==='near'&&h){map.setView([h.lat,h.lon],14,{animate:false});}
  }
  renderDeck();paintMarkers();
}
let activeBase='fallback',vectorBase=null;
function useRussianMapLabels(gl){
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

function removeCountryFlagSymbols(gl) {
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
function setupBrightBasemap(leafletMap){
  // Required copyright credits are displayed above the map; no provider footer within the map.
  const osm=root.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:19
  }).addTo(leafletMap);
  activeBase='fallback';
  setMapCreditType('fallback');
  const badge=$('mapStyleInfo');
  const note=message=>{if(badge)badge.textContent=message;};
  note('Светлая карта загружается…');
  if(!root.maplibregl||!root.L.maplibreGL){
    note('Открыта резервная карта');return;
  }
  let modern,gl,finished=false,failures=0;
  const giveUp=()=>{
    if(finished)return;
    finished=true;activeBase='fallback';vectorBase=null;setMapCreditType('fallback');
    if(modern&&leafletMap.hasLayer(modern))leafletMap.removeLayer(modern);
    note('Резервная карта');
  };
  try{
    modern=root.L.maplibreGL({style:'https://tiles.openfreemap.org/styles/bright'});
    modern.addTo(leafletMap);
    gl=modern.getMaplibreMap();
    if(!gl||typeof gl.on!=='function'){giveUp();return;}
    const russian=()=>{try{useRussianMapLabels(gl);removeCountryFlagSymbols(gl);}catch(_ignored){}};
    gl.on('style.load',russian);
    if(gl.isStyleLoaded?.())russian();
    gl.on('idle',()=>{
      if(finished)return;
      if(!gl.isStyleLoaded||!gl.isStyleLoaded())return;
      if(leafletMap.hasLayer(osm))leafletMap.removeLayer(osm);
      finished=true;activeBase='bright';vectorBase=modern;setMapCreditType('bright');note('Светлая карта · OpenFreeMap');
    });
    gl.on('error',()=>{failures++;if(failures>=5)giveUp();});
    setTimeout(()=>{if(!finished)giveUp();},16000);
  }catch(error){giveUp();}
}

function configure(options){api=options;}
function start(){
  if(mounted)return;mounted=true;
  const cardNode=document.querySelector('.map-card'),toolbar=document.querySelector('.map-toolbar');
  if(!cardNode||!toolbar)return;
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
  const modes=el('div','cm-modes');
  const near=el('button','selected','⌂ Рядом со мной');near.id='cityNearButton';near.type='button';near.addEventListener('click',()=>setMode('near'));
  const city=el('button','','▦ Весь город');city.id='cityAllButton';city.type='button';city.addEventListener('click',()=>setMode('city'));
  modes.append(near,city);toolbar.after(modes);
  const provider=el('span','cm-provider','Светлая карта загружается…');provider.id='mapStyleInfo';modes.append(provider);
  const hint=el('p','cm-hint');hint.id='cityMapHint';modes.after(hint);
  const scope=el('h3','cm-scope');scope.id='cityMapScope';
  const counts=el('p','cm-counts');counts.id='cityMapCounts';
  const filter=el('div','cm-filters');filter.setAttribute('aria-label','Службы на карте');
  for(const [value,label] of [['all','Все'],['water','💧 Вода'],['power','⚡ Свет'],['gas','♨ Газ'],['mchs','⚠ МЧС']]){
    const b=el('button',value===category?'selected':'',label);b.type='button';b.dataset.category=value;b.setAttribute('aria-pressed',String(value===category));
    b.addEventListener('click',()=>{category=value;for(const x of filter.querySelectorAll('button')){x.classList.toggle('selected',x===b);x.setAttribute('aria-pressed',String(x===b));}refresh();});filter.append(b);
  }
  const deck=el('div','cm-events');deck.id='cityMapEvents';
  const quality=el('p','cm-quality');quality.id='cityMapQuality';
  cardNode.append(scope,counts,filter,deck,quality);
  const detail=el('dialog','cm-detail');detail.id='cityEventDetail';detail.setAttribute('aria-labelledby','cityEventTitle');
  const dh=el('div','cm-detail-header');const title=el('h2');title.id='cityEventTitle';const close=el('button','cm-close','×');close.type='button';close.id='cityEventClose';close.setAttribute('aria-label','Закрыть подробности');close.addEventListener('click',closeDetails);
  const body=el('div','cm-detail-body');body.id='cityEventBody';dh.append(title,close);detail.append(dh,body);document.body.append(detail);
  detail.addEventListener('close',()=>{lastDetail=null;if(previousFocus?.isConnected)previousFocus.focus();});
  detail.addEventListener('click',ev=>{if(ev.target===detail){const r=detail.getBoundingClientRect();if(ev.clientX<r.left||ev.clientX>r.right||ev.clientY<r.top||ev.clientY>r.bottom)closeDetails();}});
  if(root.L){
    $('map').replaceChildren();const h=api.state.home||api.city;
    map=root.L.map('map',{zoomControl:false,attributionControl:false}).setView([h.lat,h.lon],api.state.home?14:12);api.state.map=map;
    setupBrightBasemap(map);
    root.L.control.zoom({position:'bottomright'}).addTo(map);layer=root.L.layerGroup().addTo(map);homeLayer=root.L.layerGroup().addTo(map);
    // Zoom and pan change only the viewport. Scope changes only through mode buttons.
    // Auto-switching here silently removed city markers on zoom 13 -> 14 near home.
  }else $('map').textContent='Карта не загрузилась. Публикации и подробности доступны ниже.';
  refresh();

}
root.CityMapV07={configure,start,refresh,setMode,openDetails,core:{isCurrent,validPoint},
  inspect:()=>({mode,category,ids:visible().map(e=>e.id),allIds:allEvents().map(e=>e.id),zoom:map?.getZoom(),basemap:activeBase,mapped:visible().filter(e=>rows(e).length).length}),
  getMap:()=>map,getVectorMap:()=>vectorBase?.getMaplibreMap(),hideCountryFlags:removeCountryFlagSymbols};
})(window);
