import asyncio
import hashlib
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import BadRequestError

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager, SessionBusy
from app.llm_client import AgentConfig, ConversationMessage as Message, LlmResult, TokenUsage
from app.main import app
from app.openai_agent_payload import context_payload, generation_payload
from app.openai_responses_llm_client import OpenAIResponsesLlmClient, provider_error_code
from app.openai_token_counter import OpenAIInputTokenCounter
from app.sqlite_conversation_store import SQLiteConversationStore
from app.token_diagnostics import CountFailure, DAY08_CONFIG
from app.token_overflow import OverflowPreparations
from app.token_pricing import estimate_turn_cost

BASE = "/api/v1/token-lab/sessions"


def llm_result(status="completed", **kwargs):
    return LlmResult(status, "Ответ" if status == "completed" else None,
        usage=TokenUsage(input_tokens=1000, cached_input_tokens=200, output_tokens=100),
        resolved_model="gpt-4o-mini-2024-07-18", actual_service_tier="default", **kwargs)


def agent_for(counts):
    llm, counter = AsyncMock(), AsyncMock()
    llm.complete.return_value = llm_result()
    counter.count.side_effect = counts
    return SimpleAgent(llm, DAY08_CONFIG, counter), llm, counter


def test_config_and_pricing():
    assert DAY08_CONFIG.model == "gpt-4o-mini" and DAY08_CONFIG.version == "day08-gpt4o-mini-v1"
    assert hashlib.sha256(DAY08_CONFIG.instructions.encode()).hexdigest() == "692ffef60e824f8cb67594abc411f7c563072e199645fb3a8a2464ce2d7147e9"
    assert DAY08_CONFIG.instructions == AgentConfig().instructions
    assert estimate_turn_cost(llm_result()).amount_usd == "0.000195"
    assert estimate_turn_cost(llm_result("incomplete")).amount_usd == "0.000195"
    for changes in ({"cached_input_tokens": None}, {"input_tokens": True},
                    {"cache_write_tokens": 900}, {"reasoning_tokens": 101}, {"total_tokens": 1}):
        result = replace(llm_result(), usage=replace(llm_result().usage, **changes))
        assert estimate_turn_cost(result).status == "unavailable"
    for changes in ({"resolved_model": "unknown"}, {"actual_service_tier": None}, {"usage": None}):
        assert estimate_turn_cost(replace(llm_result(), **changes)).status == "unavailable"
    assert estimate_turn_cost(replace(llm_result(), usage=replace(llm_result().usage,
        cache_write_tokens=100, reasoning_tokens=20, total_tokens=1100))).amount_usd == "0.000195"


@pytest.mark.asyncio
async def test_independent_counts_and_snapshot(manager):
    agent, llm, counter = agent_for([19, 139, 12, 31, 40])
    session = manager.create()
    first = await agent.run_turn(session, " U\nя ")
    assert first.committed and first.diagnostics.count_calls == 2
    assert first.diagnostics.saved_history_tokens == 0
    before = session.history
    second = await agent.run_turn(session, "U2")
    d = second.diagnostics
    assert (d.current_message_tokens, d.saved_history_tokens, d.preflight_input_tokens) == (12, 31, 40)
    assert d.history_turn_count_before == 1 and d.count_calls == 3
    assert counter.count.call_args_list[-2].args[0] == before
    assert counter.count.call_args_list[-2].kwargs == {"include_instructions": False}
    assert counter.count.call_args_list[-1].args == llm.complete.call_args.args
    assert llm.complete.await_count == 2 and session.history_turn_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [CountFailure("count_provider_error"), True, -1, "23", None])
async def test_partial_count_failure_no_generation(manager, failure):
    agent, llm, counter = agent_for([19, failure])
    result = await agent.run_turn(manager.create(), "U")
    assert result.diagnostics.current_message_tokens == 19
    assert result.diagnostics.saved_history_tokens == 0
    assert result.diagnostics.preflight_input_tokens is None
    assert result.error_origin == "preflight" and not result.committed
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_window_guard_reserve_and_unavailable_price(manager):
    agent, llm, _ = agent_for([19, 128001, 19, 127000])
    session = manager.create()
    result = await agent.run_turn(session, "U")
    assert result.error_code == "preflight_context_exceeded" and session.history == ()
    llm.complete.assert_not_called()
    llm.complete.return_value = replace(llm_result(), usage=None)
    result = await agent.run_turn(session, "U")
    assert result.committed and result.diagnostics.reserve_warning
    assert estimate_turn_cost(result.outcome).status == "unavailable"


