## Context

Мотивация и capabilities — в [proposal.md](proposal.md). Explore и уточнения пользователя приняты; этот change содержит только планирование.

Опорные точки inspected repository:

- `backend/app/agent.py`: `run_turn()` вызывает context policy, generation и немедленно commit пригодного completed ответа; `generate()` не получает session/store и не имеет commit path. Его проверка пригодности текста не является semantic Validator. `probe()` относится к overflow lab, для Day 13 используется `generate()`.
- `agent_sessions.py`: session guard и `AgentSession.commit()` сохраняют atomic pair, публикуя runtime history только после persistent append.
- `memory_selection.py`: shared active-only selection, Working architecture override и snapshot-checked `MemoryContextPolicy`. `ContextPolicy` принимает session/history; не расширяем его до resolver всех подсистем.
- `memory_store.py`: New Conversation сохраняет task и inactive history, New Task создаёт новую task/session; schema проверяет точный состав таблиц и user_version=11. Добавление State table в этот файл потребовало бы менять существующий adapter.
- `profiles.py`, `profile_store.py`, `sqlite_profile_store.py`, `profile_instructions.py`: отдельные typed Profile, binding/revisions, layout-independent persistence и pure renderer.
- `personalization_service.py`: разрешение coherent Memory/Profile snapshots под одним guard, request-scoped SimpleAgent, раздельные Send/probe. `personalization_observations.py`: actual arguments capture вокруг `LlmClient.complete`.
- `llm_client.py`: `ConversationMessage` имеет user/assistant roles, а `AgentConfig.instructions` — существующий канал behavioral instructions. OpenAI adapter остаётся за LlmClient.
- `main.py` и Android `AppContainer`: явные composition roots и изолированные Day namespaces. Android Day 12 уже имеет read/recovery без replay и immutable inspector receipts.

## Goals / Non-Goals

**Goals:** самостоятельный deterministic FSM core, durable task position, проверяемые lifecycle boundaries, реальное применение State к ordinary conversation и будущая возможность orchestration без переписывания FSM. Детали fixtures и проверки модели не входят в domain. Подробные observable contracts находятся в delta specs.

**Non-Goals:** не расширять SimpleAgent State-specific branches, не мигрировать старые Days, не строить общий runtime/PromptBuilder/workflow DSL. Не реализовывать Invariants, semantic validation, retry/reject pipeline, automatic events, dynamic plans, multi-agent/tools orchestration, RAG, Web, event sourcing или integrated Playground. Наличие этапа validation не означает наличие Validator. Генерация примера кода не означает изменение реального Checkout application.

## Decisions

### 1. Canonical node and immutable snapshot

`TaskState(task_id, machine_id, state_id, status, revision)` — frozen strict model. Task ID — canonical UUID, revision — strict nonnegative integer, status — `TaskStatus.ACTIVE | PAUSED`; extra fields/coercions не принимаются. Machine/node/event identifiers валидируются относительно переданной definition, не через импорт Checkout fixture в core.

`TaskStateDefinition` содержит versioned identity, initial node, immutable node metadata и mapping `(node_id, event_id) -> target_id`. Валидируются существование nodes/initial/endpoints, однозначность keys и отсутствие terminal exits. Никакого runtime registry, parsing DSL или user-defined definitions. Единственная Day 13 definition — обычная константа `checkout-v1` в harness module.

`phase`, `step`, `expected_action`, `is_terminal` получаются из node. `allowed_events` вычисляются из node + status и включают control events: при ACTIVE non-terminal — один workflow event и PAUSE; при PAUSED — только RESUME; при DONE — пустой список. Readiness/busy отдельно ограничивают возможность application operation.

Expected action — typed/stable action code в metadata: ближайшее содержательное действие в node, а не event выхода и не произвольный prompt. В execution это continue_implementation, а event выхода — IMPLEMENTATION_READY. При PAUSED код действия тот же, UI подписывает его «После возобновления». Терминальный node имеет action none. ACTIVE в DONE означает отсутствие паузы, а не возможность дальнейшего progress; третий status COMPLETED дублировал бы node.

Альтернатива с тремя independent phase/step/action strings отклонена из-за невозможных сочетаний; phase-only state недостаточно демонстрирует current step.

### 2. Checkout definition and exact transition semantics

