import gzip,json,tempfile,unittest
from pathlib import Path
from offline_geography import load_offline_points,valid_street_geometry,NAME
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

    def test_path_validation_rejects_swapped_outside_and_oversized_lines(self):
        import copy
        good={'streetGeometryVerified':True,'streetGeometry':{'type':'MultiLineString','coordinates':[[[40.21,47.70],[40.22,47.71]],[[40.24,47.72],[40.25,47.73]]]}}
        self.assertTrue(valid_street_geometry(good))
        bad=copy.deepcopy(good);bad['streetGeometry']['coordinates'][0][0]=[47.70,40.21]
        self.assertFalse(valid_street_geometry(bad))
        bad=copy.deepcopy(good);bad['streetGeometry']['coordinates']=[[[40.21,47.70]]*4097]
        self.assertFalse(valid_street_geometry(bad))
        bad=copy.deepcopy(good);bad['streetGeometryVerified']=False
        self.assertFalse(valid_street_geometry(bad))

    def test_all_real_water_pressure_streets_have_verified_disconnected_safe_paths(self):
        from parse_publications import Templates
        index=load_index(ROOT/'gar-rostov-20261106.json.gz');points=load_offline_points(ROOT/NAME,index)
        post=json.loads((ROOT/'testdata/water-pressure-20261113.json').read_text())
        plan=Templates(index).propose(post,{'categories':['water']})
        self.assertEqual(len(plan['addresses']),9)
        self.assertTrue(all(valid_street_geometry(points[a['id']]) for a in plan['addresses']))
