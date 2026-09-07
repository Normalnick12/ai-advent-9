import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.agent import SimpleAgent
from app.agent_models import AgentError, AgentMessageRequest, AgentTurnResponse, CreateSessionRequest, SessionResponse
from app.agent_sessions import AgentSessionManager, SessionBusy, SessionNotFound


logger = logging.getLogger("uvicorn.error")


class AgentRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            request.state.agent_request_id = uuid4().hex
            try:
                response = await handler(request)
            except SessionNotFound:
                response = self._error(request, 404, "session_not_found", "Диалог потерян после перезапуска сервера. Начните новый диалог.")
            except SessionBusy:
                response = self._error(request, 409, "session_busy", "Диалог занят. Дождитесь завершения отправки.")
            except RequestValidationError:
                response = self._error(request, 422, "validation_error", "Некорректный запрос. Проверьте сообщение.")
            except Exception:
                response = self._error(request, 500, "internal_error", "Не удалось завершить запрос.")
            response.headers["X-Request-ID"] = request.state.agent_request_id
            logger.info(
                "agent_request request_id=%s session_id=%s http_status=%s status=%s count=%s",
                request.state.agent_request_id,
                getattr(request.state, "agent_session_id", None), response.status_code,
                getattr(request.state, "agent_status", None),
                getattr(request.state, "agent_count", None),
            )
            return response
        return safe_handler

    @staticmethod
    def _error(request: Request, status: int, code: str, message: str) -> Response:
        return JSONResponse(status_code=status, content={
            "request_id": request.state.agent_request_id,
            "error": {"code": code, "message": message},
        })


router = APIRouter(prefix="/api/v1/agent/sessions", route_class=AgentRoute)


def get_session_manager(request: Request) -> AgentSessionManager:
    return request.app.state.agent_sessions


def get_agent(request: Request) -> SimpleAgent:
    return request.app.state.agent


@router.post("", status_code=201, response_model=SessionResponse)
async def create_session(
    body: CreateSessionRequest, request: Request, manager: AgentSessionManager = Depends(get_session_manager),
) -> SessionResponse:
    session = manager.create()
    request.state.agent_session_id = session.session_id
    request.state.agent_count = 0
    return SessionResponse(session_id=session.session_id, history_turn_count=0)


@router.post("/{session_id}/messages", response_model=AgentTurnResponse)
async def send_message(
    session_id: UUID, body: AgentMessageRequest, request: Request,
    manager: AgentSessionManager = Depends(get_session_manager),
    agent: SimpleAgent = Depends(get_agent),
) -> AgentTurnResponse:
    request.state.agent_session_id = str(session_id)
    session = manager.get(str(session_id))
    result = await agent.run_turn(session, body.message)
    request.state.agent_status = result.status
    request.state.agent_count = session.history_turn_count
    return AgentTurnResponse(
        session_id=session_id, request_id=request.state.agent_request_id,
        status=result.status, reply=result.reply if result.status == "completed" else None,
        history_turn_count=session.history_turn_count, incomplete_reason=result.incomplete_reason,
        error=AgentError(code=result.error_code, message=result.error_message) if result.error_code else None,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID, request: Request, manager: AgentSessionManager = Depends(get_session_manager),
) -> Response:
    request.state.agent_session_id = str(session_id)
    manager.delete(str(session_id))
    request.state.agent_count = 0
    return Response(status_code=204)
