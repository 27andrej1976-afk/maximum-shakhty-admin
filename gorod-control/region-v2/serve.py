"""Serve only the regional public bundle; never sessions, SQLite or private state."""
import argparse
import gzip
from datetime import datetime, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

EXTENSIONS = {'.html', '.js', '.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.txt'}


class PublicHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, public_dir, **kwargs):
        self.public_dir = Path(public_dir).resolve()
        super().__init__(*args, **kwargs)

    def log_message(self, *args):
        pass  # No client addresses, URL queries or credentials in application logs.

    def _reply(self, status, raw=b'', mime='application/json; charset=utf-8', *, head=False):
        compressible=(mime.startswith('text/') or mime.startswith('application/json')
                      or mime.startswith('application/javascript') or mime.startswith('image/svg'))
        accepts_gzip=False
        for item in self.headers.get('Accept-Encoding','').split(','):
            fields=[s.strip().lower() for s in item.split(';')]
            if fields[0]!='gzip':continue
            try:quality=float(next((s[2:] for s in fields[1:] if s.startswith('q=')),'1'))
            except ValueError:quality=0
            accepts_gzip=quality>0
            break
        encoded=status==200 and len(raw)>=1024 and compressible and accepts_gzip
        if encoded:raw=gzip.compress(raw,compresslevel=4,mtime=0)
        self.send_response(status)
        if encoded:self.send_header('Content-Encoding','gzip')
        self.send_header('Vary','Origin, Accept-Encoding')
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin' if mime.startswith('text/html') else 'no-referrer')
        self.send_header('Cache-Control', 'no-store' if mime.startswith('application/json') else 'public, max-age=600')
        if self.headers.get('Origin') == 'https://appassets.androidplatform.net':
            self.send_header('Access-Control-Allow-Origin', 'https://appassets.androidplatform.net')
        self.end_headers()
        if not head:
            self.wfile.write(raw)

    def _get(self, *, head=False):
        raw_path = unquote(urlsplit(self.path).path)
        if raw_path == '/healthz':
            feed = self.public_dir / 'feed.json'
            payload = {'server': 'running', 'feedAvailable': feed.is_file(),
                       'incidentPipelineVerified': False}
            return self._reply(200, json.dumps(payload).encode(), head=head)
        relative = raw_path.lstrip('/') or 'index.html'
        if ('\\' in relative or '\x00' in relative
                or any(part.startswith('.') for part in relative.split('/'))
                or (Path(relative).suffix not in EXTENSIONS and relative not in ('feed.json', 'health.json'))):
            return self._reply(404, b'{}', head=head)
        target = (self.public_dir / relative).resolve()
        if self.public_dir not in target.parents or not target.is_file():
            return self._reply(404, b'{}', head=head)
        try:
            if target.stat().st_size > 8 * 1024 * 1024:
                return self._reply(503, b'{"error":"PUBLIC_FILE_LIMIT"}', head=head)
            data = target.read_bytes()
        except OSError:
            return self._reply(503, b'{"error":"PUBLIC_FILE_UNAVAILABLE"}', head=head)
        mime = 'application/json; charset=utf-8' if relative.endswith('.json') else mimetypes.guess_type(relative)[0] or 'application/octet-stream'
        self._reply(200, data, mime, head=head)

    def do_GET(self):
        self._get()

    def do_HEAD(self):
        self._get(head=True)

    def do_POST(self):
        self._reply(405, b'{"error":"READ_ONLY_PUBLIC_SERVICE"}')


def server(public_dir, *, host='127.0.0.1', port=8791):
    return ThreadingHTTPServer((host, port), partial(PublicHandler, public_dir=public_dir))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public-dir', required=True)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8791)
    a = p.parse_args()
    server(a.public_dir, host=a.host, port=a.port).serve_forever()
