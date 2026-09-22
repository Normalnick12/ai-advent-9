import asyncio
import copy
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.main import app
from app.mcp_lab_models import McpLabRequest
from app.mcp_lab_service import INSTRUCTIONS, McpLabService, SERVER, TOOL, normalize_response

URL = "https://maven.example.org/mcp"
ARGS = {"group_id": "androidx.core", "artifact_id": "core-ktx"}
RESULT = {"status": "found", **ARGS, "versions": ["2-alpha", "1", "2"],
    "source_url": "https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml",
    "checked_at": "2026-09-22T10:00:00Z", "lookup_id": "8010fc2e-0e4a-4ff4-afbb-ae4d6701eeb9"}
DISCOVERY = {"type": "mcp_list_tools", "id": "list_1", "server_label": SERVER,
             "tools": [{"name": TOOL, "description": "Exact lookup", "input_schema": {"type": "object"}}]}


def call(**changes):
    return {"type": "mcp_call", "id": "call_1", "server_label": SERVER, "name": TOOL,
            "arguments": json.dumps(ARGS), "output": json.dumps(RESULT), **changes}


def response(*items, status="completed", text="Три версии: 2-alpha, 1, 2."):
    return {"id": "resp_1", "status": status, "output": [*items, {"type": "message", "content":
        [{"type": "output_text", "text": text}] if text is not None else []}]}


def normalize(*items, **kwargs):
    return normalize_response(response(*items, **kwargs), McpLabRequest(prompt="P"), URL, "operation_1")


@pytest.mark.parametrize("mode", ["forced", "auto"])
@pytest.mark.asyncio
async def test_exact_payload_lazy_client(mode):
    sdk = AsyncMock()
    sdk.responses.create.return_value = response(DISCOVERY, call())
    with patch("app.mcp_lab_service.AsyncOpenAI", return_value=sdk) as factory:
        service = McpLabService(server_url=URL)
        factory.assert_not_called()
        result = await service.run(McpLabRequest(prompt="Exact user prompt", mode=mode))
        assert result.outcome == "completed"
        assert sdk.responses.create.await_count == 1
        assert factory.call_args.kwargs["max_retries"] == 0
        assert factory.call_args.kwargs["timeout"].read == 75
        assert sdk.responses.create.call_args.kwargs == {
            "model": "gpt-5.6", "input": "Exact user prompt", "instructions": INSTRUCTIONS,
            "reasoning": {"effort": "none"}, "max_output_tokens": 1200, "store": False,
            "tools": [{"type": "mcp", "server_label": SERVER, "server_url": URL,
                       "allowed_tools": [TOOL], "require_approval": "never"}],
            "tool_choice": {"type": "mcp", "server_label": SERVER, "name": TOOL} if mode == "forced" else "auto"}
        await service.close()
        sdk.close.assert_awaited_once()


def test_preserves_all_items_optional_status_and_imported_schema():
    bad = call(id="bad", status="failed", error="opaque provider error", output=None)
    good = call()
    result = normalize(DISCOVERY, bad, good)
    assert result.mcp_items == [DISCOVERY, bad, good]
    assert result.imported_tools == DISCOVERY["tools"]
    assert [c.id for c in result.calls] == ["bad", "call_1"]
    assert result.calls[0].error == bad["error"]
    assert result.calls[0].status == "failed"
    assert result.calls[1].status is None
    assert result.calls[1].output == good["output"]
    assert result.calls[1].arguments == good["arguments"]
    assert result.calls[1].parsed_result.versions == RESULT["versions"]
    assert result.outcome == "unclassified_error"


@pytest.mark.parametrize("envelope", [lambda r: r, lambda r: {"structuredContent": r},
    lambda r: {"content": [{"type": "text", "text": json.dumps(r)}]}])
@pytest.mark.parametrize("status", ["found", "group_not_found", "artifact_not_found", "no_versions"])
def test_structured_and_text_results(envelope, status):
    payload = {**RESULT, "status": status, "versions": RESULT["versions"] if status == "found" else []}
    result = normalize(call(output=json.dumps(envelope(payload))))
    assert result.calls[0].outcome == status
    assert result.outcome == "completed"


@pytest.mark.parametrize("changes", [
    {"output": "unparseable"}, {"output": json.dumps({**RESULT, "versions": []})},
    {"arguments": json.dumps({**ARGS, "artifact_id": "other"})},
    {"output": json.dumps({**RESULT, "source_url": "https://other.example"})},
    {"status": "failed"}, {"name": "other_tool"}, {"server_label": "other_server"},
    {"output": json.dumps({"content": []})},
])
def test_invalid_evidence_keeps_raw_without_false_success(changes):
    original = call(**changes)
    result = normalize(original)
    assert result.outcome == "invalid_tool_result"
    assert result.calls[0].parsed_result is None
    assert result.mcp_items == [original]