| Node | Phase | Step | Expected action | Event -> target |
| --- | --- | --- | --- | --- |
| PLANNING_REQUIREMENTS | planning | collect_requirements | provide_requirements | REQUIREMENTS_READY -> PLANNING_APPROVAL |
| PLANNING_APPROVAL | planning | approve_plan | approve_plan | PLAN_APPROVED -> EXECUTION_IMPLEMENT |
| EXECUTION_IMPLEMENT | execution | implement | continue_implementation | IMPLEMENTATION_READY -> VALIDATION_CHECK |
| VALIDATION_CHECK | validation | validate | provide_validation_result | VALIDATION_CONFIRMED -> DONE |
| DONE | done | complete | none | none |

Все workflow edges требуют ACTIVE. Два planning nodes показывают различие phase и step без dynamic plan generation. Events подтверждает пользователь/application: даже PLAN_APPROVED не обещает автоматическую проверку наличия или качества плана. VALIDATION_CONFIRMED выбран вместо VALIDATION_PASSED, чтобы не смешивать user confirmation с будущим Validator.

Чистый `resolve(current, event, definition)` проверяет canonical snapshot/definition и возвращает новый frozen snapshot либо typed domain error. Успешный workflow event меняет node и revision+1. PAUSE/RESUME меняют только status и revision+1; supported control codes зарезервированы и не могут переопределяться workflow table.

Unknown event, отсутствующий edge, direct set_state_id, workflow event при PAUSED, любое событие в DONE, repeated Pause/Resume не в том status отклоняются без mutation/calls. Набор всех node/status/event комбинаций проверяется параметризованно. Terminal+PAUSED отклоняется при decode до использования. Обратные edges и validation failure loop не нужны: при неподтверждённом результате task остаётся на validation.

### 3. Independent persistence and honest partial setup

`TaskStateStore` contract: `create_initial(task_id, definition)`, `read(task_id)`, `compare_and_set(expected_revision, next_state)`, либо эквивалент с теми же guarantees. Adapter получает необходимую definition/validation dependency явно; не импортирует Day 13 fixture. Read отсутствующей записи возвращает различимый missing outcome. Create existing same-machine — no-op с возвратом существующего snapshot; incompatible identity — error. Только application event service использует CAS после resolver, HTTP arbitrary save endpoint отсутствует.

SQLite adapter хранит current rows `task_id PK, machine_id, state_id, status, revision` и schema version. Validate/decode, CAS update и revision guard защищают immutable identities, валидность next snapshot и increment old+1. SQL transaction короткая, provider await отсутствует. UPDATE с несовпавшей revision не публикует результат; failure rollback оставляет old record. Конкретные SQLite connection/path принадлежат adapter/composition root, не domain API.

Layout под отдельным `task-state/day13-v1` namespace: `memory.sqlite3`, `profiles.sqlite3`, `task-state.sqlite3`. Composition root проверяет различие с existing database paths и закрывает ресурсы. Это local implementation choice, не архитектура будущего Agent Runtime; объединённый adapter позже сохраняет тот же domain/create/read/CAS contract. Shared MemoryStore schema не меняется. Альтернатива единой БД сейчас потребовала бы расширять строгий schema contract MemoryStore; общей cross-file transaction не вводим.

Readiness — три независимых признака `memory_ready`, `profile_ready` (valid selected binding), `task_state_ready`, плюс причины missing/error. Readiness не является workflow status и не записывается в TaskState. Read/startup ничего не инициализируют.

Explicit Initialize выполняет existing memory initialize и initial State creation для полученного current task, не reset-ит существующие данные; Profile готовится отдельными typed create/select operations. New Task под application guard сначала выполняет atomic memory lifecycle, затем создаёт State. Только после обеих частей операция считается полностью успешной. При сбое второй части memory task/session уже существуют: возвращаются incomplete preparation/current identities, а не fake all-or-nothing rollback.

Отдельное explicit `initialize-state` завершает missing State setup **для уже текущей task**: принимает expected current memory snapshot/task ID и pinned machine identity, читает existing record, создаёт только отсутствующий initial State; существующий snapshot не перезаписывает. Read/recovery не вызывает её автоматически. Это явная инициализация отсутствующей записи, не обещание восстановления утраченного progress. Invalid schema/record/version/storage error не обходится этим действием. Если отсутствующая запись возникла из-за внешнего удаления, одного current-state store недостаточно, чтобы восстановить её прежнюю позицию; UI не называет создание initial State восстановлением progress. Дополнительный provisioning/event journal ради такой диагностики не добавляется.

