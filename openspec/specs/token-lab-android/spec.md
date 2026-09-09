# token-lab-android Specification

## Purpose

Определяет отдельный Android экран Day 08 «Работа с токенами», который показывает backend diagnostics полной истории и реальное переполнение фиксированной модели, сохраняя независимость прежних лабораторий.

## Requirements

### Requirement: Token laboratory has independent conversation state

Day 08 SHALL иметь собственные session ID, draft, transcript, операции, diagnostics, таблицу наблюдений и overflow preparation state. Эти значения SHALL NOT разделяться с Day 06/07. Android SHALL хранить только отдельный nullable Day 08 session ID для cold start; история LLM, diagnostics, preparations и monetary metrics SHALL NOT persist'иться. При восстановлении SHALL сначала проверяться identity/count metadata backend; старые bubbles SHALL NOT воссоздаваться. Create SHALL выполняться только при первой явной отправке или явной подготовке overflow без ID. New conversation SHALL удалить только Day 08 session и после подтверждения очистить ID/runtime state, без автоматического create/replay.

#### Scenario: Cold start with a stored identity
- **WHEN** Day 08 впервые открыт в новом процессе с сохранённым ID
- **THEN** выполняется read-only restore metadata, показывается подтверждённый count без прежнего transcript и таблицы
- **AND** до завершения restore send/overflow недоступны, generation/count requests автоматически не выполняются

#### Scenario: Reset stays within Day 08
- **WHEN** пользователь выполняет «Новый диалог» Day 08
- **THEN** удаляется только его Day 08 session и очищается собственный ID после server success
- **AND** состояние Day 06/07 не меняется, новая session пока не создаётся

### Requirement: Normal Send shows diagnostics without mandatory preview

Обычный composer SHALL принимать message до 20000 символов и предоставлять явный Send без отдельной обязательной preview кнопки. Пока backend считает токены или генерирует, UI SHALL показывать занятость одной попытки и не разрешать повторную отправку/reset/overflow. Completed turn SHALL добавлять ровно две текущие bubbles и принимать count backend; non-completed SHALL сохранять draft и прежний transcript/count, показывая error/diagnostics отдельно от assistant message. Backend SHALL быть единственным источником context counts и pricing. UI SHALL NOT отправлять history/config или считать LLM history по bubbles.

#### Scenario: First message can be sent immediately
- **WHEN** пользователь набрал короткий текст и нажал «Отправить»
- **THEN** начинается одна операция с preflight/generation на backend без обязательного Preview шага
- **AND** после ответа текущие diagnostics принадлежат именно этой попытке

#### Scenario: Explicit provider failure preserves the draft
- **WHEN** backend вернул non-completed с неизменным history count
- **THEN** draft доступен для изменения и следующей явной отправки, отсутствует фиктивная assistant bubble

### Requirement: Diagnostics distinguish standalone counts full preflight usage and cost

Экран SHALL показывать «Новое сообщение», «Сохранённая история», «Preflight input модели», «Actual API input», «Actual output», «Контекст: preflight input / 128000» и «Оценочная стоимость хода» понятными русскими подписями. Current/history SHALL иметь пояснение «Отдельный provider count, включая оформление сообщений». UI SHALL явно пояснять, что current/history/full не складываются: первые два измерены отдельно, full включает инструкции и оформление всего запроса. Карточка системной части и вычисление этой части разностью SHALL отсутствовать. Preflight SHALL обозначаться provider count до generation, actual — usage после generation; неизвестные значения SHALL отображаться «нет данных», а не 0. Контекстная шкала SHALL использовать только full preflight как источник числителя, не скрывать численное превышение 100% и не складывать reasoning повторно. Reserved output 1200 SHALL показываться отдельно от фактических tokens, если включён в шкалу. Карточка попытки SHALL сохранять history до отправки даже после commit; редактирование draft SHALL NOT подменять её метрики. Secondary details SHALL содержать model и pricing date/source; доступные cache/reasoning counters SHALL не перегружать основной блок.

#### Scenario: Preflight and actual differ
- **WHEN** backend возвращает разные preflight input и actual input
- **THEN** UI показывает оба значения с их источниками без выравнивания или пересчёта

#### Scenario: Overflow diagnostics remain available
- **WHEN** generation отклонена без usage
- **THEN** full preflight и limit остаются видимыми, standalone current/history показывают «не измерялось», если не считались; известная пустая history показывает structural 0
- **AND** actual input/output/cost показывают «нет данных»

#### Scenario: Standalone measurements are not additive
- **WHEN** backend fixture возвращает current=12, history=31, full=40
- **THEN** UI показывает все три исходных значения с пояснением неаддитивности, не рисует составную сумму и не вычисляет системную часть

#### Scenario: Empty history is different from unavailable count
- **WHEN** backend сообщает saved_history_tokens=0 с source empty_history
- **THEN** UI объясняет отсутствие сохранённых сообщений, не утверждая успешный provider count пустого запроса
- **AND** missing count при ошибке остаётся «нет данных», а not_measured в overflow — «не измерялось»

