"""Regression coverage for cached failures blocking later public street markers."""
import io,json,unittest
from unittest.mock import patch
from geography import GeometryCache,verify_geometry

NOW='2026-11-12T14:00:00+00:00'
CITY={'id':'fixture-city','name':'Ростов-на-Дону'}

def address(i):
    return {'id':'fixture-street-'+str(i),'name':'Проверочная '+str(i),
        'label':'ул. Проверочная '+str(i),'municipalityId':CITY['id']}

def feature(a,city=CITY['name']):
    return {'features':[{'properties':{'countrycode':'RU','state':'Ростовская область',
        'city':city,'osm_key':'highway','name':'улица '+a['name'],'osm_id':123,'osm_type':'W'},
        'geometry':{'type':'Point','coordinates':[39.7,47.2]}}]}

class GeometryQueueTests(unittest.TestCase):
    def test_cached_failures_do_not_spend_new_request_budget_or_block_later_streets(self):
        g=GeometryCache(':memory:')
        try:
            with g.db:g.db.executemany('INSERT INTO geometry VALUES(?,?,NULL)',
                [(address(i)['id'],NOW) for i in range(4)])
            replies=[io.BytesIO(json.dumps(feature(address(i))).encode()) for i in (4,5)]
            with patch('geography.urllib.request.urlopen',side_effect=replies) as fetch:
                result=g.resolve_missing([address(i) for i in range(8)],{CITY['id']:CITY},NOW,request_budget=2)
                self.assertEqual(set(result),{address(4)['id'],address(5)['id']})
                self.assertEqual(fetch.call_count,2)
            with patch('geography.urllib.request.urlopen',side_effect=AssertionError('No new network request expected')):
                self.assertIsNone(g.resolve(address(0),CITY,NOW))
                self.assertTrue(g.resolve(address(4),CITY,NOW)['geometryVerified'])
            self.assertEqual(g.network_requests,2)
        finally:g.close()
    def test_same_street_in_other_city_and_invalid_coordinates_never_create_markers(self):
        a=address(1)
        self.assertIsNone(verify_geometry(feature(a,'Таганрог'),a,CITY))
        data=feature(a);data['features'][0]['geometry']['coordinates']=[999,47.2]
        self.assertIsNone(verify_geometry(data,a,CITY))
        self.assertEqual(verify_geometry(feature(a),a,CITY)['locationPrecision'],'street')
