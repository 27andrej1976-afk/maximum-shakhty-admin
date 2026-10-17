import unittest
from datetime import datetime,timezone,timedelta
from xml.sax.saxutils import escape
from service_events import power_posts,affected_power,mchs_posts,_risky_mchs_scope

MSK=timezone(timedelta(hours=3))
NOW=datetime(2026,10,17,22,30,tzinfo=MSK)
POWER='''<p>г. Шахты, в 21:40 произошло технологическое нарушение в сети 10 кВ, что привело к частичному отключению потребителей в границах: ул. Ленина, ул. Красной Армии, пер. Донской.</p><p>Ориентировочное время восстановления электроснабжения в течение 3 часов.</p><p>Источник: Канал в МАКС "АО "Донэнерго" Отключения", репост Администрация города Шахты</p>'''
def rss(title,body,when='Sat, 17 Oct 2026 22:00:00 +0300',link='https://newsrostov.ru/society/2026/10/17/1.html',tag='content:encoded'):
    return ('<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:yandex="http://news.yandex.ru"><channel><item>'+
        '<title>'+escape(title)+'</title><link>'+link+'</link><pubDate>'+when+'</pubDate>'+
        '<'+tag+'><![CDATA['+body+']]></'+tag+'></item></channel></rss>').encode()
class ServiceTests(unittest.TestCase):
    def test_power_repost(self):
        data=rss('г. Шахты, технологическое нарушение в сети 10 кВ',POWER)
        parsed=power_posts(data,'newsrostov.ru',NOW)
        self.assertEqual(len(parsed),1)
        item=parsed[0]
        self.assertEqual(item['category'],'power')
        self.assertEqual(item['kind'],'emergency')
        self.assertEqual(item['origin'],'attributed_repost')
        self.assertEqual(len(item['affected']),3)
        self.assertEqual(item['affected'][2]['street'],'пер. Донской')
        self.assertEqual(item['start'],'2026-10-17T21:40:00+03:00')
        self.assertEqual(item['end'],'2026-10-18T00:40:00+03:00')
    def test_estimated_repair_is_not_resolved(self):
        from service_events import classify_power
        self.assertEqual(classify_power('Ориентировочное время восстановления электроснабжения в течение 3 часов. Технологическое нарушение.'),'emergency')
        self.assertEqual(classify_power('Электроснабжение восстановлено в 21:20.'),'resolved')
    def test_power_wrong_city_and_no_attribution(self):
        self.assertEqual(power_posts(rss('г. Азов, авария на электросетях',POWER.replace('г. Шахты','г. Азов').replace('Шахты','Азове')),'newsrostov.ru',NOW),[])
        self.assertEqual(power_posts(rss('г. Шахты, авария',POWER.replace('Источник: Канал в МАКС "АО "Донэнерго" Отключения", репост Администрация города Шахты','')),'newsrostov.ru',NOW),[])
        self.assertEqual(power_posts(rss('г. Шахты, авария',POWER,link='https://example.ru/unauthorized'),'newsrostov.ru',NOW),[])
    def test_power_address_list_strict(self):
        self.assertEqual(affected_power('В границах: ул. Мира, пер. Мира, просп. Победы.'),[
          {'street':'ул. Мира','houses':[]},
          {'street':'пер. Мира','houses':[]},
          {'street':'проспект Победы','houses':[]}])
        self.assertEqual(affected_power('Авария где-то в области. Другие населенные пункты.'),[])
    def test_mchs_forecast_for_shakhty(self):
        body='Оперативный ежедневный прогноз ЧС. Высокая пожароопасность (4 класс) в 41 МО: гг. Азов, Гуково, Волгодонск, Шахты, а также Багаевский и Каменский районы. Информация ФГБУ Северо-Кавказского УГМС.'
        xml=rss('Оперативный ежедневный прогноз ЧС на 18 октября 2026 года',body,
          link='https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/5844111',tag='yandex:full-text')
        alerts=mchs_posts(xml,NOW)
        self.assertEqual(len(alerts),1)
        self.assertEqual(alerts[0]['scope'],'city')
        self.assertEqual(alerts[0]['priority'],'info')
        self.assertEqual(alerts[0]['category'],'mchs')
        self.assertEqual(alerts[0]['end'],'2026-10-18T23:59:00+03:00')
    def test_mchs_different_districts_are_not_shakhty(self):
        body='Главное управление МЧС информирует: чрезвычайная пожароопасность (5 класс) в 3 муниципальных образованиях (Орловском, Зимовниковском, Дубовском районах). Прогнозируется возникновение ЧС и пожаров. Охраняйте свое здоровье.'
        xml=rss('Экстренное предупреждение о чрезвычайной пожароопасности от 17.10.2026',body,
          link='https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/5844000',tag='yandex:full-text')
        self.assertEqual(mchs_posts(xml,NOW),[])
    def test_regionwide_urgent_mchs_alert(self):
        body='Экстренное предупреждение МЧС: по всей территории Ростовской области ожидаются сильный ветер и очень опасные погодные явления, необходимо соблюдать меры предосторожности.'
        xml=rss('Экстренное предупреждение МЧС о сильном ветре',body,
          link='https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/5844001',tag='yandex:full-text')
        result=mchs_posts(xml,NOW)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['scope'],'region')
        self.assertEqual(result[0]['priority'],'high')
    def test_article_from_wrong_domain_skipped(self):
        body='Экстренное предупреждение. На всей территории Ростовской области сильный ветер ожидается на протяжении суток.'
        xml=rss('Экстренное предупреждение МЧС',body,link='https://bad.example/alert',tag='yandex:full-text')
        self.assertEqual(mchs_posts(xml,NOW),[])
if __name__=='__main__':unittest.main()
