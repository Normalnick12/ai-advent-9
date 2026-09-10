import pytest

from app.compression_scenario import verify_facts


@pytest.mark.parametrize("separator", ["\n", "\r\n", ",", ";", " , ", " ;\n "])
def test_exact_facts_accept_field_separators(separator):
    reply = separator.join([" identifier = ORBIT-7319 ", " limit = 37 ", " responsible = Мира "])
    assert verify_facts(reply) == (3, {"identifier": True, "limit": True, "responsible": True})


def test_reported_compressed_response_preserves_only_responsible():
    assert verify_facts("identifier=unknown, limit=unknown, responsible=Мира") == (
        1, {"identifier": False, "limit": False, "responsible": True})


@pytest.mark.parametrize("value", ["137", "037", "37.0", "37 extra", "unknown", ""])
def test_limit_requires_exact_string(value):
    score, facts = verify_facts(f"identifier=ORBIT-7319, limit={value}, responsible=Мира")
    assert score == 2 and not facts["limit"]


@pytest.mark.parametrize("field,wrong", [
    ("identifier", "unknown"), ("limit", "137"), ("responsible", "Другой"),
])
@pytest.mark.parametrize("wrong_first", [True, False])
def test_conflicting_duplicate_does_not_count_regardless_of_order(field, wrong, wrong_first):
    correct = "identifier=ORBIT-7319, limit=37; responsible=Мира"
    duplicate = f"{field}={wrong}"
    reply = f"{duplicate}\n{correct}" if wrong_first else f"{correct}; {duplicate}"
    score, facts = verify_facts(reply)
    assert score == 2 and not facts[field]


@pytest.mark.parametrize("reply", [
    "identifier=ORBIT-7319, responsible=Мира",
    "identifier=ORBIT-7319, not_limit=37, responsible=Мира",
    "identifier=ORBIT-7319, limit=37, limit=37, responsible=Мира",
])
def test_missing_and_duplicate_fields_keep_existing_strict_semantics(reply):
    score, facts = verify_facts(reply)
    assert score == 2 and not facts["limit"]


@pytest.mark.parametrize("reply", [
    "identifier=ORBIT-73190, limit=37, responsible=Мира",
    "identifier=ORBIT-7319, limit=37, responsible=Мира extra",
])
def test_names_and_identifiers_are_not_substring_matches(reply):
    assert verify_facts(reply)[0] == 2

@pytest.mark.parametrize("suffix", ["", ".", ",", ";", " . "])
def test_responsible_accepts_terminal_sentence_punctuation(suffix):
    score, facts = verify_facts(f" responsible = Мира{suffix} ")
    assert score == 1 and facts["responsible"]


@pytest.mark.parametrize("reply,score", [
    ("identifier=ORBIT-7319, limit=37, responsible=Мира.", 3),
    ("identifier=unknown, limit=unknown, responsible=Мира.", 1),
    ("identifier=ORBIT-7319.; limit=37.\n responsible=Мира.", 3),
])
def test_sentence_punctuation_keeps_exact_named_facts(reply, score):
    assert verify_facts(reply)[0] == score


@pytest.mark.parametrize("value", ["137.", "037.", "37.0", "37.0.", "unknown.", ""])
def test_sentence_punctuation_does_not_coerce_wrong_numbers(value):
    assert verify_facts(f"limit={value}")[1]["limit"] is False


@pytest.mark.parametrize("reply", [
    "responsible=Мира., responsible=Анна.",
    "responsible=Анна.; responsible=Мира.",
    "responsible=Мира., responsible=unknown.",
    "responsible=Анна.",
    "responsible=unknown.",
    "responsible=Мира extra.",
    "identifier=ORBIT-73190.",
])
def test_punctuation_does_not_hide_wrong_or_conflicting_values(reply):
    assert verify_facts(reply)[0] == 0
