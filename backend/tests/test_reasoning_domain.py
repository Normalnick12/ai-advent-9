import pytest

from app.reasoning_domain import (
    CANONICAL_TASK,
    CONSTRAINT_DESCRIPTIONS,
    FEATURES,
    REFERENCE_SOLUTIONS,
    STORY_POINT_LIMIT,
    solve_exhaustively,
    verify_solution,
)


def test_canonical_benchmark_contains_all_fixed_data() -> None:
    assert len(FEATURES) == 8
    assert len(CONSTRAINT_DESCRIPTIONS) == 4
    assert STORY_POINT_LIMIT == 15
    for feature in FEATURES:
        assert feature.id in CANONICAL_TASK
        assert str(feature.cost) in CANONICAL_TASK
        assert str(feature.value) in CANONICAL_TASK
    for constraint in CONSTRAINT_DESCRIPTIONS:
        assert constraint in CANONICAL_TASK


def test_exhaustive_solver_finds_unique_reference_optimum() -> None:
    assert solve_exhaustively() == REFERENCE_SOLUTIONS
    assert len(REFERENCE_SOLUTIONS) == 1
    optimum = REFERENCE_SOLUTIONS[0]
    assert optimum.selected_features == ("A", "C", "F", "G")
    assert optimum.total_cost == 15
    assert optimum.total_value == 29


@pytest.mark.parametrize(
    ("selected", "cost", "value", "reason"),
    [
        (["B", "E"], 13, 24, "B и E"),
        (["C"], 5, 10, "только вместе с F"),
        (["A", "D"], 7, 14, "A и D"),
        (["G", "H"], 9, 15, "G и H"),
        (["A", "B", "C", "F"], 17, 33, "Превышен лимит"),
    ],
)
def test_verifier_covers_every_constraint(
    selected: list[str], cost: int, value: int, reason: str
) -> None:
    result = verify_solution(selected, cost, value)
    assert result.correct is False
    assert any(reason in violation for violation in result.violations)


def test_verifier_accepts_normalized_unique_optimum() -> None:
    result = verify_solution(["g", "a", "f", "c"], 15, 29)
    assert result.correct is True
    assert result.violations == ()


@pytest.mark.parametrize(
    ("selected", "cost", "value", "reason"),
    [
        (["A"], 4, 8, "не оптимально"),
        (["A", "A"], 4, 8, "дубликаты"),
        (["A", "Z"], 4, 8, "Неизвестные"),
        (["A", "C", "F", "G"], 14, 29, "стоимость"),
        (["A", "C", "F", "G"], 15, 28, "ценность"),
    ],
)
def test_verifier_rejects_invalid_or_inconsistent_answers(
    selected: list[str], cost: int, value: int, reason: str
) -> None:
    result = verify_solution(selected, cost, value)
    assert result.correct is False
    assert any(reason in violation for violation in result.violations)
