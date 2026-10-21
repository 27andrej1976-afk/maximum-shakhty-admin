import sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct-v09'))
from power_retention import merge
class Retention(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,21,12,tzinfo=timezone.utc)
  self.e={'id':'a','category':'power','sourceId':'power_direct','origin':'official_site','url':'https://donenergo.ru/grafik-otklyucheniy/61/1/','status':'active','start':self.now.isoformat(),'end':self.now.isoformat(),'observedAt':self.now.isoformat(),'affected':[{'street':'ул Тестовая','houses':['12']}]}
 def test_outage_empty_and_repeated_checks_never_extend_deadline(self):
  saved=merge([], [self.e],[], self.now+timedelta(hours=35))
  self.assertEqual(saved[0]['status'],'unconfirmed');self.assertTrue(saved[0]['retained'])
  self.assertEqual(merge([],saved,[],self.now+timedelta(hours=36)),[])
 def test_successful_empty_is_not_restoration(self):
  self.assertEqual(len(merge([],[self.e],[{'id':'power_direct','status':'ok'}],self.now)),1)
 def test_no_end_uses_incident_time(self):
  del self.e['end']
  self.assertEqual(len(merge([],[self.e],[],self.now+timedelta(hours=35))),1)
  self.assertEqual(merge([],[self.e],[],self.now+timedelta(hours=36)),[])
 def test_new_explicit_restoration_matches_exact_houses_only(self):
  r={**self.e,'id':'restore','status':'resolved','publishedAt':(self.now+timedelta(hours=1)).isoformat()}
  out=merge([r],[self.e],[{'id':'power_direct','status':'ok'}],self.now+timedelta(hours=2))
  self.assertTrue(all(e['status']=='resolved' for e in out))
  r['affected']=[{'street':'ул Тестовая','houses':['14']}]
  out=merge([r],[self.e],[{'id':'power_direct','status':'ok'}],self.now+timedelta(hours=2))
  self.assertEqual(out[0]['status'],'unconfirmed')
 def test_untrusted_origin_is_rejected(self):
  self.e['url']='https://donenergo.ru.evil.test/'
  self.assertEqual(merge([],[self.e],[],self.now),[])
 def test_previous_restoration_is_not_a_new_incident_resolution(self):
  r={**self.e,'id':'restore','status':'resolved','publishedAt':(self.now-timedelta(hours=1)).isoformat()}
  self.assertEqual(merge([r],[self.e],[{'id':'power_direct','status':'ok'}],self.now)[0]['status'],'unconfirmed')
 def test_verified_max_survives_source_error_and_expires_at_36_hours(self):
  e={**self.e,'sourceId':'max_power','origin':'official_max','url':'https://max.ru/id6163089292_biz','requiresReview':False}
  saved=merge([e],[],[{'id':'max_power','status':'ok','checkedAt':self.now.isoformat()}],self.now)
  self.assertEqual(len(saved),1)
  self.assertEqual(len(merge([],saved,[{'id':'max_power','status':'error'}],self.now+timedelta(hours=35))),1)
  self.assertEqual(merge([],saved,[],self.now+timedelta(hours=36)),[])
  e['sourceId']='max_city';self.assertEqual(merge([e],[],[{'id':'max_city','status':'ok'}],self.now),[])
 def test_max_review_candidate_cannot_close_a_verified_power_event(self):
  r={**self.e,'id':'candidate','sourceId':'max_power','origin':'official_max','url':'https://max.ru/id6163089292_biz','requiresReview':True,'status':'resolved','publishedAt':(self.now+timedelta(hours=1)).isoformat()}
  out=merge([r],[self.e],[{'id':'max_power','status':'ok'}],self.now+timedelta(hours=2))
  self.assertEqual(out[0]['status'],'unconfirmed')
if __name__=='__main__':unittest.main()
