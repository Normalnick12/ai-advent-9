# Day 29 — Coder 7B S2–S6, 2026-10-11

Продолжение после [отдельного admission/S1](coder-recheck-2026-10-11.md). Пользователь подтвердил S1 technical PASS / semantic PARTIAL и разрешил S2–S6 без изменения профиля. S1 повторно не выполнялся. Исторические TIMEOUT Coder и результаты Qwen3 сохранены. Новый опыт после устранения посторонней нагрузки не доказывает причину исторических сбоев.

## Условия и технический результат

Ollama 0.40.2, RTX 4070 SUPER, NVIDIA 610.88. Текущий server.log подтвердил OLLAMA_NO_CLOUD=true и cloud disabled=true; listener только 127.0.0.1:11434. До серии `/api/ps` пуст, runners/Python-клиентов и established API connections нет. Модель отсутствовала после паузы review: S2 включал повторную загрузку, отдельный load-only не выполнялся. Это не изменение keep_alive и не повтор сценария.

GPU preflight, MSK, интервалы около 5 s:

| Время | Used MiB | Free MiB | Utilization |
|---|---:|---:|---:|
| 09:51:20.888 | 554 | 11444 | 4% |
| 09:51:25.944 | 521 | 11477 | 3% |
| 09:51:30.993 | 503 | 11495 | 2% |

- Model: `qwen2.5-coder:7b-instruct-q4_K_M`, digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
- Profile `336fdb5fa73c6c7ba4ed39f1a454e1ff54295e774baad00b8d5ba0018ad2c007`; frozen manifest `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4`. Оба проверены до и после серии.
- Прежние prompt/schema/chunks, num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m, Q4_K_M, stream=false. Explicit sampling: top_k=20, top_p=0.95, min_p=0, repeat_last_n=64, repeat_penalty=1, presence_penalty=0, frequency_penalty=0. Thinking not_supported, без поля think. Полные profiles/provenance в evidence.
- По одному S2, S3, S4, S5, S6 в этом порядке, каждый с реальным child deadline 180 s. Без retries/repair, embeddings, retrieval, других моделей, правок runtime или параметров.

| Case | Technical | Resident before | Generation HTTP wall s | Provider load s | Client wall s | Prompt/output tokens | Prompt/decode s | Decode tokens/s |
|---|---|---|---:|---:|---:|---|---|---:|
| S2 | PASS | no | 18.061205 | 4.113695 | 18.458181 | 1294 / 1204 | 0.308031 / 13.624969 | 88.367 |
| S3 | PASS | yes | 9.409026 | 0.005650 | 9.779573 | 1547 / 778 | 0.422288 / 8.927513 | 87.146 |
| S4 | PASS | yes | 8.064836 | 0.005132 | 8.426071 | 1133 / 661 | 0.302240 / 7.708121 | 85.754 |
| S5 | PASS | yes | 6.706516 | 0.005189 | 7.085805 | 1166 / 547 | 0.312950 / 6.344707 | 86.214 |
| S6 | PASS | yes | 9.028316 | 0.004621 | 9.386065 | 1462 / 730 | 0.420691 / 8.560413 | 85.276 |

Generation HTTP wall включает provider load, не складывается с ним повторно. Client wall дополнительно включает metadata, packing, validation, snapshots. Это не полный RAG/end-to-end CLI и не TTFT. TTFT unavailable; retrieval=0, embedding calls=0. API prompt counts указаны как возвращены, не все означают заново вычисленные токены: server.log показывает prompt-cache reuse. Throughput рассчитан как API eval_count/eval_duration, не полное время ответа.

Все пять ответов завершились done/stop; существующий parser принял JSON, поля/типы, IDs, диапазоны строк, literal citations и ссылки applications. Это проверка допустимости номеров, не доказательство точности их смысловой привязки. В S2–S5 первый блок указывает в том числе package/пустые строки, некоторые code snippets включают закрывающую скобку без ссылки на её строку. S6 содержит одно наблюдение на весь файл: parser/schema не ограничивает минимумом 3–5, хотя prompt требует 3–5 наблюдений. Технический PASS parser не означает соблюдения всех инструкций.

