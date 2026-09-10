import asyncio
from dataclasses import asdict, replace
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.agent import SimpleAgent
from app.agent_sessions import AgentSessionManager, SessionBusy
from app.compression_compare import CompressionComparison
from app.compression_metrics import context_metrics, measure_contexts
from app.compression_models import (CompressionOperation, CompressionPreparation, DAY09_CONFIG,
    SUMMARY_CONFIG, SUMMARY_MARKER, Phase, VERSION)
from app.compression_scenario import fixture_messages, QUESTION, scenario_applicable, verify_facts
from app.conversation_store import ConversationStorageError
from app.conversation_summary_store import SQLiteConversationSummaryStore, SummaryState, SummaryStateError
from app.history_summarizer import HistorySummarizer, RollingSummaryContextPolicy
from app.llm_client import ConversationMessage as M, LlmResult, TokenUsage
from app.main import app
from app.openai_agent_payload import context_payload, generation_payload
from app.sqlite_conversation_store import SQLiteConversationStore


def outcome(reply="Принято", status="completed"):
    return LlmResult(status, reply, usage=TokenUsage(input_tokens=100, cached_input_tokens=0,
        output_tokens=20), requested_model="gpt-4o-mini", resolved_model="gpt-4o-mini-2024-07-18",
        requested_service_tier="default", actual_service_tier="default")


@pytest.fixture
def lab(store):
    manager = AgentSessionManager(store)
    summaries = SQLiteConversationSummaryStore(store._db, store._transaction, VERSION)
    llm, counter = AsyncMock(), AsyncMock()
    llm.complete.return_value = outcome()
    counter.count.return_value = 100
    summarizer = HistorySummarizer(llm)
    agent = SimpleAgent(llm, DAY09_CONFIG, counter, RollingSummaryContextPolicy(summaries, summarizer))
    compare = CompressionComparison(summaries.load, summarizer, agent, counter)
    return manager, summaries, llm, counter, summarizer, agent, compare


def seed(manager, turns=4, fixture=False):
    session = manager.create()
    for i in range(turns):
        session.commit(M("user", fixture_messages()[i] if fixture else f" U{i}\nя "), M("assistant", "Принято"))
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("turns,covered", [(0,0),(1,0),(2,0),(3,2),(4,4)])
async def test_strict_tail_raw_source_and_exact_config(lab, store, turns, covered):
    manager, summaries, llm, counter, _, agent, _ = lab
    session = seed(manager, turns)
    before = session.history
    op = CompressionOperation()
    await agent.run_turn(session, "CURRENT", operation=op)
    assert op.committed and op.context.summarized_message_count == covered
    assert op.context.raw_tail_count == min(4, len(before))
    messages, config = llm.complete.call_args.args
    assert config == DAY09_CONFIG
    assert messages[-1] == M("user", "CURRENT")
    assert messages[1:-1] == before[covered:] if covered else messages[:-1] == before
    assert session.history == (*before, M("user", "CURRENT"), M("assistant", "Принято"))
    assert store.load_session(session.session_id).history == session.history
    assert llm.complete.await_count == 1 + bool(covered)
    if covered:
        assert messages[0].role == "assistant" and messages[0].content.startswith(SUMMARY_MARKER)
        source, sc = llm.complete.call_args_list[0].args
        assert sc == SUMMARY_CONFIG and sc.max_output_tokens == 384
        data = json.loads(source[0].content)
        assert data["new_messages"] == [asdict(m) for m in before[:covered]]
        assert "CURRENT" not in source[0].content
        assert summaries.load(session.session_id, session.history).covered_through_position == covered-1
    else:
        assert op.context.full_source == "identical_payload"
        assert counter.count.await_count == 1
    for kwargs in (context_payload(messages, config), generation_payload(messages, config)):
        assert kwargs["model"] == "gpt-4o-mini" and "reasoning" not in kwargs
        assert kwargs["truncation"] == "disabled"


