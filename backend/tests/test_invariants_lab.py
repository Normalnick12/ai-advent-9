import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
import pytest

from app.agent_sessions import AgentSessionManager
from app.coding_policy_store import CodingPolicyStore
from app.checkout_workflow import CHECKOUT
from app.invariants import ValidationResult
from app.invariants_lab_api import router
from app.invariants_lab_models import TaskReference, EventRequest, ProposalRequest, InvariantsLabError
from app.invariants_lab_service import InvariantsLabService
from app.llm_client import LlmResult
from app.memory_models import MemoryMutation
from app.memory_store import MemoryStore
from app.sqlite_profile_store import SQLiteProfileStore
from app.sqlite_task_state_store import SQLiteTaskStateStore
from test_invariants import VALID


class Recording:
    def __init__(self):
        self.calls = []
        self.result = LlmResult("completed", json.dumps(VALID))
        self.entered = asyncio.Event()
        self.gate = None

    async def complete(self, messages, config):
        self.calls.append({"messages": [asdict(m) for m in messages], "config": asdict(config)})
        self.entered.set()
        if self.gate:
            await self.gate.wait()
        return self.result


@pytest.fixture
def lab(tmp_path):
    memory = MemoryStore(tmp_path / "memory.db")
    profiles = SQLiteProfileStore(tmp_path / "profiles.db")
    states = SQLiteTaskStateStore(tmp_path / "states.db", CHECKOUT)
    policies = CodingPolicyStore(tmp_path / "policies.db")
    client = Recording()
    svc = InvariantsLabService(memory, profiles, states, policies, client)
    yield svc, client
    for store in (memory, profiles, states, policies):
        store.close()


def task_ref(svc):
    m = svc.current()["memory"]
    return TaskReference(task_id=m["task_id"], snapshot_id=m["snapshot_id"])


def event(svc, value):
    c = svc.current()
    return svc.event(EventRequest(**task_ref(svc).model_dump(), state_revision=c["task_state"]["revision"], event=value))


def setup(svc):
    svc.initialize()
    svc.setup(task_ref(svc))
    event(svc, "REQUIREMENTS_READY")
    event(svc, "PLAN_APPROVED")


def request(svc, action="compatible-retry"):
    c = svc.current()
    return ProposalRequest(**task_ref(svc).model_dump(), session_id=c["memory"]["session_id"],
        state_revision=c["task_state"]["revision"], profile_id=c["profile"]["profile_id"],
        profile_revision=c["profile"]["revision"], binding_revision=c["binding"]["revision"],
        policy_id=c["policy"]["policy_id"], policy_version=c["policy"]["definition_version"],
        policy_snapshot_id=c["policy"]["snapshot_id"], action_id=action)


def unchanged(before, after):
    for key in ("task_state", "profile", "binding", "policy"):
        assert before[key] == after[key]
    for key in ("working", "long_term", "task_id", "session_id", "memory_owner_id"):
        assert before["memory"][key] == after["memory"][key]


@pytest.mark.asyncio
async def test_compatible_and_conflict_have_exact_pair_and_actual_input(lab):
    svc, client = lab
    setup(svc)
    before = svc.current()
    op = await svc.propose(request(svc))
    o = op["observation"]
    assert o["turn"]["decision"] == "accepted" and o["turn"]["commit_status"] == "committed"
    assert o["actual_request"] == client.calls[0]
    assert "ACTIVE_INVARIANTS" in client.calls[0]["config"]["instructions"]
    assert client.calls[0]["config"]["text_format"]["type"] == "json_schema"
    assert o["raw_candidate"] not in o["turn"]["reply"]
    assert o["assembly_checks"]["status"] == "pass"
    unchanged(before, op["current"])
    conflict = await svc.propose(request(svc, "conflicting-stack"))
    refused = conflict["observation"]
    assert refused["generation_calls"] == 0 and refused["actual_request"] is None
    assert refused["candidate"] is None and refused["turn"]["decision"] == "request_refused"
    assert len(refused["turn"]["precheck"]["violations"]) == 3
    assert refused["assembly_checks"]["status"] == "not_dispatched"
    assert len(client.calls) == 1 and len(conflict["current"]["memory"]["short_term"]) == 4
    unchanged(before, conflict["current"])


