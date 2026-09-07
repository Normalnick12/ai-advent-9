import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from app.llm_client import AgentConfig, ConversationMessage
from app.openai_responses_llm_client import OpenAIResponsesLlmClient


def response(status="completed", text="Ответ", part="output_text", reason=None):
    return NS(status=status, output=[NS(type="message", content=[NS(type=part, text=text)])],
              incomplete_details=NS(reason=reason))


@pytest.mark.asyncio
async def test_exact_payload_lazy_client_and_close():
    sdk = AsyncMock()
    sdk.responses.create.return_value = response()
    with patch("app.openai_responses_llm_client.AsyncOpenAI", return_value=sdk) as factory:
        adapter = OpenAIResponsesLlmClient()
        factory.assert_not_called()
        messages = tuple(ConversationMessage(role, text) for role, text in [("user", "U1"), ("assistant", "A1"), ("user", "U2")])
        for _ in range(2):
            assert (await adapter.complete(messages, AgentConfig())).reply == "Ответ"
        assert factory.call_count == 1
        assert factory.call_args.kwargs["max_retries"] == 0
        timeout = factory.call_args.kwargs["timeout"]
        assert timeout.connect == 5 and timeout.read == timeout.write == timeout.pool == 75
        assert sdk.responses.create.call_args.kwargs == {
            "model": "gpt-5.6", "instructions": AgentConfig().instructions,
            "input": [{"role": m.role, "content": m.content} for m in messages],
            "reasoning": {"effort": "none"}, "max_output_tokens": 1200,
            "text": {"format": {"type": "text"}}, "store": False,
        }
        assert sdk.responses.create.await_count == 2
        await adapter.close()
        sdk.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw,status,code", [
    (response(text=" "), "error", "llm_invalid_response"),
    (NS(status="completed", output=[]), "error", "llm_invalid_response"),
    (response(part="refusal"), "refused", "llm_refused"),
    (response(status="incomplete", reason="secret"), "incomplete", "llm_incomplete"),
    (response(status="failed"), "error", "llm_upstream_error"),
    (response(status="in_progress"), "error", "llm_invalid_response"),
])
async def test_normalization(raw, status, code):
    adapter = OpenAIResponsesLlmClient()
    adapter._client = AsyncMock()
    adapter._client.responses.create.return_value = raw
    result = await adapter.complete((), AgentConfig())
    assert result.status == status and result.error_code == code and result.reply is None
    assert "secret" not in repr(result)
    if status == "incomplete":
        assert result.incomplete_reason == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize("error,code", [
    (APIConnectionError(request=httpx.Request("POST", "https://example.test"), message="private"), "llm_upstream_error"),
    (APITimeoutError(request=httpx.Request("POST", "https://example.test")), "llm_timeout"),
])
async def test_sdk_errors_are_safe_without_retries(error, code):
    adapter = OpenAIResponsesLlmClient()
    adapter._client = AsyncMock()
    adapter._client.responses.create.side_effect = error
    result = await adapter.complete((), AgentConfig())
    assert result.error_code == code and result.reply is None
    assert "private" not in repr(result)
    adapter._client.responses.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_deadline_cancels_upstream():
    cancelled = asyncio.Event()
    async def call(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    adapter = OpenAIResponsesLlmClient()
    adapter._client = AsyncMock()
    adapter._client.responses.create.side_effect = call
    with patch("app.openai_responses_llm_client.DEADLINE_SECONDS", 0.01):
        result = await adapter.complete((), AgentConfig())
    assert result.error_code == "llm_timeout" and cancelled.is_set()
    adapter._client.responses.create.assert_awaited_once()
