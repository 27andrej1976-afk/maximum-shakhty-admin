import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const template=fs.readFileSync('gorod-control/app-template.txt','utf8');
const web=fs.readFileSync('gorod-control/compact-v11/index.html','utf8');
const policy=s=>s.slice(s.indexOf('function freshSource('),s.indexOf('function sourceSummary(')>0?s.indexOf('function sourceSummary('):s.indexOf('function renderSources('));
assert.equal(policy(web),policy(template),'web and Android template must use identical source/freshness rules');
const now=Date.parse('2026-10-29T10:30:00Z');
class Clock extends Date{constructor(...a){super(...(a.length?a:[now]));}static now(){return now;}}
const state={events:[],checks:[]};const ctx=vm.createContext({Date:Clock,console,state,AbortSignal});
vm.runInContext(policy(template),ctx);
// Freeze the exact real divergence fixture rather than relying on subsequently updated live feeds.
const fixture=JSON.parse(fs.readFileSync('gorod-control/scripts/fixtures/feed-divergence-20261029.json','utf8'));
assert.equal(fixture.checkedAt,'2026-10-29T09:48:21.436633+00:00');
const source={id:'water_kvu',status:'ok',checkedAt:'2026-10-29T09:48:12Z'};
const media={id:'media',category:'water',origin:'media_report',sourceId:'water_kvu',url:'https://kvu.su/utilities/report.html',status:'active',start:'2026-10-29T07:00:00Z',end:'2026-10-29T15:00:00Z'};
const city={...media,id:'municipal',origin:'municipal_repost',sourceId:'repost_don',url:'https://news-don.ru/society/report',requiresReview:true};
const archive={...media,id:'archive',origin:'official_archive',sourceId:null,source:'Шахтинский водоканал',url:'https://t.me/admshakhty/31053',requiresReview:true};
const feed={schema:2,checkedAt:source.checkedAt,sources:[source,{...source,id:'repost_don'}],events:[media,city,archive]};
ctx.applyFeed(feed);
assert.deepEqual(Array.from(state.events,e=>e.id),['media','municipal']);
assert.equal(state.events[1].requiresReview,true,'uncertain municipal addresses keep review flag');
assert.equal(state.events[0].lastConfirmedAt,source.checkedAt,'confirmation uses source clock, not button clock');
for(const url of ['https://kvu.su.evil.example/utilities/report','http://kvu.su/utilities/report','https://evil.example/report']){
 assert.equal(ctx.waterSourceAccepted({...media,url},{water_kvu:source},ctx.freshSource),false);
}
assert.equal(ctx.waterSourceAccepted({...media,sourceId:'repost_don'},{water_kvu:source},ctx.freshSource),false,'healthy unrelated source cannot validate');
assert.equal(ctx.waterSourceAccepted({...city,sourceId:'repost_rostov'},{repost_rostov:source},ctx.freshSource),false,'mirror identity must match its host');
assert.equal(ctx.waterSourceAccepted({...media,status:'resolved'},{water_kvu:source},ctx.freshSource),false);
assert.equal(ctx.waterSourceAccepted({...media,end:'2026-10-27T00:00:00Z'},{water_kvu:source},ctx.freshSource),false);
const original=structuredClone(state.events);
ctx.applyFeed({...feed,sources:feed.sources.map(s=>({...s,status:'error'})),events:original});
assert.equal(state.events.length,2,'source failure retains previously accepted events');
assert.equal(state.events[0].status,'unconfirmed');
assert.equal(state.events[0].lastConfirmedAt,source.checkedAt);
assert.equal(state.events[0].retainUntil,original[0].retainUntil,'failure cannot restart 36h retention');
const device={...media,id:'device',origin:'official_device',sourceId:'ursv_device',url:'https://rovodokanal.ru/emergency-alerts/123'};
assert.equal(ctx.waterSourceAccepted(device,{ursv_device:{...source,status:'partial'}},ctx.freshSource),true);
assert.equal(ctx.waterSourceAccepted(device,{ursv_device:{...source,status:'partial',checkedAt:'2026-10-29T05:00:00Z'}},ctx.freshSource),false,'old phone cache is not a fresh source');
assert.equal(ctx.waterSourceAccepted({...device,status:'resolved'},{ursv_device:source},ctx.freshSource),false);
assert.equal(ctx.freshSource({...source,status:'partial',readStatus:'ok'}),true,'successful partial public read validates only its own events');
assert.equal(ctx.freshSource({...source,checkedAt:'2026-10-29T11:00:00Z'}),false,'future clock is not current');
const direct={schema:2,checkedAt:'2026-10-29T05:34:33Z',sources:[{...source,checkedAt:'2026-10-29T05:34:33Z'},{id:'max_power',status:'error',checkedAt:'2026-10-29T05:34:33Z'}],events:[]};
const merged=ctx.mergePublicFeeds([direct,feed]);ctx.applyFeed(merged);
assert.deepEqual(Array.from(state.events,e=>e.id),['media','municipal'],'newer baseline repairs lagging direct feed');
assert.equal(state.checks.find(s=>s.id==='max_power').checkedAt,direct.checkedAt,'baseline cannot refresh MAX clock');
assert.equal(state.checks.find(s=>s.id==='water_kvu').checkedAt,source.checkedAt);
const resolved={...feed,checkedAt:'2026-10-29T10:00:00Z',sources:feed.sources.map(s=>({...s,checkedAt:'2026-10-29T10:00:00Z'})),events:[{...media,status:'resolved'}]};
ctx.applyFeed(ctx.mergePublicFeeds([feed,resolved]));
assert.equal(state.events.length,0,'newer explicit restoration cannot be overwritten by older copy');
// A feed envelope refreshed by a native check must not renew cloud-source timestamps.
ctx.applyFeed({...feed,checkedAt:'2026-10-29T10:30:00Z',cloudCheckedAt:'2026-10-29T05:00:00Z',sources:[{id:'water_kvu',status:'ok'}],events:[media]});
assert.equal(state.events.length,0);
let calls=0;ctx.fetch=async url=>{calls++;if(url.includes('direct-v09'))throw Error('offline');return {ok:true,json:async()=>feed};};
const fallback=await ctx.readPublicFeeds();assert.equal(fallback.events.length,2);assert.equal(calls,2,'independent feeds attempted in parallel');
console.log('PASS feed policy: provenance, 36h, restoration, review flags, stale/future clocks, current baseline fallback, independent sources');
const oldConfirmed={...media,affected:[{street:'ул. Тестовая',houses:['1']}],lastConfirmedAt:'2026-10-29T08:50:00Z',retainUntil:'2026-10-31T03:00:00Z'};
const oldFeed={...feed,sources:[{...source,checkedAt:'2026-10-29T08:50:00Z'}],events:[oldConfirmed]};
const newerEmpty={schema:2,checkedAt:'2026-10-29T10:00:00Z',sources:[{...source,checkedAt:'2026-10-29T10:00:00Z'}],events:[]};
ctx.applyFeed(ctx.mergePublicFeeds([oldFeed,newerEmpty]));
assert.equal(state.events[0].retained,true,'a newer empty source does not individually reconfirm an old event');
assert.equal(state.events[0].lastConfirmedAt,'2026-10-29T08:50:00Z');
assert.equal(state.events[0].status,'unconfirmed');
const restoredIncident={...media,id:'restoration-new-id',status:'resolved',resolvedAt:'2026-10-29T09:55:00Z',publishedAt:'2026-10-29T09:55:00Z',affected:oldConfirmed.affected};
ctx.applyFeed(ctx.mergePublicFeeds([oldFeed,{...newerEmpty,incidents:[restoredIncident]}]));
assert.equal(state.events.length,0,'real incidents tombstone closes uniquely matching retained event');
ctx.applyFeed(ctx.mergePublicFeeds([oldFeed,{...newerEmpty,incidents:[{...restoredIncident,affected:[{street:'ул. Другая',houses:['1']}]}]}]));
assert.equal(state.events.length,1,'different affected address must not close old event');
ctx.applyFeed(ctx.mergePublicFeeds([oldFeed,{...newerEmpty,incidents:[{...restoredIncident,origin:'official_archive',sourceId:null,source:'Шахтинский водоканал',url:'https://t.me/admshakhty/31053'}]}]));
assert.equal(state.events.length,1,'untrusted archive restoration cannot close a legitimate incident');
console.log('PASS event provenance: newer empty feed never reconfirms, verified incidents restoration matches exact unique address only');
for(const invalid of [
 {...restoredIncident,id:oldConfirmed.id,origin:'official_archive',sourceId:null,source:'Шахтинский водоканал',url:'https://t.me/admshakhty/31053'},
 {...restoredIncident,id:oldConfirmed.id,requiresReview:true},
 {...restoredIncident,id:oldConfirmed.id,resolvedAt:'2026-10-30T12:00:00Z'}
]){
 ctx.applyFeed({...oldFeed,incidents:[invalid]});assert.equal(state.events.length,1,'invalid same-ID closure cannot remove legitimate event');
 ctx.applyFeed(ctx.mergePublicFeeds([oldFeed,{...newerEmpty,incidents:[invalid]}]));assert.equal(state.events.length,1,'invalid closure cannot overwrite during merge');
}
ctx.applyFeed({...oldFeed,sources:[{...source,status:'error'}],events:[oldConfirmed],incidents:[{...restoredIncident,id:oldConfirmed.id}]});
assert.equal(state.events.length,1,'source-error tombstone without retained proof cannot close an accepted cached event');
console.log('PASS tombstone trust: same-ID/mixed-ID, review/future/untrusted/source-error closures do not hide legitimate events');

