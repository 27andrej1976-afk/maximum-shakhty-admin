"""Read only allowlisted public MAX posts, never account/profile/session data.

Bounded inspection sample, not a complete catch-up or incident feed. Candidate
publisher provenance must still be checked before production enablement.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tempfile

from collector import envelope, millis
from diagnose_max import (REGIONAL_BASE, REGIONAL_CANDIDATES, SESSION,
                          decode_session, error_code, make_client,
                          validate_diagnostic_channel)

SOURCE_IDS = {-69418948796459: 'ursv', -72527316071728: 'donenergo',
              -69127719422667: 'rostovvodokanal-candidate',
              -69220795976413: 'mchs-rostov-candidate'}


async def sample(environ=None, *, client_factory=make_client):
    now = datetime.now(timezone.utc).isoformat()
    result = {'checkedAt': now, 'scope': 'four-allowlisted-public-channels',
              'completeHistory': False, 'channels': []}
    env = os.environ if environ is None else environ
    token = env.get('MAX_USER_SESSION_B64', '').strip()
    if not token:
        return dict(result, errorCode='NOT_CONFIGURED')
    old_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    stage = 'decode-session'
    client = None
    try:
        raw = decode_session(token)
        with tempfile.TemporaryDirectory(prefix='don-public-sample-') as folder:
            db = Path(folder)/SESSION
            db.write_bytes(raw)
            db.chmod(0o600)
            try:
                stage = 'connect'
                client = client_factory(folder)
                await asyncio.wait_for(client.connect(), 45)
                for source in REGIONAL_BASE + REGIONAL_CANDIDATES:
                    sid = SOURCE_IDS[source['chat_id']]
                    public = {'id': sid, 'chat_id': source['chat_id'],
                              'url': 'https://max.ru/'+source['slug']}
                    row = {'id': sid, 'url': public['url'], 'readVerified': False, 'posts': []}
                    try:
                        chat = await asyncio.wait_for(client.get_chat(source['chat_id']), 20)
                        validate_diagnostic_channel(chat, source)
                        history = await asyncio.wait_for(client.fetch_history(
                            chat_id=source['chat_id'], backward=100, interactive=False), 30)
                        if not isinstance(history, list) or len(history) > 100:
                            raise ValueError('Invalid history shape')
                        row['posts'] = [envelope(m, public, millis(now)) for m in history]
                        row['readVerified'] = True
                    except Exception as error:
                        row['errorCode'] = error_code(error, 'history')
                    result['channels'].append(row)
            finally:
                if client:
                    try:
                        await asyncio.wait_for(client.close(), 10)
                    except Exception:
                        pass
    except Exception as error:
        result['errorCode'] = error_code(error, stage)
    finally:
        logging.disable(old_logging)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--report', required=True)
    a = p.parse_args()
    data = asyncio.run(sample())
    Path(a.output).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    safe = {k:v for k,v in data.items() if k != 'channels'}
    safe['channels'] = [{k:v for k,v in c.items() if k != 'posts'} | {'messagesReceived':len(c['posts'])}
                        for c in data['channels']]
    Path(a.report).write_text(json.dumps(safe, ensure_ascii=False, indent=2))
    print(json.dumps(safe, ensure_ascii=False))
    raise SystemExit(0 if len(data['channels']) == 4 and all(c['readVerified'] for c in data['channels']) else 2)
