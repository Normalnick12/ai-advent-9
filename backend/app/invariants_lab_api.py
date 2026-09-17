from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.agent_sessions import SessionBusy, SessionNotFound
from app.coding_policy_store import PolicyError
from app.conversation_store import ConversationStorageError
from app.invariants_lab_models import (EmptyRequest, TaskReference, EventRequest, ProposalRequest,
    InvariantsLabError, WORKING, PROFILE, POLICY, ACTIONS)
from app.memory_models import MemoryError
from app.profiles import ProfileError
from app.task_state import TaskStateError


class InvariantsRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            request.state.invariants_dispatched = False
            try:
                return await handler(request)
            except RequestValidationError:
                code, status = "validation_error", 422
            except (InvariantsLabError, PolicyError, MemoryError, ProfileError, TaskStateError) as exc:
                code, status = exc.code, exc.status
            except (SessionBusy, SessionNotFound):
                code, status = "session_unavailable", 409
            except ConversationStorageError:
                code, status = "storage_error", 500
            except Exception:
                code, status = "operation_failed", 500
            return JSONResponse(status_code=status, content={"error": code,
                "dispatch": "unknown" if request.state.invariants_dispatched else "not_dispatched",
                "observation": None})
        return safe


router = APIRouter(prefix="/api/v1/invariants", route_class=InvariantsRoute)


def service(request: Request):
    return request.app.state.invariants_lab


@router.get("/scenario")
async def scenario():
    return {"working": WORKING, "profile": PROFILE.model_dump(), "policy": POLICY.model_dump(),
            "actions": [{"action_id": key, "text": value[0]} for key, value in ACTIONS.items()]}


@router.get("/current")
async def current(svc=Depends(service)):
    return svc.current()


@router.post("/initialize")
async def initialize(body: EmptyRequest, svc=Depends(service)):
    return svc.initialize()


@router.post("/setup")
async def setup(body: TaskReference, svc=Depends(service)):
    return svc.setup(body)


@router.post("/events")
async def event(body: EventRequest, svc=Depends(service)):
    return svc.event(body)


@router.post("/lifecycle/{action}")
async def lifecycle(action: str, body: TaskReference, svc=Depends(service)):
    return svc.lifecycle(action, body)


@router.post("/proposals")
async def propose(body: ProposalRequest, request: Request, svc=Depends(service)):
    result = await svc.propose(body, on_dispatch=lambda: setattr(request.state, "invariants_dispatched", True))
    return JSONResponse(status_code=200 if result["observation"]["turn"]["status"] == "completed" else 500,
                        content=result)