Unknown outcome любой операции ведёт к read; если New Task committed, новая task не создаётся повторно. Если State уже создан, explicit completion сохраняет его независимо от потерянного response. Send/probe/events запрещены, пока любой required component не готов. Setup/read и устранение readiness остаются доступны. Новая task может иметь пустую Working: общий readiness означает наличие подсистем, а соответствие fixture проверяется отдельно для controlled acceptance.

### 4. Lifecycle and one application guard

| Operation | State | Other sources |
| --- | --- | --- |
| New Conversation | Unchanged including revision | Новая session/empty history; прежняя inactive, memory binding snapshot меняется |
| New Task | Новый initial/ACTIVE/revision 0 после готовой подготовки | Новые task/session, empty Working/history; owner/Long-term/Profile прежние |
| Profile switch/edit | Unchanged | Только соответствующие profile/binding fields/revision |
| Clear Long-term | Unchanged | Только Long-term и memory snapshot bookkeeping |
| Pause/Resume | Только status/revision | Все memory/profile snapshots и IDs прежние |
| Ordinary Send | Unchanged | Только completed real pair и соответствующий memory snapshot |
| Probe/read/reopen | Unchanged | Нет mutations/replay |

State выбирается через current memory task binding; второго active-state binding нет. Старые State rows сохраняются для inactive tasks, но не выбираются для current request. New Task остаётся отдельным lifecycle действием и из PAUSED: оно не возобновляет старую task, её PAUSED State сохраняется.

Day13 application service использует один owner-scoped guard по образцу PersonalizationService, в рамках существующего single-worker deployment. Он охватывает source resolution и весь Send/probe await; competing event/Pause/lifecycle/memory/profile write получает busy. Session guard сохраняется. Pause означает остановку дальнейшего workflow между операциями, не cancellation уже отправленного запроса. DB transaction во время await не удерживается.

Expected references для dispatch: memory snapshot ID, task_id, State revision, active Profile ID/revision и binding revision. Backend читает authoritative state и сравнивает references; client не выбирает profile/node вместо binding. Event request содержит current task/memory reference и expected State revision; readiness проверяется на backend. CAS остаётся дополнительной persistent защитой, а process guard не объявляется multi-worker locking.

### 5. Paused conversation without a semantic gate

PAUSED блокирует formal workflow events и разрешает conversation. Общий `run_turn` по-прежнему commit-ит completed пригодный ответ, включая status answer или даже semantic adherence violation. State/Working/Profile не мутируют от Send. В instructions указать: описывать current position и факты, отвечать на уточнения, не начинать продолжение реализации и не объявлять resume/transition самостоятельно; при просьбе продолжить во время паузы указывать на explicit Resume.

FSM guarantees enforceable кодом; понимание ограничений моделью — отдельная human observation. Если она написала реализацию во время паузы, сохраняется raw outcome, FSM остаётся PAUSED, adherence отмечается нарушенным. Не добавляем query classifier, response parser как event source, semantic commit gate или retry. Option A с блокировкой всех Sends отклонён: он мешает status/clarification UX и не нужен для deterministic progress control.

### 6. Pure assembly instead of a universal prompt framework

`TaskStateRenderer(snapshot, definition)` возвращает обычный deterministic текст: fixed authority rules + structured TASK_STATE block с state_id/phase/step/expected_action/status. Значения берутся только из validated server definition/snapshot. Task IDs/revisions/storage metadata не входят в semantic section и не меняют её текст; они в receipt. Memory strings и profile names не интерполируются в workflow authority instructions.

`prepare_agent_request(base_config, memory_snapshot, profile_snapshot, task_state_snapshot, definition, query)` получает уже resolved frozen/deep-copied данные. Результат `PreparedAgentRequest` содержит effective AgentConfig, prepared context policy и query; полные generation messages вычисляются из policy.messages + user query, без независимых mutable копий. Renderer и FSM usable отдельно от этого object. Selection evidence сохраняется рядом с preparation, не становится model input.

