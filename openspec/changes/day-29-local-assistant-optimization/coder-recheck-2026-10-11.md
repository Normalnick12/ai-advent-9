# Day 29 — Coder после устранения посторонней нагрузки GPU

Отдельный разрешённый пользователем эксперимент 2026-10-11, Europe/Moscow. Исторический Coder admission TIMEOUT 60 s от 2026-10-10 сохранён в прежних отчёте и журнале. Новая попытка не доказывает причину прежнего отказа или устойчивость модели. Runtime-код, настройки, prompt/schema, fixtures, RAG и OpenSpec tasks не изменялись.

## Preflight

- Пользователь подтвердил завершение проверок Windows и разрешил ровно один load-only, затем один S1 при успешной готовности.
- Ollama 0.40.2, NVIDIA 610.88, RTX 4070 SUPER. Текущий server.log: OLLAMA_NO_CLOUD=true, cloud disabled=true, listen 127.0.0.1:11434. Только локальная установленная модель.
- `/api/ps`: пуст; среди процессов только Ollama app/serve, model runners/Python-клиентов нет. TCP 11434: только listener, установленных соединений нет. Старый runner отсутствует после перезагрузки; старое поле cleanup=unknown не переписано.
- GPU samples (интервалы около 5 s):

| Время MSK | Used MiB | Free MiB | Utilization |
|---|---:|---:|---:|
| 09:41:56.531 | 531 | 11467 | 3% |
| 09:42:01.592 | 530 | 11468 | 3% |
| 09:42:06.640 | 527 | 11471 | 3% |

Все три измерения удовлетворяют free >=9000 MiB и utilization <10%.

Tag: `qwen2.5-coder:7b-instruct-q4_K_M`.

- Digest: `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
- Profile: `336fdb5fa73c6c7ba4ed39f1a454e1ff54295e774baad00b8d5ba0018ad2c007`.
- Frozen manifest: `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4`, проверен до и после.
- Прежние num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m, Q4_K_M, stream=false. Явные top_k=20, top_p=0.95, min_p=0, repeat_last_n=64, repeat_penalty=1, presence_penalty=0, frequency_penalty=0. Thinking not_supported; поле не отправлено.
- Фактический runner: llama.cpp/CUDA, 29/29 layers offloaded, context 8192, CUDA model buffer 4168.09 MiB, KV 448 MiB, compute 280.02 MiB, CUDA_Host model buffer 292.36 MiB. Как и в исторической попытке, сервер выбрал batch/ubatch=1024: значение API default 512 в profile не является измеренным runner batch. Mmap disabled сервером по windows_cuda, настройки не менялись.

## Технический результат

| Метрика | Load-only | S1 |
|---|---:|---:|
| Outcome | PASS, done/load | PASS, done/stop |
| Начало MSK | 09:42:42.724 | 09:42:54.310 |
| Client deadline | 60 s | 180 s |
| HTTP phase wall | 11.173630 s | 12.037059 s |
| Bounded client wall с metadata/readiness | 11.578712 s | 12.401503 s |
| Cache state | not resident before | resident before/after |
| Provider total | unavailable | 12.035657 s |
| Provider load | unavailable | 0.005135 s |
| Prompt tokens / duration | N/A | 717 / 7.255625 s |
| Output tokens / duration | N/A | 390 / 4.765692 s |
| Decode throughput, API counts/duration | N/A | 81.835 tokens/s |
| System GPU used before → after | 531 → 5614 MiB | 5623 → 5632 MiB |

Readiness подтвердил правильный digest, context=8192 и size=size_vram=5,133,943,438 bytes (~4896.11 MiB / 4.781 GiB). Server.log: runner ready за 10.54 s; load/chat HTTP 200; после S1 `truncated=0`, all slots idle. Завершение ответа подтверждено, автоматической выгрузки или завершения runner не выполняли.

S1 прошёл существующий parser: JSON/ожидаемые поля и типы, IDs, уникальные допустимые номера Kotlin-строк, knowledge_status=not_requested. Rules/applications пусты, поэтому проверка точных Markdown-цитат здесь N/A, а использование документации не проверено. Retrieval=0, embedding calls=0. S1 user_request_seconds=12.038916 — packing/generation/validation, не вся команда и не полный RAG. TTFT unavailable (stream=false).

RAM: system total 34,191,245,312 bytes; available до load 21,445,582,848 bytes (~19.973 GiB), после S1 20,756,725,760 bytes (~19.331 GiB). Это system before/after snapshots, не process allocation и не peak. Runner RSS/commit unavailable. VRAM snapshots также не peak.

## Предварительный смысловой review

Reviewer: assistant provisional; user review pending. **S1 semantic PARTIAL, модель не выбрана.** Полный текст ответа показан в разговоре штатным renderer; transcript/response в файлы не записывался. Синтетический вход: [CheckoutCoordinator.kt](../../../day-27-local-architecture-assistant/tests/fixtures/CheckoutCoordinator.kt).

| Критерий S1 | Оценка |
|---|---|
| Зависимости и общий смысл | Названы верно; последовательность конкретных вызовов не объяснена |
| Empty cart до charge | Missing: результат назван, ранний возврат до платежа не объяснён |
| Declined без clear/navigation | Missing: результат назван, граница выполнения не объяснена |
| Approved → clear → receipt → Success | Missing: порядок и условие не объяснены |
| Неизвестные реализации и ошибки | Partial: недостаток деталей и обработки исключений отмечен, но утверждение об отсутствии информации о взаимодействии чрезмерно широкое — вызовы зависимостей видны |

CheckoutResult верно назван интерфейсом и перечислены варианты. Явных выдуманных транзакций/rollback/retry/callers нет. Один чрезмерно широкий тезис в limitations; ключевые алгоритмические факты пропущены. Валидные номера строк не подтверждают полноту объяснения. Compose и применение Markdown не проверены.

## Учёт и остановка

Новая серия: 2/2 разрешённых load/chat attempts, оба завершены; 23.980214 s bounded client wall. История: 4 attempts / 101.313751 s. Вместе журналы: 6/32 attempts / 125.293965 s; отдельные read-only preflight/OS/metadata проверки не записывались как bounded attempts, их полное время unavailable. Новый журнал отдельно хранит ссылку на исторический счёт и явное разрешение оператора; исходный закрытый журнал не очищен и не исправлен.

Метрики: [coder-recheck-evidence-2026-10-11.json](coder-recheck-evidence-2026-10-11.json). Локальные preflight/attempt records: `.local/day29-coder-2026-10-11-*`; прежний `.local/day29-attempts.jsonl` сохранён.

S2–S6, RAG, оптимизации: NOT RUN по явной границе review. Mac M1: NOT TESTED. OpenSpec 20/30, прежний offline результат 258 passed / 1 skipped; тесты повторно не запускались, runtime не менялся. Исторические Qwen3 S1 PARTIAL / S2 FAIL и Coder TIMEOUT остаются отдельными результатами. Commit/push/archive/видео не выполнялись.
