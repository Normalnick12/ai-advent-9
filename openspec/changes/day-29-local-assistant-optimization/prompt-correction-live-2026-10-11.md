# Day 29 — продолжение explain-evidence-v1

## Условия, закреплённые до нового preflight

Пользователь принял 118 focused tests PASS / OpenSpec strict validation PASS и разрешил один новый preflight, затем ровно S4 → S6 при допуске. Предыдущий [заблокированный preflight](prompt-correction-2026-10-11.md) с 3/4/30% и его evidence сохраняются без изменений. Его результат не пересчитывается по новому критерию.

Новый критерий GPU:

1. Шесть измерений, интервал примерно 5 секунд.
2. Медиана GPU utilization строго меньше 15% (для шести значений — среднее третьего и четвёртого после сортировки).
3. В исходном временном порядке нет двух последовательных измерений >=30%.
4. Свободная VRAM >=9000 MiB в каждом измерении.

Все условия обязательны. Недоступное/некорректное измерение не считается нулём и не даёт допуска. Проверка оценивает устойчивую фоновую нагрузку, не доказывает отсутствие любой конкуренции. Повтор измерений ради PASS не разрешён.

Local-only работающего Ollama, правильный установленный digest/profile и отсутствие незавершённых запросов обязательны. GPU gate остаётся операторской preflight-проверкой через nvidia-smi и Python, как в предыдущих запусках; в driver он не реализован. Runtime-код и tests не меняются; принятые 118 focused tests переиспользуются, повторять их без изменения входов не требуется.

Вызовы: только Coder `qwen2.5-coder:7b-instruct-q4_K_M`, opt-in `explain-evidence-v1`, S4 затем S6, каждый с child wall deadline 180 s. Без дополнительного preload, retries, repair или других сценариев. Первая техническая ошибка прекращает ветку. Отдельный журнал и общий бюджет с историческими попытками; старые ошибки остаются в знаменателе.

Неизменны num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m, прежние sampling settings, schema/validator/renderer, вопросы, Kotlin и Markdown chunks с порядком. Frozen manifest `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4`; correction prompt SHA-256 `5e5a71031346ca8ccb862af70e7431eee18cee74c0ded8c808d6da68256d6d08`. Обычный prompt приложения не меняется.

После двух запросов (либо отказа gate/technical failure) — остановка для совместного review, без выбора модели, следующей редакции prompt, RAG или оптимизаций. Оценка по прежней рубрике: полнота объяснения, правильность Kotlin/Compose, scope и entailment документации, честные ограничения; больше observations само по себе не успех.

## Единственный новый preflight: PASS

Local-only подтверждён текущим server.log (cloud disabled=true, OLLAMA_NO_CLOUD=true, 127.0.0.1:11434); Ollama 0.40.2. `/api/ps` пуст, model runners/Python-клиентов и established API connections не обнаружено. Coder digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, модельный profile `336fdb5fa73c6c7ba4ed39f1a454e1ff54295e774baad00b8d5ba0018ad2c007` подтверждены.

| Время MSK 2026-10-11 | Used MiB | Free MiB | GPU utilization |
|---|---:|---:|---:|
| 10:23:29.348 | 585 | 11413 | 9% |
| 10:23:34.405 | 609 | 11389 | 1% |
| 10:23:39.451 | 593 | 11405 | 1% |
| 10:23:44.496 | 591 | 11407 | 0% |
| 10:23:49.536 | 569 | 11429 | 1% |
| 10:23:54.584 | 555 | 11443 | 0% |

Медиана 1%, соседних значений >=30% нет, free >=9000 MiB во всех шести измерениях. Новый критерий пройден; старый заблокированный preflight остаётся отдельным историческим результатом.

## Live: S4 FAIL, S6 NOT RUN

S4 начат 10:24:10.546 MSK, завершён 10:24:37.289. Один chat без preload; модель до запроса не resident. Ответ пришёл HTTP 200 / done=true, но done_reason=length при eval_count=2048. Это достижение лимита генерации, не timeout и не сбой загрузки. Существующий validator отказал на проверке завершённости до разбора JSON/строк/ссылок. Raw content обрывается внутри limitations, JSON не завершён. Repair не выполнялся.

