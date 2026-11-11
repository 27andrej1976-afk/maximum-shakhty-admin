"""Read-only diagnostics for the EXISTING three public MAX channels.

No login, joins, messages, read receipts, feed changes or APK build. The report
contains fixed error classes/stages and counts only, never credentials or text.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from max_user_reader import CHANNELS, SESSION, LoginRequired, decode_session, make_client, validate_channel

# Public numeric hints are discovery inputs, never production coverage claims.
# API type/access/title must match before any history request. No join/search of
# private account chats and no private profiles are included in this diagnostic.
REGIONAL_CANDIDATES = (
    {'id': 'max_rostov_water', 'chat_id': -69127719422667,
     'slug': 'id6167081833_biz', 'expected_titles': ('ростовводоканал',)},
    {'id': 'max_rostov_mchs', 'chat_id': -69220795976413,
     'slug': 'id6164228703_gos', 'expected_titles': (
         'мчс ростовской области', 'главное управление мчс россии по ростовской области')},
)


class CandidateIdentityError(ValueError):
    pass


def validate_diagnostic_channel(chat, source):
    if 'expected_titles' not in source:
        validate_channel(chat, source)
        return
    def enum(value):
        return getattr(value, 'value', value)
    import re
    title = re.sub(r'[^а-яa-z0-9]+', ' ', (getattr(chat, 'title', '') or '').lower()).strip()
    if (getattr(chat, 'id', None) != source['chat_id']
            or enum(getattr(chat, 'type', None)) != 'CHANNEL'
            or enum(getattr(chat, 'access', None)) != 'PUBLIC'
            or title not in source['expected_titles']):
        raise CandidateIdentityError()


def error_code(error, stage):
    if isinstance(error, CandidateIdentityError):
        return 'IDENTITY_ERROR'
    if stage == 'decode-session':
        return 'SESSION_INVALID'
    if isinstance(error, LoginRequired):
        return 'AUTH_REQUIRED'
    if isinstance(error, ImportError):
        return 'DEPENDENCY_ERROR'
    if isinstance(error, TimeoutError):
        return 'TIMEOUT'
    # Class names are mapped to constants; neither arbitrary class names nor
    # exception messages/URLs/API payloads are included in the public report.
    name = type(error).__name__
    if name == 'ApiError' and safe_api_details(error)['loginTokenRejected']:
        return 'AUTH_REQUIRED'
    if name in {'SSLError', 'SSLCertVerificationError', 'ClientConnectorCertificateError'}:
        return 'TLS_ERROR'
    if name in {'ApiError', 'ValidationError', 'OperationalError'}:
        return {'ApiError': 'API_ERROR', 'ValidationError': 'FORMAT_ERROR',
                'OperationalError': 'SESSION_STORAGE_ERROR'}[name]
    if isinstance(error, ConnectionError) or name in {
            'ConnectionClosedError', 'ConnectionClosedOK', 'InvalidStatus',
            'InvalidStatusCode', 'ClientConnectorError', 'gaierror'}:
        return 'TRANSPORT_ERROR'
    return 'READER_ERROR'


def safe_api_details(error):
    if type(error).__name__ != 'ApiError':
        return {}
    opcode = getattr(error, 'opcode', None)
    known_rejection = opcode == 19 and any(value in (
        getattr(error, 'error', None), getattr(error, 'message', None))
        for value in ('FAIL_LOGIN_TOKEN', 'FAIL_LOGOUT_ALL'))
    return {'apiOperation': {6: 'HANDSHAKE', 19: 'LOGIN', 48: 'CHANNEL_IDENTITY',
                             49: 'CHANNEL_HISTORY'}.get(opcode, 'OTHER'),
            'loginTokenRejected': known_rejection}


async def diagnose(environ=None, *, client_factory=make_client, regional=False):
    env = os.environ if environ is None else environ
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'sdkVersion': '2.4.1',
              'readVerified': False, 'stage': 'session', 'channels': [],
              'scope': 'five-public-channels-discovery' if regional else 'existing-three-public-channels-only'}
    sources = CHANNELS + REGIONAL_CANDIDATES if regional else CHANNELS
    value = env.get('MAX_USER_SESSION_B64', '').strip()
    if not value:
        return dict(report, errorCode='NOT_CONFIGURED')
    stage = 'decode-session'
    client = None
    # Suppress library log output; raw transport logs can contain request data.
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        raw = decode_session(value)
        with tempfile.TemporaryDirectory(prefix='don-max-diagnostic-') as folder:
            target = Path(folder) / SESSION
            target.write_bytes(raw)
            target.chmod(0o600)
            try:
                stage = 'construct-client'
                client = client_factory(folder)
                stage = 'connect'
                await asyncio.wait_for(client.connect(), timeout=45)
                for channel in sources:
                    row = {'id': channel['id'], 'stage': 'identity', 'readVerified': False,
                           'publisherVerification': 'pending' if 'expected_titles' in channel else 'previously-reviewed'}
                    try:
                        chat = await asyncio.wait_for(client.get_chat(channel['chat_id']), timeout=20)
                        validate_diagnostic_channel(chat, channel)
                        row['stage'] = 'history'
                        messages = await asyncio.wait_for(client.fetch_history(
                            chat_id=channel['chat_id'], backward=20, interactive=False), timeout=20)
                        if not isinstance(messages, list):
                            raise ValueError('Unexpected history shape')
                        row.update(stage='complete', readVerified=True, messagesReceived=len(messages))
                    except Exception as error:
                        row['errorCode'] = error_code(error, row['stage'])
                        row.update(safe_api_details(error))
                    report['channels'].append(row)
                report['readVerified'] = bool(report['channels']) and all(
                    c['readVerified'] for c in report['channels'])
                report['stage'] = 'complete'
            finally:
                if client is not None:
                    try:
                        await asyncio.wait_for(client.close(), timeout=10)
                    except Exception:
                        pass
    except Exception as error:
        report.update(stage=stage, errorCode=error_code(error, stage))
        report.update(safe_api_details(error))
    finally:
        logging.disable(previous_logging)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--regional', action='store_true', help='Also check public Rostovvodokanal and regional MChS candidates')
    a = p.parse_args()
    result = asyncio.run(diagnose(regional=a.regional))
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))

    raise SystemExit(0 if result['readVerified'] else 2)