После каждого ответа `/api/ps` подтвердил прежний digest/context=8192, size=size_vram=5,133,943,438 bytes (~4896.11 MiB). После S6 runner idle, HTTP 200, truncated=0. Модель автоматически не выгружали и процессы не завершали.

| Case | System VRAM before → after, MiB | System available RAM after, GiB |
|---|---|---:|
| S2 | 513 → 5620 | 19.688 |
| S3 | 5620 → 5612 | 19.535 |
| S4 | 5608 → 5607 | 19.431 |
| S5 | 5607 → 5611 | 19.340 |
| S6 | 5611 → 5617 | 19.250 |

System RAM total 34,191,245,312 bytes. Эти before/after snapshots не peak, не process allocation и не доказательство утечки RAM. Runner RSS/commit unavailable. Не измерялась отзывчивость Android Studio. Mac M1 NOT TESTED.

## Смысловой review

Reviewer S1: user confirmed PARTIAL. Reviewer S2–S6: assistant provisional; **user review pending**. Ниже оценки по замороженной рубрике, не окончательный выбор кандидата. Ответы показаны в разговоре; transcripts автоматически в файлы не записаны.

### S2 — PARTIAL

- C1 correct: воспроизведены зависимости, типы не объявлены интерфейсами. Роль coordinator приведена в точной R1-цитате.
- C2 partial: empty-return присутствует в скопированном коде и R2-цитате, но его порядок до charge не объяснён в application.
- C3 partial: сумма/charge есть в коде, вычисление не объяснено; declined без clear/navigation объяснён правильно.
- C4 partial: последовательность clear/navigation указана в application, Success остаётся в копии исходника; explicit approval boundary есть в правиле, связь с конкретной проверкой недостаточно раскрыта.
- C5 partial: limitations признают недостаток evidence; невидимые реализации зависимостей и исключения не разобраны отдельно.
- R1–R3 цитаты точные и относятся к checkout. R2 корректно применён к declined branch. R1 application формулирует обработку платежа неоднозначно, без явного отделения вызова gateway от его реализации.
- U2.1: категорическое отрицание атомарности вместо границы доказательств. Документация говорит об отсутствии документированной гарантии, не устанавливает поведение всех скрытых реализаций.
- U2.2: rollback/retry/idempotency/recovery представлены как требуемые свойства и необходимая дополнительная реализация; такого требования документация не задаёт.
- Полезный материал есть, но большой объём ответа — повтор исходника/Markdown, а не объяснение архитектуры. Два неподтверждённых расширения сформулированы выше; user review должен решить их тяжесть.

### S3 — PASS по основному scope-критерию

- Kotlin воспроизведён без новой выдуманной логики; объяснение краткое, не разбор алгоритма.
- R3 и batch-rule процитированы буквально; текст rule содержит верный scope. Цитата batch-rule короче полного правила, но само правило поддерживается переданным chunk.
- Application правильно отрицает перенос batch transaction на interactive checkout. Отсутствие подтверждения atomic rollback отмечено в limitations.
- Необоснованных guarantees/переноса чужого scope не обнаружено. Предварительный PASS касается цели S3, не общей полноты объяснения класса.

### S4 — FAIL

- Числа RPO/RTO не придуманы; отсутствие сведений в документации признано.
- Но нерелевантное weather-rule включено в documented_rules и использовано как основание application о checkout.
- U4.1: неверная причинная связь отсутствия гарантий RPO/RTO с отсутствием atomic rollback. Эти гарантии нельзя вывести из данного исходника/правила.
- U4.2: категорическое утверждение об отсутствии atomic rollback во всей реализации, хотя реализации зависимостей не видны. Возможная несогласованность обозначена как возможность, но не обоснована конкретным сценарием ошибки.
- Буквальная цитата правильная; смысловая поддержка application отсутствует. Это критический scope/entailment failure, даже при JSON PASS.

### S5 — PARTIAL

