"""A bounded validation-before-commit turn; policy and candidate generation are injected."""
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Generic, TypeVar

from app.agent_sessions import AgentSession
from app.invariants import RuleRef, ValidationResult
from app.llm_client import ConversationMessage

C = TypeVar("C")


@dataclass(frozen=True)
class CandidateGeneration(Generic[C]):
    candidate: C | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class ValidatedTurnResult:
    status: str = "error"
    decision: str | None = None
    precheck: ValidationResult | None = None
    validation: ValidationResult | None = None
    commit_status: str = "not_attempted"
    reply: str | None = None
    error_code: str | None = None
    error_stage: str | None = None


async def run_validated_turn(
    session: AgentSession, query: str, *, context_policy,
    required_rules: tuple[RuleRef, ...],
    generate: Callable[[], Awaitable[CandidateGeneration[C]]],
    validate: Callable[[C], ValidationResult], render: Callable[[C], str],
    refuse: Callable[[ValidationResult, str], str],
    precheck: Callable[[], ValidationResult] | None = None,
) -> ValidatedTurnResult:
    session.begin_turn()
    result = ValidatedTurnResult()
    stage = "context"
    try:
        await context_policy.prepare(session.session_id, session.history)
        stage = "request_validation"
        request_check = precheck() if precheck else None
        result = replace(result, precheck=request_check)
        if request_check is not None:
            request_check.require_complete(required_rules)
        if request_check is not None and request_check.status == "violated":
            result = replace(result, decision="request_refused")
            stage = "refusal_rendering"
            reply = refuse(request_check, "request")
        else:
            stage = "candidate_generation"
            generated = await generate()
            if generated.error_code or generated.candidate is None:
                return replace(result, error_code=generated.error_code or "candidate_unavailable", error_stage=stage)
            stage = "candidate_validation"
            checked = validate(generated.candidate)
            result = replace(result, validation=checked)
            checked.require_complete(required_rules)
            if checked.status == "violated":
                result = replace(result, decision="candidate_refused")
                stage = "refusal_rendering"
                reply = refuse(checked, "candidate")
            else:
                result = replace(result, decision="accepted")
                stage = "answer_rendering"
                reply = render(generated.candidate)
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("empty final reply")
        stage = "commit"
        session.commit(ConversationMessage("user", query), ConversationMessage("assistant", reply))
        return replace(result, status="completed", commit_status="committed", reply=reply)
    except Exception:
        # No exception text, raw output, or guessed domain violation escapes this boundary.
        return replace(result, error_code="pair_storage_error" if stage == "commit" else "enforcement_error",
                       error_stage=stage, commit_status="unknown" if stage == "commit" else "not_attempted")
    finally:
        session.end_turn()
