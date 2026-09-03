import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APITimeoutError, BadRequestError

from app.temperature_domain import CANONICAL_TEMPERATURE_PROMPT
from app.temperature_models import TemperatureLabRunRequest
from app.temperature_service import (
    FREE_MODE_MESSAGE,
    TEMPERATURE_MAX_OUTPUT_TOKENS,
    TEMPERATURE_OPENAI_MAX_RETRIES,
    TEMPERATURE_OPENAI_TIMEOUT_SECONDS,
    TEMPERATURE_VALUES,
    TemperatureLabService,
    benchmark_json_schema,
    build_response_parameters,
)


def fake_response(payload: object, *, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(
        output_text=payload if isinstance(payload, str) else json.dumps(payload),
        status=status,
        incomplete_details=(SimpleNamespace(reason="max_output_tokens") if status == "incomplete" else None),
        usage=SimpleNamespace(
            input_tokens=20,
            output_tokens=30,
            total_tokens=50,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
    )


def benchmark_payload(prefix: str = "Имя") -> dict[str, object]:
    return {
        "variants": [
            {"name": f"{prefix}{index}", "slogan": "Короткий слоган для разработчика"}
            for index in range(1, 6)
        ]
    }


def client_with_create(create: AsyncMock) -> SimpleNamespace:
    return SimpleNamespace(responses=SimpleNamespace(create=create))


def test_benchmark_schema_fixes_shape_but_not_item_count() -> None:
    schema = benchmark_json_schema()
    variants = schema["properties"]["variants"]
    assert schema["additionalProperties"] is False
    assert variants["items"]["additionalProperties"] is False
    assert variants["items"]["required"] == ["name", "slogan"]
    assert "minItems" not in variants
    assert "maxItems" not in variants
    assert "uniqueItems" not in variants


def test_request_envelopes_only_differ_by_temperature_and_omit_top_p() -> None:
    envelopes = [
        build_response_parameters(
            prompt=CANONICAL_TEMPERATURE_PROMPT,
            mode="benchmark",
            temperature=temperature,
        )
        for temperature in TEMPERATURE_VALUES
    ]
    without_temperature = [
        {key: value for key, value in envelope.items() if key != "temperature"}
        for envelope in envelopes
    ]
    assert without_temperature[0] == without_temperature[1] == without_temperature[2]
    assert [item["temperature"] for item in envelopes] == [0.0, 0.7, 1.2]
    assert envelopes[0]["model"] == "gpt-5.6"
    assert envelopes[0]["reasoning"] == {"effort": "none", "mode": "standard"}
    assert envelopes[0]["max_output_tokens"] == TEMPERATURE_MAX_OUTPUT_TOKENS == 600
    assert envelopes[0]["input"] == CANONICAL_TEMPERATURE_PROMPT
    assert envelopes[0]["store"] is False
    assert envelopes[0]["prompt_cache_options"] == {"mode": "explicit"}
    assert "top_p" not in envelopes[0]
    assert "instructions" not in envelopes[0]
    assert "tools" not in envelopes[0]


@pytest.mark.asyncio
async def test_benchmark_batch_is_concurrent_stable_and_validated() -> None:
    active = 0
    max_active = 0

    async def create_response(**_: object) -> SimpleNamespace:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return fake_response(benchmark_payload())

    create = AsyncMock(side_effect=create_response)
    service = TemperatureLabService(client=client_with_create(create))
    response = await service.run(
        TemperatureLabRunRequest(prompt=CANONICAL_TEMPERATURE_PROMPT),
        "request-benchmark",
    )

    assert max_active == 3
    assert [item.temperature for item in response.results] == [0.0, 0.7, 1.2]
    assert all(item.status == "completed" for item in response.results)
    assert all(item.validation and item.validation.requirements_met == 5 for item in response.results)
    assert all(item.variants and len(item.variants) == 5 for item in response.results)
    assert response.config.output_contract == "strict_variants"


@pytest.mark.asyncio
async def test_free_prompt_is_forwarded_unchanged_and_has_no_validation() -> None:
    prompt = "  Напиши три идеи.\nНе исправляй пробелы.  "
    create = AsyncMock(return_value=fake_response("Свободный ответ"))
    service = TemperatureLabService(client=client_with_create(create))

    response = await service.run(TemperatureLabRunRequest(prompt=prompt), "request-free")

    assert response.mode == "free"
    assert response.mode_message == FREE_MODE_MESSAGE
    assert response.config.output_contract == "text"
    assert all(item.content == "Свободный ответ" for item in response.results)
    assert all(item.variants is None and item.validation is None for item in response.results)
    assert [call.kwargs["input"] for call in create.await_args_list] == [prompt, prompt, prompt]
    assert all(call.kwargs["text"]["format"] == {"type": "text"} for call in create.await_args_list)


@pytest.mark.asyncio
async def test_one_failure_does_not_hide_other_temperature_results() -> None:
    create = AsyncMock(
        side_effect=[
            fake_response(benchmark_payload("Ноль")),
            RuntimeError("secret upstream diagnostic"),
            fake_response(benchmark_payload("Высоко")),
        ]
    )
    service = TemperatureLabService(client=client_with_create(create))
    response = await service.run(
        TemperatureLabRunRequest(prompt=CANONICAL_TEMPERATURE_PROMPT),
        "request-partial",
    )

    assert [item.status for item in response.results] == ["completed", "error", "completed"]
    assert response.results[1].validation is None
    assert response.results[1].error is not None
    assert response.results[1].error.code == "openai_upstream_error"
    assert "secret upstream diagnostic" not in response.model_dump_json()


def test_default_client_has_fixed_timeout_and_zero_retries() -> None:
    with patch("app.temperature_service.AsyncOpenAI") as client_class:
        service = TemperatureLabService()
        service.client

    kwargs = client_class.call_args.kwargs
    assert kwargs["timeout"].connect == 5.0
    assert kwargs["timeout"].read == TEMPERATURE_OPENAI_TIMEOUT_SECONDS == 75.0
    assert kwargs["max_retries"] == TEMPERATURE_OPENAI_MAX_RETRIES == 0


@pytest.mark.asyncio
async def test_incomplete_parse_timeout_and_bad_request_are_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    timeout = APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    http_response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
    )
    bad_request = BadRequestError(
        "Error code: 400",
        response=http_response,
        body={"error": {"message": "bad sk-test-secret", "param": "temperature", "code": "invalid"}},
    )
    cases = [
        (fake_response("truncated", status="incomplete"), "openai_incomplete", "incomplete"),
        (fake_response("not-json"), "response_parse_error", "error"),
        (timeout, "openai_timeout", "error"),
        (bad_request, "openai_bad_request", "error"),
    ]
    for value, expected_code, expected_status in cases:
        create = AsyncMock(side_effect=value) if isinstance(value, BaseException) else AsyncMock(return_value=value)
        service = TemperatureLabService(client=client_with_create(create))
        result = await service.run_temperature(
            prompt=CANONICAL_TEMPERATURE_PROMPT,
            mode="benchmark",
            temperature=0.7,
            request_id="safe-request",
        )
        assert result.status == expected_status
        assert result.validation is None
        assert result.error is not None and result.error.code == expected_code
        assert "sk-test-secret" not in result.model_dump_json()

    assert "sk-test-secret" not in caplog.text
