import asyncio,tempfile,unittest,zlib,base64
from types import SimpleNamespace as Obj
from pathlib import Path
from datetime import datetime,timezone
from max_user_reader import CHANNELS,public_post,validate_channel,read_channels,encode_session,decode_session,collect_session
class ReaderTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime.now(timezone.utc);self.c=CHANNELS[0]
  self.m=Obj(id=123,chat_id=self.c['chat_id'],text='Снижение давления',time=int(self.now.timestamp()*1000),type='TEXT',link=None)
 def test_only_public_whitelisted_channels(self):
  chat=Obj(id=self.c['chat_id'],type='CHANNEL',access='PUBLIC',title=self.c['name']);validate_channel(chat,self.c)
  chat.type='DIALOG'
  with self.assertRaises(ValueError):validate_channel(chat,self.c)
 def test_mismatched_chat_rejected(self):
  self.m.chat_id=12345
  with self.assertRaises(ValueError):public_post(self.m,self.c,self.now)
 def test_no_secret_or_private_profile_in_public_payload(self):
  self.m.token='must-not-leak';self.m.sender=100
  p=public_post(self.m,self.c,self.now)
  self.assertEqual(p['sourceId'],'max_city');self.assertNotIn('token',p);self.assertNotIn('sender',p)
  self.assertEqual(p['url'],'https://max.ru/shakhtygorod')
 def test_future_and_forwarded_posts_excluded(self):
  self.m.link=Obj(type='FORWARD');self.assertIsNone(public_post(self.m,self.c,self.now))
  self.m.link=None;self.m.time+=86400000;self.assertIsNone(public_post(self.m,self.c,self.now))
 def test_session_transport_size_limits(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.db';p.write_bytes(b'SQLite format 3\x00'+b'a'*1000)
   self.assertEqual(decode_session(encode_session(p)),p.read_bytes())
  bomb=base64.b64encode(zlib.compress(b'SQLite format 3\x00'+b'a'*1000001)).decode()
  with self.assertRaises(ValueError):decode_session(bomb)
 def test_invalid_secret_is_redacted(self):
  posts,states=collect_session(self.now,{'MAX_USER_SESSION_B64':'secret-invalid-value'})
  self.assertEqual(posts,[]);self.assertEqual(len(states),2);self.assertNotIn('secret-invalid-value',str(states))
 def test_reader_requests_only_allowlist_and_never_mutates(self):
  calls=[]
  class Fake:
   async def get_chat(s,id):
    calls.append(id);c=next(x for x in CHANNELS if x['chat_id']==id)
    return Obj(id=id,type='CHANNEL',access='PUBLIC',title=c['name'])
   async def fetch_history(s,**kw):
    calls.append(kw);return []
  posts,states=asyncio.run(read_channels(Fake(),self.now))
  self.assertEqual(posts,[]);self.assertTrue(all(s['status']=='ok' for s in states))
  self.assertEqual([x for x in calls if isinstance(x,int)],[c['chat_id'] for c in CHANNELS])
  self.assertTrue(all(x['interactive'] is False for x in calls if isinstance(x,dict)))
if __name__=='__main__':unittest.main()
