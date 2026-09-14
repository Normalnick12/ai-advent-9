## Purpose

Определяет компактную лабораторию Day 11 в Android, которая делает видимыми ownership, lifecycle и влияние трёх memory layers без превращения эксперимента в постоянный technical dump.

## ADDED Requirements

### Requirement: Main screen presents three memory layers and explicit actions

Day 11 main SHALL показывать отдельные Short-term, Working и Long-term cards, current experiment step, latest response и небольшой A–E dashboard. Short-term SHALL показывать active session/count, Working — current task state, Long-term — owner data; полные identities SHALL быть доступны в inspector. Explicit write SHALL показывать слой/ключ/значение до dispatch. Действия SHALL включать Initialize при отсутствии owner, seed Send, structured writes/remove, New Conversation, New Task, Clear Long-term и verification. Отдельные Reset/Delete и reactivation SHALL не требоваться.

#### Scenario: User can identify the target memory
- **WHEN** подготовлено сохранение current_architecture=MVI
- **THEN** UI показывает Working и ключ/значение; после подтверждённого backend state обновляется Working card без выдуманного изменения других слоёв

#### Scenario: New conversation is not described as deletion
- **WHEN** пользователь выбирает «Новый разговор»
- **THEN** UI объясняет пустой active Short-term и сохранение previous inactive history, Working и Long-term

### Requirement: Inspector distinguishes stored selected excluded and actual response

Раскрываемый inspector SHALL показывать stored memory, selected/excluded records, exclusion reasons, current identities и immutable assembled request snapshot соответствующего response. Long-term MVVM при Working MVI SHALL отображаться как сохранённая, но исключённая preference. Inactive task/session SHALL обозначаться сохранёнными вне active context. Raw values, query и response SHALL не переписываться ради локализации. Secrets/headers SHALL не отображаться. После mutation предыдущий observation SHALL быть помечен snapshot, а не выдаваться за новый request.

#### Scenario: Override remains visible as stored
- **WHEN** пользователь раскрывает inspector на A
- **THEN** видит stored MVVM, selected MVI и причину working_override; provider input не содержит исключённую preference из diagnostics

#### Scenario: Old response belongs to old state
- **WHEN** после A изменён Working override, но B ещё не выполнена
- **THEN** latest A response показан как предыдущий снимок, новый successful observation не появляется

### Requirement: Dashboard separates context checks from model checks

Для A–E dashboard SHALL показывать независимые input checks и output checks по пяти exact fields, expected absence/null и explicit unavailable/error states. Free next_step SHALL показываться отдельно без автоматической оценки общего качества. Верный context при ошибочном response SHALL не становиться storage error. Числа score SHALL иметь узкую подпись, не «качество памяти/агента» в целом.

#### Scenario: Model ignores the selected architecture
- **WHEN** backend сообщает correct input MVI и output MVVM
- **THEN** UI показывает успешную проверку context и ошибку использования architecture в ответе отдельно

#### Scenario: Probe failure is not a zero score
- **WHEN** response не получен или structured output invalid
- **THEN** input checks остаются видны, output measurement unavailable/invalid с причиной вместо фиктивного 0/5

### Requirement: Restore and navigation do not replay experiments

Opening Day 11 SHALL читать current state с backend без mutations/provider calls. Server binding SHALL быть источником active identities; local cache SHALL NOT заменять его. Навигация и Activity recreation в текущем процессе SHALL сохранять UI/observations и не повторять Send/verify/lifecycle. Cold start/backend restart SHALL допускать потерю runtime dashboard/last observation и SHALL восстанавливать memory/current identities read-only. Отсутствие observations SHALL не означать потерю памяти. Unknown outcome SHALL вести к explicit read/recovery без automatic replay или создания нового owner.

#### Scenario: Restart restores memory without results persistence
- **WHEN** Android заново читает backend после restart на непустом A-state
- **THEN** cards показывают восстановленные слои/identities; утраченные results обозначены непроверенными и generation отсутствует

#### Scenario: Navigation during generation
- **WHEN** пользователь выходит в каталог и возвращается во время probe
- **THEN** видит ту же текущую операцию/результат, без второго provider request

#### Scenario: Lost lifecycle response
- **WHEN** HTTP outcome New Task неизвестен
- **THEN** UI читает binding и показывает confirmed current state либо recovery error, не выполняя New Task повторно автоматически

### Requirement: Controlled steps remain reviewable and explicit

UI SHALL предоставлять последовательность setup/A–E с видимыми exact markers и одним неизменным verification question. Каждый memory action и probe SHALL запускаться явно; read/navigation SHALL не запускать следующий шаг. После потери runtime progress SHALL быть доступно явное продолжение применимого этапа по backend state, без восстановления scores из expected values. Повторная подготовка SHALL не очищать память скрыто.

#### Scenario: Stage C follows the confirmed new session
- **WHEN** New Conversation не подтверждена или backend сообщает scenario_not_applicable
- **THEN** C не отображается успешно пройденной; доступно чтение состояния/исправление подготовки без hidden verification call
