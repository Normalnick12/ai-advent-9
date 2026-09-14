import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from app.memory_models import *
from app.memory_context import SEED, QUERY, LONG_FIXTURE, WORKING_FIXTURE, EXPECTED, build_context
from app.memory_store import MemoryStore
from app.memory_service import MemoryExperimentService
from app.llm_client import LlmResult, TokenUsage
from app.conversation_store import ConversationStorageError
from app.main import app
from app.memory_api import service


class RecordingClient:
    def __init__(self, store):
        self.store, self.calls, self.count_calls = store, [], 0
        self.result = None
        self.gate = None
        self.entered = asyncio.Event()

    async def complete(self, messages, config):
        assert not self.store.raw._db().in_transaction
        self.calls.append((messages, config))
        self.entered.set()
        if self.gate:
            await self.gate.wait()
        if self.result:
            return self.result
        if config.text_format is None:
            return LlmResult("completed", "Принято.", usage=TokenUsage(input_tokens=10, output_tokens=2))
        long_term = json.loads(messages[0].content.split("\n", 1)[1])
        working = json.loads(messages[1].content.split("\n", 1)[1])
        # Fake derives its response only from actual input, never from the stage oracle.
        title = None
        for m in messages[2:-1]:
            for line in m.content.splitlines():
                if line.startswith("error_title="):
                    title = line.split("=", 1)[1]
        return LlmResult("completed", json.dumps(dict(
            project_code=long_term.get("project_code"),
            release_marker=working.get("release_marker"), current_task=working.get("task"),
            effective_architecture=working.get("current_architecture", long_term.get("preferred_architecture")),
            last_error_title=title, next_step="Уточнить следующий шаг."
        ), ensure_ascii=False))