@pytest.mark.asyncio
async def test_fake_candidate_never_enters_history_or_next_input(lab):
    svc, client = lab
    setup(svc)
    before = svc.current()
    client.result = LlmResult("completed", json.dumps(VALID | {"architecture": "MVVM"}))
    bad = client.result.reply
    op = await svc.propose(request(svc))
    o = op["observation"]
    assert o["candidate_preparation"] == "parsed" and o["turn"]["decision"] == "candidate_refused"
    assert o["turn"]["commit_status"] == "committed" and o["raw_candidate"] == bad
    assert "Полученный вариант" in o["turn"]["reply"]
    unchanged(before, op["current"])
    restored = AgentSessionManager(svc.memory.raw).get(before["memory"]["session_id"])
    assert len(restored.history) == 2 and restored.history[1].content == o["turn"]["reply"]
    client.result = LlmResult("completed", json.dumps(VALID))
    await svc.propose(request(svc))
    assert all(bad not in m["content"] for m in client.calls[-1]["messages"])


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["parser", "validator", "unavailable", "renderer", "refusal_renderer", "adapter", "provider"])
async def test_technical_failures_are_not_semantic_refusals(lab, fault):
    svc, client = lab
    setup(svc)
    before = deepcopy(svc.current()["memory"])
    def fail(*args):
        raise RuntimeError("never disclose this")
    if fault == "parser":
        client.result = LlmResult("completed", json.dumps(VALID | {"explanation": "BAD"}))
    elif fault == "validator":
        svc.candidate_validator = fail
    elif fault == "unavailable":
        svc.candidate_validator = lambda *args: ValidationResult("unavailable")
    elif fault == "renderer":
        svc.answer_renderer = fail
    elif fault == "refusal_renderer":
        svc.refusal_renderer = fail
    elif fault == "adapter":
        svc.adapter_factory = fail
    else:
        client.result = LlmResult("refused", error_code="llm_refused")
    op = await svc.propose(request(svc, "conflicting-stack" if fault == "refusal_renderer" else "compatible-retry"))
    turn = op["observation"]["turn"]
    assert turn["status"] == "error" and turn["reply"] is None and turn["commit_status"] == "not_attempted"
    assert op["current"]["memory"] == before
    assert "never disclose" not in str(op) and not svc.busy


@pytest.mark.asyncio
async def test_internal_inconsistency_no_provider_no_pair(lab):
    svc, client = lab
    setup(svc)
    svc.memory.mutate(MemoryMutation(snapshot_id=svc.current()["memory"]["snapshot_id"],
        layer="LONG_TERM", key="preferred_architecture", value="MVVM", operation="set"))
    good = await svc.propose(request(svc))
    assert good["observation"]["turn"]["decision"] == "accepted"
    svc.memory.mutate(MemoryMutation(snapshot_id=svc.current()["memory"]["snapshot_id"],
        layer="WORKING", key="current_architecture", value="MVVM", operation="set"))
    before = svc.current()["memory"]
    bad = await svc.propose(request(svc))
    assert bad["observation"]["turn"]["error_code"] == "configuration_inconsistent"
    assert bad["observation"]["generation_calls"] == 0 and bad["current"]["memory"] == before
    assert len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["compatible-retry", "conflicting-stack"])
async def test_pair_rollback_and_cache_recovery(lab, action):
    svc, _ = lab
    setup(svc)
    svc.memory.raw._db().execute("CREATE TEMP TRIGGER fail AFTER INSERT ON messages BEGIN SELECT RAISE(ABORT,'fail'); END")
    before = svc.current()["memory"]
    op = await svc.propose(request(svc, action))
    assert op["observation"]["turn"]["commit_status"] == "failed"
    assert op["observation"]["turn"]["status"] == "error"
    assert op["current"]["memory"] == before and not svc.recovery_required
    svc.memory.raw._db().execute("DROP TRIGGER fail")
    assert (await svc.propose(request(svc, action)))["observation"]["turn"]["commit_status"] == "committed"


