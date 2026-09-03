import asyncio
import logging
import re
import time
from typing import Any

import httpx
from openai import APITimeoutError, AsyncOpenAI, BadRequestError
from pydantic import ValidationError

from app.models import ErrorInfo
from app.reasoning_models import TokenUsage
from app.temperature_domain import (
    TemperatureMode,
    VariantInput,
    mode_for_prompt,
    normalize_name,
    validate_variants,
)
from app.temperature_models import (
    BenchmarkValidation,
    RawBenchmarkResponse,
    RequirementCheck,
    TemperatureExperimentConfig,
    TemperatureLabBatchResponse,
    TemperatureLabRunRequest,
    TemperatureResult,
    TemperatureVariant,
)

TEMPERATURE_MODEL = "gpt-5.6"
TEMPERATURE_VALUES = (0.0, 0.7, 1.2)
TEMPERATURE_REASONING_EFFORT = "none"
TEMPERATURE_REASONING_MODE = "standard"
TEMPERATURE_MAX_OUTPUT_TOKENS = 600
TEMPERATURE_OPENAI_TIMEOUT_SECONDS = 75.0
TEMPERATURE_OPENAI_MAX_RETRIES = 0
TEMPERATURE_OPENAI_TIMEOUT = httpx.Timeout(
    TEMPERATURE_OPENAI_TIMEOUT_SECONDS,
    connect=5.0,
)

BENCHMARK_MODE_MESSAGE = "Benchmark-режим: доступна проверка пяти формальных требований."
FREE_MODE_MESSAGE = "Автопроверка benchmark недоступна для произвольного запроса."

logger = logging.getLogger("uvicorn.error")


class _TemperatureFailure(Exception):
    def __init__(self, code: str, message: str, status: str = "error") -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.status = status


def benchmark_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "slogan": {"type": "string"},
                    },
                    "required": ["name", "slogan"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["variants"],
        "additionalProperties": False,
    }


def build_response_parameters(
    *,
    prompt: str,
    mode: TemperatureMode,
    temperature: float,
) -> dict[str, Any]:
    text_format: dict[str, Any]
    if mode == "benchmark":
        text_format = {
            "type": "json_schema",
            "name": "temperature_lab_variants",
            "description": "Candidate app names and their short slogans.",
            "strict": True,
            "schema": benchmark_json_schema(),
        }
    else:
        text_format = {"type": "text"}

    return {
        "model": TEMPERATURE_MODEL,
        "input": prompt,
        "reasoning": {
            "effort": TEMPERATURE_REASONING_EFFORT,
            "mode": TEMPERATURE_REASONING_MODE,
        },
        "max_output_tokens": TEMPERATURE_MAX_OUTPUT_TOKENS,
        "store": False,
        "prompt_cache_options": {"mode": "explicit"},
        "text": {"format": text_format},
        "temperature": temperature,
    }