@pytest.mark.asyncio
async def test_count_timeout_cancellation_busy_and_independent_session(manager):
    entered = asyncio.Event()
    async def count(messages, config, **kwargs):
        if messages[-1].content == "wait":
            entered.set()
            await asyncio.Event().wait()
        return 20
    agent, llm, counter = agent_for(count)
    a, b = manager.create(), manager.create()
    with patch("app.agent.PREFLIGHT_TIMEOUT", .03):
        pending = asyncio.create_task(agent.run_turn(a, "wait"))
        await entered.wait()
        with pytest.raises(SessionBusy):
            await agent.run_turn(a, "duplicate")
        assert (await agent.run_turn(b, "ok")).committed
        result = await pending
        assert result.error_code == "count_timeout" and a.history == ()
    a.ensure_available()
    pending = asyncio.create_task(agent.run_turn(a, "wait"))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    a.ensure_available()


@pytest.mark.asyncio
async def test_openai_count_adapter_exact_payload_and_timeout():
    sdk = AsyncMock()
    sdk.responses.input_tokens.with_raw_response.count.return_value = NS(http_response=NS(json=lambda: {"input_tokens": 19}))
    counter = OpenAIInputTokenCounter()
    messages = (Message("user", " Я\n "),)
    with patch("app.openai_token_counter.AsyncOpenAI", return_value=sdk) as factory:
        assert await counter.count(messages, DAY08_CONFIG, include_instructions=False) == 19
        assert factory.call_args.kwargs["max_retries"] == 0
        timeout = factory.call_args.kwargs["timeout"]
        assert timeout.read == 15 and timeout.connect == 5
        payload = sdk.responses.input_tokens.with_raw_response.count.call_args.kwargs
        assert payload == context_payload(messages, DAY08_CONFIG, include_instructions=False)
        assert not {"instructions", "reasoning", "store", "service_tier", "max_output_tokens"} & payload.keys()
        await counter.count(messages, DAY08_CONFIG, include_instructions=True)
        full = sdk.responses.input_tokens.with_raw_response.count.call_args.kwargs
        generation = generation_payload(messages, DAY08_CONFIG)
        assert all(generation[k] == v for k, v in full.items())
        for bad in [True, -1, "5", None]:
            sdk.responses.input_tokens.with_raw_response.count.return_value = NS(http_response=NS(json=lambda: {"input_tokens": bad}))
            with pytest.raises(CountFailure):
                await counter.count(messages, DAY08_CONFIG, include_instructions=True)
        await counter.close()
        sdk.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "incomplete", "failed"])
async def test_actual_usage_preserved_even_invalid_completed(status):
    sdk = AsyncMock()
    sdk.responses.create.return_value = NS(status=status, output=[], model="gpt-4o-mini", service_tier="default",
        usage=NS(input_tokens=1000, output_tokens=100, total_tokens=1100,
            input_tokens_details=NS(cached_tokens=0, cache_write_tokens=None),
            output_tokens_details=NS(reasoning_tokens=True)))
    adapter = OpenAIResponsesLlmClient()
    adapter._client = sdk
    result = await adapter.complete((Message("user", "U"),), DAY08_CONFIG)
    assert result.usage.input_tokens == 1000 and result.usage.cached_input_tokens == 0
    assert result.usage.cache_write_tokens is None and result.usage.reasoning_tokens is None
    assert result.usage.invalid_fields == ("reasoning_tokens",)
    assert result.resolved_model == "gpt-4o-mini" and result.actual_service_tier == "default"
    assert "reasoning" not in sdk.responses.create.call_args.kwargs


@pytest.mark.parametrize("status,body,expected", [
    (400, {"code": "context_length_exceeded"}, "context_limit_exceeded"),
    (400, {"message": "context_length_exceeded"}, "llm_invalid_request"),
    (413, {"code": "context_length_exceeded"}, "llm_body_too_large"),
    (429, {}, "llm_rate_limit"),
])
def test_structured_error_classification(status, body, expected):
    assert provider_error_code(body, status) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [llm_result(), llm_result("incomplete"),
    LlmResult("error", error_code="context_limit_exceeded"), LlmResult("error", error_code="llm_timeout")])