def test_tool_error_not_negative_result():
    result = normalize(call(output=json.dumps({"isError": True, "content": [{"type": "text", "text": "upstream_xml"}]})))
    assert result.outcome == "tool_error"
    assert result.calls[0].parsed_result is None


@pytest.mark.parametrize("status", ["incomplete", "failed"])
def test_provider_status_does_not_drop_evidence(status):
    result = normalize(DISCOVERY, call(), status=status)
    assert result.outcome == status and len(result.calls) == 1
    assert result.mcp_items == [DISCOVERY, call()]


def test_refusal_and_missing_prose_preserve_calls():
    raw = response(DISCOVERY, call())
    raw["output"][-1]["content"] = [{"type": "refusal", "refusal": "No"}]
    result = normalize_response(raw, McpLabRequest(prompt="P"), URL, "operation_1")
    assert result.outcome == "refused" and result.calls
    assert normalize(call(), text=None).outcome == "model_response_missing"


@pytest.mark.parametrize("mode", ["forced", "auto"])
def test_no_call_never_uses_prose_as_evidence(mode):
    result = normalize_response(response(DISCOVERY), McpLabRequest(prompt="P", mode=mode), URL, "op")
    assert result.outcome == "not_called" and not result.calls
    assert result.invocation == "not_observed"


def test_discovery_failure_and_approval_are_not_not_called():
    assert normalize({**DISCOVERY, "error": "network", "tools": []}).outcome == "mcp_error"
    assert normalize({"type": "mcp_approval_request", "id": "approval"}).outcome == "mcp_error"


@pytest.mark.parametrize("error", [TimeoutError(), APIConnectionError(request=httpx.Request("POST", URL), message="secret")])
@pytest.mark.asyncio
async def test_provider_error_no_retry_no_fabricated_items(error):
    sdk = AsyncMock()
    sdk.responses.create.side_effect = error
    result = await McpLabService(sdk, URL).run(McpLabRequest(prompt="P"))
    assert result.outcome == "provider_error" and result.invocation == "unknown"
    assert result.response_id is None and not result.calls and not result.imported_tools
    assert sdk.responses.create.await_count == 1 and "secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_concurrent_attempts_are_independent():
    sdk = AsyncMock()
    async def create(**payload):
        await asyncio.sleep(0)
        return {**response(call(), text=payload["input"]), "id": payload["input"]}
    sdk.responses.create.side_effect = create
    service = McpLabService(sdk, URL)
    a, b = await asyncio.gather(service.run(McpLabRequest(prompt="A")), service.run(McpLabRequest(prompt="B")))
    assert a.operation_id != b.operation_id
    assert (a.response_id, a.final_text, a.submitted_prompt) == ("A", "A", "A")
    assert (b.response_id, b.final_text, b.submitted_prompt) == ("B", "B", "B")
    assert a.calls is not b.calls


@pytest.mark.parametrize("url", ["", "http://host/mcp", "https://localhost/mcp", "https://127.0.0.1/mcp",
    "https://host.example/other", "https://user:secret@host.example/mcp", "https://host.example/mcp?secret=x"])
@pytest.mark.asyncio
async def test_configuration_failure_does_not_send(url):
    sdk = AsyncMock()
    result = await McpLabService(sdk, url).run(McpLabRequest(prompt="P"))
    assert result.outcome == "configuration_error" and result.invocation == "not_sent"
    assert result.server_url is None
    sdk.responses.create.assert_not_called()


def test_route_startup_without_configuration_keeps_existing_health(monkeypatch, tmp_path):
    monkeypatch.delenv("DAY17_MCP_SERVER_URL", raising=False)
    # Isolate remaining namespaces not covered by the shared fixture.
    for name in ("memory_database_path", "personalization_memory_path", "profile_database_path"):
        monkeypatch.setattr(app.state, name, tmp_path / (name + ".sqlite3"))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        result = client.post("/api/v1/mcp-tool-lab/run", json={"prompt": "P", "mode": "forced"})
        assert result.status_code == 200 and result.json()["outcome"] == "configuration_error"
        assert client.post("/api/v1/mcp-tool-lab/run", json={"prompt": " "}).status_code == 422
