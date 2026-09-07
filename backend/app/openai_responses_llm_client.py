import asyncio

import httpx
from openai import AsyncOpenAI, APITimeoutError, OpenAIError

from app.llm_client import AgentConfig, ConversationMessage, LlmResult

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
                    model=config.model,
                    instructions=config.instructions,
                    input=[{"role": item.role, "content": item.content} for item in messages],
                    reasoning={"effort": config.reasoning_effort},
                    max_output_tokens=config.max_output_tokens,
                    text={"format": {"type": "text"}},
                    store=False,
                ),
                timeout=DEADLINE_SECONDS,
            )
        except (TimeoutError, APITimeoutError):
            return failure("llm_timeout", "Модель не ответила вовремя. Попробуйте ещё раз.")
        except OpenAIError:
            return failure("llm_upstream_error", "Не удалось получить ответ модели. Попробуйте ещё раз.")
        return self._normalize(response)

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
