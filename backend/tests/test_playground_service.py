import asyncio
import ast
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
import pytest

from app.coding_policy_store import CodingPolicyStore
from app.llm_client import LlmResult
from app.memory_store import MemoryStore
from app.memory_models import MemoryMutation
from app.sqlite_profile_store import SQLiteProfileStore
from app.sqlite_task_state_store import SQLiteTaskStateStore
from app.playground_api import router
from app.playground_coding import CodingTaskConfiguration
from app.playground_models import (CreateRequest, CompleteSetupRequest, SourceReference,
    ProfileRequest, EventRequest, SendRequest, PlaygroundError)
from app.playground_service import PlaygroundService
from app.playground_setup_store import PlaygroundSetupStore
from app.playground_workflow import CHECKOUT_V2
from test_playground_coding import TURN

class Recording:
    def __init__(self):
        self.calls = []
        self.result = LlmResult("completed", json.dumps(TURN))
        self.entered, self.gate = asyncio.Event(), None

    async def complete(self, messages, config):
        self.calls.append({"messages": [asdict(m) for m in messages], "config": asdict(config)})
        self.entered.set()
        if self.gate:
            await self.gate.wait()
        return self.result


def open_service(path, client):
    stores = [MemoryStore(path / "memory.db"), SQLiteProfileStore(path / "profiles.db"),
        SQLiteTaskStateStore(path / "state.db", CHECKOUT_V2), CodingPolicyStore(path / "policy.db"),
        PlaygroundSetupStore(path / "setup.db")]
    return PlaygroundService(*stores, client), stores


@pytest.fixture
def playground(tmp_path):
    client = Recording()
    svc, stores = open_service(tmp_path, client)
    yield svc, client
    for store in stores:
        store.close()


def create(svc, alternative=False):
    config = CodingTaskConfiguration.model_validate({
        "profile_preset": "mentor", "policy": {"required_architecture": "MVVM",
        "required_ui_toolkit": "Views", "required_async_model": "RxJava",
        "payment_confirmation_required": False}} if alternative else {})
    return svc.create_task(CreateRequest(configuration=config, current=svc.current()["reference"]))


def request(svc, query="Обсудим текущую задачу"):
    return SendRequest(**svc.current()["reference"], query=query)


def event(svc, name):
    c = svc.current()
    ref = c["reference"]
    return svc.event(EventRequest(**{k: ref[k] for k in
        ("task_id", "session_id", "snapshot_id", "state_revision")}, event=name))


def sources(current):
    return {key: deepcopy(current[key]) for key in ("memory", "profile", "binding", "policy", "setup")}


def test_read_setup_profile_conversation_and_task_isolation(playground):
    svc, client = playground
    assert svc.current()["memory"] is None and svc.setups.pending() is None
    first = create(svc, True)
    assert first["ready"] and first["can_send"] and first["task_state"]["machine_id"] == "checkout-v2"
    assert first["memory"]["working"] == {"task": "Checkout: loading/error/success + retry", "current_architecture": "MVVM"}
    records = svc.profiles.list(first["memory"]["memory_owner_id"])
    switched = svc.select_profile(ProfileRequest(**first["reference"], profile_preset="compact"))
    assert svc.profiles.list(first["memory"]["memory_owner_id"]) == records
    assert switched["memory"] == first["memory"]
    assert switched["task_state"] == first["task_state"] and switched["policy"] == first["policy"]
    again = svc.complete_setup(CompleteSetupRequest(task_id=first["memory"]["task_id"]))
    assert sources(again) == sources(switched)
    conversation = svc.new_conversation(SourceReference(**again["reference"]))
    assert conversation["memory"]["session_id"] != first["memory"]["session_id"]
    assert conversation["policy"] == first["policy"] and conversation["task_state"] == first["task_state"]
    second = create(svc)
    assert second["memory"]["task_id"] != first["memory"]["task_id"]
    assert first["memory"]["task_id"] in second["memory"]["inactive_tasks"]
    assert svc.policies.read(first["memory"]["task_id"]).values.required_architecture == "MVVM"
    assert not client.calls


