from fastapi import APIRouter, Request
from app.dependency_watch_models import WatchOperation, WatchRequest

router = APIRouter(prefix="/api/v1/dependency-watch", tags=["Day 18"])


@router.post("/run", response_model=WatchOperation)
async def run(body: WatchRequest, request: Request) -> WatchOperation:
    return await request.app.state.dependency_watch.run(body)
