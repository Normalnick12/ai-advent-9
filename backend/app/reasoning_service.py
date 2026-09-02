import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import APITimeoutError, AsyncOpenAI, BadRequestError
from pydantic import ValidationError

from app.models import ErrorInfo
from app.reasoning_domain import (
    CANONICAL_TASK,
    REFERENCE_SOLUTION,
    VerificationOutcome,
    verify_solution,
)
from app.reasoning_models import (
    ExperimentConfig,
    OptimizationSolution,
    ReasoningLabBatchResponse,
    STRATEGY_DISPLAY_NAMES,
    StrategyId,
    StrategyResult,
    TokenUsage,
    VerificationDetails,
)

REASONING_MODEL = "gpt-5.6"
REASONING_EFFORT = "medium"
REASONING_MODE = "standard"
REASONING_MAX_OUTPUT_TOKENS = 1200
REASONING_OPENAI_TIMEOUT_SECONDS = 75.0
REASONING_OPENAI_MAX_RETRIES = 0
REASONING_OPENAI_TIMEOUT = httpx.Timeout(
    REASONING_OPENAI_TIMEOUT_SECONDS,
    connect=5.0,
)

STEP_BY_STEP_INSTRUCTION = (
    "Реши задачу пошагово: проверь ограничения, сравни допустимые варианты и "
    "кратко отрази проверку в поле explanation."
)
EXPERT_PANEL_INSTRUCTION = (
    "Последовательно смоделируй вклад аналитика, инженера и критика: аналитик "
    "формализует задачу, инженер находит решение, критик проверяет ограничения "
    "и оптимальность. Затем верни один общий финальный объект решения."
)
META_PROMPT_INSTRUCTION = (
    "Создай улучшенную инструкцию для другой модели, которая решит переданную "
    "оптимизационную задачу. Инструкция должна помогать найти и проверить "
    "оптимум, не изменяя ни одну фичу, стоимость, ценность или ограничение."
)

logger = logging.getLogger("uvicorn.error")


def solution_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "selected_features": {
                "type": "array",
                "items": {"type": "string", "enum": list("ABCDEFGH")},
            },
            "total_cost": {"type": "integer"},
            "total_value": {"type": "integer"},
            "explanation": {"type": "string"},
        },
        "required": [
            "selected_features",
            "total_cost",
            "total_value",
            "explanation",
        ],
        "additionalProperties": False,
    }


def meta_prompt_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "generated_prompt": {"type": "string", "minLength": 1},
        },
        "required": ["generated_prompt"],
        "additionalProperties": False,
    }


