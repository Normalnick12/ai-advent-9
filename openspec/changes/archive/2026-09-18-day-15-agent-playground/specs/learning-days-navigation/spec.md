## ADDED Requirements

### Requirement: Day 15 provides independent playground navigation without replay

Каталог SHALL добавлять доступный Day 15 после Day 14, сохраняя прежние destinations и порядок. Day 15 SHALL иметь независимые namespace и screen state. Opening SHALL выполнять только read-only загрузку без create/setup/Send/events. Внутренние destinations SHALL включать main, reviewed setup, Inspector и Raw Debug. Back из Raw Debug SHALL возвращать к тому же Inspector, из Inspector/setup — в main, из main — в каталог; IME SHALL сохранять стандартный приоритет закрытия. Переходы и Activity recreation SHALL сохранять drafts, receipt selection, sections/scroll и выполняющуюся попытку в процессе без cancellation/replay. Cold start SHALL read-only восстанавливать durable data, не потерянные runtime receipts.

#### Scenario: Raw debug round trip retains the selected historical attempt
- **WHEN** пользователь открывает Raw Debug ответа, поворачивает устройство и возвращается через Inspector в main
- **THEN** выбран тот же receipt и сохранён conversation draft, новая generation/event/setup operation не выполняется

#### Scenario: Day 15 does not change previous labs
- **WHEN** пользователь создаёт новую конфигурацию Day 15, переключает Profile или завершает task и открывает Days 11–14
- **THEN** их identities, policy, memory, history, drafts и observations прежние

#### Scenario: Navigation does not replay an operation
- **WHEN** пользователь покидает Playground во время Send и возвращается в том же процессе
- **THEN** видит продолжающуюся ту же attempt либо её результат без второго POST
