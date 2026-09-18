"""Playground HTTP boundary with typed expected outcomes and no implicit retries."""
from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.playground_coding import catalog
from app.playground_models import (CreateRequest, CompleteSetupRequest, SourceReference,
    ProfileRequest, EventRequest, SendRequest)


class PlaygroundRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            request.state.playground_dispatched = False
            try:
                return await handler(request)
            except RequestValidationError:
                code, status = "validation_error", 422
            except Exception as exc:
                code, status = getattr(exc, "code", "operation_failed"), getattr(exc, "status", 500)
            return JSONResponse(status_code=status, content={"error": code,
                "dispatch": "unknown" if request.state.playground_dispatched else "not_dispatched",
                "receipt": None, "current": None})
        return safe


router = APIRouter(prefix="/api/v1/agent-playground", route_class=PlaygroundRoute)


def service(request: Request):
    return request.app.state.agent_playground


@router.get("/catalog")
async def get_catalog():
    return catalog()


@router.get("/current")
async def current(svc=Depends(service)):
    return svc.current()


@router.post("/create-task")
async def create(body: CreateRequest, svc=Depends(service)):
    return svc.create_task(body)


@router.post("/complete-setup")
async def complete(body: CompleteSetupRequest, svc=Depends(service)):
    return svc.complete_setup(body)


@router.post("/select-profile")
async def select_profile(body: ProfileRequest, svc=Depends(service)):
    return svc.select_profile(body)


@router.post("/new-conversation")
async def new_conversation(body: SourceReference, svc=Depends(service)):
    return svc.new_conversation(body)


@router.post("/events")
async def event(body: EventRequest, svc=Depends(service)):
    result = svc.event(body)
    outcome = result["receipt"]["outcome"]
    return JSONResponse(status_code=409 if outcome == "rejected" else 500 if outcome == "technical_error" else 200,
                        content=result)


@router.post("/send")
async def send(body: SendRequest, request: Request, svc=Depends(service)):
    result = await svc.send(body, on_dispatch=lambda: setattr(request.state, "playground_dispatched", True))
    return JSONResponse(status_code=500 if result["receipt"]["outcome"] == "technical_error" else 200, content=result)
