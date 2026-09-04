"""Fixed Day 05 experiment and deterministic, model-independent verification."""
import hashlib
import itertools
import json
from functools import lru_cache
from typing import Any

from app.model_benchmark_models import BenchmarkAnswer, Quality, TaskResult

BENCHMARK_VERSION = "day05-v1"
CANONICAL_PROMPT = """Реши 5 независимых задач. Верни только результат каждой задачи в указанном
Structured Output. Не пропускай задачи.

Задача 1 — арифметика.
Сервис обработал 240 запросов. 35% запросов были обслужены из кэша и не
обращались к базе данных. Каждый оставшийся запрос сделал ровно 3 запроса
к БД. Сколько всего запросов к БД было выполнено?

Задача 2 — логическая дедукция.
Есть четыре разработчика: Анна, Борис, Вера и Глеб, и четыре дня:
понедельник, вторник, среда, четверг. Каждый дежурит ровно один день.
Условия:
- Анна дежурит раньше Бориса.
- Вера не дежурит ни в понедельник, ни в четверг.
- Глеб дежурит ровно на следующий день после Анны.
Определи полное расписание.

Задача 3 — оптимизация.
Лимит — 15 story points.

Фичи:
A: cost 4, value 8
B: cost 6, value 11
C: cost 5, value 10
D: cost 3, value 6
E: cost 7, value 13
F: cost 2, value 4
G: cost 4, value 7
H: cost 5, value 8

Ограничения:
- B и E нельзя брать вместе;
- C можно взять только вместе с F;
- A и D нельзя брать вместе;
- G и H нельзя брать вместе;
- total cost <= 15.

Выбери допустимый набор с максимальной total value.

Задача 4 — algorithm tracing.
Индексация массива с нуля.

Начальное состояние:
a = [7, 2, 5, 1, 8, 3, 6, 4]

Сначала выполнить для i от 1 до 7 включительно:

if (a[i - 1] + i) mod 3 == 0:
    a[i] = a[i] + a[i - 1]
else:
    a[i] = a[i - 1] - a[i]

Каждая следующая итерация использует уже изменённый массив.

После этого выполнить для i от 6 до 0 включительно в обратном порядке:

if i mod 2 == 0:
    a[i] = a[i] + a[i + 1]
else:
    a[i] = a[i] - a[i + 1]

Здесь также используются текущие уже изменённые значения.

После обоих циклов вычислить:
checksum = sum((i + 1) * a[i]) для i от 0 до 7.

Верни final_array и checksum.

Задача 5 — combinatorial counting.
Посчитай количество строк длины 10 над алфавитом {A, B, C}, которые:
1. содержат ровно 4 символа A;
2. не содержат одинаковых соседних символов;
3. первый символ не C;
4. для каждого B среди одного или двух следующих существующих символов должен встретиться C;
5. соседняя подстрока AB встречается ровно 2 раза.

Для B около конца строки учитываются только реально существующие следующие позиции.
Если среди них нет C, строка не подходит.

Occurrence AB — это позиция i, где s[i]=A и s[i+1]=B.
Верни только count."""
INSTRUCTIONS = "Верни только JSON, соответствующий заданной схеме. Реши все пять задач; не добавляй пояснения вне JSON."
DAYS = ("monday", "tuesday", "wednesday", "thursday")
FEATURES = dict(zip("ABCDEFGH", ((4, 8), (6, 11), (5, 10), (3, 6), (7, 13), (2, 4), (4, 7), (5, 8))))


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def benchmark_schema() -> dict[str, Any]:
    integer = {"type": "integer"}
    string = {"type": "string"}
    return _object({
        "task1": _object({"database_queries": integer}),
        "task2": _object({day: string for day in DAYS}),
        "task3": _object({
            "selected_features": {"type": "array", "items": string},
            "total_cost": integer, "total_value": integer,
        }),
        "task4": _object({"final_array": {"type": "array", "items": integer}, "checksum": integer}),
        "task5": _object({"count": integer}),
    })


def common_parameters() -> dict[str, Any]:
    return {
        "input": CANONICAL_PROMPT,
        "instructions": INSTRUCTIONS,
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 6000,
        "text": {"format": {"type": "json_schema", "name": "five_task_benchmark", "strict": True, "schema": benchmark_schema()}},
        "store": False,
        "service_tier": "default",
    }


