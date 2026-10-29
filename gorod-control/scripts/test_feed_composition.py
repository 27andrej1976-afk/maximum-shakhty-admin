"""Offline regression for the 2026-10-29 baseline/direct-feed divergence.

No public source is fetched and no production data is written by these tests.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'direct-v09'))
from build_feed import compose_feed, source_snapshot


class FeedCompositionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 29, 10, 30, tzinfo=timezone.utc)
        self.baseline = json.loads((Path(__file__).parent / 'fixtures' / 'feed-divergence-20261029.json').read_text())
        self.power_source = {'id': 'power_direct', 'status': 'error', 'checkedAt': self.now.isoformat()}

    def compose(self, baseline=None, previous=None, now=None):
        return compose_feed(self.baseline if baseline is None else baseline, previous or [], [], [], [], self.power_source, now or self.now)

    def test_current_archive_keeps_three_attributed_reports_not_unverified_archive(self):
        data, saved, _ = self.compose()
        self.assertEqual(len(data['events']), 3)
        self.assertEqual({e['origin'] for e in data['events']}, {'media_report', 'municipal_repost'})
        self.assertEqual(sum(bool(e['requiresReview']) for e in data['events']), 2)
        self.assertTrue(all(e['fullText'] for e in data['events']))
        self.assertFalse(any(e['origin'] == 'official_archive' for e in saved))
        self.assertEqual(data['baselineCheckedAt'], self.baseline['checkedAt'])
        self.assertNotEqual(data['checkedAt'], data['baselineCheckedAt'])
        self.assertEqual(data['incidents'], [])

    def test_each_report_requires_its_own_successful_source(self):
        for source in self.baseline['sources']:
            if source['id'] == 'water_kvu':
                source.update(status='error', readStatus='error')
        data, _, _ = self.compose()
        self.assertEqual(len(data['events']), 2)
        self.assertFalse(any(e.get('sourceId') == 'water_kvu' for e in data['events']))

    def test_lookalike_domain_cannot_enter_live_events(self):
        for post in self.baseline['archive']:
            if post.get('sourceId') == 'water_kvu':
                post['url'] = post['url'].replace('kvu.su/', 'kvu.su.evil.invalid/')
        data, _, _ = self.compose()
        self.assertEqual(len(data['events']), 2)
        self.assertFalse(any(e.get('sourceId') == 'water_kvu' for e in data['events']))

    def test_unknown_source_time_is_not_promoted_to_build_time(self):
        self.baseline.pop('checkedAt')
        for source in self.baseline['sources']:
            source.pop('checkedAt', None)
        data, _, _ = self.compose()
        self.assertEqual(data['events'], [])
        self.assertTrue(all(s['checkedAt'] is None and s['status'] == 'stale' for s in data['sources'] if s['id'] != 'power_direct'))

    def test_stale_baseline_cannot_look_fresh_after_bundle_rebuild(self):
        old = (self.now - timedelta(hours=5)).isoformat()
        self.baseline['checkedAt'] = old
        for source in self.baseline['sources']:
            source['checkedAt'] = old
        data, _, _ = self.compose()
        self.assertEqual(data['events'], [])
        self.assertEqual(data['baselineCheckedAt'], old)
        self.assertTrue(all(s['checkedAt'] == old and s['status'] == 'stale' and s['readStatus'] == 'stale' for s in data['sources'] if s['id'] != 'power_direct'))

    def test_null_source_timestamp_uses_baseline_not_build_time(self):
        for source in self.baseline['sources']:
            source['checkedAt'] = None
        data, _, _ = self.compose()
        self.assertEqual(len(data['events']), 3)
        self.assertTrue(all(s['checkedAt'] == self.baseline['checkedAt'] for s in data['sources'] if s['id'] != 'power_direct'))

    def test_future_timestamp_does_not_validate_source(self):
        result = source_snapshot({'id': 'water_kvu', 'status': 'ok', 'readStatus': 'ok', 'checkedAt': (self.now + timedelta(minutes=3)).isoformat()}, None, self.now)
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(result['readStatus'], 'stale')

    def test_repeated_failed_refresh_keeps_original_confirmation_and_expiry(self):
        _, saved, _ = self.compose()
        original = {e['id']: (e['lastConfirmedAt'], e['retainUntil']) for e in saved}
        end = datetime.fromisoformat(saved[0]['end'])
        self.baseline['archive'] = []
        for source in self.baseline['sources']:
            source.update(status='error', readStatus='error')
        for hour in (1, 24, 35):
            data, saved, _ = self.compose(previous=saved, now=end + timedelta(hours=hour))
            self.assertEqual(len(data['events']), 3)
            self.assertTrue(all(e['status'] == 'unconfirmed' for e in data['events']))
            self.assertEqual({e['id']: (e['lastConfirmedAt'], e['retainUntil']) for e in saved}, original)
        self.assertEqual(self.compose(previous=saved, now=end + timedelta(hours=36))[0]['events'], [])

    def test_explicit_restoration_closes_only_matching_address(self):
        text = ('В Шахтах 29 октября с 10.00 аварийно-ремонтные работы по адресу: ул. Тестовая, д. 47.\n'
                'Нестабильное водоснабжение по адресам:\nул. Тестовая 47\n'
                'Ориентировочное время завершения работ в 18-00 час. 29.10.2026.')
        post = {'id': 'regression/1', 'publishedAt': '2026-10-29T10:00:00+03:00', 'text': text,
                'url': 'https://kvu.su/utilities/regression.html', 'sourceId': 'water_kvu', 'origin': 'media_report'}
        self.baseline['archive'] = [post]
        _, saved, _ = self.compose()
        self.assertEqual(len(saved), 1)
        restored = {**post, 'id': 'regression/2', 'publishedAt': '2026-10-29T12:00:00+03:00',
                    'text': 'В Шахтах водоснабжение восстановлено по адресу: ул. Тестовая, д. 47.\nАдреса:\nул. Тестовая 47'}
        self.baseline['archive'] = [restored]
        public = self.compose(previous=saved)[0]
        self.assertEqual(public['events'], [])
        # Serialize exactly the public payload: a previously active phone cache
        # receives both the matching event closure and its restoration evidence.
        public = json.loads(json.dumps(public))
        closed = next(e for e in public['incidents'] if e['id'] == saved[0]['id'])
        self.assertEqual(closed['status'], 'resolved')
        self.assertEqual(closed['sourceId'], 'water_kvu')
        self.assertEqual(closed['origin'], 'media_report')
        self.assertEqual(closed['url'], saved[0]['url'])
        self.assertEqual(closed['resolutionUrl'], restored['url'])
        self.assertTrue(all(e['status'] in ('resolved', 'cancelled', 'canceled') for e in public['incidents']))
        restored['text'] = restored['text'].replace('Тестовая', 'Другая')
        result = self.compose(previous=saved)[0]['events']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['status'], 'unconfirmed')

    def test_public_closures_reject_unknown_provenance_and_preserve_cancellation(self):
        _, saved, _ = self.compose()
        cancelled = {**saved[0], 'status': 'cancelled'}
        unknown = {**cancelled, 'id': 'unverified-closure', 'origin': 'official_archive'}
        spoofed = {**cancelled, 'id': 'spoofed-closure', 'url': 'https://kvu.su.evil.invalid/utilities/cancelled.html'}
        self.baseline['archive'] = []
        public = json.loads(json.dumps(self.compose(previous=[cancelled, unknown, spoofed])[0]))
        self.assertEqual(public['events'], [])
        self.assertEqual([e['id'] for e in public['incidents']], [cancelled['id']])
        self.assertEqual(public['incidents'][0]['status'], 'cancelled')
        self.assertEqual(public['incidents'][0]['retainUntil'], cancelled['retainUntil'])

    def test_direct_and_max_power_closures_are_in_public_payload(self):
        event = {'id': 'direct-power-closed', 'category': 'power', 'origin': 'official_site',
                 'sourceId': 'power_direct', 'url': 'https://donenergo.ru/grafik-otklyucheniy/61/1/',
                 'status': 'resolved', 'start': self.now.isoformat(), 'end': self.now.isoformat(),
                 'publishedAt': self.now.isoformat(), 'affected': [{'street': 'ул Тестовая', 'houses': ['47']}]}
        source = {**self.power_source, 'status': 'ok'}
        max_closed = {**event, 'id': 'max-power-closed', 'origin': 'official_max',
                      'sourceId': 'max_power', 'url': 'https://max.ru/id6163089292_biz',
                      'status': 'cancelled', 'requiresReview': False,
                      'lastConfirmedAt': self.now.isoformat()}
        baseline = {'checkedAt': self.now.isoformat(), 'archive': [], 'events': [], 'sources': []}
        public, _, _ = compose_feed(baseline, [max_closed], [], [], [event], source, self.now)
        public = json.loads(json.dumps(public))
        self.assertEqual(public['events'], [])
        self.assertEqual({e['id'] for e in public['incidents']}, {'direct-power-closed', 'max-power-closed'})
        self.assertEqual({e['origin'] for e in public['incidents']}, {'official_site', 'official_max'})

    def test_power_parser_collector_and_composer_keep_exact_mirror_source(self):
        from collect_services import collect_power
        from test_services import POWER, rss
        # Test each producer independently, with real parsing but no network.
        for domain, expected in [('newsrostov.ru', 'power_repost_rostov'), ('news-don.ru', 'power_repost_don')]:
            with self.subTest(domain=domain):
                rss_url = 'https://' + domain + '/rss/'
                raw = rss('г. Шахты, технологическое нарушение в сети 10 кВ', POWER,
                          when='Thu, 29 Oct 2026 13:00:00 +0300',
                          link='https://' + domain + '/society/2026/10/29/1.html')
                with patch('collect_services.RSS_URLS', [rss_url]), patch('collect_services.fetch_rss', return_value=raw):
                    events, states = collect_power(self.now)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['sourceId'], expected)
                self.assertEqual(states[0]['id'], expected)
                baseline = {'checkedAt': self.now.isoformat(), 'archive': [], 'events': events, 'sources': states}
                public = self.compose(baseline=baseline)[0]
                self.assertEqual(len(public['events']), 1)
                self.assertEqual(public['events'][0]['sourceId'], expected)
                # A healthy unrelated mirror must not rescue a failed origin.
                states[0].update(status='error', readStatus='error')
                states.append({'id': 'power_repost_don' if expected.endswith('rostov') else 'power_repost_rostov',
                               'status': 'ok', 'checkedAt': self.now.isoformat()})
                self.assertEqual(self.compose(baseline=baseline)[0]['events'], [])

    def test_composition_does_not_mutate_inputs(self):
        before = deepcopy(self.baseline)
        self.compose()
        self.assertEqual(self.baseline, before)

    def test_live_refresh_chain_is_main_success_same_repository_only(self):
        workflow = (ROOT.parent / '.github/workflows/gorod-v09-live.yml').read_text()
        self.assertIn("workflows: ['City Control | Shakhty Water Notices']", workflow)
        self.assertIn('types: [completed]', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn('github.event.workflow_run.head_repository.full_name == github.repository', workflow)
        self.assertIn('ref: main', workflow)
        self.assertNotIn('ref: ${{ github.event.workflow_run.head_sha', workflow)


if __name__ == '__main__':
    unittest.main()
