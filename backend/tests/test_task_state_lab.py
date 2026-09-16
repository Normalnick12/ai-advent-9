import asyncio
from copy import deepcopy
from dataclasses import asdict
import json
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
import pytest

from app import main
from app.checkout_workflow import CHECKOUT
from app.llm_client import LlmResult, ConversationMessage
from app.memory_models import MemoryMutation, SnapshotRequest
from app.memory_store import MemoryStore
from app.profiles import ProfileError
from app.sqlite_profile_store import SQLiteProfileStore
from app.sqlite_task_state_store import SQLiteTaskStateStore
from app.task_state import TaskStateError, TaskState
from app.task_state_lab_api import router
from app.task_state_lab_models import (CreateProfile, EditProfile, SelectProfile, PROFILE, WORKING,
    ApplyEvent, InitializeState, RequestSnapshot, SendRequest)
from app.task_state_lab_service import TaskStateLabService
from app.task_state_renderer import render_task_state


class Recording:
    def __init__(self):
        self.calls = []
        self.result = LlmResult("completed", "Ответ модели")
        self.gate = None
        self.entered = asyncio.Event()
        self.service = None

    async def complete(self, messages, config):
        svc = self.service
        assert not svc.memory.raw._db().in_transaction
        assert not svc.profiles._connection.in_transaction
        assert not svc.states._connection.in_transaction
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
    client = Recording()
    svc = TaskStateLabService(memory, profiles, states, client)
    client.service = svc
    yield svc, client
    memory.close(); profiles.close(); states.close()


def setup(svc):
    current = svc.initialize()
    owner = current["memory"]["memory_owner_id"]
    profile = svc.create_profile(CreateProfile(owner_id=owner, fields=PROFILE))["profile"]
    svc.select_profile(profile["profile_id"], SelectProfile(owner_id=owner,
        expected_profile_revision=0, expected_binding_revision=0))
    for key, value in WORKING.items():
        svc.mutate_memory(MemoryMutation(snapshot_id=svc.current()["memory"]["snapshot_id"],
            layer="WORKING", key=key, value=value, operation="set"))
    return svc.current()


def refs(svc):
    c = svc.current()
    p = next(p for p in c["profiles"] if p["profile_id"] == c["binding"]["active_profile_id"])
    return dict(snapshot_id=c["memory"]["snapshot_id"], task_id=c["memory"]["task_id"],
        state_revision=c["task_state"]["revision"], profile_id=p["profile_id"],
        profile_revision=p["revision"], binding_revision=c["binding"]["revision"])


def event(svc, name):
    r = refs(svc)
    return svc.apply_event(ApplyEvent(snapshot_id=r["snapshot_id"], task_id=r["task_id"],
                                      state_revision=r["state_revision"], event=name))


def lifecycle(svc, name):
    return svc.lifecycle(name, SnapshotRequest(snapshot_id=svc.current()["memory"]["snapshot_id"]))


def test_pause_all_stages_and_independent_lifecycle(lab):
    svc, client = lab
    assert svc.current()["memory"] is None and not svc.current()["ready"]
    setup(svc)
    svc.mutate_memory(MemoryMutation(snapshot_id=svc.current()["memory"]["snapshot_id"], layer="LONG_TERM",
        key="project_code", value="FIXED", operation="set"))
    svc.sessions.get(svc.current()["memory"]["session_id"]).commit(ConversationMessage("user", "Stored question"),
        ConversationMessage("assistant", "Stored reply"))
    for next_event in ("REQUIREMENTS_READY", "PLAN_APPROVED", "IMPLEMENTATION_READY", "VALIDATION_CONFIRMED"):
        before = deepcopy(svc.current())
        paused = event(svc, "PAUSE")
        for disallowed in (next_event, "PAUSE", "UNKNOWN"):
            with pytest.raises(TaskStateError):
                event(svc, disallowed)
            assert svc.current()["task_state"] == paused["task_state"]
        after = event(svc, "RESUME")
        for key in ("memory", "profiles", "binding"):
            assert before[key] == paused[key] == after[key]
        assert before["task_state"]["state_id"] == after["task_state"]["state_id"]
        assert after["task_state"]["revision"] == before["task_state"]["revision"] + 2
        event(svc, next_event)
    done = svc.current()["task_state"]
    assert done["is_terminal"] and done["allowed_events"] == ()
    for name in ("PAUSE", "RESUME", "VALIDATION_CONFIRMED"):
        with pytest.raises(TaskStateError):
            event(svc, name)
    lifecycle(svc, "new-conversation")
    lifecycle(svc, "clear-long-term")
    owner = svc.owner()
    p = svc.create_profile(CreateProfile(owner_id=owner, fields=PROFILE))["profile"]
    svc.edit_profile(p["profile_id"], EditProfile(owner_id=owner, expected_revision=0,
        fields=PROFILE.model_copy(update={"name": "Other"})))
    svc.select_profile(p["profile_id"], SelectProfile(owner_id=owner, expected_profile_revision=1,
        expected_binding_revision=svc.current()["binding"]["revision"]))
    assert svc.current()["task_state"] == done
    old_memory = svc.current()["memory"]
    new = lifecycle(svc, "new-task")
    assert new["task_state"]["state_id"] == "PLANNING_REQUIREMENTS" and new["task_state"]["revision"] == 0
    assert new["memory"]["working"] == {} and new["memory"]["short_term"] == []
    assert old_memory["task_id"] in new["memory"]["inactive_tasks"]
    assert svc.states.read(old_memory["task_id"]).state_id == "DONE"
    assert not client.calls


