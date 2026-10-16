## Purpose

Предоставлять текущую Git-ветку локального проекта через настоящий MCP-протокол, чтобы CLI мог доказуемо использовать результат инструмента и отличать его от сведений документации и предположений модели.

## ADDED Requirements

### Requirement: Local discoverable read-only tool
Локальный MCP-сервер SHALL работать через stdio в отдельном процессе и публиковать read-only инструмент `get_current_branch` с input/output schema. Корень репозитория SHALL задаваться при запуске сервера доверенным локальным кодом. Инструмент SHALL не принимать произвольные пути, команды или аргументы Git от модели/вопроса; его arguments SHALL быть пустым объектом.

#### Scenario: Discovery
- **WHEN** клиент запускает сервер и устанавливает MCP-сессию
- **THEN** завершается согласование протокола и discovery возвращает `get_current_branch` с описанием и схемами
- **AND** discovery сам по себе не считается выполнением Git-инструмента

#### Scenario: Invalid arguments
- **WHEN** инструменту переданы неожиданные аргументы
- **THEN** вызов отклоняется без выполнения переданной команды или чтения другого репозитория

### Requirement: Structured current Git state
Успешный вызов SHALL возвращать `status` (`branch` или `detached`), `branch` (строка либо null), `call_id` и `server_pid`. В состоянии `branch` SHALL возвращаться точное имя текущей ветки, включая unborn branch; в `detached` поле `branch` SHALL быть null. Результат SHALL вычисляться при каждом вызове, а не браться из README, старого индекса, окружения или предыдущего ответа. Сервер SHALL выполнять только read-only Git-операции с ограниченным временем выполнения.

#### Scenario: Branch and branch switch
- **WHEN** инструмент вызван в обычном репозитории, затем ветка изменена и инструмент вызван снова
- **THEN** каждый результат соответствует ветке на момент своего вызова
- **AND** каждый вызов имеет собственный `call_id`

#### Scenario: Unborn and detached states
- **WHEN** репозиторий имеет именованную ветку без первого commit
- **THEN** инструмент возвращает `status=branch` и её имя
- **WHEN** HEAD отсоединён от ветки
- **THEN** инструмент возвращает `status=detached`, `branch=null`, а CLI явно обозначает detached HEAD

#### Scenario: Git unavailable or invalid repository
- **WHEN** Git недоступен, путь не является репозиторием или Git не завершился в установленный срок
- **THEN** возвращается явная ошибка инструмента, а не пустая ветка или успешный detached result
- **AND** сервер не изменяет репозиторий

### Requirement: Client uses the actual MCP boundary
CLI SHALL выполнить MCP discovery и `call_tool("get_current_branch", {})`, проверить transport/tool errors и structured result. CLI MUST NOT запускать Git напрямую, читать `.git/HEAD` или использовать fallback вне MCP. При сбое запуска, discovery, вызова или валидации MCP-результата `/help` SHALL завершаться с явной ошибкой до OpenAI-запросов.

#### Scenario: Successful protocol call
- **WHEN** `/help` получает успешный ответ инструмента
- **THEN** отображаемая ветка берётся из проверенного structured result MCP
- **AND** факт вызова доступен в trace независимо от текста LLM

#### Scenario: Unavailable or malformed MCP
- **WHEN** сервер не запускается, соединение обрывается, инструмент отсутствует, возвращается `is_error` или результат нарушает контракт
- **THEN** CLI сообщает ошибку MCP и не получает ветку другим способом
- **AND** query embedding и generation не выполняются

### Requirement: Correlated execution evidence and lifecycle
Сервер SHALL формировать безопасное событие фактического выполнения инструмента на stderr, связанное с результатом через `call_id` и `server_pid`. Stdout SHALL содержать только MCP-протокол. Клиент SHALL корректно закрывать сессию и принадлежащий ему серверный процесс при завершении, ошибке и отмене. Диагностика MUST NOT включать секреты, полное окружение или необработанный вывод ошибок Git.

#### Scenario: Reproducible integration evidence
- **WHEN** integration test запускает настоящий сервер через stdio для временного Git-репозитория
- **THEN** discovery и вызов проходят через MCP, серверный PID отличается от клиентского, ответ совпадает с ожидаемой веткой
- **AND** событие выполнения имеет тот же `call_id` и PID, что structured result
- **AND** после закрытия сессии серверный процесс завершается

#### Scenario: Failure and cancellation cleanup
- **WHEN** клиент получает ошибку или пользователь отменяет команду
- **THEN** принадлежащая клиенту MCP-сессия и её процесс закрываются без завершения посторонних процессов
