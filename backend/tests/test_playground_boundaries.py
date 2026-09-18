import asyncio
from copy import deepcopy
import json
from uuid import uuid4

import pytest

from app.agent_integration import SendCoordinator
from app.agent_request import PreparedAgentRequest
from app.coding_invariants import CodingIntent, check_request, rule_refs, render_refusal
from app.conversation_store import ConversationStorageError
from app.invariants import ValidationResult
from app.llm_client import AgentConfig, LlmResult
from app.memory_selection import build_context
from app.memory_models import MemoryMutation
from app.playground_models import PlaygroundError, SourceReference, ProfileRequest, CompleteSetupRequest, EventRequest
from app.playground_setup_store import PlaygroundSetupStore
from test_playground_service import playground, create, request, event, sources, open_service, Recording
from test_playground_coding import TURN


@pytest.mark.asyncio
@pytest.mark.parametrize("component", ["candidate_validator", "answer_renderer", "refusal_renderer", "missing_coverage"])
async def test_checker_render_boundaries_do_not_commit(playground, monkeypatch, component):
    svc, client = playground
    create(svc)
    if component == "refusal_renderer":
        client.result = LlmResult("completed", json.dumps(TURN | {"decisions": TURN["decisions"] | {"architecture": "MVVM"}}))
    if component == "missing_coverage":
        monkeypatch.setattr(svc, "candidate_validator", lambda *args: ValidationResult("passed"))
    else:
        def broken(*args):
            raise RuntimeError("private diagnostic")
        monkeypatch.setattr(svc, component, broken)
    before = svc.current()
    result = await svc.send(request(svc))
    assert result["receipt"]["turn"]["status"] == "error"
    assert result["receipt"]["turn"]["commit_status"] == "not_attempted"
    assert result["receipt"]["generation_calls"] == 1
    assert sources(result["current"]) == sources(before)
    assert "private diagnostic" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("after_write", [False, True])
async def test_uncertain_pair_commit_reads_authoritative_history(playground, monkeypatch, after_write):
    svc, client = playground
    create(svc)
    original = svc.memory.raw.append_turn
    def fail(*args):
        if after_write:
            original(*args)
        raise ConversationStorageError()
    monkeypatch.setattr(svc.memory.raw, "append_turn", fail)
    result = await svc.send(request(svc))
    assert result["receipt"]["turn"]["decision"] == "accepted"
    assert result["receipt"]["turn"]["commit_status"] == ("unknown" if after_write else "failed")
    assert result["receipt"]["pair_position"] is None
    assert len(result["current"]["memory"]["short_term"]) == (2 if after_write else 0)
    assert len(client.calls) == 1
    monkeypatch.setattr(svc.memory.raw, "append_turn", original)
    next_result = await svc.send(request(svc))
    assert next_result["receipt"]["pair_position"] == (2 if after_write else 0)
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_unavailable_reconciliation_blocks_all_writes_until_explicit_read(playground, monkeypatch):
    svc, client = playground
    create(svc)
    saved_ref = svc.current()["reference"]
    original = svc.send_coordinator.reconcile
    def read_failure(*args):
        raise RuntimeError()
    def lost(*args):
        raise ConversationStorageError()
    monkeypatch.setattr(svc.memory.raw, "append_turn", lost)
    monkeypatch.setattr(svc.send_coordinator, "reconcile", read_failure)
    op = await svc.send(request(svc))
    assert op["current"]["reconciliation_required"]
    with pytest.raises(PlaygroundError, match="reconciliation_required"):
        svc.event(EventRequest(**{k: saved_ref[k] for k in ("task_id", "session_id", "snapshot_id", "state_revision")}, event="PAUSE"))
    monkeypatch.setattr(svc.send_coordinator, "reconcile", original)
    assert not svc.current()["reconciliation_required"]
    assert event(svc, "PAUSE")["receipt"]["outcome"] == "pause_applied"
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_optional_trusted_precheck_and_substituted_adapter_use_same_coordinator(playground):
    svc, client = playground
    create(svc)
    memory = svc.current()["memory"]
    policy = svc.policies.read(memory["task_id"])
    history, _ = build_context(memory)
    rules = rule_refs(policy.values, policy.source)
    def no_generation(*args):
        raise AssertionError("zero-call refusal must not prepare/generate")
    refusal = await svc.send_coordinator.send(session_id=memory["session_id"], query="known structured conflict",
        history_policy=history, prepare=no_generation, adapter_factory=no_generation,
        required_rules=rules, validate=no_generation, render=no_generation,
        refuse=lambda result, origin: render_refusal(policy.values, policy.source, result, origin),
        sources={}, coverage={}, precheck=lambda: check_request(policy.values,
            CodingIntent(architecture="MVVM"), policy.source))
    assert refusal["generation_calls"] == 0 and refusal["turn"]["decision"] == "request_refused"
    assert refusal["turn"]["commit_status"] == "committed"
    assert not client.calls


@pytest.mark.asyncio
async def test_missing_and_inconsistent_sources_fail_before_dispatch(playground):
    svc, client = playground
    create(svc)
    saved = request(svc)
    svc.memory.mutate(MemoryMutation(snapshot_id=saved.snapshot_id, layer="WORKING",
        operation="set", key="current_architecture", value="MVVM"))
    current_memory = svc.memory.read()
    with pytest.raises(PlaygroundError, match="configuration_inconsistent"):
        await svc.send(saved.model_copy(update={"snapshot_id": current_memory["snapshot_id"]}))
    assert not svc.current()["ready"] and not client.calls


