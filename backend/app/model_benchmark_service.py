"""One independent Responses call per slot, without retries or repair calls."""
import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
from openai import APIError, APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from app.model_benchmark_domain import (
    BENCHMARK_VERSION, CANONICAL_PROMPT, INSTRUCTIONS, benchmark_schema,
    common_parameters, payload_fingerprint, reference_answers, unverified_tasks, verify,
)
from app.model_benchmark_models import (
    BenchmarkAnswer, BenchmarkBatchResponse, BenchmarkCatalog, BenchmarkConfig,
    BenchmarkResult, BenchmarkRunRequest, BenchmarkUsage, RoleOption,
)
from app.model_benchmark_pricing import (
    MODEL_REGISTRY, ROLE_DEFAULTS, calculate_cost, model_options, validate_registry,
)
from app.models import ErrorInfo

OPENAI_TIMEOUT_SECONDS = 240.0
logger = logging.getLogger("uvicorn.error")


def experiment_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        benchmark_version=BENCHMARK_VERSION, prompt=CANONICAL_PROMPT,
        instructions=INSTRUCTIONS, fingerprint=payload_fingerprint(), output_schema=benchmark_schema(),
    )


def catalog() -> BenchmarkCatalog:
    models = model_options()
    return BenchmarkCatalog(
        benchmark_version=BENCHMARK_VERSION, config=experiment_config(), models=models,
        roles=[RoleOption(id=role, display_name=name, default_model_id=model_id, allowed_model_ids=list(MODEL_REGISTRY))
               for role, (name, model_id) in ROLE_DEFAULTS.items()],
    )


def validate_selections(request: BenchmarkRunRequest) -> None:
    validate_registry()
    if any(model_id not in MODEL_REGISTRY for model_id in request.models.model_dump().values()):
        raise ValueError("Выберите модели из каталога backend.")


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url="https://api.openai.com/v1", max_retries=0,
        timeout=httpx.Timeout(OPENAI_TIMEOUT_SECONDS, connect=15.0),
    )


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _counter(value: Any, name: str) -> int | None:
    number = _field(value, name)
    return number if type(number) is int and number >= 0 else None


def normalize_usage(response: Any) -> BenchmarkUsage:
    usage = _field(response, "usage")
    inputs = _field(usage, "input_tokens_details")
    outputs = _field(usage, "output_tokens_details")
    return BenchmarkUsage(
        input_tokens=_counter(usage, "input_tokens"),
        cached_input_tokens=_counter(inputs, "cached_tokens"),
        cache_write_tokens=_counter(inputs, "cache_write_tokens"),
        output_tokens=_counter(usage, "output_tokens"),
        reasoning_tokens=_counter(outputs, "reasoning_tokens"),
        total_tokens=_counter(usage, "total_tokens"),
    )


def normalize_response(response: Any, *, role: str, model_id: str, latency_ms: int) -> BenchmarkResult:
    usage = normalize_usage(response)
    raw_status = _field(response, "status")
    raw_output = _field(response, "output_text") or None
    resolved = _field(response, "model")
    result = BenchmarkResult(
        role=role, requested_model=model_id, display_name=MODEL_REGISTRY[model_id].display_name,
        resolved_model=resolved, status="invalid_response", response_status=raw_status,
        tasks=unverified_tasks(), raw_output=raw_output, latency_ms=latency_ms, api_call_count=1,
        usage=usage, cost=calculate_cost(usage, resolved, _field(response, "service_tier")),
    )
    if raw_status == "incomplete":
        result.status = "incomplete"
        result.reason = _field(_field(response, "incomplete_details"), "reason") or "incomplete"
        return result
    refusal = any(
        _field(content, "type") == "refusal"
        for item in (_field(response, "output") or [])
        for content in (_field(item, "content") or [])
    )
    if refusal:
        result.status = "refused"
        result.reason = "Модель отказалась формировать ответ."
        return result
    if raw_status != "completed":
        result.status = "api_error"
        result.reason = "OpenAI не завершил запрос."
        return result
    try:
        answer = BenchmarkAnswer.model_validate_json(raw_output or "", strict=True)
    except ValidationError:
        result.reason = "Ответ не соответствует полной структуре пяти задач."
        return result
    result.quality, result.tasks = verify(answer)
    result.status = "completed"
    return result


class ModelBenchmarkService:
    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self.client_factory = client_factory or _client

    async def run(self, request: BenchmarkRunRequest, request_id: str) -> BenchmarkBatchResponse:
        validate_selections(request)
        # Compute the independent reference before starting latency measurements.
        reference_answers()
        selections = request.models.model_dump()
        gathered = await asyncio.gather(
            *(self.run_model(role, selections[role], request_id) for role in ROLE_DEFAULTS),
            return_exceptions=True,
        )
        results = []
        for role, item in zip(ROLE_DEFAULTS, gathered, strict=True):
            if isinstance(item, BaseException):
                # run_model catches per-call failures with its exact attempt count.
                # Cancellation must propagate rather than inventing attempt metrics.
                raise item
            results.append(item)
        return BenchmarkBatchResponse(
            request_id=request_id, config=experiment_config(), results=results,
            api_call_count=sum(result.api_call_count for result in results),
        )

    async def run_model(self, role: str, model_id: str, request_id: str) -> BenchmarkResult:
        count = 0
        started = None
        elapsed = None
        try:
            async with self.client_factory() as client:
                parameters = common_parameters()
                parameters["model"] = model_id
                started = time.monotonic()
                count = 1
                logger.info("model_benchmark_call_started request_id=%s role=%s model=%s", request_id, role, model_id)
                response = await asyncio.wait_for(
                    client.responses.create(**parameters), timeout=OPENAI_TIMEOUT_SECONDS,
                )
                elapsed = round((time.monotonic() - started) * 1000)
            result = normalize_response(response, role=role, model_id=model_id, latency_ms=elapsed)
        except Exception as exc:
            latency = elapsed if elapsed is not None else (round((time.monotonic() - started) * 1000) if started is not None else 0)
            if isinstance(exc, (APITimeoutError, TimeoutError)):
                status, reason = "timeout", "Время ожидания OpenAI истекло; результат обработки неизвестен."
            elif isinstance(exc, APIError):
                status, reason = "api_error", "OpenAI отклонил запрос или недоступен. Повтор не выполнялся."
            else:
                status, reason = "internal_error", "Не удалось подготовить или обработать вызов модели."
            result = BenchmarkResult(
                role=role, requested_model=model_id, display_name=MODEL_REGISTRY[model_id].display_name,
                status=status, reason=reason, error=ErrorInfo(code=status, message=reason),
                tasks=unverified_tasks(), latency_ms=latency, api_call_count=count,
                cost=calculate_cost(BenchmarkUsage(), None, None),
            )
        logger.info(
            "model_benchmark_call_finished request_id=%s role=%s status=%s latency_ms=%s api_calls=%s",
            request_id, role, result.status, result.latency_ms, result.api_call_count,
        )
        return result
