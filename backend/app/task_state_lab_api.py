from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.agent_sessions import SessionBusy, SessionNotFound
from app.conversation_store import ConversationStorageError
from app.memory_models import EmptyRequest, MemoryError, MemoryMutation, SnapshotRequest
from app.profiles import ProfileError
from app.task_state import TaskStateError
from app.task_state_lab_models import (InitializeState, ApplyEvent, RequestSnapshot, SendRequest,
    CreateProfile, EditProfile, SelectProfile, WORKING, PROFILE, QUERY, EXECUTION_QUERY)


class TaskStateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            request.state.task_state_dispatched = False
            try:
                return await handler(request)
            except RequestValidationError:
                code, status = "validation_error", 422
            except (TaskStateError, MemoryError, ProfileError) as exc:
                code, status = exc.code, exc.status
            except (SessionBusy, SessionNotFound):
                code, status = "session_unavailable", 409
            except ConversationStorageError:
                code, status = "storage_error", 500
            except Exception:
                code, status = "operation_failed", 500
            return JSONResponse(status_code=status, content={"error": code,
                "dispatch": "unknown" if request.state.task_state_dispatched else "not_dispatched"})
        return safe


router = APIRouter(prefix="/api/v1/task-state", route_class=TaskStateRoute)


def service(request: Request):
    return request.app.state.task_state_lab


@router.get("/scenario")
async def scenario():
    return {"working": WORKING, "profile": PROFILE.model_dump(), "query": QUERY,
            "execution_query": EXECUTION_QUERY}


@router.get("/current")
async def current(svc=Depends(service)):
    return svc.current()


@router.post("/initialize")
async def initialize(body: EmptyRequest, svc=Depends(service)):
    return svc.initialize()


@router.post("/initialize-state")
async def initialize_state(body: InitializeState, svc=Depends(service)):
    return svc.initialize_state(body)


@router.post("/profiles")
async def create(body: CreateProfile, svc=Depends(service)):
    return svc.create_profile(body)


@router.put("/profiles/{pid}")
async def edit(pid: str, body: EditProfile, svc=Depends(service)):
    return svc.edit_profile(pid, body)


@router.post("/profiles/{pid}/select")
async def select(pid: str, body: SelectProfile, svc=Depends(service)):
    return svc.select_profile(pid, body)


@router.post("/memory")
async def memory(body: MemoryMutation, svc=Depends(service)):
    return svc.mutate_memory(body)


@router.post("/lifecycle/{action}")
async def lifecycle(action: str, body: SnapshotRequest, svc=Depends(service)):
    return svc.lifecycle(action, body)


@router.post("/events")
async def event(body: ApplyEvent, svc=Depends(service)):
    return svc.apply_event(body)


@router.post("/messages")
async def send(body: SendRequest, request: Request, svc=Depends(service)):
    return await svc.send(body, on_dispatch=lambda: setattr(request.state, "task_state_dispatched", True))


@router.post("/probe")
async def probe(body: RequestSnapshot, request: Request, svc=Depends(service)):
    return await svc.send(body, probe=True, on_dispatch=lambda: setattr(request.state, "task_state_dispatched", True))
