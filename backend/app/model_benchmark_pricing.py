"""Backend-controlled models and official standard short-context rates."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.model_benchmark_models import BenchmarkUsage, ModelOption, RequestCost, TokenRates

SOURCE_URL = "https://developers.openai.com/api/docs/pricing"
CHECKED_AT = "2026-09-04"
ROLE_DEFAULTS = {
    "economical": ("Экономичная", "gpt-5.6-luna"),
    "balanced": ("Сбалансированная", "gpt-5.6-terra"),
    "flagship": ("Флагманская", "gpt-5.6-sol"),
}


@dataclass(frozen=True)
class ModelEntry:
    display_name: str
    tier: str
    rates: TokenRates


MODEL_REGISTRY = {
    "gpt-5.6-luna": ModelEntry("GPT-5.6 Luna", "Экономичная", TokenRates(input="0.20", cached_input="0.02", cache_write="0.25", output="1.20")),
    "gpt-5.6-terra": ModelEntry("GPT-5.6 Terra", "Сбалансированная", TokenRates(input="2.00", cached_input="0.20", cache_write="2.50", output="12.00")),
    "gpt-5.6-sol": ModelEntry("GPT-5.6 Sol", "Флагманская", TokenRates(input="4.00", cached_input="0.40", cache_write="5.00", output="20.00")),
}
# Deliberately explicit. A future snapshot needs a verified entry, not prefix matching.
RESOLVED_MODELS = {model_id: model_id for model_id in MODEL_REGISTRY}


class RegistryError(RuntimeError):
    pass


def validate_registry() -> None:
    try:
        for _, model_id in ROLE_DEFAULTS.values():
            if model_id not in MODEL_REGISTRY:
                raise ValueError("Missing default")
        for model_id, entry in MODEL_REGISTRY.items():
            if RESOLVED_MODELS.get(model_id) != model_id:
                raise ValueError("Missing resolution")
            values = [Decimal(value) for value in entry.rates.model_dump().values()]
            if not all(value.is_finite() and value >= 0 for value in values):
                raise ValueError("Invalid rate")
    except (ValueError, InvalidOperation, AttributeError, KeyError) as exc:
        raise RegistryError("Конфигурация моделей или тарифов недоступна.") from exc


def model_options() -> list[ModelOption]:
    validate_registry()
    return [ModelOption(id=key, display_name=value.display_name, tier=value.tier) for key, value in MODEL_REGISTRY.items()]


def calculate_cost(usage: BenchmarkUsage, resolved_model: str | None, service_tier: str | None) -> RequestCost:
    model_id = RESOLVED_MODELS.get(resolved_model)
    entry = MODEL_REGISTRY.get(model_id)
    common = dict(pricing_model=model_id, source_url=SOURCE_URL, checked_at=CHECKED_AT, service_tier=service_tier)
    if entry is None:
        return RequestCost(reason="Тариф фактической модели неизвестен.", **common)
    common["rates"] = entry.rates
    if service_tier != "default":
        return RequestCost(reason="Тариф этого service tier не настроен.", **common)
    i, c, w, o = usage.input_tokens, usage.cached_input_tokens, usage.cache_write_tokens, usage.output_tokens
    if any(value is None for value in (i, c, w, o)):
        return RequestCost(reason="Недостаточно данных usage для расчёта стоимости.", **common)
    if c + w > i:
        return RequestCost(reason="Противоречивые данные cache usage.", **common)
    if i > 272_000:
        return RequestCost(reason="Тариф длинного контекста не настроен.", **common)
    ri, rc, rw, ro = (Decimal(getattr(entry.rates, name)) for name in ("input", "cached_input", "cache_write", "output"))
    amount = ((i - c - w) * ri + c * rc + w * rw + o * ro) / Decimal(1_000_000)
    return RequestCost(status="available", amount_usd=format(amount, "f"), **common)
