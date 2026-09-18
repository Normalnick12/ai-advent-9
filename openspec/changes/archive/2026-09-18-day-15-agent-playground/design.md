## Context

Мотивация и capability scope: [proposal.md](proposal.md). Behaviour contracts: [runtime](specs/agent-runtime-integration/spec.md), [experiment](specs/agent-playground-experiment/spec.md), [Android](specs/agent-playground-android/spec.md).

По инспекции текущего repository:

- `task_state.py` уже содержит pure definition/resolver, `allowed_events` и Pause/Resume; `SQLiteTaskStateStore` принимает одну definition, сохраняет CAS/revision и проверяет machine identity при чтении. `checkout_workflow.py` закрепляет `checkout-v1` с пятью узлами и четырьмя forward edges. Engine допускает явные обратные рёбра; его менять не требуется.
- `prepare_agent_request` собирает Memory, Profile и State с optional invariant section. `MemoryContextPolicy.prepare` проверяет session/history snapshot.
- `run_validated_turn` уже принимает generation/check/render/refusal callbacks, проверяет coverage, формирует final pair и вызывает `AgentSession.commit`. `SimpleAgent.generate` не пишет conversation; `run_turn` делает immediate commit и не подходит как Day 15 acceptance path.
- `InvariantsLabService` смешивает reusable orchestration/capture/recovery с Day 14 fixtures, двумя fixed action IDs и ACTIVE execution gate. Копировать целиком этот service в Playground нельзя.
- Day 14 `CodingProposal` содержит пять bounded fields без prose. Его renderer строит весь ответ из checked values. `CodingPolicy` имеет четыре typed fields; store позволяет разные values для разных tasks, запрещая replacement одной task.
- `MemoryStore` сохраняет owner/task/session и inactive records. Working schema допускает task/current_architecture/release_marker; плана или реализации там нет. Store schemas раздельные и не образуют общей транзакции.
- Android имеет constructor-injected Repository/ViewModel и AppContainer. `ChatBubble` переиспользуется; session-only `ChatViewModel` не подходит для нового lifecycle. Day 14 Inspector печатает sources/request/candidate/results целиком и хранит только latest observation.

Design обязателен: change затрагивает backend composition, durable setup recovery, новый candidate contract и Android UX. Реализация работает в существующем single-worker local demo режиме.

## Goals / Non-Goals

**Goals:**

- Сделать два независимых пути: bounded conversation acceptance и deterministic event application, с общим guard и coherent source snapshots.
- Изолировать Coding configuration от reusable orchestration и сохранить проверяемые зависимости на provider adapter.
- Не потерять выбор пользователя при partial setup в нескольких stores.
- Сделать coverage, persistence и historical evidence понятными без чтения JSON.
- Доказать три разных исхода: allowed forward, allowed recovery и forbidden/off-graph rejection; после recovery продолжить задачу до Done.

**Non-Goals:**

- Универсальная policy/workflow система, второй transition engine, миграция старых labs или исправление всей genericity Week 3.
- Generic Back/goToState, arbitrary next_state, dynamic graph editing, rollback stack, history rewind/undo conversation, semantic auto-detection failure и automatic model-selected recovery.
- Автоматическая классификация произвольного query в trusted intent, semantic proof для prose/code, tool execution или фактический запуск проверок создаваемого моделью решения.
- Распределённые транзакции/блокировки, audit event log, general operation journal, exactly-once network delivery, persistent receipt archive.

## Decisions

### 1. Small composition with separate Send and lifecycle services

В reusable integration module выделяется небольшая orchestration Send: source resolver/preparation hooks, `LlmClient`/candidate factory, required rules/check/render callbacks, capture, session recovery и receipt construction. Он не импортирует `CHECKOUT`, `CodingPolicy`, lab fixtures, FastAPI или OpenAI SDK. Concrete Coding composition связывает эти зависимости. `readCurrent` остаётся read-only projection конкретной composition; тонкий facade допустим, но класс `AgentRuntime` не обязателен.

Lifecycle service использует injected definition/store и pure `resolve`, не получает candidate adapter или LLM dependency. Обе ветви пользуются одним namespace guard, действующим также на setup, Profile switch и New Conversation. Read разрешён во время generation и сообщает busy; conflicting writes отклоняются, без implicit queue/retry.

