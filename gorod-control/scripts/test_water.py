import sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collect_water import parse_html,parse_affected,classify,feed,schedule,canonical_road,restoration_covers

class OfficialWaterTests(unittest.TestCase):
    def test_telegram_format(self):
        html='<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="shakhtinskiy/887"><div class="tgme_widget_message_text js-message_text" dir="auto">⚠️ Отключение воды<br/>🗺️ Адреса:<br/>ул. Советская 231<br/>ул. Советская 233<br/>пер. Донской 78<br/>ℹ️ Подробности</div><a><time datetime="2026-07-31T13:28:00+00:00">...</time></a></div></div>'
        msgs=parse_html(html)
        self.assertEqual(len(msgs),1)
        areas=parse_affected(msgs[0]['text'])
        self.assertEqual(areas[0]['houses'],['231','233'])
        self.assertEqual(areas[1]['houses'],['78'])
    def test_reality_style(self):
        text='⚠️ Снижение давления\n🔧 Причина\nРемонт у дома 45\n🗺️ Адреса:\n▫️ ул. Орджоникидзе\n▫️ пр-кт Карла Маркса\n▫️ ул. Чернышевского\nℹ️ Подробности\nОжидаем восстановление'
        areas=parse_affected(text)
        self.assertEqual(len(areas),3)
        self.assertTrue(all(not a['houses'] for a in areas))
    def test_history_not_active(self):
        old=(datetime.now(timezone.utc)-timedelta(days=9)).isoformat()
        post={'id':'shakhtinskiy/10','publishedAt':old,'text':'⚠️ Отключение воды\n🗺️ Адреса:\nул. Советская 233','url':'https://t.me/shakhtinskiy/10'}
        data=feed([post])
        self.assertEqual(len(data['events']),0)
        self.assertEqual(data['recent'][0]['id'],'shakhtinskiy/10')
    def test_water_restored(self):
        now=datetime.now(timezone.utc)
        a={'id':'shakhtinskiy/11','publishedAt':(now-timedelta(minutes=50)).isoformat(),'text':'⚠️ Отключение воды\n🗺️ Адреса:\nул. Советская 233','url':'https://t.me/shakhtinskiy/11'}
        b={'id':'shakhtinskiy/12','publishedAt':(now-timedelta(minutes=10)).isoformat(),'text':'⚠️ Работы завершены\nВодоснабжение восстановлено\n🗺️ Адреса:\nул. Советская 233','url':'https://t.me/shakhtinskiy/12'}
        self.assertEqual(feed([a,b])['events'],[])
    def test_unspecified_area_not_inferred(self):
        self.assertEqual(parse_affected('Ремонт по адресу: ул. Советская 233'),[])
        self.assertEqual(classify('⚠️ Плановое отключение воды'),'planned')

    def test_future_planned_city_message(self):
        published=datetime(2026,10,17,12,0,tzinfo=timezone.utc)
        text='31 октября с 8.00 до 12.00 1 ноября будет снижено давление холодного водоснабжения в направлении:\n✔️ пос. Петровка;\n✔️ ул. Смидовича;\n✔️ пер. Шишкина;'
        self.assertEqual(classify(text),'planned')
        areas=parse_affected(text)
        self.assertEqual([x['street'] for x in areas],['пос. Петровка','ул. Смидовича','пер. Шишкина'])
        start,end=schedule(text,published,'planned')
        self.assertEqual(start,'2026-10-31T08:00:00+03:00')
        self.assertEqual(end,'2026-11-01T12:00:00+03:00')


    def test_road_type_and_restoration_safety(self):
        self.assertNotEqual(canonical_road('ул. Шишкина'),canonical_road('пер. Шишкина'))
        self.assertEqual(canonical_road('ул. Советская'),canonical_road('улица Советская'))
        self.assertEqual(canonical_road('проспект Красной Армии'),canonical_road('пр-кт Красной Армии'))
        self.assertFalse(restoration_covers(
            [{'street':'ул. Советская','houses':['11','13']}],
            [{'street':'ул. Советская','houses':['15']}]))
        self.assertFalse(restoration_covers(
            [{'street':'ул. Шишкина','houses':[]}],
            [{'street':'пер. Шишкина','houses':[]}]))
        self.assertFalse(restoration_covers(
            [{'street':'ул. Советская','houses':[]},{'street':'пер. Донской','houses':[]}],
            [{'street':'ул. Советская','houses':[]}]))
        self.assertTrue(restoration_covers(
            [{'street':'ул. Советская','houses':['11','13']}],
            [{'street':'улица Советская','houses':['11','13','15']}]))

    def test_new_water_incident_not_closed_by_neighbor_repairs(self):
        now=datetime.now(timezone.utc)
        def record(postid,minutes,text):
            return {'id':f'shakhtinskiy/{postid}',
              'publishedAt':(now-timedelta(minutes=minutes)).isoformat(),
              'text':text,'url':f'https://t.me/shakhtinskiy/{postid}'}
        active=record(91,40,'⚠️ Аварийное отключение воды\n🗺️ Адреса:\nул. Советская 11\nул. Советская 13')
        unrelated=record(92,5,'⚠️ Работы завершены\nВодоснабжение восстановлено\n🗺️ Адреса:\nул. Советская 15')
        self.assertEqual(len(feed([active,unrelated],now)['events']),1)
        restored=record(93,2,'⚠️ Работы завершены\nВодоснабжение восстановлено\n🗺️ Адреса:\nул. Советская 11\nул. Советская 13')
        self.assertEqual(len(feed([active,unrelated,restored],now)['events']),0)

if __name__=='__main__':unittest.main()
