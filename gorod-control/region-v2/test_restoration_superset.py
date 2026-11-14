import copy
import json
from pathlib import Path
import unittest
from core import Store
from parse_publications import load_index
from pipeline import process

ROOT = Path(__file__).parent
NOW = '2026-11-14T20:00:00+00:00'


class RestorationCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = load_index(ROOT / 'gar-rostov-20261106.json.gz')
        cls.source = next(s for s in json.loads((ROOT / 'sources.draft.json').read_text())['channels'] if s['id'] == 'ursv')

    def setUp(self):
        self.store = Store(':memory:', [dict(self.source, enabled=True)])
        self.catalog = dict(regionId='RU-ROS', dataMode='production', municipalities=self.index['municipalities'], addresses=[])
        self.incident = json.loads((ROOT / 'testdata/water-pressure-20261113.json').read_text())
        self.restoration = json.loads((ROOT / 'testdata/water-restored-20261113.json').read_text())
        self.incident['id'] = self.incident['id'].split('/')[-1]
        self.restoration['id'] = self.restoration['id'].split('/')[-1]

    def tearDown(self):
        self.store.db.close()

    def run_posts(self, *posts):
        with self.store.db:
            for post in posts:
                self.store._write_post('ursv', post)
        return process(self.store, self.catalog, self.index, NOW)

    def test_real_restoration_with_repair_street_closes_nine_streets_once(self):
        ledger, stats = self.run_posts(self.incident, self.restoration)
        self.assertEqual(stats['restorations'], 1)
        self.assertEqual(ledger.events(NOW), [])
        row = self.store.db.execute("SELECT payload FROM review_log WHERE json_extract(payload,'$.type')='restoration'").fetchone()
        self.assertEqual(len(json.loads(row[0])['addressIds']), 9)
        _, repeated = process(self.store, self.catalog, self.index, NOW)
        self.assertEqual(repeated['restorations'], 0)

    def test_partial_street_list_does_not_close_whole_incident(self):
        self.restoration['text'] = self.restoration['text'].replace('г Шахты, ул Песчаная\n', '')
        ledger, stats = self.run_posts(self.incident, self.restoration)
        self.assertEqual(stats['restorations'], 0)
        self.assertEqual(len(ledger.events(NOW)), 1)

    def test_house_specific_restoration_does_not_close_whole_streets(self):
        self.restoration['text'] = self.restoration['text'].replace('г Шахты, ул Песчаная', 'г Шахты, ул Песчаная, д. 2')
        _, stats = self.run_posts(self.incident, self.restoration)
        self.assertEqual(stats['restorations'], 0)

    def test_multiple_overlapping_incidents_are_ambiguous(self):
        second = copy.deepcopy(self.incident)
        second['id'] = 'synthetic-second-incident'
        second['publishedAt'] = '2026-11-13T09:00:00+00:00'
        _, stats = self.run_posts(self.incident, second, self.restoration)
        self.assertEqual(stats['restorations'], 0)

    def test_older_restoration_does_not_close_newer_incident(self):
        self.incident['publishedAt'] = '2026-11-14T08:00:00+00:00'
        ledger, stats = self.run_posts(self.incident, self.restoration)
        self.assertEqual(stats['restorations'], 0)
        self.assertEqual(len(ledger.events(NOW)), 1)

    def test_unknown_restoration_street_requires_review(self):
        self.restoration['text'] = self.restoration['text'].replace('г Шахты, ул Тимирязева', 'г Шахты, ул Несуществующая12345')
        _, stats = self.run_posts(self.incident, self.restoration)
        self.assertEqual(stats['restorations'], 0)
