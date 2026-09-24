from fastapi import APIRouter, Request
from .mcp_composition_models import CompositionRequest, CompositionOperation

router = APIRouter(prefix="/api/v1/mcp-composition", tags=["Day 19"])


@router.post("/run", response_model=CompositionOperation)
async def run(body: CompositionRequest, request: Request) -> CompositionOperation:
    return await request.app.state.mcp_composition.run(body)
