#!/usr/bin/env bash
# Prepare this one isolated service after the operator verifies the server.
# Deliberately does not start services, alter Nginx or import a MAX credential.
set -euo pipefail
# Root may use umask 0077. Public code/venv must remain traversable by the
# two service users; private state/session modes are set explicitly below.
umask 0022
don_bundle_dir=$(realpath "${1:?Usage: install-prepared.sh BUNDLE_DIRECTORY}")
if [ "$(id -u)" -ne 0 ]; then echo 'Run as the authorized server administrator'; exit 1; fi
test -f "$don_bundle_dir/DEPLOYMENT_STATUS.txt"
test -f "$don_bundle_dir/app/gorod-control/region-v2/worker.py"
test -f "$don_bundle_dir/firstvds/don-collector.service"
if [ -d /opt/don-control ] && [ ! -f /opt/don-control/.don-control-owned ]; then
  echo 'Existing /opt/don-control is not identified as this project; refusing to overwrite'; exit 1
fi
for don_account in don-control don-web; do
  if getent passwd "$don_account" >/dev/null; then
    getent passwd "$don_account" | awk -F: '$5 == "Don Control service" && $7 == "/usr/sbin/nologin" { ok=1 } END { exit !ok }' || {
      echo 'Service account name is already used by an unverified account'; exit 1;
    }
  else
    useradd --system --user-group --no-create-home --comment 'Don Control service' --shell /usr/sbin/nologin "$don_account"
  fi
done
install -d -m 0755 /opt/don-control /etc/don-control /var/lib/don-control
touch /opt/don-control/.don-control-owned
install -d -m 0700 -o don-control -g don-control /var/lib/don-control/state /var/lib/don-control/session
install -d -m 0755 -o don-control -g don-control /var/lib/don-control/public
cp -a "$don_bundle_dir/app/." /opt/don-control/app/
python3 -m venv /opt/don-control/venv
/opt/don-control/venv/bin/python -m pip install --disable-pip-version-check --quiet -r "$don_bundle_dir/requirements.txt"
# Also repair a partial preparation made with a restrictive root umask.
# These trees contain only code and packages, never sessions or private state.
chmod -R u=rwX,go=rX /opt/don-control/app /opt/don-control/venv
for don_config in sources.json catalog.json; do
  if [ ! -e "/etc/don-control/$don_config" ]; then
    install -m 0644 "$don_bundle_dir/config/$don_config" "/etc/don-control/$don_config"
  fi
done
if [ ! -e /etc/don-control/collector.json ]; then
  install -m 0644 "$don_bundle_dir/firstvds/collector.example.json" /etc/don-control/collector.json
fi
# Static interface can update without resetting the last feed/health from MAX.
find "$don_bundle_dir/public" -type f ! -name feed.json ! -name health.json -print0 |
while IFS= read -r -d '' don_asset; do
  don_relative=${don_asset#"$don_bundle_dir/public/"}
  install -D -m 0644 "$don_asset" "/var/lib/don-control/public/$don_relative"
done
install -m 0644 "$don_bundle_dir/firstvds/don-collector.service" /etc/systemd/system/don-collector.service
install -m 0644 "$don_bundle_dir/firstvds/don-public.service" /etc/systemd/system/don-public.service
systemctl daemon-reload
echo 'Don service prepared only. No services started; Nginx, other projects and MAX credentials were not changed.'
echo 'Finish verified registry/catalog/incident processing and private session setup before enabling services.'
