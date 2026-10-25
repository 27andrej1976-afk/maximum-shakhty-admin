"""Read official MAX channels through the documented bot API, on the server only.

No token is placed in URLs, the public feed, HTML, or APK. Missing credentials
and channel permissions are reported explicitly, never as a successful check.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

API = 'https://platform-api2.max.ru/messages'
CHANNELS = (
    ('max_city', 'shakhtygorod', 'Администрация города Шахты', 'MAX_CITY_CHAT_ID'),
    ('max_water', 'id6167110467_gos', 'ГУП РО «УРСВ»', 'MAX_WATER_CHAT_ID'),
    ('max_power', 'id6163089292_biz', 'АО Донэнерго · отключения', 'MAX_POWER_CHAT_ID'),
)


def parse_messages(payload, channel, now):
    """Only dated messages from the requested channel; no invented timestamps."""
    if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list):
        raise ValueError('Invalid messages response')
    posts = []
    for message in payload['messages']:
        if not isinstance(message, dict):
            raise ValueError('Invalid message')
        recipient = message.get('recipient') or {}
        if str(recipient.get('chat_id')) != str(channel['chat_id']):
            raise ValueError('Unexpected channel in response')
        body = message.get('body') or {}
        mid, text, stamp = body.get('mid'), body.get('text'), message.get('timestamp')
        if not isinstance(mid, str) or not re.fullmatch(r'[\w.\-]+', mid):
            continue
        if not isinstance(text, str) or not text.strip() or not isinstance(stamp, (int, float)):
            continue
        try:
            published = datetime.fromtimestamp(stamp / 1000, timezone.utc)
        except (OverflowError, OSError, ValueError):
            continue
        if not -timedelta(minutes=30) < now - published < timedelta(days=16):
            continue
        link = message.get('url', '')
        parsed = urlsplit(link)
        if (parsed.scheme != 'https' or parsed.netloc != 'max.ru' or
                not parsed.path.startswith('/' + channel['slug'] + '/')):
            # Do not guess the public URL encoding from the internal message ID.
            link = channel['url']
        posts.append({'id': channel['id'] + '/' + mid, 'publishedAt': published.isoformat(),
                      'text': text.strip(), 'url': link, 'officialUrl': link,
                      'source': channel['name'], 'sourceId': channel['id'],
                      'origin': 'official_max'})
    return posts


def collect(now=None, environ=None, opener=urlopen):
    now = now or datetime.now(timezone.utc)
    env = os.environ if environ is None else environ
    token = env.get('MAX_BOT_TOKEN', '').strip()
    if env.get('MAX_USER_SESSION_B64', '').strip() and not token:
        from max_user_reader import collect_session
        return collect_session(now, env)
    posts, states = [], []
    for ident, slug, name, variable in CHANNELS:
        chat_id = env.get(variable, '').strip()
        channel = dict(id=ident, slug=slug, name=name, chat_id=chat_id, url='https://max.ru/' + slug)
        state = dict(id=ident, url=channel['url'], status='not_configured',
                     readStatus='not_configured', posts=0, coverage='partial', transport='max_bot_api')
        if not token or not chat_id:
            state['note'] = 'Нужен вход через MAX-коннектор либо токен бота с правами администратора канала'
            states.append(state)
            continue
        if not re.fullmatch(r'-?\d+', chat_id):
            state['note'] = 'ID канала должен быть числом; публичная ссылка не заменяет ID'
            states.append(state)
            continue
        state['checkedAt'] = now.isoformat()
        try:
            req = Request(API + '?' + urlencode({'chat_id': chat_id, 'count': 100}),
                          headers={'Authorization': token, 'Accept': 'application/json'})
            with opener(req, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Response too large')
            payload = json.loads(raw)
            batch = parse_messages(payload, channel, now)
            posts.extend(batch)
            state.update(status='ok', readStatus='ok', posts=len(payload['messages']),
                         matchingPosts=len(batch), lastPostAt=max((p['publishedAt'] for p in batch), default=None),
                         note='API прочитан: последние 100 публикаций; полнота истории не гарантируется')
        except HTTPError as exc:
            state.update(status='error', readStatus='error', httpStatus=exc.code,
                         note='MAX API: HTTP ' + str(exc.code) +
                         (' · проверьте токен и права бота на чтение канала' if exc.code in (401, 403) else ''))
        except Exception:
            # Exception text can contain request details. Never serialize credentials.
            state.update(status='error', readStatus='error', note='MAX API не прочитан: ошибка сети или формата ответа')
        states.append(state)
    return posts, states