@pytest.mark.asyncio
async def test_lifespan_isolates_v2_closes_resources_and_preserves_v1(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    import app.main as main
    for name in ("agent_database_path", "token_database_path", "compression_database_path",
                 "strategies_database_path", "memory_database_path", "personalization_memory_path",
                 "profile_database_path", "task_state_memory_path", "task_state_profile_path",
                 "task_state_database_path"):
        monkeypatch.setattr(main.app.state, name, tmp_path / (name + ".db"))
    clients = []
    def factory():
        client = AsyncMock()
        clients.append(client)
        return client
    monkeypatch.setattr(main, "OpenAIResponsesLlmClient", factory)
    monkeypatch.setattr(main, "OpenAIInputTokenCounter", factory)
    async with main.app.router.lifespan_context(main.app):
        svc = main.app.state.agent_playground
        assert svc.current()["memory"] is None
        create(svc)
        saved = event(svc, "REQUIREMENTS_READY")["current"]
        event(svc, "REQUIREMENTS_REVISION_REQUIRED")
        assert main.app.state.task_state_lab.states.definition.machine_id == "checkout-v1"
        assert main.app.state.invariants_lab.states.definition.machine_id == "checkout-v1"
        assert main.app.state.task_state_lab.current()["memory"] is None
        assert main.app.state.invariants_lab.current()["memory"] is None
    assert all(c.close.await_count == 1 and c.complete.await_count == 0 for c in clients)
    async with main.app.router.lifespan_context(main.app):
        restored = main.app.state.agent_playground.current()
        assert restored["memory"] == saved["memory"]
        assert restored["task_state"]["state_id"] == "PLANNING_REQUIREMENTS"
        assert restored["task_state"]["revision"] == 2
    monkeypatch.setattr(main.app.state, "playground_database_dir", main.app.state.invariants_database_dir)
    with pytest.raises(ValueError, match="different database"):
        async with main.app.router.lifespan_context(main.app):
            pytest.fail("namespace collision accepted")


def test_setup_corruption_and_cross_version_fail_closed(tmp_path):
    svc, stores = open_service(tmp_path, Recording())
    create(svc)
    record = svc.current()["setup"]
    record["machine_id"] = "checkout-v1"
    svc.setups.db.execute("UPDATE setups SET record=?", (json.dumps(record),))
    with pytest.raises(PlaygroundError, match="setup_record_invalid"):
        svc.current()
    for store in stores:
        store.close()
    with pytest.raises(PlaygroundError, match="setup_record_invalid"):
        PlaygroundSetupStore(tmp_path / "setup.db")


def test_reserved_creation_is_atomic_stale_safe_and_idempotent(playground):
    svc, _ = playground
    ids = dict(owner_id=str(uuid4()), task_id=str(uuid4()), session_id=str(uuid4()), expected_snapshot=None)
    db = svc.memory.raw._db()
    db.execute("CREATE TEMP TRIGGER fail AFTER INSERT ON sessions BEGIN SELECT RAISE(ABORT,'fail'); END")
    with pytest.raises(Exception):
        svc.memory.create_reserved(**ids)
    assert svc.memory.read() is None
    db.execute("DROP TRIGGER fail")
    one = svc.memory.create_reserved(**ids)
    assert svc.memory.create_reserved(**ids) == one
    with pytest.raises(Exception):
        svc.memory.create_reserved(**(ids | {"task_id": str(uuid4()), "session_id": str(uuid4())}))
    assert svc.memory.read() == one


@pytest.mark.asyncio
async def test_historical_receipt_and_profile_change_keep_exact_used_sources(playground):
    svc, client = playground
    create(svc)
    receipt = (await svc.send(request(svc)))["receipt"]
    saved = deepcopy(receipt)
    old_memory = svc.current()["memory"]
    svc.select_profile(ProfileRequest(**svc.current()["reference"], profile_preset="mentor"))
    assert svc.current()["memory"] == old_memory
    next_receipt = (await svc.send(request(svc)))["receipt"]
    assert next_receipt["sources"]["profile"]["name"] == "Mentor"
    assert receipt == saved and receipt["sources"]["profile"]["name"] == "Compact Engineer"
    event(svc, "REQUIREMENTS_READY")
    svc.new_conversation(SourceReference(**svc.current()["reference"]))
    assert svc.current()["memory"]["short_term"] == []
    assert receipt == saved


@pytest.mark.parametrize("after_write", [False, True])
def test_recovery_write_failure_does_not_claim_success(playground, monkeypatch, after_write):
    svc, client = playground
    create(svc)
    event(svc, "REQUIREMENTS_READY")
    before = svc.current()
    original = svc.states.compare_and_set
    def fail(*args):
        if after_write:
            original(*args)
        raise RuntimeError()
    monkeypatch.setattr(svc.states, "compare_and_set", fail)
    result = event(svc, "REQUIREMENTS_REVISION_REQUIRED")
    assert result["receipt"]["persistence"] == "unknown" and result["receipt"]["after"] is None
    assert result["current"]["task_state"]["revision"] == before["task_state"]["revision"] + int(after_write)
    assert sources(before) == sources(result["current"]) and not client.calls
