## Context

Мотивация — [proposal.md](proposal.md). Текущая реализация уже отделяет durable conversation от active context:

- backend/app/agent.py: SimpleAgent.run_turn использует ContextPolicy и AgentSession.commit; generate выполняет generation/validation без commit.
- backend/app/agent_sessions.py: AgentSessionManager загружает session из ConversationStore; cache и busy существуют только в процессе.
- backend/app/sqlite_conversation_store.py: sessions/messages, atomic pair transaction, строгая загрузка history. Новые таблицы не требуют изменения схемы старых таблиц.
- backend/app/conversation_summary_store.py демонстрирует отдельный store на connection raw store.
- Day 10 fact reducer даёт полезные идеи typed updates/provenance, но Fact/Day10Store завязаны на shared/A/B, exact fixtures и восемь шагов. Их не переносим.
- Android Day 10 даёт образец compact cards, inspector, latest response, отдельного dashboard и recovery без replay.

Design необходим: изменение проходит через storage, Agent context, API и Android и вводит новые ownership boundaries.

## Goals / Non-Goals

**Goals:** согласованный durable снимок трёх слоёв и identities; reuse generation lifecycle; доказуемое исключение inactive данных и overridden preference; раздельное наблюдение selection и response.

**Non-Goals:** перечисленные в proposal исследовательские расширения; generic memory schema/priority registry; архивный UI/reactivation; delete/reset; durable dashboard/results; многопользовательская авторизация и multiple-worker deployment. Наличие inactive rows не означает поддержку переключения на них.

## Decisions

### 1. Composition of the existing Agent subsystem

MemoryExperimentService координирует mutations, identity binding, immutable snapshots и experiment. Обычный Send вызывает существующий SimpleAgent.run_turn с реальным AgentSession. SimpleAgent остаётся владельцем generation/validation и atomic user/assistant commit. Verification вызывает SimpleAgent.generate без session commit.

MemoryContextPolicy адаптирует небольшой чистый builder к existing ContextPolicy.prepare. Под owner guard service получает снимок, создаёт immutable per-operation policy с этим снимком и передаёт её легковесному SimpleAgent с Day 11 config. prepare проверяет, что session/history соответствуют снимку. Один builder используется и для ordinary Send, и для verification; normal current message добавляется существующим run_turn, verification query — перед generate. Нельзя хранить shared mutable last_context в общей policy: inspector получает снимок конкретной операции.

Это позволяет оставить run_turn без ветки if day11. Отдельный StatefulAgent с собственным provider/commit cycle отвергнут как дублирование. Если понадобится небольшой совместимый helper в общей инфраструктуре, его defaults и старые payloads остаются неизменными.

### 2. Owners, tasks and conversations are independent

Один локальный demo memory owner на Day 11 database; это осознанное учебное ограничение, не user authentication. memory_owner_id, task_id, session_id — независимо созданные UUID. Stable owner создаётся только explicit Initialize; повторный Initialize возвращает уже существующий binding, не очищая память.

Task owns Working; session owns transcript; owner owns Long-term. Каждая session имеет immutable task association. Current binding выбирает одну task и одну session этого owner. Нельзя выбирать session из другой task/owner и нельзя автоматически активировать старую identity.

Read current без initialized owner возвращает not_initialized без записи. Android не является источником binding: он читает server current state после открытия, recreation/recovery и restart, не восстанавливает current pointers из старого локального cache.

### 3. Isolated SQLite with small structured states

Предлагаемая база: .local/memory-layers/day11-v1/memory.sqlite3; путь проверяется на отличие от всех старых Day namespaces. Это schema namespace, не путь, автоматически меняющийся при смене alias модели.

Таблицы:
- sessions / messages: существующая схема ConversationStore, raw pairs и порядок;
- memory_owners: owner identity и singleton demo slot;
- working_memory: task_id PK, owner_id FK, data JSON; строка представляет task identity даже при data={};
- long_term_memory: owner_id PK/FK, data JSON;
- session_tasks: session_id PK/FK, task_id FK; durable ownership старых conversations;
- memory_bindings: owner_id PK/FK, current_task_id, current_session_id, revision.

