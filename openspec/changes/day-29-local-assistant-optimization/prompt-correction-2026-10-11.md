# Day 29 — одна opt-in коррекция prompt

Пользователь подтвердил Coder S2 PARTIAL, S3 PASS по основной задаче, S4 FAIL, S5 PARTIAL, S6 PARTIAL и разрешил одну коррекцию инструкций с двумя новыми вызовами: S4, затем S6. Исторические результаты не заменяются. Общая schema, validator, renderer и обычный prompt приложения сохраняются.

## Реализация и границы

В существующем `day-29-local-assistant-optimization/driver.py` добавлен единственный вариант `explain-evidence-v1`: текст про объяснение своими словами и применимость evidence добавляется только к system message. Нет эталонных ответов, имён сценариев или Compose/RPO подсказок в тексте correction.

Opt-in задаётся полем `prompt_variant: "explain-evidence-v1"` в job существующего `execute`/`--worker`; без него payload прежний. В `packet` это одноимённый keyword argument. Не добавляются повседневные CLI-настройки или framework. В worker вариант ограничен baseline Coder chat S4/S6. `execute` требует отдельный журнал, S4 перед S6, останавливает ветку после ошибки и запрещает повтор. Исправленные ответы исключены из baseline-selection. Общий бюджет с предыдущими журналами проверяется операторским запуском до этих двух вызовов.

Identity в [prompt-correction-manifest.json](../../../day-29-local-assistant-optimization/prompt-correction-manifest.json):

- variant prompt SHA-256: `5e5a71031346ca8ccb862af70e7431eee18cee74c0ded8c808d6da68256d6d08`;
- parent prompt SHA-256: `eb36c4a194ec44b548aaf0a6156ddf41d431f037c1990cd180d6e1c39386c3f6`;
- parent frozen manifest SHA-256: `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4`;
- unchanged schema SHA-256: `478fcb753a8957c49815b62951f64b445a7a18301f8cb86425d05a540efac87c`.

Модельный profile сам по себе не включает prompt. Поэтому новый prompt identity записывается в start/end records и metrics отдельно. Исходный frozen manifest не меняется; новая редакция обязана совпасть с отдельно закреплённым manifest.

## Offline до live

Focused: **118 passed** (Day 29 tests + Day 27 test_grounded/test_rag_cli/test_explain). Проверены равенство S4/S6 payload кроме system content, отсутствие изменений обычных prompt/schema, совпадение frozen inputs/settings, worker integration, validation failure без repair, запрет других вариантов/сценариев/параметров, порядок, остановка и сохранность журналов. Старые negative tests проверяют Kotlin lines, chunk IDs, exact citations и application references. Это новый focused count, не замена историческим 258 passed / 1 skipped.

До live дополнительно проверить hashes защищённых Day 27–28/исторических файлов, strict validation, local-only, digest/profile, отсутствие незавершённых запросов и GPU. Только два chat calls S4→S6, без отдельного preload и retries, каждый под прежним child deadline 180 s. Если модель не resident, первый chat включает загрузку и отмечается отдельно. Sampling/model/keep_alive/context/schema/chunks не меняются.

Оценка использует прежнюю rubric. S4: недостаток сведений, отсутствие чужого scope/необоснованных выводов. S6: объяснение state ownership, StateFlow, collection lifecycle, effect keys/cancellation/re-entry, responsibility boundaries и unknowns. Число observations само по себе не улучшение. После серии — user review, без следующей редакции или выбора модели.

## Фактический preflight: STOP, inference не выполнялся

2026-10-11, Europe/Moscow. Strict validation PASS; синтаксис изменённых Python проверен; все 52 защищённых файла Day 27–28, исходный frozen manifest и предыдущие отчёты совпадают с хэшами до изменения.

Ollama 0.40.2, текущий server.log подтверждает OLLAMA_NO_CLOUD=true / cloud disabled=true и loopback listener. `/api/ps` пуст, model runners/Python-клиентов и established API connections не обнаружено. Точный Coder digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`, прежний model profile `336fdb5fa73c6c7ba4ed39f1a454e1ff54295e774baad00b8d5ba0018ad2c007` подтверждены read-only metadata.

| Время MSK | Used MiB | Free MiB | GPU utilization |
|---|---:|---:|---:|
| 10:18:27.021 | 672 | 11326 | 3% |
| 10:18:32.090 | 666 | 11332 | 4% |
| 10:18:37.133 | 677 | 11321 | 30% |

Принятый для контролируемого запуска критерий: free >=9000 MiB и utilization <10% в каждом из трёх измерений примерно через 5 секунд. Третий снимок не прошёл порог загрузки GPU. Свободной VRAM достаточно. Один снимок 30% не доказывает устойчивую постороннюю нагрузку и не устанавливает процесс-причину; серия остановлена без повторов измерений ради допуска.

| Сценарий | Выполнение | Semantic | Время/token metrics |
|---|---|---|---|
| S4 corrected | NOT RUN — preflight gate | NOT EVALUATED | unavailable |
| S6 corrected | NOT RUN — preflight gate | NOT EVALUATED | unavailable |

Новых load/chat calls: **0**. Общий исторический счёт остаётся **11/32**. Ответов новой редакции нет; улучшение объяснения **NOT TESTED**. Прежние S4 FAIL и S6 PARTIAL не изменены. Preflight evidence: [prompt-correction-preflight-2026-10-11.json](prompt-correction-preflight-2026-10-11.json).

Не выполнялись preload, генерация, repair, изменения sampling/schema/validator/renderer, другие сценарии, выгрузка моделей, завершение процессов, commit/push/archive или видео. Следующий необходимый этап после отдельного продолжения пользователем — свежий preflight при подходящей загрузке GPU и только затем S4→S6 той же закреплённой редакции. Никаких дополнительных prompt-правок по этому результату не требуется.
