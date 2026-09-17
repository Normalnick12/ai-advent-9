"""Typed coding decisions and predicates. No provider/parser, store, UI or lab dependency."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.invariants import RuleRef, RuleSource, InvariantViolation, ValidationResult, assessment

Architecture = Literal["MVI", "MVVM"]
Toolkit = Literal["Compose", "Views"]
AsyncModel = Literal["CoroutinesFlow", "RxJava"]


class CodingModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class CodingPolicy(CodingModel):
    required_architecture: Architecture = "MVI"
    required_ui_toolkit: Toolkit = "Compose"
    required_async_model: AsyncModel = "CoroutinesFlow"
    payment_confirmation_required: bool = True


class CodingProposal(CodingModel):
    architecture: Architecture
    ui_toolkit: Toolkit
    async_model: AsyncModel
    payment_confirmation_required: bool
    retry_mode: Literal["manual", "bounded_backoff"]


class CodingIntent(CodingModel):
    architecture: Architecture | None = None
    ui_toolkit: Toolkit | None = None
    async_model: AsyncModel | None = None
    payment_confirmation_required: bool | None = None


class CodingConfigurationError(Exception):
    pass


def rule_refs(policy: CodingPolicy, source: RuleSource) -> tuple[RuleRef, ...]:
    confirmation = "обязательно" if policy.payment_confirmation_required else "не требуется"
    return (
        RuleRef("coding.architecture", source, f"Архитектура: {policy.required_architecture}."),
        RuleRef("coding.ui_toolkit", source, f"UI: {policy.required_ui_toolkit}."),
        RuleRef("coding.async_model", source, f"Async: {policy.required_async_model}."),
        RuleRef("coding.payment_confirmation", source, f"Подтверждение оплаты {confirmation}."),
    )


def check_consistency(policy: CodingPolicy, current_architecture: str | None) -> None:
    if current_architecture != policy.required_architecture:
        raise CodingConfigurationError


def _check(policy: CodingPolicy, value: CodingIntent | CodingProposal,
           rules: tuple[RuleRef, ...], stage: Literal["request", "candidate"]) -> ValidationResult:
    # These are four concrete predicates, not interpreted field/operator definitions.
    violations = []
    if value.architecture is not None and value.architecture != policy.required_architecture:
        violations.append(InvariantViolation(rules[0], stage, "architecture_mismatch",
                                            value.architecture, policy.required_architecture))
    if value.ui_toolkit is not None and value.ui_toolkit != policy.required_ui_toolkit:
        violations.append(InvariantViolation(rules[1], stage, "toolkit_mismatch",
                                            value.ui_toolkit, policy.required_ui_toolkit))
    if value.async_model is not None and value.async_model != policy.required_async_model:
        violations.append(InvariantViolation(rules[2], stage, "async_mismatch",
                                            value.async_model, policy.required_async_model))
    if (value.payment_confirmation_required is not None
            and value.payment_confirmation_required != policy.payment_confirmation_required):
        violations.append(InvariantViolation(rules[3], stage, "confirmation_mismatch",
                                            value.payment_confirmation_required, policy.payment_confirmation_required))
    return assessment(rules, tuple(violations))


def check_request(policy: CodingPolicy, intent: CodingIntent, source: RuleSource) -> ValidationResult:
    return _check(policy, intent, rule_refs(policy, source), "request")


def check_candidate(policy: CodingPolicy, candidate: CodingProposal, source: RuleSource) -> ValidationResult:
    return _check(policy, candidate, rule_refs(policy, source), "candidate")


def render_guidance(policy: CodingPolicy, source: RuleSource) -> str:
    return ("ACTIVE_INVARIANTS\nMandatory proposal constraints. Profile preferences apply within these constraints.\n"
            + "\n".join("- " + r.description for r in rule_refs(policy, source)))


def render_answer(candidate: CodingProposal) -> str:
    retry = {"manual": "После ошибки загрузки показать кнопку «Повторить»; нажатие снова запускает загрузку.",
             "bounded_backoff": "Повторить только загрузку не более трёх раз с задержками 1, 2 и 4 секунды; затем показать ошибку и кнопку «Повторить»."}[candidate.retry_mode]
    confirmation = "обязательно" if candidate.payment_confirmation_required else "не требуется"
    return ("## Вывод\nПредложение прошло проверку заданных ограничений.\n\n"
            f"- {retry}\n"
            f"- Архитектура {candidate.architecture}, UI {candidate.ui_toolkit}, async {candidate.async_model}; состояния loading/error/success.\n"
            f"- Подтверждение оплаты {confirmation}. Retry загрузки не выполняет оплату.")


def render_refusal(policy: CodingPolicy, source: RuleSource, result: ValidationResult,
                   origin: Literal["request", "candidate"]) -> str:
    trusted = {r.rule_id: r for r in rule_refs(policy, source)}
    result.require_complete(tuple(trusted.values()))
    if result.status != "violated" or any(v.stage != origin for v in result.violations):
        raise ValueError("invalid refusal assessment")
    title = ("Запрошенные изменения нельзя принять в этой задаче." if origin == "request"
             else "Полученный вариант не прошёл проверку обязательных ограничений.")
    # Never interpolate candidate prose or even diagnostic attempted values.
    descriptions = " ".join(trusted[v.rule.rule_id].description for v in result.violations)
    return (f"{title}\n\nДействуют ограничения: {descriptions}\n\n"
            "Можно предложить повтор загрузки Checkout с сохранением этих ограничений.")
