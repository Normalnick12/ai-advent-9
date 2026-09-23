"""Print source SHA256 manifest, excluding secrets, local data and environments."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["lookup.py", "watch_models.py", "storage.py", "scheduler.py", "server.py", "run.py",
         "requirements.txt", "deploy/day18-watch.service", "deploy/Caddyfile"]
print(json.dumps({name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                  for name in FILES}, indent=2, sort_keys=True))
