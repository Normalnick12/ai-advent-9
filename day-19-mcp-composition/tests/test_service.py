import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import httpx
from mcp import Client
from pydantic import ValidationError
import pytest
from starlette.testclient import TestClient

from composition.contracts import LookupResult, DependencyReport, SaveInput
from composition.lookup import lookup, LookupFailure
from composition.report import canonical, digest, summarize
from composition.server import create_server, create_app, Events, NAMES
from composition.storage import ReportStore, StorageFailure
from collect import collect
from verify import verify

STAMP = "2026-09-24T10:00:00.123Z"
BASE = dict(status="found", group_id="androidx.core", artifact_id="core-ktx", versions=["2.0", "1.0", "2.0", "3.0-rc01"],
            source_url="https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml", checked_at=STAMP,
            lookup_id="12345678-1234-1234-1234-123456789abc")


@pytest.mark.asyncio
async def test_three_actual_calls(tmp_path):
    events, requests, calls = [], [], []
    def upstream(request):
        requests.append(request)
        return httpx.Response(200, text='<androidx.core><core-ktx versions="2.0,1.0,2.0,3.0-rc01"/></androidx.core>')
    server = create_server(tmp_path, transport=httpx.MockTransport(upstream), clock=lambda: STAMP,
                           events=Events(events.append))
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        assert [t.name for t in tools] == list(NAMES)
        for i, tool in enumerate(tools):
            assert tool.input_schema["additionalProperties"] is False
            assert tool.output_schema["additionalProperties"] is False
            assert tool.annotations.read_only_hint == (i < 2)
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is True
        args = {"group_id": "androidx.core", "artifact_id": "core-ktx"}
        outputs = []
        for index, name in enumerate(NAMES):
            result = await client.call_tool(name, args)
            assert not result.is_error
            value = result.structured_content
            assert json.loads(result.content[0].text) == value
            outputs.append(value)
            calls.append(dict(type="mcp_call", id=f"call{index}", server_label="dependency_composition",
                name=name, arguments=json.dumps(args), output=result.model_dump_json(by_alias=True), status="completed"))
            args = {"lookup" if index == 0 else "report": copy.deepcopy(value)}
    assert len(requests) == 1
    assert str(requests[0].url) == BASE["source_url"]
    assert outputs[0]["versions"] == BASE["versions"]
    assert outputs[1]["version_count"] == 4
    receipt = outputs[2]
    data = (tmp_path / (receipt["file_id"] + ".json")).read_bytes()
    assert data == canonical(outputs[1])
    assert hashlib.sha256(data).hexdigest() == receipt["sha256"]
    assert len(data) == receipt["bytes"]
    op = dict(operation_id="offline", calls=calls, invocation="observed", final_text=json.dumps(dict(
        {k: outputs[1][k] for k in ("group_id", "artifact_id", "status", "version_count", "last_three")}, file_id=receipt["file_id"])),
        request_configuration={"tools": [{"server_url": "offline"}]})
    disk = collect(receipt["file_id"], operation_id="offline", lookup_id=receipt["lookup_id"],
                   revision="offline", endpoint="offline", root=tmp_path)
    verdicts = verify(op, events, disk)
    assert verdicts["full_acceptance"]["status"] == "PASS", verdicts
    assert not any("scheduler" in module or module == "sqlite3" for module in sys.modules if module.startswith("composition"))


@pytest.mark.parametrize("field,value", [("lookup_id", BASE["lookup_id"].upper()), ("checked_at", "2026-09-24T10:00:00Z"),
    ("checked_at", "2026-02-30T10:00:00.123Z"), ("source_url", "https://example.org"), ("versions", []),
    ("versions", [1]), ("versions", ["a b"]), ("group_id", "a..b"), ("group_id", True), ("artifact_id", "x\n"),
    ("path", "secret-sentinel"), ("filename", "x"), ("directory", "x"), ("content", "x")])
def test_strict_lookup(field, value):
    with pytest.raises(ValidationError):
        LookupResult.model_validate(dict(BASE, **{field: value}))


@pytest.mark.parametrize("field,value", [("schema_version", True), ("version_count", "4"), ("version_count", False),
    ("last_three", ["x"]), ("input_sha256", "A" * 64), ("status", "no_versions"), ("content", "arbitrary")])
def test_strict_report(field, value):
    obj = summarize(LookupResult(**BASE)).model_dump()
    with pytest.raises(ValidationError):
        DependencyReport.model_validate(dict(obj, **{field: value}))


def test_golden():
    # Literal expected bytes independent of the production serializer.
    gold = b'{"a":["2","1","2"],"z":"\\u00e9\\n\\\"\\\\"}\n'
    obj = {"z": 'é\n"\\', "a": ["2", "1", "2"]}
    assert canonical(obj) == gold
    assert digest(obj) == hashlib.sha256(gold).hexdigest()
    assert canonical(dict(reversed(list(obj.items())))) == gold
    assert canonical(dict(obj, a=["1", "2", "2"])) != gold
    for status, versions in [("found", ["1"]), ("found", ["2", "1"]), ("no_versions", []),
                             ("group_not_found", []), ("artifact_not_found", [])]:
        item = LookupResult(**dict(BASE, status=status, versions=versions))
        result = summarize(item)
        assert result.version_count == len(versions) and result.last_three == versions[-3:]
        assert result == summarize(item)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,body,status", [(404, "", "group_not_found"), (200, "<androidx.core/>", "artifact_not_found"),
    (200, '<androidx.core><core-ktx versions=""/></androidx.core>', "no_versions")])
