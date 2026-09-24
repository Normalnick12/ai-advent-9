"""Run on VPS as day19 or root. No model requests; no report/watch creation."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import tempfile
from datetime import datetime, timezone

import httpx


def readiness():
    release = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(release))
    from composition.server import NAMES
    values = dict(line.split("=", 1) for line in Path("/etc/day19/composition.env").read_text().splitlines() if line and not line.startswith("#"))
    host, token = values["DAY19_MCP_PUBLIC_HOST"], values["DAY19_MCP_TOKEN"]
    url = "https://" + host + "/mcp"
    manifest = json.loads((release / "manifest.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((release / name).read_bytes()).hexdigest() == digest
    result = dict(checked_at=datetime.now(timezone.utc).isoformat(), endpoint=url, manifest=manifest,
        packages={p: importlib.metadata.version(p) for p in ("mcp", "httpx", "pydantic", "defusedxml", "uvicorn")})
    assert result["packages"]["mcp"] == "2.2.0"
    with socket.create_connection((host, 443), timeout=10) as tcp:
        with ssl.create_default_context().wrap_socket(tcp, server_hostname=host) as tls:
            result["tls"] = dict(protocol=tls.version(), certificate=tls.getpeercert())
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        headers = {"Accept": "application/json, text/event-stream"}
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        for label, extra in (("missing", {}), ("invalid", {"Authorization": "Bearer wrong"})):
            response = client.post(url, json=body, headers=headers | extra)
            assert response.status_code == 401
            result["auth_" + label] = response.status_code
        headers["Authorization"] = "Bearer " + token
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        tools = response.json()["result"]["tools"]
        assert [t["name"] for t in tools] == list(NAMES)
        result["tools"] = tools
        for label, extra in (("host", {"Host": "foreign.invalid"}), ("origin", {"Origin": "https://foreign.invalid"})):
            response = client.post("http://127.0.0.1:8019/mcp", json=body, headers=headers | extra)
            assert response.status_code in (400, 403, 421)
            result["foreign_" + label] = response.status_code
        response = client.get("https://" + host + "/health")
        assert response.json() == {"status": "ok"}
    root = Path(values["DAY19_REPORTS_DIR"])
    assert root == Path("/var/lib/day19/reports") and not root.is_symlink()
    assert os.geteuid() == root.stat().st_uid, "Run as day19 for a real permissions check"
    fd, name = tempfile.mkstemp(prefix=".readiness-", dir=root)
    with os.fdopen(fd, "wb") as file:
        file.write(b"readiness\n"); file.flush(); os.fsync(file.fileno())
    assert Path(name).read_bytes() == b"readiness\n"
    Path(name).unlink()
    result["reports_root"] = dict(path=str(root), uid=root.stat().st_uid, mode=oct(root.stat().st_mode & 0o777), writable=True)
    text = json.dumps(result, indent=2)
    assert token not in text
    print(text)


if __name__ == "__main__":
    readiness()
