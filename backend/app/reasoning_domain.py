from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Feature:
    id: str
    cost: int
    value: int


@dataclass(frozen=True)
class DomainSolution:
    selected_features: tuple[str, ...]
    total_cost: int
    total_value: int


@dataclass(frozen=True)
class VerificationOutcome:
    correct: bool
    feasible: bool
    optimal: bool
    totals_match: bool
    calculated_cost: int
    calculated_value: int
    violations: tuple[str, ...]


STORY_POINT_LIMIT = 15
FEATURES = (
    Feature("A", cost=4, value=8),
    Feature("B", cost=6, value=11),
    Feature("C", cost=5, value=10),
    Feature("D", cost=3, value=6),
    Feature("E", cost=7, value=13),
    Feature("F", cost=2, value=4),
    Feature("G", cost=4, value=7),
    Feature("H", cost=5, value=8),
)
FEATURE_BY_ID = {feature.id: feature for feature in FEATURES}
CONSTRAINT_DESCRIPTIONS = (
    "B несовместима с E",
    "C допустима только вместе с F",
    "A несовместима с D",
    "G несовместима с H",
)


def render_canonical_task() -> str:
    feature_lines = "\n".join(
        f"- {feature.id}: стоимость {feature.cost}, ценность {feature.value}."
        for feature in FEATURES
    )
    constraint_lines = "\n".join(
        f"- {description}." for description in CONSTRAINT_DESCRIPTIONS
    )
    return (
        "Выберите набор фич с максимальной суммарной ценностью.\n"
        f"Лимит: {STORY_POINT_LIMIT} story points.\n"
        "Фичи:\n"
        f"{feature_lines}\n"
        "Ограничения:\n"
        f"{constraint_lines}\n"
        f"- Суммарная стоимость не должна превышать {STORY_POINT_LIMIT}.\n"
        "Верните выбранные идентификаторы, суммарную стоимость, суммарную "
        "ценность и краткое объяснение."
    )


CANONICAL_TASK = render_canonical_task()


def constraint_violations(selected_features: Iterable[str]) -> tuple[str, ...]:
    selected = set(selected_features)
    violations: list[str] = []
    total_cost = sum(FEATURE_BY_ID[item].cost for item in selected if item in FEATURE_BY_ID)
    if total_cost > STORY_POINT_LIMIT:
        violations.append(
            f"Превышен лимит {STORY_POINT_LIMIT}: рассчитанная стоимость {total_cost}."
        )
    if {"B", "E"} <= selected:
        violations.append("Фичи B и E несовместимы.")
    if "C" in selected and "F" not in selected:
        violations.append("Фича C допустима только вместе с F.")
    if {"A", "D"} <= selected:
        violations.append("Фичи A и D несовместимы.")
    if {"G", "H"} <= selected:
        violations.append("Фичи G и H несовместимы.")
    return tuple(violations)


def solve_exhaustively() -> tuple[DomainSolution, ...]:
    best_value = -1
    best: list[DomainSolution] = []
    feature_ids = tuple(feature.id for feature in FEATURES)
    for mask in range(1 << len(feature_ids)):
        subset = tuple(
            feature_id
            for index, feature_id in enumerate(feature_ids)
            if mask & (1 << index)
        )
        if constraint_violations(subset):
            continue
        total_cost = sum(FEATURE_BY_ID[item].cost for item in subset)
        total_value = sum(FEATURE_BY_ID[item].value for item in subset)
        solution = DomainSolution(subset, total_cost, total_value)
        if total_value > best_value:
            best_value = total_value
            best = [solution]
        elif total_value == best_value:
            best.append(solution)
    return tuple(best)


REFERENCE_SOLUTIONS = solve_exhaustively()
REFERENCE_SOLUTION = REFERENCE_SOLUTIONS[0]


def verify_solution(
    selected_features: Sequence[str],
    reported_cost: int,
    reported_value: int,
) -> VerificationOutcome:
    normalized = tuple(item.upper() for item in selected_features)
    violations: list[str] = []

    if len(set(normalized)) != len(normalized):
        violations.append("Выбранные фичи содержат дубликаты.")

    unknown = sorted({item for item in normalized if item not in FEATURE_BY_ID})
    if unknown:
        violations.append(f"Неизвестные идентификаторы фич: {', '.join(unknown)}.")

    known_unique = tuple(dict.fromkeys(item for item in normalized if item in FEATURE_BY_ID))
    calculated_cost = sum(FEATURE_BY_ID[item].cost for item in known_unique)
    calculated_value = sum(FEATURE_BY_ID[item].value for item in known_unique)
    violations.extend(constraint_violations(known_unique))

    totals_match = True
    if reported_cost != calculated_cost:
        totals_match = False
        violations.append(
            "Заявленная стоимость не совпадает с рассчитанной: "
            f"{reported_cost} != {calculated_cost}."
        )
    if reported_value != calculated_value:
        totals_match = False
        violations.append(
            "Заявленная ценность не совпадает с рассчитанной: "
            f"{reported_value} != {calculated_value}."
        )

    feasible = not any(
        message
        for message in violations
        if not message.startswith("Заявленная")
    )
    optimal = feasible and calculated_value == REFERENCE_SOLUTION.total_value
    if feasible and not optimal:
        violations.append(
            "Решение допустимо, но не оптимально: "
            f"ценность {calculated_value} вместо {REFERENCE_SOLUTION.total_value}."
        )

    return VerificationOutcome(
        correct=feasible and optimal and totals_match,
        feasible=feasible,
        optimal=optimal,
        totals_match=totals_match,
        calculated_cost=calculated_cost,
        calculated_value=calculated_value,
        violations=tuple(violations),
    )
