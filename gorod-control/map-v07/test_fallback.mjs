// Regression: a failed/partially initialized vector map must leave raster map,
// controls, source refresh, pan, zoom and event markers usable.
// node gorod-control/map-v07/test_fallback.mjs [--browser]
// --browser uses Playwright + Chromium; all browser network responses are local
// fixtures. Set CHROMIUM_EXECUTABLE only when using a system Chromium.
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {resolve, dirname, extname, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const here=dirname(fileURLToPath(import.meta.url)), repo=resolve(here,'../..');
const bridgeSource=readFileSync(resolve(here,'../light-v10/vendor/leaflet-maplibre-gl.js'),'utf8');
const mapSource=readFileSync(resolve(here,'city-map.js'),'utf8');
const frames=[];
const L={Layer:{extend:spec=>spec},DomEvent:{off(){}},DomUtil:{},Util:{
  throttle:fn=>fn,requestAnimFrame:(fn,ctx)=>frames.push(()=>fn.call(ctx))
}};
vm.runInNewContext(bridgeSource,{L,maplibregl:{}});
const bridge=L.MaplibreGL;
for(const scenario of ['missing GL','remove throws','normal GL']){
  let removes=0,removedNodes=0;
  const container={parentNode:{removeChild(){removedNodes++;container.parentNode=null;}}};
  const layer={...bridge,_map:{options:{zoomAnimation:false}},_container:container,
    _glMap:scenario==='missing GL'?undefined:{remove(){removes++;if(scenario==='remove throws')throw Error('partial GL');}}};
  assert.doesNotThrow(()=>bridge.onRemove.call(layer,layer._map),scenario);
  assert.equal(layer._glMap,null,scenario+' clears renderer before deferred callbacks');
  assert.doesNotThrow(()=>bridge.onRemove.call(layer,layer._map),scenario+' is idempotent');
  assert.equal(removedNodes,1,scenario+' detaches overlay once');
  assert.equal(removes,scenario==='missing GL'?0:1,scenario+' removes GL at most once');
  for(const method of ['_update','_pinchZoom','_animateZoom','_zoomStart','_zoomEnd','_transitionEnd','_resize'])
    assert.doesNotThrow(()=>bridge[method].call(layer,{}),scenario+' ignores late '+method);
}
// A transition may already have queued an animation frame when fallback starts.
const queued={...bridge,_map:{options:{}},_glMap:{_actualCanvas:{},remove(){}}};
bridge._transitionEnd.call(queued,{});
assert.equal(frames.length,1);
bridge.onRemove.call(queued,queued._map);
assert.doesNotThrow(()=>frames.shift()(),'a pending animation frame cannot revive a removed renderer');

const setup=mapSource.slice(mapSource.indexOf('function setupBrightBasemap('),mapSource.indexOf('\nfunction configure('));
for(const scenario of ['constructor failure','missing renderer','cleanup failure','timeout','five errors','ready']){
  let registered=false,removed=0,off=0,containerRemoved=0;
  const badge={textContent:''},timeouts=[],handlers={};
  const gl={on(type,fn){handlers[type]=fn;},isStyleLoaded:()=>true};
  const modern={
    addTo(){registered=true;if(scenario==='constructor failure')throw Error('WebGL unavailable');return this;},
    getMaplibreMap:()=>scenario==='missing renderer'||scenario==='cleanup failure'?null:gl,
    getEvents:()=>({move(){}}),getContainer:()=>({remove(){containerRemoved++;}})
  };
  const osm={addTo(){return this;}};
  const leaflet={hasLayer:item=>item===osm||registered,off(){off++;},
    removeLayer(item){if(item===modern){removed++;if(scenario==='cleanup failure')throw Error('cleanup');registered=false;}}};
  const context={root:{L:{tileLayer:()=>osm,maplibreGL:()=>modern},maplibregl:{}},
    $:()=>badge,setTimeout:fn=>timeouts.push(fn),setMapCreditType(){},
    useRussianMapLabels(){},removeCountryFlagSymbols(){},leaflet};
  vm.createContext(context);
  assert.doesNotThrow(()=>vm.runInContext("let activeBase='fallback',vectorBase=null;"+setup+';setupBrightBasemap(leaflet);',context),scenario);
  if(scenario==='timeout')timeouts[0]();
  if(scenario==='five errors')for(let n=0;n<6;n++)handlers.error();
  if(scenario==='ready'){handlers.idle();timeouts[0]();assert.equal(vm.runInContext('activeBase',context),'bright');}
  else{
    assert.equal(vm.runInContext('activeBase',context),'fallback',scenario);
    assert.equal(badge.textContent,'Резервная карта',scenario+' shows final fallback state');
    assert.equal(removed,1,scenario+' attempts cleanup once');
    if(scenario==='cleanup failure'){assert.equal(off,1);assert.equal(containerRemoved,1);}
    else assert.equal(registered,false,scenario+' unregisters vector layer');
  }
}
console.log('PASS fallback unit: missing/partial GL, idempotent removal, late events, queued frames, errors, timeout, vector success');

const geometryCode=mapSource.slice(mapSource.indexOf('function mergeGeometry('),mapSource.indexOf('\nfunction refresh('));
const oldCatalog={schema:1,generatedAt:'2026-10-29T05:34:39Z',events:{
  common:{features:[{lat:47.7,lon:40.2}],affectedKey:'old'},directOnly:{features:[]}
}};
const newCatalog={schema:1,generatedAt:'2026-10-29T09:48:47Z',events:{
  common:{features:[{lat:47.71,lon:40.21}],affectedKey:'new'},baselineOnly:{features:[]}
}};
for(const failure of ['none','direct fails','baseline fails','both fail','direct timeout','sync fetch failure']){
  const timers=new Map(),requests=[];let nextTimer=0,refreshes=0;
  const context={api:{state:{checkedAt:'new-check'}},geometryLoading:false,geometryStamp:null,
    geo:{schema:1,events:{cached:{features:[],generatedAt:'2026-10-28T12:00:00Z'}}},
    AbortController,setTimeout:fn=>{timers.set(++nextTimer,fn);return nextTimer;},clearTimeout:id=>timers.delete(id),
    refresh(){refreshes++;},fetch(url,options){
      requests.push({url,options});const direct=url.includes('/direct-v09/');
      if(failure==='sync fetch failure'&&direct)throw Error('synchronous network failure');
      if(failure==='direct timeout'&&direct)return new Promise(()=>{});
      if(failure==='both fail'||failure==='direct fails'&&direct||failure==='baseline fails'&&!direct)return Promise.reject(Error('offline'));
      return Promise.resolve({ok:true,json:async()=>direct?oldCatalog:newCatalog});
    }};
  vm.createContext(context);vm.runInContext(geometryCode+';loadGeometry();',context);
  await new Promise(setImmediate);
  assert.equal(requests.length,2,failure+' requests both catalogs');
  assert.ok(requests.every(r=>r.options.signal instanceof AbortSignal),'each geometry request is abortable');
  if(failure==='direct timeout'){
    assert.equal(context.geo.events.common.affectedKey,'new','successful catalog paints before other times out');
    assert.equal(timers.size,1);for(const fn of timers.values())fn();
    await new Promise(setImmediate);
    assert.equal(requests.find(r=>r.url.includes('/direct-v09/')).options.signal.aborted,true);
  }
  assert.equal(context.geometryLoading,false,failure+' releases loading state');
  assert.equal(timers.size,0,failure+' clears timeout handles');
  assert.ok(context.geo.events.cached,failure+' retains earlier geometry on partial failure');
  if(failure==='both fail')assert.equal(context.geo.events.common,undefined);
  else assert.equal(context.geo.events.common.affectedKey,failure==='baseline fails'?'old':'new',failure+' chooses newest available geometry');
  assert.ok(refreshes>=1,failure+' refreshes map after completion');
  vm.runInContext('loadGeometry();',context);await new Promise(setImmediate);
  assert.equal(requests.length,2,'same checkedAt does not make a request loop');
}
const geometryContext={};vm.createContext(geometryContext);vm.runInContext(geometryCode,geometryContext);
geometryContext.previous={schema:1,events:{common:{features:[],generatedAt:'2026-10-29T10:00:00Z'}}};
geometryContext.catalogs=[newCatalog,oldCatalog,{schema:1,events:{common:{features:[]}}}];
assert.equal(vm.runInContext('mergeGeometry(previous,catalogs).events.common.generatedAt',geometryContext),'2026-10-29T10:00:00Z','older and undated snapshots never replace newer cached geometry');
geometryContext.catalogs=[oldCatalog,newCatalog];
assert.equal(vm.runInContext('mergeGeometry({events:{}},catalogs).events.common.affectedKey',geometryContext),'new');
geometryContext.catalogs=[newCatalog,oldCatalog];
assert.equal(vm.runInContext('mergeGeometry({events:{}},catalogs).events.common.affectedKey',geometryContext),'new','merge is independent of fetch completion order');
console.log('PASS geometry: merge two catalogs per event, newest timestamps win, partial/total failure retains cache, timeout aborts, no request loop');

if(process.argv.includes('--browser')){
  const {createRequire}=await import('node:module');
  const {chromium}=createRequire(import.meta.url)('playwright');
  const {createServer}=await import('node:http');
  const now=new Date().toISOString(),end=new Date(Date.now()+3600000).toISOString();
  const event={id:'fallback-test-water',category:'water',kind:'emergency',status:'active',
    origin:'municipal_repost',sourceId:'city',source:'Администрация города Шахты',
    url:'https://t.me/admshakhty/900001',title:'ТЕСТ резервной карты — не настоящее происшествие',
    publishedAt:now,start:now,end,point:null,affected:[{street:'ул. Тестовая',houses:['1']}]};
  const feed={schema:2,checkedAt:now,sources:[{id:'city',status:'ok',checkedAt:now,lastPostAt:now}],events:[event]};
  const geometry={schema:1,generatedAt:now,events:{[event.id]:{
    features:[{lat:47.72,lon:40.23,role:'street',label:'ул. Тестовая',lines:[]}],
    affectedKey:JSON.stringify(event.affected.map(a=>[a.street,a.houses||[]]))
  },'geometry-only-not-a-source-event':{features:[{lat:47.73,lon:40.24,role:'point',lines:[]}]}}};
  const server=createServer((req,res)=>{
    const path=resolve(repo,'.'+new URL(req.url,'http://local').pathname);
    if(!path.startsWith(repo+sep)||!existsSync(path)){res.writeHead(404);res.end();return;}
    try{res.setHeader('content-type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png'})[extname(path)]||'text/plain');res.end(readFileSync(path));}
    catch{res.writeHead(404);res.end();}
  });
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  const base='http://127.0.0.1:'+server.address().port;
  let browser;
  try{
    browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:['--disable-webgl','--disable-gpu','--no-sandbox']});
    const page=await browser.newPage({viewport:{width:393,height:852},isMobile:true,hasTouch:true});
    const errors=[];let feedRequests=0,tileRequests=0;
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',async route=>{
      const url=route.request().url();
      if(/\/(?:data\/water|direct-v09\/feed)\.json/.test(url)){
        feedRequests++;await route.fulfill({json:feed});
      }else if(url.includes('/direct-v09/map-geometry.json'))await route.fulfill({json:{schema:1,generatedAt:'2026-10-29T05:34:39Z',events:{}}});
      else if(url.includes('/data/map-geometry.json'))await route.fulfill({json:geometry});
      else if(url.startsWith('https://tile.openstreetmap.org/')){
        tileRequests++;await route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5WQAAAAASUVORK5CYII=','base64')});
      }else if(url.startsWith(base))await route.continue();
      else await route.abort();
    });
    for(let pass=0;pass<2;pass++){
      await page.goto(base+'/gorod-control/compact-v11/index.html',{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>window.CityMapV07?.inspect().allIds.includes('fallback-test-water'));
      assert.equal(await page.evaluate(()=>document.createElement('canvas').getContext('webgl2')),null,'WebGL is actually unavailable');
      assert.equal(await page.locator('#mapStyleInfo').textContent(),'Резервная карта');
      assert.equal(await page.locator('.leaflet-gl-layer').count(),0,'failed GL overlay is removed');
      assert.equal(await page.locator('.leaflet-control-zoom').count(),1,'Leaflet setup completed');
      await page.locator('#addressButton').click();
      assert.equal(await page.locator('#addressDialog').evaluate(el=>el.open),true,'manual address control works');
      await page.locator('#addressDialog button[value="cancel"]').first().click();
      const before=feedRequests;
      await page.locator('#checkButton').click();
      await page.waitForFunction(()=>!document.querySelector('#checkButton').disabled);
      assert.ok(feedRequests>before,'refresh handler makes another source request');
      await page.locator('#cityAllButton').click();
      await page.waitForFunction(()=>CityMapV07.inspect().mapped===1);
      assert.equal(await page.locator('.cm-marker').count(),1,'city marker is rendered on raster fallback');
      assert.deepEqual(await page.evaluate(()=>CityMapV07.inspect().allIds),[event.id],'geometry-only entries never create incidents');
      for(const zoom of [13,14,17,12]){
        await page.evaluate(z=>CityMapV07.getMap().setZoom(z,{animate:false}),zoom);
        await page.evaluate(()=>CityMapV07.getMap().panBy([30,-20],{animate:false}));
        assert.equal(await page.evaluate(()=>CityMapV07.inspect().mode),'city');
        assert.equal(await page.locator('.cm-marker').count(),1,'markers survive zoom/pan on fallback');
      }
      await page.locator('#cityNearButton').click();
      assert.equal(await page.evaluate(()=>CityMapV07.inspect().mode),'near');
      await page.locator('#cityAllButton').click();
      assert.equal(await page.locator('.cm-marker').count(),1,'returning to city preserves markers');
    }
    assert.ok(tileRequests>0,'raster fallback requests tiles');
    assert.deepEqual(errors,[],'no page exceptions across reload, address, refresh, scope, zoom and pan');
    console.log('PASS Chromium WebGL disabled: raster fallback, controls, refresh, city/nearby, markers, zoom/pan, reload; no page errors');
  }finally{await browser?.close();await new Promise(done=>server.close(done));}
}
