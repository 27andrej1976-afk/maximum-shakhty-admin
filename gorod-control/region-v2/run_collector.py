"""Local/operator entry point. No APK build, deployment or interactive login."""
import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile

from collector import collect_all
from core import Store
from health import snapshot


def atomic_json(path, payload, *, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.health-', suffix='.json')
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def run(args):
    registry = json.loads(Path(args.registry).read_text())
    state = Path(args.state_dir)
    state.mkdir(parents=True, exist_ok=True)
    store = Store(state / 'public-posts.sqlite', registry['channels'])
    now = datetime.now(timezone.utc).isoformat()
    client = None
    try:
        if not any(source.get('enabled') for source in store.channels.values()):
            return  # No connection for an entirely disabled draft registry.
        session = Path(args.session_dir) / 'max-session.db'
        if not session.is_file():
            for source in store.channels.values():
                if source.get('enabled'):
                    store.failure(source['id'], now, 'AUTH_REQUIRED')
            return
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        from max_user_reader import make_client, LoginRequired
        client = make_client(session.parent)
        await asyncio.wait_for(client.connect(), timeout=45)
        await collect_all(store, client, now, max_pages=args.max_pages)
    except Exception as error:
        # No raw exception output: it can contain credentials or private URLs.
        code = ('TIMEOUT' if isinstance(error, TimeoutError) else
                'DEPENDENCY_ERROR' if isinstance(error, ImportError) else
                'AUTH_REQUIRED' if 'LoginRequired' in locals() and isinstance(error, LoginRequired)
                else 'UNAVAILABLE')
        for source in store.channels.values():
            if source.get('enabled'):
                store.failure(source['id'], now, code)
    finally:
        if client is not None:
            try:
                await asyncio.wait_for(client.close(), timeout=10)
            except Exception:
                pass
        atomic_json(args.health_output, snapshot(store, args.municipality, now), mode=0o644)
        if getattr(args, 'feed_output', None):
            from events import Ledger
            catalog = json.loads(Path(args.catalog).read_text())
            atomic_json(args.feed_output, Ledger(store, catalog).feed(now), mode=0o644)
        store.db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True)
    parser.add_argument('--state-dir', required=True, help='Постоянный каталог БД; не временный runner')
    parser.add_argument('--session-dir', required=True, help='Уже авторизованная сессия, не публикуется')
    parser.add_argument('--municipality', required=True, help='Проверенный ID территории из справочника')
    parser.add_argument('--health-output', required=True)
    parser.add_argument('--catalog', help='Verified regional address catalog for client feed export')
    parser.add_argument('--feed-output', help='Client feed JSON; requires --catalog')
    parser.add_argument('--max-pages', type=int, default=20)
    args = parser.parse_args()
    if args.feed_output and not args.catalog:
        parser.error('--feed-output requires --catalog')
    asyncio.run(run(args))
