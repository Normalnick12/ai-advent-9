# model-benchmark-android Specification

## Purpose

Определяет русскоязычный мобильный экран Day 05 для выбора трёх моделей, запуска общего benchmark и сравнения проверенного качества, времени, токенов и стоимости.

## Requirements

### Requirement: Lab exposes backend-controlled model choices
Экран SHALL называться «Лаборатория моделей» и показывать роли «Экономичная», «Сбалансированная», «Флагманская» с defaults GPT-5.6 Luna/Terra/Sol из backend catalog. Каждая роль SHALL предоставлять выбор только из переданного backend allowlist без произвольного ввода id. Выбранный model id SHALL быть видимым; роль не является автоматически присваиваемым рейтингом. Повторный выбор одной модели для нескольких ролей SHALL допускаться с понятным указанием, что сравниваются отдельные вызовы одной модели. До загрузки каталога запуск SHALL быть недоступен. Ошибка каталога SHALL иметь явное действие повторной загрузки без OpenAI-вызова и без локально захардкоженного fallback allowlist.

#### Scenario: Defaults load
- **WHEN** пользователь впервые открывает Day 05 и каталог успешно загружен
- **THEN** видит три роли с defaults, доступные selectors и кнопку «Запустить сравнение»
- **AND** автоматический benchmark не запускается

#### Scenario: Catalog cannot be loaded
- **WHEN** backend недоступен при загрузке каталога
- **THEN** экран показывает русскую ошибку и повторную загрузку каталога, а запуск сравнения недоступен

### Requirement: One action launches one immutable comparison
Нажатие «Запустить сравнение» SHALL отправлять один backend batch request с текущими тремя selections. На время запуска кнопка и selectors SHALL быть заблокированы, повторные taps SHALL игнорироваться. Автозапуск при recomposition, navigation, rotation, ошибке или изменении selection SHALL отсутствовать. Изменение selection после результата SHALL NOT переименовывать старые карточки: каждый batch отображает свой снимок модели/параметров. После transport error экран SHALL показывать, что результат неизвестен и сервер мог обработать запрос; новый явный запуск является новым потенциально оплачиваемым сравнением.

#### Scenario: Double tap while loading
- **WHEN** пользователь дважды нажал кнопку во время одного запуска
- **THEN** отправлен ровно один backend request и отображается состояние «Сравнение выполняется»

#### Scenario: Selection changes after completion
- **WHEN** пользователь меняет модель роли после получения результата
- **THEN** старый результат сохраняет свой requested/resolved id до следующего успешного получения batch
- **AND** новое сравнение требует явного нажатия кнопки

### Requirement: Read-only parameters explain experiment fairness
Экран SHALL иметь общий раскрываемый read-only блок «Параметры эксперимента» со снимком prompt, instructions, benchmark version, Responses API, medium reasoning, 6000 output tokens, strict output, omitted temperature/top_p и отсутствием retries. Пользователь SHALL видеть пояснение «Меняется только модель; запрос и параметры одинаковы для всех трёх вызовов». При показе результата SHALL использоваться применённая конфигурация этого batch. Редактирование prompt и playground SHALL отсутствовать в Day 05.

#### Scenario: User inspects settings
- **WHEN** пользователь раскрывает параметры
- **THEN** может прочитать условия всех пяти задач и общие настройки, а не только название benchmark
- **AND** не может изменить параметры отдельной модели

### Requirement: Mobile dashboard distinguishes quality and completion
Экран SHALL показывать три компактные вертикальные карточки/строки со snapshot model name, «Качество», «Время», «Токены», «Стоимость» и статусом завершения. Проверенный результат SHALL показывать N/5; quality null SHALL показывать «Нет проверяемого результата». Неизвестные usage/cost SHALL отображаться «Нет данных», а не нулями. Cost SHALL показываться в USD с точностью, позволяющей различить малые расходы, и как оценка по тарифам. Доступные результаты SHALL сохраняться при ошибке другого слота. Автоматический победитель и рейтинги на основании одного запуска SHALL отсутствовать.

#### Scenario: Real quality difference
- **WHEN** batch содержит Luna 4/5 и Terra/Sol 5/5 с completed status
- **THEN** карточки показывают эти оценки и метрики текущего batch без обещания устойчивого рейтинга

#### Scenario: Incomplete and incorrect are different
- **WHEN** один слот incomplete без полного результата, второй completed с пятью ошибками, третий completed с пятью правильными ответами
- **THEN** показаны соответственно «Нет проверяемого результата», 0/5 и 5/5
- **AND** стоимость incomplete отображается, если backend смог её вычислить

### Requirement: Expandable details expose evidence and accounting
Каждая карточка SHALL раскрывать Task 1–5 с русскими verdict «Верно», «Неверно», «Не проверено», фактическим ответом и эталоном для incorrect задачи. Детали SHALL показывать input/cached input/cache write/output/reasoning/total tokens, отдельную latency, requested/resolved model, нормализованный и исходный status, reason/error, API call count, rates/source/date и формулу backend cost. Reasoning SHALL обозначаться как часть output без раскрытия скрытой цепочки рассуждений. Raw output при непроверяемом результате SHALL быть доступен при наличии. Технические ids/JSON/ответы SHALL отображаться без перевода исходных данных.

#### Scenario: User inspects a wrong Task 5
- **WHEN** пользователь раскрывает incorrect Task 5 с actual count 21
- **THEN** видит «Неверно», actual 21 и verifier 24

#### Scenario: Output is unavailable
- **WHEN** пользователь раскрывает слот timeout без output/usage
- **THEN** видит «Не проверено», причину, API calls и «Нет данных» для отсутствующих полей
- **AND** приложение не придумывает ответ, эталонную оценку или бесплатный запрос

### Requirement: New lesson follows existing session and accessibility behavior
Day 05 SHALL сохранять selection, последний batch, ошибку и выполняющийся запрос в текущей сессии при переходах через каталог и пересоздании Activity без завершения процесса. Прокрутка и раскрытые блоки неизменившегося результата SHALL восстанавливаться. Состояния других дней SHALL оставаться независимыми. Узкий экран и увеличенный системный шрифт SHALL сохранять читаемость через перенос строк и вертикальную прокрутку без обязательной горизонтальной таблицы. Кнопки и selectors SHALL иметь доступные русские подписи, а содержимое SHALL не перекрываться системными панелями.

#### Scenario: Running comparison survives navigation
- **WHEN** пользователь уходит из Day 05 в каталог и возвращается до или после завершения запроса
- **THEN** видит состояние того же запуска, без отмены или повторной отправки

#### Scenario: Large font and expanded answer
- **WHEN** пользователь увеличивает системный шрифт на узком телефоне и раскрывает ответ и usage
- **THEN** все значения доступны прокруткой и переносом, действия доступны, а текст не обрезан
