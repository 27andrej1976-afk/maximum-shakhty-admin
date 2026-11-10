"""Independent v0.9 feed. Never changes the installed v0.7 website or fabricates publication times."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,sys,json,shutil,re
from power_direct import collect as collect_power
from power_retention import merge as retain_power
from water_retention import merge as retain_water, source_id as water_source_id
from power_retention import deadline
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'direct-v09'
sys.path.insert(0,str(ROOT/'scripts'))
from max_sources import collect as collect_max
from service_events import CITY, classify_power
from max_utility import water_posts as max_water_posts,power_posts as max_power_posts

def main():
 now=datetime.now(timezone.utc)
 cache=OUT/'power-cache.json'
 previous=json.loads(cache.read_text()).get('events',[]) if cache.exists() else json.loads((OUT/'feed.json').read_text()).get('events',[])
 # Read the existing, separately maintained municipal feed. Its own check timestamps are preserved.
 baseline=json.loads((ROOT/'data/water.json').read_text(encoding='utf-8'))
 oldcheck=baseline.get('checkedAt')
 spec=importlib.util.spec_from_file_location('verified_v09',OUT/'water_verified.py')
 verified=importlib.util.module_from_spec(spec);spec.loader.exec_module(verified)
 max_posts,max_states=collect_max(now)
 # Only utility publications from the two public channels are retained for parser review.
 max_review=[p for p in max_posts if re.search(r'водоснабж|подач[а-я]*\s+вод|электро|технологическ[а-я]* наруш|газоснабж',p['text'],re.I)
             and (p['sourceId']=='max_city' or CITY.search(p['text'][:500]) or p['sourceId']=='max_water' and re.search(r'\bШахтинск[а-я]*\b|\bФШ\s+ГУП\b',p['text'],re.I))]
 (OUT/'max-public.json').write_text(json.dumps({'checkedAt':now.isoformat(),'sources':max_states,'posts':max_review},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 max_water=max_water_posts(max_posts)
 posts=baseline.get('archive',[])+max_water
 known={p['id'] for p in posts}
 # Recent notices can fall out of a short RSS window. Reparse their original
 # evidence without claiming a new source read or extending their deadline.
 for e in previous:
  ident=e.get('noticeId');until=deadline(e)
  if not ident or ident in known or not water_source_id(e) or not until or until<=now or e.get('status') in ('resolved','cancelled','canceled'):continue
  if not e.get('text') or not e.get('publishedAt'):continue
  p={k:e[k] for k in ('publishedAt','text','url','source','origin','sourceId','officialUrl','observedAt') if k in e}
  p['id']=ident;p['reparsedFromCache']=True;posts.append(p);known.add(ident)
 norm=verified.build_feed(posts,now)
 water=[]
 for e in norm['events']:
  e['fullText']=e.get('text',e.get('description',''))
  if e.get('unmappedAreaText') or e.get('zones'):e['requiresReview']=True
  if e.get('origin')=='official_max':
   assert e.get('sourceId') in ('max_city','max_water')
  water.append(e)
 power,source=collect_power(now)
 sources=[]
 for s in baseline.get('sources',[]):
  if s.get('id') in ('power_planned','power_direct','ursv_device'):continue
  s=dict(s);s['checkedAt']=s.get('checkedAt',oldcheck);sources.append(s)
 sources.append(source)
 sources.extend(max_states)
 max_events=max_power_posts(max_posts,now)
 events=water+[e for e in baseline.get('events',[]) if e.get('category')!='water']+power+max_events
 water_resolutions=[dict(n,category='water',status='resolved',id='restore-water-'+n['id']) for n in norm['notices'] if n.get('kind')=='resolved']
 water_saved=retain_water(norm['incidents']+water_resolutions,previous,sources,now)
 power_saved=retain_power(events,previous,sources,now)
 events=[e for e in events if e.get('category') not in ('power','water')]+[e for e in water_saved+power_saved if e.get('status') not in ('resolved','cancelled','canceled')]
 cache.write_text(json.dumps({'events':power_saved+water_saved},ensure_ascii=False,indent=2)+'\n')
 for e in events:
  e['observedAt']=e.get('observedAt') or oldcheck
 data={'schema':2,'version':'0.9.0-test','checkedAt':now.isoformat(),'coverage':'partial',
       'sources':sources,'events':events,'archive':baseline.get('archive',[]),
       'normalization':{'duplicatePublications':norm['duplicatePublications'],'revisionConflicts':norm['revisionConflicts'],'unlinked':norm['unlinked']}}
 (OUT/'feed.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 spec=importlib.util.spec_from_file_location('geo_v09',ROOT/'map-v07/geometry.py')
 geo=importlib.util.module_from_spec(spec);spec.loader.exec_module(geo)
 geo.FEED=OUT/'feed.json';geo.OUTPUT=OUT/'map-geometry.json';geo.CACHE=OUT/'street-geometry.json'
 if not geo.CACHE.exists():shutil.copy2(ROOT/'data/street-geometry.json',geo.CACHE)
 geo.main()
 print('DIRECT_FEED',json.dumps({'checkedAt':data['checkedAt'],'primaryPower':source,'water':len(water),'events':len(events)},ensure_ascii=False))
if __name__=='__main__':main()
