import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Response

from app.models import GenerateRequest, GenerateResponse
from app.openai_service import (
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT_SECONDS,
    OpenAIResponseService,
)

app = FastAPI(title="Response Control Lab API", version="1.0.0")

_service = OpenAIResponseService()
logger = logging.getLogger("uvicorn.error")


def get_openai_service() -> OpenAIResponseService:
    return _service


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "openai_timeout_seconds": str(OPENAI_TIMEOUT_SECONDS),
        "openai_max_retries": str(OPENAI_MAX_RETRIES),
    }


@app.post("/api/v1/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    response: Response,
    service: OpenAIResponseService = Depends(get_openai_service),
) -> GenerateResponse:
    request_id = uuid4().hex[:12]
    response.headers["X-Request-ID"] = request_id
    started_at = time.monotonic()
    logger.info(
        "generation_started request_id=%s structured=%s max_output_tokens=%s "
        "finish_instruction=%s",
        request_id,
        request.controls.structured_output,
        request.controls.max_output_tokens,
        request.controls.finish_instruction,
    )
    result = await service.generate(request, request_id=request_id)
    if result.request_id is None:
        result = result.model_copy(update={"request_id": request_id})
    logger.info(
        "generation_finished request_id=%s elapsed_ms=%s status=%s error_code=%s",
        request_id,
        round((time.monotonic() - started_at) * 1000),
        result.status,
        result.error.code if result.error else None,
    )
    return result
