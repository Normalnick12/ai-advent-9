## Purpose

Выполнить изолированную агентную операцию Day 17 через native remote MCP и вернуть ответ модели вместе с фактическим evidence этой попытки для проверки всей цепочки.

## ADDED Requirements

### Requirement: Native remote MCP with a narrow tool policy
Backend SHALL отправлять один Responses API request на явную пользовательскую отправку, используя native MCP definition с `server_label`, конфигурируемым server-side `server_url`, `allowed_tools=["get_google_maven_versions"]` и `require_approval="never"`. Backend MUST NOT заменять native integration собственным function-calling bridge или выполнять автоматическую regeneration/repair/retry. Ключ OpenAI SHALL оставаться только на backend.

#### Scenario: Forced request
- **WHEN** отправлен запрос режима «Проверить вызов»
- **THEN** Responses request содержит `tool_choice={"type":"mcp","server_label":"android_dependencies","name":"get_google_maven_versions"}` и allowlist единственного tool
- **AND** arguments формирует модель, а не скрытая подстановка backend

#### Scenario: Auto request
- **WHEN** отправлен запрос режима «Автовыбор»
- **THEN** тот же MCP definition передаётся с `tool_choice="auto"`

### Requirement: Each attempt returns atomic evidence
Результат операции SHALL атомарно содержать final model text при наличии, response id при наличии, реальные imported MCP tools, все `mcp_list_tools` и все `mcp_call`, parsed evidence и outcome. Каждый call SHALL сохранять id, server label, name, исходные arguments, status при наличии, output и error. Отсутствующие provider fields SHALL оставаться отсутствующими/null, а не выдумываться. Evidence MUST NOT извлекаться из final prose или глобального mutable last response.

#### Scenario: Multiple calls are retained
- **WHEN** Responses возвращает discovery и несколько calls, включая ошибочный и успешный
- **THEN** операция сохраняет все эти items в порядке ответа и привязывает parsed result к соответствующему call
- **AND** успешный call не скрывает предшествующую ошибку

#### Scenario: Partial or failed response retains available evidence
- **WHEN** Responses возвращает incomplete/refusal/error вместе с MCP items
- **THEN** доступные items остаются в результате этой попытки независимо от наличия final text

#### Scenario: Output cannot be parsed
- **WHEN** call output не соответствует ожидаемому structured tool result
- **THEN** исходный output сохраняется, parsed evidence помечается как недоступный/невалидный и успешный lookup не утверждается

### Requirement: Outcomes distinguish invocation from model behavior
Операция SHALL различать MCP transport/discovery/protocol failure, tool execution failure, negative Google Maven lookup и отсутствие/непригодность model response. Наличие `mcp_call` SHALL означать наблюдаемый вызов, но само по себе не успешный lookup. Приложение MUST NOT обещать самостоятельный выбор tool, правильные координаты или корректность произвольного final prose.

#### Scenario: Completed auto response without a call
- **WHEN** завершённый auto response не содержит `mcp_call` и не сообщает discovery/protocol failure
- **THEN** outcome равен `not_called` как наблюдение model selection, даже если final text выглядит правдоподобно

#### Scenario: Forced response without a call
- **WHEN** forced response не содержит `mcp_call`
- **THEN** forced acceptance не пройден, отсутствие вызова явно показано и повторная generation не запускается

#### Scenario: No response was received
- **WHEN** backend получает timeout/network error до получения Responses result
- **THEN** операция сообщает ошибку provider и неизвестность факта remote invocation, а не утверждает `not_called`

#### Scenario: Negative lookup is a normal tool result
- **WHEN** call возвращает `group_not_found`, `artifact_not_found` или `no_versions`
- **THEN** операция показывает этот lookup outcome отдельно от transport и execution errors

