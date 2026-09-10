from contextlib import asynccontextmanager, AsyncExitStack
from pathlib import Path
import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Response
from app.model_benchmark_api import router as model_benchmark_router

from app.models import GenerateRequest, GenerateResponse
from app.openai_service import (
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT_SECONDS,
    OpenAIResponseService,
)
from app.reasoning_models import ReasoningLabBatchResponse, ReasoningLabRunRequest
from app.reasoning_service import ReasoningLabService
from app.temperature_models import (
    TemperatureLabBatchResponse,
    TemperatureLabRunRequest,
)
from app.temperature_service import TemperatureLabService

from app.compression_lab_api import router as compression_lab_router
from app.compression_models import DAY09_CONFIG, VERSION
from app.compression_compare import CompressionComparison
from app.conversation_summary_store import SQLiteConversationSummaryStore
from app.history_summarizer import HistorySummarizer, RollingSummaryContextPolicy
from app.token_lab_api import router as token_lab_router
from app.token_diagnostics import DAY08_CONFIG
from app.openai_token_counter import OpenAIInputTokenCounter
from app.token_overflow import OverflowPreparations
from app.agent import SimpleAgent
from app.agent_api import router as agent_router
from app.agent_sessions import AgentSessionManager
from app.openai_responses_llm_client import OpenAIResponsesLlmClient
from app.sqlite_conversation_store import DEFAULT_DATABASE_PATH, SQLiteConversationStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    old_path = Path(app.state.agent_database_path).resolve()
    token_path = Path(app.state.token_database_path).resolve()
    compression_path = Path(app.state.compression_database_path).resolve()
    if len({old_path, token_path, compression_path}) != 3:
        raise ValueError("Agent namespaces must use different database files")
    async with AsyncExitStack() as resources:
        client = OpenAIResponsesLlmClient()
        resources.push_async_callback(client.close)
        store = SQLiteConversationStore(old_path)
        resources.callback(store.close)
        app.state.agent_sessions = AgentSessionManager(store)
        app.state.agent = SimpleAgent(client)
        token_client = OpenAIResponsesLlmClient()
        resources.push_async_callback(token_client.close)
        counter = OpenAIInputTokenCounter()
        resources.push_async_callback(counter.close)
        token_store = SQLiteConversationStore(token_path)
        resources.callback(token_store.close)
        app.state.token_sessions = AgentSessionManager(token_store)
        app.state.token_agent = SimpleAgent(token_client, DAY08_CONFIG, counter)
        app.state.token_overflow = OverflowPreparations(app.state.token_agent)
        compression_client = OpenAIResponsesLlmClient()
        resources.push_async_callback(compression_client.close)
        compression_counter = OpenAIInputTokenCounter()
        resources.push_async_callback(compression_counter.close)
        compression_store = SQLiteConversationStore(compression_path)
        resources.callback(compression_store.close)
        summaries = SQLiteConversationSummaryStore(compression_store._db, compression_store._transaction, VERSION)
        summarizer = HistorySummarizer(compression_client)
        app.state.compression_sessions = AgentSessionManager(compression_store)
        app.state.compression_summaries = summaries
        app.state.compression_agent = SimpleAgent(compression_client, DAY09_CONFIG, compression_counter,
            RollingSummaryContextPolicy(summaries, summarizer))
        app.state.compression_compare = CompressionComparison(
            summaries.load, summarizer, app.state.compression_agent, compression_counter)
        yield


app = FastAPI(title="Response Control Lab API", version="1.0.0", lifespan=lifespan)
app.state.agent_database_path = DEFAULT_DATABASE_PATH
app.state.token_database_path = DEFAULT_DATABASE_PATH.parents[1] / 'token-lab' / DAY08_CONFIG.version / 'conversations.sqlite3'
app.state.compression_database_path = DEFAULT_DATABASE_PATH.parents[1] / 'compression-lab' / VERSION / 'conversations.sqlite3'
app.include_router(compression_lab_router)
app.include_router(token_lab_router)
app.include_router(agent_router)
app.include_router(model_benchmark_router)

_service = OpenAIResponseService()
_reasoning_service = ReasoningLabService()
_temperature_service = TemperatureLabService()
logger = logging.getLogger("uvicorn.error")


def get_openai_service() -> OpenAIResponseService:
    return _service


def get_reasoning_lab_service() -> ReasoningLabService:
    return _reasoning_service


def get_temperature_lab_service() -> TemperatureLabService:
    return _temperature_service


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

@app.post(
    "/api/v1/temperature-lab/run",
    response_model=TemperatureLabBatchResponse,
)
async def run_temperature_lab(
    request: TemperatureLabRunRequest,
    response: Response,
    service: TemperatureLabService = Depends(get_temperature_lab_service),
) -> TemperatureLabBatchResponse:
    request_id = uuid4().hex[:12]
    response.headers["X-Request-ID"] = request_id
    started_at = time.monotonic()
    logger.info("temperature_batch_started request_id=%s", request_id)
    result = await service.run(request=request, request_id=request_id)
    if result.request_id != request_id:
        result = result.model_copy(update={"request_id": request_id})
    logger.info(
        "temperature_batch_finished request_id=%s duration_ms=%s result_count=%s",
        request_id,
        round((time.monotonic() - started_at) * 1000),
        len(result.results),
    )
    return result
