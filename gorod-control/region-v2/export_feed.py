"""Export reviewed MAX evidence and source health for the regional web client."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from core import Store
from events import Ledger
from run_collector import atomic_json


def export(registry_path, state_dir, catalog_path, output, *, reviews_path=None, now=None):
    registry = json.loads(Path(registry_path).read_text())
    catalog = json.loads(Path(catalog_path).read_text())
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    store = Store(state_dir / 'public-posts.sqlite', registry['channels'])
    now = now or datetime.now(timezone.utc).isoformat()
    try:
        ledger = Ledger(store, catalog)
        if reviews_path:
            ledger.apply(json.loads(Path(reviews_path).read_text())['records'], now)
        feed = ledger.feed(now)
        atomic_json(output, feed)
        return feed
    finally:
        store.db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry', required=True)
    p.add_argument('--state-dir', required=True)
    p.add_argument('--catalog', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--reviews', help='Validated parser/operator review records, not raw MAX posts')
    a = p.parse_args()
    export(a.registry, a.state_dir, a.catalog, a.output, reviews_path=a.reviews)