async def test_negatives(code, body, status):
    item = await lookup("androidx.core", "core-ktx", transport=httpx.MockTransport(lambda req: httpx.Response(code, text=body)))
    assert item.status == status and item.versions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("code,body,category", [(302, "", "upstream_http"), (500, "", "upstream_http"),
    (200, "bad", "upstream_xml"), (200, "<other/>", "upstream_xml"),
    (200, '<!DOCTYPE x [<!ENTITY y "z">]><androidx.core/>', "upstream_xml"),
    (200, '<androidx.core><core-ktx/></androidx.core>', "upstream_xml"),
    (200, '<androidx.core><core-ktx versions="1"/><core-ktx versions="2"/></androidx.core>', "upstream_xml"),
    (200, '<androidx.core><core-ktx versions="1,,2"/></androidx.core>', "upstream_xml"),
    (200, '<androidx.core><core-ktx versions="1, 2"/></androidx.core>', "upstream_xml"),
    (200, "x" * (2 * 1024 * 1024 + 1), "upstream_response")], ids=["redirect", "http", "bad-xml", "root", "dtd", "missing", "duplicate", "empty-segment", "space", "body-limit"])
async def test_upstream_errors(code, body, category):
    count = []
    def handle(req):
        count.append(req)
        return httpx.Response(code, text=body, headers={"location": "https://example.org"})
    with pytest.raises(LookupFailure) as caught:
        await lookup("androidx.core", "core-ktx", transport=httpx.MockTransport(handle))
    assert caught.value.category == category and caught.value.lookup_id
    assert len(count) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error,category", [(httpx.ConnectError("sentinel"), "upstream_network"),
                                            (httpx.ReadTimeout("sentinel"), "upstream_timeout")])
async def test_network(error, category):
    def fail(req):
        raise error
    with pytest.raises(LookupFailure, match=category) as caught:
        await lookup("a", "b", transport=httpx.MockTransport(fail))
    assert "sentinel" not in str(caught.value)


@pytest.mark.asyncio
async def test_total_deadline(monkeypatch):
    import importlib
    module = importlib.import_module("composition.lookup")
    monkeypatch.setattr(module, "UPSTREAM_SECONDS", .01)
    async def slow(req):
        await asyncio.sleep(.1)
        return httpx.Response(200, text="<a/>")
    with pytest.raises(LookupFailure, match="upstream_timeout"):
        await lookup("a", "b", transport=httpx.MockTransport(slow))


@pytest.mark.asyncio
async def test_mcp_invalid_arguments_no_io(tmp_path):
    events = []
    def unexpected(req):
        pytest.fail("unexpected upstream")
    async with Client(create_server(tmp_path, transport=httpx.MockTransport(unexpected), events=Events(events.append))) as client:
        bad = [(NAMES[0], {"group_id": "https://x", "artifact_id": "b"}),
               (NAMES[1], {"lookup": json.dumps(BASE)}), (NAMES[1], {"lookup": BASE, "path": "sentinel"}),
               (NAMES[1], {"lookup": dict(BASE, path="sentinel")}),
               (NAMES[2], {"report": summarize(LookupResult(**BASE)).model_dump(), "directory": "sentinel"})]
        for name, args in bad:
            result = await client.call_tool(name, args)
            assert result.is_error
            assert "sentinel" not in result.model_dump_json()
    assert list(tmp_path.iterdir()) == []
    assert "sentinel" not in json.dumps(events)
    assert len({e["invocation_id"] for e in events}) == len(bad)


def test_storage_atomic_repeat_failure_and_links(tmp_path, monkeypatch):
    report = summarize(LookupResult(**BASE))
    store = ReportStore(tmp_path)
    real_link = os.link
    def observe(src, dest):
        assert Path(src).read_bytes() == canonical(report.model_dump())
        assert not Path(dest).exists()
        return real_link(src, dest)
    monkeypatch.setattr(os, "link", observe)
    first = store.save(report)
    assert first == store.save(report)
    assert len(list(tmp_path.iterdir())) == 1
    new_report = report.model_copy(update={"lookup_id": "22345678-1234-1234-1234-123456789abc"})
    def failure(fd):
        raise OSError("secret-sentinel")
    monkeypatch.setattr(os, "fsync", failure)
    with pytest.raises(StorageFailure) as caught:
        store.save(new_report)
    assert "secret-sentinel" not in str(caught.value)
    assert len(list(tmp_path.iterdir())) == 1


def test_symlink_escape(tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    report = summarize(LookupResult(**BASE))
    target = root / (digest(report.model_dump()) + ".json")
    try:
        target.symlink_to(outside / "untouched.json")
    except OSError as exc:
        pytest.fail(f"Symlink gate cannot be checked: {exc}")
    with pytest.raises(StorageFailure):
        ReportStore(root).save(report)
    assert list(outside.iterdir()) == []
    link = tmp_path / "rootlink"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(StorageFailure):
        ReportStore(link).save(report)


def test_auth_host_health(tmp_path):
    token = "synthetic-secret-sentinel-" * 2
    app = create_app(root=tmp_path, token=token, public_host="day19.example.org")
    with TestClient(app, base_url="http://localhost") as client:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        for auth in ({}, {"authorization": "Bearer wrong"}):
            response = client.post("/mcp", headers=auth, json=body)
            assert response.status_code == 401 and token not in response.text
        headers = {"authorization": "Bearer " + token, "accept": "application/json, text/event-stream"}
        response = client.post("/mcp", headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert len(response.json()["result"]["tools"]) == 3
        assert client.post("/mcp", headers=dict(headers, host="evil.example"), json=body).status_code in (400, 421)
        assert client.post("/mcp", headers=dict(headers, origin="https://evil.example"), json=body).status_code in (400, 403)
        assert client.get("/health").json() == {"status": "ok"}
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError):
        create_app(root=tmp_path, token="")
