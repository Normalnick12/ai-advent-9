"""Deployment regression only; no root, services, network or model calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('day19_install', ROOT / 'deploy/install.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
HOST = 'day19-132-243-120-220.sslip.io'
OLD_HOST = '132-243-120-220.sslip.io'
ORIGINAL = b'{$DAY18_MCP_PUBLIC_HOST} {\n    reverse_proxy 127.0.0.1:8018\n}\n'
GLOBAL = b'{\n    admin localhost:2019\n}\n\n'


def service_env(monkeypatch, value=None, files=''):
    def run(*args, **kwargs):
        assert args[:3] == ('systemctl', 'show', 'caddy')
        return files if '--property=EnvironmentFiles' in args else (value or '')
    monkeypatch.setattr(d, 'run', run)


def test_existing_global_block_is_preserved(monkeypatch):
    original = GLOBAL + ORIGINAL
    service_env(monkeypatch, 'DAY18_MCP_PUBLIC_HOST=' + OLD_HOST)
    monkeypatch.delenv('DAY18_MCP_PUBLIC_HOST', raising=False)
    assert d.caddy_environment(original) == {'DAY18_MCP_PUBLIC_HOST': OLD_HOST}
    candidate = d.candidate_bytes(ROOT, original, HOST)
    assert candidate.startswith(original + b'\n')
    assert candidate.count(b'127.0.0.1:8018') == candidate.count(b'127.0.0.1:8019') == 1
    assert ('\n' + HOST + ' {\n').encode() in candidate


@pytest.mark.parametrize('raw', ['', 'DAY18_MCP_PUBLIC_HOST='])
def test_missing_service_env_not_replaced_with_ambient(monkeypatch, raw):
    service_env(monkeypatch, raw)
    monkeypatch.setenv('DAY18_MCP_PUBLIC_HOST', 'wrong.example')
    with pytest.raises(RuntimeError, match='variable missing'):
        d.caddy_environment(ORIGINAL)


def test_environment_files_require_review(monkeypatch):
    service_env(monkeypatch, files='/etc/caddy/private.env (ignore_errors=no)')
    with pytest.raises(RuntimeError, match='EnvironmentFiles'):
        d.caddy_environment(ORIGINAL)


def test_validate_passes_service_env_and_cleans_temp(monkeypatch):
    paths = []
    def run(*args, **kwargs):
        paths.append(Path(args[3]))
        assert paths[-1].read_bytes() == GLOBAL + ORIGINAL
        assert kwargs['env']['DAY18_MCP_PUBLIC_HOST'] == OLD_HOST
        raise subprocess.CalledProcessError(1, args, stderr='invalid configuration')
    monkeypatch.setattr(d, 'run', run)
    monkeypatch.setenv('DAY18_MCP_PUBLIC_HOST', 'wrong.example')
    with pytest.raises(subprocess.CalledProcessError):
        d.validate_candidate(GLOBAL + ORIGINAL, {'DAY18_MCP_PUBLIC_HOST': OLD_HOST})
    assert not paths[0].exists()


def test_initial_validation_failure_precedes_service_mutations(monkeypatch, tmp_path):
    monkeypatch.setattr(d.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(d, 'checked_manifest', lambda _: {'revision': 'a' * 16, 'files': {}})
    for name in ('CADDY', 'STATE', 'CURRENT', 'UNIT', 'RELEASES'):
        monkeypatch.setattr(d, name, tmp_path / name)
    d.CADDY.write_bytes(ORIGINAL)
    monkeypatch.setattr(d, 'caddy_environment', lambda _: {'DAY18_MCP_PUBLIC_HOST': OLD_HOST})
    class Probe:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def bind(self, address): assert address == ('127.0.0.1', 8019)
    monkeypatch.setattr(d.socket, 'socket', Probe)
    def fail(*args): raise RuntimeError('validation failed')
    monkeypatch.setattr(d, 'validate_candidate', fail)
    monkeypatch.setattr(d, 'run', lambda *args, **kwargs: pytest.fail('service mutation before validation'))
    with pytest.raises(RuntimeError, match='validation failed'):
        d.install(ROOT, HOST)
    assert list(tmp_path.iterdir()) == [d.CADDY]


def write_manifest(root, installer):
    root.mkdir(parents=True)
    files = {'run.py': b'runtime', 'deploy/install.py': installer,
             'deploy/day19-composition.service': b'unit'}
    for name, value in files.items():
        target = root / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(value)
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
    revision = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    record = dict(revision=revision, files=hashes)
    (root / 'manifest.json').write_text(json.dumps(record))
    return record


@pytest.fixture
def partial(monkeypatch, tmp_path):
    for name in ('CADDY', 'STATE', 'CURRENT', 'UNIT', 'RELEASES'):
        monkeypatch.setattr(d, name, tmp_path / name)
    d.STATE.mkdir()
    d.RELEASES.mkdir()
    temporary = d.RELEASES / 'build'
    old = write_manifest(temporary, b'old installer')
    release = d.RELEASES / old['revision']
    temporary.rename(release)
    d.CURRENT.symlink_to(release, target_is_directory=True)
    d.UNIT.write_bytes(b'unit')
    d.CADDY.write_bytes(ORIGINAL)
    (d.STATE / 'Caddyfile.before-day19').write_bytes(ORIGINAL)
    (d.STATE / 'Caddyfile.candidate').write_bytes(b'old failed candidate')
    (d.STATE / 'composition.env').write_text(f'DAY19_MCP_PUBLIC_HOST={HOST}\nDAY19_MCP_TOKEN=test-only\nDAY19_REPORTS_DIR={d.REPORTS}\n')
    # POSIX ownership is unavailable on Windows; model only these two stat calls.
    user = SimpleNamespace(pw_uid=994, pw_gid=987)
    monkeypatch.setitem(sys.modules, 'pwd', SimpleNamespace(getpwnam=lambda _: user))
    stat, is_dir = Path.stat, Path.is_dir
    def metadata(path, *args, **kwargs):
        if path in (d.REPORTS.parent, d.REPORTS):
            return SimpleNamespace(st_uid=994, st_gid=987, st_mode=0o40700)
        return stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', metadata)
    monkeypatch.setattr(Path, 'is_dir', lambda path: True if path in (d.REPORTS.parent, d.REPORTS) else is_dir(path))
    monkeypatch.setattr(d, 'run', lambda *args, **kwargs: 'active')
    new_source = tmp_path / 'new'
    new = write_manifest(new_source, b'new installer')
    return new_source, new, old, release


def test_partial_accepts_only_installer_change(partial):
    source, record, old, release = partial
    assert d.check_partial(source, record, HOST, old['revision'], ORIGINAL) == release


@pytest.mark.parametrize('changed', ['runtime', 'unit', 'backup', 'host', 'manifest', 'revision'])
def test_partial_refuses_drift(partial, changed):
    source, record, old, release = partial
    if changed == 'runtime': record['files']['run.py'] = 'f' * 64
    if changed == 'unit': d.UNIT.write_bytes(b'changed')
    if changed == 'backup': (d.STATE / 'Caddyfile.before-day19').write_bytes(b'changed')
    if changed == 'host': (d.STATE / 'composition.env').write_text('DAY19_MCP_PUBLIC_HOST=wrong.example')
    if changed == 'manifest': (release / 'run.py').write_bytes(b'changed')
    revision = '0' * 16 if changed == 'revision' else old['revision']
    with pytest.raises((RuntimeError, ValueError)):
        d.check_partial(source, record, HOST, revision, ORIGINAL)


def test_resume_preserves_old_evidence_and_runtime(monkeypatch, partial):
    source, record, old, release = partial
    monkeypatch.setattr(d.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(d, 'candidate_bytes', lambda *args: b'new candidate')
    monkeypatch.setattr(d, 'caddy_environment', lambda _: {'DAY18_MCP_PUBLIC_HOST': OLD_HOST})
    calls = []
    monkeypatch.setattr(d, 'validate_candidate', lambda *args: calls.append('validate'))
    monkeypatch.setattr(d, 'publish_caddy', lambda *args: calls.append('publish'))
    d.install(source, HOST, old['revision'])
    assert calls == ['validate', 'publish']
    assert (d.STATE / ('Caddyfile.resume-' + record['revision'])).read_bytes() == b'new candidate'
    assert (d.STATE / 'Caddyfile.candidate').read_bytes() == b'old failed candidate'
    assert (d.STATE / 'Caddyfile.before-day19').read_bytes() == ORIGINAL
    assert d.CURRENT.resolve() == release
    assert d.checked_manifest(release) == old
    calls.clear()
    with pytest.raises(FileExistsError): d.install(source, HOST, old['revision'])
    assert calls == ['validate']  # Refuse blind repeat, do not republish.


@pytest.mark.parametrize('drift', ['file', 'environment'])
def test_publish_refuses_drift_before_write(monkeypatch, tmp_path, drift):
    monkeypatch.setattr(d, 'CADDY', tmp_path / 'Caddyfile')
    original = ORIGINAL
    d.CADDY.write_bytes(b'changed' if drift == 'file' else original)
    monkeypatch.setattr(d, 'caddy_environment', lambda _: {'DAY18_MCP_PUBLIC_HOST': 'changed'})
    monkeypatch.setattr(d, 'run', lambda *args, **kwargs: pytest.fail('must not reload'))
    before = d.CADDY.read_bytes()
    with pytest.raises(RuntimeError, match='changed'):
        d.publish_caddy(original, b'candidate', {'DAY18_MCP_PUBLIC_HOST': OLD_HOST})
    assert d.CADDY.read_bytes() == before


def test_resume_validation_failure_preserves_everything(monkeypatch, partial):
    source, record, old, release = partial
    monkeypatch.setattr(d.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(d, 'candidate_bytes', lambda *args: b'new candidate')
    monkeypatch.setattr(d, 'caddy_environment', lambda _: {'DAY18_MCP_PUBLIC_HOST': OLD_HOST})
    def fail(*args): raise RuntimeError('validation failed')
    monkeypatch.setattr(d, 'validate_candidate', fail)
    monkeypatch.setattr(d, 'publish_caddy', lambda *args: pytest.fail('must not publish'))
    before = {p.name: p.read_bytes() for p in d.STATE.iterdir()}
    with pytest.raises(RuntimeError, match='validation failed'):
        d.install(source, HOST, old['revision'])
    assert {p.name: p.read_bytes() for p in d.STATE.iterdir()} == before
    assert d.CADDY.read_bytes() == ORIGINAL
    assert d.checked_manifest(release) == old


@pytest.mark.parametrize('reload_fails', [False, True])
def test_publication_is_complete_before_reload(monkeypatch, tmp_path, reload_fails):
    monkeypatch.setattr(d, 'CADDY', tmp_path / 'Caddyfile')
    d.CADDY.write_bytes(ORIGINAL)
    env = {'DAY18_MCP_PUBLIC_HOST': OLD_HOST}
    monkeypatch.setattr(d, 'caddy_environment', lambda _: env)
    monkeypatch.setattr(d.os, 'chown', lambda *args: None, raising=False)
    calls = []
    def run(*args, **kwargs):
        assert args == ('systemctl', 'reload', 'caddy')
        assert d.CADDY.read_bytes() == b'complete candidate'
        calls.append(args)
        if reload_fails: raise subprocess.CalledProcessError(1, args, stderr='reload failed')
    monkeypatch.setattr(d, 'run', run)
    if reload_fails:
        with pytest.raises(subprocess.CalledProcessError):
            d.publish_caddy(ORIGINAL, b'complete candidate', env)
    else:
        d.publish_caddy(ORIGINAL, b'complete candidate', env)
    assert len(calls) == 1
    assert d.CADDY.read_bytes() == b'complete candidate'
    assert list(tmp_path.iterdir()) == [d.CADDY]