@pytest.mark.asyncio
async def test_rolling_delta_no_current_no_repeated_raw(lab):
    manager, summaries, llm, _, summarizer, _, _ = lab
    session = seed(manager)
    old = SummaryState(session.session_id, "old compressed fact", 1, VERSION)
    summaries.save(old, session.history, None)
    prep = CompressionPreparation(old)
    await summarizer.prepare_candidate(session.session_id, session.history, prep)
    source = json.loads(llm.complete.call_args.args[0][0].content)
    assert source == {"previous_summary": old.summary_text, "new_messages": [asdict(m) for m in session.history[2:4]]}
    assert summaries.load(session.session_id, session.history) == old


@pytest.mark.asyncio
@pytest.mark.parametrize("status,reply", [("incomplete", None),("refused",None),("error",None),("completed"," ")])
async def test_summary_failure_has_usage_and_no_response(lab, status, reply):
    manager, summaries, llm, counter, _, agent, _ = lab
    session = seed(manager, 3); before = session.history
    llm.complete.return_value = outcome(reply, status)
    op = CompressionOperation()
    await agent.run_turn(session, "current", operation=op)
    assert not op.committed and op.summary_phase.usage.input_tokens == 100
    assert op.summary_phase.cost.status == "available"
    assert not op.response_phase.generation_attempted
    assert summaries.load(session.session_id, before) is None and session.history == before
    counter.count.assert_not_called()
    assert llm.complete.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["summary_save","count","response","pair_save"])
async def test_failure_boundaries_reopen_and_known_receipts(lab, store, monkeypatch, failure):
    manager, summaries, llm, counter, _, agent, _ = lab
    session = seed(manager, 3); before = session.history
    if failure == "summary_save":
        monkeypatch.setattr(summaries, "save", lambda *a: (_ for _ in ()).throw(ConversationStorageError()))
    elif failure == "count":
        counter.count.side_effect = RuntimeError()
    elif failure == "response":
        llm.complete.side_effect = [outcome("summary"), outcome(None, "incomplete")]
    else:
        monkeypatch.setattr(store, "append_turn", lambda *a: (_ for _ in ()).throw(ConversationStorageError()))
    op = CompressionOperation()
    await agent.run_turn(session, "current", operation=op)
    assert not op.committed and session.history == before
    assert AgentSessionManager(store).get(session.session_id).history == before
    assert (summaries.load(session.session_id, before) is None) == (failure == "summary_save")
    assert op.summary_phase.cost.status == "available"
    if failure == "pair_save":
        assert op.response_phase.cost.status == "available" and op.reply is None
    session.ensure_available()


@pytest.mark.asyncio
async def test_summary_persists_after_response_failure_and_is_reused(lab):
    manager, _, llm, _, _, agent, _ = lab
    session = seed(manager, 3)
    llm.complete.side_effect = [outcome("summary"), outcome(None,"incomplete"), outcome()]
    await agent.run_turn(session, "failed", operation=CompressionOperation())
    op = CompressionOperation()
    await agent.run_turn(session, "next", operation=op)
    assert op.committed and not op.summary_phase.generation_attempted
    assert llm.complete.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("f,c,delta,committed", [(130000,4000,126000,True),(100,120,-20,True),(0,0,0,True),(100,128001,-127901,False)])
async def test_signed_counts_and_actual_window(lab, f, c, delta, committed):
    manager, _, _, counter, _, agent, _ = lab
    session = seed(manager, 3)
    async def count(messages, config, include_instructions):
        if not include_instructions: raise RuntimeError("aux count unavailable")
        return c if messages[0].content.startswith(SUMMARY_MARKER) else f
    counter.count.side_effect = count
    op = CompressionOperation()
    await agent.run_turn(session, "current", operation=op)
    assert op.context.token_delta == delta and op.committed == committed
    assert op.context.summary_standalone_tokens is None and op.context.summary_error
    assert op.context.percent_delta == (100*delta/f if f else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [True, -1, "12", None])
