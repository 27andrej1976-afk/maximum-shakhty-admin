"""Synthetic transport/safety tests, not a claim of live DaData connectivity."""
import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from geography_dadata import verify_dadata,DadataGeometryCache,ENDPOINT

A={'id':'fixture-street','streetId':'fixture-street','municipalityId':'fixture-city','label':'Fixture street','name':'Fixture'}
C={'id':'fixture-city','name':'Fixture city'}
def reply(qc='2'):
    return {'suggestions':[{'data':{'country_iso_code':'RU','region_iso_code':'RU-ROS','street_fias_id':A['streetId'],
        'fias_id':A['streetId'],'city_fias_id':C['id'],'fias_level':'7','qc_geo':qc,'fias_actuality_state':'0',
        'geo_lat':'47.2','geo_lon':'39.7'}}]}

class DadataGeometryTests(unittest.TestCase):
    def test_city_centroid_wrong_city_and_wrong_gar_are_rejected(self):
        self.assertIsNone(verify_dadata(reply('4'),A,C))
        self.assertIsNone(verify_dadata(reply(),A,dict(C,id='other-city')))
        self.assertIsNone(verify_dadata(reply(),dict(A,streetId='other-street'),C))
        self.assertTrue(verify_dadata(reply(),A,C)['geometryVerified'])
    def test_only_gar_id_is_sent_to_fixed_endpoint_and_result_is_cached(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'token';p.write_text('synthetic-fixture-token');p.chmod(0o600)
            g=DadataGeometryCache(':memory:',p)
            try:
                with patch('geography_dadata.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(reply()).encode())) as fetch:
                    result=g.resolve(A,C,'2026-11-12T14:00:00+00:00')
                    self.assertTrue(result['geometryVerified'])
                    request=fetch.call_args.args[0]
                    self.assertEqual(request.full_url,ENDPOINT)
                    self.assertEqual(json.loads(request.data),{'query':A['streetId'],'count':1})
                    self.assertNotIn('synthetic-fixture-token',request.full_url)
                    self.assertEqual(g.resolve(A,C,'2026-11-12T14:01:00+00:00'),result)
                    self.assertEqual(fetch.call_count,1)
            finally:g.close()