```text
Android Playground -> Playground API -> Coding composition
                                         |            |
                                         v            v
                                Send coordinator   Lifecycle service
                                  |       |          resolve -> CAS
                                  |       v
                                  |   candidate adapter -> LlmClient
                                  v
                           run_validated_turn -> atomic pair commit
```

Reuse существующих функций предпочтителен. Общие source-reference checks/capture/reconcile из Day 14 извлекаются только при фактическом повторном использовании; изменение вызова helper старой лабораторией не меняет её поведение. Не создавать второй prepare/generate/check/commit pipeline в Playground service. `SimpleAgent.generate` остаётся generation primitive; `run_turn` для Playground не вызывается.

Альтернативы: целиком использовать `InvariantsLabService` нельзя из-за fixed actions/Execution gate; универсальный Agent framework добавляет ненужные extension points.

### 2. Explicit Coding configuration rather than AgentDefinition framework

Небольшой strict `CodingTaskConfiguration` содержит versioned setup preset/task title, выбранный Profile preset и существующий `CodingPolicy`. Workflow version `checkout-v2` закреплён серверной Day 15 composition и durable setup record, не редактируется UI. Preset catalog и допустимые values предоставляет backend; Android передаёт typed values, а не instructions или validator descriptions. Profile records создаются в Playground owner scope, не импортируются из Day 12.

Defaults: Compact Engineer, MVI, Compose, CoroutinesFlow, payment confirmation required. Поддерживаются все комбинации уже существующих enum/boolean fields; дополнительных compatibility запретов без отдельного основания не вводится. Payment=false означает точное false decision, не выключение check. Retry mode остаётся вне policy editor.

Runtime не знает domain values. Для другого агента в будущем меняются concrete source/policy/candidate/render bindings и definition, а не acceptance/lifecycle алгоритмы. Сейчас другой agent не реализуется. Известные limitations сохраняются: State renderer имеет coding wording, Profile renderer ссылается на Android/Kotlin, Memory schema предметная, один SQLite State instance использует одну definition. Preparation принимает render/preparation hooks там, где это необходимо для недопущения новых domain imports; defaults старых вызовов сохраняются.

Альтернатива: `AgentDefinition` container/registry не нужен для одной composition. Он не решает ни setup recovery, ни semantic validation.

### 3. Immutable task policy and coherent explicit creation

Для новой task формируются initial Working facts из reviewed configuration: task="Checkout: loading/error/success + retry", current_architecture равна policy architecture. Не требовать фиктивного release_marker ради старого Day 14 readiness check. Long-term новой owner изначально пуст; New Task сохраняет существующий owner Long-term. Selection и Working override остаются прежними.

Policy сохраняется через существующие `TaskCodingPolicy`/`CodingPolicyStore`: тот же policy identity/version, fingerprint всех exact values и неизменяемость на task. Поддержка MVVM/Views/RxJava/false не требует изменения durable policy schema. Profile selection изменяет только binding; дальнейший switch не пересоздаёт setup и не меняет immutable configuration record первоначального создания.

New Task получает новые task/session IDs и initial State, сохраняет inactive старые records. New Conversation создаёт новую session той же task и сохраняет policy/State/Working/Profile. Основное live использует одну conversation: перенос полного плана/реализации в Working не добавляется.

Альтернатива: hot-edit policy исключён, поскольку нарушает воспроизводимость и уже существующий immutable contract.

### 4. A small durable setup record closes the partial-creation gap

Существующего orchestration с constants недостаточно: после restart он не помнит выбранные nondefault values, а повторный `new-task` создаёт новые IDs. Поэтому Playground получает собственный небольшой durable configuration/setup store рядом с переиспользуемыми stores. Это state конфигурации создания, не журнал Sends/events.

Setup record содержит immutable configuration/version, machine_id=`checkout-v2`, effective Profile preset fields/version, reserved owner/task/session IDs, expected previous binding reference и status pending/ready. Для одного Playground допускается только один pending setup. Полный request валидируется до любых writes.

Порядок после explicit confirmation:

