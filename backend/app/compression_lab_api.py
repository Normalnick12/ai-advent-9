from dataclasses import asdict
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from app.conversation_summary_store import SummaryStateError
from pydantic import Field, StrictStr, field_validator

from app.agent_api import AgentRoute
from app.agent_models import AgentMessageRequest, CreateSessionRequest
from app.compression_models import CompressionOperation, VERSION


class CompareRequest(CreateSessionRequest):
    question: StrictStr = Field(min_length=1, max_length=20000)
    scenario_id: Literal["three-facts-v1"] | None = None

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank")
        return value


router = APIRouter(prefix="/api/v1/compression-lab/sessions", route_class=AgentRoute)


def session_for(request, session_id):
    request.state.agent_session_id = str(session_id)
    return request.app.state.compression_sessions.get(str(session_id))


def metadata(session, summary=None):
    return dict(session_id=session.session_id, history_turn_count=session.history_turn_count,
        config_version=VERSION, summary_metadata=None if summary is None else dict(
            covered_through_position=summary.covered_through_position,
            summarized_message_count=summary.covered_through_position+1,
            summary_chars=len(summary.summary_text), config_version=summary.config_version))


@router.post("", status_code=201)
async def create(body: CreateSessionRequest, request: Request):
    session = request.app.state.compression_sessions.create()
    request.state.agent_session_id = session.session_id
    return metadata(session)


@router.get("/{session_id}")
async def read(session_id: UUID, request: Request):
    session = session_for(request, session_id)
    session.ensure_available()
    try:
        return metadata(session, request.app.state.compression_summaries.load(session.session_id, session.history))
    except SummaryStateError as exc:
        return JSONResponse(status_code=500, content={"request_id": request.state.agent_request_id,
            "error": {"code": exc.code, "message": "Сохранённая сводка повреждена или несовместима. Начните новый диалог."}})


@router.get("/{session_id}/summary")
async def read_summary(session_id: UUID, request: Request):
    session = session_for(request, session_id)
    session.ensure_available()
    try:
        summary = request.app.state.compression_summaries.load(session.session_id, session.history)
        return dict(session_id=session.session_id, summary=asdict(summary) if summary else None)
    except SummaryStateError as exc:
        return JSONResponse(status_code=500, content={"request_id": request.state.agent_request_id,
            "error": {"code": exc.code, "message": "Сохранённая сводка повреждена или несовместима. Начните новый диалог."}})


@router.delete("/{session_id}", status_code=204)
async def delete(session_id: UUID, request: Request):
    request.state.agent_session_id = str(session_id)
    request.app.state.compression_sessions.delete(str(session_id))
    return Response(status_code=204)


def project(request, session, op):
    request.state.agent_status = op.status
    request.state.agent_count = session.history_turn_count
    return dict(session_id=session.session_id, history_turn_count=session.history_turn_count,
                request_id=request.state.agent_request_id, **asdict(op))


@router.post("/{session_id}/messages")
async def send(session_id: UUID, body: AgentMessageRequest, request: Request):
    session = session_for(request, session_id)
    op = CompressionOperation()
    await request.app.state.compression_agent.run_turn(session, body.message, operation=op)
    return project(request, session, op)


@router.post("/{session_id}/compare")
async def compare(session_id: UUID, body: CompareRequest, request: Request):
    session = session_for(request, session_id)
    op = CompressionOperation(kind="compare")
    await request.app.state.compression_compare.run(session, body.question, body.scenario_id, op)
    return project(request, session, op)
