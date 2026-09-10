## MODIFIED Requirements

### Requirement: Catalog is the application entry screen

При обычном запуске без восстанавливаемого состояния приложение SHALL открывать каталог «AI Advent» с подсказкой «Выберите день обучения». Каталог SHALL показывать доступные Android-уроки в порядке номера: 02 «Управление ответом», 03 «Лаборатория рассуждений», 04 «Лаборатория температуры», 05 «Лаборатория моделей», 06 «Первый агент», 07 «Сохранение контекста», 08 «Работа с токенами», 09 «Управление контекстом: сжатие истории». Нижняя панель навигации SHALL отсутствовать во всём приложении. Day 01 и ещё не реализованные Android-дни SHALL NOT отображаться как доступные уроки. Наличие сохранённого Day 07, Day 08 или Day 09 ID SHALL NOT само по себе открывать урок или запускать turn; пользователь SHALL иметь доступ к отдельным карточкам Day 07/08/09 после cold start.

#### Scenario: Fresh launch shows available days
- **WHEN** пользователь запускает приложение без восстанавливаемого состояния
- **THEN** виден каталог с восемью карточками 02, 03, 04, 05, 06, 07, 08 и 09 в указанном порядке
- **AND** ни один эксперимент или turn не открывается и не запускается автоматически
- **AND** нижняя панель и карточка Day 01 отсутствуют

### Requirement: Each catalog card opens its matching lesson

Нажатие любой части карточки SHALL открывать соответствующий урок без запуска эксперимента или turn. Доступность каталога и переходов SHALL NOT зависеть от доступности backend. Read-only загрузка каталога моделей при открытии Day 05 SHALL NOT блокировать навигацию или вызывать OpenAI. Открытие Day 06 SHALL показывать текущий или пустой chat без создания session. Открытие Day 07 SHALL показывать отдельную лабораторию «Сохранение контекста», читать сохранённый ID при первом открытии в новом процессе и при его наличии восстанавливать metadata read-only запросом. Day 08 SHALL открывать отдельную лабораторию «Работа с токенами» и при сохранённом собственном ID восстанавливать metadata без count/generation. Без ID Day 06/07 SHALL создавать session только при первой явной отправке; Day 08 — при первой явной отправке либо явной подготовке overflow. Day 09 SHALL открывать main chat «Управление контекстом: сжатие истории» и при собственном сохранённом ID read-only восстанавливать identity/count/summary metadata без count/generation; без ID session SHALL создаваться только после явного Send, а compare SHALL требовать существующую session. Восстановление SHALL NOT блокировать возврат в каталог и SHALL NOT выполнять create или send.

#### Scenario: User selects each available day
- **WHEN** пользователь выбирает карточку дня 02, 03, 04, 05, 06, 07, 08 или 09
- **THEN** открывается соответственно управление ответом, лаборатория рассуждений, лаборатория температуры, лаборатория моделей, «Первый агент», «Сохранение контекста», «Работа с токенами» или «Управление контекстом: сжатие истории»
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

### Requirement: Back returns to the catalog
Главный экран каждого урока SHALL предоставлять верхнюю кнопку с доступной подписью «Назад к дням». Эта кнопка и системное действие назад SHALL возвращать в каталог; системное закрытие клавиатуры SHALL сохранять стандартный приоритет перед возвратом. На экране каталога системное действие назад SHALL передаваться стандартному поведению Android, без перехода в ранее открытый урок.

#### Scenario: Toolbar back returns to catalog
- **WHEN** пользователь нажимает верхнюю кнопку назад на главном экране любого урока
- **THEN** отображается каталог

#### Scenario: System back returns to catalog
- **WHEN** пользователь выполняет системное действие назад на главном экране урока при закрытой клавиатуре
- **THEN** отображается каталог

#### Scenario: System back on home does not reopen a lesson
- **WHEN** пользователь вернулся в каталог и выполняет системное действие назад
- **THEN** приложение следует стандартному поведению Android для корневого экрана
- **AND** ранее посещённый урок не открывается

Day 09 Details SHALL предоставлять верхнюю кнопку «Назад к чату». Она и system Back при закрытой клавиатуре SHALL возвращать в Day 09 Chat; следующий Back из Chat SHALL возвращать в каталог. Эти переходы SHALL NOT reset-ить session или повторять network operations.

#### Scenario: Compression details back returns to its chat
- **WHEN** пользователь выполняет toolbar либо system Back из Day 09 Details при закрытой клавиатуре
- **THEN** открывается тот же Day 09 Chat; следующий Back открывает каталог

### Requirement: Navigation preserves session state