@pytest.fixture
def lab(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    client = RecordingClient(store)
    svc = MemoryExperimentService(store, client)
    yield svc, client
    store.close()


def req(svc):
    return SnapshotRequest(snapshot_id=svc.read()["state"]["snapshot_id"])


def mutate(svc, layer, key, value=None, operation="set"):
    body = dict(snapshot_id=req(svc).snapshot_id, layer=layer, key=key, operation=operation)
    if operation == "set":
        body["value"] = value
    return svc.mutate(MemoryMutation(**body))


async def setup_a(svc):
    svc.initialize()
    await svc.send(MemoryMessage(snapshot_id=req(svc).snapshot_id, message=SEED))
    for layer, data in (("LONG_TERM", LONG_FIXTURE), ("WORKING", WORKING_FIXTURE)):
        for key, value in data.items():
            mutate(svc, layer, key, value)


@pytest.mark.parametrize("bad", [
    {"layer": "SHORT"}, {"key": "project_code"}, {"value": None}, {"value": 3},
    {"value": ""}, {"value": " "}, {"value": "x"*257}, {"extra": 1},
    {"operation": "remove", "value": None},
])
def test_mutation_validation(bad):
    base = dict(snapshot_id="a"*64, layer="WORKING", key="task", operation="set", value="Checkout")
    with pytest.raises(ValidationError):
        MemoryMutation(**(base | bad))


def test_initialization_explicit_writes_and_noop(lab):
    svc, client = lab
    assert svc.read()["state"] is None
    a = svc.initialize()["state"]
    assert svc.initialize()["state"] == a
    assert len({a[k] for k in ("memory_owner_id", "task_id", "session_id")}) == 3
    b = mutate(svc, "WORKING", "current_architecture", "MVI")["state"]
    assert b["short_term"] == a["short_term"] and b["long_term"] == {}
    assert mutate(svc, "WORKING", "task", operation="remove")["state"] == b
    assert mutate(svc, "WORKING", "current_architecture", "MVI")["state"] == b
    assert not client.calls
    with pytest.raises(MemoryError, match="stale_snapshot"):
        svc.transition("new-task", SnapshotRequest(snapshot_id=a["snapshot_id"]))


@pytest.mark.asyncio
async def test_a_through_e_exact_context_isolation_and_call_budget(lab):
    svc, client = lab
    await setup_a(svc)
    a = deepcopy(svc.read()["state"])
    for stage in "ABCDE":
        if stage == "B":
            mutate(svc, "WORKING", "current_architecture", operation="remove")
        elif stage == "C":
            svc.transition("new-conversation", req(svc))
        elif stage == "D":
            svc.transition("new-task", req(svc))
        elif stage == "E":
            svc.transition("clear-long-term", req(svc))
        before = deepcopy(svc.read()["state"])
        op = await svc.verify(stage, req(svc))
        assert svc.read()["state"] == before
        obs = op["observation"]
        assert tuple(obs["parsed"][f] for f in FIELDS) == EXPECTED[stage]
        assert all(c["correct"] for c in obs["input_checks"].values())
        assert all(c["correct"] for c in obs["output_checks"].values())
        messages, config = client.calls[-1]
        assert messages[-1].content == QUERY
        assert obs["request"]["input"] == [{"role": m.role, "content": m.content} for m in messages]
        assert not obs["committed"]
        if stage == "A":
            assert "MVVM" not in json.dumps(obs["request"], ensure_ascii=False)
            assert obs["stored"]["long_term"]["preferred_architecture"] == "MVVM"
            assert obs["selection"]["excluded"][0]["reason"] == "working_override"
        if stage in "CDE":
            assert "Сбой-47" not in json.dumps(obs["request"], ensure_ascii=False)
        if stage in "DE":
            assert "RC-42" not in json.dumps(obs["request"], ensure_ascii=False)
    assert len(client.calls) == 6 and client.count_calls == 0
    assert svc.store.raw.load_session(a["session_id"]).history[0].content == SEED
    assert svc.store.working.load(a["task_id"], a["memory_owner_id"])["release_marker"] == "RC-42"
    assert len(svc.read()["state"]["inactive_sessions"]) == 2
    assert len(svc.read()["state"]["inactive_tasks"]) == 1
    assert {r[0] for r in svc.store.raw._db().execute("SELECT name FROM sqlite_master WHERE type='table'")} == {
        "sessions", "messages", "memory_owners", "working_memory", "long_term_memory",
        "session_tasks", "memory_bindings"}


@pytest.mark.asyncio
async def test_restart_restores_nonempty_memory_and_cache_without_provider(lab, tmp_path):
    svc, client = lab
    await setup_a(svc)
    before = svc.read()["state"]
    path = svc.store.raw._db().execute("PRAGMA database_list").fetchone()[2]
    reopened = MemoryStore(__import__("pathlib").Path(path))
    unused = AsyncMock()
    restored = MemoryExperimentService(reopened, unused)
    try:
        assert restored.read()["state"] == before
        assert not restored.busy and restored.sessions._sessions == {}
        assert restored.sessions.get(before["session_id"]).history[0].content == SEED
        unused.complete.assert_not_called()
        assert len(client.calls) == 1
    finally:
        reopened.close()


@pytest.mark.parametrize("action", ["new-conversation", "new-task"])
def test_lifecycle_failure_rolls_back_and_cache_is_not_published(lab, action):
    svc, client = lab
    before = svc.initialize()["state"]
    svc.sessions.get(before["session_id"])
    cached = dict(svc.sessions._sessions)
    db = svc.store.raw._db()
    db.execute("CREATE TEMP TRIGGER reject_binding BEFORE UPDATE ON memory_bindings BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(ConversationStorageError):
        svc.transition(action, req(svc))
    assert svc.read()["state"] == before and svc.sessions._sessions == cached
    assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM working_memory").fetchone()[0] == 1
    assert not svc.busy and not client.calls


def test_initialize_failure_and_corrupt_restore(lab):
    svc, _ = lab
    db = svc.store.raw._db()
    db.execute("CREATE TEMP TRIGGER reject_init BEFORE INSERT ON memory_bindings BEGIN SELECT RAISE(ABORT,'injected'); END")
    with pytest.raises(ConversationStorageError):
        svc.initialize()
    assert svc.read()["state"] is None
    db.execute("DROP TRIGGER reject_init")
    svc.initialize()
    db.execute("UPDATE working_memory SET data='{\"unknown\":\"x\"}'")
    with pytest.raises(MemoryError, match="memory_state_invalid"):
        svc.read()


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [
    LlmResult("error", error_code="fake"), LlmResult("incomplete"), LlmResult("refused"),
    LlmResult("completed", "not json"),
    LlmResult("completed", '{"project_code":null,"project_code":"duplicate"}'),
])
async def test_probe_failures_are_side_effect_free(lab, result):
    svc, client = lab
    await setup_a(svc)
    before = svc.read()["state"]
    client.result = result
    op = await svc.verify("A", req(svc))
    assert svc.read()["state"] == before
    assert all(c["correct"] for c in op["observation"]["input_checks"].values())
    assert all(c["correct"] is None for c in op["observation"]["output_checks"].values())
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_wrong_model_is_not_storage_failure_and_conflict_is_visible(lab):
    svc, client = lab
    await setup_a(svc)
    output = dict(zip(FIELDS, EXPECTED["A"])) | {"next_step": "test", "effective_architecture": "MVVM"}
    client.result = LlmResult("completed", json.dumps(output))
    op = await svc.verify("A", req(svc))
    assert op["observation"]["input_checks"]["effective_architecture"]["correct"]
    assert not op["observation"]["output_checks"]["effective_architecture"]["correct"]
    # A conflicting assistant assertion is real selected context, not silently discarded.
    db = svc.store.raw._db()
    db.execute("UPDATE messages SET content='error_title=Other' WHERE role='assistant'")
    op = await svc.verify("A", req(svc))
    assert op["observation"]["input_checks"]["last_error_title"]["status"] == "conflict"


@pytest.mark.asyncio
async def test_busy_cancellation_stale_and_failure_preserve_memory(lab):
    svc, client = lab
    await setup_a(svc)
    before = svc.read()["state"]
    client.gate = asyncio.Event()
    client.entered.clear()
    probe = asyncio.create_task(svc.verify("A", req(svc)))
    await client.entered.wait()
    with pytest.raises(MemoryError, match="memory_busy"):
        svc.transition("new-task", req(svc))
    probe.cancel()
    with pytest.raises(asyncio.CancelledError):
        await probe
    assert not svc.busy and svc.read()["state"] == before
    client.gate = None
    client.result = LlmResult("error", error_code="fake")
    await svc.send(MemoryMessage(snapshot_id=req(svc).snapshot_id, message="Теперь MVI"))
    assert svc.read()["state"] == before


@pytest.mark.asyncio
async def test_normal_turn_exact_history_and_no_structured_extraction(lab):
    svc, client = lab
    svc.initialize()
    for text in ("Предпочитаю Compose", "Теперь MVI"):
        await svc.send(MemoryMessage(snapshot_id=req(svc).snapshot_id, message=text))
    state = svc.read()["state"]
    assert state["working"] == state["long_term"] == {}
    assert [m.content for m in client.calls[-1][0]][2:] == ["Предпочитаю Compose", "Принято.", "Теперь MVI"]
    with pytest.raises(MemoryError, match="scenario_not_applicable"):
        await svc.verify("A", req(svc))
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_api_strict_read_recovery_and_wrong_identity(lab):
    svc, client = lab
    app.dependency_overrides[service] = lambda: svc
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            assert (await http.get("/api/v1/memory-layers/current")).json()["state"] is None
            a = (await http.post("/api/v1/memory-layers/initialize", json={})).json()["state"]
            assert (await http.post("/api/v1/memory-layers/memory", json={
                "snapshot_id": a["snapshot_id"], "layer": "WORKING", "key": "project_code",
                "operation": "set", "value": "bad"})).status_code == 422
            assert (await http.post("/api/v1/memory-layers/messages", json={
                "snapshot_id": a["snapshot_id"], "message": "hi", "history": []})).status_code == 422
            await http.post("/api/v1/memory-layers/lifecycle/new-task", json={"snapshot_id": a["snapshot_id"]})
            b = (await http.get("/api/v1/memory-layers/current")).json()["state"]
            assert b["session_id"] != a["session_id"]
            assert (await http.post("/api/v1/memory-layers/lifecycle/new-task",
                                   json={"snapshot_id": a["snapshot_id"]})).status_code == 409
            assert (await http.get("/api/v1/memory-layers/current")).json()["state"] == b
            assert not client.calls
    finally:
        app.dependency_overrides.pop(service, None)
