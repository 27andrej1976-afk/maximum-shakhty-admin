import copy
import unittest
from push_dispatch import Dispatcher,dispatch

NOW='2026-11-13T10:00:00+00:00'
def feed(ids):
 return {'regionId':'RU-ROS','dataMode':'production','generatedAt':NOW,'events':[{'id':i,'category':'water','status':'active','publishedAt':NOW,'expiresAt':'2026-11-14T10:00:00+00:00','sourceHash':'a'*64,'addresses':[]} for i in ids]}
class PushDispatchTests(unittest.TestCase):
 def setUp(self):self.q=Dispatcher(':memory:');self.sent=[]
 def tearDown(self):self.q.close()
 def send(self,*args):self.sent.append(args)
 def test_initial_baseline_and_new_event_only_once_data_only(self):
  self.assertEqual(self.q.run(feed(['old']),NOW,self.send)['state'],'baseline');self.assertEqual(self.sent,[])
  self.q.run(feed(['old','new']),NOW,self.send);self.q.run(feed(['old','new']),NOW,self.send)
  self.assertEqual(len(self.sent),1);topic,payload=self.sent[0];self.assertEqual(topic,'don-water-v1');self.assertNotIn('notification',payload['message']);self.assertEqual(payload['message']['android']['ttl'],'300s');self.assertNotIn('lat',str(payload))
 def test_failures_retry_but_restored_or_expired_queue_is_not_sent(self):
  self.q.run(feed([]),NOW,self.send)
  def fail(*a):raise TimeoutError()
  self.assertEqual(self.q.run(feed(['a']),NOW,fail)['failed'],1)
  self.q.run(feed([]),NOW,self.send);self.assertEqual(self.sent,[])
 def test_unconfirmed_changed_historical_and_stale_not_sent(self):
  self.q.run(feed([]),NOW,self.send)
  for field,value in [('sourceChanged',True),('status','unconfirmed'),('requiresReview',True)]:
   f=feed(['a']);f['events'][0][field]=value;self.q.run(f,NOW,self.send)
  f=feed(['a']);f['verificationMode']=True;self.q.run(f,NOW,self.send)
  f=feed(['a']);f['generatedAt']='2026-11-13T09:00:00Z';self.q.run(f,NOW,self.send)
  self.assertEqual(self.sent,[])
 def test_no_configuration_never_accesses_network_or_secret(self):
  self.assertEqual(dispatch({},'/not/read','/not/read',NOW)['state'],'not_configured')
