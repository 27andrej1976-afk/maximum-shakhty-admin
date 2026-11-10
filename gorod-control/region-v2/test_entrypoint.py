import asyncio
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from core import Store
from run_collector import run
from test_collector import SOURCE, NOW


class EntrypointTests(unittest.TestCase):
    def test_missing_session_publishes_error_and_preserves_cached_posts(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'registry.json').write_text(json.dumps({'channels': [SOURCE]}))
            state = Store(root / 'public-posts.sqlite', [SOURCE])
            state.ingest('test', [{'id': '1', 'channel_id': -123, 'publishedAt': NOW}], 'saved', NOW)
            state.db.close()
            args = SimpleNamespace(registry=root / 'registry.json', state_dir=root,
                session_dir=root / 'missing', health_output=root / 'health.json',
                municipality='test-city', max_pages=2)
            asyncio.run(run(args))
            health = json.loads((root / 'health.json').read_text())
            self.assertEqual(health['sources'][0]['errorCode'], 'AUTH_REQUIRED')
            self.assertEqual(health['categoryHealth']['water']['state'], 'unavailable')
            state = Store(root / 'public-posts.sqlite', [SOURCE])
            self.assertEqual(len(state.posts('test')), 1)
            self.assertEqual(state.checkpoint('test'), 'saved')
            state.db.close()
    def test_collector_can_export_client_feed_even_without_session(self):
        from test_events import CATALOG
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'registry.json').write_text(json.dumps({'channels': [SOURCE]}))
            (root / 'catalog.json').write_text(json.dumps(CATALOG))
            args = SimpleNamespace(registry=root / 'registry.json', state_dir=root,
                session_dir=root / 'missing', health_output=root / 'health.json',
                municipality='test-city', max_pages=2, catalog=root/'catalog.json',
                feed_output=root/'feed.json')
            asyncio.run(run(args))
            feed = json.loads((root/'feed.json').read_text())
            self.assertEqual(feed['mode'], 'max-only')
            self.assertEqual(feed['events'], [])
            self.assertEqual(feed['coverage'], 'partial')
            self.assertTrue(all(c['state'] == 'unconfigured'
                for c in feed['municipalities'][0]['health'].values()))
    def test_disabled_registry_outputs_unknown_without_sdk_or_session(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'registry.json').write_text(json.dumps({'channels': [dict(SOURCE, enabled=False)]}))
            args = SimpleNamespace(registry=root / 'registry.json', state_dir=root,
                session_dir=root / 'missing', health_output=root / 'health.json',
                municipality='test-city', max_pages=2)
            asyncio.run(run(args))
            health = json.loads((root / 'health.json').read_text())
            self.assertTrue(all(c['state'] == 'unconfigured' for c in health['categoryHealth'].values()))


if __name__ == '__main__':
    unittest.main()
