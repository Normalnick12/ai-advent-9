## MODIFIED Requirements

### Requirement: Catalog is the application entry screen

При обычном запуске без восстанавливаемого состояния приложение SHALL открывать каталог «AI Advent» с подсказкой «Выберите день обучения». Каталог SHALL показывать доступные Android-уроки в порядке номера: 02 «Управление ответом», 03 «Лаборатория рассуждений», 04 «Лаборатория температуры», 05 «Лаборатория моделей», 06 «Первый агент», 07 «Сохранение контекста», 08 «Работа с токенами», 09 «Управление контекстом: сжатие истории», 10 «Управление контекстом: разные стратегии». Нижняя панель навигации SHALL отсутствовать во всём приложении. Day 01 и ещё не реализованные Android-дни SHALL NOT отображаться как доступные уроки. Наличие сохранённого Day 07, Day 08, Day 09 ID или Day 10 run IDs SHALL NOT само по себе открывать урок или запускать turn/evaluation; пользователь SHALL иметь доступ к отдельным карточкам Day 07/08/09/10 после cold start.

#### Scenario: Fresh launch shows available days
- **WHEN** пользователь запускает приложение без восстанавливаемого состояния
- **THEN** виден каталог с девятью карточками 02, 03, 04, 05, 06, 07, 08, 09 и 10 в указанном порядке
- **AND** ни один эксперимент или turn не открывается и не запускается автоматически
- **AND** нижняя панель и карточка Day 01 отсутствуют

### Requirement: Each catalog card opens its matching lesson

Нажатие любой части карточки SHALL открывать соответствующий урок без запуска эксперимента или turn. Доступность каталога и переходов SHALL NOT зависеть от доступности backend. Read-only загрузка каталога моделей при открытии Day 05 SHALL NOT блокировать навигацию или вызывать OpenAI. Открытие Day 06 SHALL показывать текущий или пустой chat без создания session. Открытие Day 07 SHALL показывать отдельную лабораторию «Сохранение контекста», читать сохранённый ID при первом открытии в новом процессе и при его наличии восстанавливать metadata read-only запросом. Day 08 SHALL открывать отдельную лабораторию «Работа с токенами» и при сохранённом собственном ID восстанавливать metadata без count/generation. Без ID Day 06/07 SHALL создавать session только при первой явной отправке; Day 08 — при первой явной отправке либо явной подготовке overflow. Day 09 SHALL открывать main chat «Управление контекстом: сжатие истории» и при собственном сохранённом ID read-only восстанавливать identity/count/summary metadata без count/generation; без ID session SHALL создаваться только после явного Send, а compare SHALL требовать существующую session. Day 10 SHALL открывать scenario-first main с selector независимых strategies; сохранённые run IDs SHALL восстанавливаться read-only без generation/extraction/count/evaluation. Без ID Day 10 run SHALL создаваться только перед первой явной отправкой. Восстановление SHALL NOT блокировать возврат в каталог и SHALL NOT выполнять create или send.

#### Scenario: User selects each available day
- **WHEN** пользователь выбирает карточку дня 02, 03, 04, 05, 06, 07, 08, 09 или 10
- **THEN** открывается соответственно управление ответом, лаборатория рассуждений, лаборатория температуры, лаборатория моделей, «Первый агент», «Сохранение контекста», «Работа с токенами», «Управление контекстом: сжатие истории» или «Управление контекстом: разные стратегии»
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

## ADDED Requirements

### Requirement: Day 10 navigation preserves independent strategy runs and outputs

Day 10 SHALL сохранять независимые Window/Facts/Branching states при selector/main/dashboard/inspector/каталог переходах и Activity recreation по `context-strategies-android`. Navigation SHALL NOT reset-ить, отменять или повторять выполняющиеся Sends/evaluations. Back из dashboard/inspector SHALL возвращать к тому же Day 10 main, следующий Back — в каталог; клавиатура SHALL сохранять обычный приоритет закрытия. После process death SHALL восстанавливаться scoped run identities, durable progress/state и separate evaluation outputs без provider calls; потерянный runtime accounting SHALL не изображаться восстановленным полным. Day 02–09 navigation и session state SHALL оставаться независимыми.

#### Scenario: Dashboard back preserves the current experiment
- **WHEN** пользователь открывает dashboard, поворачивает устройство и возвращается назад
- **THEN** виден прежний Day 10 main с выбранной strategy, progress и outputs без повторной evaluation

#### Scenario: Day 10 reset does not reset earlier labs
- **WHEN** пользователь сбрасывает один Day 10 run и возвращается в Day 06–09
- **THEN** прежние IDs/drafts/results/operations этих уроков сохранены, а два остальных Day 10 runs не изменены
