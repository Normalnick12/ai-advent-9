#!/usr/bin/env bash
# One-time Ubuntu bootstrap, run interactively with sudo after reviewing this file.
# No secrets are accepted as arguments or printed. Requires the adjacent snapshot.tar.gz.
set -euo pipefail
umask 077
test "$(id -u)" -eq 0 || { echo 'Run this reviewed script with sudo.' >&2; exit 1; }
stage=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test -f "$stage/snapshot.tar.gz"
test -f "$stage/snapshot.sha256"
(cd "$stage" && sha256sum --check snapshot.sha256)
test ! -e /opt/day18/current || { echo 'Existing deployment: review upgrade separately.' >&2; exit 1; }
test ! -e /etc/caddy/Caddyfile || { echo 'Existing Caddy configuration: review before replacing.' >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv debian-keyring debian-archive-keyring apt-transport-https curl gnupg ufw unattended-upgrades
# Official Caddy stable repository: https://caddyserver.com/docs/install#debian-ubuntu-raspbian
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key -o "$stage/caddy.gpg"
gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg "$stage/caddy.gpg"
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt -o /etc/apt/sources.list.d/caddy-stable.list
chmod 0644 /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
systemctl mask caddy.service
apt-get update
apt-get install -y caddy

getent passwd day18 >/dev/null || useradd --system --home-dir /var/lib/day18 --shell /usr/sbin/nologin day18
install -d -o root -g root -m 0755 /opt/day18/releases
release="/opt/day18/releases/$(cut -c1-16 "$stage/snapshot.sha256")"
test ! -e "$release" || { echo 'Release already exists: inspect partial bootstrap before retry.' >&2; exit 1; }
install -d -o root -g root -m 0755 "$release"
python3 - "$stage/snapshot.tar.gz" "$release" <<'PY'
import hashlib, json, pathlib, sys, tarfile
archive, destination = sys.argv[1:]
with tarfile.open(archive) as tar:
    tar.extractall(destination, filter='data')
root = pathlib.Path(destination)
manifest = json.loads((root / 'snapshot-manifest.json').read_text())
for name, expected in manifest.items():
    file = root / name
    assert file.is_file() and not file.is_symlink(), name
    assert hashlib.sha256(file.read_bytes()).hexdigest() == expected, name
print('Snapshot manifest verified:', len(manifest), 'files')
PY
find "$release" -type d -exec chmod 0755 {} +
find "$release" -type f -exec chmod 0644 {} +
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install -r "$release/requirements.txt"
"$release/.venv/bin/python" -m pip freeze > "$release/installed-requirements.txt"
chmod -R a+rX "$release"

public_host=$(sed -n 's/^DAY18_MCP_PUBLIC_HOST=//p' "$release/deploy/public.conf" | tr -d '\r')
python3 - "$public_host" <<'PY'
import ipaddress, re, socket, sys
host = sys.argv[1]
assert re.fullmatch(r'[A-Za-z0-9.-]+', host), 'Invalid hostname'
ips = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
assert ips == {'132.243.120.220'}, f'DNS mismatch, stop for review: {ips}'
print('VPS DNS verified:', host, sorted(ips))
PY
install -d -o day18 -g day18 -m 0700 /var/lib/day18
install -d -o root -g day18 -m 0750 /etc/day18
test ! -e /etc/day18/dependency-watch.env || { echo 'Existing credential file: stop; never overwrite silently.' >&2; exit 1; }
python3 - "$public_host" <<'PY'
import grp, os, secrets, sys
path = '/etc/day18/dependency-watch.env'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
with os.fdopen(fd, 'w') as file:
    file.write('DAY18_MCP_TOKEN=' + secrets.token_urlsafe(48) + '\n')
    file.write('DAY18_MCP_PUBLIC_HOST=' + sys.argv[1] + '\n')
    file.write('DAY18_DATABASE_PATH=/var/lib/day18/watch.sqlite3\nDAY18_ALLOW_SHORT_INTERVALS=false\n')
os.chown(path, 0, grp.getgrnam('day18').gr_gid)
os.chmod(path, 0o640)
PY
# Operator may securely transfer this credential into the local backend environment.
# SQLite stays 0700, accessible only to the service user/root.
usermod -a -G day18 aiadvent
install -o root -g root -m 0644 "$release/deploy/day18-watch.service" /etc/systemd/system/day18-watch.service
ln -s "$release" /opt/day18/current
install -d -o root -g root -m 0755 /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironment=DAY18_MCP_PUBLIC_HOST=%s\n' "$public_host" > /etc/systemd/system/caddy.service.d/day18.conf
chmod 0644 /etc/systemd/system/caddy.service.d/day18.conf
install -o root -g caddy -m 0644 "$release/deploy/Caddyfile" /etc/caddy/Caddyfile
DAY18_MCP_PUBLIC_HOST="$public_host" caddy validate --config /etc/caddy/Caddyfile
systemd-analyze verify /etc/systemd/system/day18-watch.service

# Preserve SSH access before enabling the firewall. Never reset existing rules.
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw default allow outgoing
ufw --force enable
ufw status verbose

# Public-key login has already been verified from the deployment client.
test ! -e /etc/ssh/sshd_config.d/00-day18-key-only.conf
printf 'PubkeyAuthentication yes\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/00-day18-key-only.conf
chmod 0644 /etc/ssh/sshd_config.d/00-day18-key-only.conf
/usr/sbin/sshd -t
systemctl reload ssh

install -d -m 0755 /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=200M\nMaxRetentionSec=7day\n' > /etc/systemd/journald.conf.d/day18.conf
chmod 0644 /etc/systemd/journald.conf.d/day18.conf
systemctl restart systemd-journald
systemctl enable unattended-upgrades
systemctl unmask caddy.service
systemctl daemon-reload
systemctl enable --now day18-watch caddy
systemctl restart caddy
systemctl is-enabled day18-watch caddy
systemctl is-active day18-watch caddy
ss -ltnp

# No insecure curl flag, certificate substitution, or hostname fallback.
for attempt in $(seq 1 12); do
    if curl --fail --silent --show-error --connect-timeout 5 --max-time 10 "https://$public_host/health"; then
        printf '\nTrusted HTTPS health passed.\n'
        exit 0
    fi
    sleep 5
done
echo 'Trusted HTTPS unavailable: stop for review. No hostname/certificate fallback performed.' >&2
journalctl -u caddy -n 60 --no-pager
exit 1
