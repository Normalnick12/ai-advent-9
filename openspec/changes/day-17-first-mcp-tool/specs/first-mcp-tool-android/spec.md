## Purpose

Дать пользователю отдельный Android lab Day 17 для отправки запроса агенту и просмотра ответа вместе с MCP evidence конкретной попытки без изменения Day 15 Playground.

## ADDED Requirements

### Requirement: Independent lab supports explicit forced and auto sends
Day 17 SHALL предоставлять поле запроса, режимы «Проверить вызов» / «Автовыбор», явную кнопку отправки, final model response и краткий outcome. По умолчанию SHALL быть выбран режим проверки вызова и заполнен запрос точной публичной dependency. Отправка SHALL инициироваться только явным действием пользователя; повторная отправка во время текущей операции SHALL блокироваться.

#### Scenario: User starts an attempt
- **WHEN** пользователь отправляет непустой запрос
- **THEN** запускается одна backend operation со снимком текста и режима, отображается loading и недоступна повторная отправка до завершения

### Requirement: Inspector exposes actual attempt evidence
Раскрываемый Inspector SHALL показывать MCP server, imported tools, каждый call с tool name, фактическими arguments, provider status при наличии, output/result/error, response id, call id и lookup id при наличии. Provider status и вычисленный outcome SHALL различаться. Большой raw JSON MUST NOT заменять краткий результат на основном экране.

#### Scenario: Inspect a successful call
- **WHEN** пользователь раскрывает Inspector завершённой попытки
- **THEN** он видит фактические координаты, structured tool result и идентификаторы для сопоставления с Responses и серверным логом

#### Scenario: No call or optional field
- **WHEN** результат имеет `not_called`, ошибку либо отсутствующий provider call status
- **THEN** UI явно показывает соответствующее состояние без выдуманного call, status, result или lookup id

### Requirement: New attempts cannot inherit old evidence
Экран SHALL связывать результат с неизменяемым снимком отправленного запроса и режима. При новой отправке previous success MUST NOT отображаться как evidence новой попытки; локальные/сетевые ошибки SHALL также заменять состояние текущей попытки. Редактирование черновика MUST NOT переименовывать уже полученный результат.

#### Scenario: Failure follows success
- **WHEN** после успешного lookup пользователь отправляет другой запрос, который завершается ошибкой
- **THEN** актуальная попытка показывает эту ошибку без старых response/call/lookup identifiers в качестве её evidence

### Requirement: Lifecycle changes never replay operations
Rotation, recomposition, navigation back и повторное открытие Day 17 MUST NOT автоматически отправлять запрос. В пределах живой session экран SHALL сохранять актуальные draft/mode/result/loading; восстановление после process death MUST NOT воспроизводить незавершённый запрос или фабриковать результат.

#### Scenario: Rotate or reopen
- **WHEN** пользователь поворачивает устройство либо возвращается в каталог и открывает Day 17 во время/после запроса
- **THEN** состояние существующей операции доступно без дополнительного backend request

#### Scenario: Restart after process death
- **WHEN** процесс приложения был уничтожен и затем открыт Day 17
- **THEN** никакая generation не запускается до новой явной отправки
