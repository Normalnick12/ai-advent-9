"""Operator-only lossless read. No MCP, model or production storage imports."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path("/var/lib/day19/reports")


def collect(file_id, *, operation_id, lookup_id, revision, endpoint, root=ROOT):
    if not re.fullmatch(r"[0-9a-f]{64}", file_id):
        raise ValueError("invalid_file_id")
    root = Path(os.path.abspath(root))
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("symlink_root")
    target = root / (file_id + ".json")
    result = dict(operation_id=operation_id, lookup_id=lookup_id, revision=revision, endpoint=endpoint,
                  file_id=file_id, read_at=datetime.now(timezone.utc).isoformat())
    try:
        if target.is_symlink():
            raise OSError("symlink")
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        with os.fdopen(fd, "rb") as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise OSError("nonregular")
            data = file.read()
        return dict(result, status="read", bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    base64=base64.b64encode(data).decode("ascii"))
    except FileNotFoundError:
        return dict(result, status="missing")
    except OSError:
        return dict(result, status="unavailable")


def collect_events(since):
    # Fixed unit, argument vector (no shell), journal messages contain safe server events only.
    raw = subprocess.run(["journalctl", "-u", "day19-composition", "--since", since,
                          "--no-pager", "-o", "cat"], capture_output=True, text=True, check=True).stdout
    events = []
    for line in raw.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("event") in ("tool_start", "tool_end", "google_maven_lookup"):
            events.append(value)
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    disk = sub.add_parser("file")
    for key in ("file_id", "operation_id", "lookup_id", "revision", "endpoint"):
        disk.add_argument(key)
    logs = sub.add_parser("events")
    logs.add_argument("since")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(collect(**args) if command == "file" else collect_events(**args), ensure_ascii=True))