@pytest.mark.asyncio
async def test_controlled_assembly_only_state_changes(lab):
    svc, client = lab
    baseline = setup(svc)
    observations = []
    for events in ((), ("REQUIREMENTS_READY", "PLAN_APPROVED"), ("IMPLEMENTATION_READY",)):
        for name in events:
            event(svc, name)
        op = await svc.send(RequestSnapshot(**refs(svc)), probe=True)
        o = op["observation"]
        observations.append(o)
        assert o["request"] == client.calls[-1]
        assert not o["conversation_committed"]
        assert op["current"]["memory"] == baseline["memory"]
        assert all(v["correct"] for v in o["assembly_checks"].values())
    assert len(client.calls) == 3
    first = observations[0]
    for o in observations[1:]:
        assert o["profile_section"] == first["profile_section"]
        assert o["request"]["messages"] == first["request"]["messages"]
        a = dict(o["request"]["config"]); b = dict(first["request"]["config"])
        a["instructions"] = a["instructions"].replace(o["state_section"], "STATE")
        b["instructions"] = b["instructions"].replace(first["state_section"], "STATE")
        assert a == b and o["state_section"] != first["state_section"]
    state = svc.states.read(refs(svc)["task_id"])
    renamed = TaskState(**(state.model_dump() | {"task_id": str(uuid4()), "revision": 400}))
    assert render_task_state(state, CHECKOUT) == render_task_state(renamed, CHECKOUT)


@pytest.mark.asyncio
async def test_two_new_conversations_real_pairs_and_reopen(lab, tmp_path):
    svc, client = lab
    setup(svc)
    event(svc, "REQUIREMENTS_READY"); event(svc, "PLAN_APPROVED")
    async def send(query, reply):
        before = svc.current()["task_state"]
        client.result = LlmResult("completed", reply)
        op = await svc.send(SendRequest(**refs(svc), message=query))
        assert op["observation"]["conversation_committed"] and op["current"]["task_state"] == before
        assert op["observation"]["request"] == client.calls[-1]
        return op
    execution = await send("EXECUTION_QUERY_UNIQUE", "EXECUTION_REPLY_UNIQUE")
    s0 = svc.current()["memory"]["session_id"]
    assert len(svc.current()["memory"]["short_term"]) == 2
    event(svc, "PAUSE")
    paused = svc.current()
    c1 = lifecycle(svc, "new-conversation")
    assert c1["task_state"] == paused["task_state"] and c1["memory"]["short_term"] == []
    status = await send("Где мы остановились?", "STATUS_REPLY_UNIQUE")
    s1 = svc.current()["memory"]["session_id"]
    assert "EXECUTION_REPLY_UNIQUE" not in json.dumps(client.calls[-1])
    c2 = lifecycle(svc, "new-conversation")
    assert c2["memory"]["short_term"] == [] and c2["task_state"] == paused["task_state"]
    event(svc, "RESUME")
    continued = await send("Продолжим", "IMPLEMENTATION_READY — just text")
    actual = client.calls[-1]
    assert len(actual["messages"]) == 3  # Two memory blocks, only the current query.
    assert actual["messages"][-1]["content"] == "Продолжим"
    for marker in ("EXECUTION_QUERY_UNIQUE", "EXECUTION_REPLY_UNIQUE", "STATUS_REPLY_UNIQUE", "Где мы остановились?"):
        assert marker not in json.dumps(actual, ensure_ascii=False)
    assert svc.current()["task_state"]["state_id"] == "EXECUTION_IMPLEMENT"
    assert svc.current()["task_state"]["revision"] == 4
    assert len(client.calls) == 3
    assert svc.memory.raw.load_session(s0).history and svc.memory.raw.load_session(s1).history
    saved = svc.current()
    memory = MemoryStore(tmp_path / "memory.db")
    profiles = SQLiteProfileStore(tmp_path / "profiles.db")
    states = SQLiteTaskStateStore(tmp_path / "states.db", CHECKOUT)
    try:
        restored = TaskStateLabService(memory, profiles, states, client).current()
        for key in ("memory", "profiles", "binding", "task_state"):
            assert restored[key] == saved[key]
        assert restored["last_transition"] is None and restored["generation_calls"] == 0
    finally:
        memory.close(); profiles.close(); states.close()
    event(svc, "IMPLEMENTATION_READY")
    assert svc.current()["task_state"]["state_id"] == "VALIDATION_CHECK" and len(client.calls) == 3
    assert status["observation"]["selected_state"]["status"] == "PAUSED"
    assert execution["observation"]["selected_state"]["revision"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["error", "refused", "incomplete"])
