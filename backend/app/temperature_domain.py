import re
from dataclasses import dataclass
from typing import Literal, Sequence

CANONICAL_TEMPERATURE_PROMPT = """Придумай ровно 5 названий для мобильного приложения, которое помогает разработчикам готовиться к техническим собеседованиям.

Для каждого названия придумай короткий рекламный слоган.

Требования:

1. Название должно состоять из 1–2 слов.
2. Все 5 названий должны различаться.
3. В названиях нельзя использовать отдельные слова «Interview», «AI» и «ИИ».
4. Каждый слоган должен содержать не более 8 слов.
5. Названия и слоганы должны быть уместны для продукта подготовки разработчиков к техническим собеседованиям.

Не добавляй вступление, заключение или дополнительные комментарии."""

TemperatureMode = Literal["benchmark", "free"]

FORBIDDEN_NAME_WORDS = frozenset(word.casefold() for word in ("Interview", "AI", "ИИ"))


@dataclass(frozen=True)
class VariantInput:
    name: str
    slogan: str


@dataclass(frozen=True)
class CheckOutcome:
    check_id: str
    label: str
    passed: bool


@dataclass(frozen=True)
class ValidationOutcome:
    requirements_met: int
    checks: tuple[CheckOutcome, ...]


def mode_for_prompt(prompt: str) -> TemperatureMode:
    return "benchmark" if prompt == CANONICAL_TEMPERATURE_PROMPT else "free"


def normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def word_count(value: str) -> int:
    return len(value.split())


def contains_forbidden_name_word(value: str) -> bool:
    tokens = re.findall(r"[^\W_]+", value, flags=re.UNICODE)
    return any(token.casefold() in FORBIDDEN_NAME_WORDS for token in tokens)


def validate_variants(variants: Sequence[VariantInput]) -> ValidationOutcome:
    normalized_names = [normalize_name(item.name) for item in variants]
    has_variants = bool(variants)
    checks = (
        CheckOutcome("exactly_five", "Ровно 5 вариантов", len(variants) == 5),
        CheckOutcome(
            "name_word_count",
            "Каждое название состоит из 1–2 слов",
            has_variants and all(1 <= word_count(item.name) <= 2 for item in variants),
        ),
        CheckOutcome(
            "unique_names",
            "Все названия уникальны после нормализации",
            has_variants and len(set(normalized_names)) == len(normalized_names),
        ),
        CheckOutcome(
            "forbidden_words",
            "В названиях нет отдельных слов Interview, AI и ИИ",
            has_variants and all(
                not contains_forbidden_name_word(item.name) for item in variants
            ),
        ),
        CheckOutcome(
            "slogan_word_count",
            "Каждый слоган содержит не более 8 слов",
            has_variants and all(word_count(item.slogan) <= 8 for item in variants),
        ),
    )
    return ValidationOutcome(
        requirements_met=sum(item.passed for item in checks),
        checks=checks,
    )
