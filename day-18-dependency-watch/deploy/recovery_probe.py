"""VPS recovery probes: pre needs sudo and reboots; post only reads. No OpenAI.

Two finite watches, one create call each, no retries. pre refuses existing evidence.
Token stays in protected VPS env and memory; never in output or command arguments.
"""
import argparse
from datetime import datetime, timezone
import grp
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import httpx

ENV = Path('/etc/day18/dependency-watch.env')
EVIDENCE = Path('/var/lib/day18-probes/recovery.json')
RELEASE = Path('/opt/day18/current')


def now():
    return datetime.now(timezone.utc).isoformat()


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=60).stdout.strip()


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def values():
    return dict(line.split('=', 1) for line in ENV.read_text().splitlines()
                if line and not line.startswith('#'))


def set_short(enabled):
    lines = ENV.read_text().splitlines()
    assert sum(line.startswith('DAY18_ALLOW_SHORT_INTERVALS=') for line in lines) == 1
    content = '\n'.join('DAY18_ALLOW_SHORT_INTERVALS=' + str(enabled).lower()
                        if line.startswith('DAY18_ALLOW_SHORT_INTERVALS=') else line for line in lines) + '\n'
    with ENV.open('w') as file:  # Retain protected owner/mode.
        file.write(content)
        file.flush()
        os.fsync(file.fileno())


class Probe:
    def __init__(self):
        self.config = values()
        self.token = self.config['DAY18_MCP_TOKEN']
        self.base = 'https://' + self.config['DAY18_MCP_PUBLIC_HOST']
        self.client = httpx.Client(timeout=20, trust_env=False, follow_redirects=False,
            headers={'Authorization': 'Bearer ' + self.token,
                     'Accept': 'application/json, text/event-stream'})
        self.report = {'started_at': now(), 'boot_before': boot_id(), 'calls': []}

    def safe_json(self, value):
        encoded = json.dumps(value, ensure_ascii=False, indent=2)
        assert self.token not in encoded
        return encoded

    def save(self):
        temporary = EVIDENCE.with_suffix('.tmp')
        with temporary.open('w') as file:
            file.write(self.safe_json(self.report) + '\n')
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, 0o640)
        os.chown(temporary, 0, grp.getgrnam('day18').gr_gid)
        temporary.replace(EVIDENCE)
        fd = os.open(EVIDENCE.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def health(self):
        deadline = time.monotonic() + 40
        while True:
            response = self.client.get(self.base + '/health')
            if response.status_code == 200:
                assert response.json() == {'status': 'ok'}
                return
            assert response.status_code in (502, 503), 'Unexpected health status'
            assert time.monotonic() < deadline, 'Service did not become ready'
            time.sleep(1)  # Health polling only; TLS errors stop the probe.

    def call(self, name, arguments, persist=False):
        attempt = {'at': now(), 'name': name, 'arguments': arguments, 'outcome': 'unknown'}
        if persist:
            self.report['calls'].append(attempt)
            self.save()  # Write-ahead evidence even for unknown create outcome.
        response = self.client.post(self.base + '/mcp', json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments}})
        response.raise_for_status()
        result = response.json()
        if persist:
            attempt.update(outcome='received', result=result, completed_at=now())
            self.save()
        assert 'error' not in result and not result['result'].get('isError'), 'MCP tool error'
        return result['result']['structuredContent']

    def summary(self, watch_id):
        result = self.call('get_dependency_watch_summary', {'watch_id': watch_id})
        assert result['watch_id'] == watch_id
        runs = result['executions']
        assert result['runs_total'] == len(runs) == result['successful'] + result['failed']
        assert result['through_execution_id'] == (runs[-1]['run_id'] if runs else None)
        assert len({run['scheduled_at'] for run in runs}) == len(runs)
        assert result['interrupted'] == sum(run['error_category'] == 'interrupted' for run in runs)
        for run in runs:
            offset = (datetime.fromisoformat(run['scheduled_at']) -
                      datetime.fromisoformat(result['created_at'])).total_seconds()
            assert offset > 0 and offset % result['interval_seconds'] == 0
        if result['status'] == 'completed':
            assert result['runs_total'] == result['max_runs'] and result['next_run_at'] is None
        else:
            assert result['runs_total'] < result['max_runs'] and result['next_run_at'] is not None
        return result

    def wait_runs(self, watch_id, count):
        deadline = time.monotonic() + 150
        while True:
            result = self.summary(watch_id)
            if result['runs_total'] >= count:
                return result
            assert time.monotonic() < deadline, 'Timed out waiting for scheduled execution'
            time.sleep(1)

    def create(self):
        receipt = self.call('create_dependency_watch', {'group_id': 'androidx.core',
            'artifact_id': 'core-ktx', 'interval_seconds': 30, 'max_runs': 2}, persist=True)
        assert receipt['max_runs'] == 2 and receipt['runs_total'] == 0
        return receipt['watch_id']

    def snapshot(self, watch_id):
        summary = self.summary(watch_id)
        with sqlite3.connect('file:' + self.config['DAY18_DATABASE_PATH'] + '?mode=ro', uri=True) as db:
            row = db.execute('SELECT aggregate_json FROM watches WHERE watch_id=?', (watch_id,)).fetchone()
        assert all(summary[key] == value for key, value in json.loads(row[0]).items())
        return summary