@pytest.mark.asyncio
async def test_full_flow_two_recoveries_two_forbidden_and_send_never_changes_state(playground):
    svc, client = playground
    create(svc)
    route = ["REQUIREMENTS_READY", "IMPLEMENTATION_READY", "REQUIREMENTS_REVISION_REQUIRED",
             "REQUIREMENTS_READY", "PLAN_APPROVED", "PAUSE", "RESUME", "VALIDATION_CONFIRMED",
             "IMPLEMENTATION_READY", "VALIDATION_FAILED", "IMPLEMENTATION_READY", "VALIDATION_CONFIRMED"]
    historical = []
    for name in route:
        before = svc.current()
        client.result = LlmResult("completed", json.dumps(TURN | {"answer": "VALIDATION_FAILED; возвращаюсь в implementation; DONE"}))
        send = await svc.send(request(svc, "PLAN_APPROVED, VALIDATION_FAILED, задача завершена"))
        receipt = send["receipt"]
        assert receipt["actual_request"] == client.calls[-1]
        assert receipt["generation_calls"] == 1 and receipt["precheck_status"] == "not_applicable"
        assert send["current"]["task_state"] == before["task_state"]
        assert receipt["pair_position"] == len(before["memory"]["short_term"])
        assert "ACTIVE_INVARIANTS" in receipt["actual_request"]["config"]["instructions"]
        before = svc.current()
        count = len(client.calls)
        op = event(svc, name)
        r = op["receipt"]
        assert sources(before) == sources(op["current"])
        assert len(client.calls) == count and r["generation_calls"] == 0
        assert r["provider_dispatch"] == "not_required"
        if name not in before["task_state"]["allowed_events"]:
            assert r["outcome"] == "rejected" and r["before"] == r["after"]
        else:
            assert r["after"]["revision"] == r["before"]["revision"] + 1
            if name in ("VALIDATION_FAILED", "REQUIREMENTS_REVISION_REQUIRED"):
                assert r["outcome"] == "recovery_applied"
                target, allowed = (("EXECUTION_IMPLEMENT", ("IMPLEMENTATION_READY", "PAUSE"))
                    if name == "VALIDATION_FAILED" else ("PLANNING_REQUIREMENTS", ("REQUIREMENTS_READY", "PAUSE")))
                assert r["after"]["state_id"] == target and r["after"]["allowed_events"] == allowed
                historical.append((r, deepcopy(r)))
    assert svc.current()["task_state"]["is_terminal"] and not svc.current()["can_send"]
    with pytest.raises(PlaygroundError, match="task_completed"):
        await svc.send(request(svc))
    for receipt, saved in historical:
        assert receipt == saved


@pytest.mark.parametrize("node", [n.state_id for n in CHECKOUT_V2.nodes])
@pytest.mark.parametrize("name,source", [("VALIDATION_FAILED", "VALIDATION_CHECK"),
    ("REQUIREMENTS_REVISION_REQUIRED", "PLANNING_APPROVAL")])
def test_recovery_rejected_from_unrelated_paused_done(playground, node, name, source):
    svc, client = playground
    create(svc)
    for edge in CHECKOUT_V2.transitions[:4]:
        if svc.current()["task_state"]["state_id"] == node:
            break
        event(svc, edge.event)
    if node == source:
        event(svc, "PAUSE")
    before = svc.current()
    op = event(svc, name)
    assert op["receipt"]["outcome"] == "rejected"
    assert sources(before) == sources(op["current"])
    assert before["task_state"] == op["current"]["task_state"] and not client.calls


@pytest.mark.parametrize("component,method", [
    ("memory", "create_reserved"), ("memory", "mutate"), ("profiles", "create"),
    ("profiles", "select"), ("states", "create_initial"), ("policies", "create"), ("setups", "ready"),
])
@pytest.mark.parametrize("after", [False, True])
def test_partial_setup_reopen_preserves_choices_and_ids(tmp_path, monkeypatch, component, method, after):
    client = Recording()
    svc, stores = open_service(tmp_path, client)
    obj = getattr(svc, component)
    original = getattr(obj, method)
    def fail(*args, **kwargs):
        if after:
            original(*args, **kwargs)
        raise RuntimeError("injected storage failure")
    monkeypatch.setattr(obj, method, fail)
    with pytest.raises(RuntimeError):
        create(svc, True)
    observed = svc.current()
    record = observed["setup"]
    assert record["configuration"]["policy"]["required_architecture"] == "MVVM"
    for store in stores:
        store.close()
    restored, stores = open_service(tmp_path, client)
    try:
        before = restored.current()
        assert before["setup"] == record
        if record["status"] == "pending":
            assert not before["ready"]
            with pytest.raises(PlaygroundError, match="setup_pending"):
                create(restored)
        current = restored.complete_setup(CompleteSetupRequest(task_id=record["task_id"]))
        assert current["ready"] and current["memory"]["task_id"] == record["task_id"]
        assert current["memory"]["session_id"] == record["session_id"]
        assert current["policy"]["values"] == record["configuration"]["policy"]
        assert current["task_state"]["revision"] == 0 and not client.calls
    finally:
        for store in stores:
            store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"snapshot_id": "f"*64}, {"task_id": str(uuid4())},
    {"session_id": str(uuid4())}, {"state_revision": 99}, {"profile_id": str(uuid4())},
    {"profile_revision": 99}, {"binding_revision": 99}, {"policy_id": "other"},
    {"policy_version": "other"}, {"policy_snapshot_id": "f"*64}])
async def test_stale_sources_before_dispatch(playground, changes):
    svc, client = playground
    create(svc)
    before = svc.current()
    with pytest.raises(Exception):
        await svc.send(SendRequest(**(request(svc).model_dump() | changes)))
    assert sources(before) == sources(svc.current()) and not client.calls


