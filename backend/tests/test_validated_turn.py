from dataclasses import dataclass
import json

import pytest

from app.agent_sessions import AgentSessionManager
from app.context_policy import FullHistoryContextPolicy
from app.invariants import RuleRef, RuleSource, ValidationResult, InvariantViolation
from app.sqlite_conversation_store import SQLiteConversationStore
from app.validated_turn import CandidateGeneration, run_validated_turn


@dataclass(frozen=True)
class Quantity:
    count: int


@pytest.mark.asyncio
async def test_two_adapters_share_non_coding_gate_and_optional_intent(tmp_path):
    rule = RuleRef("positive", RuleSource("agent", "example", "v1"), "Count must be positive")
    def validate(candidate):
        violations = () if candidate.count > 0 else (InvariantViolation(rule, "candidate", "negative", str(candidate.count), "positive"),)
        return ValidationResult("violated" if violations else "passed", (rule,), violations)
    async def json_adapter():
        return CandidateGeneration(Quantity(json.loads('{"count":-1}')["count"]))
    async def local_adapter():
        return CandidateGeneration(Quantity(-1))
    store = SQLiteConversationStore(tmp_path / "conversations.db")
    sessions = AgentSessionManager(store)
    outcomes = []
    for adapter in (json_adapter, local_adapter):
        session = sessions.create()
        result = await run_validated_turn(session, "quantity", context_policy=FullHistoryContextPolicy(),
            required_rules=(rule,), generate=adapter, validate=validate, render=lambda c: str(c.count),
            refuse=lambda result, origin: "Count must be positive")
        assert result.commit_status == "committed" and result.precheck is None
        assert session.history[1].content == "Count must be positive"
        outcomes.append(result)
    assert outcomes[0] == outcomes[1]
    store.close()


@pytest.mark.asyncio
async def test_incomplete_check_coverage_never_commits(tmp_path):
    store = SQLiteConversationStore(tmp_path / "conversations.db")
    session = AgentSessionManager(store).create()
    rule = RuleRef("required", RuleSource("agent", "example", "v1"), "Required")
    async def generate():
        return CandidateGeneration(Quantity(1))
    result = await run_validated_turn(session, "x", context_policy=FullHistoryContextPolicy(),
        required_rules=(rule,), generate=generate, validate=lambda c: ValidationResult("passed"),
        render=lambda c: "must not render", refuse=lambda *args: "must not refuse")
    assert result.status == "error" and result.error_stage == "candidate_validation" and session.history == ()
    store.close()
