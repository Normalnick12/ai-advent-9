"""Run on VPS with the release venv. Emits only non-secret readiness evidence."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import socket
import sys

import httpx

ENV = Path('/etc/day18/dependency-watch.env')
values = dict(line.split('=', 1) for line in ENV.read_text().splitlines() if line and not line.startswith('#'))
host, token = values['DAY18_MCP_PUBLIC_HOST'], values['DAY18_MCP_TOKEN']
url = f'https://{host}/mcp'
headers = {'Accept': 'application/json, text/event-stream'}
report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'endpoint': url}

with socket.create_connection((host, 443), timeout=10) as tcp:
    with ssl.create_default_context().wrap_socket(tcp, server_hostname=host) as tls:
        cert = tls.getpeercert()
        report['tls'] = {'protocol': tls.version(), 'issuer': cert['issuer'],
                         'subject_alt_names': cert['subjectAltName'], 'not_after': cert['notAfter']}

with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
    health = client.get(f'https://{host}/health')
    health.raise_for_status()
    assert health.json() == {'status': 'ok'}
    report['health'] = health.json()
    init = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2025-11-25', 'capabilities': {},
        'clientInfo': {'name': 'day18-readiness', 'version': '1'}}}
    for label, authorization in [('missing', None), ('invalid', 'Bearer synthetic-invalid')]:
        check_headers = headers | ({'Authorization': authorization} if authorization else {})
        response = client.post(url, json=init, headers=check_headers)
        assert response.status_code == 401, label
        report[f'auth_{label}'] = response.status_code
    authorized = headers | {'Authorization': 'Bearer ' + token}
    response = client.post(url, json=init, headers=authorized)
    response.raise_for_status()
    assert 'result' in response.json()
    report['initialize'] = response.json()['result']
    response = client.post(url, json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, headers=authorized)
    response.raise_for_status()
    tools = response.json()['result']['tools']
    indexed = {tool['name']: tool for tool in tools}
    assert set(indexed) == {'create_dependency_watch', 'get_dependency_watch_summary'}
    create = indexed['create_dependency_watch']
    assert 'max_runs' in create['inputSchema']['required']
    assert create['annotations']['idempotentHint'] is False
    assert indexed['get_dependency_watch_summary']['annotations']['readOnlyHint'] is True
    report['tools'] = tools
    response = client.post('http://127.0.0.1:8018/mcp', json=init, headers=authorized | {'Host': 'foreign.invalid'})
    assert response.status_code == 421
    report['foreign_host'] = response.status_code

sys.path.insert(0, '/opt/day18/current')
from lookup import lookup
result = asyncio.run(lookup('androidx.core', 'core-ktx'))
report['upstream'] = {'status': result.status, 'version_count': len(result.versions),
                      'lookup_id': result.lookup_id, 'checked_at_ms': result.checked_at}
assert result.status == 'found'
encoded = json.dumps(report, ensure_ascii=False, indent=2)
assert token not in encoded
print(encoded)