async def test_probe_never_commits_and_is_single_use(tmp_path, outcome):
    path = tmp_path / "probe.sqlite3"
    store = SQLiteConversationStore(path)
    manager = AgentSessionManager(store)
    session = manager.create()
    session.commit(Message("user", "U1"), Message("assistant", "A1"))
    before = session.history
    agent, llm, counter = agent_for([82072, 139902, 19, 35, 139])
    probes = OverflowPreparations(agent)
    prepared, info = await probes.prepare(session)
    assert info.repeats == 13975 and info.full_payload_bytes < 2*1024*1024
    assert prepared.diagnostics.preflight_input_tokens == 139902
    assert prepared.diagnostics.current_message_tokens is None and prepared.diagnostics.saved_history_tokens is None
    assert prepared.diagnostics.count_calls == 2
    assert all(c.kwargs["include_instructions"] for c in counter.count.call_args_list)
    llm.complete.assert_not_called()
    llm.complete.return_value = outcome
    result = await probes.execute(session, info.preparation_id)
    assert result.reply is None and not result.committed and result.generation_attempted
    if outcome.status == "completed":
        assert result.error_code == "unexpected_provider_acceptance"
        assert result.outcome.usage == outcome.usage
    assert session.history == before
    assert not (await probes.execute(session, info.preparation_id)).generation_attempted
    llm.complete.assert_awaited_once()
    sid = session.session_id
    store.close()
    reopened = SQLiteConversationStore(path)
    restored = AgentSessionManager(reopened).get(sid)
    assert restored.history == before
    llm.complete.return_value = llm_result()
    assert (await agent.run_turn(restored, "next")).committed
    assert restored.history_turn_count == 2
    reopened.close()


@pytest.mark.asyncio
async def test_preparation_expiry_stale_and_capacity(manager):
    agent, llm, counter = agent_for([140000]*10)
    probes = OverflowPreparations(agent)
    session = manager.create()
    _, info = await probes.prepare(session)
    _, replacement = await probes.prepare(session)
    assert not (await probes.execute(session, info.preparation_id)).generation_attempted
    session.commit(Message("user", "U"), Message("assistant", "A"))
    assert not (await probes.execute(session, replacement.preparation_id)).generation_attempted
    with patch("app.token_overflow.TTL_SECONDS", -1):
        _, expired = await probes.prepare(session)
    assert not (await probes.execute(session, expired.preparation_id)).generation_attempted
    with patch("app.token_overflow.CAPACITY", 1):
        await probes.prepare(session)
        result, info = await probes.prepare(manager.create())
        assert result.error_code == "preparation_capacity" and info is None
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_namespaces_http_projection_and_pricing_failure():
    async with app.router.lifespan_context(app):
        agent, llm, _ = agent_for([19, 139])
        app.state.token_agent = agent
        app.state.token_overflow = OverflowPreparations(agent)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            sid = (await client.post(BASE, json={})).json()["session_id"]
            old = (await client.post("/api/v1/agent/sessions", json={})).json()["session_id"]
            for suffix, body in [("/messages", {"message":"U"}), ("/overflow/prepare", {}),
                                 ("/overflow/execute", {"preparation_id":"x", "confirm":True})]:
                assert (await client.post(BASE+f"/{old}"+suffix, json=body)).status_code == 404
            assert (await client.get(BASE+f"/{old}")).status_code == 404
            assert (await client.delete(BASE+f"/{old}")).status_code == 204
            assert (await client.get(f"/api/v1/agent/sessions/{old}")).status_code == 200
            for body in ({"message":"x"*20001}, {"message":"x", "history":[]}, {"message":" "}):
                assert (await client.post(BASE+f"/{sid}/messages", json=body)).status_code == 422
            for confirm in (False, 1, "true"):
                assert (await client.post(BASE+f"/{sid}/overflow/execute", json={"preparation_id":"x", "confirm":confirm})).status_code == 422
            with patch("app.token_lab_api.estimate_turn_cost", side_effect=ValueError):
                response = await client.post(BASE+f"/{sid}/messages", json={"message":"U"})
            assert response.status_code == 200
            body = response.json()
            assert body["committed"] and body["history_turn_count"] == 1
            assert body["cost"]["status"] == "unavailable" and body["usage"]["input_tokens"] == 1000
            assert body["diagnostics"]["preflight_input_tokens"] == 139
            assert "instructions" not in body and "history" not in body
    async with app.router.lifespan_context(app):
        assert app.state.token_sessions.get(sid).history_turn_count == 1
        assert app.state.agent_sessions.get(old).history_turn_count == 0


@pytest.mark.asyncio
async def test_same_database_is_rejected(monkeypatch):
    monkeypatch.setattr(app.state, "token_database_path", app.state.agent_database_path)
    with pytest.raises(ValueError, match="different database"):
        async with app.router.lifespan_context(app):
            pytest.fail("must fail")
