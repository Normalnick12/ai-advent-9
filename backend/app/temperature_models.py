from typing import Literal

from pydantic import Field

from app.models import ErrorInfo, StrictModel
from app.reasoning_models import TokenUsage


class TemperatureLabRunRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=20_000)


class TemperatureExperimentConfig(StrictModel):
    model: Literal["gpt-5.6"] = "gpt-5.6"
    temperatures: list[float] = Field(default_factory=lambda: [0.0, 0.7, 1.2])
    reasoning_effort: Literal["none"] = "none"
    reasoning_mode: Literal["standard"] = "standard"
    max_output_tokens: Literal[600] = 600
    top_p: Literal["default"] = "default"
    prompt_cache_mode: Literal["explicit"] = "explicit"
    output_contract: Literal["strict_variants", "text"]
    temperature_only_variable: Literal[True] = True


class RawVariant(StrictModel):
    name: str
    slogan: str


class RawBenchmarkResponse(StrictModel):
    variants: list[RawVariant]


class TemperatureVariant(StrictModel):
    name: str
    slogan: str
    normalized_name: str


class RequirementCheck(StrictModel):
    id: Literal[
        "exactly_five",
        "name_word_count",
        "unique_names",
        "forbidden_words",
        "slogan_word_count",
    ]
    label: str
    passed: bool


class BenchmarkValidation(StrictModel):
    requirements_met: int = Field(ge=0, le=5)
    total_requirements: Literal[5] = 5
    checks: list[RequirementCheck]


class TemperatureResult(StrictModel):
    temperature: float
    status: Literal["completed", "incomplete", "error"]
    latency_ms: int = Field(ge=0)
    usage: TokenUsage
    variants: list[TemperatureVariant] | None = None
    content: str | None = None
    validation: BenchmarkValidation | None = None
    error: ErrorInfo | None = None


class TemperatureLabBatchResponse(StrictModel):
    request_id: str
    mode: Literal["benchmark", "free"]
    mode_message: str
    config: TemperatureExperimentConfig
    results: list[TemperatureResult]
