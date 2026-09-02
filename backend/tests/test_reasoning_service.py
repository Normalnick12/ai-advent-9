import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APITimeoutError, BadRequestError

from app.reasoning_domain import CANONICAL_TASK
from app.reasoning_models import StrategyId
from app.reasoning_service import (
    EXPERT_PANEL_INSTRUCTION,
    META_PROMPT_INSTRUCTION,
    REASONING_MAX_OUTPUT_TOKENS,
    REASONING_OPENAI_MAX_RETRIES,
    REASONING_OPENAI_TIMEOUT_SECONDS,
    STEP_BY_STEP_INSTRUCTION,
    ReasoningLabService,
)


def fake_response(
    payload: dict[str, object] | str,
    *,
    status: str = "completed",
    input_tokens: int = 11,
    output_tokens: int = 7,
    reasoning_tokens: int = 3,
    incomplete_reason: str | None = None,
) -> SimpleNamespace:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        output_text=text,
        status=status,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            output_tokens_details=SimpleNamespace(
                reasoning_tokens=reasoning_tokens,
            ),
            total_tokens=input_tokens + output_tokens,
        ),
        incomplete_details=(
            SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None
        ),
    )


def optimal_response(**kwargs: object) -> SimpleNamespace:
    return fake_response(
        {
            "selected_features": ["A", "C", "F", "G"],
            "total_cost": 15,
            "total_value": 29,
            "explanation": "Проверены все ограничения.",
        },
        **kwargs,
    )


def client_with_create(create: AsyncMock) -> SimpleNamespace:
    return SimpleNamespace(responses=SimpleNamespace(create=create))


def assert_fixed_envelope(kwargs: dict[str, object]) -> None:
    assert kwargs["model"] == "gpt-5.6"
    assert kwargs["reasoning"] == {"effort": "medium", "mode": "standard"}
    assert kwargs["max_output_tokens"] == REASONING_MAX_OUTPUT_TOKENS == 1200
    assert kwargs["store"] is False
    assert kwargs["prompt_cache_options"] == {"mode": "explicit"}
    assert kwargs["input"] == CANONICAL_TASK
    assert "previous_response_id" not in kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy", "expected_instruction"),
    [
        (StrategyId.DIRECT, None),
        (StrategyId.STEP_BY_STEP, STEP_BY_STEP_INSTRUCTION),
        (StrategyId.EXPERT_PANEL, EXPERT_PANEL_INSTRUCTION),
    ],
)
async def test_single_call_strategies_only_vary_instruction(
    strategy: StrategyId,
    expected_instruction: str | None,
) -> None:
    create = AsyncMock(return_value=optimal_response())
    service = ReasoningLabService(client=client_with_create(create))

    result = await service.run_strategy(strategy, "request-1")

    assert result.correct is True
    assert result.api_call_count == 1
    kwargs = create.await_args.kwargs
    assert_fixed_envelope(kwargs)
    assert kwargs["text"]["format"]["name"] == "optimization_solution"
    assert kwargs["text"]["format"]["strict"] is True
    assert kwargs["text"]["format"]["schema"]["additionalProperties"] is False
    assert "uniqueItems" not in kwargs["text"]["format"]["schema"][
        "properties"
    ]["selected_features"]
    if expected_instruction is None:
        assert "instructions" not in kwargs
    else:
        assert kwargs["instructions"] == expected_instruction


@pytest.mark.asyncio
async def test_meta_prompt_uses_two_independent_fixed_envelope_calls() -> None:
    generated = "Сначала перечисли допустимые множества, затем проверь максимум."
    create = AsyncMock(
        side_effect=[
            fake_response(
                {"generated_prompt": generated},
                input_tokens=5,
                output_tokens=4,
                reasoning_tokens=2,
            ),
            optimal_response(
                input_tokens=13,
                output_tokens=9,
                reasoning_tokens=5,
            ),
        ]
    )
    service = ReasoningLabService(client=client_with_create(create))

    result = await service.run_strategy(StrategyId.META_PROMPT, "request-meta")

    assert result.correct is True
    assert result.api_call_count == 2
    assert result.generated_prompt == generated
    assert result.usage.input_tokens == 18
    assert result.usage.output_tokens == 13
    assert result.usage.reasoning_tokens == 7
    assert result.usage.total_tokens == 31

    first, second = [call.kwargs for call in create.await_args_list]
    assert_fixed_envelope(first)
    assert_fixed_envelope(second)
    assert first["instructions"] == META_PROMPT_INSTRUCTION
    assert first["text"]["format"]["name"] == "generated_meta_prompt"
    assert second["instructions"] == generated
    assert second["text"]["format"]["name"] == "optimization_solution"
    assert first["input"] == second["input"] == CANONICAL_TASK


