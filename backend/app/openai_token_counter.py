import asyncio

import httpx
from openai import AsyncOpenAI, APIStatusError, APITimeoutError, OpenAIError

from app.llm_client import AgentConfig, ConversationMessage
from app.openai_agent_payload import context_payload
from app.token_diagnostics import COUNT_TIMEOUT, CountFailure


class OpenAIInputTokenCounter:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = AsyncOpenAI(timeout=httpx.Timeout(COUNT_TIMEOUT, connect=5), max_retries=0)
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.close()

    async def count(self, messages: tuple[ConversationMessage, ...], config: AgentConfig,
                    *, include_instructions: bool) -> int:
        try:
            raw = await asyncio.wait_for(
                self._get_client().responses.input_tokens.with_raw_response.count(
                    **context_payload(messages, config, include_instructions=include_instructions)),
                timeout=COUNT_TIMEOUT)
            # Inspect JSON before SDK coercion: missing, bool and strings are not counters.
            body = raw.http_response.json()
            value = body.get("input_tokens") if isinstance(body, dict) else None
            if type(value) is not int or value < 0:
                raise CountFailure("count_invalid_response")
            return value
        except (TimeoutError, APITimeoutError) as exc:
            raise CountFailure("count_timeout") from exc
        except APIStatusError as exc:
            code = {429: "count_rate_limit", 413: "count_body_too_large"}.get(
                exc.status_code, "count_provider_error")
            raise CountFailure(code) from exc
        except (OpenAIError, ValueError) as exc:
            raise CountFailure("count_unavailable") from exc
