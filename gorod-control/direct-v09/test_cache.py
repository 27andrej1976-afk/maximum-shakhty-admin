import unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import power_resilient as r
class CacheTests(unittest.TestCase):
 def test_500_keeps_last_true_timestamp_and_marks_every_event(self):
  now=datetime(2026,10,18,0,0,tzinfo=timezone.utc);old=now-timedelta(hours=1)
  record={'source':{'id':'power_direct','status':'ok','checkedAt':old.isoformat(),'tlsVerified':True},'events':[{'id':'x','sourceId':'power_direct','end':(now+timedelta(days=1)).isoformat(),'status':'active','description':'Реальные плановые работы'}]}
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'cache.json';p.write_text(json.dumps(record))
   with patch.object(r,'CACHE',p),patch.object(r,'network_collect',return_value=([],{'status':'error','note':'HTTP 500'})):
    events,src=r.collect(now)
  self.assertEqual(src['checkedAt'],old.isoformat());self.assertEqual(src['lastAttemptAt'],now.isoformat());self.assertEqual(src['status'],'cached')
  self.assertTrue(events[0]['cachedEvidence']);self.assertTrue(events[0]['requiresReview'])
 def test_expired_cache_is_not_current(self):
  now=datetime.now(timezone.utc)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'cache.json';p.write_text(json.dumps({'source':{'checkedAt':(now-timedelta(days=2)).isoformat()},'events':[]}))
   with patch.object(r,'CACHE',p),patch.object(r,'network_collect',return_value=([],{'status':'error','note':'HTTP 500'})):
    events,src=r.collect(now)
  self.assertEqual(events,[]);self.assertEqual(src['status'],'error')
if __name__=='__main__':unittest.main(verbosity=2)
