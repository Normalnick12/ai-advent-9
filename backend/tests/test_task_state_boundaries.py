from copy import deepcopy
from uuid import uuid4

import pytest

from app.agent_request import prepare_agent_request
from app.checkout_workflow import CHECKOUT
from app.llm_client import ConversationMessage
from app.memory_models import MemoryMutation
from app.task_state import TaskState, TaskStateError
from app.task_state_lab_models import CONFIG, SendRequest, ApplyEvent
from app.sqlite_task_state_store import SQLiteTaskStateStore
from test_task_state_lab import lab, setup, refs, event, lifecycle


def test_preparation_immutable_sources_order_and_working_override(lab):
    svc, client = lab
    setup(svc)
    svc.mutate_memory(MemoryMutation(snapshot_id=svc.current()["memory"]["snapshot_id"],
        layer="LONG_TERM", key="preferred_architecture", value="MVVM", operation="set"))
    c = svc.current()
    svc.sessions.get(c["memory"]["session_id"]).commit(ConversationMessage("user", "active user"),
                                                  ConversationMessage("assistant", "active reply"))
    c = svc.current()
    memory, profile, _, state = svc.resolve_sources(SendRequest(**refs(svc), message="x"))
    original = deepcopy(memory)
    prepared = prepare_agent_request(CONFIG, memory, profile, state, CHECKOUT, "query")
    assert memory == original and CONFIG.instructions not in (prepared.config.instructions, "")
    assert prepared.config.instructions == CONFIG.instructions + "\n\nPROFILE\n" + prepared.profile_section + "\n\n" + prepared.state_section
    assert [m.content for m in prepared.messages][-3:] == ["active user", "active reply", "query"]
    assert "MVVM" not in str(prepared.messages) and "MVI" in str(prepared.messages)
    assert "TASK_STATE" not in str(prepared.messages)
    memory["short_term"].clear(); memory["working"]["task"] = "mutated"
    assert "mutated" not in str(prepared.messages) and prepared.policy.history
    with pytest.raises(TaskStateError, match="source_mismatch"):
        prepare_agent_request(CONFIG, original, profile, TaskState(**(state.model_dump() | {"task_id": str(uuid4())})), CHECKOUT, "x")
    assert not client.calls


@pytest.mark.asyncio
async def test_receipts_stay_historical_and_failed_cas_does_not_publish(lab):
    svc, client = lab
    setup(svc)
    op = await svc.send(SendRequest(**refs(svc), message="old query"))
    saved = deepcopy(op)
    event(svc, "PAUSE")
    transition = deepcopy(svc.current()["last_transition"])
    svc.states._connection.execute("CREATE TEMP TRIGGER fail_update AFTER UPDATE ON task_states "
        "BEGIN SELECT RAISE(ABORT,'fault'); END")
    with pytest.raises(TaskStateError, match="storage_error"):
        event(svc, "RESUME")
    assert svc.current()["last_transition"] == transition
    assert svc.current()["task_state"]["status"] == "PAUSED"
    lifecycle(svc, "new-conversation")
    assert op == saved
    assert len(client.calls) == 1


@pytest.mark.parametrize("events", [(), ("PAUSE",),
    ("REQUIREMENTS_READY", "PLAN_APPROVED", "IMPLEMENTATION_READY", "VALIDATION_CONFIRMED")])
def test_exact_active_paused_done_reopen_with_zero_calls(lab, tmp_path, events):
    svc, client = lab
    setup(svc)
    for e in events:
        event(svc, e)
    state = svc.current()["task_state"]
    reopened = SQLiteTaskStateStore(tmp_path / "states.db", CHECKOUT)
    try:
        assert CHECKOUT.view(reopened.read(state["task_id"])) == state
    finally:
        reopened.close()
    assert not client.calls


@pytest.mark.asyncio
async def test_missing_profile_and_missing_state_gate_dispatch(lab):
    svc, client = lab
    c = svc.initialize()
    request = ApplyEvent(snapshot_id=c["memory"]["snapshot_id"], task_id=c["memory"]["task_id"], state_revision=0, event="PAUSE")
    with pytest.raises(TaskStateError, match="profile_unselected"):
        svc.apply_event(request)
    setup(svc)
    before = refs(svc)
    svc.states._connection.execute("DELETE FROM task_states")
    with pytest.raises(TaskStateError, match="task_state_missing"):
        await svc.send(SendRequest(**before, message="x"))
    assert not svc.current()["ready"] and not client.calls
