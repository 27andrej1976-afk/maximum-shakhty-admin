import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const html=fs.readFileSync(path.resolve("gorod-control/index.html"),"utf8");
const blocks=[...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/gi)]
  .map(m=>m[1]).filter(Boolean);
assert.ok(blocks.length>=2,"expected two inline scripts");
assert.doesNotMatch(html,/id:'water',\s*icon:/,"outdated Telegram water channel must be absent from the displayed sources");
assert.match(html,/id:'repost_rostov'/,"current official-linked mirror must be present");
assert.match(html,/id:'repost_don'/,"backup source must be present");

assert.match(html,/CityControlNativeGPSResult/,"native Android coordinate callback must exist");
assert.match(html,/CityControlNativeGPSError/,"native GPS failure callback must exist");
assert.match(html,/citycontrol:\/\/get-location/,"native Android geolocation route must exist");
assert.match(html,/id="geoStatus"/,"GPS status must be visible");
assert.match(html,/Номер дома не подтверждён|номер дома не подтверждён/,"missing house must be disclosed");

for(const [i,script] of blocks.entries())new vm.Script(script,{filename:"inline-"+i+".js"});
const ctx=vm.createContext({console,Date,Math});
new vm.Script(blocks[0]).runInContext(ctx);
const C=ctx.CityLogic;
assert.ok(C);
assert.equal(C.normalStreet("проспект Красной Армии"),C.normalStreet("пр-кт Красной Армии"));
assert.equal(C.normalStreet("Советская улица"),C.normalStreet("ул. Советская"),"street name suffix from geocoder");
assert.notEqual(C.normalStreet("ул. Шишкина"),C.normalStreet("пер. Шишкина"),"street and lane must NEVER be treated as same place");
assert.notEqual(C.normalStreet("улица Маяковского"),C.normalStreet("проезд Маяковского"),"street and passage differ");
assert.equal(C.normalStreet("переулок Шишкина"),C.normalStreet("пер Шишкина"),"lane aliases match");
assert.equal(C.parseHomeAddress("ул. Советская, 25").street,"ул. советская","address type must survive storage");

const home={lat:47.7086,lon:40.2146,street:"пер. Шишкина",house:"183А"};
assert.equal(C.parseHomeAddress("г. Шахты, пер. Шишкина, 183А").house,"183а");
const activeTime=new Date().toISOString();
const near={kind:"emergency",status:"active",start:activeTime,point:{lat:47.711,lon:40.2146},affected:[]};
assert.equal(C.matchImpact(near,home).relevant,true,"nearby incident");
const far={kind:"emergency",status:"active",start:activeTime,point:{lat:47.77,lon:40.2146},affected:[]};
assert.equal(C.matchImpact(far,home).relevant,false,"remote unrelated incident");
const address={kind:"planned",status:"active",start:new Date(Date.now()+3600000).toISOString(),
  affected:[{street:"пер Шишкина",houses:["183а"]}],point:{lat:47.8,lon:40.2146}};
assert.equal(C.matchImpact(address,home).match,"address","listed home even if work farther than radius");
const different={...address,affected:[{street:"пер Шишкина",houses:["180","182"]}],point:{lat:47.709,lon:40.2146}};
assert.equal(C.matchImpact(different,home).relevant,false,"different numbered houses should be excluded");
const streetOnly={...address,affected:[{street:"пер Шишкина",houses:[]}]};
assert.equal(C.matchImpact(streetOnly,home).confidence,"medium","street without houses is preliminary");
const stale={...near,status:"resolved"};
assert.equal(C.matchImpact(stale,home).relevant,false,"completed event hidden");
const shHome={...home,label:"г. Шахты, пер. Шишкина, 183А"};
const mchs={id:"forecast-mchs-001",category:"mchs",kind:"warning",status:"active",scope:"city",
  start:new Date().toISOString(),end:new Date(Date.now()+86400000).toISOString(),affected:[],point:null};
assert.equal(C.matchImpact(mchs,shHome).relevant,true,"Shakhty-wide forecast is shown to a verified Shakhty address");
assert.equal(C.matchImpact(mchs,{...shHome,label:"г. Таганрог, ул. Морская"}).relevant,false,"do not show Shakhty scope to another city");
assert.equal(C.matchImpact({...mchs,end:new Date(Date.now()-7200000).toISOString()},shHome).relevant,false,
  "expired MCHS advisories do not remain visible");
assert.match(html,/id:'power_repost_rostov'/,"electricity repost source");
assert.match(html,/id:'power_city'/,"city power announcements");
assert.match(html,/id:'gas_city'/,"city gas announcements");
assert.match(html,/id:'mchs'/,"official MCHS feed");
assert.match(html,/data-filter="warning"/,"MCHS notices can be filtered separately");

console.log("City frontend: "+blocks.length+" scripts parsed, 21 address/scope/source checks passed");

// A valid read with no local notices differs from a network error or missing access.
const summaryScript=html.slice(html.indexOf('function sourceSummary('),html.indexOf('function renderSources('));
const summaryCtx=vm.createContext({Date,Set,Number,state:{checkedAt:new Date().toISOString()}});
new vm.Script(summaryScript).runInContext(summaryCtx);
const rows=[{id:'a',url:'https://one.example/rss'},{id:'b',url:'https://one.example/rss'},
  {id:'c',url:'https://two.example/rss'},{id:'d',url:'https://max.ru/shakhtygorod'}];
const checks={a:{status:'ok'},b:{status:'partial',readStatus:'ok'},c:{status:'error'},d:{status:'not_configured'}};
const summary=summaryCtx.sourceSummary(rows,checks);
assert.equal(summary.read,2);
assert.equal(summary.errors,1);
assert.equal(summary.unconfigured,1);
assert.equal(summary.unique,3);
assert.equal(summaryCtx.sourceSummary(rows,checks,Date.now()+5*3600000).read,0);
console.log('Source status: empty matches, network errors, missing access, duplicate URLs and stale data checked');
