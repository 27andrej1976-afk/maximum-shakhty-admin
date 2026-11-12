import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import sample_publications as sample

class FakeClient:
    def __init__(self, folder):
        self.folder = folder
        self.reads = []
    async def connect(self): pass
    async def close(self): pass
    async def get_chat(self, cid):
        titles={-69418948796459:'ГУП РО «УРСВ»',-72527316071728:'АО Донэнерго Отключения',
                -69127719422667:'Ростовводоканал',-69220795976413:'МЧС Ростовской области'}
        return NS(id=cid,type='CHANNEL',access='PUBLIC',title=titles[cid])
    async def fetch_history(self, *, chat_id, backward, interactive):
        assert backward==100 and interactive is False
        self.reads.append(chat_id)
        return [NS(id=1,time=1700000000000,chat_id=chat_id,text='Отключение',
                   type='CHANNEL',attaches=[],link=None,loginToken='NEVER_EXPORT',sender='PRIVATE_PROFILE')]

class PublicSamplesTests(unittest.TestCase):
    def test_only_four_public_channels_and_no_credentials_in_export(self):
        clients=[]
        def factory(folder):
            c=FakeClient(folder);clients.append(c);return c
        with patch.object(sample,'decode_session',return_value=b'session-private'):
            result=asyncio.run(sample.sample({'MAX_USER_SESSION_B64':'secret'},client_factory=factory))
        self.assertEqual(set(clients[0].reads),set(sample.SOURCE_IDS))
        self.assertEqual(len(result['channels']),4)
        self.assertNotIn('NEVER_EXPORT',json.dumps(result))
        self.assertNotIn('PRIVATE_PROFILE',json.dumps(result))
        self.assertFalse(Path(clients[0].folder).exists())
        self.assertFalse(result['completeHistory'])
    def test_private_candidate_never_reads_history(self):
        class Private(FakeClient):
            async def get_chat(self,cid):
                c=await super().get_chat(cid)
                if cid == -69127719422667:c.access='PRIVATE'
                return c
        clients=[]
        def factory(folder):
            c=Private(folder);clients.append(c);return c
        with patch.object(sample,'decode_session',return_value=b'session-private'):
            result=asyncio.run(sample.sample({'MAX_USER_SESSION_B64':'secret'},client_factory=factory))
        self.assertNotIn(-69127719422667,clients[0].reads)
        self.assertFalse(next(c for c in result['channels'] if c['id']=='rostovvodokanal-candidate')['readVerified'])