```text
resolved Memory ----> selected data + active history --+
resolved Profile ---> behavioral renderer ------------+--> prepared request
resolved State -----> workflow authority renderer -----+       |
current query ----------------------------------------+       v
                                                     SimpleAgent
                                                     /         \
                                                run_turn     generate
                                                 Send         probe
                                                     \         /
                                                   capture LlmClient
                                                          |
                                                   provider adapter
```

Effective instructions имеют фиксированный порядок: neutral base, PROFILE section, TASK_STATE authority rules/block. Messages: selected LONG_TERM, selected WORKING, active history с исходными roles/text/order, current query. State authority относится к workflow position; Profile управляет language/tone/format; Memory сообщает факты. Старый transcript не определяет текущий node. Это конкретная композиция трёх inputs, не configurable priority system.

Existing Memory selection сохраняет исключение preferred_architecture при Working override. Profile renderer применяется к typed fields. Fixed base остаётся нейтральной к выбранному стилю. State section не добавляется synthetic transcript message и не сохраняется через commit. AgentConfig создаётся per request, global configs не мутируют. `run_turn` получает прежние interface/config/policy; State-specific argument или branch ему не нужен. Probe использует `generate(prepared.messages)` с той же preparation.

Объект оправдан появлением третьего реального source и устраняет повторную сборку ordinary/probe/inspector. Альтернатива одного renderer внутри большого lab service проще по diff, но оставляет composition tied to harness. Universal AgentRequestContext с future fields/registries отклонён; Invariants позднее расширят только preparation/coordinator.

### 7. Actual capture and independent observations

Выделить существующий CapturingClient в нейтральный модуль, если это нужно для reuse, сохранив exact Day 12 calls/receipts. Wrapper фиксирует deep copy реальных arguments `complete(messages, config)` перед delegate и не делает дополнительный call. Capture exceptions/unknown transport outcomes не превращаются в fictional provider result. Day12 output checks не переносятся в State domain.

Attempt receipt: attempt ID/mode, source snapshots и references, selected/excluded Memory, rendered Profile/State sections/template versions, actual messages/config/query, outcome и conversation_committed. State metadata сохраняется независимо от semantic input. Recording delegate проверяет точное равенство captured arguments; receipt не пересобирается из current state после ответа.

Четыре группы: storage observation (сохранённый прочитанный snapshot; reopen evidence отдельно), selection checks (current task/machine/revision/profile), actual assembly checks (exact sections/messages/settings), human model adherence. Storage read не выдаётся за выполненный restart test. Marker matches не доказывают семантику. Pre-dispatch rejection: not_dispatched; dispatched failure: input evidence доступно, semantic output unavailable. Semantic violation не меняет provider outcome/commit и не запускает retry.

Runtime last transition receipt `before/event/after` публикуется только после durable CAS; ошибки показаны отдельно без fake after. Он не input source, не event log и не нужен для reopen. После restart потерянные observations обозначаются unavailable/not measured.

### 8. Controlled inputs and strengthened live acceptance

Server config: отдельная `day13-v1`, `gpt-4o-mini`, reasoning_effort=None, service_tier=default, truncation=disabled, max_output_tokens=2000, natural text без structured output. Это текущая Day12-derived лабораторная настройка, не domain/Profile field. Live доступность provider проверяется отдельно; silent fallback запрещён.

Fixture: Working task=`Checkout: обработка loading/error/success`, current_architecture=`MVI`, release_marker=`RC-42`. Существующее поле task уже вмещает постановку: Memory schema не расширяется. Long-term для минимального сценария пустая и неизменная; markers/override покрыты existing memory tests. Profile — явно созданный и выбранный Compact Engineer с Day 12 typed fields (ru/technical/concise/summary_bullets max 3/no_emoji/skip_basic_explanations), но отдельной Day 13 identity. Не импортировать fixtures из personalization harness: использовать Profile domain и собственный lab catalog. Startup ничего не seed-ит.

Deterministic influence: одна task, unchanged Memory с empty history, один Profile/query `Что делать дальше?`/config. Снять planning request, применить REQUIREMENTS_READY/PLAN_APPROVED, снять execution request, применить IMPLEMENTATION_READY, снять validation request. Probes вызывают `generate` без commit; recording stub outputs не используются далее. Assert: одинаковые messages/query/Profile/non-state instructions/settings; отличается только State section. Revision меняется в receipt, не semantic input. Сохранённый comparison framework или arbitrary node setter не нужны; baseline snapshots проверяет test harness. При interactive probe снимается current state; результаты с разной Memory не объявляются controlled comparison.

