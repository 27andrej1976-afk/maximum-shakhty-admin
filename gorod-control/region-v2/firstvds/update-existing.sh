#!/usr/bin/env bash
# Scoped code/data update only. Keeps the verified registry, MAX session, Caddy,
# existing units, other projects, and permanent APK key untouched.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo 'Root required for existing service update'; exit 1; }
src=$(readlink -f "${1:?Pass extracted region-v2 source directory}")
app=/opt/don-control/app/gorod-control/region-v2
public=/var/lib/don-control/public
state=/var/lib/don-control/state
[ -f "$app/worker.py" ] && [ -f /etc/don-control/collector.json ]
[ -f "$src/osm-streets-20261112.json.gz" ] && [ -f "$src/push_dispatch.py" ]
cd "$src"
/opt/don-control/venv/bin/python - <<'PY'
from parse_publications import load_index
from offline_geography import load_offline_points,NAME
index=load_index('gar-rostov-20261106.json.gz')
points=load_offline_points(NAME,index)
assert len(points)==19230
print('Staged GAR catalogue validated:',len(points),'street reference points')
PY
backup=/var/lib/don-control/backups/code-update-$(date -u +%Y%m%dT%H%M%SZ)
install -d -m0700 "$backup"
tar -C "$app" -czf "$backup/app-before.tar.gz" .
install -d -m0700 "$backup/public"
for file in app.js client.js index.html about.html; do cp -a "$public/$file" "$backup/public/$file"; done
systemctl stop don-collector.service
cp -a "$state" "$backup/state"
rollback() {
  trap - ERR
  systemctl stop don-collector.service || true
  tar -C "$app" -xzf "$backup/app-before.tar.gz"
  mv "$state" "$backup/failed-state"
  cp -a "$backup/state" "$state"
  for file in app.js client.js index.html about.html; do cp -a "$backup/public/$file" "$public/$file"; done
  systemctl start don-collector.service
  echo 'Update failed; previous collector code/state restored' >&2
}
trap rollback ERR
for file in parse_publications.py pipeline.py events.py run_collector.py worker.py push_dispatch.py offline_geography.py osm-streets-20261112.json.gz; do install -m0644 "$src/$file" "$app/$file"; done
for file in app.js client.js index.html about.html; do install -m0644 "$src/web/$file" "$public/$file"; done
cd "$app"
runuser -u don-control -- /opt/don-control/venv/bin/python worker.py --config /etc/don-control/collector.json --check-config
systemctl start don-collector.service
trap - ERR
echo "Collector update started; private rollback snapshot: $backup"
systemctl is-active don-collector.service don-public.service
