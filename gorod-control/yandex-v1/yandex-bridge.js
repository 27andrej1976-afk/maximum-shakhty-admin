/* Yandex Maps JS API v3 beta adapter. API key is entered locally, never stored in source. */
(function(root){
'use strict';
const STORAGE='city-control-yandex-jsapi-v1';
const CITY=[47.7086,40.2146];
const toLonLat=p=>[Number(p[1]),Number(p[0])];
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const css=String.raw;
let active=false,failed=false;
function element(tag,cls,text){
 const e=document.createElement(tag);
 if(cls)e.className=cls;
 if(text!=null)e.textContent=text;
 return e;
}
function distance(a,b){
 const R=6371000,dLat=(b.lat-a.lat)*Math.PI/180,dLon=(b.lng-a.lng)*Math.PI/180;
 const x=Math.sin(dLat/2)**2+Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*Math.sin(dLon/2)**2;
 return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));
}
function overlay(map,node){
 if(map.popup)map.popup.remove();
 const pane=element('div','ym-city-popup');
 const close=element('button','ym-city-popup-close','×');
 close.type='button';close.setAttribute('aria-label','Закрыть информацию');close.addEventListener('click',()=>pane.remove());
 pane.append(close,node);
 map.node.append(pane);map.popup=pane;
}
function makeShim(y){
 class MapCompat{
   constructor(id){
     this.node=document.getElementById(id);
     this.node.style.position='relative';
     this.zoom=12;this.center=CITY.slice();this.callbacks=[];this.noZoomEventUntil=0;
     this.inner=new y.YMap(this.node,{location:{center:toLonLat(CITY),zoom:12},mode:'vector'});
     this.inner.addChild(new y.YMapDefaultSchemeLayer({}));
     this.inner.addChild(new y.YMapDefaultFeaturesLayer({}));
     this.inner.addChild(new y.YMapListener({onUpdate:({location})=>{
       if(!location)return;
       if(Array.isArray(location.center))this.center=[location.center[1],location.center[0]];
       if(Number.isFinite(location.zoom)&&Math.abs(location.zoom-this.zoom)>.1){
         this.zoom=location.zoom;
         if(Date.now()>this.noZoomEventUntil)for(const cb of this.callbacks)cb();
       }
     }}));
     this.popup=null;
   }
   setView(point,zoom){
     this.center=[Number(point[0]),Number(point[1])];this.zoom=zoom;
     this.noZoomEventUntil=Date.now()+350;
     this.inner.setLocation({center:toLonLat(this.center),zoom,duration:0});
     return this;
   }
   fitBounds(bounds,opts){
     const a=bounds.points||bounds;
     const lats=a.map(p=>Number(p[0])),lons=a.map(p=>Number(p[1]));
     const n=Math.max(...lats),s=Math.min(...lats),w=Math.min(...lons),e=Math.max(...lons);
     this.center=[(n+s)/2,(w+e)/2];this.zoom=Math.min(opts?.maxZoom||13,11);
     this.noZoomEventUntil=Date.now()+350;
     this.inner.setLocation({bounds:[[w,s],[e,n]],duration:0});
     return this;
   }
   getZoom(){return this.zoom;}
   getCenter(){const p={lat:this.center[0],lng:this.center[1]};p.distanceTo=q=>distance(p,q);return p;}
   on(type,handler){if(type==='zoomend')this.callbacks.push(handler);return this;}
 }
 class LayerGroup{
   constructor(){this.map=null;this.items=[];}
   addTo(map){this.map=map;return this;}
   add(entity){if(!this.map)throw Error('Map layer not mounted');this.items.push(entity);this.map.inner.addChild(entity);}
   clearLayers(){
     if(this.map)for(const e of this.items){try{this.map.inner.removeChild(e);}catch(_e){}}
     this.items=[];
   }
 }
 class Geometry{
   constructor(type,data,style){
     this.type=type;this.data=data;this.style=style||{};this.item=null;this.group=null;this.popupNode=null;
   }
   addTo(group){
     this.group=group;
     const map=group.map;
     if(this.type==='marker'||this.type==='dot'){
       const body=this.type==='dot'?element('div','ym-home-dot'):element('div','ym-city-marker');
       if(this.type==='marker'){
         const template=document.createElement('template');
         template.innerHTML=this.style.icon?.html||'<span>!</span>';
         body.append(template.content);
       }
       const coords=toLonLat(this.data);
       body.addEventListener('click',event=>{
         event.preventDefault();event.stopPropagation();
         if(this.popupNode)overlay(map,this.popupNode);
       });
       this.item=new y.YMapMarker({coordinates:coords},body);
     }else{
       let coordinates=this.type==='line'?this.data.map(toLonLat):this.data;
       if(this.type==='circle'){
         const mid=this.data,lat=mid[0],lon=mid[1],meters=this.style.radius||1000;
         const ring=[];
         for(let i=0;i<=60;i++){
           const angle=i*Math.PI*2/60;
           ring.push([lon+Math.cos(angle)*meters/(111320*Math.cos(lat*Math.PI/180)),lat+Math.sin(angle)*meters/111320]);
         }
         coordinates=[ring];
       }
       this.item=new y.YMapFeature({
         geometry:{type:this.type==='line'?'LineString':'Polygon',coordinates},
         style:{stroke:[{color:this.style.color||'#139d84',width:this.style.weight||2,opacity:this.style.opacity??1}],
           fill:this.type==='circle'?[{color:this.style.fillColor||'#21b59c',opacity:this.style.fillOpacity||.06}]:undefined},
         onClick:()=>{if(this.popupNode)overlay(map,this.popupNode);},
         onMouseEnter:()=>this.setStyle({weight:8}),
         onMouseLeave:()=>this.setStyle({weight:this.style.weight||6})
       });
     }
     group.add(this.item);
     return this;
   }
   bindPopup(node){this.popupNode=node;return this;}
   bindTooltip(text){if(this.item&&this.type==='dot')this.item.element?.setAttribute('title',text);return this;}
   on(){return this;}
   setStyle(style){
     if(!this.item||!this.item.update)return this;
     this.item.update({style:{stroke:[{color:this.style.color||'#139d84',width:style.weight||this.style.weight||2,opacity:this.style.opacity??1}]}});
     return this;
   }
 }
 const L={
   map:(id)=>new MapCompat(id),
   tileLayer:()=>({addTo:()=>{}}),
   layerGroup:()=>new LayerGroup(),
   circle:(point,style)=>new Geometry('circle',point,{...style,radius:style.radius}),
   circleMarker:(point,style)=>new Geometry('dot',point,style),
   polyline:(line,style)=>new Geometry('line',line,style),
   divIcon:opts=>opts,
   marker:(point,style)=>new Geometry('marker',point,style),
   latLng:(lat,lng)=>({lat,lng}),
   latLngBounds:points=>({points:points.map(x=>x.slice()),extend(p){this.points.push([p[0],p[1]]);return this;}}),
   control:{zoom:()=>({addTo:(map)=>{
     const bar=element('div','ym-city-zoom');
     for(const [label,step] of [['+',1],['−',-1]]){
       const button=element('button','',label);button.type='button';
       button.setAttribute('aria-label',step>0?'Приблизить':'Отдалить');
       button.addEventListener('click',()=>map.setView(map.center,clamp(map.getZoom()+step,4,20)));
       bar.append(button);
     }
     map.node.append(bar);
   }})}
 };
 return L;
}
function createPanel(startLeaflet){
 const panel=element('div','ym-city-panel');
 const title=element('strong','','Карты: Яндекс · тест');
 const status=element('span','ym-city-status','В текущей версии сохранён резерв OpenStreetMap.');
 const row=element('div','ym-city-controls');
 const input=element('input','ym-city-key');
 input.type='password';input.autocomplete='off';input.placeholder='Ключ JavaScript API Яндекс Карт';input.setAttribute('aria-label','API-ключ Яндекс Карт');
 const connect=element('button','','Подключить Яндекс');
 const reset=element('button','','OpenStreetMap');
 connect.type=reset.type='button';
 connect.addEventListener('click',()=>{
   const key=input.value.trim();
   if(!/^[\w-]{16,160}$/.test(key)){status.textContent='Проверьте введённый ключ JavaScript API.';return;}
   try{root.localStorage.setItem(STORAGE,key);}catch(_){}
   root.location.reload();
 });
 reset.addEventListener('click',()=>{
   try{root.localStorage.removeItem(STORAGE);}catch(_){}
   root.location.reload();
 });
 row.append(input,connect,reset);
 panel.append(title,status,row);
 const toolbar=document.querySelector('.map-toolbar');
 if(toolbar)toolbar.after(panel);
 return {panel,status,input};
}
function startWithFallback(startLeaflet){
 const ui=createPanel(startLeaflet);
 let key=null;
 try{key=root.localStorage.getItem(STORAGE);}catch(_){}
 if(!key){ui.status.textContent='Введите ключ однократно для включения Яндекс Карт. Сейчас используется OpenStreetMap.';startLeaflet();return;}
 let done=false;
 const fallback=message=>{
   if(done)return;
   done=true;failed=true;
   root.L=root.CityYandexV1.originalLeaflet;
   ui.status.textContent=message+' Переключено на OpenStreetMap.';
   startLeaflet();
 };
 const timeout=root.setTimeout(()=>fallback('Сервер Яндекс Карт долго не отвечает.'),18000);
 const script=document.createElement('script');
 script.src='https://api-maps.yandex.ru/v3/?apikey='+encodeURIComponent(key)+'&lang=ru_RU';
 script.async=true;
 script.onerror=()=>{root.clearTimeout(timeout);fallback('Не удалось загрузить Яндекс Карты. Проверьте ключ и ограничения домена.');};
 script.onload=async()=>{
   try{
     if(!root.ymaps3)throw Error('Нет доступа к ymaps3');
     await root.ymaps3.ready;
     if(done)return;
     root.clearTimeout(timeout);
     root.L=makeShim(root.ymaps3);
     active=true;done=true;
     ui.status.textContent='Яндекс Карты активны · метки и домашний радиус сохранены.';
     startLeaflet();
   }catch(err){root.clearTimeout(timeout);fallback('Ошибка запуска Яндекс Карт.');}
 };
 ui.status.textContent='Загружаю Яндекс Карты. Если не откроются, появится резервная карта.';
 document.head.append(script);
}
root.CityYandexV1={
 originalLeaflet:root.L,
 startWithFallback,
 inspect:()=>({active,failed,mode:active?'yandex':'osm'})
};
})(window);