1. Под общим guard проверить current reference и отсутствие другого pending setup; выделить target IDs и durable сохранить record до materialization источников.
2. Создать Memory owner/task/session с reserved identities или подтвердить уже созданные exact bindings. Для этого допускается узкий explicit-identity/idempotent creation helper в Memory persistence, использующий существующую atomic transaction; старые `initialize`/`transition` сохраняют defaults и контракты. Не добавлять произвольные records в существующий Memory schema и не копировать SQL жизненного цикла в UI/service.
3. Дополнить coherent Working facts, создать/найти exact preset profiles в текущем owner, выбрать reviewed Profile, создать initial State и task policy существующими adapters. Уже materialized task facts/State/policy проверяются на совпадение, не перезаписываются. Выбор Profile — отдельно разрешённое review-confirmation действие над binding: для New Task он может явно заменить предыдущий active Profile; partial completion проверяет ожидаемый binding и уже применённый выбор.
4. После проверки всех источников отметить setup ready. Доменный stage при этом остаётся initial; не применять progress events автоматически.

При failure record остаётся pending и `/current` показывает его choices, reserved IDs и missing components, даже если Memory binding ещё не materialized. Другие mutations блокируются. После restart выполняется только read. Пользователь явно выбирает completion, который продолжает на тех же identities; если config record повреждён или обнаружен конфликт, вернуть error без guessing/defaults. При потере acknowledgement setup ready тоже восстанавливается чтением; stale create не должен создавать вторую task. Повторное completion ready record — no-op по источникам, оно не откатывает последующий Profile switch или State.

Нужны fault-injection проверки каждого меж-store разрыва, включая failure до первой Memory write, после binding write и после final readiness write. Общая атомарность всех stores не обещается.

Альтернативы: Android-only draft теряется после process death; запись policy только в конце не хранит ранний выбор; повторное создание не сохраняет IDs. Общая migration всех stores или operation journal значительно шире необходимого.

### 5. Separate versioned conversation candidate with four bounded decisions

Day 15 candidate (`coding-turn-v1`) содержит:

```text
answer: nonempty bounded text
decisions:
  architecture: MVI | MVVM
  ui_toolkit: Compose | Views
  async_model: CoroutinesFlow | RxJava
  payment_confirmation_required: boolean
```

Все четыре decisions обязательны на каждом Send; это заявленные coding choices/constraints текущего ответа, не доказательство их соблюдения каждым фрагментом prose. Parser strict: extra/duplicate/missing fields, неверные types/enum и пустой answer дают technical candidate-preparation error. Предел query/answer — 20000 characters; generation output limit задаётся отдельно серверной config. Decisions допускают incompatible values, иначе schema подменила бы policy gate.

Существующие четыре predicates повторно используются. При необходимости выделить общий typed four-field `CodingDecisions` base и расширить его старым `CodingProposal` с обязательным retry_mode; JSON shape и strict Day 14 extra-field rejection не меняются. Новый renderer принимает parsed candidate только после checks и публикует answer, не raw JSON envelope. Safe refusal строится из trusted descriptions выбранной policy, без rejected answer или diagnostic strings.

Coverage metadata создаёт приложение: четыре проверенных decisions, structural answer checks, prose semantics not checked. Candidate не присылает себе verdict/pass. Согласованные decisions с противоречивым prose могут пройти этот bounded gate; это честное limitation, проверяемое отдельным regression. UI не подписывает результат «полностью безопасен» и не превращает prose в реальные side effects.

Natural query не имеет trusted structured intent: `precheck=None`, evidence not applicable. Не использовать пустой `CodingIntent()` как доказательство понимания запроса и не классифицировать текст дополнительным LLM. Known structured-request conflict support общего coordinator сохраняется; Day 14 продолжает его демонстрировать. Generation для Day 15 — максимум один call без repair/retry/reviewer/count. Profile/State/invariant guidance реально присутствуют в input, но adherence оценивается отдельно.

Альтернативы: старый five-field proposal даёт только шаблонный retry-ответ и не поддерживает настоящий разговор; semantic judge расширяет scope и не создаёт deterministic proof. Новое поле «этап ответа» также не доказывает отсутствие implementation prose во время planning.

### 6. Exact Send outcomes and lifecycle results

Send проходит source checks, подготовку и `run_validated_turn`; prepared snapshot проверяется по session/history до generation. Successful rendering ещё не означает сохранённую пару. В ответе разделяются operation status, acceptance decision, provider dispatch/outcome и commit status.

