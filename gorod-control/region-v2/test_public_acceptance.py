"""No-current-incidents must not become a false outage of the live build check."""
import io,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from verify_public_endpoint import verify,URL

class Response(io.BytesIO):
    status=200
    url=URL

class PublicAcceptanceTests(unittest.TestCase):
    def test_empty_live_feed_and_historical_fixture_are_kept_distinct(self):
        live={'regionId':'RU-ROS','mode':'max-only','dataMode':'production',
            'generatedAt':datetime.now(timezone.utc).isoformat(),'events':[],'pendingPublicationCount':0}
        with tempfile.TemporaryDirectory() as folder,patch('verify_public_endpoint.urlopen',return_value=Response(json.dumps(live).encode())),patch('builtins.print'):
            output=Path(folder)/'qa.json';report=Path(folder)/'report.json';verify(output,report)
            r=json.loads(report.read_text());qa=json.loads(output.read_text())
            self.assertEqual(r['eventsByCategory'],{});self.assertEqual(r['markers'],0)
            self.assertTrue(qa['qaSnapshotAt']);self.assertTrue(qa['verificationMode'])
            self.assertEqual({e['category'] for e in qa['events']},{'water','power','mchs'})
