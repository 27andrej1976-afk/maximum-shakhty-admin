"""Compare candidate and baseline on captured real notices; no deployment."""
import json,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'report'
sys.path.insert(0,str(ROOT.parent/'scripts'))
import collect_water as old
import water_verified as new
from test_verified import EXPECTED,RAW,POSTS
rows=[]
for key,wanted in EXPECTED.items():
    ident='oursv/'+key if key=='1591' else 'shakhtinskiy/'+key
    p=POSTS[ident];kind=old.classify(p['text']);areas=old.parse_affected(p['text'])
    start,end=old.schedule(p['text'],datetime.fromisoformat(p['publishedAt']),kind)
    fixed=new.normalize(p)
    checked=('kind','roadCount') if wanted[0]=='resolved' else ('kind','roadCount','start','end')
    before={'kind':kind,'roadCount':len(areas),'start':start,'end':end}
    after={'kind':fixed['kind'],'roadCount':len(fixed['affected']),'start':fixed['start'],'end':fixed['end']}
    expected=dict(zip(('kind','roadCount','start','end'),wanted))
    row={'id':ident,'source':p['url'],'publishedAt':p['publishedAt'],'historical':key!='1591',
      'before':before,'after':after,'expected':expected,
      'beforePass':all(before[k]==expected[k] for k in checked),
      'afterPass':all(after[k]==expected[k] for k in checked),
      'checkedFields':checked,'reviewRequired':fixed['reviewRequired']}
    rows.append(row)
now=datetime.now(timezone.utc)
feed=new.build_feed(RAW,now)
current=json.loads((ROOT.parent/'data/water.json').read_text(encoding='utf-8'))
feed['sources']=current['sources']
summary={'evaluatedAt':now.isoformat(),'productionChanged':False,'sourcesProbed':13,
 'realPublicationsCaptured':len(RAW),'uniqueRealNotices':len(rows),'historicalNotices':20,
 'recentUniqueNotices':1,'beforeFullyPassed':sum(r['beforePass'] for r in rows),
 'candidateFullyPassed':sum(r['afterPass'] for r in rows),
 'currentCandidateEventCount':len(feed['events']),'unitTestExpectedCount':37,
 'limitations':['No authorized MAX bot channel access. Public profiles do not expose a feed.',
 'Replay verifies fixed examples, not complete source coverage.',
 'Native Android delivery and multi-day monitoring not tested by this run.'],
 'comparison':rows}
(OUT/'evaluation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'candidate_feed.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2),encoding='utf-8')
code=OUT/'candidate';code.mkdir(exist_ok=True)
for name in ('water_verified.py','test_verified.py','evaluate.py'):
    shutil.copy2(ROOT/name,code/name)
shutil.copy2(OUT/'real_posts.json',code/'fixtures.json')
print('REPLAY_EVALUATION',json.dumps({k:v for k,v in summary.items() if k!='comparison'},ensure_ascii=False),flush=True)
if summary['candidateFullyPassed']!=len(rows):raise SystemExit('Manual replay expectations failed')