def build_response_parameters(
    *,
    format_name: str,
    schema: dict[str, Any],
    description: str,
    instructions: str | None = None,
) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "model": REASONING_MODEL,
        "input": CANONICAL_TASK,
        "reasoning": {
            "effort": REASONING_EFFORT,
            "mode": REASONING_MODE,
        },
        "max_output_tokens": REASONING_MAX_OUTPUT_TOKENS,
        "store": False,
        "prompt_cache_options": {"mode": "explicit"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": format_name,
                "description": description,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if instructions is not None:
        parameters["instructions"] = instructions
    return parameters


@dataclass
class _PipelineState:
    api_call_count: int = 0
    usage: TokenUsage = field(default_factory=lambda: _zero_usage())
    generated_prompt: str | None = None


class _StrategyFailure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message


class ReasoningLabService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                timeout=REASONING_OPENAI_TIMEOUT,
                max_retries=REASONING_OPENAI_MAX_RETRIES,
            )
        return self._client

    async def run(self, request_id: str) -> ReasoningLabBatchResponse:
        strategies = (
            StrategyId.DIRECT,
            StrategyId.STEP_BY_STEP,
            StrategyId.META_PROMPT,
            StrategyId.EXPERT_PANEL,
        )
        gathered = await asyncio.gather(
            *(self.run_strategy(strategy, request_id) for strategy in strategies),
            return_exceptions=True,
        )
        results: list[StrategyResult] = []
        for strategy, item in zip(strategies, gathered, strict=True):
            if isinstance(item, BaseException):
                logger.error(
                    "reasoning_strategy_unhandled request_id=%s strategy=%s error_type=%s",
                    request_id,
                    strategy.value,
                    type(item).__name__,
                )
                item = _failure_result(
                    strategy=strategy,
                    latency_ms=0,
                    state=_PipelineState(),
                    code="internal_error",
                    message="Внутренняя ошибка стратегии.",
                )
            results.append(item)

        reference = OptimizationSolution(
            selected_features=list(REFERENCE_SOLUTION.selected_features),
            total_cost=REFERENCE_SOLUTION.total_cost,
            total_value=REFERENCE_SOLUTION.total_value,
            explanation="Детерминированный оптимум полного перебора.",
        )
        return ReasoningLabBatchResponse(
            request_id=request_id,
            config=ExperimentConfig(),
            reference_solution=reference,
            results=results,
        )

    async def run_strategy(
        self,
        strategy: StrategyId,
        request_id: str,
    ) -> StrategyResult:
        started_at = time.monotonic()
        state = _PipelineState()
        logger.info(
            "reasoning_strategy_started request_id=%s strategy=%s",
            request_id,
            strategy.value,
        )
        try:
            if strategy is StrategyId.META_PROMPT:
                solution = await self._run_meta_prompt(state)
            else:
                instruction = {
                    StrategyId.DIRECT: None,
                    StrategyId.STEP_BY_STEP: STEP_BY_STEP_INSTRUCTION,
                    StrategyId.EXPERT_PANEL: EXPERT_PANEL_INSTRUCTION,
                }[strategy]
                solution = await self._run_final_call(state, instruction)
            outcome = verify_solution(
                solution.selected_features,
                solution.total_cost,
                solution.total_value,
            )
            result = _success_result(
                strategy=strategy,
                latency_ms=_elapsed_ms(started_at),
                state=state,
                solution=solution,
                outcome=outcome,
            )
        except BadRequestError as exc:
            status_code, error_message, error_param, error_code = (
                _bad_request_log_details(exc)
            )
            logger.warning(
                "reasoning_strategy_bad_request request_id=%s strategy=%s "
                "status_code=%s error_code=%s error_param=%s error_message=%s",
                request_id,
                strategy.value,
                status_code,
                error_code,
                error_param,
                error_message,
            )
            result = _failure_result(
                strategy=strategy,
                latency_ms=_elapsed_ms(started_at),
                state=state,
                code="openai_bad_request",
                message="OpenAI отклонил параметры запроса стратегии.",
            )
        except APITimeoutError:
            result = _failure_result(
                strategy=strategy,
                latency_ms=_elapsed_ms(started_at),
                state=state,
                code="openai_timeout",
                message="OpenAI не ответил за отведённое время.",
            )
        except _StrategyFailure as failure:
            result = _failure_result(
                strategy=strategy,
                latency_ms=_elapsed_ms(started_at),
                state=state,
                code=failure.code,
                message=failure.public_message,
            )
        except Exception as exc:
            logger.warning(
                "reasoning_strategy_upstream_error request_id=%s strategy=%s "
                "error_type=%s",
                request_id,
                strategy.value,
                type(exc).__name__,
            )
            result = _failure_result(
                strategy=strategy,
                latency_ms=_elapsed_ms(started_at),
                state=state,
                code="openai_upstream_error",
                message="OpenAI временно недоступен для этой стратегии.",
            )

        logger.info(
            "reasoning_strategy_finished request_id=%s strategy=%s duration_ms=%s "
            "status=%s api_call_count=%s",
            request_id,
            strategy.value,
            result.latency_ms,
            "correct" if result.correct else "incorrect",
            result.api_call_count,
        )
        return result

    async def _run_meta_prompt(
        self,
        state: _PipelineState,
    ) -> OptimizationSolution:
        response = await self._create_response(
            state,
            build_response_parameters(
                format_name="generated_meta_prompt",
                schema=meta_prompt_json_schema(),
                description="An improved instruction for solving the fixed benchmark.",
                instructions=META_PROMPT_INSTRUCTION,
            ),
        )
        self._require_completed(response)
        try:
            payload = json.loads(_output_text(response))
            generated_prompt = payload["generated_prompt"]
            if not isinstance(generated_prompt, str) or not generated_prompt.strip():
                raise ValueError("generated_prompt must be a non-empty string")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise _StrategyFailure(
                "meta_prompt_parse_error",
                "Мета-промпт вернул некорректную структурированную инструкцию.",
            ) from exc
        state.generated_prompt = generated_prompt
        return await self._run_final_call(state, generated_prompt)

    async def _run_final_call(
        self,
        state: _PipelineState,
        instructions: str | None,
    ) -> OptimizationSolution:
        response = await self._create_response(
            state,
            build_response_parameters(
                format_name="optimization_solution",
                schema=solution_json_schema(),
                description="A selected feature set with independently checkable totals.",
                instructions=instructions,
            ),
        )
        self._require_completed(response)
        try:
            return OptimizationSolution.model_validate_json(_output_text(response))
        except (ValidationError, ValueError) as exc:
            raise _StrategyFailure(
                "structured_output_parse_error",
                "OpenAI вернул некорректный структурированный результат.",
            ) from exc

    async def _create_response(
        self,
        state: _PipelineState,
        parameters: dict[str, Any],
    ) -> Any:
        state.api_call_count += 1
        response = await self.client.responses.create(**parameters)
        state.usage = _add_usage(state.usage, _usage_from_response(response))
        return response

    @staticmethod
    def _require_completed(response: Any) -> None:
        status = _string_value(_attribute(response, "status", "unknown"))
        if status == "completed":
            return
        reason = _string_value(
            _attribute(_attribute(response, "incomplete_details", None), "reason", None)
        )
        safe_reason = reason if reason in {"max_output_tokens", "content_filter"} else "unknown"
        raise _StrategyFailure(
            "openai_incomplete",
            f"OpenAI не завершил ответ (причина: {safe_reason}).",
        )