@pytest.mark.asyncio
async def test_completed_suboptimal_result_includes_usage_and_verification() -> None:
    create = AsyncMock(
        return_value=fake_response(
            {
                "selected_features": ["A"],
                "total_cost": 4,
                "total_value": 8,
                "explanation": "Выбрана A.",
            }
        )
    )
    service = ReasoningLabService(client=client_with_create(create))

    result = await service.run_strategy(StrategyId.DIRECT, "request-suboptimal")

    assert result.correct is False
    assert result.solution is not None
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert result.usage.reasoning_tokens == 3
    assert any("не оптимально" in item for item in result.verification.violations)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (
            fake_response(
                '{"selected_features":',
                status="incomplete",
                incomplete_reason="max_output_tokens",
            ),
            "openai_incomplete",
        ),
        (fake_response("not-json"), "structured_output_parse_error"),
    ],
)
async def test_incomplete_and_parse_errors_are_isolated(
    response: SimpleNamespace,
    expected_code: str,
) -> None:
    service = ReasoningLabService(
        client=client_with_create(AsyncMock(return_value=response))
    )

    result = await service.run_strategy(StrategyId.DIRECT, "request-error")

    assert result.correct is False
    assert result.error is not None
    assert result.error.code == expected_code
    assert result.api_call_count == 1
    assert CANONICAL_TASK not in result.error.message


@pytest.mark.asyncio
async def test_timeout_and_upstream_errors_are_prompt_and_secret_free() -> None:
    timeout = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    timeout_service = ReasoningLabService(
        client=client_with_create(AsyncMock(side_effect=timeout))
    )
    upstream_service = ReasoningLabService(
        client=client_with_create(
            AsyncMock(
                side_effect=RuntimeError(
                    f"secret-key-value and canonical prompt: {CANONICAL_TASK}"
                )
            )
        )
    )

    timeout_result = await timeout_service.run_strategy(
        StrategyId.DIRECT, "request-timeout"
    )
    upstream_result = await upstream_service.run_strategy(
        StrategyId.DIRECT, "request-upstream"
    )

    assert timeout_result.error is not None
    assert timeout_result.error.code == "openai_timeout"
    assert upstream_result.error is not None
    assert upstream_result.error.code == "openai_upstream_error"
    serialized = upstream_result.model_dump_json()
    assert "secret-key-value" not in serialized
    assert CANONICAL_TASK not in serialized


@pytest.mark.asyncio
async def test_bad_request_logs_safe_upstream_details_and_returns_safe_contract(
    caplog: pytest.LogCaptureFixture,
) -> None:
    upstream_message = (
        "Invalid schema for response_format 'optimization_solution': In "
        "context=('properties', 'selected_features'), 'uniqueItems' is not "
        "permitted. diagnostic=sk-test-secret-12345678"
    )
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
    )
    bad_request = BadRequestError(
        "Error code: 400",
        response=response,
        body={
            "error": {
                "message": upstream_message,
                "type": "invalid_request_error",
                "param": "text.format.schema",
                "code": "invalid_json_schema",
            }
        },
    )
    service = ReasoningLabService(
        client=client_with_create(AsyncMock(side_effect=bad_request))
    )

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        result = await service.run_strategy(StrategyId.DIRECT, "bad-request-id")

    assert result.error is not None
    assert result.error.code == "openai_bad_request"
    assert "Invalid schema" not in result.model_dump_json()
    assert "bad-request-id" in caplog.text
    assert "status_code=400" in caplog.text
    assert "error_code=invalid_json_schema" in caplog.text
    assert "error_param=text.format.schema" in caplog.text
    assert "'uniqueItems' is not permitted" in caplog.text
    assert "sk-test-secret-12345678" not in caplog.text
    assert "[REDACTED]" in caplog.text


@pytest.mark.asyncio
async def test_batch_is_concurrent_stable_and_preserves_partial_results() -> None:
    active = 0
    max_active = 0

    async def create_response(**kwargs: object) -> SimpleNamespace:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        if kwargs.get("instructions") == STEP_BY_STEP_INSTRUCTION:
            raise RuntimeError("one strategy failed")
        if kwargs["text"]["format"]["name"] == "generated_meta_prompt":
            return fake_response({"generated_prompt": "Проверь полный перебор."})
        return optimal_response()

    service = ReasoningLabService(
        client=client_with_create(AsyncMock(side_effect=create_response))
    )

    response = await service.run("batch-request")

    assert [item.strategy for item in response.results] == [
        StrategyId.DIRECT,
        StrategyId.STEP_BY_STEP,
        StrategyId.META_PROMPT,
        StrategyId.EXPERT_PANEL,
    ]
    assert max_active >= 2
    assert response.results[1].correct is False
    assert response.results[1].error is not None
    assert response.results[1].error.code == "openai_upstream_error"
    assert [item.correct for item in response.results] == [True, False, True, True]
    assert response.results[2].api_call_count == 2


@pytest.mark.asyncio
async def test_structured_logs_do_not_contain_prompt_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    generated = "Уникальный сгенерированный текст."
    create = AsyncMock(
        side_effect=[
            fake_response({"generated_prompt": generated}),
            optimal_response(),
        ]
    )
    service = ReasoningLabService(client=client_with_create(create))

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        await service.run_strategy(StrategyId.META_PROMPT, "safe-request-id")

    logs = caplog.text
    assert "safe-request-id" in logs
    assert "META_PROMPT" in logs
    assert CANONICAL_TASK not in logs
    assert generated not in logs


def test_default_client_has_fixed_timeout_and_zero_retries() -> None:
    with patch("app.reasoning_service.AsyncOpenAI") as client_class:
        service = ReasoningLabService()

        service.client

    kwargs = client_class.call_args.kwargs
    assert kwargs["timeout"].connect == 5.0
    assert kwargs["timeout"].read == REASONING_OPENAI_TIMEOUT_SECONDS == 75.0
    assert kwargs["max_retries"] == REASONING_OPENAI_MAX_RETRIES == 0