async def test_malformed_count_blocks_generation(lab, bad):
    manager, _, llm, counter, _, agent, _ = lab
    counter.count.return_value = bad
    op = CompressionOperation()
    await agent.run_turn(manager.create(), "current", operation=op)
    assert not op.committed and op.error_code == "count_invalid_response"
    llm.complete.assert_not_called()


def test_summary_schema_validation_atomicity_and_delete(tmp_path):
    path = tmp_path / "state.sqlite3"
    raw = SQLiteConversationStore(path)
    assert not raw._db().execute("SELECT name FROM sqlite_master WHERE name='conversation_summaries'").fetchall()
    summaries = SQLiteConversationSummaryStore(raw._db, raw._transaction, VERSION)
    manager = AgentSessionManager(raw); session = seed(manager, 4)
    state = SummaryState(session.session_id, " точная\nсводка ", 1, VERSION)
    summaries.save(state, session.history, None)
    raw._db().execute("CREATE TRIGGER reject_summary BEFORE UPDATE ON conversation_summaries BEGIN SELECT RAISE(ABORT, 'test'); END")
    with pytest.raises(ConversationStorageError):
        summaries.save(replace(state, summary_text="new", covered_through_position=3), session.history, state)
    assert summaries.load(session.session_id, session.history) == state
    raw.close()
    raw = SQLiteConversationStore(path)
    summaries = SQLiteConversationSummaryStore(raw._db, raw._transaction, VERSION)
    assert summaries.load(session.session_id, session.history) == state
    manager = AgentSessionManager(raw)
    assert manager.get(session.session_id).history == session.history
    manager = AgentSessionManager(raw)  # delete still-unloaded session
    manager.delete(session.session_id)
    assert raw.load_session(session.session_id) is None
    assert not raw._db().execute("SELECT * FROM conversation_summaries").fetchall()
    manager.delete(session.session_id); raw.close()


@pytest.mark.parametrize("field,value", [("summary_text"," "),("covered_through_position",0),
    ("covered_through_position",2),("covered_through_position",5),("config_version","other")])
def test_corruption_fails_explicitly_without_repair(lab, store, field, value):
    manager, summaries, llm, *_ = lab
    session = seed(manager)
    state = SummaryState(session.session_id, "summary", 1, VERSION)
    summaries.save(state, session.history, None)
    store._db().execute(f"UPDATE conversation_summaries SET {field}=?", (value,))
    with pytest.raises(SummaryStateError): summaries.load(session.session_id, session.history)
    llm.complete.assert_not_called()


@pytest.mark.asyncio
async def test_compare_parallel_same_snapshot_no_commit_and_score(lab):
    manager, summaries, llm, counter, _, _, comparison = lab
    session = seed(manager, fixture=True); before = session.history
    old = SummaryState(session.session_id, "early summary", 1, VERSION)
    summaries.save(old, before, None)
    barrier = asyncio.Event(); responses = []
    async def complete(messages, config):
        if config == SUMMARY_CONFIG:
            return outcome("identifier=ORBIT-7319; limit=37")
        responses.append((messages, config))
        if len(responses) == 2: barrier.set()
        await asyncio.wait_for(barrier.wait(), .5)
        return outcome("identifier=ORBIT-7319\nlimit=37\nresponsible=Мира")
    llm.complete.side_effect = complete
    op = CompressionOperation(kind="compare")
    await comparison.run(session, QUESTION, "three-facts-v1", op)
    assert op.status == "completed" and op.full.score == op.compressed.score == 3
    assert op.summary_source == "compare_local" and op.compare_summary.covered_through_position == 3
    assert op.durable_summary == old and summaries.load(session.session_id, before) == old
    assert session.history == before and not op.committed
    assert all(m[-1] == M("user", QUESTION) and cfg == DAY09_CONFIG for m,cfg in responses)
    assert responses[0][0][:-1] == before
    assert responses[1][0][1:-1] == before[-4:]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["full_count","full_response","summary"])
