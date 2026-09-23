"""Local backend-environment probe: one native Responses summary, never create.

Run with backend/.venv Python. SSH agent must provide authorized VPS access.
The remote credential is captured in memory, placed in backend environment and
never echoed or stored in a local credential file.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
from app.dependency_watch_models import WatchRequest
from app.dependency_watch_service import DependencyWatchService


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ssh', required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / 'backend/.env')
    process = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
        args.ssh, 'cat /etc/day18/dependency-watch.env'], capture_output=True, text=True, timeout=15)
    if process.returncode:
        raise SystemExit('Cannot read protected VPS environment through authorized SSH.')
    remote = dict(line.split('=', 1) for line in process.stdout.splitlines() if line and not line.startswith('#'))
    os.environ['DAY18_MCP_TOKEN'] = remote['DAY18_MCP_TOKEN']
    os.environ['DAY18_MCP_SERVER_URL'] = 'https://' + remote['DAY18_MCP_PUBLIC_HOST'] + '/mcp'
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY is not configured in backend environment.')
    watch_id = str(uuid4())
    service = DependencyWatchService()
    try:
        operation = await service.run(WatchRequest(operation='summary', watch_id=watch_id,
            prompt=f'Получи сводку watch {watch_id} один раз. Если watch отсутствует, сообщи это. Ничего не создавай и не повторяй вызов.'))
    finally:
        await service.close()
    report = operation.model_dump(mode='json')
    report['readiness_only'] = True
    report['expected_missing_watch_id'] = watch_id
    text = json.dumps(report, ensure_ascii=False, indent=2)
    assert remote['DAY18_MCP_TOKEN'] not in text
    print(text)


if __name__ == '__main__':
    asyncio.run(main())
