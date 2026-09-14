from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from app.conversation_store import ConversationStorageError
from app.agent_sessions import SessionBusy, SessionNotFound
from app.memory_models import EmptyRequest, SnapshotRequest, MemoryMutation, MemoryMessage, MemoryError
from app.memory_context import SEED, QUERY, LONG_FIXTURE, WORKING_FIXTURE


class MemoryRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                return await handler(request)
            except MemoryError as exc:
                return JSONResponse(status_code=exc.status, content={"error": exc.code})
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"error": "validation_error"})
            except (SessionBusy, SessionNotFound):
                return JSONResponse(status_code=409, content={"error": "session_unavailable"})
            except ConversationStorageError:
                return JSONResponse(status_code=500, content={"error": "storage_error"})
            except Exception:
                return JSONResponse(status_code=500, content={"error": "operation_failed"})
        return safe


router = APIRouter(prefix="/api/v1/memory-layers", route_class=MemoryRoute)


def service(request: Request):
    return request.app.state.memory_layers


@router.get("/scenario")
async def scenario():
    return {"seed": SEED, "query": QUERY, "working": WORKING_FIXTURE, "long_term": LONG_FIXTURE}


@router.get("/current")
async def current(svc=Depends(service)):
    return svc.read()


@router.post("/initialize")
async def initialize(body: EmptyRequest, svc=Depends(service)):
    return svc.initialize()


@router.post("/memory")
async def mutate(body: MemoryMutation, svc=Depends(service)):
    return svc.mutate(body)


@router.post("/lifecycle/{action}")
async def transition(action: str, body: SnapshotRequest, svc=Depends(service)):
    return svc.transition(action, body)


@router.post("/messages")
async def send(body: MemoryMessage, svc=Depends(service)):
    return await svc.send(body)


@router.post("/verify/{stage}")
async def verify(stage: str, body: SnapshotRequest, svc=Depends(service)):
    return await svc.verify(stage, body)
