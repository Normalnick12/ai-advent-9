import json
import logging

import httpx
import pytest
from mcp import Client
from starlette.testclient import TestClient

import server

COORDS = {"group_id": "androidx.core", "artifact_id": "core-ktx"}
INDEX = b'<androidx.core><core-ktx versions="2.0-alpha01,1.0,2.0"/></androidx.core>'


async def call_with(response=None, *, arguments=None, error=None):
    requests = []

    def respond(request):
        requests.append(request)
        if error:
            raise error
        return response or httpx.Response(200, content=INDEX)

    async with Client(server.create_server(httpx.MockTransport(respond))) as client:
        result = await client.call_tool("get_google_maven_versions", COORDS if arguments is None else arguments)
    return result, requests


@pytest.mark.asyncio
async def test_discovery_and_structured_result(caplog):
    caplog.set_level(logging.INFO, logger="google_maven_lookup")
    async with Client(server.create_server(httpx.MockTransport(lambda r: httpx.Response(200, content=INDEX)))) as client:
        tools = (await client.list_tools()).tools
        assert [t.name for t in tools] == ["get_google_maven_versions"]
        tool = tools[0]
        assert "Google Maven only" in tool.description
        assert tool.annotations.read_only_hint is True
        schema = tool.input_schema
        assert set(schema["required"]) == {"group_id", "artifact_id"}
        for name in schema["required"]:
            assert schema["properties"][name]["type"] == "string"
            assert schema["properties"][name]["description"]
            assert schema["properties"][name]["pattern"]
        assert tool.output_schema
        result = await client.call_tool(tool.name, COORDS)
    assert not result.is_error
    data = result.structured_content
    assert data["versions"] == ["2.0-alpha01", "1.0", "2.0"]
    assert data["status"] == "found"
    assert data["source_url"] == "https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml"
    assert data["checked_at"].endswith("Z") or data["checked_at"].endswith("+00:00")
    event = next(json.loads(r.message) for r in caplog.records if r.name == "google_maven_lookup")
    assert event["lookup_id"] == data["lookup_id"]
    assert event["source_url"] == data["source_url"]
    assert event["http_status"] == 200
    assert event["outcome"] == "found"
    assert event["versions_count"] == 3


@pytest.mark.parametrize("value", ["", " ", " a", "a ", "a\nb", "a\n", "a/b", "a\\b",
    "https://host", "a?b", "a#b", "%2e%2e", "a%2Fb", ".", 1, None, "x" * 257])
@pytest.mark.parametrize("field", ["group_id", "artifact_id"])
@pytest.mark.asyncio
async def test_invalid_input_never_fetches(field, value, caplog):
    caplog.set_level(logging.INFO, logger="google_maven_lookup")
    result, requests = await call_with(arguments={**COORDS, field: value})
    assert result.is_error
    assert not requests
    assert not [r for r in caplog.records if r.name == "google_maven_lookup"]


@pytest.mark.parametrize("group", [".androidx", "androidx.", "androidx..core"])
@pytest.mark.asyncio
async def test_empty_group_segments(group):
    result, requests = await call_with(arguments={**COORDS, "group_id": group})
    assert result.is_error and not requests


@pytest.mark.parametrize("status,xml,expected", [
    (200, INDEX, "found"), (404, b"not found", "group_not_found"),
    (200, b"<androidx.core><other versions='1'/></androidx.core>", "artifact_not_found"),
    (200, b"<androidx.core><core-ktx versions=''/></androidx.core>", "no_versions"),
])
@pytest.mark.asyncio
async def test_normal_lookup(status, xml, expected):
    result, requests = await call_with(httpx.Response(status, content=xml))
    assert not result.is_error
    assert result.structured_content["status"] == expected
    assert bool(result.structured_content["versions"]) == (expected == "found")
    assert len(requests) == 1
    assert str(requests[0].url) == server.source_url("androidx.core")


@pytest.mark.parametrize("xml", [b"broken", b"<html/>", b"<androidx.core><core-ktx/></androidx.core>",
    b"<androidx.core><core-ktx versions='1,,2'/></androidx.core>",
    b"<androidx.core><core-ktx versions='1'/><core-ktx versions='2'/></androidx.core>",
    b'<!DOCTYPE a [<!ENTITY e "x">]><androidx.core/>',
])
@pytest.mark.asyncio
async def test_xml_failure_is_execution_error(xml):
    result, requests = await call_with(httpx.Response(200, content=xml))
    assert result.is_error and len(requests) == 1
    assert "upstream_xml" in result.content[0].text
    assert result.structured_content is None


@pytest.mark.parametrize("status", [301, 403, 429, 500, 503])
@pytest.mark.asyncio
async def test_http_failure_not_negative_lookup(status):
    result, requests = await call_with(httpx.Response(status, headers={"Location": "https://other.example"}))
    assert result.is_error and len(requests) == 1
    assert "upstream_http" in result.content[0].text


@pytest.mark.parametrize("error,category", [(httpx.ReadTimeout("private details"), "upstream_timeout"),
    (httpx.ConnectError("private details"), "upstream_network")])
@pytest.mark.asyncio
async def test_network_errors_are_safe_and_logged(error, category, caplog):
    caplog.set_level(logging.INFO, logger="google_maven_lookup")
    result, requests = await call_with(error=error)
    assert result.is_error and len(requests) == 1
    text = result.content[0].text
    assert category in text and "private details" not in text
    event = next(json.loads(r.message) for r in caplog.records if r.name == "google_maven_lookup")
    assert event["lookup_id"] in text
    assert event["outcome"] == category and event["http_status"] is None


@pytest.mark.asyncio
async def test_body_limit(monkeypatch):
    monkeypatch.setattr(server, "MAX_BODY_BYTES", 10)
    result, _ = await call_with()
    assert result.is_error and "upstream_response" in result.content[0].text


def test_asgi_host_protection_and_health():
    app = server.create_app(public_host="maven.example.org")
    with TestClient(app, base_url="https://maven.example.org") as client:
        assert client.get("/health").json() == {"status": "ok"}
        headers = {"Accept": "application/json, text/event-stream"}
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
        assert client.post("/mcp", json=body, headers=headers).status_code == 200
        assert client.post("/mcp", json=body, headers={**headers, "Host": "evil.example"}).status_code == 421
        assert client.post("/mcp", json=body, headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    with pytest.raises(ValueError):
        server.transport_security("https://maven.example.org/path")