async def test_compare_partial_failure(lab, failure):
    manager, _, llm, counter, _, _, comparison = lab
    session = seed(manager, 4)
    async def complete(messages, config):
        if config == SUMMARY_CONFIG:
            return outcome(None,"incomplete") if failure == "summary" else outcome("summary")
        if failure == "full_response" and not messages[0].content.startswith(SUMMARY_MARKER):
            return outcome(None,"error")
        return outcome("reply")
    async def count(messages, config, include_instructions):
        if failure == "full_count" and not messages[0].content.startswith(SUMMARY_MARKER):
            raise RuntimeError()
        return 100
    llm.complete.side_effect = complete; counter.count.side_effect = count
    op = CompressionOperation(kind="compare")
    await comparison.run(session, "question", None, op)
    assert op.status == "partial" and not op.committed
    assert (op.full if failure == "summary" else op.compressed).status == "completed"
    assert op.full.score is None and op.compressed.score is None


@pytest.mark.asyncio
@pytest.mark.parametrize("after_summary", [False, True])
async def test_normal_deadline_cancellation_busy_and_other_session(lab, monkeypatch, after_summary):
    from app import compression_models
    manager, summaries, llm, _, _, agent, _ = lab
    session = seed(manager, 3); entered = asyncio.Event()
    async def complete(messages, config):
        if after_summary and config == SUMMARY_CONFIG: return outcome("summary")
        entered.set(); await asyncio.Event().wait()
    llm.complete.side_effect = complete
    monkeypatch.setattr(compression_models, "OPERATION_TIMEOUT", .04)
    op = CompressionOperation()
    task = asyncio.create_task(agent.run_turn(session,"current",operation=op))
    await entered.wait()
    with pytest.raises(SessionBusy): await agent.run_turn(session,"duplicate",operation=CompressionOperation())
    with pytest.raises(SessionBusy): manager.delete(session.session_id)
    seed(manager, 1).ensure_available()
    await task
    assert op.error_code == "operation_timeout" and session.history_turn_count == 3
    assert (summaries.load(session.session_id, session.history) is not None) == after_summary
    assert op.summary_phase.generation_attempted
    session.ensure_available()


@pytest.mark.asyncio
async def test_compare_deadline_keeps_completed_branch_and_drains_sibling(lab, monkeypatch):
    from app import compression_models
    manager, _, llm, _, _, _, comparison = lab
    session = seed(manager, 4); exited = asyncio.Event()
    async def complete(messages, config):
        if config == SUMMARY_CONFIG: return outcome("summary")
        if not messages[0].content.startswith(SUMMARY_MARKER): return outcome("full answer")
        try: await asyncio.Event().wait()
        finally: exited.set()
    llm.complete.side_effect = complete
    monkeypatch.setattr(compression_models, "OPERATION_TIMEOUT", .04)
    op = CompressionOperation(kind="compare")
    await comparison.run(session,"question",None,op)
    assert op.error_code == "operation_timeout" and op.full.reply == "full answer"
    assert op.full.phase.cost.status == "available" and exited.is_set()
    session.ensure_available()


@pytest.mark.asyncio
@pytest.mark.parametrize("contamination", ["ORBIT-7319", "limit=37"])
async def test_contamination_rejected_before_paid_compare(lab, contamination):
    manager, _, llm, counter, _, _, comparison = lab
    session = manager.create()
    for i, content in enumerate(fixture_messages()):
        session.commit(M("user",content),M("assistant",contamination if i==3 else "Принято"))
    op = CompressionOperation(kind="compare")
    await comparison.run(session,QUESTION,"three-facts-v1",op)
    assert op.scenario_status == "not_applicable" and op.full is None
    llm.complete.assert_not_called(); counter.count.assert_not_called()


