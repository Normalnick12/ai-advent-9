"""Protocol/discovery ONLY. Never calls tools or a model; reuses Day 16 MCP SDK."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

EXPECTED = {
    "deepwiki": {"read_wiki_structure", "read_wiki_contents", "ask_wiki_question"},
    "dependency_composition": {"get_google_maven_versions", "summarize_dependency_versions"},
}


async def discover(label, url, token=None):
    if not url or (label == "dependency_composition" and not token):
        return dict(server_label=label, endpoint=url or None, status="NOT_PROVEN",
                    reason="DAY19_MCP_SERVER_URL / DAY19_MCP_TOKEN missing locally; no SSH attempted")
    try:
        async with asyncio.timeout(45):
            async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token} if token else {},
                                         timeout=30, follow_redirects=False) as http:
                async with Client(streamable_http_client(url, http_client=http), cache=None) as client:
                    tools, cursor = [], None
                    while True:
                        page = await client.list_tools(cursor=cursor)
                        tools.extend(t.model_dump(mode="json", by_alias=True) for t in page.tools)
                        cursor = page.next_cursor
                        if cursor is None:
                            break
                    return dict(server_label=label, endpoint=url,
                        status="PASS" if EXPECTED[label] <= {t["name"] for t in tools} else "FAIL",
                        protocol_version=client.protocol_version, tools=tools)
    except Exception as error:
        return dict(server_label=label, endpoint=url, status="NOT_PROVEN",
                    reason=type(error).__name__)  # never persist auth-bearing exception text


async def main(output):
    # Exclusive output file: discovery is not a Day 20 model attempt.
    with Path(output).open("x", encoding="utf-8") as file:
        results = []
        for label, url, token in [
            ("deepwiki", "https://mcp.deepwiki.com/mcp", None),
            ("dependency_composition", os.getenv("DAY19_MCP_SERVER_URL"), os.getenv("DAY19_MCP_TOKEN")),
        ]:
            result = await discover(label, url, token)
            results.append(result)
            print(label, result["status"], flush=True)
        json.dump(dict(kind="readiness_only", checked_at=datetime.now(timezone.utc).isoformat(),
                       tools_called=False, model_called=False, servers=results), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return 0 if all(r["status"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)  # schemas/status only; avoid transport exception logging
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New local JSON file")
    raise SystemExit(asyncio.run(main(parser.parse_args().output)))
