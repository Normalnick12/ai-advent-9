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
from app.reasoning_models import ReasoningLabBatchResponse, ReasoningLabRunRequest
from app.reasoning_service import ReasoningLabService

app = FastAPI(title="Response Control Lab API", version="1.0.0")

_service = OpenAIResponseService()
_reasoning_service = ReasoningLabService()
logger = logging.getLogger("uvicorn.error")


def get_openai_service() -> OpenAIResponseService:
    return _service


def get_reasoning_lab_service() -> ReasoningLabService:
    return _reasoning_service


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


@app.post(
    "/api/v1/reasoning-lab/run",
    response_model=ReasoningLabBatchResponse,
)
async def run_reasoning_lab(
    _: ReasoningLabRunRequest,
    response: Response,
    service: ReasoningLabService = Depends(get_reasoning_lab_service),
) -> ReasoningLabBatchResponse:
    request_id = uuid4().hex[:12]
    response.headers["X-Request-ID"] = request_id
    started_at = time.monotonic()
    logger.info("reasoning_batch_started request_id=%s", request_id)
    result = await service.run(request_id=request_id)
    if result.request_id != request_id:
        result = result.model_copy(update={"request_id": request_id})
    logger.info(
        "reasoning_batch_finished request_id=%s duration_ms=%s result_count=%s "
        "correct_count=%s",
        request_id,
        round((time.monotonic() - started_at) * 1000),
        len(result.results),
        sum(item.correct for item in result.results),
    )
    return result
