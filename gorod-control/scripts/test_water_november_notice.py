import json,sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'direct-v09'))
import water_verified as v
from water_retention import merge
class NovemberNoticeTests(unittest.TestCase):
 def setUp(self):
  self.p=json.loads((ROOT/'scripts/fixtures/water-municipal-2026-11-09.json').read_text())['post']
  self.q=dict(self.p,id='mirror/second',sourceId='repost_rostov',url='https://newsrostov.ru/society/2026/11/07/603895.html')
  self.now=datetime(2026,11,10,4,tzinfo=timezone.utc)
 def result(self,posts=None):return v.build_feed(posts or [self.p,self.q],self.now)
 def test_full_date_before_time_and_next_day_completion(self):
  e=self.result()['events'][0]
  self.assertEqual(e['start'],'2026-11-09T21:00:00+03:00')
  self.assertEqual(e['end'],'2026-11-10T05:00:00+03:00')
  self.assertEqual(e['startBasis'],'explicit')
 def test_body_start_date_takes_precedence_over_an_earlier_headline(self):
  p=dict(self.p,text='Опубликовано 8 ноября.\n'+self.p['text'])
  self.assertEqual(self.result([p])['events'][0]['start'],'2026-11-09T21:00:00+03:00')
 def test_all_34_addresses_and_no_false_footer(self):
  e=self.result()['events'][0]
  self.assertEqual(len(e['affected']),34);self.assertFalse(e['requiresReview'])
  self.assertIn('проспект Победа Революции',[a['street'] for a in e['affected']])
  self.assertIn('проезд 3-й Микрорайон',[a['street'] for a in e['affected']])
 def test_mirrors_merge_without_work_site(self):
  d=self.result();self.assertEqual(len(d['events']),1)
  self.assertEqual(len(d['events'][0]['evidence']),2)
 def test_similar_but_changed_notice_is_not_merged(self):
  q=dict(self.q,text=self.q['text'].replace('ул. Советская','ул. Советская, д. 10'))
  self.assertEqual(len(self.result([self.p,q])['events']),2)
 def test_unrecognized_address_remains_reviewed(self):
  p=dict(self.p,text=self.p['text'].replace('ул. Советская','неуточнённая территория'))
  self.assertTrue(self.result([p])['events'][0]['requiresReview'])
 def test_reparse_supersedes_old_cached_mirror_without_renewing_confirmation(self):
  e=self.result()['events'][0];e['reparsedFromCache']=True
  old=[]
  for n in e['updates']:
   old.append(dict(e,id='water-'+n.replace('/','-'),noticeId=n,affected=[],end=None,lastConfirmedAt='2026-11-09T00:00:00+00:00'))
  states=[dict(id=x,status='ok',checkedAt=self.now.isoformat()) for x in ['repost_don','repost_rostov']]
  saved=merge([e],old,states,self.now)
  self.assertEqual(len(saved),1);self.assertEqual(len(saved[0]['affected']),34)
  self.assertEqual(saved[0]['lastConfirmedAt'],'2026-11-09T00:00:00+00:00')
  self.assertTrue(saved[0]['retained'])
  self.assertEqual(datetime.fromisoformat(saved[0]['retainUntil']),datetime(2026,11,11,14,tzinfo=timezone.utc))
 def test_36_hour_deadline_does_not_slide_on_refresh(self):
  e=self.result()['events'][0];states=[dict(id=e['sourceId'],status='ok',checkedAt=self.now.isoformat())]
  deadline=datetime(2026,11,11,14,tzinfo=timezone.utc)
  self.assertEqual(len(merge([e],[],states,deadline-timedelta(seconds=1))),1)
  self.assertEqual(merge([e],[],states,deadline),[])
if __name__=='__main__':unittest.main()
