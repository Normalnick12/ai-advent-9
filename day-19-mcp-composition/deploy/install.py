"""Isolated initial install, or guarded Caddy-only recovery after partial install.

Never rerun an old initial installer after failure. --resume-caddy-from requires
an inspected existing release; it preserves runtime, credentials and old evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import tempfile

CADDY = Path('/etc/caddy/Caddyfile')
STATE = Path('/etc/day19')
CURRENT = Path('/opt/day19/current')
RELEASES = Path('/opt/day19/releases')
UNIT = Path('/etc/systemd/system/day19-composition.service')
REPORTS = Path('/var/lib/day19/reports')


def run(*args, env=None):
    return subprocess.run(args, check=True, text=True, capture_output=True, env=env).stdout.strip()


def checked_manifest(source):
    source = source.resolve()
    record = json.loads((source / 'manifest.json').read_text())
    for name, digest in record['files'].items():
        path = source / name
        if (path.is_symlink() or not path.resolve().is_relative_to(source)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError('manifest mismatch')
    expected = hashlib.sha256(json.dumps(record['files'], sort_keys=True).encode()).hexdigest()[:16]
    if record['revision'] != expected:
        raise ValueError('revision mismatch')
    return record


def caddy_environment(original):
    """Use Caddy's systemd Environment, never assume sudo inherited its variables.

    This installer supports the inspected Environment= setup. EnvironmentFiles
    require a separate review rather than guessing values or reading secrets.
    """
    if run('systemctl', 'show', 'caddy', '--property=EnvironmentFiles', '--value'):
        raise RuntimeError('Caddy EnvironmentFiles need review; no changes applied')
    raw = run('systemctl', 'show', 'caddy', '--property=Environment', '--value')
    values = dict(item.split('=', 1) for item in shlex.split(raw))
    required = set(re.findall(rb'\{\$([A-Za-z_][A-Za-z0-9_]*)\}', original))
    if b'{$' in re.sub(rb'\{\$[A-Za-z_][A-Za-z0-9_]*\}', b'', original):
        raise RuntimeError('Unsupported Caddy environment placeholder; review required')
    required = {name.decode('ascii') for name in required}
    if any(not values.get(name) for name in required):
        raise RuntimeError('Required Caddy variable missing from systemd Environment')
    # Only the referenced variables are relevant to the candidate.
    return {name: values[name] for name in required}


def candidate_bytes(source, original, host):
    if host.encode() in original or b'127.0.0.1:8019' in original:
        raise RuntimeError('Day 19 Caddy route already present; inspect state')
    fragment = (source / 'deploy/Caddyfile.fragment').read_text().replace('{$DAY19_MCP_PUBLIC_HOST}', host)
    # Append outside all existing site/global blocks. Keep original bytes intact.
    return original + b'\n' + fragment.encode()


def validate_candidate(content, environment):
    env = os.environ.copy()
    env.update(environment)
    with tempfile.TemporaryDirectory(prefix='day19-caddy-') as folder:
        candidate = Path(folder) / 'Caddyfile'
        candidate.write_bytes(content)
        run('caddy', 'validate', '--config', str(candidate), '--adapter', 'caddyfile', env=env)


def publish_caddy(original, content, environment):
    if CADDY.is_symlink() or CADDY.read_bytes() != original or caddy_environment(original) != environment:
        raise RuntimeError('Caddy file/environment changed; refusing overwrite')
    metadata = CADDY.stat()
    descriptor, name = tempfile.mkstemp(prefix='.day19-', dir=CADDY.parent)
    try:
        with os.fdopen(descriptor, 'wb') as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(name, metadata.st_mode & 0o777)
        os.chown(name, metadata.st_uid, metadata.st_gid)
        os.replace(name, CADDY)
    finally:
        Path(name).unlink(missing_ok=True)
    # If reload fails, preserve the candidate and backup; inspect instead of retry.
    run('systemctl', 'reload', 'caddy')


def check_partial(source, record, host, revision, original):
    """Read-only guards for the specific failure after service start, before Caddy."""
    import pwd
    if not re.fullmatch(r'[0-9a-f]{16}', revision):
        raise ValueError('Invalid previous revision')
    release = RELEASES / revision
    if not CURRENT.is_symlink() or CURRENT.resolve() != release or release.is_symlink():
        raise RuntimeError('Unexpected current release')
    old = checked_manifest(release)
    if old['revision'] != revision:
        raise RuntimeError('Previous revision mismatch')
    # Only the installer may differ. This recovery never updates runtime files.
    old_files = {k: v for k, v in old['files'].items() if k != 'deploy/install.py'}
    new_files = {k: v for k, v in record['files'].items() if k != 'deploy/install.py'}
    if old_files != new_files:
        raise RuntimeError('Runtime differs; Caddy-only recovery is not applicable')
    if UNIT.is_symlink() or UNIT.read_bytes() != (release / 'deploy/day19-composition.service').read_bytes():
        raise RuntimeError('Unexpected installed unit')
    if run('systemctl', 'is-active', 'day19-composition') != 'active':
        raise RuntimeError('Day 19 is not active')
    backup = STATE / 'Caddyfile.before-day19'
    if backup.is_symlink() or backup.read_bytes() != original:
        raise RuntimeError('Caddy differs from preserved backup; inspect before proceeding')
    env_path = STATE / 'composition.env'
    if env_path.is_symlink():
        raise RuntimeError('Unexpected environment symlink')
    values = dict(line.split('=', 1) for line in env_path.read_text().splitlines() if line and not line.startswith('#'))
    if values.get('DAY19_MCP_PUBLIC_HOST') != host or values.get('DAY19_REPORTS_DIR') != str(REPORTS) or not values.get('DAY19_MCP_TOKEN'):
        raise RuntimeError('Unexpected existing Day 19 configuration')
    user = pwd.getpwnam('day19')
    for folder in (REPORTS.parent, REPORTS):
        info = folder.stat()
        if folder.is_symlink() or not folder.is_dir() or (info.st_uid, info.st_gid, info.st_mode & 0o777) != (user.pw_uid, user.pw_gid, 0o700):
            raise RuntimeError('Unexpected reports directory ownership/mode')
    return release


def install(source, host, resume_caddy_from=None):
    if os.geteuid() != 0:
        raise SystemExit('Root required for separate service deployment.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*[a-z0-9]', host):
        raise ValueError('invalid host')
    source = Path(source).resolve()
    record = checked_manifest(source)
    original = CADDY.read_bytes()
    content = candidate_bytes(source, original, host)
    environment = caddy_environment(original)
    if resume_caddy_from:
        release = check_partial(source, record, host, resume_caddy_from, original)
        validate_candidate(content, environment)
        # New evidence path; old failed candidate and rollback backup stay intact.
        with (STATE / ('Caddyfile.resume-' + record['revision'])).open('xb') as file:
            file.write(content)
        publish_caddy(original, content, environment)
        print(json.dumps(dict(mode='caddy-only', runtime_revision=release.name,
            installer_revision=record['revision'], endpoint=f'https://{host}/mcp', day18_restarted=False)))
        return
    if any(p.exists() or p.is_symlink() for p in (CURRENT, STATE / 'composition.env', UNIT)):
        raise SystemExit('Day 19 already present: inspect state, do not repeat initial install.')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 8019))
    # Fail before user/release/credentials/service changes if the config is invalid.
    validate_candidate(content, environment)
    import pwd
    try:
        pwd.getpwnam('day19')
    except KeyError:
        run('useradd', '--system', '--user-group', '--home-dir', '/var/lib/day19', '--shell', '/usr/sbin/nologin', 'day19')
    user = pwd.getpwnam('day19')
    release = RELEASES / record['revision']
    release.mkdir(parents=True, exist_ok=False)
    for name in [*record['files'], 'manifest.json']:
        target = release / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        target.chmod(0o644)
    run('python3', '-m', 'venv', str(release / '.venv'))
    run(str(release / '.venv/bin/python'), '-m', 'pip', 'install', '-r', str(release / 'requirements.txt'))
    for folder in (REPORTS.parent, REPORTS):
        folder.mkdir(exist_ok=True)
        folder.chmod(0o700)
        os.chown(folder, user.pw_uid, user.pw_gid)
    STATE.mkdir(mode=0o750, exist_ok=True)
    os.chown(STATE, 0, user.pw_gid)
    env = STATE / 'composition.env'
    with env.open('x') as file:
        file.write(f'DAY19_MCP_PUBLIC_HOST={host}\nDAY19_MCP_TOKEN={secrets.token_urlsafe(48)}\nDAY19_REPORTS_DIR={REPORTS}\n')
    env.chmod(0o640)
    os.chown(env, 0, user.pw_gid)
    run('usermod', '-a', '-G', 'day19', 'aiadvent')
    CURRENT.symlink_to(release, target_is_directory=True)
    shutil.copyfile(release / 'deploy/day19-composition.service', UNIT)
    run('systemd-analyze', 'verify', str(UNIT))
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'day19-composition')
    with (STATE / 'Caddyfile.before-day19').open('xb') as file:
        file.write(original)
    with (STATE / 'Caddyfile.candidate').open('xb') as file:
        file.write(content)
    publish_caddy(original, content, environment)
    print(json.dumps(dict(revision=record['revision'], endpoint=f'https://{host}/mcp',
        old_caddy_sha256=hashlib.sha256(original).hexdigest(), day18_restarted=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('hostname')
    parser.add_argument('--resume-caddy-from', metavar='EXISTING_REVISION',
                        help='guarded Caddy-only recovery; preserve the existing runtime')
    args = parser.parse_args()
    try:
        install(args.source, args.hostname, args.resume_caddy_from)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f'{error.cmd[0]} failed ({error.returncode}): {error.stderr}') from error
