## Purpose

Определяет самостоятельное durable состояние задачи как детерминированный конечный автомат, независимый от conversation, Memory, Profile, лабораторных fixtures и LLM provider.

## ADDED Requirements

### Requirement: Task state has one canonical workflow position

Task State SHALL содержать immutable task_id и machine_id, canonical state_id, operational status ACTIVE или PAUSED и integer revision >= 0. Phase, step, expected_action, is_terminal и allowed_events SHALL выводиться из versioned machine definition и status; они SHALL NOT сохраняться или приниматься как независимо редактируемые поля. Снимки SHALL быть immutable для потребителя. Task State SHALL быть отдельным task-scoped subsystem от Working Memory при общем task_id.

#### Scenario: One node gives coherent metadata
- **WHEN** читается допустимый state_id конкретной definition
- **THEN** phase/step/expected_action/terminal metadata соответствуют ровно этому node, без произвольных сочетаний полей

#### Scenario: Invalid canonical data is rejected
- **WHEN** create/update/decode получает неизвестный status, отрицательную или нецелую revision, некорректную identity, extra fields либо независимо заданные phase/step/action
- **THEN** данные отклонены без изменения сохранённого State или provider calls

### Requirement: Machine identity pins the meaning of persisted nodes

Machine identity SHALL включать версию definition. Definition SHALL задавать initial node, конечный набор nodes с metadata и deterministic mapping пары node/event в next node. Initial node и endpoints всех transitions SHALL существовать, mapping SHALL быть однозначным, terminal nodes SHALL не иметь workflow exits. Неизвестная machine version или node SHALL давать явную несовместимость, без fallback, silent migration или переинтерпретации сохранённого State. Day 13 SHALL NOT предоставлять пользовательский DSL, registry management или редактор workflows.

#### Scenario: Unsupported definition cannot restore as another machine
- **WHEN** сохранённая machine_id не поддерживается текущей definition
- **THEN** чтение для использования/dispatch отклонено с incompatibility, запись не пересоздана и generation отсутствует

#### Scenario: Invalid definition is not executable
- **WHEN** definition содержит отсутствующий initial/target node, неоднозначный transition либо workflow exit из terminal node
- **THEN** definition отклонена до создания/применения State

### Requirement: Only explicit events resolve workflow transitions

Для ACTIVE non-terminal State явное событие SHALL разрешаться точным mapping current node/event. Client SHALL NOT выбирать next node напрямую. Resolver SHALL быть детерминированным и не зависеть от model output. Unknown event, отсутствующий mapping, workflow event при PAUSED и любое workflow event из terminal node SHALL отклоняться без State mutation, revision increment или provider calls. Успешный переход SHALL сохранять task_id/machine_id/status и увеличивать revision ровно на 1.

#### Scenario: Supported event advances exactly one edge
- **WHEN** ACTIVE current node имеет mapping для полученного explicit event
- **THEN** результирующий node равен target этого mapping, revision увеличена на 1 и никакого model classification не выполнено

#### Scenario: Invalid event cannot skip a step
- **WHEN** событие не является допустимым для current node/status либо клиент передаёт direct state_id update
- **THEN** операция отклонена, snapshot целиком совпадает с before state, provider calls равны нулю

#### Scenario: Text cannot become an event
- **WHEN** query или assistant reply содержит название supported event либо утверждение о завершении этапа
- **THEN** без отдельной explicit event operation durable State не меняется

### Requirement: Pause and resume preserve workflow position

PAUSE SHALL переводить каждый ACTIVE non-terminal node в PAUSED, RESUME SHALL переводить PAUSED non-terminal node в ACTIVE, сохраняя node и увеличивая revision ровно на 1. Повторный PAUSE при PAUSED, RESUME при ACTIVE и обе операции для terminal node SHALL отклоняться. Terminal node + PAUSED SHALL считаться invalid persisted state. Status ACTIVE SHALL означать отсутствие паузы, а доступность workflow progress SHALL дополнительно учитывать terminal condition. Expected action SHALL оставаться metadata node; при PAUSED оно описывает действие после Resume, а разрешённым управляющим событием SHALL быть только RESUME.

