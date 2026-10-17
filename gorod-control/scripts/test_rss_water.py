import unittest
from datetime import datetime,timezone,timedelta
from xml.sax.saxutils import escape
from rss_water import feed_messages, html_text
from collect_water import parse_affected, feed

SAMPLE='''<p><strong>Филиал "Шахтинский" сообщает:</strong></p>
<p>Снижение давления</p>
<p>Причина</p>
<p>В связи с проведением аварийно-ремонтных работ по адресу: пер. Шишкина д. 183А с 09-30 час. 17.10.2026</p>
<p>Адреса:</p><p>г Шахты, ул Юный Спартак</p><p>г Шахты, ул Федюнина</p>
<p>г Шахты, ул Кадровая</p><p>г Шахты, пер Шишкина</p>
<p>г Шахты, пр-кт Красной Армии</p>
<p>Подробности</p><p>Ориентировочное время завершения работ 18-00 час. 17.10.2026</p>
<p>Подробнее: <a href="https://rovodokanal.ru/emergency-alerts/1591">УРСВ</a></p>'''
def xml_article(content=SAMPLE,title='Филиал "Шахтинский" сообщает:',link='https://newsrostov.ru/society/2026/10/17/597903.html'):
    return ('''<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>'''
        +'<title>'+escape(title)+'</title><link>'+link+'</link>'
        +'<pubDate>Sat, 17 Oct 2026 10:00:48 +0300</pubDate>'
        +'<content:encoded><![CDATA['+content+']]></content:encoded>'
        +'</item></channel></rss>').encode()

class RssMirrorTests(unittest.TestCase):
    def test_preserves_notice_lines(self):
        s=html_text(SAMPLE)
        self.assertIn('Адреса:\n',s)
        self.assertIn('ул Юный Спартак\n',s)
        self.assertIn('пер Шишкина\n',s)
    def test_valid_official_reprint(self):
        x=feed_messages(xml_article(),'newsrostov.ru')
        self.assertEqual(len(x),1)
        self.assertEqual(x[0]['id'],'oursv/1591')
        self.assertEqual(x[0]['origin'],'verified_repost')
        self.assertTrue(x[0]['officialUrl'].endswith('/1591'))
    def test_rejects_nonofficial_mirror(self):
        self.assertEqual(feed_messages(xml_article(content=SAMPLE.replace('https://rovodokanal.ru/emergency-alerts/1591','https://untrusted.example.org/1591')),'newsrostov.ru'),[])
    def test_rejects_offtopic(self):
        self.assertEqual(feed_messages(xml_article(content='<p>Наш город проводит фестиваль в Шахтах</p><a href="https://rovodokanal.ru/emergency-alerts/1591">link</a>'),'newsrostov.ru'),[])
    def test_no_external_domains(self):
        self.assertEqual(feed_messages(xml_article(link='https://example.com/danger'),'newsrostov.ru'),[])

    def test_17_october_notice_in_live_feed(self):
        post=feed_messages(xml_article(),'newsrostov.ru')[0]
        impact=parse_affected(post['text'])
        self.assertEqual([i['street'] for i in impact],[
            'ул Юный Спартак','ул Федюнина','ул Кадровая','пер Шишкина','пр-кт Красной Армии'])
        before=feed([post],datetime(2026,10,17,12,0,tzinfo=timezone(timedelta(hours=3))))
        self.assertEqual(len(before['events']),1)
        event=before['events'][0]
        self.assertEqual(event['id'],'water-oursv-1591')
        self.assertEqual(event['start'],'2026-10-17T09:30:00+03:00')
        self.assertEqual(event['end'],'2026-10-17T18:00:00+03:00')
        self.assertEqual(event['status'],'active')
        after=feed([post],datetime(2026,10,17,20,0,tzinfo=timezone(timedelta(hours=3))))
        self.assertEqual(after['events'][0]['status'],'unconfirmed')
        old=feed([post],datetime(2026,10,19,20,0,tzinfo=timezone(timedelta(hours=3))))
        self.assertEqual(old['events'],[])

if __name__=='__main__':unittest.main()
