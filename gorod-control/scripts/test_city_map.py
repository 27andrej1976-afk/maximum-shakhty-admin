"""Regression tests for public affected-road geometry (no live service access)."""
import importlib.util
import math
import unittest
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/'map-v07'/'geometry.py'
spec=importlib.util.spec_from_file_location('city_geometry',FILE)
geo=importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)

class CityGeometryTests(unittest.TestCase):
    def test_road_type_is_not_lost(self):
        self.assertEqual(geo.key('ул Юный Спартак'),geo.key('улица Юный Спартак'))
        self.assertEqual(geo.key('переулок Шишкина'),geo.key('пер. Шишкина'))
        self.assertNotEqual(geo.key('улица Шишкина'),geo.key('переулок Шишкина'))
    def test_missing_road_type_not_guessed(self):
        self.assertIsNone(geo.key('Шишкина'))
        self.assertIsNone(geo.key(''))
    def test_real_way_geometry_is_preserved(self):
        raw={'id':10,'type':'way','tags':{'highway':'residential'},
             'geometry':[{'lat':47.73,'lon':40.22},{'lat':47.74,'lon':40.23}]}
        self.assertEqual(geo.shape(raw),{'osmId':10,'line':[[47.73,40.22],[47.74,40.23]]})
    def test_invalid_coordinates_cannot_form_a_pin(self):
        for lat,lon in [(0,0),(55.75,37.62),(float('nan'),40.2),(47.7,float('inf'))]:
            raw={'id':11,'type':'way','tags':{'highway':'residential'},
                 'geometry':[{'lat':lat,'lon':lon},{'lat':47.74,'lon':40.23}]}
            self.assertIsNone(geo.shape(raw))
    def test_forecast_and_point_are_not_street_geometry(self):
        self.assertIsNone(geo.shape({'id':12,'type':'relation','tags':{'boundary':'administrative'}}))
        self.assertIsNone(geo.shape({'id':13,'type':'node','lat':47.7,'lon':40.2}))

if __name__=='__main__':unittest.main()
