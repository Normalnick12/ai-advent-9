# android-dependency-mcp Specification

## Purpose

Предоставить опубликованные версии точной Android/JVM dependency из Google Maven через собственный read-only MCP tool с проверяемым результатом и явной семантикой ошибок.

## Requirements

### Requirement: One discoverable read-only dependency tool
Сервер SHALL публиковать ровно один tool `get_google_maven_versions` с понятным описанием и input schema, содержащей обязательные строковые `group_id` и `artifact_id` с описаниями и ограничениями. Discovery SHALL быть доступен через публичный HTTPS Streamable HTTP endpoint `/mcp`.

#### Scenario: Remote discovery
- **WHEN** MCP client выполняет discovery на работающем remote endpoint
- **THEN** `tools/list` содержит ровно `get_google_maven_versions`, его description и schema обоих параметров

### Requirement: Validate coordinates before upstream access
Tool MUST отклонять пустые значения, whitespace, `/`, `\`, URL/query/fragment, percent-encoded path tricks и пустые сегменты `group_id`. Невалидные координаты SHALL приводить к ошибке вызова без HTTP обращения. Вход MUST NOT управлять origin или произвольным path запроса.

#### Scenario: Invalid coordinates cannot cause a fetch
- **WHEN** любой параметр содержит запрещённое значение, включая `androidx..core`, `../core`, `%2f`, пробел или URL
- **THEN** вызов отклоняется и число HTTP обращений к upstream равно нулю

### Requirement: Exact lookup uses only the official group index
Для валидных координат tool SHALL обращаться к официальному Google Maven group index, сформированному из точного `group_id`, и искать точный `artifact_id`. Tool MUST NOT обращаться к master index или другим repositories, сортировать версии, определять latest/stable, рекомендовать обновление или утверждать compatibility/security.

#### Scenario: Source order is preserved
- **WHEN** запрошен `androidx.core:core-ktx` и group index содержит этот artifact с непустым списком
- **THEN** возвращаются все версии именно этого artifact в порядке источника без интерпретации суффиксов версий
- **AND** lookup использует только `https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml`

### Requirement: Normal results preserve distinct lookup outcomes
Нормальный structured result SHALL содержать `status`, исходные проверенные `group_id`, `artifact_id`, `versions`, `source_url`, UTC `checked_at` и уникальный `lookup_id`. `status` SHALL принимать `found`, `group_not_found`, `artifact_not_found` или `no_versions`. Только `found` SHALL иметь непустые `versions`; остальные нормальные статусы SHALL иметь пустой список и явную причину через status.

#### Scenario: Group index is absent
- **WHEN** официальный group index возвращает HTTP 404
- **THEN** результат имеет `group_not_found`, что означает отсутствие индекса только в Google Maven

#### Scenario: Artifact is absent
- **WHEN** валидный group index не содержит запрошенный artifact
- **THEN** результат имеет `artifact_not_found`

#### Scenario: Artifact has an explicitly empty versions attribute
- **WHEN** найденный artifact содержит пустой атрибут `versions`
- **THEN** результат имеет `no_versions`

### Requirement: Upstream failures remain tool execution errors
Timeout/network, HTTP failure кроме обработанного 404 и malformed/unexpected XML SHALL различаться как диагностируемые tool execution errors. Они MUST NOT становиться normal result с `versions=[]` или обозначаться как MCP protocol failure. Tool errors MUST NOT раскрывать stack trace клиенту.

#### Scenario: Upstream failure
- **WHEN** upstream не отвечает, соединение не устанавливается либо возвращает HTTP 429/5xx
- **THEN** MCP возвращает ошибку выполнения tool с соответствующей категорией вместо negative lookup

#### Scenario: Invalid index structure
- **WHEN** ответ содержит malformed XML, неверный root, отсутствующий у найденного artifact атрибут `versions` или неоднозначный artifact
- **THEN** MCP возвращает ошибку выполнения tool категории XML response

### Requirement: Lookup evidence refers to actual upstream work
Каждый normal result SHALL содержать `lookup_id`, сопоставимый со структурированным серверным логом фактической попытки обращения к Google Maven. Лог SHALL содержать координаты, source URL, время, HTTP status при наличии и outcome; ошибки upstream SHALL также логироваться с корреляцией. Сервер MUST NOT требовать БД, tracing platform или секретов Google Maven.

#### Scenario: Result can be correlated
- **WHEN** tool завершил lookup
- **THEN** по `lookup_id` результата находится лог соответствующего upstream обращения с теми же координатами, URL и outcome

### Requirement: Remote service uses explicit transport protection
Remote deployment SHALL поддерживать конечные read-only вызовы без зависимости от сохранённой HTTP session. Защита transport SHALL разрешать настроенный public host и отклонять неподходящий Host; защита MUST NOT отключаться целиком ради deployment. `OPENAI_API_KEY` MUST NOT требоваться на MCP server.

#### Scenario: Public host configuration
- **WHEN** клиент обращается к настроенному `/mcp` с разрешённым host
- **THEN** discovery и вызов доступны через HTTPS
- **AND** запрос с посторонним Host не принимается как допустимый transport request
