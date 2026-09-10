import re

SCENARIO_ID = "three-facts-v1"
QUESTION = ("Верни три строки: identifier=<идентификатор проекта>, limit=<лимит>, "
            "responsible=<ответственный>. Если значение неизвестно, напиши unknown. Без дополнительных пояснений")
EXPECTED = {"identifier": "ORBIT-7319", "limit": "37", "responsible": "Мира"}
ACK = "Ответь только: Принято. Не повторяй факты из диалога."


def fixture_messages():
    # Start at 100: filler numbering must never accidentally introduce the target number 37.
    filler = "\n".join(f"Запись {i}: учебный текст о повторной передаче истории и стоимости контекста."
                       for i in range(100, 180))
    return (f"Учебный сценарий. identifier=ORBIT-7319\n{filler}\n{ACK}",
            f"Учебный сценарий. limit=37\n{filler}\n{ACK}",
            f"Учебный сценарий. responsible=Мира\n{ACK}",
            f"Подтверди готовность к проверке. {ACK}")


def scenario_applicable(history, question):
    if len(history) != 8 or question != QUESTION or tuple(m.content for m in history[::2]) != fixture_messages():
        return False
    tail = "\n".join(m.content for m in history[-4:])
    return "ORBIT-7319" not in tail and re.search(r"(?<!\d)37(?!\d)", tail) is None and "Мира" in tail


def verify_facts(reply):
    fields = {k: [] for k in EXPECTED}
    for line in re.split(r"[\r\n,;]", reply):
        match = re.fullmatch(r"\s*(identifier|limit|responsible)\s*=\s*(.*?)\s*", line)
        if match:
            # Strip one terminal sentence period, never internal decimal punctuation.
            fields[match[1]].append(match[2].removesuffix(".").rstrip())
    facts = {k: values == [EXPECTED[k]] for k, values in fields.items()}
    return sum(facts.values()), facts
