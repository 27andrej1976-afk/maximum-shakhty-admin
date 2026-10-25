import unittest,json,importlib.util,tempfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
v=module('water_untyped_regression',ROOT/'direct-v09/water_verified.py')
g=module('water_untyped_geometry',ROOT/'map-v07/geometry.py')
class UntypedWaterMapTests(unittest.TestCase):
 def test_plan_name_is_not_square_prefix(self):
  self.assertEqual(v.road('Планировочная')['street'],'ул Планировочная')
  self.assertEqual(v.road('пл. Ленина')['street'],'пл Ленина')
  self.assertIsNone(v.road('ПланБезПроверенногоАдреса'))
 def test_real_notice_maps_all_eight_verified_roads_without_network(self):
  post=json.loads((ROOT/'scripts/fixtures/water-untyped-streets-20261025.json').read_text())
  feed=v.build_feed([post],datetime(2026,10,25,12,tzinfo=timezone.utc))
  self.assertEqual(len(feed['events']),1);e=feed['events'][0]
  self.assertEqual(len(e['affected']),8);self.assertFalse(e['requiresReview'])
  self.assertIn('проспект Строителей',[a['street'] for a in e['affected']])
  self.assertIn('пер Демехина',[a['street'] for a in e['affected']])
  with tempfile.TemporaryDirectory() as folder:
   paths={k:getattr(g,k) for k in ['FEED','CACHE','OUTPUT']};fetch=g.fetch_roads
   try:
    for k in paths:setattr(g,k,Path(folder)/(k+'.json'))
    g.FEED.write_text(json.dumps(feed));g.CACHE.write_text((ROOT/'direct-v09/street-geometry.json').read_text())
    g.fetch_roads=lambda *_:(_ for _ in ()).throw(AssertionError('Verified fallback must not require network'))
    g.main();out=json.loads(g.OUTPUT.read_text())
    points=out['events'][e['id']]['features'];self.assertEqual(len(points),8)
    self.assertTrue(all(p['osmWays'] and p['role']=='street' for p in points))
   finally:
    for k,p in paths.items():setattr(g,k,p)
    g.fetch_roads=fetch
 def test_other_town_is_not_shakhty_water(self):
  from max_utility import water_posts
  post={'sourceId':'max_water','origin':'official_max','url':'https://max.ru/id6167110467_gos','text':'Филиал Новошахтинский сообщает: водоснабжение приостановлено. Адреса: ул Тестовая'}
  self.assertEqual(water_posts([post]),[])
