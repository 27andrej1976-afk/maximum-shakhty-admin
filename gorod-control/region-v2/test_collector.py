import asyncio
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as Obj
import unittest

from collector import collect_channel, collect_all, envelope, millis, iso, PAGE_SIZE
from core import Store
from health import snapshot

NOW = '2026-11-10T10:00:00+03:00'
SOURCE = {'id': 'test', 'url': 'https://max.ru/example', 'chat_id': -123,
          'identity_verified': True, 'enabled': True, 'transport': 'max',
          'categories': ['water'], 'municipalities': ['test-city']}


def message(mid, age=1000, **kwargs):
    return Obj(**dict(id=mid, time=millis(NOW) - age, chat_id=-123,
                      text='Тестовое объявление', type='CHANNEL', attaches=[], link=None, **kwargs))


class Fake:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.requests = []
    async def get_chat(self, ident):
        self.requests.append(('identity', ident))
        return Obj(id=ident, type='CHANNEL', access='PUBLIC')
    async def fetch_history(self, **kwargs):
        self.requests.append(kwargs)
        page = next(self.pages)
        if isinstance(page, Exception):
            raise page
        return page


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:', [SOURCE])
    def tearDown(self):
        self.store.db.close()
    def collect(self, pages, **kwargs):
        self.client = Fake(pages)
        return asyncio.run(collect_channel(self.store, self.client, 'test', NOW, **kwargs))
    def test_multi_page_and_boundary_overlap(self):
        result = self.collect([[message(3, 1000), message(2, 2000)],
                               [message(2, 2000), message(1, 3000)],
                               [message(1, 3000)], []])
        self.assertEqual(result['state'], 'read')
        self.assertEqual(len(self.store.posts('test')), 3)
        requests = [r for r in self.client.requests if isinstance(r, dict)]
        self.assertEqual(requests[1]['from_time'], millis(NOW) - 2000)
        self.assertTrue(all(r['interactive'] is False for r in requests))
    def test_timeout_preserves_partial_page_without_advancing_checkpoint(self):
        self.collect([[message(1)], TimeoutError('TOKEN-must-not-leak')])
        self.assertEqual(len(self.store.posts('test')), 1)
        self.assertIsNone(self.store.checkpoint('test'))
        health = snapshot(self.store, 'test-city', NOW)
        self.assertTrue(health['categoryHealth']['water']['hasHistoryGap'])
        self.assertNotIn('TOKEN', str(health))
        self.assertEqual(health['categoryHealth']['water']['state'], 'unavailable')
    def test_restart_resumes_saved_page_position(self):
        with TemporaryDirectory() as folder:
            self.store.db.close()
            self.store = Store(Path(folder) / 'data.sqlite', [SOURCE])
            self.collect([[message(2, 1000), message(1, 2000)], TimeoutError()])
            self.store.db.close()
            self.store = Store(Path(folder) / 'data.sqlite', [SOURCE])
            result = self.collect([[message(1, 2000)], []])
            self.assertEqual(result['state'], 'read')
            req = next(r for r in self.client.requests if isinstance(r, dict))
            self.assertEqual(req['from_time'], millis(NOW) - 2000)
            self.assertEqual(len(self.store.posts('test')), 2)
            self.store.db.close()
            self.store = Store(':memory:', [SOURCE])
    def test_saturated_equal_timestamp_is_gap_never_silent_skip(self):
        page = [message(n, 1000) for n in range(1, PAGE_SIZE + 1)]
        result = self.collect([page, page])
        self.assertEqual(result['errorCode'], 'GAP')
        self.assertIsNone(self.store.checkpoint('test'))
        self.assertEqual(len(self.store.posts('test')), PAGE_SIZE)
    def test_budget_limit_resumes_instead_of_marking_read(self):
        result = self.collect([[message(2), message(1, 2000)]], max_pages=1)
        self.assertEqual(result['errorCode'], 'GAP')
        self.assertIsNone(self.store.checkpoint('test'))
        self.assertEqual(self.collect([[message(1, 2000)], []])['state'], 'read')
    def test_attachment_only_and_forwarded_posts_are_not_lost(self):
        first = message(1)
        first.text = None
        first.attaches = [Obj(url='secret-media-signature')]
        second = message(2, 2000)
        second.link = Obj(token='private')
        self.collect([[first, second], [second], []])
        posts = self.store.posts('test')
        self.assertEqual(len(posts), 2)
        self.assertTrue(all(p['requiresReview'] for p in posts))
        self.assertNotIn('secret-media-signature', str(posts))
        self.assertNotIn('private', str(posts))
        health = snapshot(self.store, 'test-city', NOW)['categoryHealth']['water']
        self.assertEqual(health['state'], 'partial')
        self.assertEqual(health['pendingReview'], 2)
    def test_different_chat_is_rejected_atomically(self):
        invalid = message(2, 2000)
        invalid.chat_id = -987
        result = self.collect([[message(1), invalid]])
        self.assertEqual(result['errorCode'], 'FORMAT_ERROR')
        self.assertEqual(self.store.posts('test'), [])
    def test_missing_optional_chat_id_uses_verified_request_context(self):
        post = message(1)
        post.chat_id = None
        self.assertEqual(self.collect([[post], [post], []])['state'], 'read')
        self.assertEqual(self.store.posts('test')[0]['channelBinding'], 'verified_history_request')
        self.assertEqual(self.store.posts('test')[0]['channel_id'], -123)
    def test_mismatched_public_identity_is_rejected_before_history(self):
        client = Fake([])
        async def wrong(ident):
            return Obj(id=-999, type='CHANNEL', access='PUBLIC')
        client.get_chat = wrong
        result = asyncio.run(collect_channel(self.store, client, 'test', NOW))
        self.assertEqual(result['errorCode'], 'IDENTITY_ERROR')
        self.assertEqual(client.requests, [])
    def test_disabled_source_never_requests_network(self):
        store = Store(':memory:', [dict(SOURCE, enabled=False)])
        client = Fake([])
        self.assertEqual(asyncio.run(collect_all(store, client, NOW)), [])
        self.assertEqual(client.requests, [])
        store.db.close()
    def test_last_success_is_not_replaced_by_failure_attempt(self):
        self.collect([[]])
        later = '2026-11-10T11:00:00+03:00'
        self.store.failure('test', later, 'TIMEOUT')
        data = snapshot(self.store, 'test-city', later)
        self.assertEqual(data['sources'][0]['lastAttemptAt'], later)
        self.assertEqual(millis(data['sources'][0]['lastSuccessAt']), millis(NOW))
        self.assertEqual(data['categoryHealth']['water']['state'], 'unavailable')
    def test_unknown_category_and_municipality_never_show_read(self):
        self.collect([[]])
        data = snapshot(self.store, 'test-city', NOW)
        self.assertEqual(data['categoryHealth']['mchs']['state'], 'unconfigured')
        self.assertEqual(snapshot(self.store, 'other-city', NOW)['categoryHealth']['water']['state'], 'unconfigured')
    def test_gap_survives_a_later_connection_error(self):
        self.collect([[message(1)], TimeoutError()])
        self.store.failure('test', NOW, 'UNAVAILABLE')
        self.assertTrue(snapshot(self.store, 'test-city', NOW)['sources'][0]['historyGap'])
    def test_error_in_one_channel_does_not_stop_other_channel(self):
        second = dict(SOURCE, id='other', chat_id=-456)
        store = Store(':memory:', [SOURCE, second])
        class Two(Fake):
            async def get_chat(self, ident):
                if ident == -123:
                    raise RuntimeError('do-not-leak')
                return await super().get_chat(ident)
        result = asyncio.run(collect_all(store, Two([[]]), NOW))
        self.assertEqual([x['state'] for x in result], ['unavailable', 'read'])
        self.assertNotIn('do-not-leak', str(result))
        store.db.close()
    def test_downtime_longer_than_lookback_is_not_skipped(self):
        import json
        old = millis(NOW) - int(timedelta(days=30).total_seconds() * 1000)
        self.store.db.execute('INSERT INTO checkpoints VALUES(?,?)', ('test', json.dumps({'throughMs': old})))
        self.store.db.commit()
        self.collect([[message(1)]], max_pages=1)
        cutoff = self.store.db.execute('SELECT cutoff_ms FROM scans WHERE channel=?', ('test',)).fetchone()[0]
        self.assertEqual(cutoff, old - int(timedelta(hours=24).total_seconds() * 1000))
    def test_completed_old_scan_does_not_make_stale_snapshot_fresh(self):
        self.collect([[message(1)]], max_pages=1)
        later = '2026-11-11T10:00:00+03:00'
        result = asyncio.run(collect_channel(self.store, Fake([[message(1)], []]), 'test', later))
        self.assertEqual(result['state'], 'read')
        self.assertEqual(snapshot(self.store, 'test-city', later)['categoryHealth']['water']['state'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
