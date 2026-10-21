import importlib.util
from pathlib import Path
from datetime import datetime,timezone
import unittest
spec=importlib.util.spec_from_file_location('verified_audit',Path(__file__).resolve().parents[1]/'direct-v09/water_verified.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class WaterHeadingTests(unittest.TestCase):
    def test_municipal_heading_and_duplicate_mirrors(self):
        text='''В Шахтах 21 октября с 9.30 снижено давление. Аварийно-ремонтные работы по адресу ул. Тестовая, д. 65.
С нестабильным водоснабжением адреса:
ул. Тестовая
пер. Проверочный
ул. Северная
Ориентировочное время завершения работ – 22.00, 21 октября.
Организован подвоз воды.'''
        posts=[dict(id='mirror/'+str(i),text=text,publishedAt='2026-10-21T10:20:00+03:00',origin='municipal_repost',sourceId=s,url=url) for i,s,url in [(1,'repost_don','https://news-don.ru/test'),(2,'repost_rostov','https://newsrostov.ru/test')]]
        result=v.build_feed(posts,datetime(2026,10,21,9,tzinfo=timezone.utc))
        self.assertEqual(len(result['events']),1)
        e=result['events'][0]
        self.assertEqual(len(e['affected']),3)
        self.assertFalse(e['requiresReview'])
        self.assertEqual(len(e['evidence']),2)
        self.assertEqual(e['end'],'2026-10-21T22:00:00+03:00')
    def test_work_site_is_not_affected_address_without_heading(self):
        area=v.extract_areas('В Шахтах аварийные работы по адресу ул. Тестовая, д. 65.')
        self.assertEqual(area['affected'],[])
if __name__=='__main__':unittest.main()
