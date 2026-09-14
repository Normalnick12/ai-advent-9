## MODIFIED Requirements

### Requirement: Catalog is the application entry screen

При обычном запуске без восстанавливаемого состояния приложение SHALL открывать каталог «AI Advent» с подсказкой «Выберите день обучения». Каталог SHALL показывать доступные Android-уроки в порядке номера: 02 «Управление ответом», 03 «Лаборатория рассуждений», 04 «Лаборатория температуры», 05 «Лаборатория моделей», 06 «Первый агент», 07 «Сохранение контекста», 08 «Работа с токенами», 09 «Управление контекстом: сжатие истории», 10 «Управление контекстом: разные стратегии», 11 «Модель памяти агента». Нижняя панель навигации SHALL отсутствовать во всём приложении. Day 01 и ещё не реализованные Android-дни SHALL NOT отображаться как доступные уроки. Наличие сохранённого Day 07, Day 08, Day 09 ID или Day 10 run IDs, а также durable Day 11 memory binding SHALL NOT само по себе открывать урок или запускать turn/evaluation; пользователь SHALL иметь доступ к отдельным карточкам Day 07/08/09/10/11 после cold start.

#### Scenario: Fresh launch shows available days
- **WHEN** пользователь запускает приложение без восстанавливаемого состояния
- **THEN** виден каталог с десятью карточками 02, 03, 04, 05, 06, 07, 08, 09, 10 и 11 в указанном порядке
- **AND** ни один эксперимент или turn не открывается и не запускается автоматически
- **AND** нижняя панель и карточка Day 01 отсутствуют

### Requirement: Each catalog card opens its matching lesson

Нажатие любой части карточки SHALL открывать соответствующий урок без запуска эксперимента или turn. Доступность каталога и переходов SHALL NOT зависеть от доступности backend. Read-only загрузка каталога моделей при открытии Day 05 SHALL NOT блокировать навигацию или вызывать OpenAI. Открытие Day 06 SHALL показывать текущий или пустой chat без создания session. Открытие Day 07 SHALL показывать отдельную лабораторию «Сохранение контекста», читать сохранённый ID при первом открытии в новом процессе и при его наличии восстанавливать metadata read-only запросом. Day 08 SHALL открывать отдельную лабораторию «Работа с токенами» и при сохранённом собственном ID восстанавливать metadata без count/generation. Без ID Day 06/07 SHALL создавать session только при первой явной отправке; Day 08 — при первой явной отправке либо явной подготовке overflow. Day 09 SHALL открывать main chat «Управление контекстом: сжатие истории» и при собственном сохранённом ID read-only восстанавливать identity/count/summary metadata без count/generation; без ID session SHALL создаваться только после явного Send, а compare SHALL требовать существующую session. Day 10 SHALL открывать scenario-first main с selector независимых strategies; сохранённые run IDs SHALL восстанавливаться read-only без generation/extraction/count/evaluation. Без ID Day 10 run SHALL создаваться только перед первой явной отправкой. Day 11 SHALL открывать отдельную лабораторию «Модель памяти агента» и read-only читать current memory binding/слои, без Initialize, memory mutations, count или generation. При not_initialized создание owner/task/session SHALL требовать явного действия пользователя. Восстановление SHALL NOT блокировать возврат в каталог и SHALL NOT выполнять create или send.

#### Scenario: User selects each available day
- **WHEN** пользователь выбирает карточку дня 02, 03, 04, 05, 06, 07, 08, 09, 10 или 11
- **THEN** открывается соответственно управление ответом, лаборатория рассуждений, лаборатория температуры, лаборатория моделей, «Первый агент», «Сохранение контекста», «Работа с токенами», «Управление контекстом: сжатие истории», «Управление контекстом: разные стратегии» или «Модель памяти агента»
- **AND** переход не отправляет запрос генерации

#### Scenario: Backend is unavailable
- **WHEN** backend недоступен и пользователь открывает каталог и выбирает день
- **THEN** навигация работает; Day 05 показывает ошибку загрузки каталога моделей с повторной загрузкой, а ошибки генерации остальных дней остаются частью явного запуска эксперимента
- **AND** Day 06 и Day 07 без ID позволяют набрать сообщение; create выполняется только после явной отправки
- **AND** Day 07 с сохранённым ID показывает ошибку восстановления и явный retry, не создаёт замену и позволяет вернуться к дням

#### Scenario: Opening token diagnostics never starts the experiment
- **WHEN** пользователь открывает Day 08 при доступном или недоступном backend
- **THEN** навигация работает и не запускает count, generation или overflow preparation
- **AND** без ID доступен composer, с ID выполняется только metadata restore с явным retry при ошибке

#### Scenario: Opening compression does not prepare a summary
- **WHEN** пользователь открывает Day 09 main либо Details
- **THEN** навигация не выполняет generation/count/summary preparation, допускает read-only metadata restore и возврат при недоступном backend

#### Scenario: Opening context strategies does not evaluate a run
- **WHEN** пользователь открывает Day 10 main или dashboard
- **THEN** допускается только read-only restore, provider calls и automatic run creation отсутствуют, возврат доступен при ошибке backend

#### Scenario: Opening memory layers is read only
- **WHEN** пользователь открывает Day 11 main, inspector либо dashboard
- **THEN** разрешены read-only current state/preview, provider calls и implicit initialization отсутствуют; возврат работает при недоступном backend

## ADDED Requirements

### Requirement: Day 11 navigation preserves runtime observations without replay

Day 11 SHALL иметь отдельное состояние от Day 02–10. Переходы main/inspector/dashboard и каталог SHALL сохранять current UI/scroll/observations в процессе без повторных mutations или provider calls. Back из inspector/dashboard SHALL возвращать в Day 11 main, из main — в каталог. Cold start SHALL читать durable current identities и слои с backend без требования восстанавливать runtime observations. New Conversation/New Task/Clear Long-term SHALL не менять состояние старых уроков.

#### Scenario: Return from inspector
- **WHEN** пользователь открывает inspector, меняет ориентацию и возвращается
- **THEN** видит тот же Day 11 main/observation без повторной verification

#### Scenario: Day 11 lifecycle is isolated from older lessons
- **WHEN** пользователь выполняет New Task Day 11 и возвращается в Day 06–10
- **THEN** IDs, history, drafts и результаты старых уроков не меняются
