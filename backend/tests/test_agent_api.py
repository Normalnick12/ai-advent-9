import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.agent import SimpleAgent
from app.llm_client import LlmResult
from app.main import app


@pytest_asyncio.fixture
async def api():
    async with app.router.lifespan_context(app):
        llm = AsyncMock()
        llm.complete.return_value = LlmResult("completed", "Ответ")
        app.state.agent = SimpleAgent(llm)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, llm


BASE = "/api/v1/agent/sessions"


@pytest.mark.asyncio
async def test_lifecycle_and_safe_outcomes(api):
    client, llm = api
    created = await client.post(BASE, json={})
    assert created.status_code == 201 and created.headers["X-Request-ID"]
    assert set(created.json()) == {"session_id", "history_turn_count"}
    sid = created.json()["session_id"]
    llm.complete.assert_not_called()
    for count in (1, 2):
        sent = await client.post(f"{BASE}/{sid}/messages", json={"message": "Вопрос"})
        data = sent.json()
        assert sent.status_code == 200
        assert data["history_turn_count"] == count
        assert data["request_id"] == sent.headers["X-Request-ID"]
        assert set(data) == {"session_id", "request_id", "status", "reply", "history_turn_count", "incomplete_reason", "error"}
    llm.complete.return_value = LlmResult("incomplete", error_code="llm_incomplete", error_message="Ответ не завершён", incomplete_reason="max_output_tokens")
    data = (await client.post(f"{BASE}/{sid}/messages", json={"message": "Ещё"})).json()
    assert data["history_turn_count"] == 2 and data["reply"] is None
    for _ in range(2):
        deleted = await client.delete(f"{BASE}/{sid}")
        assert deleted.status_code == 204 and deleted.content == b""
    assert app.state.agent_sessions._sessions == {}
    lost = await client.post(f"{BASE}/{sid}/messages", json={"message": "Старый"})
    assert lost.status_code == 404 and lost.json()["error"]["code"] == "session_not_found"
    assert llm.complete.await_count == 3
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"message": 1}, {"message": ""}, {"message": " \n "}, {"message": "a" * 20001}, {"message": "private", "history": []}, {"message": "private", "instructions": "secret"}, {"message": "private", "model": "secret"}])
async def test_strict_safe_validation(api, body):
    client, llm = api
    result = await client.post(f"{BASE}/{uuid4()}/messages", json=body)
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "validation_error"
    assert "private" not in result.text and "secret" not in result.text
    assert result.json()["request_id"] == result.headers["X-Request-ID"]
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_create_validation_uuid_and_program_failure(api):
    client, llm = api
    for body in ({"history": []}, {"model": "private"}, None):
        result = await client.post(BASE, json=body)
        assert result.status_code == 422 and "private" not in result.text
    assert (await client.delete(f"{BASE}/bad-id")).status_code == 422
    sid = (await client.post(BASE, json={})).json()["session_id"]
    llm.complete.side_effect = RuntimeError("private credentials")
    result = await client.post(f"{BASE}/{sid}/messages", json={"message": "Вопрос"})
    assert result.status_code == 500 and "private" not in result.text
    assert app.state.agent_sessions.get(sid).history == ()
    assert (await client.delete(f"{BASE}/{sid}")).status_code == 204


@pytest.mark.asyncio
async def test_http_busy_turn_and_delete(api):
    client, llm = api
    started, release = asyncio.Event(), asyncio.Event()
    async def complete(*args):
        started.set()
        await release.wait()
        return LlmResult("completed", "Ответ")
    llm.complete.side_effect = complete
    sid = (await client.post(BASE, json={})).json()["session_id"]
    task = asyncio.create_task(client.post(f"{BASE}/{sid}/messages", json={"message": "Первый"}))
    await started.wait()
    for result in [await client.post(f"{BASE}/{sid}/messages", json={"message": "Второй"}), await client.delete(f"{BASE}/{sid}")]:
        assert result.status_code == 409 and result.json()["error"]["code"] == "session_busy"
    release.set()
    assert (await task).json()["history_turn_count"] == 1
    llm.complete.assert_awaited_once()
