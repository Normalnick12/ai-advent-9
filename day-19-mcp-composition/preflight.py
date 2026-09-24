"""One direct remote lookup for sizing, never a model request or save call."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import httpx
from verify import unwrap, validate


def preflight(url, token):
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.post(url, headers={"Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream"}, json={"jsonrpc": "2.0", "id": "preflight",
            "method": "tools/call", "params": {"name": "get_google_maven_versions",
                "arguments": {"group_id": "androidx.core", "artifact_id": "core-ktx"}}})
    response.raise_for_status()
    raw = response.json()
    lookup = validate(unwrap(raw["result"]), "lookup")
    return dict(readiness_only=True, checked_at=datetime.now(timezone.utc).isoformat(), endpoint=url,
                raw_mcp=raw, lookup=lookup)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    args = parser.parse_args()
    # Reserve before lookup, avoid accidental overwrite of prior readiness evidence.
    with Path(args.output).open("x", encoding="utf-8") as file:
        result = preflight(os.environ["DAY19_MCP_SERVER_URL"], os.environ["DAY19_MCP_TOKEN"])
        json.dump(result, file, indent=2)
        file.write("\n")
    print("Readiness lookup saved; no model call or report save.")
