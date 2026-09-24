import copy
import configparser
import json
from pathlib import Path
import sys

import httpx
from mcp import Client
from pydantic import ValidationError
import pytest

from composition.contracts import Coordinates, LookupResult, SaveReceipt
from composition.lookup import lookup
from composition.report import summarize, canonical
from composition.storage import ReportStore
from composition.server import create_server
from sizing import measure
import verify as v


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["", "https://evil.org", "a/b", "a%2fb", "a b", "a..b", "x" * 257, 1, True])
async def test_coordinates_before_network(value):
    def unexpected(req): pytest.fail("network must not be called")
    with pytest.raises(ValidationError):
        await lookup(value, "artifact", transport=httpx.MockTransport(unexpected))


def test_required_fields_and_receipt_types():
    raw = dict(status="saved", lookup_id="12345678-1234-1234-1234-123456789abc", file_id="a"*64, sha256="a"*64, bytes=1)
    for key in raw:
        value = raw.copy(); value.pop(key)
        with pytest.raises(ValidationError): SaveReceipt.model_validate(value)
    for value in (True, "1", 0):
        with pytest.raises(ValidationError): SaveReceipt.model_validate(dict(raw, bytes=value))
    with pytest.raises(ValidationError): SaveReceipt.model_validate(dict(raw, sha256="b"*64))


@pytest.mark.asyncio
async def test_negative_full_chain_and_forged_save(tmp_path):
    async with Client(create_server(tmp_path, transport=httpx.MockTransport(lambda req: httpx.Response(404)))) as client:
        lookup_result = (await client.call_tool(v.NAMES[0], {"group_id":"androidx.core", "artifact_id":"core-ktx"})).structured_content
        report = (await client.call_tool(v.NAMES[1], {"lookup": lookup_result})).structured_content
        assert report["status"] == "group_not_found" and report["version_count"] == 0 and report["last_three"] == []
        receipt = (await client.call_tool(v.NAMES[2], {"report": report})).structured_content
        assert (tmp_path / (receipt["file_id"]+".json")).read_bytes() == canonical(report)
        # Save accepts schema-valid objects without recomputing hashes.
        report["input_sha256"] = "f"*64
        forged = (await client.call_tool(v.NAMES[2], {"report": report})).structured_content
        assert json.loads((tmp_path / (forged["file_id"]+".json")).read_bytes())["input_sha256"] == "f"*64


def test_deploy_templates_and_sizing():
    root = Path(__file__).resolve().parents[1]
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read(root / "deploy/day19-composition.service")
    assert unit["Service"]["User"] == "day19" and unit["Service"]["UMask"] == "0077"
    assert unit["Service"]["StateDirectory"] == "day19"
    assert "/opt/day19/current" in unit["Service"]["ExecStart"]
    fragment = (root / "deploy/Caddyfile.fragment").read_text()
    assert "127.0.0.1:8019" in fragment and "day18" not in fragment
    item = dict(status="found", group_id="androidx.core", artifact_id="core-ktx", versions=[str(i) for i in range(1000)],
        source_url="https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml", checked_at="2026-09-24T00:00:00.000Z",
        lookup_id="12345678-1234-1234-1234-123456789abc")
    result = measure(item, [])
    assert result["status"] == "PASS" and result["max_output_tokens"] > result["generated_token_upper_bound"] * 2
    item["versions"] = ["1" * 1000] * 1000
    assert measure(item, [])["status"] == "BLOCKED"
