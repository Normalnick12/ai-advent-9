from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APITimeoutError

from app.models import GenerateRequest, GenerationControls
from app.openai_service import (
    FINISH_INSTRUCTION,
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT_SECONDS,
    OpenAIResponseService,
)


def fake_response(
    *,
    content: str,
    status: str = "completed",
    output_tokens: int = 42,
    incomplete_reason: str | None = None,
):
    return SimpleNamespace(
        _request_id="openai-test-request",
        output_text=content,
        status=status,
        usage=SimpleNamespace(output_tokens=output_tokens),
        incomplete_details=(
            SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None
        ),
        error=None,
    )


@pytest.mark.asyncio
async def test_free_request_has_no_controls() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(return_value=fake_response(content="Свободный ответ"))
        )
    )
    service = OpenAIResponseService(client=client)

    result = await service.generate(GenerateRequest(prompt="Один prompt"))

    kwargs = client.responses.create.await_args.kwargs
    assert kwargs == {"model": "gpt-5.6", "input": "Один prompt"}
    assert result.content == "Свободный ответ"
    assert result.recipe is None
    assert result.output_tokens == 42


@pytest.mark.asyncio
async def test_all_controls_are_applied_independently() -> None:
    recipe_json = (
        '{"recipe_name":"Салат","ingredients":['
        '{"name":"Томат","weight_grams":200,"order":1}],'
        '"steps":[{"order":1,"description":"Нарезать"}]}'
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(return_value=fake_response(content=recipe_json))
        )
    )
    service = OpenAIResponseService(client=client)
    request = GenerateRequest(
        prompt="Один prompt",
        controls=GenerationControls(
            structured_output=True,
            max_output_tokens=600,
            finish_instruction=True,
        ),
    )

    result = await service.generate(request)

    kwargs = client.responses.create.await_args.kwargs
    assert kwargs["input"] == "Один prompt"
    assert kwargs["max_output_tokens"] == 600
    assert kwargs["instructions"] == FINISH_INSTRUCTION
    response_format = kwargs["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert response_format["schema"]["additionalProperties"] is False
    assert (
        response_format["schema"]["properties"]["ingredients"]["items"]
        ["additionalProperties"]
        is False
    )
    assert result.recipe is not None
    assert result.recipe.recipe_name == "Салат"
    assert result.content is None


@pytest.mark.asyncio
async def test_incomplete_response_is_returned_without_parsing_failure() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                return_value=fake_response(
                    content='{"recipe_name":"Оборвано"',
                    status="incomplete",
                    output_tokens=10,
                    incomplete_reason="max_output_tokens",
                )
            )
        )
    )
    service = OpenAIResponseService(client=client)
    request = GenerateRequest(
        prompt="Один prompt",
        controls=GenerationControls(structured_output=True, max_output_tokens=10),
    )

    result = await service.generate(request)

    assert result.status == "incomplete"
    assert result.incomplete_reason == "max_output_tokens"
    assert result.content == '{"recipe_name":"Оборвано"'
    assert result.recipe is None
    assert result.error is None


@pytest.mark.asyncio
async def test_sdk_error_uses_public_error_contract() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("offline")))
    )
    service = OpenAIResponseService(client=client)

    result = await service.generate(GenerateRequest(prompt="Один prompt"))

    assert result.status == "error"
    assert result.error is not None
    assert result.error.code == "RuntimeError"
    assert result.error.message == "offline"


@pytest.mark.asyncio
async def test_openai_timeout_has_a_specific_public_error() -> None:
    timeout = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=timeout))
    )
    service = OpenAIResponseService(client=client)

    result = await service.generate(
        GenerateRequest(prompt="Один prompt"),
        request_id="timeout-test",
    )

    assert result.status == "error"
    assert result.request_id == "timeout-test"
    assert result.error is not None
    assert result.error.code == "openai_timeout"
    assert "request_id" in result.error.message


def test_default_client_has_bounded_timeout_and_retry_budget() -> None:
    with patch("app.openai_service.AsyncOpenAI") as client_class:
        service = OpenAIResponseService()

        service.client

    kwargs = client_class.call_args.kwargs
    assert kwargs["timeout"].connect == 5.0
    assert kwargs["timeout"].read == OPENAI_TIMEOUT_SECONDS
    assert kwargs["max_retries"] == OPENAI_MAX_RETRIES == 1
