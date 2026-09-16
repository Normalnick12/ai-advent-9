## ADDED Requirements

### Requirement: Day 13 navigation preserves task controls and observations without replay

Day 13 SHALL иметь отдельный destination и screen state, независимый от Day 02–12. Переходы main/inspector/каталог и Activity recreation SHALL сохранять composer draft, scroll, observations, optional notes и выполняющуюся попытку в процессе без повторных Sends/events/lifecycle operations. Back из inspector SHALL возвращать к тому же Day 13 main, из main — в каталог; клавиатура SHALL сохранять обычный приоритет закрытия. Cold start SHALL читать authoritative Memory/Profile/State без replay. Navigation SHALL не означать Pause, Resume или New Conversation.

#### Scenario: Rotation during send does not repeat the request
- **WHEN** устройство повёрнуто или пользователь возвращается из каталога во время Send
- **THEN** продолжается та же попытка или виден её результат, вторая generation/event operation не создаётся

#### Scenario: Inspector preserves the paused attempt
- **WHEN** пользователь покидает inspector status response и возвращается
- **THEN** доступен тот же immutable receipt, navigation не меняет Task State или conversation

#### Scenario: Earlier days remain independent
- **WHEN** пользователь выполняет Day 13 New Task/Pause/Resume и открывает Day 11/12 или более ранний день
- **THEN** identities, history, profiles, drafts и observations старых уроков прежние
