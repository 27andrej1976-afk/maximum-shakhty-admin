import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const html=fs.readFileSync(path.resolve("gorod-control/index.html"),"utf8");
const blocks=[...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/gi)]
  .map(m=>m[1]).filter(Boolean);
assert.ok(blocks.length>=2,"expected two inline scripts");
for(const [i,script] of blocks.entries())new vm.Script(script,{filename:"inline-"+i+".js"});
const ctx=vm.createContext({console,Date,Math});
new vm.Script(blocks[0]).runInContext(ctx);
const C=ctx.CityLogic;
assert.ok(C);
assert.equal(C.normalStreet("проспект Красной Армии"),C.normalStreet("пр-кт Красной Армии"));
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
console.log("City frontend: "+blocks.length+" scripts parsed, 8 address/filter checks passed");
