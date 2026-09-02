import pytest
from pydantic import ValidationError

from app.reasoning_models import (
    ExperimentConfig,
    OptimizationSolution,
    ReasoningLabBatchResponse,
    ReasoningLabRunRequest,
    StrategyId,
    StrategyResult,
    TokenUsage,
    VerificationDetails,
)


def test_empty_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ReasoningLabRunRequest.model_validate({"prompt": "not configurable"})


def test_response_models_are_strict_and_serialize_metrics() -> None:
    solution = OptimizationSolution(
        selected_features=["A", "C", "F", "G"],
        total_cost=15,
        total_value=29,
        explanation="Полный перебор.",
    )
    result = StrategyResult(
        strategy=StrategyId.DIRECT,
        display_name="Прямой ответ",
        correct=True,
        latency_ms=321,
        usage=TokenUsage(
            input_tokens=10,
            output_tokens=20,
            reasoning_tokens=7,
            total_tokens=30,
        ),
        api_call_count=1,
        solution=solution,
        verification=VerificationDetails(
            feasible=True,
            optimal=True,
            totals_match=True,
            calculated_cost=15,
            calculated_value=29,
            violations=[],
        ),
    )
    payload = ReasoningLabBatchResponse(
        request_id="request-1",
        config=ExperimentConfig(),
        reference_solution=solution,
        results=[result],
    ).model_dump(mode="json")

    assert payload["config"] == {
        "model": "gpt-5.6",
        "reasoning_effort": "medium",
        "reasoning_mode": "standard",
        "max_output_tokens": 1200,
        "prompt_cache_mode": "explicit",
        "story_point_limit": 15,
    }
    assert payload["results"][0]["usage"] == {
        "input_tokens": 10,
        "output_tokens": 20,
        "reasoning_tokens": 7,
        "total_tokens": 30,
    }
    assert payload["results"][0]["api_call_count"] == 1

    with pytest.raises(ValidationError):
        StrategyResult.model_validate({**result.model_dump(), "secret": "forbidden"})