### Requirement: Day 17 is isolated from established day contracts
Day 17 SHALL возвращать final text и MCP evidence единым результатом, сохраняя прежние контракты и поведение Days 6–15. Отсутствующая Day 17 remote configuration MUST NOT препятствовать запуску и использованию других Days. Таймауты предыдущих Days MUST NOT увеличиваться для обхода cold start.

#### Scenario: Missing Day 17 endpoint
- **WHEN** backend запущен без URL Day 17 MCP server
- **THEN** прежние Days остаются доступны, а явная Day 17 отправка получает понятную configuration error без OpenAI request

### Requirement: Forced live acceptance uses a correlated evidence chain
Основной live SHALL использовать заранее заданный запрос для `androidx.core:core-ktx`. Успех SHALL подтверждаться remote discovery/schema, отправкой из Android, реальным `mcp_call` с нужным name и фактическими корректными arguments, сопоставимым structured result/output, логом Google Maven lookup по `lookup_id` и final response, использующим данные этого результата. Final prose отдельно SHALL NOT считаться доказательством вызова. Попытка SHALL завершаться без автоматического retry/regeneration/repair.

#### Scenario: Full chain is observed
- **WHEN** forced live выполнен после отдельной проверки готовности deployment
- **THEN** зафиксированы подтверждённый commit SHA фактически deployed MCP server, deployment reference/endpoint, response id, call id, actual arguments, lookup id, соответствующий серверный лог и проверка фактов final response по tool result
- **AND** наличие одного зарегистрированного tool не трактуется как гарантия ровно одного provider call

#### Scenario: Model prose mismatch remains a failed acceptance result
- **WHEN** полная MCP evidence-цепочка подтверждена, но количество или последние элементы в final response не соответствуют tool result
- **THEN** эксперимент SHALL сохранить подтверждение MCP mechanism и failed verdict точности final response раздельно, без retry/regeneration/repair
- **AND** проверка эксперимента SHALL считаться выполненной после фиксации расхождения и полного evidence; завершение и архивирование дня MUST NOT обозначать полный forced acceptance как passed

#### Scenario: Optional auto observation
- **WHEN** отдельно выполнен auto experiment с запросом актуальных данных Google Maven
- **THEN** фиксируется фактический выбор модели, включая `not_called`, с deployed commit SHA этой попытки и без повторов ради получения желаемого ответа

### Requirement: Deployment revision is traceable without premature day completion
Day 17 SHALL публиковать проверенную deployable revision отдельным pre-live commit/push после реализации, всех offline checks, scoped diff review и strict OpenSpec validation, до Git-backed Render deployment. Pre-live publication MUST NOT означать завершение дня, архивирование change или выполнение live/video tasks. Live evidence SHALL сохранять полный commit SHA фактически deployed MCP server, подтверждённый deployment, и связь с конкретной попыткой. Финальное завершение SHALL происходить через отдельный `$finish-day Day 17` после live и подтверждённого видео; оно актуализирует evidence/docs, архивирует завершённый change и создаёт final commit/push при наличии последующих изменений.

#### Scenario: Published revision is ready for deployment only
- **WHEN** pre-live commit/push выполнен после успешных offline checks и review/validation
- **THEN** Render может получить deployable code, но live/video tasks остаются невыполненными и OpenSpec change активен

#### Scenario: Live evidence identifies the running server revision
- **WHEN** выполняется forced live или optional auto experiment
- **THEN** evidence содержит SHA подтверждённого Render deployment, а не неподтверждённый локальный HEAD
- **AND** последующие docs/archive commits не заменяют SHA уже выполненной попытки

#### Scenario: Finalization follows live and video
- **WHEN** пользователь вызывает `$finish-day Day 17` после обязательной проверки live, фиксации фактического verdict при подтверждённой MCP evidence-цепочке и подтверждённого видео
- **THEN** evidence/docs и task statuses сверяются с фактами, завершённый change проходит strict validation и архивируется, а последующие scoped changes входят в final commit/push без пустого commit
