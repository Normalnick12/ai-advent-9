## Context

См. [proposal.md](proposal.md) — Why. Существующий Python CLI в `day-27-local-architecture-assistant/` уже разделяет временный Kotlin Workspace, постоянный Markdown Knowledge и SQLite index. Extended explain использует общий JSON Schema, literal citations, loopback-only Ollama, без retries/repair/content persistence. Байтовые лимиты не являются tokenizer preflight.

Day 27: offline 101 passed / 1 skipped, live technical PASS / semantic PARTIAL. Day 28: 222 passed / 1 skipped, active 26/28, A/B incomplete из-за загрузки Qwen3.5, negative technical PASS / semantic PARTIAL, Mac NOT TESTED. Это исторические результаты, не проверка Day 29. Источники: [validation](../day-28-local-architecture-rag/validation.md), [preload](../day-28-local-architecture-rag/diagnostic-followup-2026-10-10.md), [lifecycle](../day-28-local-architecture-rag/lifecycle-experiment-2026-10-10.md).

Explore локализовал наблюдаемые отказы до готовности runner, после warm-up message; успешная предзагрузка заняла 5.064 s, последующий chat 14.479 s. Корневая причина не установлена; keep_alive=5m не проверен между A/B. Метаданные Qwen3.5 наследуют presence_penalty=1.5, top_k=20, top_p=0.95. Не интерпретировать load failure как ошибку retrieval или недостаток качества модели.

## Goals / Non-Goals

**Goals:** выбрать минимально достаточную конфигурацию по Android-смыслу и ограничениям рабочего места; объяснить стоимость загрузки/переключений; получить reviewable результаты без сокрытия отказов. Design нужен из-за воспроизводимости sampling, измерений времени/памяти и сохранения совместимости.

**Non-Goals:** доказательство production reliability или понимания всего Compose, бесконечный runtime debugging, смена embedding profile, глобальный tokenizer/framework, изменение main specs Day 27–28, автоматический переход на другой runtime. Фактические fixtures/driver/runtime создаются только при apply, не в этом proposal.

## Decisions

### 1. Identity is pinned before live; absent models remain absent during planning

Read-only `/api/tags` на 2026-10-10 дал:

| Роль | Точный tag | Полный установленный digest |
|---|---|---|
| Первый кандидат, приоритет Mac | `qwen3:4b-q4_K_M` | NOT INSTALLED / UNAVAILABLE |
| Кодовый кандидат | `qwen2.5-coder:7b-instruct-q4_K_M` | NOT INSTALLED / UNAVAILABLE |
| Только исторический контроль | `qwen3.5:9b-q4_K_M` | `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90` |

Публичные короткие hashes не подставляются вместо local digest. Наличие точных candidates — prerequisite live, не повод скачать их в proposal. Перед будущим запуском проверить installed tag/digest, local-only server, capability и quantization; hash повторно сверить после серии. Изменение digest прекращает сравнимую серию. Не вызывать исторический 9B даже для preload на первом этапе.

Сначала оставляем один runtime Ollama и embedding `qwen3-embedding:0.6b` с существующим index profile. Смена generation не требует reindex. Стабильность Qwen3 4B и преимущество Coder 7B — гипотезы, не обещания. Если кандидат не установлен, записать NOT READY и перейти только к независимой offline-подготовке.

### 2. Shared implementation with an opt-in experiment driver

Runtime остаётся в существующей утилите. Узкий driver и безопасные synthetic manifests относятся к `day-29-local-assistant-optimization/`: они вызывают общие сборку prompt, transport и validation, не копируют CLI/RAG и не являются новым пользовательским продуктом. Driver явно запрещает произвольные private inputs для сохранения fixture manifests.

Повседневный extended explain получает только `--temperature` и `--keep-alive`; num_ctx/num_predict уже доступны. Остальные фиксированные sampler settings и thinking задаются маленьким synthetic driver. Настройки — простой словарь и hash, не система профилей/реестр. Неподдерживаемые значения отклоняются; прежние вызовы сохраняют defaults и prompts.

Достаточно небольшой структуры generation settings и безопасного metrics record. Provider registry, ORM, новая БД, агенты и backend не нужны. Экспериментальные prompt variants выбираются driver, не произвольным template engine пользовательского CLI. Проверки источников не ослабляются.

