import json
from pathlib import Path
import unittest
from core import Store,utc
from datetime import timedelta
from events import Ledger
from parse_publications import Templates,load_index
from pipeline import process

ROOT=Path(__file__).parent
NOW='2026-11-12T13:00:00+00:00'

class RealPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=load_index(ROOT/'gar-rostov-20261106.json.gz')
        cls.sample=json.loads((ROOT/'testdata/real-max-20261112.json').read_text())
        cls.registry=json.loads((ROOT/'sources.draft.json').read_text())
    def setUp(self):
        sources=[dict(s,enabled=True) for s in self.registry['channels'] if s.get('chat_id') and s.get('identity_verified')]
        self.store=Store(':memory:',sources)
        self.catalog={'regionId':'RU-ROS','dataMode':'production','municipalities':self.index['municipalities'],'addresses':[]}
        for c in self.sample['channels']:
            source=next(s for s in sources if s['url']==c['url'])
            with self.store.db:
                for post in c['posts']:self.store._write_post(source['id'],dict(post,sourceId=source['id']))
        self.geometry=json.loads((ROOT/'geometry.verified.json').read_text())
    def tearDown(self):self.store.db.close()
    def test_real_water_restoration_does_not_remove_new_outage_and_power_boilerplate_is_not_restoration(self):
        ledger,stats=process(self.store,self.catalog,self.index,NOW,geometry=self.geometry)
        events=ledger.events(NOW)
        self.assertEqual(stats['restorations'],1)
        self.assertEqual({e['category'] for e in events},{'water','power','mchs'})
        water=next(e for e in events if e['category']=='water')
        self.assertIn('117603244689656812',water['id'])
        self.assertNotIn('117602005754466972',' '.join(e['id'] for e in events))
        self.assertEqual(len(water['addresses']),10)
        self.assertEqual(sum(a.get('geometryVerified',False) for a in water['addresses']),3)
        self.assertEqual(water['end'],'2026-11-12T18:00:00+03:00')
        power=next(e for e in events if e['category']=='power')
        self.assertEqual(power['end'],'2026-11-12T15:30:00+03:00')
        self.assertEqual(len(power['addresses']),3)
        self.assertTrue(all(a['geometryVerified'] for a in power['addresses']))
        mchs=next(e for e in events if e['category']=='mchs')
        self.assertEqual(mchs['scope'],'region')
        self.assertEqual(mchs['expiresAt'],'2026-11-13T21:00:00+00:00')
        later=(utc(water['end'])+timedelta(hours=36)).isoformat()
        self.assertFalse(any(e['category']=='water' for e in ledger.events(later)))
        self.assertTrue(any('подвозу воды' in p['text'].lower() for p in ledger.pending()))
    def test_restart_is_idempotent_and_source_failure_preserves_markers(self):
        ledger,_=process(self.store,self.catalog,self.index,NOW,geometry=self.geometry)
        before=[e['id'] for e in ledger.events(NOW)]
        ledger,stats=process(self.store,self.catalog,self.index,NOW,geometry=self.geometry)
        self.assertEqual(stats['incidents'],0);self.assertEqual(stats['restorations'],0)
        self.store.failure('ursv',NOW,'TIMEOUT')
        self.assertEqual(before,[e['id'] for e in ledger.events(NOW)])
        city=next(e['municipalityId'] for e in ledger.events(NOW) if e['category']=='water')
        self.assertEqual(self.store.category_status('water',city,NOW)['state'],'unavailable')
    def test_unknown_street_and_same_name_other_town_never_get_guessed(self):
        t=Templates(self.index)
        city=t.city('г. Белая Калитва, ул. Вокзальная')
        known,unknown=t.addresses('ул. Несуществующая_12345, ул. Вокзальная',city)
        self.assertEqual(len(known),1);self.assertEqual(len(unknown),1)
        self.assertEqual(known[0]['municipalityId'],city['id'])
        self.assertNotEqual(known[0]['id'],t.addresses('ул. Вокзальная',t.city('г. Таганрог'))[0][0]['id'])