Основной live flow:

1. Explicit setup, выбранный фиксированный Profile, Working fixture; REQUIREMENTS_READY и PLAN_APPROVED дают EXECUTION_IMPLEMENT/ACTIVE revision 2.
2. Обязательный ordinary execution Send в session S0: получить настоящий completed ответ и подтвердить сохранённую user/assistant pair до Pause. State остаётся EXECUTION_IMPLEMENT/ACTIVE revision 2. Этот реальный execution transcript должен быть исключён первым New Conversation; без подтверждённой pair S0 live acceptance не считается успешно пройденным.
3. PAUSE даёт EXECUTION_IMPLEMENT/PAUSED revision 3.
4. New Conversation #1 создаёт S1 с empty active history; task/Working/Profile/State те же, S0 inactive.
5. Ordinary Send `Где мы остановились?`: actual input без S0, с PAUSED. Показать raw response и отдельно оценить task/phase/step/pause, отсутствие возврата в planning. State revision 3 сохраняется, completed pair становится history S1.
6. **Обязательный New Conversation #2** создаёт S2; подтвердить empty active Short-term, прежние task/Working/Profile/PAUSED State. Теперь S0 и status pair S1 inactive.
7. RESUME даёт тот же node/ACTIVE revision 4 и не пишет history.
8. Ordinary Send `Продолжим`: pre-dispatch history S2 пуста; actual input — neutral base + fixed Profile + ACTIVE execution State, selected Working/empty Long-term и query. Никаких S0/S1 messages, summaries, receipts или hidden seed. Оценить continuation implementation loading/error/success/MVI, отсутствие повторного запроса постановки/planning.
9. Completed pair сохраняется в S2; State остаётся EXECUTION_IMPLEMENT/ACTIVE revision 4. Optional отдельный IMPLEMENTATION_READY переводит его в validation/revision 5, без generation.

Успешный live flow выполняет ровно три generation calls: execution Send, status Send и continuation Send; все setup/events/lifecycle/read дают ноль provider calls. Три дополнительных live State influence runs не требуются. При failed/incomplete/misaligned output сохранить фактическое наблюдение; повтор возможен только явно, без cherry-picked fake success.

FSM восстанавливает node, не потерянный произвольный план/код. Постановка loading/error/success находится в Working и доступна после очистки active transcript; detailed implementation choices, не сохранённые в Working, восстановленными не объявляются. Backend restart — отдельная deterministic reopen acceptance, не обязательный видео-шаг.

### 9. API and Android lab boundaries

Prefix `/api/v1/task-state` для isolated Day13 service. Минимальные группы: read-only current/scenario; explicit initialize и initialize-state; memory mutations/lifecycle; typed Profile create/edit/select через reused domain; events; ordinary messages; non-committing current probe. Event body принимает event/task/current references/expected revision, без target node/derived fields. PAUSE/RESUME проходят тот же event endpoint. Строгие transport DTO отделены от FSM models. Read/current возвращает State canonical+derived view, allowed_events, component readiness и busy.

Profile/memory operations нужны для setup и lifecycle tests; полный Day12 editor/A-B dashboard не копируется. Минимальный UI подготовки может явно создавать/выбирать один fixture через обычные typed operations, показывая реальные values и partial readiness. Другие Profile lifecycle contracts проверяются API tests, не становятся переменной controlled live.

Android: отдельные Repository/ViewModel/Compose destination с constructor injection через AppContainer. Backend authoritative: main показывает compact summaries/State card/allowed event buttons/Pause или Resume/lifecycle/session count/composer/latest response. Full JSON/IDs — inspector; optional current probe в разделе проверки, без большого stepper. PAUSED composer доступен, workflow buttons недоступны, action подписано как after Resume; DONE не имеет events/Pause/Resume. Локальные busy/recovery блокируют actions, но не заменяют backend guard.

