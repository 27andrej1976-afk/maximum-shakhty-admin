import asyncio
import base64
import json
import unittest
import zlib
from types import SimpleNamespace as Obj
from diagnose_max import diagnose, error_code, safe_api_details, REGIONAL_CANDIDATES
from max_user_reader import CHANNELS


class DiagnosticTests(unittest.TestCase):
    def test_missing_session_does_not_access_network(self):
        def factory(folder):
            self.fail('No session must not construct client')
        self.assertEqual(asyncio.run(diagnose({}, client_factory=factory))['errorCode'], 'NOT_CONFIGURED')
    def test_connection_error_redacts_all_exception_details(self):
        value = base64.b64encode(zlib.compress(b'SQLite format 3\x00'+b'a'*1000)).decode()
        class Fake:
            def __init__(self, folder):
                pass
            async def connect(self):
                raise TimeoutError('private-token-and-account-data')
            async def close(self):
                pass
        report = asyncio.run(diagnose({'MAX_USER_SESSION_B64': value}, client_factory=Fake))
        self.assertEqual(report['stage'], 'connect')
        self.assertEqual(report['errorCode'], 'TIMEOUT')
        self.assertNotIn('private-token', json.dumps(report))
        self.assertNotIn(value, json.dumps(report))
    def test_known_login_rejection_uses_fixed_codes_only(self):
        ApiError = type('ApiError', (Exception,), {})
        error = ApiError('private-token')
        error.opcode = 19
        error.error = 'FAIL_LOGIN_TOKEN'
        error.message = 'private-account-data'
        self.assertEqual(error_code(error, 'connect'), 'AUTH_REQUIRED')
        details = safe_api_details(error)
        self.assertTrue(details['loginTokenRejected'])
        self.assertEqual(details['apiOperation'], 'LOGIN')
        self.assertNotIn('private', json.dumps(details))
    def test_handshake_error_does_not_claim_login_expired(self):
        ApiError = type('ApiError', (Exception,), {})
        error = ApiError('private-token')
        error.opcode = 6
        error.error = 'private-opaque-value'
        self.assertEqual(error_code(error, 'connect'), 'API_ERROR')
        self.assertFalse(safe_api_details(error)['loginTokenRejected'])
        self.assertEqual(safe_api_details(error)['apiOperation'], 'HANDSHAKE')
        self.assertNotIn('private', json.dumps(safe_api_details(error)))
    def test_success_never_exposes_message_text_or_private_profile(self):
        value = base64.b64encode(zlib.compress(b'SQLite format 3\x00'+b'a'*1000)).decode()
        class Fake:
            def __init__(self, folder):
                pass
            async def connect(self):
                pass
            async def close(self):
                pass
            async def get_chat(self, chat_id):
                source = next(c for c in CHANNELS if c['chat_id'] == chat_id)
                return Obj(id=chat_id, type='CHANNEL', access='PUBLIC', title=source['name'])
            async def fetch_history(self, **kwargs):
                return [Obj(text='DO-NOT-PUBLISH-TEXT', sender='PRIVATE-PROFILE')]
        report = asyncio.run(diagnose({'MAX_USER_SESSION_B64': value}, client_factory=Fake))
        self.assertTrue(report['readVerified'])
        self.assertEqual(len(report['channels']), 3)
        self.assertNotIn('DO-NOT-PUBLISH-TEXT', json.dumps(report))
        self.assertNotIn('PRIVATE-PROFILE', json.dumps(report))

    def test_regional_discovery_reads_five_public_channels_without_certifying_publisher(self):
        value = base64.b64encode(zlib.compress(b'SQLite format 3\x00'+b'a'*1000)).decode()
        class Fake:
            def __init__(self, folder):
                self.sources = {c['chat_id']: c for c in CHANNELS + REGIONAL_CANDIDATES}
            async def connect(self): pass
            async def close(self): pass
            async def get_chat(self, chat_id):
                c = self.sources[chat_id]
                title = c['expected_titles'][0] if 'expected_titles' in c else c['name']
                return Obj(id=chat_id, type='CHANNEL', access='PUBLIC', title=title)
            async def fetch_history(self, **kwargs):
                assert kwargs['interactive'] is False
                return [Obj(text='DO-NOT-PUBLISH-RAW-TEXT')]
        report = asyncio.run(diagnose({'MAX_USER_SESSION_B64': value}, client_factory=Fake, regional=True))
        self.assertTrue(report['readVerified'])
        self.assertEqual(len(report['channels']), 5)
        self.assertTrue(all(r['publisherVerification'] == 'pending' for r in report['channels'][-2:]))
        self.assertNotIn('DO-NOT-PUBLISH', json.dumps(report))

    def test_private_candidate_is_rejected_before_history_while_other_candidates_continue(self):
        value = base64.b64encode(zlib.compress(b'SQLite format 3\x00'+b'a'*1000)).decode()
        private_id = REGIONAL_CANDIDATES[0]['chat_id']
        requests = []
        class Fake:
            def __init__(self, folder): pass
            async def connect(self): pass
            async def close(self): pass
            async def get_chat(self, chat_id):
                c = next(c for c in CHANNELS + REGIONAL_CANDIDATES if c['chat_id'] == chat_id)
                title = c['expected_titles'][0] if 'expected_titles' in c else c['name']
                return Obj(id=chat_id, type='CHANNEL', access='PRIVATE' if chat_id == private_id else 'PUBLIC', title=title)
            async def fetch_history(self, **kwargs):
                requests.append(kwargs['chat_id'])
                return []
        report = asyncio.run(diagnose({'MAX_USER_SESSION_B64': value}, client_factory=Fake, regional=True))
        self.assertNotIn(private_id, requests)
        self.assertEqual(report['channels'][3]['errorCode'], 'IDENTITY_ERROR')
        self.assertTrue(report['channels'][4]['readVerified'])
        self.assertFalse(report['readVerified'])


if __name__ == '__main__':
    unittest.main()
