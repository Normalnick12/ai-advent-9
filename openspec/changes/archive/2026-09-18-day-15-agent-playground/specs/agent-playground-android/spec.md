## Purpose

Определяет Android Agent Playground как понятный интерфейс задачи, диалога и явных workflow actions, с progressive disclosure диагностики и восстановлением без повторных операций.

## ADDED Requirements

### Requirement: Main screen prioritizes the task and conversation

Main SHALL показывать Coding Agent, task title, current stage/step, next action, active Profile selector, compact immutable policy, committed chat и contextual lifecycle controls. Last operation result SHALL быть понятным пользователю. UUIDs, revisions, snapshot hashes, raw candidates, provider settings и receipt JSON SHALL NOT отображаться на main. Accepted answers и safe invariant refusals SHALL быть assistant messages; rejected raw candidate и technical failures SHALL NOT становиться обычными assistant bubbles. Pending user input SHALL визуально отличаться от committed history и не считаться сохранённым до подтверждения.

#### Scenario: User can understand the current task without Inspector
- **WHEN** открыта execution task
- **THEN** видно, что реализуется, какой этап, что делать дальше, активный Profile, действующие rules и разговор без чтения JSON

#### Scenario: Technical failure preserves retryable draft without a fake answer
- **WHEN** Send завершился technical error до commit
- **THEN** показана operation error, draft доступен для последующего явного действия, новая committed pair и synthetic refusal bubble отсутствуют

### Requirement: Creation is one reviewed typed setup flow

UI SHALL объединять task, Profile selection, fixed workflow preview и четыре typed policy controls в один reviewed flow перед explicit creation. Cold opening SHALL NOT выполнять setup. Partial setup SHALL показывать сохранённые choices и действие «Завершить подготовку» на тех же IDs; normal actions SHALL быть заблокированы до readiness. Current policy SHALL показываться read-only; «Новая задача» SHALL открывать новый review без изменения существующей task до confirmation. Отмена review SHALL не выполнять writes.

#### Scenario: Review changes do not affect the current task
- **WHEN** пользователь меняет policy draft новой task и выходит без подтверждения
- **THEN** текущая task, conversation, Profile binding и policy остаются прежними, provider не вызван

#### Scenario: Incomplete setup restores its actual choices
- **WHEN** после process restart backend возвращает pending nondefault configuration
- **THEN** UI показывает эту configuration и explicit completion, не подменяет её defaults и не отправляет create повторно

### Requirement: Contextual controls follow backend authority

Normal lifecycle controls SHALL строиться по backend allowed_events; Android SHALL NOT хранить собственную transition table или извлекать event из model text. Event labels SHALL быть понятными русскими действиями. Возможность Send SHALL учитывать backend readiness/terminal semantics и local busy/persistence reconciliation. Успешный domain recovery SHALL NOT сам по себе включать error/reconciliation blocking; normal controls SHALL обновляться по recovered State. Profile switch, New Conversation, New Task и events SHALL быть недоступны во время конфликтующей операции. Отправленная операция SHALL NOT повторяться из-за duplicate tap, recomposition или navigation.

#### Scenario: Plan approval shows only applicable normal controls
- **WHEN** backend сообщает PLANNING_APPROVAL с PLAN_APPROVED, REQUIREMENTS_REVISION_REQUIRED и PAUSE
- **THEN** main показывает «Утвердить план», «Уточнить требования» и «Приостановить», без normal кнопок завершения implementation/validation

#### Scenario: Validation offers both confirmation and recovery
- **WHEN** backend сообщает VALIDATION_CHECK с VALIDATION_CONFIRMED, VALIDATION_FAILED и PAUSE
- **THEN** main показывает normal controls «Подтвердить проверку», «Проверка не пройдена» и «Приостановить»; recovery не скрыт в educational invalid actions

### Requirement: Allowed recovery has a normal actionable operation result