Repository валидирует identities, revisions, source association и shape received DTO без собственной transition table. ViewModel не делает optimistic node changes. Unknown outcome -> read/recovery, без replay; incomplete setup предлагает завершить State для current task, не New Task ещё раз. Navigation/rotation сохраняют in-flight work/drafts/receipts/scroll, cold start только читает. Insets/IME/narrow screen проверяются в scoped UI tests. Human notes runtime-only.

### 10. Reuse map and future integration boundary

| Reusable | Day13-only |
| --- | --- |
| TaskState, TaskStatus, state/node definition contract | checkout-v1 constants и concrete workflow events/metadata |
| TransitionEvent representation, pure resolver, Pause/Resume | fixture preparation и explicit user confirmations |
| TaskStateStore, SQLite adapter, CAS/errors | namespace paths, application DTO/API coordinator |
| TaskStateRenderer | controlled query/settings/expected observations |
| Small request preparation | lab dashboard/inspector presentation/human notes |
| Provider-neutral capturing client | specific live and deterministic experiment harness |
| Existing Memory/Profile/Agent primitives | runtime latest operation receipts |

Core import tests запрещают зависимость FSM domain/store от LlmClient/AgentConfig/SDK, Memory/Profile storage, Day13 fixtures/results/UI. Renderer возвращает text, composition размещает его в AgentConfig. Простой resolver usable без store/LLM; persistence usable без provider.

Сегодня Send -> `run_turn` -> conversation commit; State event выполняется отдельным действием. Будущая integration orchestration сможет capture -> `generate` -> validate -> retry/reject или commit accepted conversation -> apply accepted event. `run_turn -> validate` непригоден: bad completed reply уже committed. Ни один последовательный порядок commit/event сам по себе не атомарен: будущий coordinator отдельно выберет transactional storage/unit-of-work или reconciliation. Day13 CAS и pure resolver сохраняются; общей атомарности сегодня нет. Integrated Playground логичен после Invariants/Validation и этого integration decision.

## Risks / Trade-offs

- [PAUSED model violation] -> отделить guaranteed event rejection от human adherence; не добавлять скрытый Validator/commit gate.
- [Transcript leakage] -> две новые sessions, empty pre-turn assertions и exact captured-input comparison, без summaries/receipts в sources.
- [Insufficient task facts] -> сохранить полную компактную постановку в existing Working.task; не обещать восстановления несохранённых решений.
- [Cross-file partial setup] -> независимая readiness, explicit initialize-state для current task, read без replay, existing state never reset; отсутствие записи не выдаётся за восстановленный progress.
- [Definition drift] -> machine_id pins semantics, unknown versions fail explicitly; version migration framework отложен.
- [Single-worker guard] -> сохранить заявленный deployment scope, CAS для persistent conflict; production multi-worker coordination не заявлять.
- [Probe proves only request] -> recording-client evidence не считать live semantic success; сохранить actual live failures и human observations.
- [Future commit consistency] -> event отдельно от generation, layout-independent store, никакой сегодняшней atomicity promise.
- [Accidental old-Day changes during extraction] -> точечные regression tests exact Day11/12 assembly/capture и shared Agent contracts; no data migration.

## Migration Plan

1. После отдельного apply request добавить reusable core/adapter/composition и isolated Day13 wiring; existing schema/data/config namespaces не менять.
2. Добавить strict API и lab UI/navigation, затем targeted deterministic backend, Android JVM/build/scoped UI checks по tasks. Preferred Windows path — PowerShell 7 `scripts/dev.ps1` по component docs. При недоступном `pwsh` или блокировке ExecutionPolicy разрешён fallback: Android — прямые Gradle commands для тех же tasks; backend — `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` из каталога `backend`. Исправление PowerShell/tooling не входит в scope Day 13. Не запускать конкурирующий Gradle и не менять cache/daemon flags без диагностики.
3. Live acceptance выполнить отдельно после readiness backend+emulator; backend держать в управляемой сессии со stdout/stderr. Health не доказывает provider availability. Существующий эмулятор и успешные проверки актуального кода переиспользовать.
4. Добавить Day README по трём кратким разделам с реальными результатами/явным not-run, ссылку в корневом README; общие setup/API commands — в component README.
5. Rollback отключает Day13 wiring/destination, сохраняя local files и старые namespaces. Никаких automatic delete/reset/migration.
6. Planning заканчивается review artifacts и strict OpenSpec validation; implementation, commit/push и archive не выполняются этим запросом.