### 3. Common baseline and model-specific capabilities

Исходный сравнимый профиль: num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m, stream=false, существующий extended system prompt/schema. Для обеих моделей явно задаются поддерживаемые top_k=20, top_p=0.95, min_p=0, repeat_penalty=1, presence_penalty=0, frequency_penalty=0. Это новый Day 29 baseline, не реконструкция Day 28 с inherited presence_penalty=1.5. Если значение не поддерживается, отметить unsupported и зафиксировать действующее поведение до допуска; скрыто сравнивать разные effective settings нельзя.

Для каждого известного supported sampling option записать effective value и происхождение: explicit / model metadata / documented runtime default. Сохранять canonical profile hash, model digest, prompt/schema hashes, version/backend, server concurrency и load-state observations. `unknown` допустим в отчёте, но не даёт права заявлять причинное сравнение этого параметра. Не менять native chat template модели ради искусственного равенства: прикладные system/user/schema одинаковы, template hash различен и записывается.

Thinking: исходно off при поддержке; для Coder без thinking — not_supported, поле не отправляется. Включение thinking не входит в обязательные оптимизации: это отдельный ограниченный опыт только при нерешённой смысловой задаче, с бюджетом reasoning+answer и соответствующим sampling. Температура 0 не объявляется универсальным оптимумом, одинаковый seed не гарантирует идентичность между backend/model/version.

### 4. Six scenarios and a single compact Compose input

Сохраняем прежние fixtures и [рубрику Day 28](../../../day-28-local-architecture-rag/fixtures/rubric.md). Day 29 создаёт supplement со ссылками на них, без переписывания исторического файла. Отдельный paraphrase case заменяется Compose; базовый no-knowledge case сохраняется.

| ID | Kotlin / Knowledge | Вопрос и основной критерий |
|---|---|---|
| S1 | CheckoutCoordinator / none | «Что делает этот класс?»; C1–C5, неизвестная реализация collaborators; также компактный технический запрос |
| S2 | тот же Kotlin / checkout rules | тот же вопрос; корректная роль Coordinator, success boundary, применённые R1–R3; сравнение с S1 |
| S3 | тот же Kotlin / checkout + batch scope | доказывает ли batch-rule atomic rollback интерактивного checkout; правильное неприменение чужого scope |
| S4 | тот же Kotlin / нерелевантные найденные docs | утверждённые RPO/RTO; признать отсутствие сведений, не выводить ответ из nonempty hits |
| S5 | прежняя adversarial comment mutation / weather docs | rollback при navigation failure; injection игнорируется, поведение неизвестных зависимостей не выдумывается |
| S6 | один новый Compose Kotlin-файл / один короткий Markdown | объяснить data flow, effect lifecycle и обязанности Compose/ViewModel/Coordinator |

S6: один синтетический файл порядка 60–100 строк, внутри явные `CatalogUiState`, `CatalogViewModel`, `CatalogRoute` и минимальный контракт `CatalogCoordinator`; это несколько деклараций одного входного файла, не multi-file feature. ViewModel содержит private MutableStateFlow и наружный read-only StateFlow; suspend load(itemId) делегирует координатору получение данных и обновляет state. Route получает ViewModel, собирает state через collectAsStateWithLifecycle и запускает load через LaunchedEffect(itemId, viewModel); отображение и callbacks видны в том же файле. Нет необходимости добавлять сборку Android-приложения: fixture — reviewable вход модели, не исполняемый новый экран. Не добавлять заведомо ошибочный код для получения «красивого» verdict.

Новый Markdown содержит только краткие правила: UI отображает state/передаёт действия, ViewModel владеет UI state, Coordinator организует use case без Compose-rendering; короткие документированные framework semantics, нужные для grounded explanation. Полный эталонный ответ и рубрика не передаются модели. Эта документация добавляется только к отдельной synthetic Knowledge Day 29; прежние indexes не перезаписываются.

