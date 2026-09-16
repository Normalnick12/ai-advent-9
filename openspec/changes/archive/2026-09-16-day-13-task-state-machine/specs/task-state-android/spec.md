## Purpose

Определяет Android лабораторию Day 13, показывающую formal Task State отдельно от Memory и Profile, с явными событиями, разговором при паузе и проверяемым actual request inspector.

## ADDED Requirements

### Requirement: Main screen exposes task position and explicit controls

Day 13 SHALL показывать compact Task/Memory summary, active Profile summary, phase/step/expected action/status, допустимые workflow events, Pause/Resume, New Conversation/New Task, current session/turn count, ordinary composer, последний ответ и вход в inspector. Полные IDs и technical JSON SHALL размещаться в inspector. Большой A–E stepper и постоянный JSON dump SHALL не требоваться. Readiness Memory/Profile/State, busy, errors и recovery SHALL быть различимы. Explicit setup SHALL показывать сохраняемые fixture values, не перезаписывая существующие данные автоматически.

#### Scenario: Ready execution state is understandable without JSON
- **WHEN** открыт ready EXECUTION_IMPLEMENT/ACTIVE
- **THEN** видны execution/implement/continue_implementation, Pause, событие IMPLEMENTATION_READY и обычный composer с актуальной session

#### Scenario: Partial preparation is visible
- **WHEN** Memory существует, а Profile или State не готовы
- **THEN** UI показывает сохранённые данные и недостающую подготовку, блокирует Send/events и предлагает соответствующую explicit setup operation без reset

### Requirement: Backend determines allowed events and confirmed state

Android SHALL использовать backend allowed_events и SHALL NOT содержать собственную transition table. State SHALL обновляться после подтверждённого response/read, без optimistic progress. Backend SHALL повторно проверять событие, identity и expected revision независимо от UI. Unknown event/DTO inconsistency SHALL не изображаться успешным переходом. Workflow confirmations SHALL не вызывать скрытый Send.

#### Scenario: Stale button cannot override authoritative state
- **WHEN** UI отправил event со старой revision
- **THEN** conflict виден, UI перечитывает backend без replay, прежний предполагаемый переход не публикуется как success

#### Scenario: Terminal task has no progress or pause controls
- **WHEN** backend сообщает DONE и пустой allowed_events
- **THEN** UI не предлагает workflow events или Pause/Resume, сохраняя read/inspector/conversation и New Task

### Requirement: Paused mode permits conversation while disabling workflow events

При PAUSED и ready state composer, New Conversation и Resume SHALL оставаться доступными; workflow events SHALL быть недоступны. Expected action SHALL показываться как действие после Resume. Busy/recovery SHALL блокировать conflicting actions независимо от status. UI SHALL различать PAUSED task и выполняющийся сетевой запрос, не обещая in-flight cancellation кнопкой Pause.

#### Scenario: Paused status question uses ordinary send
- **WHEN** PAUSED task готова и пользователь вводит «Где мы остановились?»
- **THEN** Send доступен, completed ответ и updated turn count видны, task остаётся на том же paused node

#### Scenario: Resume is explicit
- **WHEN** пользователь отправляет «Продолжим» при PAUSED без Resume
- **THEN** сам Send не изображается Resume, status меняется только после подтверждённой отдельной операции

### Requirement: Inspector displays actual immutable evidence

Inspector SHALL показывать stored/selected Task State, derived metadata, status/revision, rendered State section, Memory/Profile snapshots и selections, actual instructions/messages/settings/query/outcome, conversation_committed и optional last transition before/event/after. Runtime transition receipt SHALL быть отдельно маркирован от generation attempt и current preview. Historical receipts SHALL сохранять исходные snapshots и обозначаться историческими при изменении current state. Storage/selection/assembly/model-adherence SHALL отображаться раздельно без общего score. Human adherence notes SHALL не попадать в input. Secrets/headers SHALL не отображаться.

#### Scenario: State changes do not rewrite a previous attempt
- **WHEN** после status response выполнены New Conversation и Resume
- **THEN** inspector этого ответа сохраняет прежние session/revision/PAUSED и actual request, current main показывает новый ACTIVE snapshot

#### Scenario: No actual request exists after pre-dispatch rejection
- **WHEN** backend отклонил stale/incomplete request до generation
- **THEN** UI показывает not_dispatched и причину, а не preview как successful actual assembly

### Requirement: Two-conversation live flow is executable without hidden replay

UI SHALL позволять последовательно обязательный ordinary execution Send, подтверждение настоящего сохранённого transcript S0, Pause, New Conversation #1, ordinary status Send, New Conversation #2, Resume и ordinary continuation Send. После каждой New Conversation SHALL отображаться подтверждённая новая session и zero turn count при прежнем task/state/profile. Inspector финального continuation SHALL позволять проверить отсутствие обоих inactive transcripts. Переход к validation SHALL требовать отдельного explicit IMPLEMENTATION_READY.

#### Scenario: Status answer is excluded before continuation
- **WHEN** пользователь создаёт вторую новую conversation после status answer
- **THEN** count снова равен нулю, task остаётся PAUSED, после Resume финальный Send использует пустую pre-turn history и не запускает IMPLEMENTATION_READY

### Requirement: Recovery reads authoritative state without repeating actions

Opening/cold start SHALL выполнять read-only loading, без create/event/generation. Unknown HTTP outcome SHALL вести к read/reconciliation без automatic повторения New Task, New Conversation, event или Send. Пока current неизвестен/busy, conflicting actions SHALL блокироваться. После read успешный durable переход SHALL отображаться без replay; missing actual receipt SHALL оставаться unknown/unavailable. После process restart runtime results/notes/last transition SHALL не восстанавливаться из fixtures.

#### Scenario: Lost pause response is reconciled
- **WHEN** PAUSE committed, но response не получен Android
- **THEN** read восстанавливает PAUSED/revision, второй PAUSE не отправляется, отсутствие receipt не маскируется

#### Scenario: Cold start restores paused state without calls
- **WHEN** приложение открыто с durable PAUSED task
- **THEN** main восстанавливает backend state read-only, generation/event replay отсутствуют
