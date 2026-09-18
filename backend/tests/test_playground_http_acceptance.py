import json
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.agent_lifecycle import LifecycleService
from app.llm_client import LlmResult
from app.playground_api import router
from app.sqlite_task_state_store import SQLiteTaskStateStore
from app.task_state import TaskStateDefinition, StateDefinition, StateTransition
from test_playground_coding import TURN
from test_playground_service import playground, create, request, sources


@pytest.mark.asyncio
@pytest.mark.parametrize("alternative", [False, True])
async def test_production_http_full_flow_and_all_source_evidence(playground, alternative):
    svc, client = playground
    app = FastAPI()
    app.include_router(router)
    app.state.agent_playground = svc
    config = {"profile_preset": "mentor", "policy": {"required_architecture": "MVVM",
        "required_ui_toolkit": "Views", "required_async_model": "RxJava",
        "payment_confirmation_required": False}} if alternative else {}
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test/api/v1/agent-playground") as http:
        created = await http.post("/create-task", json={"configuration": config})
        assert created.status_code == 200
        current = created.json()
        values = current["policy"]["values"]
        client.result = LlmResult("completed", json.dumps(TURN | {"decisions": {
            "architecture": values["required_architecture"], "ui_toolkit": values["required_ui_toolkit"],
            "async_model": values["required_async_model"], "payment_confirmation_required": values["payment_confirmation_required"]}}))
        for event in ("REQUIREMENTS_READY", "IMPLEMENTATION_READY", "REQUIREMENTS_REVISION_REQUIRED",
                      "REQUIREMENTS_READY", "PLAN_APPROVED", "PAUSE", "RESUME", "VALIDATION_CONFIRMED",
                      "IMPLEMENTATION_READY", "VALIDATION_FAILED", "IMPLEMENTATION_READY", "VALIDATION_CONFIRMED"):
            before = current
            send = await http.post("/send", json=current["reference"] | {"query": "VALIDATION_FAILED: обсудим исправление"})
            assert send.status_code == 200
            op = send.json()
            assert op["current"]["task_state"] == before["task_state"]
            assert op["receipt"]["actual_request"] == client.calls[-1]
            assert op["receipt"]["sources"]["profile"] == before["profile"]
            assert op["receipt"]["sources"]["policy"] == before["policy"]
            assert op["receipt"]["sources"]["memory"] == before["memory"]
            assert op["receipt"]["coverage"]["prose_semantics"] == "not_checked"
            assert op["receipt"]["turn"]["commit_status"] == "committed"
            current = op["current"]
            ref = current["reference"]
            body = {k: ref[k] for k in ("task_id", "session_id", "snapshot_id", "state_revision")}
            response = await http.post("/events", json=body | {"event": event})
            result = response.json()
            assert response.status_code == (200 if event in current["task_state"]["allowed_events"] else 409)
            assert sources(result["current"]) == sources(current)
            assert result["receipt"]["generation_calls"] == 0
            current = result["current"]
        assert not current["can_send"] and current["task_state"]["state_id"] == "DONE"
        calls = len(client.calls)
        blocked = await http.post("/send", json=current["reference"] | {"query": "one more"})
        assert blocked.status_code == 409 and len(client.calls) == calls
        assert (await http.get("/current")).json()["task_state"] == current["task_state"]


def test_lifecycle_accepts_another_definition_without_another_engine(tmp_path):
    definition = TaskStateDefinition(machine_id="example-v1", initial_node="START", nodes=(
        StateDefinition(state_id="START", phase="plan", step="start", expected_action="confirm"),
        StateDefinition(state_id="FINISHED", phase="done", step="finish", expected_action="none", is_terminal=True)),
        transitions=(StateTransition(source="START", event="CONFIRMED", target="FINISHED"),))
    store = SQLiteTaskStateStore(tmp_path / "generic.db", definition)
    try:
        initial = store.create_initial(str(uuid4()))
        boundary = LifecycleService(definition, store, lambda event: "forward_applied",
            lambda outcome, event, state: state["expected_action"])
        result = boundary.apply(initial.task_id, initial.revision, "CONFIRMED")
        assert result["after"]["state_id"] == "FINISHED" and result["generation_calls"] == 0
    finally:
        store.close()


@pytest.mark.asyncio
async def test_provider_substitution_keeps_acceptance_and_commit(playground):
    svc, first = playground
    create(svc)
    one = (await svc.send(request(svc)))["receipt"]

    class OtherProvider:
        calls = 0
        async def complete(self, messages, config):
            self.calls += 1
            return LlmResult(status="completed", reply=json.dumps(TURN))
    other = OtherProvider()
    svc.send_coordinator.client = other
    two = (await svc.send(request(svc)))["receipt"]
    assert one["turn"]["decision"] == two["turn"]["decision"] == "accepted"
    assert one["turn"]["commit_status"] == two["turn"]["commit_status"] == "committed"
    assert one["coverage"] == two["coverage"] and other.calls == 1
    assert svc.current()["task_state"]["revision"] == 0
