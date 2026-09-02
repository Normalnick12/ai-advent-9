from enum import Enum
from typing import Literal

from pydantic import Field

from app.models import ErrorInfo, StrictModel


class StrategyId(str, Enum):
    DIRECT = "DIRECT"
    STEP_BY_STEP = "STEP_BY_STEP"
    META_PROMPT = "META_PROMPT"
    EXPERT_PANEL = "EXPERT_PANEL"


STRATEGY_DISPLAY_NAMES = {
    StrategyId.DIRECT: "Прямой ответ",
    StrategyId.STEP_BY_STEP: "Пошаговое решение",
    StrategyId.META_PROMPT: "Мета-промпт",
    StrategyId.EXPERT_PANEL: "Группа экспертов",
}


class ReasoningLabRunRequest(StrictModel):
    pass


class ExperimentConfig(StrictModel):
    model: Literal["gpt-5.6"] = "gpt-5.6"
    reasoning_effort: Literal["medium"] = "medium"
    reasoning_mode: Literal["standard"] = "standard"
    max_output_tokens: Literal[1200] = 1200
    prompt_cache_mode: Literal["explicit"] = "explicit"
    story_point_limit: Literal[15] = 15


class OptimizationSolution(StrictModel):
    selected_features: list[Literal["A", "B", "C", "D", "E", "F", "G", "H"]]
    total_cost: int
    total_value: int
    explanation: str = Field(min_length=1)


class VerificationDetails(StrictModel):
    feasible: bool
    optimal: bool
    totals_match: bool
    calculated_cost: int
    calculated_value: int
    violations: list[str]


class TokenUsage(StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class StrategyResult(StrictModel):
    strategy: StrategyId
    display_name: str
    correct: bool
    latency_ms: int = Field(ge=0)
    usage: TokenUsage
    api_call_count: int = Field(ge=0)
    solution: OptimizationSolution | None = None
    verification: VerificationDetails
    error: ErrorInfo | None = None
    generated_prompt: str | None = None


class ReasoningLabBatchResponse(StrictModel):
    request_id: str
    config: ExperimentConfig
    reference_solution: OptimizationSolution
    results: list[StrategyResult]
