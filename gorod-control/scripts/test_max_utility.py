import json,sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct-v09'))
from max_utility import water_posts,power_posts,power_areas
from water_verified import build_feed

class MaxUtilityTests(unittest.TestCase):
 def setUp(self):
  self.posts=json.loads((Path(__file__).parent/'fixtures/max-public-notices-2026-10.json').read_text(encoding='utf-8'))['posts']
  self.now=datetime(2026,10,21,13,tzinfo=timezone.utc)
 def test_real_water_notices_have_eight_streets_each_and_correct_times(self):
  result=build_feed(water_posts(self.posts),self.now)
  self.assertEqual(len(result['events']),2)
  self.assertTrue(all(len(e['affected'])==8 and not e['requiresReview'] for e in result['events']))
  self.assertEqual({e['end'] for e in result['events']},{'2026-10-21T22:00:00+03:00','2026-10-21T20:00:00+03:00'})
 def test_city_news_is_not_an_outage(self):
  news=next(p for p in self.posts if p['id']=='max_city/117438441723099196')
  self.assertEqual(water_posts([news]),[])
  self.assertEqual(power_posts([news],self.now),[])
 def test_historical_power_is_not_a_current_incident(self):
  self.assertEqual(power_posts(self.posts,self.now),[])
 def test_real_power_replay_preserves_all_streets_and_ninety_minutes(self):
  post=next(p for p in self.posts if p['sourceId']=='max_power')
  replay=datetime.fromisoformat(post['publishedAt'])+timedelta(minutes=5)
  e=power_posts([post],replay)[0]
  self.assertEqual(len(e['affected']),10);self.assertFalse(e['requiresReview'])
  self.assertEqual(e['start'],'2026-10-06T17:10:00+03:00')
  self.assertEqual(e['end'],'2026-10-06T18:40:00+03:00')
  self.assertIn('проспект К. Маркса',[a['street'] for a in e['affected']])
 def test_partial_address_block_needs_review(self):
  areas,issues=power_areas('г. Шахты, в границах: ул. Тестовая 12, 14; неизвестный район.\nОриентировочно 1 час.')
  self.assertEqual(areas[0]['houses'],['12','14']);self.assertTrue(issues)
 def test_untrusted_channel_url_is_rejected(self):
  self.assertEqual(water_posts([{**p,'url':'https://max.ru/other'} for p in self.posts]),[])
 def test_explicit_restoration_and_future_restoration_are_different(self):
  post=next(p for p in self.posts if p['sourceId']=='max_power')
  when=datetime.fromisoformat(post['publishedAt'])+timedelta(minutes=5)
  restored={**post,'text':'г. Шахты. Электроснабжение восстановлено. В границах: ул. Тестовая 12.'}
  self.assertEqual(power_posts([restored],when)[0]['status'],'resolved')
  future={**restored,'text':'г. Шахты. Электроснабжение будет восстановлено. В границах: ул. Тестовая 12.'}
  self.assertEqual(power_posts([future],when),[])
if __name__=='__main__':unittest.main()
