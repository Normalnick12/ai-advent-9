## ADDED Requirements

### Requirement: Day 14 has an independent destination without replay

Каталог SHALL добавлять доступный Day 14 после Day 13, сохраняя прежние карточки и их порядок. Day 14 SHALL иметь собственный screen state и namespace, независимые от Day 02–13. Открытие SHALL выполнять только read-only загрузку без setup/generation/events. Переходы main/setup/inspector/каталог и Activity recreation SHALL сохранять текущую попытку, observations и scroll в процессе без повторных действий. Back из setup/inspector SHALL возвращать в main, из main — в каталог. Cold start SHALL читать durable state без восстановления выдуманных receipts или replay.

#### Scenario: Rotation does not repeat generation or refusal
- **WHEN** устройство повёрнуто во время compatible или conflicting action
- **THEN** продолжается та же попытка либо виден её результат, второй запрос и duplicate pair не создаются

#### Scenario: Inspector round trip preserves evidence
- **WHEN** пользователь выходит из inspector в каталог и возвращается
- **THEN** доступен тот же historical receipt в текущем процессе, navigation не меняет policy, task или conversation

#### Scenario: Other days remain independent
- **WHEN** Day 14 выполняет New Task или сохраняет refusal, затем открыт более ранний Day
- **THEN** его identities, history, settings и observations неизменны
