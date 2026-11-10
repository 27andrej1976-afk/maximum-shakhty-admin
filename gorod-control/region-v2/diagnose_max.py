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


def error_code(error, stage):
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


async def diagnose(environ=None, *, client_factory=make_client):
    env = os.environ if environ is None else environ
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'sdkVersion': '2.4.1',
              'readVerified': False, 'stage': 'session', 'channels': [],
              'scope': 'existing-three-public-channels-only'}
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
                for channel in CHANNELS:
                    row = {'id': channel['id'], 'stage': 'identity', 'readVerified': False}
                    try:
                        chat = await asyncio.wait_for(client.get_chat(channel['chat_id']), timeout=20)
                        validate_channel(chat, channel)
                        row['stage'] = 'history'
                        messages = await asyncio.wait_for(client.fetch_history(
                            chat_id=channel['chat_id'], backward=20, interactive=False), timeout=20)
                        if not isinstance(messages, list):
                            raise ValueError('Unexpected history shape')
                        row.update(stage='complete', readVerified=True, messagesReceived=len(messages))
                    except Exception as error:
                        row['errorCode'] = error_code(error, row['stage'])
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
    finally:
        logging.disable(previous_logging)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    result = asyncio.run(diagnose())
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))

    raise SystemExit(0 if result['readVerified'] else 2)
