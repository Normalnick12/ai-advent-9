import asyncio
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager
from app.compression_compare import CompressionComparison
from app.compression_models import CompressionOperation, DAY09_CONFIG, SUMMARY_CONFIG, VERSION
from app.compression_scenario import fixture_messages, QUESTION, scenario_applicable
from app.conversation_store import ConversationStorageError
from app.conversation_summary_store import SQLiteConversationSummaryStore, SummaryState
from app.history_summarizer import HistorySummarizer, RollingSummaryContextPolicy
from app.llm_client import ConversationMessage as M, LlmResult
from app.main import app
from app.sqlite_conversation_store import SQLiteConversationStore


@pytest.mark.asyncio
@pytest.mark.parametrize("other", ["agent_database_path", "token_database_path"])
async def test_day09_path_must_differ_from_both_old_namespaces(monkeypatch, other):
    monkeypatch.setattr(app.state, "compression_database_path", getattr(app.state, other))
    with pytest.raises(ValueError):
        async with app.router.lifespan_context(app):
            pytest.fail("startup must reject shared file")


@pytest.mark.asyncio
async def test_partial_startup_closes_all_owned_resources(monkeypatch):
    from app import main
    clients, counters, stores = [], [], []
    def client():
        value = AsyncMock(); clients.append(value); return value
    def counter():
        value = AsyncMock(); counters.append(value); return value
    def store(path):
        value = SQLiteConversationStore(path); stores.append(value); return value
    monkeypatch.setattr(main, "OpenAIResponsesLlmClient", client)
    monkeypatch.setattr(main, "OpenAIInputTokenCounter", counter)
    monkeypatch.setattr(main, "SQLiteConversationStore", store)
    def fail(*args):
        raise ConversationStorageError()
    monkeypatch.setattr(main, "SQLiteConversationSummaryStore", fail)
    with pytest.raises(ConversationStorageError):
        async with app.router.lifespan_context(app):
            pytest.fail("startup must fail")
    assert len(clients) == len(stores) == 3 and len(counters) == 2
    for resource in clients + counters:
        resource.close.assert_awaited_once()
    for raw in stores:
        with pytest.raises(ConversationStorageError): raw._db()


@pytest.mark.asyncio
async def test_no_transaction_during_llm_and_compare_reopen_has_no_changes(tmp_path):
    path = tmp_path / "durable.sqlite3"
    raw = SQLiteConversationStore(path)
    manager = AgentSessionManager(raw)
    summaries = SQLiteConversationSummaryStore(raw._db, raw._transaction, VERSION)
    session = manager.create()
    for text in fixture_messages()[:3]: session.commit(M("user", text), M("assistant", "Принято"))
    llm, counter = AsyncMock(), AsyncMock(); counter.count.return_value = 100
    async def complete(messages, config):
        assert not raw._db().in_transaction
        if config == SUMMARY_CONFIG:
            source = json.loads(messages[0].content)
            assert fixture_messages()[3] not in [m["content"] for m in source["new_messages"]]
        await asyncio.sleep(0)
        return LlmResult("completed", "summary" if config == SUMMARY_CONFIG else "Принято")
    llm.complete.side_effect = complete
    summarizer = HistorySummarizer(llm)
    agent = SimpleAgent(llm, DAY09_CONFIG, counter, RollingSummaryContextPolicy(summaries, summarizer))
    await agent.run_turn(session, fixture_messages()[3], operation=CompressionOperation())
    old = summaries.load(session.session_id, session.history)
    assert old.covered_through_position == 1
    before = session.history
    compare = CompressionComparison(summaries.load, summarizer, agent, counter)
    op = CompressionOperation(kind="compare")
    await compare.run(session, QUESTION, "three-facts-v1", op)
    assert op.compare_summary.covered_through_position == 3
    raw.close()
    reopened = SQLiteConversationStore(path)
    try:
        fresh = AgentSessionManager(reopened).get(session.session_id)
        assert fresh.history == before
        adapter = SQLiteConversationSummaryStore(reopened._db, reopened._transaction, VERSION)
        assert adapter.load(session.session_id, before) == old
        reopened._db().execute("CREATE TRIGGER reject_delete BEFORE DELETE ON sessions BEGIN SELECT RAISE(ABORT, 'test'); END")
        with pytest.raises(ConversationStorageError): AgentSessionManager(reopened).delete(session.session_id)
        assert reopened.load_session(session.session_id).history == before
        assert adapter.load(session.session_id, before) == old
    finally: reopened.close()


@pytest.mark.asyncio
async def test_safe_corrupt_metadata_busy_and_cross_namespace_writes():
    async with app.router.lifespan_context(app):
        manager = app.state.compression_sessions
        session = manager.create()
        for i in range(3): session.commit(M("user",str(i)),M("assistant","ok"))
        summaries = app.state.compression_summaries
        state = SummaryState(session.session_id, "summary", 1, VERSION)
        summaries.save(state, session.history, None)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            base = f"/api/v1/compression-lab/sessions/{session.session_id}"
            session.begin_turn()
            try:
                for suffix, body in [("/messages", {"message":"x"}), ("/compare", {"question":"q"})]:
                    assert (await client.post(base+suffix,json=body)).status_code == 409
                assert (await client.get(base+"/summary")).status_code == 409
                assert (await client.delete(base)).status_code == 409
            finally: session.end_turn()
            for bad in [{"question":" "},{"question":"q","history":[]},{"question":"q","scenario_id":"bad"}]:
                assert (await client.post(base+"/compare",json=bad)).status_code == 422
            for prefix in ("/api/v1/agent/sessions", "/api/v1/token-lab/sessions"):
                other = (await client.post(prefix,json={})).json()["session_id"]
                for suffix, body in [("/messages", {"message":"x"}), ("/compare", {"question":"q"})]:
                    assert (await client.post(f"/api/v1/compression-lab/sessions/{other}"+suffix,json=body)).status_code == 404
                assert (await client.post(f"{prefix}/{session.session_id}/messages",json={"message":"x"})).status_code == 404
            summaries._connection().execute("UPDATE conversation_summaries SET config_version='incompatible'")
            for suffix in ("", "/summary"):
                response = await client.get(base+suffix)
                assert response.status_code == 500 and response.json()["error"]["code"] == "summary_config_mismatch"
            assert (await client.delete(base)).status_code == 204


def test_fixture_number_boundaries_and_role_contamination():
    history = tuple(m for text in fixture_messages() for m in (M("user",text),M("assistant","Принято")))
    assert scenario_applicable(history, QUESTION)
    assert scenario_applicable((*history[:-1], M("assistant","137")), QUESTION)
    assert not scenario_applicable((*history[:-1], M("assistant","37")), QUESTION)
    assert not scenario_applicable((*history[:-2], replace(history[-2], content=history[-2].content+" ORBIT-7319"), history[-1]), QUESTION)
