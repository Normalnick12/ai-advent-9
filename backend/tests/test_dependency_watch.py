import copy
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
from openai import APIConnectionError
import pytest

from app.dependency_watch_api import router
from app.dependency_watch_models import WatchRequest
from app.dependency_watch_service import DependencyWatchService, SERVER, TOOLS, normalize

TOKEN = "synthetic-day18-secret-sentinel-0123456789"
URL = "https://watch.example.org/mcp"
ARGS = {"group_id": "androidx.core", "artifact_id": "core-ktx", "max_runs": 3, "interval_seconds": 30}
RECEIPT = {"watch_id": str(uuid4()), **ARGS, "created_at": "2026-09-23T10:00:00Z",
    "next_run_at": "2026-09-23T10:00:30Z", "status": "active", "runs_total": 0, "skipped_slots": 0}
SUMMARY = {**RECEIPT, "successful": 0, "failed": 0, "interrupted": 0, "comparable_snapshots": 0,
    "first_checked_at": None, "last_checked_at": None, "first_version_count": None, "last_version_count": None,
    "changes_detected": 0, "newly_seen_versions": [], "latest_execution": None, "through_execution_id": None,
    "generated_at": RECEIPT["created_at"], "executions": [], "running_execution": None}


def call(operation="create", result=None, **changes):
    args = ARGS if operation == "create" else {"watch_id": RECEIPT["watch_id"]}
    return {"type": "mcp_call", "id": "call1", "server_label": SERVER, "name": TOOLS[operation],
        "arguments": json.dumps(args), "output": json.dumps(result or (RECEIPT if operation == "create" else SUMMARY)), **changes}


def response(*items, status="completed", text="Модель говорит 999 версий"):
    return {"id": "resp", "status": status, "output": [*items, {"type": "message", "content":
        [{"type": "output_text", "text": text}] if text else []}]}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "summary"])
async def test_native_authorization_every_call_and_immutable_evidence(tmp_path, operation):
    sdk = AsyncMock()
    sdk.responses.create.return_value = response(call(operation))
    request = WatchRequest(prompt="P", operation=operation,
                           watch_id=RECEIPT["watch_id"] if operation == "summary" else None)
    with patch("app.dependency_watch_service.AsyncOpenAI", return_value=sdk) as factory:
        service = DependencyWatchService(server_url=URL, token=TOKEN, evidence_dir=tmp_path)
        for _ in range(2):
            result = await service.run(request)
            config = sdk.responses.create.call_args.kwargs
            assert config["tools"] == [{"type": "mcp", "server_label": SERVER, "server_url": URL,
                "authorization": TOKEN, "allowed_tools": [TOOLS[operation]], "require_approval": "never"}]
            assert config["tool_choice"]["name"] == TOOLS[operation]
            assert config["model"] == "gpt-5.6" and not config["store"]
            assert result.evidence_saved and result.outcome == "completed"
        assert factory.call_args.kwargs["max_retries"] == 0
        assert sdk.responses.create.await_count == 2
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 2 and files[0].read_text() != files[1].read_text()
    assert all(TOKEN not in file.read_text() for file in files)
    if operation == "summary":
        assert result.calls[0].summary.last_version_count is None
        assert "999" in result.final_text  # prose is preserved, never repairs primary facts


def test_all_create_calls_preserved_even_partial():
    second = {**RECEIPT, "watch_id": str(uuid4())}
    req = WatchRequest(prompt="P", operation="create")
    raw = response(call(), call(result=second, id="call2"), status="incomplete")
    result = normalize(raw, req, URL, "op")
    assert result.outcome == "incomplete" and len(result.calls) == 2
    assert result.calls[0].receipt.watch_id != result.calls[1].receipt.watch_id
    raw["output"].clear()
    assert len(result.mcp_items) == 2


@pytest.mark.parametrize("wrapper", ["structuredContent", "structured_content", "content"])
def test_real_mcp_wrappers(wrapper):
    raw = {wrapper: [{"type": "text", "text": json.dumps(RECEIPT)}] if wrapper == "content" else RECEIPT}
    result = normalize(response(call(result=raw)), WatchRequest(prompt="P", operation="create"), URL, "op")
    assert result.calls[0].receipt is not None


@pytest.mark.parametrize("item,outcome", [(call(result={"isError": True}), "tool_error"),
    (call(output="bad json"), "invalid_tool_result"), (call(error="opaque"), "unclassified_error"),
    (call(result={**RECEIPT, "max_runs": 2}), "invalid_tool_result")])
def test_error_outcomes(item, outcome):
    assert normalize(response(item), WatchRequest(prompt="P", operation="create"), URL, "op").outcome == outcome


def test_summary_mismatch_and_refusal_no_call():
    req = WatchRequest(prompt="P", operation="summary", watch_id=str(uuid4()))
    assert normalize(response(call("summary")), req, URL, "op").outcome == "invalid_tool_result"
    raw = response()
    raw["output"][0]["content"] = [{"type": "refusal", "refusal": "No"}]
    assert normalize(raw, req, URL, "op").outcome == "refused"
    assert normalize(response(), req, URL, "op").outcome == "not_called"


@pytest.mark.asyncio
async def test_timeout_unknown_no_retry(tmp_path):
    sdk = AsyncMock()
    sdk.responses.create.side_effect = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    service = DependencyWatchService(sdk, server_url=URL, token=TOKEN, evidence_dir=tmp_path)
    result = await service.run(WatchRequest(prompt="P", operation="create"))
    assert result.invocation == "unknown" and result.outcome == "provider_error"
    assert sdk.responses.create.await_count == 1 and result.evidence_saved


@pytest.mark.asyncio
async def test_secret_redaction_in_every_output_and_input(tmp_path, caplog):
    sdk = AsyncMock()
    sdk.responses.create.return_value = response(call(error={"authorization": TOKEN, "message": "Bearer " + TOKEN}), text=TOKEN)
    service = DependencyWatchService(sdk, server_url=URL, token=TOKEN, evidence_dir=tmp_path)
    result = await service.run(WatchRequest(prompt="P " + TOKEN, operation="create"))
    assert TOKEN not in result.model_dump_json()
    assert TOKEN not in sdk.responses.create.call_args.kwargs["input"]
    assert TOKEN not in caplog.text
    assert all(TOKEN not in p.read_text() for p in tmp_path.glob("*.json"))


@pytest.mark.asyncio
async def test_missing_configuration_does_not_send(tmp_path):
    sdk = AsyncMock()
    result = await DependencyWatchService(sdk, token="", server_url=URL, evidence_dir=tmp_path).run(
        WatchRequest(prompt="P", operation="create"))
    assert result.outcome == "configuration_error" and result.invocation == "not_sent"
    sdk.responses.create.assert_not_awaited()


def test_route_validation_and_contract(tmp_path):
    sdk = AsyncMock()
    sdk.responses.create.return_value = response(call())
    app = FastAPI()
    app.include_router(router)
    app.state.dependency_watch = DependencyWatchService(sdk, server_url=URL, token=TOKEN, evidence_dir=tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/v1/dependency-watch/run", json={"operation": "summary", "prompt": "P"}).status_code == 422
        result = client.post("/api/v1/dependency-watch/run", json={"operation": "create", "prompt": "P"})
        assert result.status_code == 200 and result.json()["calls"][0]["receipt"] == RECEIPT