@pytest.mark.asyncio
async def test_uncertain_write_reconciles_without_replay(lab, monkeypatch):
    svc, client = lab
    setup(svc)
    original = svc.memory.raw.append_turn
    def write_then_fail(*args):
        original(*args)
        raise RuntimeError("lost storage acknowledgement")
    monkeypatch.setattr(svc.memory.raw, "append_turn", write_then_fail)
    op = await svc.propose(request(svc))
    assert op["observation"]["turn"]["commit_status"] == "unknown"
    assert len(op["current"]["memory"]["short_term"]) == 2
    assert len(svc.sessions.get(op["current"]["memory"]["session_id"]).history) == 2
    assert len(client.calls) == 1
    monkeypatch.setattr(svc.memory.raw, "append_turn", original)
    await svc.propose(request(svc))
    assert len(client.calls) == 2 and len(svc.current()["memory"]["short_term"]) == 4


@pytest.mark.asyncio
async def test_failed_recovery_blocks_until_authoritative_read(lab, monkeypatch):
    svc, client = lab
    setup(svc)
    req = request(svc)
    def fail(*args):
        raise RuntimeError("failed read")
    with monkeypatch.context() as patch:
        patch.setattr(svc.memory.raw, "append_turn", fail)
        # Reconciliation uses load_session, ordinary source reads are allowed until commit.
        original = svc.memory.raw.load_session
        def load(sid):
            if svc.recovery_required:
                return fail()
            return original(sid)
        patch.setattr(svc.memory.raw, "load_session", load)
        op = await svc.propose(req)
        assert op["current"] is None and svc.recovery_required
        with pytest.raises(InvariantsLabError, match="recovery_required"):
            await svc.propose(req)
        assert len(client.calls) == 1
    assert svc.current()["recovery_required"] is False


@pytest.mark.asyncio
async def test_busy_cancellation_and_stale_refs(lab):
    svc, client = lab
    setup(svc)
    req = request(svc)
    client.gate = asyncio.Event()
    task = asyncio.create_task(svc.propose(req))
    await client.entered.wait()
    with pytest.raises(InvariantsLabError, match="busy"):
        event(svc, "PAUSE")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not svc.busy and svc.current()["memory"]["short_term"] == []
    svc.sessions.get(req.session_id).ensure_available()
    client.gate = None
    event(svc, "PAUSE")
    with pytest.raises(InvariantsLabError):
        await svc.propose(req)
    event(svc, "RESUME")
    await svc.propose(request(svc))
    assert len(client.calls) == 2


def test_lifecycle_and_partial_setup(lab, monkeypatch):
    svc, client = lab
    assert svc.current()["memory"] is None and not svc.current()["ready"]
    svc.initialize()
    tid = svc.current()["memory"]["task_id"]
    with monkeypatch.context() as patch:
        def fail(*args):
            raise RuntimeError("storage unavailable")
        patch.setattr(svc.policies, "create", fail)
        with pytest.raises(RuntimeError):
            svc.setup(task_ref(svc))
    assert svc.current()["policy"] is None and svc.current()["memory"]["task_id"] == tid
    svc.setup(task_ref(svc))
    before = svc.current()
    assert svc.setup(task_ref(svc))["policy"] == before["policy"]
    svc.lifecycle("new-conversation", task_ref(svc))
    assert svc.current()["policy"] == before["policy"]
    svc.lifecycle("new-task", task_ref(svc))
    assert svc.current()["policy"] is None and svc.policies.read(tid).view() == before["policy"]
    assert svc.current()["task_state"]["revision"] == 0 and not client.calls


@pytest.mark.asyncio
async def test_http_contracts_and_technical_receipt(lab):
    svc, recording = lab
    app = FastAPI()
    app.state.invariants_lab = svc
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/invariants/current")).json()["memory"] is None
        setup(svc)
        req = request(svc).model_dump()
        for bad in (req | {"action_id": "unknown"}, req | {"instructions": "bypass"}):
            response = await client.post("/api/v1/invariants/proposals", json=bad)
            assert response.status_code == 422 and response.json()["dispatch"] == "not_dispatched"
        response = await client.post("/api/v1/invariants/proposals", json=req | {"task_id": str(uuid4())})
        assert response.status_code == 404 and not recording.calls
        recording.result = LlmResult("completed", "invalid json")
        response = await client.post("/api/v1/invariants/proposals", json=req)
        assert response.status_code == 500
        receipt = response.json()["observation"]
        assert receipt["turn"]["error_code"] == "invalid_candidate" and receipt["actual_request"] == recording.calls[0]
        response = await client.post("/api/v1/invariants/proposals", json=request(svc, "conflicting-stack").model_dump())
        assert response.status_code == 200 and response.json()["observation"]["generation_calls"] == 0
