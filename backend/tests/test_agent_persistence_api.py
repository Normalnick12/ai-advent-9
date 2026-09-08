from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent import SimpleAgent
from app.conversation_store import ConversationStorageError
from app.llm_client import LlmResult
from app.main import app
from app.sqlite_conversation_store import SQLiteConversationStore


BASE = "/api/v1/agent/sessions"


@pytest.mark.asyncio
async def test_lifespan_reopen_metadata_and_next_turn(isolated_agent_database, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = AsyncMock()
    llm.complete.return_value = LlmResult("completed", "A1")
    async with app.router.lifespan_context(app):
        app.state.agent = SimpleAgent(llm)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(BASE, json={})
            sid = response.json()["session_id"]
            empty = await client.get(f"{BASE}/{sid}")
            assert empty.json() == {"session_id": sid, "history_turn_count": 0}
            llm.complete.assert_not_called()
            assert (await client.post(f"{BASE}/{sid}/messages", json={"message": "U1"})).json()["status"] == "completed"
        old_connection = app.state.agent_sessions._store._db()
    import sqlite3
    with pytest.raises(sqlite3.ProgrammingError):
        old_connection.execute("SELECT 1")
    async with app.router.lifespan_context(app):
        assert app.state.agent_sessions._sessions == {}
        app.state.agent = SimpleAgent(llm)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            count = llm.complete.await_count
            metadata = await client.get(f"{BASE}/{sid}")
            assert metadata.json() == {"session_id": sid, "history_turn_count": 1}
            assert metadata.headers["X-Request-ID"]
            assert llm.complete.await_count == count
            sent = await client.post(f"{BASE}/{sid}/messages", json={"message": "U2"})
            assert sent.json()["history_turn_count"] == 2
            assert [m.content for m in llm.complete.call_args.args[0]] == ["U1", "A1", "U2"]
            assert (await client.delete(f"{BASE}/{sid}")).status_code == 204
            missing = await client.get(f"{BASE}/{sid}")
            assert missing.status_code == 404
            assert "перезапуска" not in missing.text
            invalid = await client.get(f"{BASE}/not-a-uuid")
            assert invalid.status_code == 422
            assert invalid.json()["request_id"] == invalid.headers["X-Request-ID"]
    reopened = SQLiteConversationStore(isolated_agent_database)
    try:
        assert reopened.load_session(sid) is None
    finally:
        reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create_session", "append_turn", "delete_session", "load_session"])
async def test_storage_errors_never_become_http_success(operation, monkeypatch):
    async with app.router.lifespan_context(app):
        llm = AsyncMock()
        llm.complete.return_value = LlmResult("completed", "A1")
        app.state.agent = SimpleAgent(llm)
        manager = app.state.agent_sessions
        session = manager.create()
        def fail(*args):
            raise ConversationStorageError
        monkeypatch.setattr(manager._store, operation, fail)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            if operation == "create_session":
                response = await client.post(BASE, json={})
                assert len(manager._sessions) == 1
            elif operation == "append_turn":
                response = await client.post(f"{BASE}/{session.session_id}/messages", json={"message": "private"})
                assert session.history == ()
                session.ensure_available()
                llm.complete.assert_awaited_once()
            elif operation == "delete_session":
                response = await client.delete(f"{BASE}/{session.session_id}")
                assert manager.get(session.session_id) is session
                session.ensure_available()
            else:
                manager._sessions.clear()
                response = await client.get(f"{BASE}/{session.session_id}")
            assert response.status_code == 500
            assert set(response.json()) == {"request_id", "error"}
            assert response.json()["error"]["code"] == "internal_error"
            assert "private" not in response.text
            if operation != "append_turn":
                llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_lifespan_closes_client_on_failed_storage_startup(tmp_path, monkeypatch):
    import app.main as main
    client = AsyncMock()
    monkeypatch.setattr(main, "OpenAIResponsesLlmClient", lambda: client)
    invalid = tmp_path / "file"
    invalid.write_text("not a directory")
    monkeypatch.setattr(app.state, "agent_database_path", invalid / "database.sqlite3")
    with pytest.raises(ConversationStorageError):
        async with app.router.lifespan_context(app):
            pytest.fail("startup must fail")
    client.close.assert_awaited_once()
