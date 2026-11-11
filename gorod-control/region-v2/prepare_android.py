"""Prepare the independent regional Android preview without building/signing it."""
import argparse
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit

from build_client import build

ROOT = Path(__file__).resolve().parent


def prepare(*, feed_url=None):
    if feed_url:
        url = urlsplit(feed_url)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.port not in (None, 443)):
            raise ValueError('A public HTTPS feed URL without credentials or query is required')
    target = ROOT / 'android/app/src/main/assets/web'
    build(target)
    config = {'feedConfigured': bool(feed_url), 'feedURL': feed_url, 'androidPreview': True}
    (target / 'config.js').write_text('window.DonConfig = ' + json.dumps(config) + ';\n')
    drawable = ROOT / 'android/app/src/main/res/drawable-nodpi'
    drawable.mkdir(parents=True, exist_ok=True)
    # Preserve the original supplied coat; no reconstruction or image editing.
    shutil.copyfile(ROOT / 'assets/rostov-coat.png', drawable / 'rostov_coat.png')
    return target


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--feed-url', help='Approved public feed endpoint; never a MAX session URL')
    a = p.parse_args()
    print(prepare(feed_url=a.feed_url))