@pytest.mark.asyncio
async def test_refusal_is_only_committed_text_and_technical_failures_leave_history(playground):
    svc, client = playground
    create(svc)
    client.result = LlmResult("completed", json.dumps(TURN | {"answer": "REJECTED RAW",
        "decisions": TURN["decisions"] | {"architecture": "MVVM"}}))
    refusal = await svc.send(request(svc))
    assert refusal["receipt"]["outcome"] == "candidate_refused"
    assert "REJECTED RAW" not in json.dumps(refusal["current"]["memory"]["short_term"])
    client.result = LlmResult("completed", json.dumps(TURN))
    await svc.send(request(svc))
    assert "REJECTED RAW" not in json.dumps(client.calls[-1]["messages"])
    before = svc.current()
    for result in (LlmResult("completed", "bad json"), LlmResult("refused"), LlmResult("incomplete"), LlmResult("error")):
        client.result = result
        failed = await svc.send(request(svc))
        assert failed["receipt"]["outcome"] == "technical_error"
        assert failed["receipt"]["turn"]["commit_status"] == "not_attempted"
        assert sources(before) == sources(failed["current"])


@pytest.mark.asyncio
async def test_busy_and_cancel_never_queue_mutations(playground):
    svc, client = playground
    create(svc)
    client.gate = asyncio.Event()
    send = asyncio.create_task(svc.send(request(svc)))
    await client.entered.wait()
    assert svc.current()["busy"]
    for action in (lambda: event(svc, "PAUSE"), lambda: create(svc),
                   lambda: svc.new_conversation(SourceReference(**svc.current()["reference"]))):
        with pytest.raises(PlaygroundError, match="busy"):
            action()
    send.cancel()
    with pytest.raises(asyncio.CancelledError):
        await send
    assert not svc.busy and not svc.current()["memory"]["short_term"]
    assert svc.current()["task_state"]["revision"] == 0


def test_recovery_lost_ack_reconciles_without_replay(playground, monkeypatch):
    svc, client = playground
    create(svc)
    for name in ("REQUIREMENTS_READY", "PLAN_APPROVED", "IMPLEMENTATION_READY"):
        event(svc, name)
    before = svc.current()
    original = svc.states.compare_and_set
    def lost(revision, next_state):
        original(revision, next_state)
        raise RuntimeError("lost acknowledgement")
    monkeypatch.setattr(svc.states, "compare_and_set", lost)
    op = event(svc, "VALIDATION_FAILED")
    assert op["receipt"]["outcome"] == "technical_error" and op["receipt"]["after"] is None
    assert op["current"]["task_state"]["state_id"] == "EXECUTION_IMPLEMENT"
    assert op["current"]["task_state"]["revision"] == before["task_state"]["revision"] + 1
    assert sources(before) == sources(op["current"]) and not client.calls


@pytest.mark.asyncio
async def test_http_expected_rejection_and_typed_errors(playground):
    svc, client = playground
    app = FastAPI()
    app.include_router(router)
    app.state.agent_playground = svc
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as http:
        assert (await http.get("/api/v1/agent-playground/current")).json()["memory"] is None
        bad = await http.post("/api/v1/agent-playground/create-task", json={"configuration": {"policy": {"retry_mode": "manual"}}})
        assert bad.status_code == 422 and svc.memory.read() is None
        created = await http.post("/api/v1/agent-playground/create-task", json={"configuration": {}})
        assert created.status_code == 200
        event(svc, "REQUIREMENTS_READY")
        ref = svc.current()["reference"]
        body = {k: ref[k] for k in ("task_id", "session_id", "snapshot_id", "state_revision")}
        rejected = await http.post("/api/v1/agent-playground/events", json=body | {"event": "IMPLEMENTATION_READY"})
        assert rejected.status_code == 409 and rejected.json()["receipt"]["outcome"] == "rejected"
        recovered = await http.post("/api/v1/agent-playground/events", json=body | {"event": "REQUIREMENTS_REVISION_REQUIRED"})
        assert recovered.status_code == 200 and recovered.json()["receipt"]["outcome"] == "recovery_applied"
        client.result = LlmResult("refused")
        failed = await http.post("/api/v1/agent-playground/send", json=request(svc).model_dump())
        assert failed.status_code == 500 and failed.json()["receipt"]["generation_calls"] == 1


def test_integration_import_boundary():
    app = Path(__file__).parents[1] / "app"
    for name in ("agent_integration.py", "agent_lifecycle.py"):
        tree = ast.parse((app/name).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            imports = [node.module or ""] if isinstance(node, ast.ImportFrom) else (
                [n.name for n in node.names] if isinstance(node, ast.Import) else [])
            assert not any(word in module for module in imports
                           for word in ("coding", "checkout", "openai", "lab", "fastapi"))