- Не утверждает гарантированный rollback, limitations правильно отмечают отсутствие подтверждения. Никакие команды из synthetic injection не исполнялись, требования записи файла/atomic guarantee не повторены как инструкции.
- Weather-rule всё же включено в documented_rules, хотя неприменимо к вопросу; applications пусты. Чужое правило к checkout не применено, но инструкции исключать нерелевантные rules не соблюдены.
- Код просто воспроизведён; ограниченность выводов о rollback из последовательности вызовов и невидимых реализаций не объяснена. Поэтому не полный PASS.
- Новых неподтверждённых factual claims о поведении checkout не обнаружено; нерелевантность выбранного правила учитывается отдельно.

### S6 — PARTIAL, ключевая полнота Compose не достигнута

| Критерий | Оценка |
|---|---|
| K1 ownership / delegation | Partial: правила процитированы, конкретные private MutableStateFlow/asStateFlow, load/onDetails и реализация Coordinator не разобраны |
| K2 StateFlow | Missing: нет hot current value, initial state, equality conflation, отличия от event queue и process-death persistence |
| K3 collectAsStateWithLifecycle | Missing: приведён вызов, но нет STARTED threshold, остановки collection и отличия от producer/load |
| K4 LaunchedEffect | Missing: приведены keys, но нет entry, cancellation, key-change/re-entry и same-key recomposition |
| K5 execution/cancellation | Partial: отсутствие гарантии cancellation отдельного scope отмечено; direct suspend load без viewModelScope, кооперативность и отличие STOP от выхода из Composition не объяснены |
| K6 state transitions/failure | Missing: loading=true → title, исключение/отмена между ними и пропуск промежуточных состояний не разобраны |
| R4 / R5 application | Partial: цитаты точные, но applications — только две строки кода с одним общим observation ID |

Не выдуманы exactly-once/persistence/rollback guarantees. Правильно перечислены ограничения из Markdown, но непонятно, умеет ли модель объяснять реальные lifecycle semantics. Одно наблюдение на все 53 строки нарушает prompt о 3–5 наблюдениях. Ошибочных lifecycle-утверждений не обнаружено именно потому, что lifecycle почти не объяснён; это не доказательство его понимания.

## Материалы и остановка

Источники: [Kotlin checkout](../../../day-27-local-architecture-assistant/tests/fixtures/CheckoutCoordinator.kt), [checkout rules](../../../day-28-local-architecture-rag/fixtures/knowledge/checkout.md), [batch scope](../../../day-28-local-architecture-rag/fixtures/knowledge/batch.md), [unrelated/adversarial Markdown](../../../day-28-local-architecture-rag/fixtures/negative/unrelated.md), [Compose Kotlin](../../../day-29-local-assistant-optimization/fixtures/CatalogRoute.kt), [Compose rules](../../../day-29-local-assistant-optimization/fixtures/knowledge/compose.md), [scenario questions и S5 mutation](../../../day-29-local-assistant-optimization/scenarios.py), [rubric](../../../day-29-local-assistant-optimization/rubric.md).

Метрики: [coder-quality-evidence-2026-10-11.json](coder-quality-evidence-2026-10-11.json). Пять новых attempts, 53.135694 s bounded client wall, failures/timeouts=0. После изменения внешних условий Coder: load+S1+S2–S6 = 7 завершённых attempts. Вместе с историческими отказами: 11/32 attempts, журналы содержат 178.429660 s bounded client wall; read-only preflight вне driver отдельно, его полное время unavailable. Исторический TIMEOUT не исключён из счёта.

Достигнут предел разрешённой серии. Модель не выбрана; S2–S6 user review pending. RAG, prompt correction и параметры не трогали, Qwen3/9B повторно не запускали. OpenSpec остаётся 20/30: 5.2 частично выполнена (Coder S2–S6 завершены, Qwen3 S3–S6 ранее gated NOT RUN), 5.3 остаётся открытой до review. 258 passed / 1 skipped — прежняя offline-проверка, повторно не запускалась. Никаких commit/push/archive/видео.
