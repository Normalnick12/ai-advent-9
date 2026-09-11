from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import Field
from app.context_strategies_models import StrictModel, Strategy, Target, Variant, LabError, VERSION, SCENARIO
from app.context_strategies_scenario import catalog

router = APIRouter(prefix="/api/v1/context-strategies")


class VersionRequest(StrictModel):
    config_version: Literal[VERSION]
    scenario_version: Literal[SCENARIO]


class RevisionRequest(VersionRequest):
    expected_revision: int = Field(ge=0)


class EvaluationRequest(RevisionRequest):
    attempt_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class MessageRequest(EvaluationRequest):
    step_id: int = Field(ge=1,le=8)
    target: Target
    message: str = Field(min_length=1,max_length=10000)


def service(request: Request): return request.app.state.context_strategies


async def lab_error_handler(request, exc: LabError):
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code,"message":"Операция Day 10 не завершена. Проверьте состояние эксперимента."}})


@router.get("/scenario")
async def scenario(): return catalog()


@router.post("/{strategy}/runs")
async def create(strategy: Strategy, body: VersionRequest, svc=Depends(service)):
    run = svc.store.create(strategy)
    return svc.read(run["run_id"],strategy)


@router.get("/{strategy}/runs/{run_id}")
async def read(strategy: Strategy, run_id: UUID, svc=Depends(service)):
    return svc.read(str(run_id),strategy)


@router.post("/{strategy}/runs/{run_id}/messages")
async def send(strategy: Strategy, run_id: UUID, body: MessageRequest, svc=Depends(service)):
    return await svc.send(str(run_id),strategy,body)


@router.post("/{strategy}/runs/{run_id}/checkpoint")
async def checkpoint(strategy: Strategy, run_id: UUID, body: RevisionRequest, svc=Depends(service)):
    return svc.checkpoint(str(run_id),strategy,body.expected_revision)


@router.get("/{strategy}/runs/{run_id}/facts")
async def facts(strategy: Strategy, run_id: UUID, svc=Depends(service)):
    run = svc.store.load(str(run_id),strategy)
    if strategy != "facts": raise LabError("invalid_strategy",422)
    return {"run_id":str(run_id),"revision":run["revision"],"facts":run["facts"]}


@router.get("/{strategy}/runs/{run_id}/messages/{message_id}")
async def raw(strategy: Strategy, run_id: UUID, message_id: UUID, svc=Depends(service)):
    run = svc.store.load(str(run_id),strategy)
    found = next((m for m in run["messages"] if m["message_id"] == str(message_id)),None)
    if found is None: raise LabError("message_not_found",404)
    return found


@router.post("/{strategy}/runs/{run_id}/evaluations/{variant}")
async def evaluate(strategy: Strategy, run_id: UUID, variant: Variant, body: EvaluationRequest, svc=Depends(service)):
    return await svc.evaluate(str(run_id),strategy,variant,body)


@router.delete("/{strategy}/runs/{run_id}")
async def reset(strategy: Strategy, run_id: UUID, svc=Depends(service)):
    svc.reset(str(run_id),strategy)
    return {"deleted":True}
