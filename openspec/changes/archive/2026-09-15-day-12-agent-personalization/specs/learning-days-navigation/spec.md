## ADDED Requirements

### Requirement: Day 12 navigation preserves profile editing and experiment state without replay

Day 12 SHALL иметь самостоятельный destination и screen state, независимый от Day 02–11. Переходы main/editor/inspector/каталог и Activity recreation SHALL сохранять drafts, selection display, observations, human notes, scroll и выполняющуюся попытку в процессе без повторных mutations/generation. Back из editor/inspector SHALL возвращать к тому же main, из main — к каталогу; Back SHALL не сохранять draft автоматически. Cold start SHALL читать authoritative backend profiles/binding/Memory по profile-personalization-android без replay; исчезнувшие runtime comparisons SHALL не подменяться fixtures. Navigation SHALL не менять active Profile или Memory.

#### Scenario: Editor round trip preserves an unsaved draft
- **WHEN** пользователь меняет typed fields, поворачивает устройство и возвращается в editor
- **THEN** draft сохранён в процессе, backend Profile прежний до explicit Save, provider calls отсутствуют

#### Scenario: Inspector round trip preserves the actual attempt
- **WHEN** пользователь открывает inspector ответа A, выходит в каталог и возвращается
- **THEN** тот же captured snapshot доступен, новая A/B probe не выполняется

#### Scenario: Older days retain their independent state
- **WHEN** пользователь выполняет Day 12 Profile switch/New Task и открывает Day 11 либо более ранний день
- **THEN** старые identities, history, settings, drafts и results не меняются