Раздельные WorkingMemoryStore и LongTermMemoryStore используют одну connection и coordinator транзакций с raw store. JSON содержит только небольшой typed allowlist: Working task/current_architecture/release_marker; Long-term project_code/preferred_architecture. Значения — непустые строки с ограничением длины; отсутствие ключа обозначает unknown. Set требует value; remove не принимает value и для отсутствующего ключа является no-op. Null не является ещё одним вариантом значения/отмены. Arbitrary nested JSON и keys других слоёв отклоняются.

FK плюс проверка binding/task/session ownership внутри транзакции и при restore обеспечивают согласованность. Не нужна отдельная таблица knowledge или observations. Schema/version mismatch и повреждённые ссылки дают ошибку без repair, fallback к чужой базе или silent recreation.

Альтернатива единой memory table с layer discriminator отвергнута ради ясного разделения ownership и lifecycle; отдельные базы для каждого слоя усложнили бы atomic New Task. JSON предпочтён множеству универсальных key/value/type таблиц из-за малого фиксированного сценария.

### 4. Lifecycle transactions and runtime cache

| Operation | Durable effect |
| --- | --- |
| Initialize | При отсутствии demo owner атомарно создать owner, пустые Long-term/Working, task, session, session association и binding |
| New Conversation | Создать новую пустую session в current task и переключить binding; прежняя session/messages остаются |
| New Task | Создать пустую task/Working и session, association и переключить binding; прежняя task и все её sessions остаются |
| Clear Long-term | Заменить только current owner Long-term data на {}; сохранить ownership/identities |
| Restart | Прочитать существующий binding и активные слои; восстановить свободный runtime lifecycle без provider calls |

Binding revision меняется вместе с effective explicit mutations/lifecycle; no-op не меняет revision. Short-term identity+confirmed message positions/content входят в snapshot fingerprint отдельно, поэтому pair commit не требует связывать ordinary Agent commit с новой revision-транзакцией.

Lifecycle SQL выполняется одной транзакцией shared connection без вызова AgentSessionManager.create/delete внутри уже открытой transaction. Координатор вставляет новые sessions через небольшой transaction-aware storage helper/adapter. После COMMIT manager.get(new_session_id) загружает созданную session обычным путём. Старые cached sessions могут оставаться валидными inactive objects; service запрещает операции по ним через проверку binding. Manager.delete и Session.close не вызываются для New.

При rollback cache/binding не переключаются и новых runtime sessions нет. Если COMMIT прошёл, а HTTP ответ потерян, следующий read получает durable current; не повторяем lifecycle автоматически. При сбое runtime publication binding перечитывается прежде следующей операции. Нет незаконченной SQL transaction во время await provider.

Так cache не нужно разрушительно инвалидировать при New. Расширять SessionManager методом destructive replace не требуется. Альтернатива последовательных create+update commits отвергнута: возможны частичный task/binding и неверный current state.

### 5. Explicit mutations and concurrency

API Day 11 имеет отдельный prefix /api/v1/memory-layers. Минимальные действия: read current/catalog, initialize, explicit set/remove Working/Long-term, normal Send, New Conversation, New Task, Clear Long-term, verify A–E. Exact URI DTO names уточняются при реализации, но contracts strict: нет client history, instructions, model, expected answers или client-selected active identities.

Working/Long-term mutation принимает explicit layer, allowlisted key, operation и value только для set. Endpoint/service не классифицирует natural language. Chat сам по себе не меняет structured states. Explicit writes durable независимо от последующей generation failure.

Мутации, normal Send и verification сериализуются одним guard на demo owner, у normal Send дополнительно остаётся existing session guard. Клиент передаёт expected snapshot_id; fingerprint включает identities, binding revision, structured data и confirmed transcript. Stale/inactive target даёт conflict до provider/storage effects. Read возвращает согласованный committed state и busy отдельно. После неизвестного HTTP outcome выполняется read, не retry POST. Busy/requests/results не persistent.

Single worker соответствует существующей AgentSession модели. Один guard проще Day 10 concurrent A/B evaluation slots: здесь параллельные probes не нужны. Hidden SDK/application retries, summarization, extraction, input-token count requests отсутствуют.

### 6. Context assembly and the one precedence rule

Builder получает immutable current snapshot. Full History включает только current session, без summaries, windows, inactive task/session sources и previous probe outputs.

