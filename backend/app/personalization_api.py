from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.agent_sessions import SessionBusy, SessionNotFound
from app.conversation_store import ConversationStorageError
from app.memory_models import EmptyRequest, MemoryError, MemoryMutation, SnapshotRequest
from app.personalization_models import (CreateProfile, EditProfile, SelectProfile, RequestSnapshot,
    SendRequest, FreezeRequest, ProbeRequest, FIXTURES, SEED, QUERY, LONG, WORKING)
from app.profiles import ProfileError


class PersonalizationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                return await handler(request)
            except (ProfileError, MemoryError) as exc:
                return JSONResponse(status_code=exc.status, content={"error": exc.code,
                    "dispatch": "not_dispatched" if exc.code in {"stale_snapshot", "stale_profile_binding",
                    "profile_unselected", "personalization_busy", "not_initialized", "comparison_not_found",
                    "stale_comparison", "active_profile_mismatch", "seed_requires_empty_memory"} else "unknown"})
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"error": "validation_error", "dispatch": "not_dispatched"})
            except (SessionBusy, SessionNotFound):
                return JSONResponse(status_code=409, content={"error": "session_unavailable"})
            except ConversationStorageError:
                return JSONResponse(status_code=500, content={"error": "storage_error"})
            except Exception:
                return JSONResponse(status_code=500, content={"error": "operation_failed"})
        return safe


router = APIRouter(prefix="/api/v1/profile-personalization", route_class=PersonalizationRoute)


def service(request: Request):
    return request.app.state.personalization


@router.get("/scenario")
async def scenario():
    return {"profiles": {slot: p.model_dump() for slot, p in FIXTURES.items()},
            "seed": SEED, "query": QUERY, "working": WORKING, "long_term": LONG}


@router.get("/current")
async def current(svc=Depends(service)):
    return svc.current()


@router.get("/profiles")
async def profiles(svc=Depends(service)):
    return svc.current()["profiles"]


@router.get("/profiles/{pid}")
async def profile(pid: str, svc=Depends(service)):
    return svc.profiles.read(svc.owner(), pid)


@router.post("/initialize")
async def initialize(body: EmptyRequest, svc=Depends(service)):
    return svc.initialize()


@router.post("/profiles")
async def create(body: CreateProfile, svc=Depends(service)):
    return svc.create(body)


@router.put("/profiles/{pid}")
async def edit(pid: str, body: EditProfile, svc=Depends(service)):
    return svc.edit(pid, body)


@router.post("/profiles/{pid}/select")
async def select(pid: str, body: SelectProfile, svc=Depends(service)):
    return svc.select(pid, body)


@router.post("/memory")
async def memory(body: MemoryMutation, svc=Depends(service)):
    return svc.mutate_memory(body)


@router.post("/lifecycle/{action}")
async def lifecycle(action: str, body: SnapshotRequest, svc=Depends(service)):
    return svc.transition(action, body)


@router.post("/seed")
async def seed(body: RequestSnapshot, svc=Depends(service)):
    return await svc.send(body, seed=True)


@router.post("/messages")
async def send(body: SendRequest, svc=Depends(service)):
    return await svc.send(body)


@router.post("/freeze")
async def freeze(body: FreezeRequest, svc=Depends(service)):
    return svc.freeze(body)


@router.post("/probe")
async def probe(body: ProbeRequest, svc=Depends(service)):
    return await svc.probe(body)