ctx.applyFeed({...feed,nativeCheckedAt:'2026-10-29T10:30:00Z',checkedAt:'2026-10-29T10:30:00Z',sources:[{id:'water_kvu',status:'ok'}],events:[media]});
assert.equal(state.events.length,0,'legacy native snapshot without cloud clock cannot freshen unknown source');
console.log('PASS native cache parity: absent cloud clock remains unknown');

const legacyPower={...media,id:'legacy-power',category:'power',sourceId:'power_repost',origin:'attributed_repost',url:'https://news-don.ru/society/power'};
assert.equal(ctx.powerSourceAccepted(legacyPower,{power_repost_don:source}),true,'legacy generic ID maps only to its exact allowed domain source');
assert.equal(ctx.powerSourceAccepted({...legacyPower,url:'https://newsrostov.ru/society/power'},{power_repost_rostov:source}),true);
assert.equal(ctx.powerSourceAccepted({...legacyPower,sourceId:'power_repost_rostov'},{power_repost_don:source}),false,'mismatched specific source stays rejected');
assert.equal(ctx.powerSourceAccepted({...legacyPower,url:'https://news-don.ru.evil.example/x'},{power_repost_don:source}),false);
assert.equal(ctx.powerSourceAccepted(legacyPower,{power_repost_rostov:source}),false,'another healthy mirror cannot validate generic legacy ID');
console.log('PASS legacy producer compatibility: exact domain-specific state binding for electricity reposts');

const knownClosure={...oldConfirmed,status:'resolved',resolvedAt:'2026-10-29T09:20:00Z',retained:true};
const olderClosed={...oldFeed,events:[knownClosure]};
const newerActive={...newerEmpty,events:[media]};
for(const feeds of [[olderClosed,newerActive],[newerActive,olderClosed]]){
 ctx.applyFeed(ctx.mergePublicFeeds(feeds));assert.equal(state.events.length,0,'validated retained closure cannot be resurrected by newer active copy in either feed order');
}
console.log('PASS closure parity: a verified closed event never resurrects from an old active publication');
