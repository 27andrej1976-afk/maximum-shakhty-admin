import unittest,tempfile
from datetime import datetime,timezone,timedelta
from core import Store,same_address,visible_event
class RegionalTests(unittest.TestCase):
 def setUp(self):
  self.c={'id':'demo','url':'https://max.ru/demo_public','chat_id':123,'transport':'max','identity_verified':True,'categories':['water'],'municipalities':['sha']}
  self.s=Store(':memory:',[self.c]);self.now='2026-11-10T08:00:00+03:00'
  self.p={'id':'a','channel_id':123,'publishedAt':self.now,'text':'Тестовое объявление'}
 def test_replaying_page_does_not_duplicate(self):
  self.s.ingest('demo',[self.p],'1',self.now);self.s.ingest('demo',[self.p],'1',self.now)
  self.assertEqual(len(self.s.posts('demo')),1)
 def test_restart_preserves_cursor_and_evidence(self):
  with tempfile.TemporaryDirectory() as t:
   s=Store(t+'/store.sqlite',[self.c]);s.ingest('demo',[self.p],'cursor',self.now);s.db.close()
   s=Store(t+'/store.sqlite',[self.c]);self.assertEqual(s.checkpoint('demo'),'cursor');self.assertEqual(len(s.posts('demo')),1);s.db.close()
 def test_failure_preserves_posts_and_cursor(self):
  self.s.ingest('demo',[self.p],'1',self.now);self.s.failure('demo',self.now,'TIMEOUT')
  self.assertEqual(len(self.s.posts('demo')),1);self.assertEqual(self.s.checkpoint('demo'),'1')
  self.assertEqual(self.s.category_status('water','sha',self.now)['state'],'unavailable')
 def test_incomplete_history_never_advances_cursor(self):
  self.s.ingest('demo',[self.p],'1',self.now)
  with self.assertRaises(ValueError):self.s.ingest('demo',[],'2',self.now,complete=False)
  self.assertEqual(self.s.checkpoint('demo'),'1')
 def test_atomic_batch_rolls_back(self):
  with self.assertRaises(RuntimeError):self.s.ingest('demo',[self.p],'1',self.now,fail_before_commit=True)
  self.assertEqual(self.s.posts('demo'),[]);self.assertIsNone(self.s.checkpoint('demo'))
 def test_edit_preserves_revision(self):
  self.s.ingest('demo',[self.p],'1',self.now);p=dict(self.p,text='Исправлено');self.s.ingest('demo',[p],'2',self.now)
  self.assertEqual(self.s.posts('demo')[0]['text'],'Исправлено')
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM revisions').fetchone()[0],2)
 def test_non_max_or_unknown_identity_is_rejected(self):
  for c in [dict(self.c,transport='rss'),dict(self.c,url='https://example.org'),dict(self.c,identity_verified=False),dict(self.c,enabled=False)]:
   with self.subTest(c=c),self.assertRaises(ValueError):Store(':memory:',[c]).ingest('demo',[self.p],'1',self.now)
 def test_different_chat_is_not_ingested(self):
  with self.assertRaises(ValueError):self.s.ingest('demo',[dict(self.p,channel_id=999)],'1',self.now)
 def test_no_coverage_is_not_no_incidents(self):
  self.assertEqual(self.s.category_status('mchs','sha',self.now)['state'],'unconfigured')
  self.assertEqual(self.s.category_status('water','rostov',self.now)['state'],'unconfigured')
 def test_old_check_never_becomes_green(self):
  self.s.ingest('demo',[],'1',self.now)
  self.assertEqual(self.s.category_status('water','sha','2026-11-10T09:00:00+03:00')['state'],'unavailable')
 def test_same_street_in_other_city_never_matches(self):
  a={'region_id':'RU-ROS','municipality_id':'sha','street_id':'1','houses':[]}
  self.assertFalse(same_address(a,dict(a,municipality_id='rostov')));self.assertTrue(same_address(a,a))
 def test_retention_and_resolution(self):
  e={'region_id':'RU-ROS','municipality_id':'sha','category':'water','end':self.now,'status':'unconfirmed'}
  self.assertTrue(visible_event(e,'2026-11-11T19:59:59+03:00'))
  self.assertFalse(visible_event(e,'2026-11-11T20:00:00+03:00'))
  self.assertFalse(visible_event(dict(e,status='resolved'),self.now))
 def test_mchs_uses_official_expiration(self):
  e={'region_id':'RU-ROS','municipality_id':'sha','category':'mchs','end':self.now}
  self.assertFalse(visible_event(e,self.now));self.assertFalse(visible_event(dict(e,end=None),self.now))
if __name__=='__main__':unittest.main()
