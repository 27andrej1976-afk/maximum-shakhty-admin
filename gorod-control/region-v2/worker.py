"""Persistent regional worker. Fixed public sources, no interactive login."""
import argparse
import asyncio
import fcntl
import json
from pathlib import Path
import signal
from types import SimpleNamespace
from urllib.parse import urlsplit

from core import CATEGORIES
from export_feed import export
from run_collector import run


def configuration(path):
    raw = json.loads(Path(path).read_text())
    registry = json.loads(Path(raw['registry']).read_text())
    catalog = json.loads(Path(raw['catalog']).read_text())
    if registry.get('region') != 'RU-ROS' or catalog.get('regionId') != 'RU-ROS':
        raise ValueError('Wrong region')
    if set(registry.get('categories', [])) != CATEGORIES:
        raise ValueError('First release requires only water, power and MChS')
    for source in registry['channels']:
        url = urlsplit(source['url'])
        if source['id'] in {'max_city', 'shakhty-admin'} or url.path.rstrip('/') == '/shakhtygorod':
            raise ValueError('City administration is excluded from regional monitoring')
        if (url.scheme != 'https' or url.netloc != 'max.ru' or url.query or url.fragment
                or not set(source.get('categories', [])) <= CATEGORIES):
            raise ValueError('Invalid regional public source')
        if source.get('enabled') and (not source.get('identity_verified')
                or type(source.get('chat_id')) is not int):
            raise ValueError('Enabled source must have verified public identity')
    if not any(s.get('enabled') for s in registry['channels']):
        raise ValueError('Registry is disabled; refusing to pretend the collector is connected')
    cities = [c for c in catalog.get('municipalities', []) if c.get('verified')]
    if not cities:
        raise ValueError('Verified regional territory catalog required before live collection')
    provider=raw.get('geometryProvider','photon')
    if provider not in {'photon','dadata'}:raise ValueError('Unsupported geometry provider')
    if provider=='dadata' and not Path(raw.get('geometryTokenFile','/missing')).is_file():
        raise ValueError('Private geometry token file required')
    state = Path(raw['stateDir'])
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    return raw, SimpleNamespace(registry=raw['registry'], catalog=raw['catalog'],
        state_dir=state, session_dir=raw['sessionDir'], municipality=cities[0]['id'],
        health_output=raw['healthOutput'], feed_output=raw['feedOutput'],
        max_pages=min(30, max(1, int(raw.get('maxPages', 20)))),
        gar_index=raw.get('garIndex'),geometry_budget=min(4,max(0,int(raw.get('geometryBudget',0)))),
        geometry_endpoint=raw.get('geometryEndpoint'),geometry_provider=provider,
        geometry_token_file=raw.get('geometryTokenFile'))


async def work(path, *, once=False):
    config, args = configuration(path)
    # Two workers cannot move the same SQLite checkpoint independently.
    with (args.state_dir / 'collector.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop.set)
        while not stop.is_set():
            await run(args)
            if config.get('reviews'):
                export(args.registry, args.state_dir, args.catalog, args.feed_output,
                       reviews_path=config['reviews'])
            # Optional, fail-isolated push delivery cannot stop MAX ingestion.
            try:
                from push_dispatch import dispatch
                from run_collector import atomic_json
                from datetime import datetime,timezone
                now=datetime.now(timezone.utc).isoformat()
                push_status=dispatch(config,args.feed_output,args.state_dir,now)
                atomic_json(args.state_dir/'push-status.json',dict(push_status,checkedAt=now))
            except Exception:
                atomic_json(args.state_dir/'push-status.json',{'state':'error','deliveryVerified':False})
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(60, int(config.get('intervalSeconds', 120))))
            except TimeoutError:
                pass


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--once', action='store_true')
    p.add_argument('--check-config', action='store_true', help='Validate deployment configuration without accessing MAX')
    a = p.parse_args()
    try:
        if a.check_config:
            configuration(a.config)
            print('Regional configuration validated; account access was not attempted')
        else:
            asyncio.run(work(a.config, once=a.once))
    except (ValueError, KeyError, FileNotFoundError, BlockingIOError):
        # Configuration and lock failure are explicit; no raw provider data.
        raise SystemExit('Regional collector not started: verify configuration, territories and single-worker lock')
