import pytest
from pydantic import ValidationError

from app.reasoning_models import TokenUsage
from app.temperature_models import (
    TemperatureExperimentConfig,
    TemperatureLabBatchResponse,
    TemperatureLabRunRequest,
    TemperatureResult,
)


def test_temperature_request_accepts_only_nonempty_prompt() -> None:
    assert TemperatureLabRunRequest(prompt="Тест").prompt == "Тест"
    with pytest.raises(ValidationError):
        TemperatureLabRunRequest(prompt="")
    with pytest.raises(ValidationError):
        TemperatureLabRunRequest.model_validate({"prompt": "Тест", "model": "other"})


def test_config_serializes_fixed_experiment_parameters() -> None:
    payload = TemperatureExperimentConfig(output_contract="strict_variants").model_dump()
    assert payload == {
        "model": "gpt-5.6",
        "temperatures": [0.0, 0.7, 1.2],
        "reasoning_effort": "none",
        "reasoning_mode": "standard",
        "max_output_tokens": 600,
        "top_p": "default",
        "prompt_cache_mode": "explicit",
        "output_contract": "strict_variants",
        "temperature_only_variable": True,
    }


def test_three_result_response_serializes_nullable_benchmark_fields() -> None:
    usage = TokenUsage(input_tokens=1, output_tokens=2, reasoning_tokens=0, total_tokens=3)
    response = TemperatureLabBatchResponse(
        request_id="request",
        mode="free",
        mode_message="Автопроверка недоступна",
        config=TemperatureExperimentConfig(output_contract="text"),
        results=[
            TemperatureResult(
                temperature=temperature,
                status="completed",
                latency_ms=10,
                usage=usage,
                content="Ответ",
            )
            for temperature in (0.0, 0.7, 1.2)
        ],
    )
    payload = response.model_dump(mode="json")

    assert len(payload["results"]) == 3
    assert all(item["validation"] is None for item in payload["results"])
    assert all(item["variants"] is None for item in payload["results"])
    with pytest.raises(ValidationError):
        TemperatureResult.model_validate({**payload["results"][0], "api_key": "forbidden"})
