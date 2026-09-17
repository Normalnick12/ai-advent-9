# invariants-android Specification

## Purpose

Определяет компактную Android лабораторию Day 14, позволяющую увидеть действующие ограничения, принятый результат или отказ и раздельные доказательства generation, enforcement и conversation commit.

## Requirements

### Requirement: Compact lab exposes active rules and controlled actions

Экран SHALL показывать Current invariants card, краткие Memory/Profile/State summaries, current conversation/turn count, readiness и две actions: compatible request и conflicting request. Подготовка SHALL быть явной и показывать сохраняемые fixture values и необходимые workflow confirmations; read/open SHALL не запускать setup. Missing components SHALL допускать completion без overwrite существующих данных. Busy, incomplete setup, recovery и State вне ACTIVE execution SHALL блокировать proposal actions. Огромный stepper, free-text composer, policy editor и встроенный fake-provider simulator SHALL не требоваться.

#### Scenario: Ready task can run both controlled cases
- **WHEN** текущая task имеет согласованные Memory/Profile/State/policy и ACTIVE execution
- **THEN** видны четыре обязательных ограничения и две доступные actions без ручного ввода instructions или intent fields

#### Scenario: Partial setup stays reviewable
- **WHEN** task существует, но policy отсутствует
- **THEN** UI показывает existing task и missing policy, блокирует proposals и предлагает явное completion без повторного создания task

### Requirement: Result distinguishes refusal technical error and commit

Main SHALL отображать только trusted final answer или deterministic semantic refusal как conversational result. Technical errors SHALL иметь отдельное представление без normal refusal wording. Decision, provider dispatch и committed status SHALL читаться из backend receipt независимо друг от друга. Успешный HTTP response для request conflict SHALL NOT обозначаться как provider dispatch. Failed/unknown commit SHALL NOT показываться как успешно сохранённый ответ. Raw candidate SHALL не выводиться в main вместо final reply.

#### Scenario: Successful conflict handling used no provider
- **WHEN** backend вернул committed request-conflict refusal
- **THEN** UI показывает отказ и сохранённую пару с generation_calls=0 и not_dispatched

#### Scenario: Technical validation error is visible as an error
- **WHEN** после generation обязательная validation недоступна
- **THEN** UI показывает technical error, candidate not accepted и отсутствие новой пары без сообщения о нарушенном пользователем правиле

### Requirement: Inspector separates immutable evidence from current preview

Inspector SHALL показывать использованные Memory/Profile/State/policy snapshots, source/version metadata, rendered invariant guidance, actual messages/config/query, доступный raw/parsed candidate, parsing/validation status, violations, final decision и commit outcome. Storage, selection, assembly, enforcement и model adherence SHALL оставаться отдельными observations без общего score. Raw rejected candidate SHALL быть помечен как диагностический, отклонённый и не сохранённый в conversation. При pre-generation conflict actual request/candidate SHALL показываться absent; preview SHALL не подменять dispatch evidence. Secret values и headers SHALL не отображаться.

#### Scenario: Current state changes after a refusal
- **WHEN** после attempt пользователь создаёт новую conversation
- **THEN** historical receipt сохраняет исходные session/policy/source snapshots, current summary показывает новое состояние

#### Scenario: No generation has no raw candidate
- **WHEN** выбран request conflict и precheck его отклонил
- **THEN** inspector показывает exact violations, no provider call и отсутствие candidate, не заполняя поля fixtures

### Requirement: Recovery reads state without replaying an action

Cold start и recovery SHALL выполнять только read-only загрузку authoritative state. Unknown HTTP outcome SHALL приводить к read/reconciliation без автоматического повторения proposal, commit, setup, event или lifecycle action. Пока backend/current state неизвестен или busy, conflicting actions SHALL блокироваться. После восстановления history SHALL отражать durable commit, а отсутствующий runtime receipt SHALL оставаться unavailable. New Conversation/New Task SHALL быть явными действиями с lifecycle по invariants-experiment.

#### Scenario: Lost conflict response does not duplicate refusal
- **WHEN** user/refusal pair committed, но Android не получил HTTP response
- **THEN** read восстанавливает confirmed turn count, второй request conflict автоматически не отправляется и receipt не выдумывается

#### Scenario: Cold opening requires no credentials or generation
- **WHEN** пользователь открывает lab с сохранённой task
- **THEN** UI читает её состояние без provider calls, setup или replay и позволяет вернуться в каталог при ошибке backend