Порядок input:
1. фиксированные Day 11 instructions;
2. user-role structured LONG_TERM data block;
3. user-role structured WORKING data block;
4. полный подтверждённый transcript current session с исходными roles/text;
5. точный current user либо один и тот же verification query.

Blocks маркированы как данные, не инструкции; значения не интерполируются в instructions. Synthetic blocks не записываются в raw history. Для пустых слоёв передаётся empty data block, чтобы отсутствие было явным. Transcript остаётся разговором, не командой автоматической записи structured memory.

Ровно одно правило: наличие Working current_architecture исключает preferred_architecture из передаваемого Long-term block; Working значение остаётся. При отсутствии override preferred_architecture передаётся; при отсутствии обоих effective architecture unknown. Stored Long-term не меняется. Никакого ConflictResolver/RuleRegistry.

Diagnostics отдельно сохраняют stored preference и exclusion reason working_override. Это описание не отправляется provider: иначе MVVM вновь попадёт в input через inspector metadata. Provider получает только selected blocks/transcript/query. UI знает both stored и selected, модель — selected.

Day 11 instructions объясняют scopes, unknown/null, general default при пустой task и запрет выдумывать exact fields. Старые instructions о памяти только текущего диалога не наследуются дословно. Arbitrary semantic conflicts в natural language не решаются новым движком.

### 7. Controlled scenario without self-contamination

До заполнения structured layers: initialized current Working/Long-term пусты, active transcript пуст. Один настоящий ordinary Send с exact fixture `error_title=Сбой-47` и просьбой кратко подтвердить создаёт U/A pair. Затем отдельные explicit действия записывают Long-term ORION-17/MVVM и Working Checkout/MVI/RC-42. Так normal seed reply не получает structured markers и не переносит их в Short-term до A.

Fixed verification query:
«По доступным данным укажи project_code, release_marker, current_task, effective_architecture, last_error_title и предложи один краткий next_step. Если точное значение неизвестно, верни null. При отсутствии текущей задачи не придумывай её; доступную архитектуру профиля укажи как общую рекомендацию.»

Structured output: пять required nullable string fields с этими именами, плюс required string next_step; extra fields запрещены. Schema задаёт types, не enums с expected values. Fixtures, oracle и stage labels не добавляются в instructions/query/schema. Fields сравниваются точно, включая case/пунктуацию; null проверяется как отсутствие, не как строка "unknown". next_step показывается человеку и не даёт exact score.

| Stage | Operation before probe | Expected fields: project / release / task / architecture / error |
| --- | --- | --- |
| A | Завершить explicit setup | ORION-17 / RC-42 / Checkout / MVI / Сбой-47 |
| B | Remove only Working current_architecture | ORION-17 / RC-42 / Checkout / MVVM / Сбой-47 |
| C | New Conversation | ORION-17 / RC-42 / Checkout / MVVM / null |
| D | New Task | ORION-17 / null / null / MVVM / null |
| E | Clear Long-term | null / null / null / null / null |

Все пять probes используют generate без commit. Runtime step labels сами по себе не доказывают stage: coordinator проверяет actual snapshot preconditions и remembered before/after identities для lifecycle observations. Если snapshot не соответствует сценарию, результат помечается scenario_not_applicable, не успешной проверкой. Нет полноценной state machine.

Availability строится из exact assembled source manifest до generation: structured selected fields и exact Short-term assertion в текущих selected messages. Доступность означает однозначную поддержку поля источниками, а не substring в diagnostics/expected fixture. Противоречащие точные assertions в transcript показываются как conflict; raw history не обрезается ради зелёного score. Fake responses не подставляют live результаты.

Успешный полный прогон — 1 normal seed generation + 5 explicit verification generations, 0 extraction/summary/count calls. Один и тот же model/settings во всех A–E; разумная стартовая конфигурация — существующий gpt-4o-mini с reasoning_effort=None, service_tier=default, truncation=disabled, max_output_tokens=1200. Это проектное предположение, не исследование актуальной линейки моделей. Alias/settings фиксируются в metadata; недоступность provider показывается ошибкой без silent model fallback.

