import importlib.util
from pathlib import Path
from datetime import datetime, timezone
import unittest
from secondary_water import feed_messages, split_notices
from rss_water import feed_messages as mirror_messages
from xml.sax.saxutils import escape
spec=importlib.util.spec_from_file_location('verified_water',Path(__file__).resolve().parents[1]/'direct-v09/water_verified.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
NOW=datetime(2026,10,20,13,tzinfo=timezone.utc)
NOTICE='''В Шахтах 20 октября с 9.30 аварийно-ремонтные работы по адресу: ул. Тестовая, д. 47 снижено давление.
Нестабильное водоснабжение по адресам:
ул Тестовая
пер Проверочный
Ориентировочное время завершения работ в 18-00 час. 20.10.2026.
Подвоз воды по заявкам.'''
FIRST='''В Шахтах аварийно-ремонтные работы с 9.30 в направлении улиц:
Неуточнённая
Рыночный
Ориентировочное время окончания работ – 18.00, 20 октября.'''
def rss(text=NOTICE,title='Где в Шахтах отключили воду 20 октября',url='https://kvu.su/utilities/123-test.html',author='Редакция'):
    return ('<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><title>'+escape(title)+'</title><link>'+url+'</link><pubDate>Tue, 20 Oct 2026 10:22:07 +0300</pubDate><dc:creator>'+author+'</dc:creator><content:encoded>'+escape(''.join('<p>'+escape(x)+'</p>' for x in text.splitlines()))+'</content:encoded></item></channel></rss>').encode()
class SecondaryWaterTests(unittest.TestCase):
    def test_two_outages_do_not_mix_addresses(self):
        posts=feed_messages(rss(FIRST+'\n'+NOTICE))
        self.assertEqual(len(posts),2)
        events=v.build_feed(posts,NOW)['events']
        self.assertEqual(events[0]['affected'],[])
        self.assertTrue(events[0]['requiresReview'])
        self.assertEqual(len(events[1]['affected']),2)
        self.assertEqual(events[1]['workSite'],'ул тестовая|47')
        self.assertEqual(events[1]['end'],'2026-10-20T18:00:00+03:00')
    def test_exact_municipal_attribution_without_document(self):
        posts=mirror_messages(rss(url='https://news-don.ru/society/test.html',author='Администрация города Шахты'),'news-don.ru')
        self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]['origin'],'municipal_repost')
        self.assertIsNone(posts[0]['officialUrl'])
        self.assertEqual(mirror_messages(rss(url='https://news-don.ru/society/test.html'),'news-don.ru'),[])
    def test_dedup_preserves_both_evidence_links(self):
        posts=feed_messages(rss())+mirror_messages(rss(url='https://news-don.ru/society/test.html',author='Администрация города Шахты'),'news-don.ru')
        result=v.build_feed(posts,NOW)
        self.assertEqual(len(result['events']),1)
        self.assertEqual(len(result['events'][0]['evidence']),2)
        self.assertEqual(result['events'][0]['sourceId'],'repost_don')
        posts[1]['text']=NOTICE.replace('18-00','19-00')
        self.assertEqual(len(v.build_feed(posts,NOW)['events']),2)
    def test_colon_in_time_before_address_heading(self):
        text=NOTICE.replace('с 9.30','с 9:30').replace('Нестабильное водоснабжение по адресам:', 'С 9:30 работают в следующих направлениях:')
        self.assertEqual(v.extract_areas(text)['unmappedAreaText'],[])
    def test_not_restored_at_estimated_end(self):
        posts=feed_messages(rss())
        result=v.build_feed(posts,NOW.replace(hour=20))
        self.assertEqual(result['events'][0]['status'],'unconfirmed')
        self.assertEqual(v.build_feed(posts,NOW.replace(day=22))['events'],[])
    def test_rejects_general_article_other_city_wrong_domain_and_html(self):
        self.assertEqual(feed_messages(rss(title='Жители Шахт год живут без воды')),[])
        self.assertEqual(feed_messages(rss(title='В Новошахтинске отключили воду')),[])
        self.assertEqual(feed_messages(rss(url='https://kvu.su.evil.test/utilities/123')),[])
        with self.assertRaises(ValueError):feed_messages(b'<html></html>')
if __name__=='__main__':unittest.main()
