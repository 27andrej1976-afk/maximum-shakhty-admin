import unittest,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct-v09'))
from water_retention import merge
class WaterRetention(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,25,12,tzinfo=timezone.utc)
  self.e={'id':'water-test','category':'water','sourceId':'water_kvu','origin':'media_report','url':'https://kvu.su/utilities/report.html','status':'active','publishedAt':self.now.isoformat(),'start':self.now.isoformat(),'end':self.now.isoformat(),'affected':[{'street':'ул Индустриальная','houses':[]}]}
  self.sources=[{'id':'water_kvu','status':'ok','checkedAt':self.now.isoformat()}]
 def test_errors_empty_success_and_refresh_never_extend_36_hours(self):
  saved=merge([self.e],[],self.sources,self.now)
  for hour in (1,24,35):
   saved=merge([],saved,[{'id':'water_kvu','status':'error'}],self.now+timedelta(hours=hour));self.assertEqual(len(saved),1)
  self.assertEqual(merge([],saved,self.sources,self.now+timedelta(hours=36)),[])
 def test_no_end_uses_original_start(self):
  del self.e['end'];self.assertEqual(len(merge([self.e],[],self.sources,self.now+timedelta(hours=35))),1)
  self.assertEqual(merge([self.e],[],self.sources,self.now+timedelta(hours=36)),[])
 def test_explicit_restoration_closes_matching_coverage(self):
  r={**self.e,'id':'restoration','status':'resolved','publishedAt':(self.now+timedelta(hours=1)).isoformat()}
  out=merge([r],[self.e],self.sources,self.now+timedelta(hours=2));self.assertTrue(all(x['status']=='resolved' for x in out))
  r['affected']=[{'street':'ул Другая','houses':[]}]
  out=merge([r],[self.e],self.sources,self.now+timedelta(hours=2));self.assertEqual(out[0]['status'],'unconfirmed')
 def test_resolved_notice_does_not_reappear(self):
  closed={**self.e,'status':'resolved'}
  out=merge([self.e],[closed],self.sources,self.now);self.assertEqual(out[0]['status'],'resolved')
