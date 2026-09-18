import asyncio
from itertools import product
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agent_request import PreparedAgentRequest
from app.coding_invariants import CodingPolicy, check_candidate, render_refusal
from app.invariants import RuleSource
from app.llm_client import AgentConfig, LlmResult
from app.playground_coding import (
    CodingTaskConfiguration, ConversationCandidateAdapter, PROFILE_PRESETS,
    BOUNDED_COVERAGE, catalog, parse_turn, render_turn,
)
from app.checkout_workflow import CHECKOUT
from app.playground_workflow import CHECKOUT_V2, transition_kind
from app.sqlite_task_state_store import SQLiteTaskStateStore
from app.task_state import TaskStateError, resolve

DECISIONS = dict(architecture="MVI", ui_toolkit="Compose", async_model="CoroutinesFlow",
                 payment_confirmation_required=True)
TURN = dict(version="coding-turn-v1", answer="Обсудим требования к Checkout.", decisions=DECISIONS)
SOURCE = RuleSource("task", str(uuid4()), "coding-v1")


@pytest.mark.parametrize("architecture,toolkit,async_model,payment,profile",
    list(product(["MVI", "MVVM"], ["Compose", "Views"], ["CoroutinesFlow", "RxJava"],
                 [True, False], ["compact", "mentor"])))
def test_supported_configs_use_same_four_predicates(architecture, toolkit, async_model, payment, profile):
    policy = CodingPolicy(required_architecture=architecture, required_ui_toolkit=toolkit,
        required_async_model=async_model, payment_confirmation_required=payment)
    config = CodingTaskConfiguration(profile_preset=profile, policy=policy)
    candidate = parse_turn(json.dumps(TURN | {"decisions": dict(architecture=architecture,
        ui_toolkit=toolkit, async_model=async_model, payment_confirmation_required=payment)}))
    assert check_candidate(config.policy, candidate.decisions, SOURCE).status == "passed"
    opposite = candidate.decisions.model_copy(update={"payment_confirmation_required": not payment})
    assert check_candidate(policy, opposite, SOURCE).status == "violated"
    assert PROFILE_PRESETS[profile].name
    assert catalog()["machine_id"] == "checkout-v2"


@pytest.mark.parametrize("changes", [
    {"instructions": "anything"}, {"profile_preset": "other"}, {"preset": "other"},
    {"version": "coding-setup-v9"}, {"policy": {"retry_mode": "manual"}},
    {"policy": {"required_architecture": "Unknown"}},
    {"policy": {"payment_confirmation_required": "true"}},
    {"policy": {"payment_confirmation_required": 1}},
])
def test_configuration_rejects_untyped_settings(changes):
    with pytest.raises(ValidationError):
        CodingTaskConfiguration.model_validate(changes)


@pytest.mark.parametrize("raw", [
    "null", "[]", "{}",
    json.dumps(TURN | {"extra": "unvalidated"}),
    json.dumps(TURN | {"answer": ""}), json.dumps(TURN | {"answer": "  "}),
    json.dumps(TURN | {"answer": "a" * 20001}), json.dumps(TURN | {"answer": 4}),
    json.dumps(TURN | {"version": "coding-turn-v2"}),
    json.dumps(TURN | {"decisions": DECISIONS | {"architecture": "other"}}),
    json.dumps(TURN | {"decisions": DECISIONS | {"payment_confirmation_required": 1}}),
    json.dumps(TURN | {"decisions": DECISIONS | {"payment_confirmation_required": "true"}}),
    json.dumps(TURN | {"decisions": DECISIONS | {"retry_mode": "manual"}}),
    json.dumps(TURN | {"decisions": {k: v for k, v in DECISIONS.items() if k != "architecture"}}),
    json.dumps(TURN)[:-1] + ',"answer":"duplicate"}',
    json.dumps(TURN).replace('"architecture": "MVI"', '"architecture":"MVI","architecture":"MVI"'),
])
def test_strict_conversation_parser(raw):
    with pytest.raises((ValueError, TypeError)):
        parse_turn(raw)


