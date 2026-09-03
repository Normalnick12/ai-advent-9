## Purpose

Определяет полностью русскоязычный экран существующего Android-приложения для запуска Temperature Lab, сравнения трёх ответов и просмотра ограниченной session-only истории без смешивания разных prompt.

## ADDED Requirements

### Requirement: Temperature Lab is an additive Russian screen
Приложение SHALL предоставить отдельный экран «Лаборатория температуры» в существующем Android `app` module, сохранить доступ к экранам Day 02 и Day 03 и использовать русский язык для всех пользовательских подписей, состояний, ошибок и действий нового экрана.

#### Scenario: User opens Temperature Lab
- **WHEN** пользователь выбирает раздел Day 04 в навигации
- **THEN** отображается экран «Лаборатория температуры»
- **AND** пользователь может вернуться к существующим экранам Day 02 и Day 03

### Requirement: Prompt can be edited and restored
Экран SHALL показывать редактируемое многострочное поле prompt, изначально заполненное точным каноническим benchmark-текстом, кнопку «Запустить сравнение» и действие «Вернуть benchmark». Пустой prompt SHALL NOT запускать backend-запрос и SHALL сопровождаться русским сообщением валидации.

#### Scenario: Default benchmark is visible
- **WHEN** экран открыт впервые в session
- **THEN** поле содержит полный канонический benchmark prompt без изменений

#### Scenario: User restores benchmark
- **WHEN** пользователь изменил prompt и выбирает «Вернуть benchmark»
- **THEN** поле снова содержит точный канонический текст
- **AND** следующий запуск распознаётся backend как benchmark mode

#### Scenario: User launches one comparison
- **WHEN** непустой prompt находится в поле и пользователь нажимает «Запустить сравнение»
- **THEN** приложение отправляет ровно один batch request с этим prompt
- **AND** блокирует повторный запуск до terminal response

### Requirement: Fixed experiment parameters are inspectable but not editable
Экран SHALL содержать раскрываемую read-only секцию «Параметры эксперимента», показывающую три temperature, `gpt-5.6`, `reasoning.effort=none`, standard reasoning mode, `max_output_tokens=600`, default `top_p`, текущий output mode и то, что остальные strategy/reasoning/output settings зафиксированы. Экран SHALL NOT добавлять editable controls Day 02 или Day 03 в основной эксперимент.

#### Scenario: User expands experiment parameters
- **WHEN** пользователь раскрывает «Параметры эксперимента»
- **THEN** отображаются фактически возвращённые backend параметры и пояснение «Меняется только temperature»
- **AND** ни один параметр конфигурации нельзя изменить на этом экране

### Requirement: Three results are readable and expandable
После batch response экран SHALL показывать отдельный результат для temperature 0, 0.7 и 1.2 со status, token usage и отдельной latency; полный ответ каждой temperature SHALL раскрываться и скрываться. Для успешно проверенного benchmark-ответа карточка SHALL показывать точную подпись «Соблюдение требований: N/5», а для free mode SHALL явно сообщать «Автопроверка benchmark недоступна для произвольного запроса».

#### Scenario: Successful benchmark cards
- **WHEN** backend возвращает три успешно разобранных benchmark-результата
- **THEN** каждая карточка показывает temperature, status, «Соблюдение требований: N/5», tokens и latency
- **AND** пользователь может раскрыть все пары name/slogan соответствующей temperature

#### Scenario: Successful free-mode cards
- **WHEN** backend возвращает free-mode результаты
- **THEN** карточки показывают temperature, status, tokens, latency и раскрываемый обычный текст
- **AND** экран не показывает формальный score или секцию уникальности

#### Scenario: Partial failure stays local to one card
- **WHEN** одна temperature содержит ошибку, а другие содержат ответы
- **THEN** русское сообщение ошибки отображается в соответствующей карточке
- **AND** успешные карточки, их ответы и метрики остаются доступны

#### Scenario: Latency is not promoted as the conclusion
- **WHEN** экран показывает latency трёх результатов
- **THEN** она подписана как метрика конкретного запуска
- **AND** UI не объявляет самую быструю temperature лучшей или причинно более быстрой

### Requirement: History is session-only and scoped to the current prompt
ViewModel SHALL хранить только в памяти не более трёх последних полученных batch runs для одного точного prompt и показывать историю только когда текущий текст поля совпадает с prompt этой истории. При принятом результате запуска с другим prompt активная история SHALL быть заменена историей нового prompt; Room, DataStore, файлы и иное межсессионное хранение SHALL NOT использоваться.

#### Scenario: Fourth run evicts the oldest run
- **WHEN** для одного неизменённого prompt получен четвёртый batch response
- **THEN** история содержит три самых новых запуска этого prompt в порядке от нового к старому

#### Scenario: Editing prompt does not mix visible history
- **WHEN** текст поля отличается от prompt сохранённой активной истории
- **THEN** предыдущие runs не отображаются под новым текстом

#### Scenario: Running a different prompt starts a new history scope
- **WHEN** backend возвращает batch для prompt, отличного от prompt активной истории
- **THEN** активная история очищается и начинается с нового batch

#### Scenario: New application session starts without history
- **WHEN** процесс приложения создаёт новый ViewModel после завершения предыдущей session
- **THEN** история запусков пуста

### Requirement: Benchmark uniqueness accumulates per temperature
В benchmark mode экран SHALL показывать накопительную session-only секцию «Уникальные названия» отдельно для temperature 0, 0.7 и 1.2 в формате «точные нормализованные уникальные названия / всего сгенерировано». Нормализация SHALL совпадать с backend: trim, collapse whitespace и Unicode case-insensitive normalization. Агрегат SHALL учитывать все успешно разобранные benchmark-варианты текущей application session независимо от трёхэлементного лимита видимой run history и SHALL NOT включать free-mode ответы.

#### Scenario: Repeated normalized name changes only denominator
- **WHEN** новый benchmark run повторяет для одной temperature название с отличиями только в регистре или whitespace
- **THEN** total generated для этой temperature увеличивается
- **AND** normalized unique count для повторённого названия не увеличивается

#### Scenario: Aggregates are independent by temperature
- **WHEN** одно нормализованное название встречается при разных temperature
- **THEN** оно учитывается отдельно в агрегате каждой temperature

#### Scenario: Free mode disables uniqueness section
- **WHEN** текущий результат относится к изменённому prompt и free mode
- **THEN** секция «Уникальные названия» не отображается и её benchmark-агрегаты не изменяются

### Requirement: Android never handles the OpenAI credential
Temperature Lab Android client SHALL обращаться только к локальному FastAPI backend и SHALL не запрашивать, не хранить и не передавать OpenAI API key.

#### Scenario: App runs against emulator backend
- **WHEN** пользователь запускает Temperature Lab на Android Emulator
- **THEN** batch request направляется на существующий backend URL `http://10.0.2.2:8000/`
- **AND** в Android UI, DTO, repository и настройках отсутствует поле для `OPENAI_API_KEY`