def _success_result(
    *,
    strategy: StrategyId,
    latency_ms: int,
    state: _PipelineState,
    solution: OptimizationSolution,
    outcome: VerificationOutcome,
) -> StrategyResult:
    return StrategyResult(
        strategy=strategy,
        display_name=STRATEGY_DISPLAY_NAMES[strategy],
        correct=outcome.correct,
        latency_ms=latency_ms,
        usage=state.usage,
        api_call_count=state.api_call_count,
        solution=solution,
        verification=_verification_details(outcome),
        generated_prompt=state.generated_prompt,
    )


def _failure_result(
    *,
    strategy: StrategyId,
    latency_ms: int,
    state: _PipelineState,
    code: str,
    message: str,
) -> StrategyResult:
    return StrategyResult(
        strategy=strategy,
        display_name=STRATEGY_DISPLAY_NAMES[strategy],
        correct=False,
        latency_ms=latency_ms,
        usage=state.usage,
        api_call_count=state.api_call_count,
        verification=VerificationDetails(
            feasible=False,
            optimal=False,
            totals_match=False,
            calculated_cost=0,
            calculated_value=0,
            violations=[message],
        ),
        error=ErrorInfo(code=code, message=message),
        generated_prompt=state.generated_prompt,
    )


def _verification_details(outcome: VerificationOutcome) -> VerificationDetails:
    return VerificationDetails(
        feasible=outcome.feasible,
        optimal=outcome.optimal,
        totals_match=outcome.totals_match,
        calculated_cost=outcome.calculated_cost,
        calculated_value=outcome.calculated_value,
        violations=list(outcome.violations),
    )


def _zero_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
        total_tokens=0,
    )


def _usage_from_response(response: Any) -> TokenUsage:
    usage = _attribute(response, "usage", None)
    details = _attribute(usage, "output_tokens_details", None)
    return TokenUsage(
        input_tokens=int(_attribute(usage, "input_tokens", 0) or 0),
        output_tokens=int(_attribute(usage, "output_tokens", 0) or 0),
        reasoning_tokens=int(_attribute(details, "reasoning_tokens", 0) or 0),
        total_tokens=int(_attribute(usage, "total_tokens", 0) or 0),
    )


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        reasoning_tokens=left.reasoning_tokens + right.reasoning_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
    )


def _output_text(response: Any) -> str:
    value = _attribute(response, "output_text", None)
    if not isinstance(value, str) or not value:
        raise _StrategyFailure(
            "structured_output_parse_error",
            "OpenAI не вернул структурированный текст результата.",
        )
    return value


def _attribute(value: Any, name: str, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _string_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _bad_request_log_details(
    error: BadRequestError,
) -> tuple[int, str | None, str | None, str | None]:
    body = error.body if isinstance(error.body, dict) else {}
    payload = body.get("error", body)
    if not isinstance(payload, dict):
        payload = {}
    message = payload.get("message", getattr(error, "message", None))
    return (
        error.status_code,
        _safe_upstream_log_value(message),
        _safe_upstream_log_value(payload.get("param")),
        _safe_upstream_log_value(payload.get("code")),
    )


def _safe_upstream_log_value(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    text = re.sub(
        r"(?i)(?:Bearer\s+)?sk-[A-Za-z0-9_-]+",
        "[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)(OPENAI_API_KEY\s*[=:]\s*)\S+",
        r"\1[REDACTED]",
        text,
    )
    return text[:2000]


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.monotonic() - started_at) * 1000))
