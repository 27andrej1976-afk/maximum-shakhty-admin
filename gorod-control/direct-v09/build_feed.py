"""Independent v0.9 feed. Never changes the installed v0.7 website or fabricates publication times."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import importlib.util,sys,json,shutil,re
from power_direct import collect as collect_power
from power_retention import merge as retain_power,stamp
from water_retention import merge as retain_water
from water_verified import build_feed as normalize_water
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'direct-v09'
sys.path.insert(0,str(ROOT/'scripts'))
from max_sources import collect as collect_max
from service_events import CITY
from max_utility import water_posts as max_water_posts,power_posts as max_power_posts

def source_snapshot(source,default_stamp,now):
 """A new bundle timestamp is not evidence that its inputs were read again."""
 result=deepcopy(source)
 result['checkedAt']=result.get('checkedAt') or default_stamp
 checked=stamp(result['checkedAt'])
 if not checked or not timedelta(minutes=-2)<=now-checked<timedelta(hours=4):
  if result.get('status')=='ok' or result.get('readStatus')=='ok':
   result['status']='stale'
   result['readStatus']='stale'
 return result

def compose_feed(baseline,previous,max_posts,max_states,power,power_source,now):
 """Pure composition for offline regression tests; no fetches or writes.

 Only provenance accepted by retention enters live water/power output.
 Archives are re-parsed so explicit restorations are not lost; unknown
 official_archive records remain diagnostics, not trusted live events.
 """
 baseline=deepcopy(baseline)
 oldcheck=baseline.get('checkedAt')
 # Only utility publications from the two public channels are retained for parser review.
 max_review=[p for p in max_posts if re.search(r'водоснабж|подач[а-я]*\s+вод|электро|технологическ[а-я]* наруш|газоснабж',p['text'],re.I)
             and (p['sourceId']=='max_city' or CITY.search(p['text'][:500]) or p['sourceId']=='max_water' and re.search(r'\bШахтинск[а-я]*\b|\bФШ\s+ГУП\b',p['text'],re.I))]
 max_water=max_water_posts(max_posts)
 norm=normalize_water(baseline.get('archive',[])+max_water,now)
 for e in norm['incidents']:
  e['fullText']=e.get('text',e.get('description',''))
  if e.get('unmappedAreaText') or e.get('zones'):e['requiresReview']=True
  if e.get('origin')=='official_max':
   assert e.get('sourceId') in ('max_city','max_water')
 sources=[]
 for s in baseline.get('sources',[]):
  if s.get('id') in ('power_planned','power_direct','ursv_device'):continue
  sources.append(source_snapshot(s,oldcheck,now))
 sources.append(source_snapshot(power_source,None,now))
 sources.extend(source_snapshot(s,None,now) for s in max_states)
 max_events=max_power_posts(max_posts,now)
 events=[e for e in baseline.get('events',[]) if e.get('category')!='water']+deepcopy(power)+max_events
 water_resolutions=[dict(n,category='water',status='resolved',id='restore-water-'+n['id']) for n in norm['notices'] if n.get('kind')=='resolved']
 water_saved=retain_water(norm['incidents']+water_resolutions,previous,sources,now)
 power_saved=retain_power(events,previous,sources,now)
 events=[e for e in events if e.get('category') not in ('power','water')]+[e for e in water_saved+power_saved if e.get('status') not in ('resolved','cancelled','canceled')]
 for e in events:
  e['observedAt']=e.get('observedAt') or oldcheck
 data={'schema':2,'version':'0.9.0-test','checkedAt':now.isoformat(),'coverage':'partial',
       'baselineCheckedAt':oldcheck,
       'sources':sources,'events':events,'archive':baseline.get('archive',[]),
       # Publish closure evidence as well as visible notices. Otherwise a phone
       # retaining an earlier active event cannot learn of direct/MAX repairs.
       # These records already passed provenance/retention checks; never expose
       # arbitrary archive posts as authoritative cancellation tombstones.
       'incidents':[deepcopy(e) for e in water_saved+power_saved if e.get('status') in ('resolved','cancelled','canceled')],
       'normalization':{'duplicatePublications':norm['duplicatePublications'],'revisionConflicts':norm['revisionConflicts'],'unlinked':norm['unlinked']}}
 return data,power_saved+water_saved,{'checkedAt':now.isoformat(),'sources':deepcopy(max_states),'posts':deepcopy(max_review)}

def main():
 now=datetime.now(timezone.utc)
 cache=OUT/'power-cache.json'
 previous=json.loads(cache.read_text()).get('events',[]) if cache.exists() else json.loads((OUT/'feed.json').read_text()).get('events',[])
 # Read the separately maintained municipal feed without renewing its clock.
 baseline=json.loads((ROOT/'data/water.json').read_text(encoding='utf-8'))
 max_posts,max_states=collect_max(now)
 power,source=collect_power(now)
 data,saved,max_review=compose_feed(baseline,previous,max_posts,max_states,power,source,now)
 (OUT/'max-public.json').write_text(json.dumps(max_review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 cache.write_text(json.dumps({'events':saved},ensure_ascii=False,indent=2)+'\n')
 (OUT/'feed.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 spec=importlib.util.spec_from_file_location('geo_v09',ROOT/'map-v07/geometry.py')
 geo=importlib.util.module_from_spec(spec);spec.loader.exec_module(geo)
 geo.FEED=OUT/'feed.json';geo.OUTPUT=OUT/'map-geometry.json';geo.CACHE=OUT/'street-geometry.json'
 if not geo.CACHE.exists():shutil.copy2(ROOT/'data/street-geometry.json',geo.CACHE)
 geo.main()
 print('DIRECT_FEED',json.dumps({'checkedAt':data['checkedAt'],'baselineCheckedAt':data['baselineCheckedAt'],'primaryPower':source,'water':sum(e.get('category')=='water' for e in data['events']),'events':len(data['events'])},ensure_ascii=False))
if __name__=='__main__':main()
