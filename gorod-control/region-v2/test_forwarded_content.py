import json
from types import SimpleNamespace as O
import unittest
from collector import envelope,millis
from test_collector import message,SOURCE,NOW

class ForwardedContentTests(unittest.TestCase):
    def test_empty_wrapper_keeps_embedded_public_text_but_not_private_origin(self):
        p=message(1);p.text=''
        origin=message(2,2000);origin.text='Вода отключена: г. Батайск, ул. Ленина'
        p.link=O(type='FORWARD',message=origin,chat_id=991,chat_access_type='PRIVATE',
                 chat_name='PRIVATE_NAME',chat_link='PRIVATE_URL')
        r=envelope(p,SOURCE,millis(NOW))
        self.assertTrue(r['forwarded']);self.assertTrue(r['requiresReview'])
        self.assertEqual(r['linkedContent'][0]['text'],origin.text)
        self.assertNotIn('PRIVATE',json.dumps(r))
        self.assertNotIn('publicOriginChatId',r['linkedContent'][0])
    def test_reply_is_not_a_forwarded_incident(self):
        p=message(1);p.text='Восстановлено'
        p.link=O(type='REPLY',message=message(2,2000),chat_id=-123)
        r=envelope(p,SOURCE,millis(NOW))
        self.assertFalse(r['forwarded']);self.assertEqual(r['text'],'Восстановлено')
        self.assertEqual(r['linkedContent'][0]['kind'],'REPLY')
    def test_circular_forward_is_bounded(self):
        p=message(1);p.link=O(type='FORWARD',message=p,chat_id=-123)
        self.assertEqual(envelope(p,SOURCE,millis(NOW))['linkedContent'],[])
