"""Collect read-only VPS evidence through interactive SSH sudo; no model/MCP calls.

The remote Python program runs from memory with -B; no files are written on VPS.
The local JSON excludes sudo prompts. Password is entered only in the SSH terminal.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
BEGIN = 'DAY18_LIVE_EVIDENCE_BEGIN'
END = 'DAY18_LIVE_EVIDENCE_END'
REMOTE = r'''
from datetime import datetime, timezone
import hashlib, json, pathlib, sqlite3, subprocess, sys
sys.path.insert(0, '/opt/day18/current')
from storage import aggregate
watch_id, since = sys.argv[1:]
config = dict(line.split('=', 1) for line in pathlib.Path('/etc/day18/dependency-watch.env').read_text().splitlines() if line and not line.startswith('#'))
with sqlite3.connect('file:' + config['DAY18_DATABASE_PATH'] + '?mode=ro', uri=True) as db:
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    watch = db.execute('SELECT * FROM watches WHERE watch_id=?', (watch_id,)).fetchone()
    assert watch is not None, 'Watch absent from SQLite'
    runs = db.execute('SELECT * FROM executions WHERE watch_id=? ORDER BY scheduled_at,run_id', (watch_id,)).fetchall()
    saved = json.loads(watch['aggregate_json'])
    generated_ms = int(datetime.fromisoformat(saved['generated_at']).timestamp() * 1000)
    recomputed = aggregate([row for row in runs if row['state'] != 'running'], generated_ms).model_dump(mode='json')
    report = {'watch': dict(watch), 'executions': [dict(row) for row in runs],
              'persisted_aggregate': saved, 'recomputed_aggregate': recomputed,
              'aggregate_matches': saved == recomputed}
end = datetime.now(timezone.utc)
logs = subprocess.check_output(['journalctl', '-u', 'day18-watch', '--since', since,
    '--until', end.strftime('%Y-%m-%d %H:%M:%S UTC'), '--no-pager', '-o', 'json'], text=True)
report['journal'] = [{key: item.get(key) for key in ('__REALTIME_TIMESTAMP', '_BOOT_ID', 'MESSAGE')}
                     for line in logs.splitlines() if line for item in [json.loads(line)]]
release = pathlib.Path('/opt/day18/current')
manifest = json.loads((release / 'snapshot-manifest.json').read_text())
report.update(collected_at=end.isoformat(), release=str(release.resolve()), manifest=manifest,
    manifest_matches=all(hashlib.sha256((release / name).read_bytes()).hexdigest()==digest for name,digest in manifest.items()),
    short_intervals=config['DAY18_ALLOW_SHORT_INTERVALS'],
    boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip())
encoded = json.dumps(report, ensure_ascii=True)
assert config['DAY18_MCP_TOKEN'] not in encoded
print('DAY18_LIVE_EVIDENCE_BEGIN', flush=True)
print(encoded, flush=True)
print('DAY18_LIVE_EVIDENCE_END', flush=True)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh', required=True)
    args=parser.parse_args()
    directory=ROOT/'.local/day18-live'
    window=json.loads((directory/'background-window.json').read_text(encoding='utf-8-sig'))
    assert datetime.now(timezone.utc)>=datetime.fromisoformat(window['background_window_not_before_end']), 'Background window still active'
    assert len(window['watch_ids'])==1, 'Review multiple/unknown watch IDs first'
    watch=str(UUID(window['watch_ids'][0]))
    since=datetime.fromisoformat(window['response_completed_at']).strftime('%Y-%m-%d %H:%M:%S UTC')
    program='import base64;exec(base64.b64decode(' + repr(base64.b64encode(REMOTE.encode()).decode()) + '))'
    command='sudo /opt/day18/current/.venv/bin/python -B -c ' + shlex.quote(program) + ' ' + shlex.quote(watch) + ' ' + shlex.quote(since)
    print('Read-only SQLite/journal export. Enter sudo password only at the SSH prompt.', flush=True)
    process=subprocess.Popen(['ssh','-t','-o','StrictHostKeyChecking=yes',args.ssh,command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    output=bytearray()
    show_prompt=True
    while chunk:=process.stdout.read(1):
        output.extend(chunk)
        if show_prompt:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            if output.endswith(BEGIN.encode()):
                show_prompt=False
                print('\nReceiving safe evidence...', flush=True)
    if process.wait():
        raise SystemExit('SSH export failed; no model request sent.')
    text=output.decode('utf-8',errors='replace')
    assert text.count(BEGIN)==1 and text.count(END)==1, 'Missing/ambiguous evidence markers'
    report=json.loads(text.split(BEGIN,1)[1].split(END,1)[0].strip())
    path=directory/'vps-live-evidence.json'
    with path.open('x',encoding='utf-8') as file:
        json.dump(report,file,ensure_ascii=False,indent=2)
    print('\nSaved:',path)
    print(json.dumps({'watch_id':report['watch']['watch_id'],'status':report['watch']['status'],
        'runs_total':report['persisted_aggregate']['runs_total'],'successful':report['persisted_aggregate']['successful'],
        'failed':report['persisted_aggregate']['failed'],'aggregate_matches':report['aggregate_matches'],
        'manifest_matches':report['manifest_matches']},indent=2))


if __name__=='__main__':
    main()
