"""Bounded read-only real MAX -> persistent contracts -> public Android QA feed.

Private session and evidence DB exist only inside a temporary directory, never
in the exported assets/artifacts. Does not deploy, join or send messages.
"""
import argparse,asyncio,json,logging,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from collector import collect_all
from core import Store
from diagnose_max import decode_session,make_client,SESSION,error_code
from parse_publications import load_index
from pipeline import process
from run_collector import atomic_json

ROOT=Path(__file__).parent

async def verify(output,report_path):
    now=datetime.now(timezone.utc).isoformat()
    report={'checkedAt':now,'readScope':'four-verified-public-resource-and-emergency-channels',
            'deployed':False,'channels':[],'completeHistory':False,'stage':'session'}
    old_logging=logging.root.manager.disable;logging.disable(logging.CRITICAL)
    try:
        raw=decode_session(os.environ.get('MAX_USER_SESSION_B64',''))
        with tempfile.TemporaryDirectory(prefix='don-real-pipeline-') as folder:
            db=Path(folder)/SESSION;db.write_bytes(raw);db.chmod(0o600)
            sources=[dict(s,enabled=True) for s in json.loads((ROOT/'sources.draft.json').read_text())['channels']
                     if s.get('identity_verified') and type(s.get('chat_id')) is int]
            index=load_index(ROOT/'gar-rostov-20261106.json.gz')
            catalog={'regionId':'RU-ROS','dataMode':'production','municipalities':index['municipalities'],'addresses':[]}
            store=Store(Path(folder)/'evidence.sqlite',sources)
            client=None
            try:
                client=make_client(folder);report['stage']='connect'
                await asyncio.wait_for(client.connect(),45)
                report['stage']='history'
                # Resume actual checkpoints instead of assuming the newest 100
                # messages are a complete water feed.
                for _ in range(3):
                    results=await asyncio.wait_for(collect_all(store,client,now,max_pages=20),240)
                    if all(r['state']=='read' for r in results):break
                report['channels']=results
                report['completeHistory']=len(results)==4 and all(r['state']=='read' for r in results)
                report['stage']='process'
                geometry=json.loads((ROOT/'geometry.verified.json').read_text())
                ledger,stats=process(store,catalog,index,now,geometry=geometry)
                feed=ledger.feed(now)
                feed['verificationMode']='real-MAX-to-Android-QA-export-not-a-deployment'
                feed['notice']='Контрольная выгрузка MAX для проверки Android, не публичный постоянный сборщик. '+feed['notice']
                atomic_json(output,feed,mode=0o644)
                report.update(stage='complete',stats=stats,events=len(feed['events']),
                    markers=sum(a.get('geometryVerified',False) for e in feed['events'] for a in e['addresses']),
                    categories={c:sum(e['category']==c for e in feed['events']) for c in ['water','power','mchs']},
                    pending=len(feed['pendingPublications']))
            finally:
                if client:
                    try:await asyncio.wait_for(client.close(),10)
                    except Exception:pass
                store.db.close()
    except Exception as error:
        report['errorCode']=error_code(error,report['stage'])
    finally:
        logging.disable(old_logging)
    atomic_json(report_path,report,mode=0o644)
    print(json.dumps(report,ensure_ascii=False))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();r=asyncio.run(verify(a.output,a.report))
    raise SystemExit(0 if r['stage']=='complete' and r['completeHistory'] and r.get('markers',0)>0 else 2)
