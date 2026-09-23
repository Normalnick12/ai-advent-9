import asyncio
import json
import logging
from uuid import uuid4

from mcp import Client
import pytest
from starlette.testclient import TestClient

from server import create_app, create_server, OwnerLock
from storage import Store
from watch_models import CreateInput, WatchError

TOKEN = "synthetic-secret-sentinel-0123456789"
ARGS = {"group_id": "androidx.core", "artifact_id": "core-ktx", "max_runs": 3}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.mark.asyncio
async def test_mcp_discovery_structured_and_text_wrappers(tmp_path):
    store = Store(tmp_path / "w.db")
    async with Client(create_server(lambda: store)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert set(tools) == {"create_dependency_watch", "get_dependency_watch_summary"}
        create = tools["create_dependency_watch"]
        assert "max_runs" in create.input_schema["required"]
        assert not create.annotations.idempotent_hint and not create.annotations.read_only_hint
        assert tools["get_dependency_watch_summary"].annotations.read_only_hint
        first = await client.call_tool("create_dependency_watch", ARGS)
        assert not first.is_error
        receipt = first.structured_content
        assert receipt == json.loads(first.content[0].text)
        summary = await client.call_tool("get_dependency_watch_summary", {"watch_id": receipt["watch_id"]})
        assert summary.structured_content["runs_total"] == 0
        assert summary.structured_content["first_version_count"] is None
        bad = await client.call_tool("get_dependency_watch_summary", {"watch_id": str(uuid4())})
        assert bad.is_error
        for invalid in ({k: v for k, v in ARGS.items() if k != "max_runs"}, {**ARGS, "max_runs": True}):
            assert (await client.call_tool("create_dependency_watch", invalid)).is_error


def test_bearer_before_dispatch_host_health_and_secret_logs(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    app = create_app(path=tmp_path / "w.db", token=TOKEN)
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/health").json() == {"status": "ok"}
        for token in (None, "wrong"):
            headers = HEADERS | ({"Authorization": "Bearer " + token} if token else {})
            response = client.post("/mcp", json=INIT, headers=headers)
            assert response.status_code == 401
        headers = HEADERS | {"Authorization": "Bearer " + TOKEN}
        response = client.post("/mcp", json=INIT, headers=headers)
        assert response.status_code == 200
        assert TOKEN not in response.text
        assert client.post("/mcp", json=INIT, headers=headers | {"Host": "evil.example"}).status_code == 421
        assert client.post("/mcp", json=INIT, headers=headers | {"Origin": "https://evil.example"}).status_code == 403
        app.state.store.create(CreateInput(**ARGS))
    assert TOKEN not in caplog.text
    assert "watch_created" in caplog.text and "watch_id" in caplog.text


def test_startup_token_and_second_owner_fail_closed(tmp_path):
    with pytest.raises(WatchError, match="bearer_token"):
        create_app(token="")
    first, second = OwnerLock(tmp_path / "owner.lock"), OwnerLock(tmp_path / "owner.lock")
    first.acquire()
    try:
        with pytest.raises(WatchError, match="owner_exists"):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


@pytest.mark.asyncio
async def test_worker_failure_makes_app_unhealthy_and_notifies_supervisor(tmp_path):
    from unittest.mock import patch
    import httpx
    fatal = asyncio.Event()
    async def broken(self):
        raise RuntimeError("not exposed")
    app = create_app(path=tmp_path / "w.db", token=TOKEN, fatal_callback=fatal.set)
    with patch("scheduler.Scheduler.run", broken):
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(fatal.wait(), 2)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as client:
                health = await client.get("/health")
                assert health.status_code == 503
                assert "not exposed" not in health.text