async def test_failure_and_stale_do_not_commit_or_transition(lab, status):
    svc, client = lab
    setup(svc)
    old = refs(svc)
    event(svc, "PAUSE")
    with pytest.raises(TaskStateError, match="stale"):
        await svc.send(SendRequest(**old, message="x"))
    assert not client.calls
    before = svc.current()
    client.result = LlmResult(status, error_code="failure")
    op = await svc.send(SendRequest(**refs(svc), message="x"))
    assert not op["observation"]["conversation_committed"]
    assert op["observation"]["model_adherence"]["status"] == "unavailable"
    assert op["current"]["memory"] == before["memory"] and op["current"]["task_state"] == before["task_state"]
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_guard_and_cancellation(lab):
    svc, client = lab
    setup(svc)
    client.gate = asyncio.Event()
    pending = asyncio.create_task(svc.send(SendRequest(**refs(svc), message="x")))
    await client.entered.wait()
    for action in (lambda: event(svc, "PAUSE"), lambda: lifecycle(svc, "new-conversation"),
                   lambda: svc.create_profile(CreateProfile(owner_id=svc.owner(), fields=PROFILE))):
        with pytest.raises(TaskStateError, match="busy"):
            action()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not svc.busy and svc.current()["memory"]["short_term"] == []
    assert svc.current()["task_state"]["revision"] == 0


@pytest.mark.asyncio
async def test_api_readiness_partial_setup_strictness_and_recovery(lab, monkeypatch):
    svc, client = lab
    app = FastAPI(); app.state.task_state_lab = svc; app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1/task-state") as api:
        assert (await api.get("/current")).json()["memory"] is None
        setup(svc)
        previous = svc.current()
        original = svc.states.create_initial
        def fail(tid):
            raise TaskStateError("task_state_storage_error", 500)
        monkeypatch.setattr(svc.states, "create_initial", fail)
        response = await api.post("/lifecycle/new-task", json={"snapshot_id": previous["memory"]["snapshot_id"]})
        assert response.status_code == 500
        partial = (await api.get("/current")).json()
        assert partial["memory"]["task_id"] != previous["memory"]["task_id"] and not partial["ready"]
        body = {"snapshot_id": partial["memory"]["snapshot_id"], "task_id": partial["memory"]["task_id"],
                "state_revision": 0, "event": "REQUIREMENTS_READY"}
        assert (await api.post("/events", json=body)).json()["dispatch"] == "not_dispatched"
        monkeypatch.setattr(svc.states, "create_initial", original)
        init = {"snapshot_id": body["snapshot_id"], "task_id": body["task_id"], "machine_id": "checkout-v1"}
        ready = (await api.post("/initialize-state", json=init)).json()
        assert ready["ready"] and ready["memory"]["task_id"] == body["task_id"]
        assert (await api.post("/events", json=body)).status_code == 200
        again = (await api.post("/initialize-state", json=init)).json()
        assert again["task_state"]["state_id"] == "PLANNING_APPROVAL"
        for invalid in (body | {"state_id": "DONE"}, body | {"event": "UNKNOWN"},
                        body | {"task_id": str(uuid4())}, body | {"state_revision": True}):
            rejected = await api.post("/events", json=invalid)
            assert rejected.status_code in (404, 409, 422) and rejected.json()["dispatch"] == "not_dispatched"
        assert not client.calls


@pytest.mark.asyncio
async def test_lifespan_isolation_and_close(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    keys = ("agent_database_path", "token_database_path", "compression_database_path", "strategies_database_path",
        "memory_database_path", "personalization_memory_path", "profile_database_path",
        "task_state_memory_path", "task_state_profile_path", "task_state_database_path")
    for key in keys:
        monkeypatch.setattr(main.app.state, key, tmp_path / (key + ".db"))
    clients = []
    def factory():
        c = AsyncMock(); clients.append(c); return c
    monkeypatch.setattr(main, "OpenAIResponsesLlmClient", factory)
    monkeypatch.setattr(main, "OpenAIInputTokenCounter", factory)
    async with main.app.router.lifespan_context(main.app):
        svc = main.app.state.task_state_lab
        setup(svc)
        event(svc, "PAUSE")
        saved = svc.current()
        assert main.app.state.personalization.current()["memory"] is None
    assert all(c.close.await_count == 1 and c.complete.await_count == 0 for c in clients)
    async with main.app.router.lifespan_context(main.app):
        restored = main.app.state.task_state_lab.current()
        assert restored["task_state"] == saved["task_state"]
    monkeypatch.setattr(main.app.state, "task_state_database_path", main.app.state.profile_database_path)
    with pytest.raises(ValueError, match="different database"):
        async with main.app.router.lifespan_context(main.app):
            pytest.fail("collision accepted")
