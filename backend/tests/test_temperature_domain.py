from app.temperature_domain import (
    CANONICAL_TEMPERATURE_PROMPT,
    VariantInput,
    mode_for_prompt,
    normalize_name,
    validate_variants,
)


def valid_variants() -> list[VariantInput]:
    return [
        VariantInput("Код Старт", "Тренируйся и проходи технические интервью уверенно"),
        VariantInput("АлгоШаг", "Решай задачи и усиливай навыки"),
        VariantInput("Dev Рывок", "Готовься системно к следующему офферу"),
        VariantInput("КодНавык", "Практика для сильных ответов разработчика"),
        VariantInput("ТехПульс", "Прокачай знания перед важной встречей"),
    ]


def test_mode_requires_exact_canonical_prompt() -> None:
    assert mode_for_prompt(CANONICAL_TEMPERATURE_PROMPT) == "benchmark"
    assert mode_for_prompt(CANONICAL_TEMPERATURE_PROMPT + "\n") == "free"
    assert mode_for_prompt(CANONICAL_TEMPERATURE_PROMPT.replace(" 5 ", " пять ")) == "free"


def test_normalization_trims_collapses_whitespace_and_ignores_case() -> None:
    assert normalize_name("  Код\t  СТАРТ \n") == "код старт"


def test_validator_accepts_all_five_formal_requirements() -> None:
    result = validate_variants(valid_variants())

    assert result.requirements_met == 5
    assert [check.passed for check in result.checks] == [True] * 5


def test_validator_checks_each_formal_requirement_independently() -> None:
    variants = valid_variants()
    variants[0] = VariantInput("Слишком Длинное Название", "Раз два три четыре пять шесть семь восемь девять")
    variants[1] = VariantInput("Interview", variants[1].slogan)
    variants[2] = VariantInput("  interview  ", variants[2].slogan)
    variants.pop()

    result = validate_variants(variants)
    checks = {check.check_id: check.passed for check in result.checks}

    assert checks == {
        "exactly_five": False,
        "name_word_count": False,
        "unique_names": False,
        "forbidden_words": False,
        "slogan_word_count": False,
    }


def test_forbidden_words_are_standalone_and_case_insensitive() -> None:
    variants = valid_variants()
    variants[0] = VariantInput("ai Sprint", variants[0].slogan)
    variants[1] = VariantInput("ИИ-Практика", variants[1].slogan)
    result = validate_variants(variants)
    checks = {check.check_id: check.passed for check in result.checks}
    assert checks["forbidden_words"] is False

    variants[0] = VariantInput("Aiming", variants[0].slogan)
    variants[1] = VariantInput("ИИшник", variants[1].slogan)
    result = validate_variants(variants)
    checks = {check.check_id: check.passed for check in result.checks}
    assert checks["forbidden_words"] is True


def test_validator_item_count_and_slogan_boundaries() -> None:
    four = valid_variants()[:4]
    six = valid_variants() + [VariantInput("Шестое", "Раз два три")]
    assert validate_variants(four).checks[0].passed is False
    assert validate_variants(six).checks[0].passed is False

    eight_words = "раз два три четыре пять шесть семь восемь"
    nine_words = f"{eight_words} девять"
    variants = valid_variants()
    variants[0] = VariantInput(variants[0].name, eight_words)
    assert validate_variants(variants).checks[4].passed is True
    variants[0] = VariantInput(variants[0].name, nine_words)
    assert validate_variants(variants).checks[4].passed is False
