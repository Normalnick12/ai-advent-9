from fastapi import APIRouter, Request
from .mcp_orchestration_models import OrchestrationRequest, OrchestrationOperation

router = APIRouter(prefix="/api/v1/mcp-orchestration", tags=["Day 20"])


@router.post("/run", response_model=OrchestrationOperation)
async def run(body: OrchestrationRequest, request: Request) -> OrchestrationOperation:
    return await request.app.state.mcp_orchestration.run(body)
