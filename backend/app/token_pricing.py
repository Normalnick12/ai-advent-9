from dataclasses import dataclass
from decimal import Decimal

from app.llm_client import LlmResult


@dataclass(frozen=True)
class EstimatedCost:
    status: str = "unavailable"
    amount_usd: str | None = None
    reason: str | None = None
    pricing_date: str = "2026-09-09"
    source: str = "https://developers.openai.com/api/docs/models/gpt-4o-mini"
    input_rate: str = "0.15"
    cached_input_rate: str = "0.075"
    output_rate: str = "0.60"


def estimate_turn_cost(result: LlmResult) -> EstimatedCost:
    if result.resolved_model not in {"gpt-4o-mini", "gpt-4o-mini-2024-07-18"}:
        return EstimatedCost(reason="unknown_model")
    if result.actual_service_tier != "default":
        return EstimatedCost(reason="unknown_tier")
    u = result.usage
    if u is None:
        return EstimatedCost(reason="usage_unavailable")
    values = (u.input_tokens, u.cached_input_tokens, u.output_tokens,
              u.cache_write_tokens, u.reasoning_tokens, u.total_tokens)
    if u.invalid_fields or any(v is not None and (type(v) is not int or v < 0) for v in values):
        return EstimatedCost(reason="invalid_usage")
    i, c, o, w, r, total = values
    if i is None or c is None or o is None:
        return EstimatedCost(reason="usage_unavailable")
    if c > i or (w is not None and c+w > i) or (r is not None and r > o) or (
            total is not None and total != i+o):
        return EstimatedCost(reason="inconsistent_usage")
    amount = (Decimal(i-c)*Decimal("0.15")+Decimal(c)*Decimal("0.075")+
              Decimal(o)*Decimal("0.60"))/Decimal(1000000)
    return EstimatedCost(status="available", amount_usd=format(amount, "f"))
