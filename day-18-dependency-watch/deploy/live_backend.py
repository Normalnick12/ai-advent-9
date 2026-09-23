"""Start the local backend with a VPS credential in memory; no model requests.

Run manually from Windows PowerShell when Codex cannot reach SSH. Keep this
terminal open. Use --phase summary to start again after the background window.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[2]


def ssh_failure_reason(stderr):
    # Classify known diagnostics; never echo captured stdout or arbitrary stderr.
    lowered = stderr.lower()
    checks = [
        ('permission denied (', 'SSH authentication denied; check the Windows SSH agent/key.'),
        ('host key verification failed', 'SSH host key verification failed; review known_hosts.'),
        ('remote host identification has changed', 'SSH host key changed; stop for host verification.'),
        ('could not resolve hostname', 'SSH hostname resolution failed.'),
        ('connection timed out', 'SSH connection timed out before remote execution.'),
        ('connection refused', 'SSH connection refused.'),
        ('connection reset', 'SSH connection reset.'),
        ('permissionerror', 'Remote Python could not read the protected env; check day18 group membership.'),
        ('filenotfounderror', 'Remote Python reported a missing file or executable.'),
        ('syntaxerror', 'Remote Python command failed to parse.'),
        ('python3: not found', 'Remote python3 is unavailable.'),
    ]
    return next((reason for marker, reason in checks if marker in lowered),
                'Unclassified SSH/remote-command failure; run the non-secret SSH diagnostic below.')


def find_powershell(explicit=None):
    candidates = [explicit] if explicit else [shutil.which('pwsh')]
    if not explicit:
        for variable in ('ProgramFiles', 'ProgramW6432'):
            if os.getenv(variable):
                candidates.append(Path(os.environ[variable]) / 'PowerShell/7/pwsh.exe')
        runtimes = Path.home() / '.cache/codex-runtimes'
        candidates.extend(sorted(runtimes.glob('*/dependencies/native/powershell/pwsh.exe')))
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        executable = str(Path(candidate).resolve())
        try:
            version = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command',
                '$PSVersionTable.PSVersion.Major'], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if version.returncode == 0 and version.stdout.strip().isdigit() and int(version.stdout.strip()) >= 7:
            return executable
    raise SystemExit('PowerShell 7 not found. Supply --pwsh with its full executable path. No SSH/model request sent.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh', required=True)
    parser.add_argument('--phase', choices=['create', 'summary'], required=True)
    parser.add_argument('--pwsh', help='Optional full path to PowerShell 7 executable')
    args = parser.parse_args()
    powershell = find_powershell(args.pwsh)  # Fail before SSH or reading credentials.
    evidence = ROOT / '.local/day18-live'
    evidence.mkdir(parents=True, exist_ok=True)
    if args.phase == 'create' and list((ROOT / 'backend/.local/day18/evidence').glob('*.attempt')):
        raise SystemExit('Existing Responses attempt evidence: stop for review, not another create.')
    remote_code = (
        "import json,pathlib,datetime,subprocess; "
        "print(json.dumps({'env':pathlib.Path('/etc/day18/dependency-watch.env').read_text(),"
        "'server_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),"
        "'ntp_synchronized':subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()}))"
    )
    before = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=yes', args.ssh, "python3 -c \"" + remote_code + "\""],
            capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        raise SystemExit('SSH timeout before backend start; no model request sent.') from None
    after = datetime.now(timezone.utc).isoformat()
    if result.returncode:
        reason = ssh_failure_reason(result.stderr)
        failure = {'phase': args.phase, 'client_before_ssh': before, 'client_after_ssh': after,
                   'ssh_exit_code': result.returncode, 'reason': reason, 'model_requests': 0}
        with (evidence / f'ssh-failure-{uuid4()}.json').open('x', encoding='utf-8') as file:
            json.dump(failure, file, ensure_ascii=False, indent=2)
        raise SystemExit(f'SSH failed (exit {result.returncode}): {reason} No model request sent.')
    remote = json.loads(result.stdout)
    env = dict(line.split('=', 1) for line in remote['env'].splitlines() if line and not line.startswith('#'))
    if args.phase == 'create' and env['DAY18_ALLOW_SHORT_INTERVALS'] != 'true':
        raise SystemExit('Short intervals disabled: stop before create. No model request sent.')
    token = env['DAY18_MCP_TOKEN']
    host = env['DAY18_MCP_PUBLIC_HOST']
    url = 'https://' + host
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        health = client.get(url + '/health')
        health.raise_for_status()
        assert health.json() == {'status': 'ok'}
        discovery = client.post(url + '/mcp', headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/event-stream'},
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        discovery.raise_for_status()
        tools = discovery.json()['result']['tools']
        assert {tool['name'] for tool in tools} == {'create_dependency_watch', 'get_dependency_watch_summary'}
    report = {'phase': args.phase, 'client_before_ssh': before, 'client_after_ssh': after,
        'server_utc': remote['server_utc'], 'ntp_synchronized': remote['ntp_synchronized'],
        'short_intervals': env['DAY18_ALLOW_SHORT_INTERVALS'], 'endpoint': url + '/mcp',
        'health': health.json(), 'tools': tools, 'model_requests': 0}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    assert token not in encoded
    # Readiness may be repeated before any model attempt; preserve every observation.
    preflight = evidence / f'{args.phase}-preflight-{uuid4()}.json'
    with preflight.open('x', encoding='utf-8') as file:
        file.write(encoded + '\n')
    os.environ['DAY18_MCP_TOKEN'] = token
    os.environ['DAY18_MCP_SERVER_URL'] = url + '/mcp'
    print('Readiness passed; credential set only in backend environment. No model requests sent.', flush=True)
    # dev.ps1 owns the backend session/lock and loads backend/.env for OPENAI_API_KEY.
    return subprocess.call([powershell, '-NoProfile', '-File', str(ROOT / 'scripts/dev.ps1'), 'backend'], cwd=ROOT)


if __name__ == '__main__':
    sys.exit(main())
