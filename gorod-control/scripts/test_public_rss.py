import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from public_rss import fetch
class RssFetchTests(unittest.TestCase):
    def test_retry_timeout_once(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'<rss><channel/></rss>'
        with patch('public_rss.urlopen',side_effect=[TimeoutError(),response]) as get:
            self.assertEqual(fetch('https://example.org/rss'),b'<rss><channel/></rss>')
            self.assertEqual(get.call_count,2)
    def test_timeout_stops_after_second_attempt(self):
        with patch('public_rss.urlopen',side_effect=TimeoutError()) as get:
            with self.assertRaises(TimeoutError):fetch('https://example.org/rss')
            self.assertEqual(get.call_count,2)
    def test_no_retry_for_denied_or_invalid_content(self):
        with patch('public_rss.urlopen',side_effect=HTTPError('https://example.org',403,'denied',{},None)) as get:
            with self.assertRaises(HTTPError):fetch('https://example.org/rss')
            self.assertEqual(get.call_count,1)
        response=MagicMock();response.__enter__.return_value.read.return_value=b'<html/>'
        with patch('public_rss.urlopen',return_value=response) as get:
            with self.assertRaises(ValueError):fetch('https://example.org/rss')
            self.assertEqual(get.call_count,1)
if __name__=='__main__':unittest.main()