| Outcome | Generation | Conversation |
|---|---|---|
| Accepted candidate | 1 | user/rendered answer при confirmed commit |
| Candidate policy violation | 1 | user/trusted refusal при confirmed commit |
| Trusted structured request conflict (core) | 0 | user/trusted refusal при confirmed commit |
| Source/configuration error | 0 | unchanged |
| Provider/parser/checker/rendering failure | 0 или 1 по факту | unchanged до commit |
| Storage failure | по факту | failed/unknown; authoritative reconciliation |
| Forward applied | 0 | unchanged, commit not applicable |
| Recovery applied | 0 | unchanged, commit not applicable |
| Forbidden event rejected | 0 | unchanged, commit not applicable |
| Pause/Resume applied | 0 | unchanged, commit not applicable |

Lifecycle request несёт current task reference, event и expected State revision. Проверить stale reference до resolver, затем `resolve` и CAS. `compare_and_set` сам по себе не проверяет наличие ребра; публичного direct State update не вводится. Lifecycle service не разрешает sources для генерации и не требует LLM/Profile для объяснения event; setup pending всё же блокирует mutation.

Expected invalid event возвращает typed lifecycle result с before/after, reason, attempted event, allowed_events, expected_action и dispatch not_required. HTTP status — 409 с discriminated lifecycle result envelope; Repository отличает этот известный rejection от transport failure. CAS stale/storage failure — отдельные codes, без ложного `state_unchanged` при unknown acknowledgement. Human labels формируются из trusted workflow metadata/catalog, не model call.

### 7. Versioned workflow with two explicit recovery edges

Day 15 получает отдельную concrete definition `checkout-v2` поверх неизменённых TaskStateDefinition, resolver, allowed_events, CAS store и Pause/Resume. Machine identity закрепляет смысл persisted nodes: расширение `checkout-v1` изменило бы разрешённые события существующих задач Days 13–14. Поэтому их definition, contracts и data сохраняются; новая definition использует отдельный Playground State namespace. Stored v1 state не принимается v2 store и не мигрируется автоматически. Setup/current/state обязаны согласовывать machine_id; reopen сохраняет version, node и revision без reset.

В v2 сохраняются пять узлов, их phase/step/expected_action/terminal metadata и четыре forward edges:

```text
PLANNING_REQUIREMENTS -- REQUIREMENTS_READY --> PLANNING_APPROVAL
PLANNING_APPROVAL -- PLAN_APPROVED --> EXECUTION_IMPLEMENT
EXECUTION_IMPLEMENT -- IMPLEMENTATION_READY --> VALIDATION_CHECK
VALIDATION_CHECK -- VALIDATION_CONFIRMED --> DONE

PLANNING_APPROVAL -- REQUIREMENTS_REVISION_REQUIRED --> PLANNING_REQUIREMENTS
VALIDATION_CHECK -- VALIDATION_FAILED --> EXECUTION_IMPLEMENT
```

Два последних ребра — allowed domain recovery, не invalid transitions. Каждое требует explicit user/application event, меняет только state_id на заданный target и revision ровно на +1; task_id, machine_id и ACTIVE status остаются прежними. Conversation, Working/Long-term Memory и их revisions, Profile/binding, policy и setup configuration сохраняются точно; provider calls=0, dispatch=not_required, conversation commit=not_applicable. Нет скрытой очистки плана/кода, rewind или автоматического повтора. Natural Send, включая «validation failed, возвращаюсь в implementation», никогда не применяет ни forward, ни recovery event.

После REQUIREMENTS_REVISION_REQUIRED allowed_events = REQUIREMENTS_READY и PAUSE; после VALIDATION_FAILED = IMPLEMENTATION_READY и PAUSE. Повторный progress требует обычных explicit forward events: requirements revision снова проходит Plan Approval, validation failure снова проходит Validation перед Done. Recovery event из любого другого узла отклоняется без изменения sources/revision; PAUSED разрешает только RESUME, DONE — никаких событий.

Receipt содержит typed outcome `forward_applied`, `recovery_applied` или `rejected`; Pause/Resume имеют отдельные `pause_applied`/`resume_applied`. Concrete Coding catalog классифицирует именованные рёбра для receipt/labels через injected metadata, не меняя TaskStateDefinition/StateTransition/resolver contracts и не вычисляя «назад» по порядку enum. Resolver остаётся единственным authority допустимости; applied outcome возможен только после confirmed CAS. Stale/storage unknown — отдельные outcomes, не fabricated applied/rejected.

Normal controls строятся по backend allowed_events: Plan Approval предлагает «Утвердить план», «Уточнить требования», Pause; Validation — «Подтвердить проверку», «Проверка не пройдена», Pause. Recovery result — обычная operation card: «Проверка не пройдена. Задача возвращена на этап реализации. Следующий шаг: исправить найденные проблемы». Для requirements recovery следующий шаг — уточнить требования и снова согласовать план. Это trusted operation-specific explanation; canonical expected_action узла сохраняется, durable last-recovery flag не вводится.