Confirmed recovery SHALL отображаться отдельной удерживаемой operation card до следующего действия либо явного закрытия: applied outcome, before/event/after, следующий шаг, Provider not required и Conversation unchanged. Recovery SHALL NOT отображаться как invalid transition, technical error, assistant bubble или очищать history/draft. Normal actions SHALL соответствовать returned recovered State; UI SHALL NOT выводить или применять recovery из query/model text.

#### Scenario: Failed validation returns the task to implementation
- **WHEN** explicit «Проверка не пройдена» получает confirmed VALIDATION_FAILED result
- **THEN** карточка сообщает «Проверка не пройдена. Задача возвращена на этап реализации. Следующий шаг: исправить найденные проблемы», provider не требуется, transcript прежний; доступны implementation actions и обычный Send, без error banner

#### Scenario: Requirements revision returns to requirements
- **WHEN** explicit «Уточнить требования» получает confirmed REQUIREMENTS_REVISION_REQUIRED result
- **THEN** карточка сообщает о возврате к требованиям и необходимости повторного согласования плана, transcript прежний; controls обновляются для PLANNING_REQUIREMENTS

### Requirement: Educational invalid events use the real lifecycle boundary

Отдельный раскрываемый educational action SHALL позволять отправить IMPLEMENTATION_READY из PLANNING_APPROVAL и VALIDATION_CONFIRMED из EXECUTION_IMPLEMENT через обычную backend lifecycle operation. Normal controls SHALL не загромождаться заведомо неверными кнопками. UI SHALL NOT подменять запрос локальным simulated rejection. Result SHALL показывать rejected action, why, current stage, required next action, State unchanged и Provider not required. Это SHALL быть отдельная operation card, видимая до следующего действия или явного закрытия, не conversation pair; её durable persistence не требуется. После rejection normal controls SHALL оставаться работоспособными.

#### Scenario: Invalid jump is visible and does not poison chat
- **WHEN** educational action на согласовании плана получает deterministic rejection
- **THEN** карточка объясняет необходимость утверждения плана, transcript не меняется, затем можно применить PLAN_APPROVED

### Requirement: Paused and completed states have distinct user meaning

PAUSED SHALL показывать «Задача приостановлена», остановленный этап, действие после Resume и единственный lifecycle control Resume. Composer для clarification SHALL оставаться доступным при readiness и отсутствии busy/recovery, с указанием, что Send не возобновляет задачу. Busy SHALL показываться отдельно и SHALL NOT называться Pause. DONE SHALL показывать «Задача завершена», read-only chat, доступные history/Inspector и «Новая задача» без progress controls/automatic reset.

#### Scenario: Resume restores the same position
- **WHEN** execution task после Pause получает успешный Resume
- **THEN** виден тот же этап реализации и его contextual action, без повторного generation

#### Scenario: Done is not presented as another active work step
- **WHEN** State terminal при operational status ACTIVE
- **THEN** UI использует terminal metadata и показывает completed read-only task

### Requirement: Inspector progressively explains the selected operation

Inspector SHALL открываться для конкретной attempt или committed response. Level 1 SHALL показывать outcome, provider dispatch/count когда известен, conversation commit, State/Profile used, bounded invariant coverage и applicable lifecycle result. Lifecycle summary SHALL явно различать Forward applied / Recovery applied / Forbidden transition rejected (Pause/Resume отдельно), показывать before/event/after, revisions и next action; generic success/fail SHALL NOT заменять эти outcomes. Level 2 SHALL содержать expandable semantic sections Memory, Profile, Task State, Invariants, Request, Validation/Enforcement, Lifecycle и Conversation commit. Memory SHALL показывать selected facts/turn count/exclusions; Request SHALL различать resolved sources и actual dispatched input. Полный JSON SHALL быть только в отдельном Raw Debug, содержащем exact IDs/revisions/snapshots/messages/config/provider outcome/raw and parsed candidate/violations/receipt. Raw rejected data SHALL быть помечены diagnostic/untrusted и не переиспользоваться для Send.

