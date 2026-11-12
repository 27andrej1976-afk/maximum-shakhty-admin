"""Verify the deployed public HTTPS feed, without accessing any MAX account."""
import argparse,json,ssl
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

URL='https://chat.sportoskop.ru/don-control/feed.json'

def verify(output,report):
    with urlopen(Request(URL,headers={'Accept':'application/json','User-Agent':'DonControl-Android-QA/1.0'}),timeout=30,context=ssl.create_default_context()) as response:
        if response.status!=200 or response.url!=URL:raise ValueError('Unexpected public endpoint response')
        raw=response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('Public feed exceeds limit')
    feed=json.loads(raw);now=datetime.now(timezone.utc)
    if (feed.get('regionId')!='RU-ROS' or feed.get('mode')!='max-only'
            or feed.get('dataMode')!='production' or feed.get('verificationMode')):
        raise ValueError('A live regional production feed is required')
    age=(now-datetime.fromisoformat(feed['generatedAt'])).total_seconds()
    if not -60<=age<=600:raise ValueError('Live public feed is not fresh')
    counts=Counter(e['category'] for e in feed['events'])
    markers=sum(bool(a.get('geometryVerified')) for e in feed['events'] for a in e['addresses'])
    if not all(counts[c]>0 for c in ['water','power','mchs']) or markers<3:
        raise ValueError('Current real incident sample is insufficient for this Android acceptance check')
    # This bundled asset is a captured snapshot. A separate instrumentation test
    # fetches URL over HTTPS on the emulator; do not confuse those two checks.
    feed['verificationMode']='real-MAX-to-Android-QA-export-not-a-deployment'
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(feed,ensure_ascii=False))
    result={'checkedAt':now.isoformat(),'feedGeneratedAt':feed['generatedAt'],'publicEndpoint':URL,
        'eventsByCategory':dict(counts),'markers':markers,'pending':feed.get('pendingPublicationCount'),
        'maxAccountAccessedByThisCheck':False,'scope':'HTTPS snapshot; separate Android network runtime test required'}
    Path(report).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--report',required=True);a=p.parse_args()
    verify(a.output,a.report)
