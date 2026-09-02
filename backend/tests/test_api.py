import logging
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, get_openai_service, get_reasoning_lab_service
from app.models import AppliedControls, ErrorInfo, GenerateResponse
from app.reasoning_models import (
    ExperimentConfig,
    OptimizationSolution,
    ReasoningLabBatchResponse,
    StrategyId,
    StrategyResult,
    TokenUsage,
    VerificationDetails,
)


@pytest.mark.asyncio
async def test_generate_endpoint_contract() -> None:
    service = AsyncMock()
    service.generate.return_value = GenerateResponse(
        content="Обычный текст",
        status="completed",
        output_tokens=15,
        controls=AppliedControls(
            structured_output=False,
            max_output_tokens=None,
            finish_instruction=False,
        ),
    )
    app.dependency_overrides[get_openai_service] = lambda: service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/generate",
                json={"prompt": "Один prompt", "controls": {}},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content"] == "Обычный текст"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    service.generate.assert_awaited_once()


def reasoning_batch_response(*, partial_failure: bool) -> ReasoningLabBatchResponse:
    solution = OptimizationSolution(
        selected_features=["A", "C", "F", "G"],
        total_cost=15,
        total_value=29,
        explanation="Проверено.",
    )
    usage = TokenUsage(
        input_tokens=10,
        output_tokens=8,
        reasoning_tokens=3,
        total_tokens=18,
    )
    verification = VerificationDetails(
        feasible=True,
        optimal=True,
        totals_match=True,
        calculated_cost=15,
        calculated_value=29,
        violations=[],
    )
    results = [
        StrategyResult(
            strategy=strategy,
            display_name=display_name,
            correct=not (partial_failure and strategy is StrategyId.STEP_BY_STEP),
            latency_ms=100,
            usage=usage,
            api_call_count=2 if strategy is StrategyId.META_PROMPT else 1,
            solution=(
                None
                if partial_failure and strategy is StrategyId.STEP_BY_STEP
                else solution
            ),
            verification=(
                VerificationDetails(
                    feasible=False,
                    optimal=False,
                    totals_match=False,
                    calculated_cost=0,
                    calculated_value=0,
                    violations=["OpenAI временно недоступен."],
                )
                if partial_failure and strategy is StrategyId.STEP_BY_STEP
                else verification
            ),
            error=(
                ErrorInfo(
                    code="openai_upstream_error",
                    message="OpenAI временно недоступен.",
                )
                if partial_failure and strategy is StrategyId.STEP_BY_STEP
                else None
            ),
            generated_prompt=(
                "Уникальный сгенерированный промпт."
                if strategy is StrategyId.META_PROMPT
                else None
            ),
        )
        for strategy, display_name in [
            (StrategyId.DIRECT, "Прямой ответ"),
            (StrategyId.STEP_BY_STEP, "Пошаговое решение"),
            (StrategyId.META_PROMPT, "Мета-промпт"),
            (StrategyId.EXPERT_PANEL, "Группа экспертов"),
        ]
    ]
    return ReasoningLabBatchResponse(
        request_id="service-placeholder",
        config=ExperimentConfig(),
        reference_solution=solution,
        results=results,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("partial_failure", [False, True])
async def test_reasoning_lab_endpoint_contract(partial_failure: bool) -> None:
    service = AsyncMock()
    service.run.return_value = reasoning_batch_response(
        partial_failure=partial_failure
    )
    app.dependency_overrides[get_reasoning_lab_service] = lambda: service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/reasoning-lab/run", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == response.headers["X-Request-ID"]
    assert [item["strategy"] for item in payload["results"]] == [
        "DIRECT",
        "STEP_BY_STEP",
        "META_PROMPT",
        "EXPERT_PANEL",
    ]
    assert payload["results"][2]["api_call_count"] == 2
    if partial_failure:
        assert payload["results"][1]["correct"] is False
        assert payload["results"][1]["error"]["code"] == "openai_upstream_error"
        assert payload["results"][0]["correct"] is True
    service.run.assert_awaited_once_with(request_id=payload["request_id"])


@pytest.mark.asyncio
async def test_reasoning_lab_batch_logs_are_prompt_free(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AsyncMock()
    service.run.return_value = reasoning_batch_response(partial_failure=False)
    app.dependency_overrides[get_reasoning_lab_service] = lambda: service
    try:
        with caplog.at_level(logging.INFO, logger="uvicorn.error"):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post("/api/v1/reasoning-lab/run", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] in caplog.text
    assert "reasoning_batch_started" in caplog.text
    assert "reasoning_batch_finished" in caplog.text
    assert "Уникальный сгенерированный промпт." not in caplog.text
    assert "Выберите набор фич" not in caplog.text


@pytest.mark.asyncio
async def test_reasoning_lab_request_rejects_configurable_fields() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/reasoning-lab/run",
            json={"model": "other"},
        )

    assert response.status_code == 422