def preserved(before, after):
    assert before['watch_id'] == after['watch_id']
    assert after['executions'][:len(before['executions'])] == before['executions']


def pre(probe):
    assert os.geteuid() == 0, 'pre requires sudo'
    assert not EVIDENCE.exists(), 'Existing evidence: inspect; never repeat create blindly'
    assert values()['DAY18_ALLOW_SHORT_INTERVALS'] == 'false', 'Expected normal configuration'
    EVIDENCE.parent.mkdir(mode=0o750, exist_ok=True)
    os.chown(EVIDENCE.parent, 0, grp.getgrnam('day18').gr_gid)
    probe.save()
    try:
        manifest = json.loads((RELEASE / 'snapshot-manifest.json').read_text())
        assert all(hashlib.sha256((RELEASE / name).read_bytes()).hexdigest() == digest
                   for name, digest in manifest.items()), 'Deployed manifest mismatch'
        probe.report['deployment'] = {'release': str(RELEASE.resolve()), 'manifest': manifest,
            'packages': command(str(RELEASE / '.venv/bin/python'), '-m', 'pip', 'freeze'),
            'firewall': command('ufw', 'status', 'verbose'),
            'sshd': [line for line in command('/usr/sbin/sshd', '-T').splitlines()
                     if line.split()[0] in {'passwordauthentication', 'kbdinteractiveauthentication',
                                           'permitrootlogin', 'pubkeyauthentication'}],
            'listeners': command('ss', '-ltn'),
            'enabled': command('systemctl', 'is-enabled', 'day18-watch', 'caddy')}
        probe.save()
        set_short(True)
        command('systemctl', 'restart', 'day18-watch')
        probe.health()
        restart_id = probe.create()
        probe.wait_runs(restart_id, 1)
        before = probe.snapshot(restart_id)
        assert before['status'] == 'active' and before['runs_total'] == 1
        pid = command('systemctl', 'show', 'day18-watch', '-p', 'MainPID', '--value')
        probe.report['restart'] = {'before': before, 'pid_before': pid, 'at': now()}
        probe.save()
        command('systemctl', 'restart', 'day18-watch')
        probe.health()
        after = probe.snapshot(restart_id)
        preserved(before, after)
        new_pid = command('systemctl', 'show', 'day18-watch', '-p', 'MainPID', '--value')
        assert pid != new_pid and new_pid != '0'
        probe.report['restart'].update(after_startup=after, pid_after=new_pid)
        probe.wait_runs(restart_id, 2)
        completed = probe.snapshot(restart_id)
        preserved(before, completed)
        assert completed['status'] == 'completed'
        probe.report['restart']['completed'] = completed
        probe.save()
        reboot_id = probe.create()
        probe.wait_runs(reboot_id, 1)
        before = probe.snapshot(reboot_id)
        assert before['status'] == 'active' and before['runs_total'] == 1
        probe.report['reboot'] = {'before': before, 'requested_at': now()}
        set_short(False)
        probe.report['normal_configuration_restored'] = True
        probe.report['phase'] = 'awaiting_reboot'
        probe.save()
    except BaseException:
        set_short(False)
        command('systemctl', 'restart', 'day18-watch')
        probe.report['phase'] = 'failed_before_reboot'
        probe.save()
        raise
    print('Restart probe recorded; two bounded watches created. Normal configuration restored. Rebooting.', flush=True)
    command('systemctl', 'reboot')


def post(probe):
    report = json.loads(EVIDENCE.read_text())
    assert report['phase'] == 'awaiting_reboot'
    assert boot_id() != report['boot_before'], 'VPS has not rebooted'
    assert values()['DAY18_ALLOW_SHORT_INTERVALS'] == 'false'
    probe.health()
    before = report['reboot']['before']
    immediate = probe.summary(before['watch_id'])
    preserved(before, immediate)
    completed = probe.wait_runs(before['watch_id'], 2)
    preserved(before, completed)
    assert completed['status'] == 'completed'
    boot_seconds = int(next(line.split()[1] for line in Path('/proc/stat').read_text().splitlines()
                            if line.startswith('btime ')))
    assert datetime.fromisoformat(completed['executions'][-1]['started_at']).timestamp() >= boot_seconds
    report['reboot'].update(after_first_read=immediate, completed=completed, boot_after=boot_id(),
        services=command('systemctl', 'is-active', 'day18-watch', 'caddy'), checked_at=now())
    report['phase'] = 'passed'
    print(probe.safe_json(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['pre', 'post'])
    args = parser.parse_args()
    probe = Probe()
    try:
        (pre if args.phase == 'pre' else post)(probe)
    finally:
        probe.client.close()
