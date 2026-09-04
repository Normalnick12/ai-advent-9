"""Day 05 contracts; unknown measurements remain nullable."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ErrorInfo


class BenchmarkModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ArithmeticAnswer(BenchmarkModel):
    database_queries: int


class ScheduleAnswer(BenchmarkModel):
    monday: str
    tuesday: str
    wednesday: str
    thursday: str


class FeatureAnswer(BenchmarkModel):
    selected_features: list[str]
    total_cost: int
    total_value: int


class TraceAnswer(BenchmarkModel):
    final_array: list[int]
    checksum: int


class CountAnswer(BenchmarkModel):
    count: int


class BenchmarkAnswer(BenchmarkModel):
    task1: ArithmeticAnswer
    task2: ScheduleAnswer
    task3: FeatureAnswer
    task4: TraceAnswer
    task5: CountAnswer


RoleId = Literal["economical", "balanced", "flagship"]


class ModelSelections(BenchmarkModel):
    economical: str
    balanced: str
    flagship: str


class BenchmarkRunRequest(BenchmarkModel):
    models: ModelSelections


class BenchmarkConfig(BenchmarkModel):
    benchmark_version: str
    prompt: str
    instructions: str
    fingerprint: str
    api: Literal["responses"] = "responses"
    reasoning_effort: Literal["medium"] = "medium"
    max_output_tokens: Literal[6000] = 6000
    temperature: Literal["omitted"] = "omitted"
    top_p: Literal["omitted"] = "omitted"
    strict_output: Literal[True] = True
    output_schema: dict[str, Any]
    max_retries: Literal[0] = 0
    store: Literal[False] = False
    service_tier: Literal["default"] = "default"
    execution: Literal["concurrent"] = "concurrent"
    upstream_timeout_seconds: Literal[240] = 240


class ModelOption(BenchmarkModel):
    id: str
    display_name: str
    tier: str


class RoleOption(BenchmarkModel):
    id: RoleId
    display_name: str
    default_model_id: str
    allowed_model_ids: list[str]


class BenchmarkCatalog(BenchmarkModel):
    benchmark_version: str
    config: BenchmarkConfig
    models: list[ModelOption]
    roles: list[RoleOption]


class Quality(BenchmarkModel):
    correct_count: int = Field(ge=0, le=5)
    total_tasks: Literal[5] = 5


class TaskResult(BenchmarkModel):
    task_id: Literal["task1", "task2", "task3", "task4", "task5"]
    verdict: Literal["correct", "incorrect", "unverified"]
    actual_answer: dict[str, Any] | None = None
    reference_answer: dict[str, Any] | None = None


class BenchmarkUsage(BenchmarkModel):
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class TokenRates(BenchmarkModel):
    input: str
    cached_input: str
    cache_write: str
    output: str


class RequestCost(BenchmarkModel):
    status: Literal["available", "unavailable"] = "unavailable"
    amount_usd: str | None = None
    currency: Literal["USD"] = "USD"
    reason: str | None = None
    pricing_model: str | None = None
    rates: TokenRates | None = None
    source_url: str | None = None
    checked_at: str | None = None
    service_tier: str | None = None
    formula: str = "((I-C-W)*Ri + C*Rc + W*Rw + O*Ro) / 1000000"


class BenchmarkResult(BenchmarkModel):
    role: RoleId
    requested_model: str
    display_name: str
    resolved_model: str | None = None
    status: Literal["completed", "incomplete", "refused", "invalid_response", "timeout", "api_error", "internal_error"]
    response_status: str | None = None
    reason: str | None = None
    error: ErrorInfo | None = None
    quality: Quality | None = None
    tasks: list[TaskResult] = Field(min_length=5, max_length=5)
    raw_output: str | None = None
    latency_ms: int = Field(ge=0)
    api_call_count: int = Field(ge=0, le=1)
    usage: BenchmarkUsage = Field(default_factory=BenchmarkUsage)
    cost: RequestCost = Field(default_factory=RequestCost)


class BenchmarkBatchResponse(BenchmarkModel):
    request_id: str
    config: BenchmarkConfig
    results: list[BenchmarkResult] = Field(min_length=3, max_length=3)
    api_call_count: int = Field(ge=0, le=3)
