"""Create synthetic QA data through the actual evidence/review/feed pipeline.

Never load this registry or data into production. It is always dataMode=test.
"""
import argparse
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from core import Store
from events import Ledger
from run_collector import atomic_json


def make(output, *, restore_first=False):
    now = datetime.now(timezone.utc)
    stamp = lambda h: (now + timedelta(hours=h)).isoformat()
    sources = [dict(id=key, url='https://max.ru/qa_example_'+key, chat_id=-(100+i),
        transport='max', identity_verified=True, enabled=True, categories=[key],
        municipalities=['fixture-a'], regionCoverageVerified=key=='mchs')
        for i,key in enumerate(['water','power','mchs'])]
    catalog = {'regionId':'RU-ROS','dataMode':'test','municipalities':[
        {'id':'fixture-a','name':'Тестовый город А','verified':True},
        {'id':'fixture-b','name':'Тестовый город Б','verified':True}], 'addresses':[
        {'id':'a1','municipalityId':'fixture-a','streetId':'fixture-street','label':'Условная улица, 1','lat':47.709,'lon':40.215,'geometryVerified':True,'verified':True},
        {'id':'a2','municipalityId':'fixture-a','streetId':'fixture-street','label':'Условная улица, 2','lat':47.712,'lon':40.219,'geometryVerified':True,'verified':True},
        {'id':'a3','municipalityId':'fixture-a','streetId':'fixture-power-street','label':'Условный переулок, 8','lat':47.707,'lon':40.211,'geometryVerified':True,'verified':True}]}
    with TemporaryDirectory() as folder:
        store = Store(folder+'/qa.sqlite',sources)
        ledger = Ledger(store,catalog)
        for source in sources:
            post = {'id':'1','channel_id':source['chat_id'],'publishedAt':stamp(-1),
                    'text':'ВЫМЫШЛЕННАЯ публикация для проверки интерфейса: '+source['id']}
            store.ingest(source['id'],[post],'qa',now.isoformat())
            source_hash=store.db.execute('SELECT hash FROM posts WHERE channel=? AND id=?',(source['id'],'1')).fetchone()[0]
            record={'reviewId':source['id']+'-r','sourceId':source['id'],'messageId':'1','sourceHash':source_hash,
                'category':source['id'],'type':'incident','eventId':source['id']+'-example',
                'municipalityId':'fixture-a','addressIds':['a1','a2'] if source['id']=='water' else ['a3'],
                'title':{'water':'ТЕСТ · Ограничение водоснабжения','power':'ТЕСТ · Работы на электросети','mchs':'ТЕСТ · Областное предупреждение МЧС'}[source['id']],
                'description':'Синтетический пример. Не является сообщением о реальном происшествии.',
                'start':stamp(-1),'end':stamp(3)}
            if source['id']=='mchs':record.update(scope='region',municipalityId=None,addressIds=[])
            ledger.apply([record],now.isoformat())
        store.ingest('water',[{'id':'2','channel_id':sources[0]['chat_id'],'publishedAt':stamp(-0.5),
            'text':'ТЕСТ · Сообщение с нераспознанным вложением','requiresReview':True,'attachmentCount':1}], 'qa2',now.isoformat())
        if restore_first:
            store.ingest('water',[{'id':'3','channel_id':sources[0]['chat_id'],'publishedAt':stamp(-0.1),
                'text':'ТЕСТ · Вода восстановлена на первом адресе'}], 'qa3',now.isoformat())
            source_hash=store.db.execute("SELECT hash FROM posts WHERE channel='water' AND id='3'").fetchone()[0]
            ledger.apply([dict(reviewId='restore-a1',sourceId='water',messageId='3',sourceHash=source_hash,
                category='water',type='restoration',targetEventId='water-example',municipalityId='fixture-a',
                addressIds=['a1'])],now.isoformat())
        store.failure('water',now.isoformat(),'TIMEOUT')
        atomic_json(output,ledger.feed(now.isoformat()))
        store.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--restore-first',action='store_true')
    a=p.parse_args();make(a.output,restore_first=a.restore_first)
