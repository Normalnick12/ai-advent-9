from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.checkout_workflow import CHECKOUT
from app.sqlite_task_state_store import SQLiteTaskStateStore
from app.task_state import TaskState, TaskStateDefinition, StateTransition, TaskStateError, resolve


def snapshot(node="PLANNING_REQUIREMENTS", status="ACTIVE", revision=0):
    return TaskState(task_id=str(uuid4()), machine_id="checkout-v1", state_id=node,
                     status=status, revision=revision)


@pytest.mark.parametrize("bad", [
    {"task_id": "not-uuid"}, {"task_id": str(uuid4()).upper()}, {"status": "RUNNING"},
    {"revision": -1}, {"revision": True}, {"revision": "1"}, {"revision": 1.2},
    {"phase": "execution"}, {"step": "implement"}, {"expected_action": "finish"},
    {"machine_id": "checkout"}, {"state_id": ""},
])
def test_strict_canonical_model(bad):
    with pytest.raises(ValidationError):
        TaskState.model_validate(snapshot().model_dump() | bad)


def test_snapshots_and_definition_are_immutable():
    state = snapshot()
    with pytest.raises(ValidationError):
        state.revision = 10
    with pytest.raises(ValidationError):
        CHECKOUT.nodes[0].phase = "wrong"
    with pytest.raises(ValidationError):
        CHECKOUT.transitions = ()


@pytest.mark.parametrize("bad", [
    {"initial_node": "MISSING"}, {"nodes": CHECKOUT.nodes + (CHECKOUT.nodes[0],)},
    {"transitions": CHECKOUT.transitions + (CHECKOUT.transitions[0],)},
    {"transitions": (StateTransition(source="MISSING", event="GO", target="DONE"),)},
    {"transitions": (StateTransition(source="DONE", event="GO", target="DONE"),)},
    {"transitions": (StateTransition(source="PLANNING_APPROVAL", event="GO", target="MISSING"),)},
    {"transitions": (StateTransition(source="PLANNING_APPROVAL", event="PAUSE", target="DONE"),)},
    {"transitions": (StateTransition(source="PLANNING_APPROVAL", event="RESUME", target="DONE"),)},
])
def test_invalid_definition(bad):
    values = dict(machine_id=CHECKOUT.machine_id, initial_node=CHECKOUT.initial_node,
                  nodes=CHECKOUT.nodes, transitions=CHECKOUT.transitions)
    with pytest.raises(ValidationError):
        TaskStateDefinition(**(values | bad))


EVENTS = ("REQUIREMENTS_READY", "PLAN_APPROVED", "IMPLEMENTATION_READY", "VALIDATION_CONFIRMED",
          "PAUSE", "RESUME", "UNKNOWN", "VALIDATION_PASSED")
EXPECTED = {
    ("PLANNING_REQUIREMENTS", "REQUIREMENTS_READY"): "PLANNING_APPROVAL",
    ("PLANNING_APPROVAL", "PLAN_APPROVED"): "EXECUTION_IMPLEMENT",
    ("EXECUTION_IMPLEMENT", "IMPLEMENTATION_READY"): "VALIDATION_CHECK",
    ("VALIDATION_CHECK", "VALIDATION_CONFIRMED"): "DONE",
}


@pytest.mark.parametrize("node", [n.state_id for n in CHECKOUT.nodes])
@pytest.mark.parametrize("status", ["ACTIVE", "PAUSED"])
@pytest.mark.parametrize("event", EVENTS)
def test_full_transition_matrix(node, status, event):
    state = snapshot(node, status, 9)
    before = state.model_dump()
    target = EXPECTED.get((node, event)) if status == "ACTIVE" else None
    control = node != "DONE" and ((status == "ACTIVE" and event == "PAUSE")
                                   or (status == "PAUSED" and event == "RESUME"))
    if target or control:
        after = resolve(state, event, CHECKOUT)
        assert after.state_id == (target or node)
        assert after.status == ("PAUSED" if event == "PAUSE" else "ACTIVE")
        assert after.revision == 10
        assert (after.task_id, after.machine_id) == (state.task_id, state.machine_id)
    else:
        with pytest.raises(TaskStateError):
            resolve(state, event, CHECKOUT)
    assert state.model_dump() == before