Рубрика S6 объединяет обязательные пункты в 3–5 наблюдений существующей schema: (1) state ownership/read-only StateFlow, (2) сбор state с lifecycle, (3) effect keys/entry/cancel/re-entry, (4) delegation/data flow, (5) границы доказательств. StateFlow не гарантирует доставку каждого промежуточного значения как event queue и не обеспечивает process-death persistence сам по себе. collectAsStateWithLifecycle по умолчанию собирает при STARTED и выше, не останавливает произвольную работу производителя. LaunchedEffect связан с Composition: отмена при выходе, перезапуск при изменении ключей; обычная recomposition с прежними ключами сама по себе не перезапускает effect. Это не обещание exactly-once за жизнь приложения, автоматической отмены независимой ViewModel job или rollback. Coordinator contract не раскрывает его реализации.

Для авторского review fixture/rubric используются первичные источники: [Compose state](https://developer.android.com/develop/ui/compose/state), [side effects](https://developer.android.com/develop/ui/compose/side-effects), [UI state production](https://developer.android.com/topic/architecture/ui-layer/state-production). Нормы команды и внешние framework facts различаются в Markdown; модель не должна приписывать исходнику невидимые свойства.

### 5. Freeze generation inputs, then evaluate retrieval separately

До первого generation подготовить manifest S1–S6: source/question/schema/prompt hashes, chunk IDs, relative source/section/lines, exact selected text hash, rank/order, fixture/index profile. Выбор spans производится до просмотра ответов; существующие Day 28 chunks переиспользуются при совпадении источников/hashes. Для нового S6 получить или явно выбрать supporting spans и пометить способ selection. Это тест generation на фиксированном evidence, не новый benchmark retrieval.

Оба кандидата получают идентичные selected chunks и порядок без query embedding между их generation-запросами. Во время сравнения не менять top-k, chunker, Markdown или seed ради ответа. Model native templates могут отличаться; это часть model profile. Все массивы и ссылки продолжают проверяться общим validator.

После выбора: отдельно S2 и S6 через настоящий `explain --retrieval vector`, с существующими embed_query/search/pack. Зафиксировать отличия реально найденных chunks от frozen manifest, selected/omitted и supporting coverage. Если retrieval не принёс правило, не обвинять generation и не подменять hits вручную. Если пригодного кандидата нет, этот этап NOT RUN с причиной.

### 6. Stage gates and finite experiment budget

| Этап | Действие | Переход / остановка |
|---|---|---|
| P0 offline | Проверки совместимости, manifests/rubric/settings, metadata без inference | Отсутствующие модели: NOT READY; никакого автоматического pull |
| P1 admission | Для каждого кандидата один load-only с keep_alive=5m (60 s total), readiness digest/context, затем S1 с baseline keep_alive=5m (180 s total) | Ошибка load/stop/schema/citation: закрыть ветку; S1 success переиспользовать; admission cold только при ps not-resident до вызова, иначе reused/warm/unknown; S1 residence проверяется отдельно, preload+S1 не является обычной cold CLI latency |
| P2 quality | Остальные S2–S6 только допущенных моделей, один ответ на scenario | Смысл оценивать отдельно; технический отказ прекращает остаток ветки; новые load-only перед каждым case не делать |
| P3 selection | Review C/R/Compose facts, unsupported claims; не более одной адресной prompt-коррекции на кандидата при необходимости | Исправленная ветка — отдельный profile; сравнимый общий prompt требует одинаковой правки обоим и нового review, а не смешанной таблицы |
| P4 real flow | У выбранного кандидата S2/S6 с query embedding → retrieval → generation | Отметить loading/retrieval/generation issues раздельно; при load failure остановить ветку |
| P5 optimization | По одному фактору, на S2/S6; принимать только варианты без смысловой регрессии | Необоснованный фактор пропустить с причиной; один отказ прекращает этот вариант |
| P6 final regression | S1–S6 финального профиля; результаты неизменившихся идентичных проверок переиспользовать | User review и итог: accepted / partial / no suitable profile; Mac отдельно |

Бюджет Windows-сессии: максимум 32 generation/load-only attempts всего, включая технические probes, отменённые попытки, prompt correction и повторную итоговую проверку; максимум 90 минут суммарного bounded client wall time, включая metadata/инструментирование, без пауз review. Start резервирует попытку даже если HTTP completion неизвестен; журнал сохраняет счёт между запусками. Metadata и embeddings считаются отдельно и явно, без retries; index build однократный только для отдельной синтетической K, повторный unchanged build не нужен. В driver весь query embedding → retrieval → generation ограничен одним child deadline 180 s (строже отдельного chat deadline); индекс строится существующим CLI отдельно и его HTTP read timeout не называется total deadline. Бюджет — потолок, не план обязательно потратить все вызовы. При нехватке бюджета оставшиеся условные абляции NOT RUN; не увеличивать предел и не объявлять их проверенными. Не начинать новую операцию после достижения времени; deadline активной ограничен остатком бюджета. Не компенсировать failed attempts успешными повторами.

Один timeout останавливает профиль и требует подтверждения очистки принадлежащего ему runner перед любым следующим live. Если состояние неясно — остановить сессию. Ни kill всех процессов, ни удаление locks, ни автоматический restart Ollama не допустимы. Сходная нестабильность двух новых моделей заканчивает Day 29 live: предложить отдельную диагностику максимум 30 минут / 4 load probes с одной выбранной runtime-переменной. Эта диагностика не выполняется без отдельного согласования; повторный 9B не входит в первый этап.

### 7. One-factor optimization and memory lifecycle

Основное сравнение качества использует keep_alive=5m и Q4_K_M с независимой проверкой residency. Сравнение 5m и 0 — отдельный явно маркированный опыт; режимы не смешиваются в общей таблице без settings hash. Далее: num_predict 2048 → 1024; num_ctx 8192 → 4096 при доказанном fit; temperature 0 → 0.2; одна целевая prompt-правка только при обнаруженном дефекте и если лимит правок кандидата не исчерпан на P3. Каждая пара имеет parent profile hash, delta, фиксированный сценарий и критерий полезности до запуска. После принятия варианта он становится parent следующей пары. Это последовательные локальные решения, не глобальный оптимум.

Для keep_alive сравнить повторную generation без embeddings и отдельно полную цепочку с embeddings. Порядок warm-up/измерения и одинаковые входы фиксируются; учитывать prompt cache. Warm означает подтверждённую резидентность перед запросом и load metrics, не только значение keep_alive. При MAX_LOADED_MODELS=1 embedding может вытеснить generator; не обещать ускорение повторного vector-запроса. Серверные concurrency/load settings записывать; приложение их не меняет. Одновременное размещение двух моделей не включать молча как вторую переменную.

Fit проверять для каждого frozen payload отдельно под tokenizer/template выбранной модели: полный input, schema overhead и output reserve. Подходящий model-specific tokenizer либо подтверждённый untruncated prompt_eval_count при достаточном исходном context допустимы; если отсутствие truncation подтвердить нельзя, оставить 8192. Не вводить тяжёлый tokenizer stack ради 4096. 24 KiB не является token fit. `length` — technical failure, не успешная экономия. Меньший output limit не ускоряет уже короткий stop-ответ автоматически.

Основная серия — только Q4_K_M. Q4/Q8 одной base model/revision — отдельный опыт лишь при наблюдаемой причине и достаточном бюджете памяти/времени; иначе NOT TESTED без выводов о влиянии quantization. Thinking/runtime/driver/Flash Attention/KV-cache quantization в основной серии фиксированы.

### 8. Honest timings, resources and content-free evidence

Расширить общие metrics без сохранения content: attempt/scenario/profile ID, platform, stage, outcome/error category, selected/omitted, load state, model/digest/settings, prompt_eval_count, eval_count, load_duration, prompt_eval_duration, eval_duration, total_duration, done_reason. Добавить monotonic retrieval_wall (query embedding + search), generation_wall (chat round-trip, может включать загрузку), end_to_end_wall (вся команда). Provider durations в nanoseconds переводить явно; не складывать перекрывающиеся интервалы. Decode throughput = eval_count / eval_duration отдельно от полного пользовательского времени.

P1 preload имеет отдельные load_wall и readiness; дальнейшие запросы без preload используют provider load duration либо unavailable. Cold = модель не resident, но OS disk cache может быть warm; не очищать системный cache. Non-stream TTFT всегда unavailable. Read timeout HTTPX не является total deadline. Driver запускает ограниченную операцию в собственном дочернем Python-процессе: communicate(timeout), затем kill/wait только своего child. Это прекращает HTTP-клиента, но не доказывает завершение runner Ollama. Future/thread timeout без отмены не используется. При timeout сессия останавливается с server_cleanup=unknown до отдельной проверки оператором. Посторонние процессы не завершаются, Ollama не перезапускается. Partial durations и NOT STARTED сохраняются.

Memory: минимальные before/after snapshots штатными средствами Python/ОС и nvidia-smi без фонового мониторинга. Windows: total/available RAM и system used VRAM; недоступные runner RSS/commit — unavailable. Mac: форма для ручных pressure/swap observations с IDE, без устройства unavailable. Snapshots не peak; system VRAM не приписывается runner. Для отдельной ручной серии указывать sampled maximum и sample count/interval.

Driver выдаёт allowlisted content-free attempt records в stderr; оператор может сохранить их в отдельной ignored локальной директории. Запись opt-in, без Workspace content, query text, prompts, model responses/reasoning, absolute private paths или exception body. Synthetic manifests содержат только публичные fixtures. Каждый completed/failed/cancelled attempt сохраняется; после аварийного завершения start record без end record остаётся incomplete. NOT RUN создаётся с причиной stage gate/budget, а не как успешная попытка. Итоговый report содержит все counts, unavailable и reviewer verdicts, не transcripts.

### 9. Selection and practical acceptance

Критерии заранее фиксируются в рубрике: существенные C1–C5; R1–R3 и scope; отсутствие выдуманных interface/guarantees/callers; отказ от unsupported RPO/RTO; все перечисленные S6 lifecycle/responsibility distinction. Точные цитаты проверяются механически, entailment/application — человеком. Оценка каждого факта: supported / partial / unsupported / omitted; critical false claims перечисляются отдельными ID. Assistant review provisional, user review pending до фактического просмотра.

Принимаемый профиль должен завершить все шесть semantic scenarios без critical unsupported claims и покрыть обязательные факты; не требуется слово-в-слово эталон. S2 должен добавить поддержанное архитектурное объяснение без потери важных S1 facts. Сначала correctness/reliability, затем latency/memory среди прошедших; агрегированный score не скрывает критическую ошибку. Если кандидат только один допущен, это single-candidate observation, не победа по качеству над отсутствующими ответами. Если ни один не прошёл — no suitable profile с причинами.

Предварительные UX targets из Explore: короткий ответ cold end-to-end <=60 s, repeated end-to-end <=30 s, отсутствие заметной помехи редактированию/навигации IDE и устойчивого роста pressure/swap. Это цели практической приёмки, не technical deadlines и не измеренные обещания. Превышение записывается отдельно как latency limitation; предел не меняется после просмотра результата. Резерв keep_alive помогает только при фактической резидентности. Малые серии дают median/max/count, не p95 и не production SLA.

### 10. Separate Mac validation and documentation

На доступном разрешённом M1: metadata/digest/settings, focused offline tests/FTS5, один compact admission, frozen S1–S6 и реальный S2/S6; максимум 12 load/chat calls, 45 минут live, тот же stop-on-failure. Android Studio открыта на фиксированном проекте, нагрузка indexing/build отмечена; baseline без inference, затем те же действия редактирования/навигации. Эмулятор выключен для базового результата; его совместная работа — отдельный optional profile. Давление памяти и прирост swap оцениваются серией, единичный ненулевой swap не объявляется failure.

Без Mac/разрешения task остаётся unchecked PENDING / NOT TESTED. Windows outcome можно завершить отдельно; никакого переноса measured speed на M1. Если Mac использует другой backend/модельный digest, результаты получают отдельный platform profile.

Day README создаётся при apply по трём разделам из AGENTS.md с проверенными итогами либо честным NOT TESTED. Setup/CLI flags/check commands — в README существующей утилиты; корневой README получает упорядоченную относительную ссылку. Подробный experiment report — в change artifacts, история Day 27–28 не редактируется. Условные неисполненные эксперименты отмечаются SKIPPED/NOT RUN с причиной; реальный pending Mac не превращается в completed checkbox.

## Risks / Trade-offs

- [Одинаковое семейство API не гарантирует одинаковый sampler/template] → effective config, native template hash и supported/unknown поля; не выдавать несовпадающие профили за чистую абляцию.
- [Frozen evidence завышает реальную пользу] → отдельная обязательная end-to-end проверка retrieval после выбора.
- [4B проходит checkout, ошибается на Compose] → S6 обязателен, один prompt correction на кандидата, затем limitation/другой кандидат.
- [keep_alive скрывает плохой cold start] → cold и warm outcomes раздельно; no automatic retry.
- [Ограниченный budget не позволяет проверить все варианты] → приоритет semantic + real flow + final regression, необязательные оптимизации пропускаются явно.
- [Память кратковременно превышает sampled maximum] → маркировка метода, без заявления истинного пика; IDE pressure отдельно.
- [Одно устройство/малый набор] → smoke evidence, отдельный Mac outcome, без утверждений обо всех Kotlin/Compose-модулях.

## Migration Plan

1. После review реализовать opt-in settings/metrics и synthetic driver поверх общей утилиты; старые defaults и source contracts остаются.
2. Пройти focused offline tests, включая legacy payloads/privacy/stop logic, до любого live. Не нужны backend, Android build или Gradle UI tests для Python изменений.
3. Выполнить только разрешённые live stages с установленными моделями, выбрать или отклонить профиль, записать evidence. Profile не становится новым default автоматически.
4. Rollback оптимизации — убрать явные новые опции/профиль; SQLite migration/reindex не требуются. Исторические файлы и пользовательские данные не восстанавливаются из новых reports, потому что не изменялись.

## Дополнение 2026-10-11: compact-evidence-v1, только offline до review

После принятого отказа explain-evidence-v1 пользователь отдельно разрешил минимальный эксперимент контракта. Это совместное изменение schema и необходимых инструкций формата, не однофакторная оптимизация и не следующая коррекция отклонённого prompt. Обычный extended контракт, baseline Day 29 и исторические profiles сохраняются.

Один opt-in `contract_variant=compact-evidence-v1` в существующем synthetic driver. Небольшой helper этого driver содержит schema, parser и renderer; это не новый CLI, backend или framework. Ответ: `code_observations[{text,lines}]`, `documented_applications[{rule,text,lines,citations[{chunk_id,quote}]}]`, `assumptions[]`, `limitations[]`. В каждом documentary object различаются формулировка правила и интерпретация применения; Kotlin lines и точная Markdown citation находятся рядом. Пустой documented_applications допустим. Перекрёстных ID и knowledge_status в ответе модели нет; Python нумерует элементы при отображении и добавляет status из retrieval mode/selected chunks. Статус candidates_provided не доказывает релевантность.

Базовая system instruction адаптируется только к этим полям и runtime-owned status. Не добавлять explain-evidence-v1, эталон S4/S6 или подсказки Compose/RPO. Отдельно закрепить prompt/schema hashes и parent frozen manifest; model/sampling остаются прежними. Variant не смешивается с baseline/correction в журналах и candidate selection. Runtime и renderer получают authoritative metadata только из выбранных chunks. Parser требует done=true/stop, полный JSON, точные поля/типы, nonempty text, уникальные integer lines 1..N (bool запрещён), существующие selected chunks, непрерывные буквальные quotes <=400 символов без duplicate citations. Unknown fields, IDs/status, length, malformed JSON отклоняются без repair. Нет автоматического поиска supporting quotes или перепривязки утверждений.

Offline: сравнить все baseline payloads до/после, проверить variant delta только system/schema; mock worker/renderer и негативные ссылки/статусы/завершённость; privacy sentinels не попадают в metrics/journal. Пока только offline; отдельный review обязателен до live. Потенциальная серия — один Coder S4, затем S6 при technical PASS, прежние frozen inputs/settings, GPU criterion v2, deadlines и общий budget; первый technical failure останавливает ветку. Полный live launcher/новый registry не нужны. Исторический explain-evidence-v1 закрыт, но его код/evidence не переписываются.

## Open Questions

- Полные digests кандидатов будут известны после их отдельной установки и metadata preflight; отсутствие значений сейчас намеренно блокирует live, не planning.
- Доступность и разрешения на M1, версия macOS/Android Studio и фактическая память фиксируются на target-device этапе.
- Конкретный supported memory sampler зависит от доступных OS инструментов; unavailable допустим, вывод о memory suitability без достаточных наблюдений остаётся pending.
