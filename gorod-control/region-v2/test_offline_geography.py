import gzip,json,tempfile,unittest
from pathlib import Path
from offline_geography import load_offline_points,NAME
from parse_publications import load_index

ROOT=Path(__file__).parent
class OfflineGeographyTests(unittest.TestCase):
    def test_all_reference_points_have_gar_ids_and_public_osm_boundary_evidence(self):
        index=load_index(ROOT/'gar-rostov-20261106.json.gz');points=load_offline_points(ROOT/NAME,index)
        self.assertEqual(len(points),19230)
        cities={s['municipalityId'] for s in index['streets'] if s['id'] in points}
        self.assertEqual(len(cities),1245)
        self.assertTrue(all(p['locationPrecision']=='street' for p in points.values()))
    def test_unknown_gar_id_is_rejected_and_absent_optional_catalogue_is_explicitly_empty(self):
        index=load_index(ROOT/'gar-rostov-20261106.json.gz')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'geo.gz';self.assertEqual(load_offline_points(p,index),{})
            data={'schemaVersion':1,'regionId':'RU-ROS','license':'ODbL-1.0','points':{'not-a-gar-street':{}}}
            p.write_bytes(gzip.compress(json.dumps(data).encode()))
            with self.assertRaisesRegex(ValueError,'Invalid offline street'):load_offline_points(p,index)
