import json
import logging
import time
from typing import Any

import httpx
from openai import APITimeoutError, AsyncOpenAI
from pydantic import ValidationError

from app.models import (
    AppliedControls,
    ErrorInfo,
    GenerateRequest,
    GenerateResponse,
    Recipe,
)

MODEL = "gpt-5.6"
OPENAI_TIMEOUT_SECONDS = 75.0
OPENAI_MAX_RETRIES = 1
OPENAI_TIMEOUT = httpx.Timeout(OPENAI_TIMEOUT_SECONDS, connect=5.0)

logger = logging.getLogger("uvicorn.error")

FINISH_INSTRUCTION = (
    "После выполнения запрошенной задачи немедленно заверши ответ. "
    "Не добавляй вступление, заключение, дополнительные рекомендации, "
    "предложения продолжить диалог или другие комментарии. "
    "Если используется структурированный формат, после формирования полного "
    "объекта рецепта немедленно заверши ответ."
)


def _recipe_json_schema() -> dict[str, Any]:
    """A strict, explicit schema sent to the Responses API."""
    return {
        "type": "object",
        "properties": {
            "recipe_name": {"type": "string"},
            "ingredients": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "weight_grams": {"type": "integer"},
                        "order": {"type": "integer"},
                    },
                    "required": ["name", "weight_grams", "order"],
                    "additionalProperties": False,
                },
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "order": {"type": "integer"},
                        "description": {"type": "string"},
                    },
                    "required": ["order", "description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["recipe_name", "ingredients", "steps"],
        "additionalProperties": False,
    }


class OpenAIResponseService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client

    @property
    def client(self) -> AsyncOpenAI:
        # Lazy construction keeps importing the FastAPI app possible without a key.
        if self._client is None:
            self._client = AsyncOpenAI(
                timeout=OPENAI_TIMEOUT,
                max_retries=OPENAI_MAX_RETRIES,
            )
        return self._client

    async def generate(
        self,
        request: GenerateRequest,
        request_id: str = "unknown",
    ) -> GenerateResponse:
        applied = AppliedControls(**request.controls.model_dump())
        parameters: dict[str, Any] = {
            "model": MODEL,
            "input": request.prompt,
        }

        if request.controls.structured_output:
            parameters["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "recipe",
                    "description": "A recipe with ordered ingredients and preparation steps.",
                    "strict": True,
                    "schema": _recipe_json_schema(),
                }
            }
        if request.controls.max_output_tokens is not None:
            parameters["max_output_tokens"] = request.controls.max_output_tokens
        if request.controls.finish_instruction:
            parameters["instructions"] = FINISH_INSTRUCTION

        started_at = time.monotonic()
        logger.info(
            "openai_request_started request_id=%s structured=%s max_output_tokens=%s "
            "finish_instruction=%s timeout_seconds=%s max_retries=%s",
            request_id,
            applied.structured_output,
            applied.max_output_tokens,
            applied.finish_instruction,
            OPENAI_TIMEOUT_SECONDS,
            OPENAI_MAX_RETRIES,
        )
        try:
            response = await self.client.responses.create(**parameters)
        except APITimeoutError:
            elapsed_ms = round((time.monotonic() - started_at) * 1000)
            logger.warning(
                "openai_request_timeout request_id=%s elapsed_ms=%s timeout_seconds=%s "
                "max_retries=%s",
                request_id,
                elapsed_ms,
                OPENAI_TIMEOUT_SECONDS,
                OPENAI_MAX_RETRIES,
            )
            return GenerateResponse(
                request_id=request_id,
                status="error",
                controls=applied,
                error=ErrorInfo(
                    code="openai_timeout",
                    message=(
                        "OpenAI did not respond within the configured backend timeout. "
                        "Check backend logs with this request_id."
                    ),
                ),
            )
        except Exception as exc:  # The public contract must also cover SDK/network errors.
            elapsed_ms = round((time.monotonic() - started_at) * 1000)
            logger.exception(
                "openai_request_failed request_id=%s elapsed_ms=%s error_type=%s",
                request_id,
                elapsed_ms,
                type(exc).__name__,
            )
            return GenerateResponse(
                request_id=request_id,
                status="error",
                controls=applied,
                error=ErrorInfo(code=type(exc).__name__, message=str(exc)),
            )

        status = _string_value(getattr(response, "status", "unknown"))
        content = getattr(response, "output_text", None) or None
        usage = getattr(response, "usage", None)
        output_tokens = getattr(usage, "output_tokens", None) if usage else None
        incomplete_details = getattr(response, "incomplete_details", None)
        incomplete_reason = (
            _string_value(getattr(incomplete_details, "reason", None))
            if incomplete_details
            else None
        )
        response_error = getattr(response, "error", None)
        elapsed_ms = round((time.monotonic() - started_at) * 1000)
        logger.info(
            "openai_request_finished request_id=%s openai_request_id=%s elapsed_ms=%s "
            "status=%s output_tokens=%s",
            request_id,
            getattr(response, "_request_id", None),
            elapsed_ms,
            status,
            output_tokens,
        )
        error = None
        if response_error:
            error = ErrorInfo(
                code=_string_value(getattr(response_error, "code", "openai_error")),
                message=str(getattr(response_error, "message", "OpenAI response failed")),
            )

        recipe = None
        if request.controls.structured_output and content and status == "completed":
            try:
                recipe = Recipe.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                error = ErrorInfo(
                    code="structured_output_parse_error",
                    message=f"OpenAI returned an invalid recipe object: {exc}",
                )

        return GenerateResponse(
            request_id=request_id,
            content=content if not recipe else None,
            recipe=recipe,
            status=status,
            output_tokens=output_tokens,
            controls=applied,
            incomplete_reason=incomplete_reason,
            error=error,
        )


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))
