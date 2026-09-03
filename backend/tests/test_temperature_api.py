from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, get_temperature_lab_service
from app.models import ErrorInfo
from app.reasoning_models import TokenUsage
from app.temperature_models import (
    BenchmarkValidation,
    RequirementCheck,
    TemperatureExperimentConfig,
    TemperatureLabBatchResponse,
    TemperatureResult,
    TemperatureVariant,
)


def batch_response() -> TemperatureLabBatchResponse:
    checks = [
        RequirementCheck(id="exactly_five", label="Ровно 5 вариантов", passed=True),
        RequirementCheck(id="name_word_count", label="Названия 1–2 слова", passed=True),
        RequirementCheck(id="unique_names", label="Уникальные названия", passed=True),
        RequirementCheck(id="forbidden_words", label="Нет запрещённых слов", passed=True),
        RequirementCheck(id="slogan_word_count", label="Слоганы до 8 слов", passed=True),
    ]
    usage = TokenUsage(input_tokens=10, output_tokens=20, reasoning_tokens=0, total_tokens=30)
    return TemperatureLabBatchResponse(
        request_id="placeholder",
        mode="benchmark",
        mode_message="Benchmark-режим",
        config=TemperatureExperimentConfig(output_contract="strict_variants"),
        results=[
            TemperatureResult(
                temperature=temperature,
                status="completed",
                latency_ms=123,
                usage=usage,
                variants=[TemperatureVariant(name="Код", slogan="Готовься уверенно", normalized_name="код")],
                validation=BenchmarkValidation(requirements_met=5, checks=checks),
            )
            for temperature in (0.0, 0.7, 1.2)
        ],
    )


@pytest.mark.asyncio
async def test_temperature_lab_endpoint_contract() -> None:
    service = AsyncMock()
    service.run.return_value = batch_response()
    app.dependency_overrides[get_temperature_lab_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/temperature-lab/run", json={"prompt": "Тест"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert [item["temperature"] for item in payload["results"]] == [0.0, 0.7, 1.2]
    assert payload["results"][0]["validation"]["requirements_met"] == 5
    service.run.assert_awaited_once()
    assert service.run.await_args.kwargs["request"].prompt == "Тест"
    assert service.run.await_args.kwargs["request_id"] == payload["request_id"]


@pytest.mark.asyncio
async def test_temperature_lab_rejects_empty_or_configurable_request() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        empty = await client.post("/api/v1/temperature-lab/run", json={"prompt": ""})
        extra = await client.post(
            "/api/v1/temperature-lab/run",
            json={"prompt": "Тест", "temperature": 0.5},
        )

    assert empty.status_code == 422
    assert extra.status_code == 422


@pytest.mark.asyncio
async def test_temperature_lab_endpoint_preserves_free_and_partial_contracts() -> None:
    response_model = batch_response().model_copy(
        update={
            "mode": "free",
            "mode_message": "Автопроверка benchmark недоступна для произвольного запроса.",
            "config": TemperatureExperimentConfig(output_contract="text"),
            "results": [
                item.model_copy(
                    update=(
                        {
                            "status": "error",
                            "variants": None,
                            "validation": None,
                            "content": None,
                            "error": ErrorInfo(code="openai_upstream_error", message="OpenAI недоступен."),
                        }
                        if index == 1
                        else {"variants": None, "validation": None, "content": "Ответ"}
                    )
                )
                for index, item in enumerate(batch_response().results)
            ],
        }
    )
    service = AsyncMock()
    service.run.return_value = response_model
    app.dependency_overrides[get_temperature_lab_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/temperature-lab/run", json={"prompt": "Свободный"})
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert payload["mode"] == "free"
    assert payload["config"] == {
        "model": "gpt-5.6",
        "temperatures": [0.0, 0.7, 1.2],
        "reasoning_effort": "none",
        "reasoning_mode": "standard",
        "max_output_tokens": 600,
        "top_p": "default",
        "prompt_cache_mode": "explicit",
        "output_contract": "text",
        "temperature_only_variable": True,
    }
    assert all(item["validation"] is None for item in payload["results"])
    assert [item["status"] for item in payload["results"]] == [
        "completed",
        "error",
        "completed",
    ]
    assert payload["results"][1]["error"]["code"] == "openai_upstream_error"
    assert "accuracy" not in response.text.lower()
    assert "creativity" not in response.text.lower()
