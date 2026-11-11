import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from serve import server
from worker import configuration
from run_collector import atomic_json


class PublicBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.public = self.root/'public'
        self.public.mkdir()
        (self.public/'index.html').write_text('Regional interface')
        (self.root/'max-session.db').write_bytes(b'PRIVATE-SESSION')
        (self.public/'max-session.db').write_bytes(b'PRIVATE-SESSION')
        (self.public/'leaked.png').symlink_to(self.root/'max-session.db')
        atomic_json(self.public/'feed.json', {'events': []}, mode=0o644)
        self.http = server(self.public, port=0)
        self.thread = Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:'+str(self.http.server_port)

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_private_files_traversal_and_symlinks_are_not_served(self):
        for path in ['/max-session.db', '/%2e%2e/max-session.db', '/leaked.png', '/.env']:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.url+path)
            self.assertEqual(error.exception.code, 404)

    def test_feed_is_readable_by_separate_web_user_with_exact_android_origin(self):
        request = Request(self.url+'/feed.json', headers={'Origin':'https://appassets.androidplatform.net'})
        with urlopen(request) as response:
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://appassets.androidplatform.net')
            self.assertEqual(json.load(response), {'events': []})
        self.assertEqual((self.public/'feed.json').stat().st_mode & 0o777, 0o644)
        with urlopen(Request(self.url+'/feed.json', headers={'Origin':'https://unrelated.invalid'})) as response:
            self.assertIsNone(response.headers.get('Access-Control-Allow-Origin'))

    def test_post_cannot_overwrite_feed_and_health_is_not_incident_readiness(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url+'/feed.json', data=b'overwritten', method='POST'))
        self.assertEqual(error.exception.code, 405)
        with urlopen(self.url+'/healthz') as response:
            self.assertFalse(json.load(response)['incidentPipelineVerified'])
        self.assertEqual(json.loads((self.public/'feed.json').read_text()), {'events': []})

    def test_worker_refuses_disabled_registry_and_city_feed_before_account_access(self):
        registry = {'region':'RU-ROS','categories':['water','power','mchs'],'channels':[]}
        catalog = {'regionId':'RU-ROS','municipalities':[]}
        (self.root/'sources.json').write_text(json.dumps(registry))
        (self.root/'catalog.json').write_text(json.dumps(catalog))
        config = dict(registry=str(self.root/'sources.json'), catalog=str(self.root/'catalog.json'),
                      stateDir=str(self.root/'state'),sessionDir=str(self.root/'session'),
                      healthOutput=str(self.public/'health.json'),feedOutput=str(self.public/'feed.json'))
        path = self.root/'config.json'
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'Registry is disabled'):
            configuration(path)
        registry['channels']=[dict(id='different-name',url='https://max.ru/shakhtygorod',categories=['water'])]
        (self.root/'sources.json').write_text(json.dumps(registry))
        with self.assertRaisesRegex(ValueError, 'City administration'):
            configuration(path)


if __name__=='__main__':
    unittest.main()