#### Scenario: Developer understands acceptance without raw data
- **WHEN** открыт receipt успешного Send
- **THEN** первым виден accepted outcome, actual calls, committed pair и bounded coverage; Memory/Profile/State доступны понятными sections, raw JSON скрыт

#### Scenario: Recovery evidence explains the applied reverse edge
- **WHEN** выбран receipt VALIDATION_FAILED после confirmed recovery
- **THEN** Inspector показывает Before: Validation, Event: Validation Failed, After: Implementation, Outcome: Recovery applied, revision +1, Provider: Not required/calls=0 и Conversation: unchanged; это не rejected transition

#### Scenario: Later forward progress preserves recovery evidence
- **WHEN** после recovery применён IMPLEMENTATION_READY и открыт historical recovery receipt
- **THEN** его After остаётся Implementation, Current может показывать Validation отдельно; outcome не пересчитывается из current State

#### Scenario: No dispatch means no actual request
- **WHEN** открыта попытка без provider dispatch
- **THEN** Inspector не выдаёт preview за actual messages и не показывает assembly passed по отсутствующему request

### Requirement: Inspector preserves historical evidence and distinct absence states

Current SHALL отображаться отдельно от Used in this turn. Profile switch, State event, Memory mutation и New Conversation SHALL NOT менять выбранный historical receipt. Runtime receipts SHALL быть связаны с attempt и conversation response, а не только с последней операцией. После process death утраченный receipt SHALL обозначаться «Диагностика попытки недоступна». UI SHALL различать Not applicable, Not attempted, Not required, Unavailable, Failed и Unknown; отсутствие данных SHALL NOT превращаться в pass, error или нулевой измеренный usage. Invariant checks SHALL обозначать проверенные decisions, не всю семантику текста/кода.

#### Scenario: Historical answer retains its original profile
- **WHEN** пользователь после смены Profile открывает Inspector предыдущего ответа
- **THEN** Used in this turn показывает прежний Profile, Current при наличии — новый, и оба не смешиваются

#### Scenario: Unknown commit is not shown as failure or success
- **WHEN** receipt подтверждает validation, но commit outcome неизвестен
- **THEN** summary показывает technical/unknown persistence отдельно от passed decisions и предлагает read/reconcile без automatic Send

### Requirement: Restore and error recovery do not replay mutations

Первое открытие SHALL выполнять только read-only configuration/current reads. Cold restore SHALL загружать durable transcript и источники; runtime diagnostics SHALL не выдумываться. При неизвестном Send/event outcome UI SHALL выполнять read/reconcile либо показывать явный read retry, не повторять POST автоматически. Пока результат не согласован, mutations SHALL быть заблокированы. Navigation/Activity recreation SHALL сохранять draft, review draft, selected receipt, expanded sections, scroll и in-flight operation в процессе. Узкий экран, увеличенный шрифт, системные панели и IME SHALL не перекрывать controls и readable content.

#### Scenario: Lost Send response restores a committed pair
- **WHEN** Send response потерян, а authoritative read содержит сохранённый turn
- **THEN** transcript показывает durable pair без второго Send, receipt остаётся unavailable если не был получен

#### Scenario: Lost recovery response does not repeat the reverse edge
- **WHEN** response VALIDATION_FAILED потерян, а authoritative read показывает EXECUTION_IMPLEMENT с новой revision
- **THEN** UI показывает фактическое recovered State без повторного POST, rewind conversation или fabricated historical receipt; блокировка reconciliation снимается после согласования

#### Scenario: Backend unavailable still permits navigation
- **WHEN** current/recovery read не удался
- **THEN** доступен явный read retry и возврат к каталогу, но implicit initialization и mutations отсутствуют

#### Scenario: Narrow layout preserves usable conversation controls
- **WHEN** Playground/Inspector открыт на узком экране с увеличенным шрифтом и клавиатурой
- **THEN** labels и ответы переносятся, controls доступны прокруткой, composer и Back не перекрываются inset-ами
