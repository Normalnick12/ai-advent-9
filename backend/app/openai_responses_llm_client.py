import asyncio
from dataclasses import replace

import httpx
from openai import AsyncOpenAI, APIStatusError, APITimeoutError, OpenAIError

from app.llm_client import AgentConfig, ConversationMessage, LlmResult, TokenUsage
from app.openai_agent_payload import generation_payload

DEADLINE_SECONDS = 75


def failure(code: str, message: str) -> LlmResult:
    return LlmResult("error", error_code=code, error_message=message)


class OpenAIResponsesLlmClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                timeout=httpx.Timeout(75.0, connect=5.0), max_retries=0,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()

    async def complete(
        self, messages: tuple[ConversationMessage, ...], config: AgentConfig,
    ) -> LlmResult:
        try:
            response = await asyncio.wait_for(
                self._get_client().responses.create(
                    **generation_payload(messages, config),
                ),
                timeout=DEADLINE_SECONDS,
            )
        except (TimeoutError, APITimeoutError):
            return failure("llm_timeout", "Модель не ответила вовремя. Попробуйте ещё раз.")
        except APIStatusError as exc:
            if config.version is None:
                return failure("llm_upstream_error", "Не удалось получить ответ модели. Попробуйте ещё раз.")
            body = exc.body if isinstance(exc.body, dict) else {}
            error = body.get("error", body)
            code = provider_error_code(error, exc.status_code)
            return replace(failure(code, provider_error_message(code)),
                           **metadata(body, config))
        except OpenAIError:
            return failure("llm_upstream_error", "Не удалось получить ответ модели. Попробуйте ещё раз.")
        outcome = self._normalize(response)
        if config.version is not None and getattr(response, "status", None) == "failed":
            code = provider_error_code(getattr(response, "error", None))
            outcome = replace(outcome, error_code=code, error_message=provider_error_message(code))
        return replace(outcome, **metadata(response, config))

    @staticmethod
    def _normalize(response: object) -> LlmResult:
        status = getattr(response, "status", None)
        if status == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            return LlmResult(
                "incomplete", error_code="llm_incomplete",
                error_message="Ответ модели не завершён. Попробуйте ещё раз.",
                incomplete_reason=reason if reason in {"max_output_tokens", "content_filter"} else "unknown",
            )
        text: list[str] = []
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "message":
                continue
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "refusal":
                    return LlmResult("refused", error_code="llm_refused", error_message="Модель отказалась отвечать на запрос.")
                if getattr(part, "type", None) == "output_text":
                    value = getattr(part, "text", None)
                    if isinstance(value, str):
                        text.append(value)
        reply = "".join(text)
        if status == "completed" and reply.strip():
            return LlmResult("completed", reply=reply)
        if status == "failed":
            return failure("llm_upstream_error", "Не удалось получить ответ модели. Попробуйте ещё раз.")
        return failure("llm_invalid_response", "Модель вернула непригодный ответ. Попробуйте ещё раз.")



def field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def metadata(response, config):
    raw = field(response, "usage")
    usage = None
    if raw is not None:
        input_details = field(raw, "input_tokens_details")
        output_details = field(raw, "output_tokens_details")
        counters = {
            "input_tokens": field(raw, "input_tokens"),
            "cached_input_tokens": field(input_details, "cached_tokens"),
            "cache_write_tokens": field(input_details, "cache_write_tokens"),
            "output_tokens": field(raw, "output_tokens"),
            "reasoning_tokens": field(output_details, "reasoning_tokens"),
            "total_tokens": field(raw, "total_tokens"),
        }
        invalid = tuple(k for k, v in counters.items() if v is not None and
                        (type(v) is not int or v < 0))
        usage = TokenUsage(**{k: v if type(v) is int and v >= 0 else None
                              for k, v in counters.items()}, invalid_fields=invalid)
    def string(name):
        value = field(response, name)
        return value if isinstance(value, str) else None
    return dict(usage=usage, requested_model=config.model, resolved_model=string("model"),
                requested_service_tier=config.service_tier, actual_service_tier=string("service_tier"),
                provider_status=string("status"))


def provider_error_code(error, http_status=None):
    # HTTP status alone never proves context overflow.
    if http_status == 429:
        return "llm_rate_limit"
    if http_status == 413:
        return "llm_body_too_large"
    if field(error, "code") in {"context_length_exceeded"}:
        return "context_limit_exceeded"
    return "llm_invalid_request" if http_status == 400 else "llm_upstream_error"


def provider_error_message(code):
    return {
        "context_limit_exceeded": "Модель отклонила запрос: превышено окно контекста. История сохранена.",
        "llm_rate_limit": "Provider ограничил частоту или объём запросов. Это не доказательство переполнения.",
        "llm_body_too_large": "Provider отклонил размер тела запроса. Это не доказательство переполнения.",
        "llm_invalid_request": "Provider отклонил параметры запроса.",
    }.get(code, "Не удалось получить ответ модели.")
