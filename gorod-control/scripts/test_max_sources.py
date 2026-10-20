import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from urllib.error import HTTPError
from max_sources import collect, parse_messages

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)
ENV = {'MAX_BOT_TOKEN': 'test-secret-never-publish', 'MAX_CITY_CHAT_ID': '-123'}


def message(chat=-123, url='https://max.ru/shakhtygorod/post1'):
    return {'recipient': {'chat_id': chat}, 'timestamp': int(NOW.timestamp()*1000),
            'body': {'mid': 'mid.post1', 'text': 'Объявление о работах'}, 'url': url}


class MaxTests(unittest.TestCase):
    def test_missing_access_does_not_claim_check_or_call_network(self):
        opener = Mock()
        posts, states = collect(NOW, {}, opener)
        self.assertEqual(posts, [])
        self.assertTrue(all(s['status']=='not_configured' and 'checkedAt' not in s for s in states))
        opener.assert_not_called()

    def test_credentials_only_in_header_and_empty_valid_feed_is_read(self):
        opener = Mock(return_value=io.BytesIO(b'{"messages":[]}'))
        posts, states = collect(NOW, ENV, opener)
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), ENV['MAX_BOT_TOKEN'])
        self.assertNotIn(ENV['MAX_BOT_TOKEN'], request.full_url)
        self.assertNotIn(ENV['MAX_BOT_TOKEN'], json.dumps(states))
        self.assertEqual(states[0]['readStatus'], 'ok')
        self.assertEqual(states[0]['posts'], 0)
        self.assertEqual(posts, [])

    def test_permission_denied_is_not_success(self):
        opener = Mock(side_effect=HTTPError('https://platform-api2.max.ru/messages', 403, 'denied', {}, None))
        _, states = collect(NOW, ENV, opener)
        self.assertEqual(states[0]['status'], 'error')
        self.assertEqual(states[0]['httpStatus'], 403)

    def test_wrong_channel_rejected_and_bad_public_link_not_used(self):
        channel = dict(id='max_city', chat_id='-123', name='Администрация',
                       slug='shakhtygorod', url='https://max.ru/shakhtygorod')
        with self.assertRaises(ValueError):
            parse_messages({'messages':[message(chat=-124)]}, channel, NOW)
        posts = parse_messages({'messages':[message(url='https://bad.example/post')]}, channel, NOW)
        self.assertEqual(posts[0]['url'], channel['url'])
        self.assertEqual(posts[0]['publishedAt'], NOW.isoformat())

    def test_invalid_json_and_network_details_never_leak_token(self):
        opener = Mock(side_effect=RuntimeError(ENV['MAX_BOT_TOKEN']))
        _, states = collect(NOW, ENV, opener)
        self.assertNotIn(ENV['MAX_BOT_TOKEN'], json.dumps(states))
        self.assertEqual(states[0]['status'], 'error')


if __name__ == '__main__':
    unittest.main()