def payload_fingerprint() -> str:
    return hashlib.sha256(json.dumps(common_parameters(), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def feature_totals(selected: set[str]) -> tuple[int, int]:
    return tuple(sum(FEATURES[x][i] for x in selected) for i in (0, 1))


def feasible(selected: set[str]) -> bool:
    return (
        selected <= FEATURES.keys()
        and not {"B", "E"} <= selected
        and ("C" not in selected or "F" in selected)
        and not {"A", "D"} <= selected
        and not {"G", "H"} <= selected
        and feature_totals(selected)[0] <= 15
    )


def schedule_valid(names: tuple[str, ...]) -> bool:
    return (
        len(names) == 4 and set(names) == {"Анна", "Борис", "Вера", "Глеб"}
        and names.index("Анна") < names.index("Борис")
        and names.index("Вера") not in (0, 3)
        and names.index("Глеб") == names.index("Анна") + 1
    )


def trace_array() -> dict[str, Any]:
    a = [7, 2, 5, 1, 8, 3, 6, 4]
    for i in range(1, 8):
        a[i] = a[i] + a[i - 1] if (a[i - 1] + i) % 3 == 0 else a[i - 1] - a[i]
    for i in range(6, -1, -1):
        a[i] = a[i] + a[i + 1] if i % 2 == 0 else a[i] - a[i + 1]
    return {"final_array": a, "checksum": sum((i + 1) * value for i, value in enumerate(a))}


def b_has_following_c(s: str) -> bool:
    return all("C" in s[i + 1:i + 3] for i, char in enumerate(s) if char == "B")


def valid_counting_string(s: str) -> bool:
    return (
        len(s) == 10 and set(s) <= set("ABC") and s.count("A") == 4
        and all(a != b for a, b in zip(s, s[1:]))
        and s[0] != "C"
        and b_has_following_c(s)
        and sum(s[i:i + 2] == "AB" for i in range(9)) == 2
    )


@lru_cache(maxsize=1)
def _reference_json() -> str:
    schedules = [p for p in itertools.permutations(("Анна", "Борис", "Вера", "Глеб")) if schedule_valid(p)]
    subsets = [
        {name for i, name in enumerate(FEATURES) if mask & (1 << i)}
        for mask in range(1 << len(FEATURES))
    ]
    best = max((s for s in subsets if feasible(s)), key=lambda s: feature_totals(s)[1])
    cost, value = feature_totals(best)
    count = sum(valid_counting_string("".join(s)) for s in itertools.product("ABC", repeat=10))
    return json.dumps({
        "task1": {"database_queries": (240 * (100 - 35) // 100) * 3},
        "task2": dict(zip(DAYS, schedules[0])),
        "task3": {"selected_features": sorted(best), "total_cost": cost, "total_value": value},
        "task4": trace_array(),
        "task5": {"count": count},
    }, ensure_ascii=False)


def reference_answers() -> dict[str, Any]:
    # The cached value is immutable; callers cannot mutate another run's reference.
    return json.loads(_reference_json())


def unverified_tasks() -> list[TaskResult]:
    return [TaskResult(task_id=f"task{i}", verdict="unverified") for i in range(1, 6)]


def verify(answer: BenchmarkAnswer) -> tuple[Quality, list[TaskResult]]:
    actual = answer.model_dump()
    reference = reference_answers()
    correct = {key: actual[key] == reference[key] for key in ("task1", "task4", "task5")}
    correct["task2"] = schedule_valid(tuple(actual["task2"][day].strip() for day in DAYS))
    t3 = answer.task3
    selected = set(t3.selected_features)
    correct["task3"] = (
        len(selected) == len(t3.selected_features)
        and feasible(selected)
        and feature_totals(selected) == (t3.total_cost, t3.total_value)
        and t3.total_value == reference["task3"]["total_value"]
    )
    tasks = [
        TaskResult(
            task_id=key, verdict="correct" if correct[key] else "incorrect",
            actual_answer=actual[key], reference_answer=None if correct[key] else reference[key],
        )
        for key in actual
    ]
    return Quality(correct_count=sum(correct.values())), tasks
