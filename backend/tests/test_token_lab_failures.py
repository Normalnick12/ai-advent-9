import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import BadRequestError

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager, SessionBusy
from app.conversation_store import ConversationStorageError
from app.llm_client import ConversationMessage as Message, LlmResult
from app.main import app
from app.openai_responses_llm_client import OpenAIResponsesLlmClient
from app.openai_token_counter import OpenAIInputTokenCounter
from app.sqlite_conversation_store import SQLiteConversationStore
from app.token_diagnostics import CountFailure, DAY08_CONFIG
from app.token_overflow import OverflowPreparations


@pytest.mark.asyncio
async def test_second_storage_startup_failure_closes_all_resources(tmp_path, monkeypatch):
    import app.main as main
    clients = [AsyncMock(), AsyncMock()]
    factory = iter(clients)
    monkeypatch.setattr(main, "OpenAIResponsesLlmClient", lambda: next(factory))
    opened = []
    def store(path):
        if opened:
            raise ConversationStorageError
        value = SQLiteConversationStore(path)
        opened.append(value._db())
        return value
    monkeypatch.setattr(main, "SQLiteConversationStore", store)
    with pytest.raises(ConversationStorageError):
        async with app.router.lifespan_context(app):
            pytest.fail("startup must fail")
    import sqlite3
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")
    for client in clients:
        client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_failure_reopen_and_cancel_preserve_pair(tmp_path):
    path = tmp_path / "history.sqlite3"
    store = SQLiteConversationStore(path)
    session = AgentSessionManager(store).create()
    session.commit(Message("user", "U"), Message("assistant", "A"))
    before, sid = session.history, session.session_id
    counter, llm = AsyncMock(), AsyncMock()
    counter.count.side_effect = CountFailure("count_rate_limit")
    probes = OverflowPreparations(SimpleAgent(llm, DAY08_CONFIG, counter))
    result, info = await probes.prepare(session)
    assert result.error_code == "count_rate_limit" and info is None and session.history == before
    assert not probes._items
    entered = asyncio.Event()
    async def hanging(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()
    counter.count.side_effect = hanging
    task = asyncio.create_task(probes.prepare(session))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    session.ensure_available()
    assert not probes._items and session.history == before
    llm.complete.assert_not_called()
    store.close()
    reopened = SQLiteConversationStore(path)
    assert AgentSessionManager(reopened).get(sid).history == before
    reopened.close()


@pytest.mark.asyncio
async def test_concurrent_execute_and_cancellation_consume_permission(manager):
    llm, counter = AsyncMock(), AsyncMock()
    counter.count.return_value = 139902
    entered = asyncio.Event()
    async def generation(*args):
        entered.set()
        await asyncio.Event().wait()
    llm.complete.side_effect = generation
    probes = OverflowPreparations(SimpleAgent(llm, DAY08_CONFIG, counter))
    session = manager.create()
    _, info = await probes.prepare(session)
    task = asyncio.create_task(probes.execute(session, info.preparation_id))
    await entered.wait()
    with pytest.raises(SessionBusy):
        await probes.execute(session, info.preparation_id)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not (await probes.execute(session, info.preparation_id)).generation_attempted
    assert session.history == ()
    llm.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_deadline_and_provider_context_error_remain_count_errors():
    counter = OpenAIInputTokenCounter()
    sdk = AsyncMock()
    counter._client = sdk
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com/v1/responses/input_tokens"))
    sdk.responses.input_tokens.with_raw_response.count.side_effect = BadRequestError(
        "private", response=response, body={"code":"context_length_exceeded"})
    with pytest.raises(CountFailure, match="count_provider_error"):
        await counter.count((Message("user", "U"),), DAY08_CONFIG, include_instructions=True)
    async def hanging(**kwargs):
        await asyncio.Event().wait()
    sdk.responses.input_tokens.with_raw_response.count.side_effect = hanging
    with patch("app.openai_token_counter.COUNT_TIMEOUT", .01):
        with pytest.raises(CountFailure, match="count_timeout"):
            await counter.count((Message("user", "U"),), DAY08_CONFIG, include_instructions=True)
    assert sdk.responses.input_tokens.with_raw_response.count.await_count == 2


@pytest.mark.asyncio
async def test_generation_context_mapping_preserves_old_configuration_behavior():
    from app.llm_client import AgentConfig
    sdk = AsyncMock()
    adapter = OpenAIResponsesLlmClient()
    adapter._client = sdk
    sdk.responses.create.return_value = NS(status="failed", output=[],
        error=NS(code="context_length_exceeded"), usage=NS(input_tokens=1))
    old = await adapter.complete((), AgentConfig())
    new = await adapter.complete((), DAY08_CONFIG)
    assert old.error_code == "llm_upstream_error"
    assert new.error_code == "context_limit_exceeded" and new.usage.input_tokens == 1
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    sdk.responses.create.side_effect = BadRequestError("private", response=response,
        body={"error":{"code":"context_length_exceeded"}, "usage":{"input_tokens":2}})
    result = await adapter.complete((), DAY08_CONFIG)
    assert result.error_code == "context_limit_exceeded" and result.usage.input_tokens == 2
    assert "private" not in repr(result)
