"""Restartable, read-only MAX history collector. Not enabled in production.

Requires an already authenticated local session and an explicitly verified source
registry. Never logs in, joins channels, sends messages or marks anything read.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from core import utc

PAGE_SIZE = 100
LOOKBACK = timedelta(days=16)
OVERLAP = timedelta(hours=24)


class CollectionError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def millis(stamp):
    return int(utc(stamp).timestamp() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def value(obj):
    return getattr(obj, 'value', obj)


def verify_source(source, chat):
    link = urlsplit(source['url'])
    if (not source.get('enabled') or not source.get('identity_verified')
            or source.get('transport') != 'max' or link.scheme != 'https'
            or link.netloc != 'max.ru' or not isinstance(source.get('chat_id'), int)
            or isinstance(source['chat_id'], bool)):
        raise CollectionError('IDENTITY_ERROR')
    if (getattr(chat, 'id', None) != source['chat_id']
            or value(getattr(chat, 'type', None)) != 'CHANNEL'
            or value(getattr(chat, 'access', None)) != 'PUBLIC'):
        raise CollectionError('IDENTITY_ERROR')


def envelope(message, source, target_ms):
    """Allowlist public fields. No session, sender, profile or signed media URL."""
    mid, stamp = getattr(message, 'id', None), getattr(message, 'time', None)
    if (not isinstance(mid, int) or isinstance(mid, bool) or mid <= 0
            or not isinstance(stamp, int) or isinstance(stamp, bool)
            or stamp <= 0 or stamp > target_ms + 300000
            or getattr(message, 'chat_id', None) not in (None, source['chat_id'])):
        raise CollectionError('FORMAT_ERROR')
    text = getattr(message, 'text', '')
    if text is None:
        text = ''
    if not isinstance(text, str) or len(text) > 100000:
        raise CollectionError('FORMAT_ERROR')
    attachments = getattr(message, 'attaches', None) or []
    if not isinstance(attachments, (list, tuple)) or len(attachments) > 1000:
        raise CollectionError('FORMAT_ERROR')
    forwarded = getattr(message, 'link', None) is not None
    kind = value(getattr(message, 'type', None))
    # Unknown payloads stay in the evidence store, never become incidents silently.
    review = bool(attachments or forwarded or not text.strip() or kind not in ('CHANNEL', 'TEXT'))
    return {
        'id': str(mid), 'channel_id': source['chat_id'],
        'publishedAt': iso(stamp), 'text': text,
        'channelBinding': 'message' if getattr(message, 'chat_id', None) is not None else 'verified_history_request',
        'sourceId': source['id'], 'url': source['url'], 'transport': 'max',
        'attachmentCount': len(attachments),
        'attachmentTypes': [type(a).__name__ for a in attachments],
        'forwarded': forwarded, 'requiresReview': review,
    }


def _tables(store):
    store.db.execute('''CREATE TABLE IF NOT EXISTS scans(
        channel TEXT PRIMARY KEY,target_ms INTEGER,cutoff_ms INTEGER,before_ms INTEGER)''')
    store.db.commit()


def _persist_page(store, cid, posts, before_ms, now):
    # New evidence and scan continuation commit together. The proven checkpoint
    # and lastSuccess are NOT advanced by an unfinished page.
    with store.db:
        for post in posts:
            store._write_post(cid, post)
        store.db.execute('UPDATE scans SET before_ms=? WHERE channel=?', (before_ms, cid))
        store.db.execute('''INSERT INTO health(channel,attempt,error,gap)
            VALUES(?,?,'GAP',1) ON CONFLICT(channel) DO UPDATE SET
            attempt=excluded.attempt,error='GAP',gap=1''', (cid, now))


def _finish(store, cid, target_ms, now):
    # A long catch-up must not pretend that its old snapshot was checked now.
    with store.db:
        store.db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?)',
                         (cid, json.dumps({'throughMs': target_ms})))
        store.db.execute('INSERT OR REPLACE INTO health VALUES(?,?,?,NULL,0)',
                         (cid, iso(target_ms), now))
        store.db.execute('DELETE FROM scans WHERE channel=?', (cid,))


async def collect_channel(store, client, cid, now, *, max_pages=20):
    """Catch up one channel; preserve partial evidence and resume after failure.

    Uses documented PyMax from_time milliseconds. Inclusive boundary overlap and
    no-progress detection avoid skipping messages at equal timestamps. More than
    one page at an indistinguishable timestamp remains a visible GAP, not success.
    """
    if max_pages < 1:
        raise ValueError('max_pages must be positive')
    utc(now)
    _tables(store)
    source = store.channels[cid]
    try:
        # Validate configured source before any external request.
        probe = type('Identity', (), {'id': source.get('chat_id'), 'type': 'CHANNEL', 'access': 'PUBLIC'})()
        verify_source(source, probe)
        chat = await client.get_chat(source['chat_id'])
        verify_source(source, chat)
        scan = store.db.execute('SELECT target_ms,cutoff_ms,before_ms FROM scans WHERE channel=?', (cid,)).fetchone()
        if scan:
            target, cutoff, before = scan
        else:
            target = millis(now)
            previous = store.checkpoint(cid)
            cutoff = target - int(LOOKBACK.total_seconds() * 1000)
            if previous:
                checkpoint = json.loads(previous)
                cutoff = checkpoint['throughMs'] - int(OVERLAP.total_seconds() * 1000)
            before = target
            with store.db:
                store.db.execute('INSERT INTO scans VALUES(?,?,?,?)', (cid, target, cutoff, before))
        for _ in range(max_pages):
            messages = await client.fetch_history(chat_id=source['chat_id'], backward=PAGE_SIZE,
                                                  from_time=before, interactive=False)
            if not isinstance(messages, list) or len(messages) > PAGE_SIZE:
                raise CollectionError('FORMAT_ERROR')
            if not messages:
                _finish(store, cid, target, now)
                return {'id': cid, 'state': 'read', 'caughtUpThrough': iso(target)}
            posts = [envelope(message, source, target) for message in messages]
            oldest = min(millis(post['publishedAt']) for post in posts)
            # Server returning only newer or identical boundary positions cannot
            # establish continuity. Keep posts, retain checkpoint, expose a gap.
            selected = [p for p in posts if cutoff <= millis(p['publishedAt']) <= target]
            next_before = oldest
            if oldest == before and len(messages) < PAGE_SIZE:
                # A short boundary page fits in one MAX page. Skip that already
                # fetched millisecond only; a saturated boundary stays a GAP.
                next_before = before - 1
            _persist_page(store, cid, selected, min(next_before, before), now)
            if oldest < cutoff:
                _finish(store, cid, target, now)
                return {'id': cid, 'state': 'read', 'caughtUpThrough': iso(target)}
            if next_before >= before:
                raise CollectionError('GAP')
            before = next_before  # deliberately overlap every ordinary boundary
        raise CollectionError('GAP')
    except Exception as exc:
        code = (exc.code if isinstance(exc, CollectionError) else
                'TIMEOUT' if isinstance(exc, TimeoutError) else 'UNAVAILABLE')
        store.failure(cid, now, code, gap=bool(store.db.execute(
            'SELECT 1 FROM scans WHERE channel=?', (cid,)).fetchone()))
        # Never serialize raw exceptions, which can contain URLs or credentials.
        return {'id': cid, 'state': 'unavailable', 'errorCode': code}


async def collect_all(store, client, now, **options):
    results = []
    for source in store.channels.values():
        if source.get('enabled'):
            results.append(await collect_channel(store, client, source['id'], now, **options))
    return results
