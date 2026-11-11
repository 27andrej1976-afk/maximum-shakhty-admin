import json
import unittest
from copy import deepcopy
from core import Store
from events import Ledger

NOW = '2026-11-10T12:00:00+03:00'
SOURCE = {'id': 'test', 'url': 'https://max.ru/fixture', 'chat_id': -123, 'transport': 'max',
          'identity_verified': True, 'enabled': True, 'categories': ['water', 'power', 'mchs'],
          'municipalities': ['city-a', 'city-b']}
CATALOG = {'regionId': 'RU-ROS', 'dataMode': 'test', 'municipalities': [
    {'id': 'city-a', 'name': 'Тестовый город А', 'verified': True},
    {'id': 'city-b', 'name': 'Тестовый город Б', 'verified': True}], 'addresses': [
    {'id': 'a1', 'municipalityId': 'city-a', 'streetId': 's1', 'label': 'Условная улица, 1', 'verified': True},
    {'id': 'a2', 'municipalityId': 'city-a', 'streetId': 's1', 'label': 'Условная улица, 2', 'verified': True},
    {'id': 'b1', 'municipalityId': 'city-b', 'streetId': 's1', 'label': 'Условная улица, 1', 'verified': True}]}


class EventTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:', [SOURCE])
        self.ledger = Ledger(self.store, CATALOG)
        self.post('1', '2026-11-10T08:00:00+03:00')
    def tearDown(self):
        self.store.db.close()
    def post(self, mid, stamp, text='Тестовое сообщение', **extra):
        self.store.ingest('test', [dict(id=mid, channel_id=-123, text=text, publishedAt=stamp, **extra)], 'cursor', NOW)
    def record(self, mid='1', **extra):
        row = self.store.db.execute('SELECT hash FROM posts WHERE channel=? AND id=?', ('test', mid)).fetchone()
        return dict({'reviewId': 'review-' + mid, 'sourceId': 'test', 'messageId': mid, 'sourceHash': row[0],
                     'category': 'water', 'type': 'incident', 'eventId': 'e-' + mid,
                     'municipalityId': 'city-a', 'addressIds': ['a1', 'a2'],
                     'title': 'Тестовое ограничение воды', 'start': '2026-11-10T08:00:00+03:00',
                     'end': '2026-11-10T09:00:00+03:00'}, **extra)
    def test_offline_source_does_not_remove_accepted_event(self):
        self.ledger.apply([self.record()], NOW)
        self.store.failure('test', NOW, 'TIMEOUT')
        feed = self.ledger.feed(NOW)
        self.assertEqual(len(feed['events']), 1)
        self.assertEqual(feed['municipalities'][0]['health']['water']['state'], 'unavailable')
    def test_review_requires_current_source_hash(self):
        record = self.record()
        self.post('1', '2026-11-10T08:00:00+03:00', text='Изменённое объявление')
        with self.assertRaises(ValueError):
            self.ledger.apply([record], NOW)
    def test_replay_is_idempotent(self):
        self.ledger.apply([self.record()], NOW)
        self.ledger.apply([self.record()], NOW)
        self.assertEqual(len(self.ledger.events(NOW)), 1)
    def test_review_batch_rolls_back_if_restoration_target_invalid(self):
        self.post('2', '2026-11-10T11:00:00+03:00')
        bad = self.record('2', type='restoration', targetEventId='not-found')
        with self.assertRaises(ValueError):
            self.ledger.apply([self.record(), bad], NOW)
        self.assertEqual(self.ledger.events(NOW), [])
    def test_streets_in_different_cities_do_not_match(self):
        with self.assertRaises(ValueError):
            self.ledger.apply([self.record(addressIds=['b1'])], NOW)
    def test_partial_restoration_removes_only_confirmed_address(self):
        self.ledger.apply([self.record()], NOW)
        self.post('2', '2026-11-10T11:00:00+03:00')
        self.ledger.apply([self.record('2', type='restoration', targetEventId='e-1', addressIds=['a1'])], NOW)
        event = self.ledger.events(NOW)[0]
        self.assertEqual(event['addressIds'], ['a2'])
        self.assertTrue(event['partialRestoration'])
    def test_full_restoration_removes_event_immediately(self):
        self.ledger.apply([self.record()], NOW)
        self.post('2', '2026-11-10T11:00:00+03:00')
        self.ledger.apply([self.record('2', type='restoration', targetEventId='e-1')], NOW)
        self.assertEqual(self.ledger.events(NOW), [])
    def test_old_restoration_cannot_close_new_incident(self):
        self.ledger.apply([self.record()], NOW)
        self.post('2', '2026-11-09T11:00:00+03:00')
        with self.assertRaises(ValueError):
            self.ledger.apply([self.record('2', type='restoration', targetEventId='e-1')], NOW)
        self.assertEqual(len(self.ledger.events(NOW)), 1)
    def test_excluded_gas_category_cannot_close_water(self):
        self.ledger.apply([self.record()], NOW)
        self.post('2', '2026-11-10T11:00:00+03:00')
        with self.assertRaises(ValueError):
            self.ledger.apply([self.record('2', type='restoration', targetEventId='e-1', category='gas')], NOW)
    def test_36_hours_boundary_for_each_utility_category(self):
        for category in ['water', 'power']:
            with self.subTest(category=category):
                store = Store(':memory:', [SOURCE])
                store.ingest('test', self.store.posts('test'), 'cursor', NOW)
                ledger = Ledger(store, CATALOG)
                ledger.apply([self.record(category=category)], NOW)
                self.assertEqual(len(ledger.events('2026-11-11T20:59:59+03:00')), 1)
                self.assertEqual(ledger.events('2026-11-11T21:00:00+03:00'), [])
                store.db.close()
    def test_mchs_expires_at_official_end_without_extra_36_hours(self):
        self.ledger.apply([self.record(category='mchs', end='2026-11-10T14:00:00+03:00')], NOW)
        self.assertEqual(len(self.ledger.events('2026-11-10T13:59:59+03:00')), 1)
        self.assertEqual(self.ledger.events('2026-11-10T14:00:00+03:00'), [])
    def test_mchs_without_expiry_stays_pending(self):
        with self.assertRaises(ValueError):
            self.ledger.apply([self.record(category='mchs', end=None)], NOW)
        self.assertEqual(len(self.ledger.pending()), 1)
    def test_reloading_post_does_not_extend_expiry(self):
        self.ledger.apply([self.record()], NOW)
        first = self.ledger.events(NOW)[0]['expiresAt']
        self.post('1', '2026-11-10T08:00:00+03:00')
        self.assertEqual(self.ledger.events(NOW)[0]['expiresAt'], first)
    def test_edited_source_preserves_event_but_flags_it_for_review(self):
        self.ledger.apply([self.record()], NOW)
        self.post('1', '2026-11-10T08:00:00+03:00', text='Текст исправлен')
        event = self.ledger.events(NOW)[0]
        self.assertTrue(event['sourceChanged'])
        self.assertEqual(event['status'], 'unconfirmed')
        self.assertEqual(len(self.ledger.pending()), 1)
    def test_reviewed_attachment_no_longer_keeps_health_pending(self):
        self.post('1', '2026-11-10T08:00:00+03:00', requiresReview=True)
        self.ledger.apply([self.record()], NOW)
        health = self.ledger.feed(NOW)['municipalities'][0]['health']['water']
        self.assertEqual(health['pendingReview'], 0)
        self.assertEqual(health['state'], 'read')
    def test_unknown_publication_is_visible_pending_not_an_incident(self):
        feed = self.ledger.feed(NOW)
        self.assertEqual(feed['events'], [])
        self.assertEqual(len(feed['pendingPublications']), 1)
        self.assertEqual(feed['municipalities'][0]['health']['water']['state'], 'partial')
    def test_region_warning_has_no_fake_point_and_is_visible_without_city(self):
        self.store.channels['test']['regionCoverageVerified'] = True
        record = self.record(category='mchs', scope='region', municipalityId=None,
                             addressIds=[], end='2026-11-10T14:00:00+03:00')
        self.ledger.apply([record], NOW)
        event = self.ledger.events(NOW)[0]
        self.assertEqual(event['scope'], 'region')
        self.assertEqual(event['addresses'], [])
    def test_region_warning_requires_verified_region_scope(self):
        with self.assertRaises(ValueError):
            self.ledger.apply([self.record(category='mchs', scope='region', municipalityId=None,
                addressIds=[], end='2026-11-10T14:00:00+03:00')], NOW)
    def test_explicit_region_cancellation_closes_warning(self):
        self.store.channels['test']['regionCoverageVerified'] = True
        self.ledger.apply([self.record(category='mchs', scope='region', municipalityId=None,
            addressIds=[], end='2026-11-10T14:00:00+03:00')], NOW)
        self.post('2', '2026-11-10T11:00:00+03:00')
        self.ledger.apply([self.record('2', type='cancellation', category='mchs', scope='region',
            municipalityId=None, addressIds=[], targetEventId='e-1')], NOW)
        self.assertEqual(self.ledger.events(NOW), [])
    def test_no_arbitrary_extra_fields_in_reviewed_records(self):
        self.ledger.apply([self.record(token='private-token')], NOW)
        self.assertNotIn('private-token', json.dumps(self.ledger.feed(NOW)))


if __name__ == '__main__':
    unittest.main()