class TemperatureLabService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                timeout=TEMPERATURE_OPENAI_TIMEOUT,
                max_retries=TEMPERATURE_OPENAI_MAX_RETRIES,
            )
        return self._client

    async def run(
        self,
        request: TemperatureLabRunRequest,
        request_id: str,
    ) -> TemperatureLabBatchResponse:
        mode = mode_for_prompt(request.prompt)
        gathered = await asyncio.gather(
            *(
                self.run_temperature(
                    prompt=request.prompt,
                    mode=mode,
                    temperature=temperature,
                    request_id=request_id,
                )
                for temperature in TEMPERATURE_VALUES
            ),
            return_exceptions=True,
        )

        results: list[TemperatureResult] = []
        for temperature, item in zip(TEMPERATURE_VALUES, gathered, strict=True):
            if isinstance(item, BaseException):
                logger.error(
                    "temperature_result_unhandled request_id=%s temperature=%s "
                    "error_type=%s",
                    request_id,
                    temperature,
                    type(item).__name__,
                )
                item = _failure_result(
                    temperature=temperature,
                    latency_ms=0,
                    usage=_zero_usage(),
                    code="internal_error",
                    message="Внутренняя ошибка запуска temperature.",
                )
            results.append(item)

        return TemperatureLabBatchResponse(
            request_id=request_id,
            mode=mode,
            mode_message=(
                BENCHMARK_MODE_MESSAGE if mode == "benchmark" else FREE_MODE_MESSAGE
            ),
            config=TemperatureExperimentConfig(
                output_contract=(
                    "strict_variants" if mode == "benchmark" else "text"
                )
            ),
            results=results,
        )

    async def run_temperature(
        self,
        *,
        prompt: str,
        mode: TemperatureMode,
        temperature: float,
        request_id: str,
    ) -> TemperatureResult:
        started_at = time.monotonic()
        usage = _zero_usage()
        logger.info(
            "temperature_result_started request_id=%s temperature=%s mode=%s",
            request_id,
            temperature,
            mode,
        )
        try:
            response = await self.client.responses.create(
                **build_response_parameters(
                    prompt=prompt,
                    mode=mode,
                    temperature=temperature,
                )
            )
            usage = _usage_from_response(response)
            self._require_completed(response)
            output_text = _output_text(response)

            if mode == "benchmark":
                parsed = RawBenchmarkResponse.model_validate_json(output_text)
                inputs = [
                    VariantInput(name=item.name, slogan=item.slogan)
                    for item in parsed.variants
                ]
                outcome = validate_variants(inputs)
                result = TemperatureResult(
                    temperature=temperature,
                    status="completed",
                    latency_ms=_elapsed_ms(started_at),
                    usage=usage,
                    variants=[
                        TemperatureVariant(
                            name=item.name,
                            slogan=item.slogan,
                            normalized_name=normalize_name(item.name),
                        )
                        for item in parsed.variants
                    ],
                    validation=BenchmarkValidation(
                        requirements_met=outcome.requirements_met,
                        checks=[
                            RequirementCheck(
                                id=check.check_id,
                                label=check.label,
                                passed=check.passed,
                            )
                            for check in outcome.checks
                        ],
                    ),
                )
            else:
                result = TemperatureResult(
                    temperature=temperature,
                    status="completed",
                    latency_ms=_elapsed_ms(started_at),
                    usage=usage,
                    content=output_text,
                )
        except BadRequestError as exc:
            status_code, error_message, error_param, error_code = (
                _bad_request_log_details(exc)
            )
            logger.warning(
                "temperature_result_bad_request request_id=%s temperature=%s "
                "status_code=%s error_code=%s error_param=%s error_message=%s",
                request_id,
                temperature,
                status_code,
                error_code,
                error_param,
                error_message,
            )
            result = _failure_result(
                temperature=temperature,
                latency_ms=_elapsed_ms(started_at),
                usage=usage,
                code="openai_bad_request",
                message="OpenAI отклонил фиксированные параметры temperature-запроса.",
            )
        except APITimeoutError:
            result = _failure_result(
                temperature=temperature,
                latency_ms=_elapsed_ms(started_at),
                usage=usage,
                code="openai_timeout",
                message="OpenAI не ответил за отведённое время.",
            )
        except _TemperatureFailure as failure:
            result = _failure_result(
                temperature=temperature,
                latency_ms=_elapsed_ms(started_at),
                usage=usage,
                code=failure.code,
                message=failure.public_message,
                status=failure.status,
            )
        except (ValidationError, ValueError) as exc:
            logger.warning(
                "temperature_result_parse_error request_id=%s temperature=%s "
                "error_type=%s",
                request_id,
                temperature,
                type(exc).__name__,
            )
            result = _failure_result(
                temperature=temperature,
                latency_ms=_elapsed_ms(started_at),
                usage=usage,
                code="response_parse_error",
                message="OpenAI вернул некорректный ответ temperature-запроса.",
            )
        except Exception as exc:
            logger.warning(
                "temperature_result_upstream_error request_id=%s temperature=%s "
                "error_type=%s",
                request_id,
                temperature,
                type(exc).__name__,
            )
            result = _failure_result(
                temperature=temperature,
                latency_ms=_elapsed_ms(started_at),
                usage=usage,
                code="openai_upstream_error",
                message="OpenAI временно недоступен для этого temperature-запроса.",
            )

        logger.info(
            "temperature_result_finished request_id=%s temperature=%s "
            "duration_ms=%s status=%s",
            request_id,
            temperature,
            result.latency_ms,
            result.status,
        )
        return result

    @staticmethod
    def _require_completed(response: Any) -> None:
        status = _string_value(_attribute(response, "status", "unknown"))
        if status == "completed":
            return
        reason = _string_value(
            _attribute(_attribute(response, "incomplete_details", None), "reason", None)
        )
        safe_reason = reason if reason in {"max_output_tokens", "content_filter"} else "unknown"
        if status == "incomplete":
            raise _TemperatureFailure(
                "openai_incomplete",
                f"OpenAI не завершил ответ (причина: {safe_reason}).",
                status="incomplete",
            )
        raise _TemperatureFailure(
            "openai_failed",
            "OpenAI не завершил temperature-запрос успешно.",
        )


def _failure_result(
    *,
    temperature: float,
    latency_ms: int,
    usage: TokenUsage,
    code: str,
    message: str,
    status: str = "error",
) -> TemperatureResult:
    return TemperatureResult(
        temperature=temperature,
        status=status,
        latency_ms=latency_ms,
        usage=usage,
        error=ErrorInfo(code=code, message=message),
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


def _output_text(response: Any) -> str:
    value = _attribute(response, "output_text", None)
    if not isinstance(value, str) or not value:
        raise _TemperatureFailure(
            "response_parse_error",
            "OpenAI не вернул текст temperature-ответа.",
        )
    return value


def _attribute(value: Any, name: str, default: Any = None) -> Any:
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
    text = re.sub(r"(?i)(?:Bearer\s+)?sk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(
        r"(?i)(OPENAI_API_KEY\s*[=:]\s*)\S+",
        r"\1[REDACTED]",
        text,
    )
    return text[:2000]


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((time.monotonic() - started_at) * 1000))