def test_fixture_and_exact_verifier():
    assert all(len(x)<=20000 for x in fixture_messages())
    assert all(v not in QUESTION for v in ("ORBIT-7319","37","Мира"))
    score, facts = verify_facts("identifier=ORBIT-7319\nlimit=137\nresponsible=Мира")
    assert score==2 and not facts["limit"]
    assert verify_facts("limit=37\nlimit=37")[0]==0
    assert verify_facts(" limit = 37 \n")[0]==1
    assert asdict(Phase())["status"] == "not_attempted"


@pytest.mark.asyncio
async def test_api_isolation_safe_contracts_and_restore(monkeypatch):
    async with app.router.lifespan_context(app):
        llm, counter = AsyncMock(), AsyncMock()
        llm.complete.return_value=outcome(); counter.count.return_value=100
        agent = SimpleAgent(llm, DAY09_CONFIG, counter, RollingSummaryContextPolicy(
            app.state.compression_summaries, HistorySummarizer(llm)))
        app.state.compression_agent=agent
        app.state.compression_compare=CompressionComparison(app.state.compression_summaries.load,
            HistorySummarizer(llm),agent,counter)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            base="/api/v1/compression-lab/sessions"
            r=await client.post(base,json={}); assert r.status_code==201
            sid=r.json()["session_id"]
            assert (await client.get(f"{base}/{sid}")).status_code==200
            assert (await client.get(f"{base}/{sid}/summary")).json()["summary"] is None
            llm.complete.assert_not_called(); counter.count.assert_not_called()
            for bad in [{"message":" "},{"message":"x","history":[]},{"message":"x"*20001}]:
                assert (await client.post(f"{base}/{sid}/messages",json=bad)).status_code==422
            for old in ("/api/v1/agent/sessions","/api/v1/token-lab/sessions"):
                assert (await client.get(f"{old}/{sid}")).status_code==404
                other=(await client.post(old,json={})).json()["session_id"]
                assert (await client.get(f"{base}/{other}")).status_code==404
                assert (await client.delete(f"{base}/{other}")).status_code==204
                assert (await client.get(f"{old}/{other}")).status_code==200
            sent=await client.post(f"{base}/{sid}/messages",json={"message":"U"})
            assert sent.json()["committed"] and sent.json()["response_phase"]["usage"]["input_tokens"]==100
            compared=await client.post(f"{base}/{sid}/compare",json={"question":"Q"})
            assert not compared.json()["committed"] and compared.json()["history_turn_count"]==1
            assert "history" not in compared.json() and "instructions" not in compared.json()
            assert (await client.delete(f"{base}/{sid}")).status_code==204
            assert (await client.get(f"{base}/{sid}")).status_code==404

@pytest.mark.asyncio
@pytest.mark.parametrize("compressed_status", ["completed", "error", "incomplete", "refused"])
async def test_live_response_format_and_unavailable_failed_branch_score(lab, compressed_status):
    manager, _, llm, _, _, _, comparison = lab
    session = seed(manager, fixture=True)
    async def complete(messages, config):
        if config == SUMMARY_CONFIG:
            return outcome("summary")
        if messages[0].content.startswith(SUMMARY_MARKER):
            return outcome("identifier=unknown, limit=unknown, responsible=Мира", compressed_status)
        return outcome("identifier=ORBIT-7319, limit=37, responsible=Мира")
    llm.complete.side_effect = complete
    op = CompressionOperation(kind="compare")
    await comparison.run(session, QUESTION, "three-facts-v1", op)
    assert op.full.score == 3
    if compressed_status == "completed":
        assert op.compressed.score == 1
        assert op.compressed.facts == {"identifier": False, "limit": False, "responsible": True}
    else:
        assert op.compressed.score is None and op.compressed.facts is None
        assert op.compressed.reply is None
    assert not op.committed and session.history_turn_count == 4
