import json
from uuid import uuid4

import pytest

from app.invariants_lab_models import ProposalRequest, InvariantsLabError
from app.llm_client import LlmResult
from app.memory_models import MemoryMutation
from test_invariants_lab import lab, setup, request, task_ref, event


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["refused", "incomplete", "error", "exception"])
async def test_provider_noncompletion_is_technical_with_one_call(lab, status):
    svc, client = lab
    setup(svc)
    before = svc.current()["memory"]
    if status == "exception":
        async def failing(messages, config):
            client.calls.append(True)
            raise RuntimeError("private provider details")
        client.complete = failing
    else:
        client.result = LlmResult(status)
    op = await svc.propose(request(svc))
    o = op["observation"]
    assert o["generation_calls"] == len(client.calls) == 1
    assert o["turn"]["status"] == "error" and o["turn"]["decision"] is None
    assert o["turn"]["reply"] is None and o["turn"]["validation"] is None
    assert op["current"]["memory"] == before
    assert "private provider" not in json.dumps(op)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    {"snapshot_id": "f" * 64}, {"task_id": str(uuid4())}, {"session_id": str(uuid4())},
    {"state_revision": 99}, {"profile_id": str(uuid4())}, {"profile_revision": 99},
    {"binding_revision": 99}, {"policy_id": "other-policy"}, {"policy_version": "coding-v9"},
    {"policy_snapshot_id": "f" * 64},
])
async def test_every_stale_source_ref_blocks_before_generation(lab, change):
    svc, client = lab
    setup(svc)
    before = svc.current()["memory"]
    req = ProposalRequest(**(request(svc).model_dump() | change))
    with pytest.raises(Exception):
        await svc.propose(req)
    assert not client.calls and svc.current()["memory"] == before and not svc.busy


def test_setup_does_not_overwrite_and_cold_read_does_not_initialize(lab):
    svc, client = lab
    assert svc.current()["memory"] is None
    assert svc.memory.read() is None and not client.calls
    svc.initialize()
    svc.memory.mutate(MemoryMutation(snapshot_id=svc.current()["memory"]["snapshot_id"],
        layer="WORKING", key="current_architecture", value="MVVM", operation="set"))
    before = svc.current()["memory"]
    with pytest.raises(InvariantsLabError, match="working_setup_conflict"):
        svc.setup(task_ref(svc))
    assert svc.current()["memory"] == before and svc.current()["policy"] is None and not client.calls


@pytest.mark.asyncio
async def test_inactive_task_reference_and_nonexecution_never_dispatch(lab):
    svc, client = lab
    setup(svc)
    old = request(svc)
    svc.lifecycle("new-task", task_ref(svc))
    with pytest.raises(Exception):
        await svc.propose(old)
    svc.setup(task_ref(svc))
    with pytest.raises(InvariantsLabError, match="proposal_not_applicable"):
        await svc.propose(request(svc))
    assert not client.calls and svc.current()["memory"]["short_term"] == []
