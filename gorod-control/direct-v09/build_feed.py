"""Independent v0.9 feed. Never changes the installed v0.7 website or fabricates publication times."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,sys,json,shutil
from power_direct import collect as collect_power
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'direct-v09'
sys.path.insert(0,str(ROOT/'scripts'))

def main():
 now=datetime.now(timezone.utc)
 # Read the existing, separately maintained municipal feed. Its own check timestamps are preserved.
 baseline=json.loads((ROOT/'data/water.json').read_text(encoding='utf-8'))
 oldcheck=baseline.get('checkedAt')
 spec=importlib.util.spec_from_file_location('verified_v09',OUT/'water_verified.py')
 verified=importlib.util.module_from_spec(spec);spec.loader.exec_module(verified)
 norm=verified.build_feed(baseline.get('archive',[]),now)
 water=[]
 for e in norm['events']:
  e['fullText']=e.get('text',e.get('description',''))
  if e.get('unmappedAreaText') or e.get('zones'):e['requiresReview']=True
  water.append(e)
 power,source=collect_power(now)
 sources=[]
 for s in baseline.get('sources',[]):
  if s.get('id') in ('power_planned','power_direct','ursv_device'):continue
  s=dict(s);s['checkedAt']=s.get('checkedAt',oldcheck);sources.append(s)
 sources.append(source)
 events=water+[e for e in baseline.get('events',[]) if e.get('category')!='water']+power
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
