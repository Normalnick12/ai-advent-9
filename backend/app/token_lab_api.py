from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import Field, StrictBool, StrictStr, field_validator

from app.agent_api import AgentRoute
from app.agent_models import AgentError, AgentMessageRequest, CreateSessionRequest, SessionResponse
from app.llm_client import TokenUsage
from app.token_diagnostics import AgentTurnResult, TokenDiagnostics
from app.token_overflow import PreparationInfo
from app.token_pricing import EstimatedCost, estimate_turn_cost


class ExecuteRequest(CreateSessionRequest):
    preparation_id: StrictStr = Field(min_length=1, max_length=128)
    confirm: StrictBool

    @field_validator("confirm")
    @classmethod
    def confirmed(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation required")
        return value


class TokenLabResponse(SessionResponse):
    request_id: str
    attempt_id: str
    status: str
    reply: str | None
    error: AgentError | None
    error_origin: str | None
    generation_attempted: bool
    committed: bool
    diagnostics: TokenDiagnostics | None
    usage: TokenUsage | None
    cost: EstimatedCost
    requested_model: str | None
    resolved_model: str | None
    requested_service_tier: str | None
    actual_service_tier: str | None
    provider_status: str | None
    preparation: PreparationInfo | None = None


router = APIRouter(prefix="/api/v1/token-lab/sessions", route_class=AgentRoute)


def session_for(request, session_id):
    request.state.agent_session_id = str(session_id)
    return request.app.state.token_sessions.get(str(session_id))


def project(request, session, attempt: AgentTurnResult, preparation=None):
    result = attempt.outcome
    try:
        cost = estimate_turn_cost(result)
    except Exception:
        # Billing diagnostics must never turn a committed pair into an HTTP failure.
        cost = EstimatedCost(reason="pricing_unavailable")
    request.state.agent_status = result.status
    request.state.agent_count = session.history_turn_count
    return TokenLabResponse(
        session_id=session.session_id, history_turn_count=session.history_turn_count,
        request_id=request.state.agent_request_id, attempt_id=attempt.attempt_id,
        status="prepared" if preparation is not None else result.status,
        reply=result.reply if attempt.committed else None,
        error=AgentError(code=result.error_code, message=result.error_message or "Ошибка запроса")
            if result.error_code else None,
        error_origin=attempt.error_origin, generation_attempted=attempt.generation_attempted,
        committed=attempt.committed, diagnostics=attempt.diagnostics, usage=result.usage,
        cost=cost, requested_model=result.requested_model, resolved_model=result.resolved_model,
        requested_service_tier=result.requested_service_tier, actual_service_tier=result.actual_service_tier,
        provider_status=result.provider_status, preparation=preparation)


@router.post("", status_code=201, response_model=SessionResponse)
async def create(body: CreateSessionRequest, request: Request):
    session = request.app.state.token_sessions.create()
    request.state.agent_session_id = session.session_id
    request.state.agent_count = 0
    return SessionResponse(session_id=session.session_id, history_turn_count=0)


@router.get("/{session_id}", response_model=SessionResponse)
async def read(session_id: UUID, request: Request):
    session = session_for(request, session_id)
    session.ensure_available()
    request.state.agent_count = session.history_turn_count
    return SessionResponse(session_id=session.session_id, history_turn_count=session.history_turn_count)


@router.delete("/{session_id}", status_code=204)
async def delete(session_id: UUID, request: Request):
    request.state.agent_session_id = str(session_id)
    request.app.state.token_sessions.delete(str(session_id))
    request.app.state.token_overflow.invalidate(str(session_id))
    return Response(status_code=204)


@router.post("/{session_id}/messages", response_model=TokenLabResponse)
async def send(session_id: UUID, body: AgentMessageRequest, request: Request):
    session = session_for(request, session_id)
    attempt = await request.app.state.token_agent.run_turn(session, body.message)
    if attempt.committed:
        request.app.state.token_overflow.invalidate(session.session_id)
    return project(request, session, attempt)


@router.post("/{session_id}/overflow/prepare", response_model=TokenLabResponse)
async def prepare(session_id: UUID, body: CreateSessionRequest, request: Request):
    session = session_for(request, session_id)
    attempt, info = await request.app.state.token_overflow.prepare(session)
    return project(request, session, attempt, info)


@router.post("/{session_id}/overflow/execute", response_model=TokenLabResponse)
async def execute(session_id: UUID, body: ExecuteRequest, request: Request):
    session = session_for(request, session_id)
    attempt = await request.app.state.token_overflow.execute(session, body.preparation_id)
    return project(request, session, attempt)