Educational actions объявляются Coding catalog отдельно для соответствующего current node; они посылают настоящее forbidden event в тот же endpoint и не блокируются normal-action filter ViewModel:

- PLANNING_APPROVAL + IMPLEMENTATION_READY: отказ; сначала PLAN_APPROVED.
- EXECUTION_IMPLEMENT + VALIDATION_CONFIRMED: отказ; сначала IMPLEMENTATION_READY и validation stage.

Для сравнения normal actions на Validation:

- VALIDATION_CHECK + VALIDATION_CONFIRMED: allowed forward к Done.
- VALIDATION_CHECK + VALIDATION_FAILED: allowed recovery к Implementation.

Android содержит labels, не transition table. Не добавлять FINISH или второй validation substage. FSM гарантирует порядок подтверждений, не факт прочтения плана/выполнения тестов: VALIDATION_FAILED — явное заявление пользователя о необходимости исправления, не semantic verdict модели или автоматически запущенного verifier.

PAUSED позволяет clarification Send с существующей State guidance и только RESUME event. Node сохраняется; во время busy Pause не является cancellation и отклоняется/disabled. DONE использует terminal metadata при status ACTIVE: Send блокируется backend-ом и composer отсутствует, history/Inspector остаются доступны, New Task explicit.

### 8. Minimal API and Android feature ownership

Новый `/api/v1/agent-playground` namespace имеет read-only catalog/current и явные create-task, complete-setup, send, events, select-profile, new-conversation operations. Поля refs строятся по current projection; arbitrary policy update/next_state endpoints отсутствуют. Domain expected results декодируются отдельно от network error; technical Send response сохраняет receipt, если он доступен.

`PlaygroundViewModel` через Repository вызывает backend composition. Он хранит current projection, committed transcript, draft/pending state, operation busy/recovery, reviewed config draft, operation results, receipt map и selected attempt. Readiness/can_send приходят с backend; UI не вычисляет собственную FSM. До confirmed commit pending input не добавляется в committed transcript. При known no-commit failure draft сохраняется; при unknown outcome read сверяет durable history до нового Send.

Reuse `ChatBubble`; composer выделить/слегка параметризовать для отсутствия постоянного reset button, не менять semantics старых экранов. `ChatViewModel` и его delete-session reset не используются. Wiring через существующий AppContainer/MainActivity/AppRoot/LearningDaysHome; новые DI/navigation frameworks не нужны.

Main: compact task/stage/next-action header, Profile и policy summary, conversation занимает основную площадь, composer и contextual action доступны при IME. New Conversation/New Task и educational check — secondary menu/section. Lifecycle forward/recovery/rejection — удерживаемая operation result card с before/event/after и next action, не snackbar-only и не chat pair. Allowed recovery не получает error banner или transport reconciliationRequired только из-за движения назад; после confirmed success доступны actions recovered node. Setup — единая форма/review, без технических fixture buttons.

Альтернатива: копирование Day 14 main оставит acceptance dashboard вместо conversation tool; полное переиспользование старого chat lifecycle нарушит restore/reset semantics.

### 9. Inspector summary and raw evidence use the same receipt

Внутренние страницы: main/setup/inspector/raw-debug в одной feature. Back: raw-debug -> inspector -> main -> catalog. Использовать текущие ViewModel/saveable-state patterns, сохранять per-page scroll/sections и selected attempt при rotation/navigation.

Level 1 строится pure presentation mapping из selected receipt: operation outcome, dispatch/count, commit, State/Profile used, check coverage и lifecycle result. Lifecycle явно различает Forward applied / Recovery applied / Forbidden transition rejected (Pause/Resume отдельно) и показывает before node/revision, event, after node/revision, next action. Для recovery Provider: Not required, calls=0, Conversation: unchanged; summary не сводится к success/fail. Нельзя выводить общий success только по `decision=accepted`. Level 2 раскрывает semantic facts, selected history count, excluded memory facts, preferences, State position, rule-by-rule assessment, actual assembly и commit. Current показывается отдельным явно подписанным блоком и не заменяет Used in this turn.