В рамках текущей сессии переходы через каталог SHALL сохранять запросы, настройки, результаты, ошибки, session-only историю и текущие операции каждого урока независимо от других дней. Прокрутка каталога и уроков и раскрытые блоки для неизменившихся результатов SHALL сохраняться при уходе и возврате. Возврат SHALL NOT сбрасывать состояние или повторять запрос. Для Day 06 и Day 07 SHALL независимо сохраняться UI transcript, draft, backend session ID и состояние отправки/сброса/восстановления; переход назад SHALL NOT удалять backend session. Day 07 дополнительно SHALL восстанавливать свою сохранённую identity/count после cold start; это SHALL NOT вводить persistence результатов Day 02–05 или полного Android transcript. Backend sessions обоих чатов SHALL использовать общий durable lifecycle; локальный ID Day 06 не обязан переживать Android process restart.


Day 08 SHALL независимо сохранять draft, transcript, ID, diagnostics, runtime таблицу, незавершённую операцию и подготовку overflow при навигации и Activity recreation. Возврат SHALL NOT выполнять prepare/execute/send повторно. Cold start SHALL восстанавливать только отдельный Day 08 ID/count, без diagnostics/таблицы/preparation.

#### Scenario: User returns to an edited lesson
- **WHEN** пользователь меняет запрос или настройки, получает результат, прокручивает урок, раскрывает блок и посещает другой день через каталог
- **THEN** при возврате прежние данные, позиция прокрутки и раскрытый блок неизменившегося результата восстановлены
- **AND** состояние другого урока не подменяет сохранённое состояние

#### Scenario: Running experiment finishes while user is elsewhere
- **WHEN** пользователь покидает урок с выполняющимся запросом и возвращается в той же сессии
- **THEN** видит актуальное состояние того же запуска: выполнение либо полученный результат или ошибку
- **AND** навигация не отменяет и не дублирует запуск

#### Scenario: Catalog scroll survives a round trip
- **WHEN** пользователь прокручивает каталог, открывает карточку и возвращается
- **THEN** каталог показывает прежнюю позицию прокрутки

#### Scenario: Activity recreation preserves the current visit
- **WHEN** конфигурация устройства меняется с пересозданием Activity без завершения процесса
- **THEN** выбранный экран и данные текущей сессии остаются доступны
- **AND** запрос генерации или уже завершённое восстановление не запускаются повторно из-за пересоздания

#### Scenario: Chat and experiments retain independent state
- **WHEN** пользователь с текущим диалогом Day 06 или Day 07 посещает Day 02–05 и возвращается
- **THEN** chat transcript, draft и session ID сохранены без повторного POST или DELETE
- **AND** prompts, настройки, результаты и текущие операции лабораторий сохранены независимо от чата

#### Scenario: Agent lessons do not share the current conversation
- **WHEN** пользователь ведёт отдельные диалоги в Day 06 и Day 07 и переключается между карточками
- **THEN** каждый экран сохраняет собственные ID, transcript, draft и операцию
- **AND** reset Day 06 не удаляет session или сохранённый Android ID Day 07 и наоборот

#### Scenario: Returning to Day 07 does not repeat restoration
- **WHEN** metadata Day 07 уже восстановлена или восстановление выполняется, а пользователь уходит и возвращается в том же процессе
- **THEN** видит текущее состояние без второго GET, create или message request, вызванного только навигацией

#### Scenario: Token laboratory state is independent
- **WHEN** пользователь переключается между Day 06/07/08 или сбрасывает один из чатов
- **THEN** другие namespaces, ID, transcript и операции остаются прежними
- **AND** выполняющийся Day 08 request продолжает ту же попытку без cancellation/replay из-за навигации

Day 09 SHALL независимо сохранять в одном screen-level состоянии draft/transcript/session ID, operation, last context snapshot, compare question/results, observations/totals и раскрытые неизменившиеся блоки при Chat/Details/каталог переходах и Activity recreation. Chat/Details SHALL сохранять собственную прокрутку. Navigation SHALL NOT отменять или повторять операции. После process death SHALL восстанавливаться только отдельный ID и backend identity/count/summary metadata; bubbles и billing observations SHALL отсутствовать.

#### Scenario: Compression details survive a round trip and rotation
- **WHEN** пользователь открывает Details из Day 09 Chat, поворачивает устройство и возвращается
- **THEN** draft, scroll, results и totals сохранены, тот же запрос продолжается или показывает свой результат без второго send/compare

#### Scenario: Day 09 remains independent of older lessons
- **WHEN** пользователь меняет или сбрасывает Day 09 и возвращается в Day 06–08
- **THEN** старые ID, configurations, drafts и operations остаются прежними