def test_metadata_initial_terminal_and_versions():
    state = CHECKOUT.initial(str(uuid4()))
    assert state.revision == 0 and state.status == "ACTIVE"
    assert CHECKOUT.view(state)["expected_action"] == "provide_requirements"
    for event in EVENTS[:4]:
        state = resolve(state, event, CHECKOUT)
    assert CHECKOUT.view(state)["is_terminal"] and state.revision == 4
    assert CHECKOUT.allowed_events(state) == ()
    with pytest.raises(TaskStateError, match="machine_version_incompatible"):
        CHECKOUT.validate_state(TaskState(**(state.model_dump() | {"machine_id": "checkout-v2"})))
    with pytest.raises(TaskStateError, match="task_state_invalid"):
        CHECKOUT.validate_state(snapshot("UNKNOWN"))


@pytest.mark.parametrize("node", [n.state_id for n in CHECKOUT.nodes if not n.is_terminal])
def test_pause_round_trip(node):
    state = snapshot(node)
    paused = resolve(state, "PAUSE", CHECKOUT)
    assert CHECKOUT.allowed_events(paused) == ("RESUME",)
    resumed = resolve(paused, "RESUME", CHECKOUT)
    assert resumed.model_dump() == state.model_dump() | {"revision": 2}


def test_store_cas_two_connections_duplicate_init_and_reopen(tmp_path):
    path = tmp_path / "state.db"
    one = SQLiteTaskStateStore(path, CHECKOUT)
    two = SQLiteTaskStateStore(path, CHECKOUT)
    tid = str(uuid4())
    assert one.read(tid) is None
    initial = one.create_initial(tid)
    paused = resolve(initial, "PAUSE", CHECKOUT)
    assert one.compare_and_set(0, paused) == paused
    assert two.read(tid) == paused and two.create_initial(tid) == paused
    with pytest.raises(TaskStateError, match="stale"):
        two.compare_and_set(0, paused)
    with pytest.raises(TaskStateError, match="invalid_state_update"):
        one.compare_and_set(1, initial)
    one.close(); two.close()
    reopened = SQLiteTaskStateStore(path, CHECKOUT)
    assert reopened.read(tid) == paused
    reopened.close()


def test_failure_rollback_preserves_state(tmp_path):
    store = SQLiteTaskStateStore(tmp_path / "state.db", CHECKOUT)
    state = store.create_initial(str(uuid4()))
    store._connection.execute("CREATE TEMP TRIGGER fail_update AFTER UPDATE ON task_states "
                              "BEGIN SELECT RAISE(ABORT,'write failure'); END")
    with pytest.raises(TaskStateError, match="storage_error"):
        store.compare_and_set(0, resolve(state, "PAUSE", CHECKOUT))
    assert store.read(state.task_id) == state
    store.close()
    reopened = SQLiteTaskStateStore(tmp_path / "state.db", CHECKOUT)
    assert reopened.read(state.task_id) == state
    reopened.close()


@pytest.mark.parametrize("sql", [
    "UPDATE task_states SET state_id='UNKNOWN'",
    "UPDATE task_states SET state_id='DONE',status='PAUSED'",
    "UPDATE task_states SET machine_id='checkout-v2'",
    "UPDATE task_states SET task_id='wrong'",
    "PRAGMA user_version=99",
])
def test_corrupt_restore_never_repairs(tmp_path, sql):
    path = tmp_path / "state.db"
    store = SQLiteTaskStateStore(path, CHECKOUT)
    store.create_initial(str(uuid4()))
    store._connection.execute(sql)
    store.close()
    with pytest.raises(TaskStateError):
        SQLiteTaskStateStore(path, CHECKOUT)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM task_states").fetchone() == (1,)


def test_core_has_no_provider_memory_profile_or_harness_imports():
    import ast
    app = Path(__file__).parents[1] / "app"
    banned = ("openai", "llm_client", "memory", "profile", "checkout", "task_state_lab", "personalization")
    for name in ("task_state.py", "task_state_store.py", "sqlite_task_state_store.py"):
        tree = ast.parse((app / name).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            imports = [node.module or ""] if isinstance(node, ast.ImportFrom) else (
                [n.name for n in node.names] if isinstance(node, ast.Import) else [])
            assert not any(word in module for module in imports for word in banned)