| Метрика | Исторический S4 | S4 explain-evidence-v1 | S6 explain-evidence-v1 |
|---|---:|---:|---|
| Technical | PASS, stop | FAIL, length | NOT RUN — gate после S4 |
| Resident before | yes | no | N/A |
| Generation HTTP wall | 8.064836 s | 26.361095 s | unavailable |
| Provider load | 0.005132 s | 2.363756 s | unavailable |
| Bounded client wall | 8.426071 s | 26.744342 s | unavailable |
| Prompt tokens / duration | 1133 / 0.302240 s | 1416 / 0.310747 s | unavailable |
| Output tokens / duration | 661 / 7.708121 s | 2048 / 23.673615 s | unavailable |
| Decode throughput, API counts/duration | 85.754 tokens/s | 86.510 tokens/s | unavailable |
| System VRAM before → after | 5608 → 5607 MiB | 557 → 5671 MiB | unavailable |

Полное время между baseline и correction не является чистым сравнением скорости prompt: состояние загрузки различается. Provider load входит в generation wall, повторно не суммируется. Retrieval=0, embedding calls=0, TTFT unavailable. Provider total=26.359722 s; driver user_request_seconds=26.365903 s включает packing/generation/отказ validation, не полный пользовательский RAG.

System RAM available: 21,655,048,192 → 20,879,089,664 bytes (~20.168 → 19.445 GiB), total 34,191,245,312 bytes. Это before/after snapshots, не peak и не память одного процесса. Runner RSS/commit unavailable.

После ошибки сделаны только read-only проверки: `/api/ps` подтвердил прежний digest, context=8192, size=size_vram=5,133,943,438 bytes; server.log — all slots idle. `truncated=0` в runner не отменяет output limit length: это не доказательство завершённого ответа. Ответ сервера завершён, зависший запрос не наблюдается. Модель не выгружали и процессы не завершали.

## Review фрагмента и сравнение с историей

Reviewer: assistant provisional, user review pending. S4 semantic **FAIL** по необоснованной связи RPO/RTO с atomic rollback в limitations; дополнительно ответ технически незавершён. S6 semantic NOT EVALUATED. Прежние user-confirmed S4 FAIL / S6 PARTIAL не изменены.

- Kotlin: вместо трёх скопированных блоков дано одно объяснение своими словами. Верно описаны empty/declined returns и successful clear → receipt → Success. Детальное вычисление суммы не разобрано, но это не основной вопрос S4. Одно observation по-прежнему не выполняет prompt о 3–5 наблюдениях.
- Источники: в полученном фрагменте documented_rules=[], applications=[]; weather-rule больше не применяется к CheckoutCoordinator. Это локальное улучшение отбора evidence, а не schema/citation PASS: полная validation не состоялась.
- Отсутствующие знания: прямо отмечено отсутствие сведений о RPO/RTO. Чисел и положительных гарантий не придумано.
- Неподтверждённый вывод: остаётся формулировка, смешивающая свойства RPO/RTO с гарантиями atomic rollback. Она не поддерживается переданными источниками.
- Завершённость/полезность: после начальных ограничений одно предложение дословно повторено **38 раз**, затем обрыв. Это новый существенный дефект; пользоваться ответом целиком нельзя.
- S6 не выполнялся: о влиянии коррекции на Compose, StateFlow и lifecycle выводов нет. Старый PARTIAL не превращается ни в PASS, ни в новый FAIL.

Итог: копирование Kotlin в S4 уменьшилось, отказ от нерелевантного правила стал лучше, но полезное завершённое объяснение не получено. Коррекция в разрешённом опыте не подтвердила практическое улучшение. Нельзя приписывать зацикливание конкретной sampling-настройке или доказывать причинность по одному ответу. Следующая редакция prompt, изменение penalty/output limit или новая генерация не выполняются.

Полный полученный raw fragment предоставляется в разговоре, без исправления/продолжения. В файлах только metrics/verdicts, без model transcript. [Evidence](prompt-correction-live-evidence-2026-10-11.json).

## Учёт и завершение

Новая серия: 1 attempted / 1 technical FAIL / 1 NOT RUN, 26.744342 s bounded client wall. Общий счёт с историческими отказами: **12/32 attempts**, 205.174002 s записанного bounded client wall; read-only preflight учитывается отдельно. Лимит 180 s не достигнут. S6 остановлен по gate; разрешение на два сценария не отменяет stop-on-error.

Код driver/tests, variant manifest, исходные Day 27–28/исторические reports и старый preflight не менялись. 118 focused tests — ранее принятый результат, повторно не запускались без изменений кода. OpenSpec 20/30; после обновления документов выполняется strict validation. Модель не выбрана, Mac NOT TESTED. Без commit/push/archive/видео. Остановка для review.