Повторный проход после E: explicit New Task (Long-term уже пуст), затем seed и explicit записи. Начинать setup при непустых structured states нельзя без явной подготовки: она использует New Task и при необходимости отдельный Clear Long-term, не скрытый reset. Старт нового локального прохода очищает только runtime dashboard.

Restart acceptance выполняется на непустом A-state до B: зафиксировать IDs/слои, перезапустить backend, read current, сравнить exact values и history; счётчик provider calls не растёт. Live A–E labels/results могут потеряться при process restart и не восстанавливаются как measurements. При необходимости продолжить сценарий явно выбрать подходящий этап по actual state; loss observations не требует повторять generation.

### 8. Independent observations and compact Android UI

Memory snapshot — durable state; context preview/observation — runtime view. Immutable observation содержит snapshot_id, identities, stored/selected refs, exclusion reasons, exact assembled messages и fixed config/schema metadata, provider outcome, parsed fields, raw response и две независимые per-field checks:
- input availability/expected absence;
- output exact match/expected null.

Model mismatch не меняет storage/selection result. Failed/refused/incomplete/invalid structured output означает usage check unavailable/invalid; successful availability остаётся видимой. Snapshot assembly violation останавливает dispatch, а не отправляет чужие источники.

Android получает отдельные DTO/repository/ViewModel/screen через существующий AppContainer. Main: Short/Working/Long cards, current step, explicit action с target layer, latest response, A–E dashboard. Inspector раскрывает stored -> selected/excluded + reason -> exact request -> raw/parsed reply. Inactive inventories доступны как counts/refs для демонстрации сохранности, без загрузки старых текстов в prompt и без archive browser.

Dashboard и last observation живут в ViewModel/runtime; навигация и Activity recreation сохраняют их в процессе. Cold start/read restore не создаёт фиктивных evaluations. Старый observation после mutation помечается previous snapshot. Exact input inspector не содержит secrets/headers.

### 9. Validation boundaries

Deterministic backend tests с temporary SQLite и recording fake client проверяют storage, source selection, strict contracts, atomic lifecycle rollback, restart/cache consistency, exact payloads, calls и no-commit probes; fake не доказывает live model influence. Отдельные JVM tests проверяют DTO validation, state/recovery/no replay. Targeted Compose tests — cards, actions, inspector, dashboard и navigation.

Для live acceptance фиксируются actual values/response по A–E и отдельно restart без generation. Результат не предрешён; неверный model field при правильном input записывается как model-use failure, а не скрывается. Day README содержит только подтверждённые наблюдения; архитектура и технические проверки остаются в component docs/OpenSpec.

## Risks / Trade-offs

- [Assistant повторяет данные и создаёт вторую копию в Short-term] -> seed до structured writes, probes без commit, exact manifest и проверка конфликтов; Clear Long-term не обещает стереть упоминания из transcript.
- [Inactive memory продолжает занимать место] -> допустимо для малого сценария; GC/retention/reactivation вне scope.
- [HTTP outcome неизвестен] -> read current и explicit recovery; никакого replay, нового owner вместо старого или optimistic success.
- [Lost dashboard после restart] -> явно unavailable observations при сохранных memory/identities; restart acceptance сравнивает только durable state.
- [Single-owner/single-worker guard] -> явная граница локального эксперимента; не заявлять production concurrency/auth.
- [Exact score не равен полезности] -> пять узких checks отдельно от свободного next_step и человеческой оценки; один прогон не закономерность.
- [Случайное изменение shared Agent primitives] -> минимальные additive storage hooks при необходимости и existing regression payload/call-count tests.
- [Known marker может быть угадан] -> exact marker каждого слоя, null stages, проверка actual sources; только ответ без source manifest не считается доказательством.

## Migration Plan

1. Реализация добавляет только Day 11 schema/API/config и Android entry; старые базы и contracts не мигрируются.
2. Startup открывает Day 11 storage, но не создаёт owner/session и не вызывает provider; Initialize только explicit.
3. При schema corruption/mismatch показать безопасную ошибку, не пересоздавать durable memory.
4. Rollback приложения отключает Day 11 wiring/card; отдельная база остаётся на диске. Не выполнять drop/delete старых данных.
5. До реализации выполнить review этих planning artifacts; apply — только отдельным запросом пользователя.
