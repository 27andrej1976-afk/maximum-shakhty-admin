"""Manual assertions over captured real notices. Historical samples are replay-only."""
import json,unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import water_verified as v
P=Path(__file__).parent
F=P/'fixtures.json'
if not F.exists():F=P/'report'/'real_posts.json'
RAW=json.loads(F.read_text(encoding='utf-8'))
POSTS={p['id']:p for p in RAW}
EXPECTED={
'10840':('emergency',7,'2026-08-06T15:15:00+03:00','2026-08-06T20:00:00+03:00'),
'10841':('resolved',7,None,None),
'10842':('emergency',9,'2026-08-10T13:35:00+03:00','2026-08-10T19:00:00+03:00'),
'10843':('resolved',0,None,None),
'10844':('emergency',11,'2026-08-11T09:30:00+03:00','2026-08-11T18:00:00+03:00'),
'10845':('emergency',13,'2026-08-11T14:30:00+03:00','2026-08-11T18:00:00+03:00'),
'10846':('resolved',13,None,None),
'10847':('emergency',10,'2026-08-12T15:00:00+03:00','2026-08-12T21:00:00+03:00'),
'10848':('resolved',10,None,None),
'10849':('emergency',15,'2026-08-13T07:00:00+03:00','2026-08-13T17:00:00+03:00'),
'10850':('emergency',5,'2026-08-13T11:30:00+03:00','2026-08-13T17:00:00+03:00'),
'10851':('resolved',15,None,None),
'10852':('extension',5,None,'2026-08-13T20:00:00+03:00'),
'10853':('resolved',5,None,None),
'10854':('planned',10,'2026-08-17T08:00:00+03:00','2026-08-20T08:00:00+03:00'),
'10855':('emergency',10,'2026-08-16T12:30:00+03:00','2026-08-16T19:00:00+03:00'),
'10856':('emergency',2,'2026-08-19T09:50:00+03:00','2026-08-19T18:00:00+03:00'),
'10857':('emergency',5,'2026-08-19T11:40:00+03:00','2026-08-19T18:00:00+03:00'),
'10858':('resolved',2,None,None),
'10859':('resolved',5,None,None),
'1591':('emergency',5,'2026-10-17T09:30:00+03:00','2026-10-17T18:00:00+03:00')}
def p(n):return POSTS['shakhtinskiy/'+str(n)]
class RealReplay(unittest.TestCase):
 def test_suffix_houses(self):
  x=v.normalize(p(10844));self.assertIn({'street':'пер Туркменский','houses':['23','25']},x['affected']);self.assertIn({'street':'пер Ангелиной','houses':[]},x['affected'])
 def test_three_day_plan_and_partial_areas(self):
  x=v.normalize(p(10854));self.assertEqual(len(x['zones']),6);self.assertEqual(sum(z['partial'] for z in x['zones']),2)
  self.assertTrue(x['reviewRequired']);self.assertTrue(x['unmappedAreaText']);self.assertIn({'street':'проспект Карла Маркса','houses':['152-188']},x['affected'])
  self.assertEqual((datetime.fromisoformat(x['end'])-datetime.fromisoformat(x['start'])).total_seconds()/3600,72)
 def test_extension_one_incident_updated_not_duplicated(self):
  r=v.build_feed([p(10850),p(10852)],datetime.fromisoformat('2026-08-13T17:10:00+03:00'))
  self.assertEqual(len(r['events']),1);e=r['events'][0]
  self.assertEqual(e['start'],'2026-08-13T11:30:00+03:00');self.assertEqual(e['end'],'2026-08-13T20:00:00+03:00');self.assertEqual(e['revision'],2);self.assertEqual(len(e['evidence']),2)
 def test_exact_restoration_chain(self):
  r=v.build_feed([p(10850),p(10852),p(10853)],datetime.fromisoformat('2026-08-13T20:00:00+03:00'))
  self.assertEqual(len(r['events']),0);self.assertEqual(r['incidents'][0]['status'],'resolved');self.assertEqual(len(r['incidents'][0]['evidence']),3)
 def test_conflicting_work_address_requires_review(self):
  r=v.build_feed([p(10842),p(10843)],datetime.fromisoformat('2026-08-10T18:00:00+03:00'));self.assertEqual(len(r['events']),1);self.assertEqual(len(r['unlinked']),1)
 def test_conflicting_street_lane_no_false_restoration(self):
  r=v.build_feed([p(10857),p(10859)],datetime.fromisoformat('2026-08-19T18:00:00+03:00'));self.assertEqual(len(r['events']),1);self.assertEqual(len(r['unlinked']),1)
 def test_same_event_from_two_mirrors(self):
  r=v.build_feed([i for i in RAW if i['id']=='oursv/1591'],datetime.fromisoformat('2026-10-17T12:00:00+03:00'))
  self.assertEqual(len(r['events']),1);self.assertEqual(r['duplicatePublications'],1);self.assertEqual(len(r['events'][0]['evidence']),2)
 def test_historical_data_never_becomes_current(self):
  r=v.build_feed(RAW,datetime.fromisoformat('2026-10-18T00:20:00+03:00'))
  self.assertEqual([i['id'] for i in r['events']],['water-oursv-1591']);self.assertEqual(r['events'][0]['status'],'unconfirmed')
 def test_changed_shorter_message_newer_version(self):
  a=deepcopy(POSTS['oursv/1591']);b=deepcopy(a);a['observedAt']='2026-10-17T10:05:00+03:00';b['observedAt']='2026-10-17T10:20:00+03:00'
  b['text']=b['text'].replace('18-00','19-00').split('Подвоз воды')[0]
  r=v.build_feed([a,b],datetime.fromisoformat('2026-10-17T12:00:00+03:00'));self.assertEqual(len(r['events']),1);self.assertEqual(r['events'][0]['end'],'2026-10-17T19:00:00+03:00')
 def test_unknown_edit_order_is_not_invented(self):
  a=deepcopy(POSTS['oursv/1591']);b=deepcopy(a);b['text']=b['text'].replace('18-00','19-00')
  r=v.build_feed([a,b],datetime.fromisoformat('2026-10-17T12:00:00+03:00'));self.assertEqual(len(r['events']),0);self.assertEqual(len(r['revisionConflicts']),1)
 def test_no_forecast_restoration(self):
  self.assertNotEqual(v.classify('Снижение давления. Ожидаем восстановление водоснабжения.'),'resolved');self.assertNotEqual(v.classify('Работы не завершены. Водоснабжение будет восстановлено позже.'),'resolved')
 def test_unknown_completion(self):
  x=deepcopy(POSTS['oursv/1591']);x['text']=x['text'].split('Ориентировочное')[0];self.assertIsNone(v.normalize(x)['end'])
 def test_restoration_cannot_cover_other_houses(self):
  self.assertFalse(v.covers([{'street':'ул Советская','houses':['11']}],[{'street':'ул Советская','houses':['13']}]))
 def test_partial_restore_not_full(self):
  self.assertFalse(v.covers([{'street':'ул Советская','houses':[]},{'street':'пер Мира','houses':[]}],[{'street':'ул Советская','houses':[]}]))
 def test_month_name_dates(self):
  start,end=v.schedule('31 октября с 8.00 до 12.00 1 ноября будут плановые работы',datetime.fromisoformat('2026-10-17T12:00:00+03:00'),'planned');self.assertEqual(start,'2026-10-31T08:00:00+03:00');self.assertEqual(end,'2026-11-01T12:00:00+03:00')
 def test_minutes_not_publication_seconds(self):self.assertEqual(v.normalize(p(10842))['start'],'2026-08-10T13:35:00+03:00')
def make_case(ident,want):
 def case(self):
  post=POSTS['oursv/'+ident if ident=='1591' else 'shakhtinskiy/'+ident];n=v.normalize(post);self.assertEqual((n['kind'],len(n['affected']),n['start'],n['end']),want)
 return case
for ident,want in EXPECTED.items():setattr(RealReplay,'test_real_published_'+ident,make_case(ident,want))
if __name__=='__main__':unittest.main(verbosity=2)