### Requirement: Runtime observations do not claim durable billing history

Экран SHALL показывать runtime-only таблицу последних 20 наблюдаемых попыток с номером, actual input, output, estimated cost и различимым outcome. Номера попыток SHALL отличаться от числа committed turns. Count-only подготовка SHALL NOT добавлять generation usage. Недостоверный транспортный исход SHALL обозначаться unknown без автоматического replay. При отображении необязательных сумм UI SHALL указывать интервал наблюдений и пропуски; неизвестный расход SHALL NOT считаться нулевым. Навигация/Activity recreation SHALL сохранять runtime таблицу; process restart/reset SHALL очищать её. Повторный render одного attempt ID SHALL NOT добавлять строку.

#### Scenario: Failed attempt does not advance conversation count
- **WHEN** после четырёх committed turns наблюдается overflow attempt
- **THEN** таблица получает отдельную попытку с её outcome, а «Завершённых ходов» остаётся 4

#### Scenario: Older measurements are absent after cold start
- **WHEN** восстановлен Day 08 ID с history count больше нуля
- **THEN** таблица пуста и UI поясняет, что измерения относятся только к текущему запуску
- **AND** стоимость сохранённого диалога не восстанавливается из messages

### Requirement: Overflow requires visible preparation and a separate explicit action

Day 08 SHALL предоставлять отдельное действие «Подготовить переполнение». При успешной подготовке UI SHALL показать `gpt-4o-mini`, limit 128000, измеренный full input, размеры текста/full payload, повторяемый блок и число повторов, описание «один новый сгенерированный тестовый user message поверх сохранённой истории» и предупреждение о реальном provider request. Кнопка «Выполнить один overflow-запрос» SHALL быть отдельной, доступной только при валидной подтверждённой подготовке. Подготовка SHALL NOT отправляться автоматически. Cancel SHALL только сбрасывать подготовку без удаления history; normal completed turn/reset SHALL делать её stale. Большой текст SHALL NOT вставляться в обычный composer или выдаваться за старый диалог. Preview SHALL не возвращать внутреннюю saved history; отображение образца SHALL не изменять backend payload.

#### Scenario: Preparation is not authorization
- **WHEN** пользователь нажал подготовку и читает полученные размер/предупреждение
- **THEN** generation ещё не выполнена и без отдельного нажатия не начнётся

#### Scenario: A single explicit execution
- **WHEN** пользователь нажал выполнение актуальной подготовки
- **THEN** UI отправляет один execute с preparation ID и confirm=true, блокирует повторное действие и показывает результат этой попытки
- **AND** повторная навигация, render или ошибка не запускают execute автоматически

#### Scenario: Unprepared or expired overflow cannot run
- **WHEN** подсчёт не подтвердил превышение либо preparation устарела/исчезла после backend restart
- **THEN** UI объясняет причину, не отправляет generation и предлагает новую явную подготовку

### Requirement: Error presentation preserves experiment evidence and recovery

UI SHALL различать preflight error, подтверждённый provider `context_limit_exceeded`, rate-limit/body-size/other upstream error и неизвестный transport outcome. Только provider context rejection SHALL называться подтверждённым переполнением модели. Подтверждённый overflow SHALL оставлять прежнюю session доступной для нормального short turn без reset. Unknown normal-send outcome SHALL сохранять прежнее требование явного reset без replay, поскольку commit мог состояться. Unknown overflow-execute outcome SHALL не разрешать повтор того же preparation ID и SHALL NOT утверждать отсутствие расхода; после read-only проверки availability/count нормальный turn допустим, так как probe не имеет права commit. Restore errors SHALL иметь явный retry без автоматического создания заменяющей session.

#### Scenario: Context rejection permits continued conversation
- **WHEN** backend подтвердил context error и прежний count
- **THEN** UI показывает diagnostics/ошибку и позволяет следующее короткое сообщение в той же session

#### Scenario: A different provider error is honest
- **WHEN** provider вернул 429, 413 либо обычный 400
- **THEN** UI показывает соответствующий тип ошибки и не отмечает overflow эксперимент успешным

### Requirement: Short and long stages remain visible and accessible

Экран и краткий сценарий SHALL позволять явно отправить короткий факт, короткий вопрос, подготовленный длинный текст и следующий короткий вопрос. Подготовленный long текст SHALL загружаться в видимый редактируемый composer только по действию пользователя, укладываться в обычный лимит и не отправляться сам. Значения метрик SHALL быть измеренными; подсказки SHALL NOT содержать выдуманные ответы или ожидаемые token counts. Diagnostics, таблица и overflow actions SHALL оставаться читаемыми и доступными прокруткой на узком телефоне, с IME и увеличенным шрифтом; общий chat UI Day 06/07 SHALL сохранять поведение.

#### Scenario: Long fixture is an explicit message
- **WHEN** пользователь выбирает подготовленный длинный текст
- **THEN** видит его в composer и может изменить до Send, а backend получает ровно отправленный текст
- **AND** следующий короткий turn показывает standalone count накопленной backend history и отдельный full preflight
