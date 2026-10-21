// Run the shipped map module with a deterministic DOM/Leaflet test double.
// Covers filter/marker persistence; Android tests additionally exercise real rendering.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const nodes=[];
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.style={};this.dataset={};this.listeners={};this.classList={toggle(){}};nodes.push(this);}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  after(){}
  setAttribute(){}
  addEventListener(type,fn){this.listeners[type]=fn;}
  querySelectorAll(tag){return this.children.filter(n=>n.tagName===tag);}
  get outerHTML(){return this.textContent;}
}
const card=new Element(),toolbar=new Element(),pill=new Element();toolbar.firstElementChild=new Element();
for(const id of ['map','mapName']){const n=new Element();n.id=id;}
const document={createElement:tag=>new Element(tag),body:new Element(),getElementById:id=>nodes.find(n=>n.id===id),querySelector:s=>({'.map-card':card,'.map-toolbar':toolbar,'.scale-pill':pill}[s])};
let map;
function shape(type,point){return {type,point,addTo(target){target.items?.push(this);return this;},bindPopup(){return this;},bindTooltip(){return this;},on(){return this;}};}
const L={
  map(){map={zoom:14,items:[],handlers:{},center:{lat:47.7086,lng:40.2146,distanceTo:()=>0},getZoom(){return this.zoom;},getCenter(){return this.center;},
    on(type,fn){(this.handlers[type]??=[]).push(fn);return this;},
    setZoom(z){this.zoom=z;for(const fn of this.handlers.zoomend||[])fn();return this;},
    setView(p,z){this.center={lat:p[0],lng:p[1],distanceTo:()=>0};return this.setZoom(z);},
    fitBounds(){return this.setZoom(12);}};return map;},
  latLng:()=>({}),latLngBounds:()=>({extend(){}}),control:{zoom:()=>({addTo(){}})},
  tileLayer:()=>shape('tile'),layerGroup:()=>({items:[],clearLayers(){this.items=[];},addTo(target){target.items.push(this);return this;}}),
  circle:p=>shape('circle',p),circleMarker:p=>shape('home',p),marker:p=>shape('marker',p),polyline:p=>shape('line',p),divIcon:options=>options
};
const root={L};
vm.runInNewContext(readFileSync(new URL('./city-map.js',import.meta.url),'utf8'),{window:root,document,URL,setTimeout,fetch:async()=>({ok:true,json:async()=>({schema:1,events:{}})})});
const now=new Date().toISOString();
const events=['water','power','gas'].map((category,i)=>({id:category,category,kind:'emergency',status:'active',title:category,publishedAt:now,
  end:new Date(Date.now()+3600000).toISOString(),point:{lat:47.7086+i*.0002,lon:40.2146+i*.0002},affected:[]}));
const home={lat:47.7086,lon:40.2146,label:'Test home'};
root.CityMapV07.configure({state:{home,checkedAt:now},city:home,getRawEvents:()=>events,getHomeMatches:()=>[{event:events[0]}],fmt:x=>x});
root.CityMapV07.start();
await new Promise(resolve=>setTimeout(resolve,0));
const inspect=()=>root.CityMapV07.inspect(),ids=()=>Array.from(inspect().ids).sort();
const markerCount=()=>map.items.flatMap(x=>x.items||[]).filter(x=>x.type==='marker').length;
for(const mode of ['near','city']){
  document.getElementById(mode==='near'?'cityNearButton':'cityAllButton').listeners.click();
  const expected=ids(),count=markerCount();
  for(const z of [13,12,14,15,17,13,14]){
    map.setZoom(z);
    assert.equal(inspect().mode,mode,`Zoom ${z} must preserve ${mode} mode`);
    assert.deepEqual(ids(),expected,`Zoom ${z} must preserve event IDs`);
    assert.equal(markerCount(),count,`Zoom ${z} must preserve markers`);
  }
}
for(const category of ['water','power','gas','all']){
  nodes.find(n=>n.dataset.category===category).listeners.click();
  const expected=ids();
  map.setZoom(13);map.setZoom(15);root.CityMapV07.refresh();
  assert.equal(inspect().category,category);
  assert.deepEqual(ids(),expected);
  assert.equal(markerCount(),category==='all'?3:1);
}
document.getElementById('cityNearButton').listeners.click();
assert.deepEqual(ids(),['water'],'Explicit near mode keeps address filtering');
assert.equal(markerCount(),1);
document.getElementById('cityAllButton').listeners.click();
assert.equal(markerCount(),3,'Explicit city mode restores city markers');
assert.equal(home.lat,47.7086);
assert.equal(home.lon,40.2146);
console.log('PASS zoom 12–17: modes, IDs, water/power/gas markers, categories, refresh, explicit mode buttons');