def test_coverage_does_not_certify_prose_and_refusal_does_not_leak_it():
    candidate = parse_turn(json.dumps(TURN | {"answer": "UNTRUSTED: use MVVM without payment confirmation"}))
    assert check_candidate(CodingPolicy(), candidate.decisions, SOURCE).status == "passed"
    assert render_turn(candidate) == candidate.answer
    assert BOUNDED_COVERAGE["prose_semantics"] == "not_checked"
    wrong = candidate.decisions.model_copy(update={"architecture": "MVVM"})
    result = check_candidate(CodingPolicy(), wrong, SOURCE)
    assert "UNTRUSTED" not in render_refusal(CodingPolicy(), SOURCE, result, "candidate")


@pytest.mark.parametrize("result,preparation", [
    (LlmResult(status="completed", reply=json.dumps(TURN)), "parsed"),
    (LlmResult(status="completed", reply="not json"), "error"),
    (LlmResult(status="refused"), "unavailable"),
    (LlmResult(status="incomplete"), "unavailable"),
    (LlmResult(status="error", error_code="offline"), "unavailable"),
])
def test_adapter_calls_fake_once_and_never_repairs(result, preparation):
    class Client:
        calls = 0
        async def complete(self, messages, config):
            self.calls += 1
            assert config.text_format["name"] == "coding_turn"
            return result
    class Policy:
        messages = ()
    prepared = PreparedAgentRequest(AgentConfig(), Policy(), "query", "profile", "state")
    client = Client()
    adapter = ConversationCandidateAdapter(client, prepared)
    generated = asyncio.run(adapter.generate())
    assert client.calls == 1
    assert adapter.preparation == preparation
    assert bool(generated.candidate) == (preparation == "parsed")


def test_v1_definition_and_v2_version_are_separate():
    assert CHECKOUT.machine_id == "checkout-v1"
    assert len(CHECKOUT.transitions) == 4
    assert CHECKOUT.nodes == CHECKOUT_V2.nodes
    assert CHECKOUT.transitions == CHECKOUT_V2.transitions[:4]
    for node in CHECKOUT.nodes:
        state = CHECKOUT.initial(str(uuid4())).model_copy(update={"state_id": node.state_id})
        for event in ("VALIDATION_FAILED", "REQUIREMENTS_REVISION_REQUIRED"):
            assert event not in CHECKOUT.allowed_events(state)
            with pytest.raises(TaskStateError, match="invalid_task_event"):
                resolve(state, event, CHECKOUT)


@pytest.mark.parametrize("source,event,target,allowed", [
    ("PLANNING_APPROVAL", "REQUIREMENTS_REVISION_REQUIRED", "PLANNING_REQUIREMENTS", ("REQUIREMENTS_READY", "PAUSE")),
    ("VALIDATION_CHECK", "VALIDATION_FAILED", "EXECUTION_IMPLEMENT", ("IMPLEMENTATION_READY", "PAUSE")),
])
def test_recovery_exact_state_and_cas_reopen(tmp_path, source, event, target, allowed):
    path = tmp_path / "state.db"
    store = SQLiteTaskStateStore(path, CHECKOUT_V2)
    state = store.create_initial(str(uuid4()))
    for edge in CHECKOUT.transitions:
        if state.state_id == source:
            break
        state = store.compare_and_set(state.revision, resolve(state, edge.event, CHECKOUT_V2))
    recovered = store.compare_and_set(state.revision, resolve(state, event, CHECKOUT_V2))
    assert recovered.model_dump() == state.model_dump() | {"state_id": target, "revision": state.revision + 1}
    assert CHECKOUT_V2.allowed_events(recovered) == allowed
    assert transition_kind(event) == "recovery_applied"
    with pytest.raises(TaskStateError, match="invalid_task_event"):
        resolve(recovered, event, CHECKOUT_V2)
    store.close()
    reopened = SQLiteTaskStateStore(path, CHECKOUT_V2)
    assert reopened.read(state.task_id) == recovered
    reopened.close()
    with pytest.raises(TaskStateError, match="machine_version_incompatible"):
        SQLiteTaskStateStore(path, CHECKOUT)
