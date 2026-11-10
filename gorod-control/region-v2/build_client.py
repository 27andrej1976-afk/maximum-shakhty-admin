"""Package the regional web client for local QA or a later approved APK build.

Does not compile APKs, deploy or connect to MAX. Default data has no invented
territories, incidents or successful checks.
"""
import argparse
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from export_feed import export

ROOT = Path(__file__).resolve().parent


def build(destination, *, feed=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'web', destination, dirs_exist_ok=True)
    shutil.copytree(ROOT / 'assets', destination / 'assets', dirs_exist_ok=True)
    if feed:
        shutil.copyfile(feed, destination / 'feed.json')
    else:
        with TemporaryDirectory() as state:
            export(ROOT / 'sources.draft.json', state, ROOT / 'catalog.draft.json', destination / 'feed.json')
    return destination


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--feed', help='Existing exported feed; test fixtures remain visibly labelled')
    args = p.parse_args()
    print(build(args.output, feed=args.feed))
