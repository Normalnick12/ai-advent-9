## Purpose

Android Day 25 предоставляет небольшой наглядный mini-chat с источниками и Task Memory, сохраняя backend источником истины и не подменяя воспроизводимый CLI acceptance ручной работой в emulator.

## ADDED Requirements

### Requirement: Chat exposes answers sources and task memory

Day 25 SHALL показывать user/assistant bubbles, sources под каждым answered response, collapsible Task Memory card с goal/constraints/terms/clarifications и явные loading/error/session count states. Backend SHALL владеть history/memory/RAG; Android SHALL передавать только current message/session identity/expected revision, не local history или model settings. Runtime/model abstention SHALL отличаться от technical error и показывать отсутствие memory update; фиктивные sources SHALL не добавляться. Source viewer, streaming, WebSockets и production chat features SHALL отсутствовать.

#### Scenario: Grounded answer updates the screen
- **WHEN** backend подтверждает answered turn
- **THEN** UI добавляет пару с sources и отображает только подтверждённые memory/count/revision; pending send не изображается accepted answer

#### Scenario: Abstention or invalid generation
- **WHEN** backend подтверждает abstention либо возвращает technical/validation failure
- **THEN** abstention отображается с пустыми sources и skipped memory update, а failure отображается как error без fabricated successful pair или optimistic memory update

### Requirement: Session restore and recovery are read only

Android SHALL хранить только Day 25 current session ID в отдельном local namespace. Cold start с ID SHALL читать authoritative metadata/memory до разрешения Send, без create/generation/replay; без ID SHALL открывать пустой экран без automatic create. Старые bubbles восстанавливать не требуется. Unknown outcome SHALL блокировать повторную отправку до reconciliation и предлагать read, без automatic retry/reset/new session. Explicit reset валидного ID SHALL очищать local identity только после DELETE 204, включая уже отсутствующую session; transport/server error SHALL не разрешать clear. Для malformed local ID explicit reset SHALL очищать непригодную local identity без HTTP delete. Lost/missing session SHALL отображаться явно.

#### Scenario: Existing chat is reopened
- **WHEN** Android открывается с сохранённым Day 25 ID
- **THEN** backend read восстанавливает тот же ID/count/memory; отсутствие старых bubbles не превращает count в ноль и не создаёт новую session

#### Scenario: Send result is uncertain
- **WHEN** transport не подтверждает исход Send
- **THEN** UI показывает unknown/recovery, перечитывает по явному действию authoritative state и не повторяет Send; подтверждённый при read turn показывается с его saved sources, недоступные сведения остаются unknown

#### Scenario: Reset response was lost
- **WHEN** DELETE уже выполнен, но local ID остался после потерянного response и пользователь явно повторяет reset
- **THEN** DELETE отсутствующей session подтверждается 204 и local ID очищается без generation или automatic create

### Requirement: Android remains a small demonstration client

Day 25 SHALL использовать существующее приложение и navigation, сохраняя поведение прежних дней. UI SHALL не запускать acceptance scripts или оценивать grounding/memory самостоятельно. Два длинных сценария и provider-call accounting SHALL выполняться backend/CLI harness независимо от emulator; Android demonstration SHALL быть отдельным коротким пользовательским flow.

#### Scenario: Long-scenario acceptance runs without Android
- **WHEN** emulator отсутствует, но backend harness и pinned index доступны
- **THEN** оба frozen scenarios и saved report доступны независимо от Android, а UI integration проверяется отдельными focused tests
