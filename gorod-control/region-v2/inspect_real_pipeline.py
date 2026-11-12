"""Process a bounded public-channel snapshot locally; no false healthy catch-up."""
import argparse,json
from pathlib import Path
from core import Store
from parse_publications import load_index
from pipeline import process
from geography import GeometryCache
from run_collector import atomic_json


def inspect(sample,index_path,registry_path,output,*,geometry_path=None):
    sample=json.loads(Path(sample).read_text());now=sample['checkedAt'];index=load_index(index_path)
    sources=json.loads(Path(registry_path).read_text())['channels']
    sources=[dict(s,enabled=bool(s.get('identity_verified'))) for s in sources if s.get('chat_id')]
    catalog={'regionId':'RU-ROS','dataMode':'production','municipalities':index['municipalities'],'addresses':[]}
    store=Store(':memory:',sources)
    for channel in sample['channels']:
        source=next(s for s in sources if s['url']==channel['url'])
        with store.db:
            for post in channel['posts']:
                post=dict(post,sourceId=source['id'])
                store._write_post(source['id'],post)
        # A 100-message sample proves neither complete history nor current feed.
        store.failure(source['id'],now,'GAP',gap=True)
    cache=GeometryCache(geometry_path) if geometry_path else None
    ledger,stats=process(store,catalog,index,now,geometry=cache.values() if cache else {})
    feed=ledger.feed(now);feed['verificationMode']='bounded-real-publication-snapshot'
    feed['notice']='Контрольная сводка реальных MAX-публикаций; это не работающий постоянный сборщик. '+feed['notice']
    atomic_json(output,feed,mode=0o644)
    result={'checkedAt':now,'stats':stats,'events':len(feed['events']),
            'byCategory':{c:sum(e['category']==c for e in feed['events']) for c in ['water','power','mchs']},
            'addressMarkers':sum(a.get('geometryVerified',False) for e in feed['events'] for a in e['addresses']),
            'pendingPublications':len(feed['pendingPublications']),'completeHistory':False}
    if cache:cache.close()
    store.db.close();return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['sample','index','registry','output']:p.add_argument('--'+key,required=True)
    p.add_argument('--geometry');a=p.parse_args()
    print(json.dumps(inspect(a.sample,a.index,a.registry,a.output,geometry_path=a.geometry),ensure_ascii=False))