#### Scenario: Every non-terminal node supports a pause round trip
- **WHEN** для каждого non-terminal node выполнены PAUSE затем RESUME с актуальными revisions
- **THEN** исходный node и ACTIVE восстановлены, revision увеличена на 2, связанные Memory/Profile и owner/task/session identities не меняются

#### Scenario: Terminal or repeated control operations fail
- **WHEN** запрошены PAUSE/RESUME для terminal node, PAUSE для PAUSED либо RESUME для ACTIVE
- **THEN** прежний snapshot/revision сохраняется и provider не вызывается

### Requirement: Durable writes are revision checked and atomic

Persistence contract SHALL поддерживать explicit initial creation, read и compare-and-set по expected revision независимо от physical layout. Initial State SHALL иметь initial node, ACTIVE и revision 0. Повторное explicit создание уже существующего State той же task/machine SHALL возвращать существующий snapshot без reset; несовместимая machine SHALL отклоняться. CAS SHALL проверять expected revision и неизменность identities, сохранять целиком валидный next snapshot с revision old+1 либо ничего. Stale operation SHALL отклоняться до effects, включая потенциально повторённое событие. Failed write SHALL не публиковать неподтверждённый runtime State.

#### Scenario: Concurrent requests cannot overwrite progress
- **WHEN** два update используют одну expected revision и первый committed
- **THEN** второй отклонён как stale, первый State сохранён, revision увеличена только один раз

#### Scenario: Repeated initialization is not reset
- **WHEN** explicit initial creation повторяется для существующей progressed или paused task
- **THEN** возвращается прежний node/status/revision без изменения

#### Scenario: Write failure rolls back
- **WHEN** запись next snapshot завершается ошибкой до commit
- **THEN** runtime read и reopen возвращают прежний snapshot, частичный update не виден

### Requirement: Restore is exact and never silently repairs state

Reopen SHALL восстанавливать task_id/machine_id/state_id/status/revision точно без provider calls. Missing State SHALL явно отличаться от invalid record/schema, неподдерживаемой definition и недоступного storage. Reads SHALL не создавать State и не сбрасывать corruption к initial node. Store SHALL сохранять только current State/revision без обязательной durable transition history; runtime observations SHALL не требоваться для restore.

#### Scenario: Paused state survives reopen
- **WHEN** store закрыт и открыт после сохранённого PAUSED non-terminal State
- **THEN** snapshot совпадает с before reopen и generation/count calls равны нулю

#### Scenario: Corrupt terminal status fails closed
- **WHEN** restore обнаруживает terminal node с PAUSED, unknown node/status, invalid revision или inconsistent identity
- **THEN** возвращается ошибка без generation, скрытого исправления или потери прежних данных

### Requirement: Workflow rendering is a pure independent projection

Validated State и соответствующая definition SHALL давать deterministic provider-neutral workflow representation с node, phase, step, expected_action и status. Representation SHALL указывать authoritative current workflow position, явное управление transitions приложением и ограничение PAUSED на status/clarification conversation без самостоятельного возобновления/продвижения. Projection SHALL не читать stores, вызывать provider, включать Memory values, metadata identities/revisions как semantic instructions или зависеть от expected model responses. Она SHALL быть usable независимо от request preparation layer.

#### Scenario: Metadata does not become semantic state content
- **WHEN** два snapshots различаются только task_id/revision при одинаковых definition/node/status
- **THEN** semantic workflow section совпадает, identities/revisions остаются observation metadata

#### Scenario: Pause changes workflow guidance without changing position
- **WHEN** один node переключён с ACTIVE на PAUSED
- **THEN** renderer сохраняет phase/step/expected_action и отражает paused conversation policy

### Requirement: State contracts remain independent of providers and storage layout

FSM domain и persistence contract SHALL NOT зависеть от LLM client/config/settings, SDK, response payload, Memory/Profile storage, количества database files, UI, experiment DTO, fixtures или expected answers. Definition SHALL передаваться как отдельные validated данные. Изменение physical storage layout SHALL сохранять identities и create/read/CAS semantics без изменения FSM domain API.

#### Scenario: Different storage layout preserves domain behavior
- **WHEN** persistence adapter заменён с сохранением canonical records и revisions
- **THEN** downstream State resolution, rendering и event operations используют те же task/machine identities без paths других подсистем