Raw Debug показывает actual provider-neutral arguments captured в `LlmClient.complete`, а не обещанный HTTP wire payload. Если dispatch отсутствовал, actual_request=null; никакого восстановления из preview. Raw candidate/provider outcome доступны с diagnostic/untrusted label. Distinct absence/error statuses сохраняются без сведения к Boolean pass/fail.

Receipts копируются по значению на terminal attempt; `attempt_id`, task/session и confirmed pair position позволяют связать Inspector с конкретным ответом. Lifecycle receipts имеют иной operation kind и отсутствие provider/candidate sections. Runtime map ограничить 50 последними receipts; eviction/process death показывает unavailable для старого ответа, не реконструкцию. Ограничение не меняет receipts, которые ещё доступны. Unknown commit не получает придуманной confirmed pair association; last operation Inspector может показать такой receipt отдельно.

Альтернативы: один latest ломает Inspector предыдущего ответа; persistence всех receipts или raw JSON на первой странице создают лишний scope/шум. Receipts содержат несколько представлений растущей history, поэтому Raw Debug оправдан отдельной страницей.

### 10. Persistence reconciliation and provider independence

После неизвестной записи Send пересоздать только Playground session cache из authoritative conversation; не повторять generate/commit. Unknown event, включая recovery edge, требует current State read, без повторного event. Это техническое reconciliation, отдельное от разрешённого domain recovery из §7; authoritative recovered node нельзя автоматически возвращать в прежний узел. Если authoritative read не удался, guard/UI блокируют writes и разрешают read retry. Уже durable pair после потерянного HTTP response не объявляется отменённой.

Cold reads не создают demo/task/profile/policy и не завершают pending setup. Открытие storage может выполнить обычную техническую schema initialization пустого нового namespace, но не создаёт domain task/configuration и не вызывает provider. Damaged/version-incompatible records fail closed без migration/default replacement.

Core зависит от `LlmClient` и candidate adapter. OpenAI JSON schema mapping, service_tier/reasoning/truncation остаются за adapter/config mapping boundary. Другой/local provider реализует mapping/strict parser того же candidate. Policy, four predicates, Memory/Profile domain, FSM и acceptance/commit semantics не меняются. Unsupported provider format даёт explicit error, а не обход gate через plain `run_turn`.

### 11. Verification and human-readable live flow

Backend tests используют recording/fake client и production entrypoints, не обходя gate. Проверяются оба recovery edges: exact target, revision +1, прежние task/machine/status, exact equality всех non-State sources (conversation, Working/Long-term, Profile/binding, policy/config), ноль provider calls, updated allowed_events, wrong-node/repeated-event rejection и повторный forward путь до Validation/Done. Отдельно оба forbidden skips, recovery при PAUSED/DONE, stale CAS и lost recovery acknowledgement/reopen без replay. Send с текстом failure/recovery сохраняет State/revision. Проверяются alternative policies, exact request/capture, immutable historical typed receipts и failure/restore boundaries. Setup fault injection покрывает nondefault config, machine_id и stable IDs; cross-version read fails closed. Старые tests Memory/Profile/FSM/Day 14 gate выполняются как targeted regressions, включая отсутствие новых recovery events у checkout-v1. Import/dependency test запрещает coding/checkout/openai/lab imports в новом reusable coordinator; definition/provider substitution проверяется без реализации второго agent.

Android JVM tests проверяют Repository typed forward/recovery/rejection decoding, summary mapping, immutable receipts, reconciliation/no replay, duplicate taps и source-preserving Profile switch. UI tests покрывают reviewed setup, normal recovery controls и result card без chat bubble/error banner, updated recovered actions, отдельные educational rejections, chat, pause/done, Inspector/Raw Debug/back/rotation и narrow/IME layout. Gradle через PowerShell 7 scripts/dev.ps1 unit/build/ui -Test; среда, сборка, UI и live проверяются отдельно, успешные актуальные проверки не повторяются без причины.

Основной live в одной conversation, defaults reviewed пользователем:

| Шаг | Запрос или explicit action | Проверяемое evidence |
|---|---|---|
| 1 | Создать default Coding task | initial stage, 0 provider calls |
| 2 | «Сформулируй требования к loading/error/success и retry загрузки Checkout» | обычный requirements answer, State прежний |
| 3 | REQUIREMENTS_READY | Plan Approval |
| 4 | Educational IMPLEMENTATION_READY | rejection card, state unchanged, 0 calls |
| 5 | «Предложи краткий план реализации по этим требованиям» | план в conversation, State прежний |
| 6 | PLAN_APPROVED | Execution |
| 7 | «Покажи реализацию состояния и обработки retry по утверждённому плану» | normal answer и краткий Inspector источников/gate/commit |
| 8 | PAUSE, затем RESUME | тот же execution node, 0 calls |
| 9 | IMPLEMENTATION_READY | Validation, forward applied, 0 calls |
| 10 | «Какими проверками подтвердить состояния, retry и отсутствие повторной оплаты?» | обычный validation answer без auto-Done/recovery |
| 11 | «Проверка не пройдена» / VALIDATION_FAILED | Validation -> Implementation, revision +1, Recovery applied, 0 calls, conversation unchanged |
| 12 | «Проверка отмечена как не пройденная. Пересмотри реализацию: исключи параллельные retry и сохрани подтверждение оплаты» | correction discussion, State прежний; query явно сообщает контекст исправления |
| 13 | IMPLEMENTATION_READY | повторный forward к Validation, 0 calls |
| 14 | VALIDATION_CONFIRMED | forward к Done, no progress, read-only chat |

Успешный демонстрационный маршрут содержит пять generation calls, один forbidden skip, Pause/Resume и один applied recovery с повторным forward до Done. Фактические failures/refusals сохраняются как результаты, без automatic repair или повторов ради картинки. VALIDATION_FAILED применяется явно для демонстрации recovery; это не утверждение о реально выполненном автоматическом тесте. Event/receipt не записывается в conversation и не добавляется скрыто в model input: контекст исправления сообщает следующий пользовательский query.

REQUIREMENTS_REVISION_REQUIRED и второй forbidden skip (Execution + VALIDATION_CONFIRMED) обязательны offline; оба educational controls могут оставаться доступными в своих узлах, но live не удлиняется вторым skip. Проверка альтернативной policy обязательна offline и доступна через New Task; второй длинный live не требуется. Достаточно открыть Inspector один-два раза, включая recovery before/event/after/outcome/Not required, без чтения JSON. Инструкции запуска хранятся в component README; Day README — краткий русский обзор и подтверждённые результаты.

## Risks / Trade-offs

- [Free prose может противоречить checked decisions] -> coverage явно bounded; regression запрещает ложный semantic-safe claim, никакие side effects из prose не выполняются.
- [Setup в нескольких stores частично сохранится] -> durable immutable creation record до materialization, reserved IDs, explicit completion и fault-injection tests; общей транзакции не обещать.
- [Расширение definition переопределит старые задачи] -> отдельные checkout-v1/v2 и namespace, machine compatibility check без migration.
- [Allowed recovery примут за ошибку или откат history] -> typed outcome, обычная operation card и source equality tests; история сохраняется.
- [Reusable extraction изменит старые labs] -> минимальные helpers/default-preserving interfaces, отдельные Day 15 namespace/API/candidate и targeted regressions.
- [State/Pause изменится во время Send] -> общий single-worker guard всех writes; distributed режим вне scope.
- [Пользователь подтвердит validation без реальных тестов] -> event обозначает user/application confirmation; качество проверки не выдаётся за FSM guarantee.
- [Накопление history и receipts увеличивает объём] -> один bounded demo workflow, 50 runtime receipts, отдельный Raw Debug; без скрытой summarization/truncation/replay. Context/provider failure остаётся technical outcome.
- [New Conversation теряет содержательные детали] -> явно сохраняет task sources/position, но не transcript; основной live не требует смены conversation.
- [Profile preferences конфликтуют с hard rules] -> policy gate проверяет decisions, Profile регулирует presentation; profile adherence не является invariant verdict.

## Migration Plan

1. Добавить checkout-v2 только в Day 15 composition, новые domain/API/UI модули и отдельные Playground paths; проверить уникальность database paths в backend lifespan. Новые setup records не внедрять в existing strict schemas.
2. Подключить reusable helpers с обратной совместимостью существующих вызовов; старые Day endpoints, data и candidate contracts не мигрировать.
3. Добавить Day 15 destination, README и relative ссылку в корневом README, выполнить targeted checks и approved live flow.
4. Для rollback отключить новый destination/router/wiring и вернуть изменения общих helpers; Day 15 данные оставить на месте, не удалять и не импортировать в старые namespaces. Unsupported future config versions возвращают incompatibility без silent reinterpretation.
