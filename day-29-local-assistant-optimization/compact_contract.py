"""Opt-in Day 29 contract. Mechanical provenance is not semantic certification."""
import json

import grounded_explain as baseline
from explain import safe_text

VARIANT = "compact-evidence-v1"
LINES = baseline.array({"type": "integer", "minimum": 1}, minItems=1, uniqueItems=True)
SCHEMA = baseline.obj({
    "code_observations": baseline.array(baseline.obj({"text": baseline.TEXT, "lines": LINES})),
    "documented_applications": baseline.array(baseline.obj({
        "rule": baseline.TEXT, "text": baseline.TEXT, "lines": LINES,
        "citations": baseline.array(baseline.obj({
            "chunk_id": baseline.TEXT, "quote": {**baseline.TEXT, "maxLength": 400}
        }), minItems=1),
    })),
    "assumptions": baseline.array(baseline.TEXT),
    "limitations": baseline.array(baseline.TEXT),
})

# Baseline instructions, with only the output-format clauses adapted. No correction suffix.
INSTRUCTIONS = baseline.INSTRUCTIONS
for old, new in (
    ("коду, id, text, непустые", "коду, text (объяснение), непустые"),
    ("documented_rules: до 3 относящихся к вопросу правил, id, text, citations {chunk_id,quote}; ",
     "documented_applications: до 3 применений относящихся к вопросу правил; в каждом объекте "
     "rule (документированное правило), text (его применение), непустые уникальные lines 1..N "
     "(строки Kotlin, к которым применяется правило), citations {chunk_id,quote}; "),
    ("applications: интерпретации применения конкретных rules к конкретным observations, с observation_ids "
     "и rule_ids. ", "text в documented_applications — интерпретация применения rule к указанным lines. "),
    ("Верни knowledge_status точно как в данных. Для not_requested/no_candidates rules и applications пусты, ",
     "knowledge_status задан runtime во входных данных; не возвращай его или IDs элементов. "
     "Для not_requested/no_candidates documented_applications пуст, "),
    ("rules/applications пусты", "documented_applications пуст"),
):
    if INSTRUCTIONS.count(old) != 1:
        raise ValueError("Baseline format instruction changed; review compact adaptation.")
    INSTRUCTIONS = INSTRUCTIONS.replace(old, new)


def parse(response, line_count, expected_status, selected):
    if response.get("done") is not True or response.get("done_reason") != "stop":
        raise RuntimeError("Генерация не завершена done/stop; ответ не принят.")
    try:
        result = json.loads(response["message"]["content"])

        def text(value):
            return isinstance(value, str) and bool(value.strip())

        def fields(value, keys):
            return isinstance(value, dict) and set(value) == set(keys)

        def lines(values):
            return (isinstance(values, list) and bool(values)
                    and all(type(n) is int and 1 <= n <= line_count for n in values)
                    and len(values) == len(set(values)))

        if expected_status not in ("not_requested", "no_candidates", "candidates_provided"):
            raise ValueError
        if not fields(result, SCHEMA["properties"]) or not all(isinstance(v, list) for v in result.values()):
            raise ValueError
        if not all(text(v) for key in ("assumptions", "limitations") for v in result[key]):
            raise ValueError
        for item in result["code_observations"]:
            if not fields(item, {"text", "lines"}) or not text(item["text"]) or not lines(item["lines"]):
                raise ValueError
        contexts = {c["chunk_id"]: c for c in selected}
        for item in result["documented_applications"]:
            if (not fields(item, {"rule", "text", "lines", "citations"})
                    or not text(item["rule"]) or not text(item["text"]) or not lines(item["lines"])
                    or not isinstance(item["citations"], list) or not item["citations"]):
                raise ValueError
            seen = set()
            for cite in item["citations"]:
                if (not fields(cite, {"chunk_id", "quote"}) or not text(cite["chunk_id"])
                        or not text(cite["quote"]) or cite["chunk_id"] not in contexts
                        or len(cite["quote"]) > 400 or cite["quote"] not in contexts[cite["chunk_id"]]["text"]):
                    raise ValueError
                pair = cite["chunk_id"], cite["quote"]
                if pair in seen:
                    raise ValueError
                seen.add(pair)
        applications = result["documented_applications"]
        if expected_status != "candidates_provided" and applications:
            raise ValueError
        if (expected_status != "candidates_provided" or not applications
                or not result["code_observations"]) and not result["limitations"]:
            raise ValueError
        # Runtime-only display metadata, after validating the exact model response.
        return {**result, "knowledge_status": expected_status}
    except (KeyError, TypeError, ValueError, RecursionError):
        raise RuntimeError("Недопустимые schema, строки, chunk или точные цитаты ответа.") from None


def render(result, selected):
    output = ["Knowledge: " + result["knowledge_status"], "Наблюдения по Kotlin (смысл требует review):"]
    for number, item in enumerate(result["code_observations"], 1):
        output.append(f"- {number}. {item['text']} [Kotlin: {', '.join(map(str, item['lines']))}]")
    output.append("\nДокументированные применения (цитата не доказывает применимость):")
    contexts = {c["chunk_id"]: c for c in selected}
    for number, item in enumerate(result["documented_applications"], 1):
        output.append(f"- {number}. Правило: {item['rule']}")
        output.append(f"  Применение: {item['text']} [Kotlin: {', '.join(map(str, item['lines']))}]")
        for cite in item["citations"]:
            c = contexts[cite["chunk_id"]]
            output.append(f"  [{c['source']} / {c['section']} / Markdown L{c['start_line']}-{c['end_line']}; "
                          f"{c['chunk_id']}] «{cite['quote']}»")
    for field, title in (("assumptions", "Предположения"), ("limitations", "Ограничения")):
        output.append("\n" + title + ":")
        output.extend("- " + value for value in result[field] or ["Нет."])
    return safe_text("\n".join(output))
