# Spec Delta

## Purpose

Предоставить durable наблюдение за версиями Google Maven, которое регистрируется через MCP, самостоятельно выполняется на VPS и возвращает программно вычисленную сводку сохранённых проверок.

## ADDED Requirements

### Requirement: Two tools require Bearer authorization
Day 18 service SHALL публиковать ровно `create_dependency_watch` и `get_dependency_watch_summary` через HTTPS `/mcp`. Доступ к discovery и вызовам SHALL требовать валидную Bearer authorization; неавторизованный запрос MUST NOT читать watches, создавать их или обращаться к Google Maven. Create SHALL обозначаться как state-changing и неидемпотентный; summary SHALL быть read-only. Service MUST NOT требовать OpenAI API key.

#### Scenario: Authenticated discovery
- **WHEN** клиент с валидной Bearer authorization выполняет discovery
- **THEN** доступны ровно два tools с typed input/output schemas и соответствующими annotations

#### Scenario: Missing or invalid credential
- **WHEN** запрос к `/mcp` не содержит валидного Bearer token
- **THEN** доступ отклонён до MCP dispatch без изменения данных и upstream lookup

### Requirement: Create registers a finite watch before acknowledging it
Create SHALL принимать точные `group_id`, `artifact_id`, целый `interval_seconds` и обязательный целый `max_runs`. Интервал по умолчанию SHALL быть 21600 секунд; обычный диапазон SHALL быть 3600–86400 секунд, `max_runs` — 1–100. Явно включённая серверная acceptance configuration SHALL разрешать интервалы 30–3599 секунд только с `max_runs<=3` и максимум одним активным ускоренным watch. Общее число active watches SHALL быть ограничено пятью. Неверные типы, включая boolean вместо integer, координаты и превышение лимитов SHALL отклоняться до записи/lookup. Create SHALL возвращать UUID `watch_id`, фактические параметры, UTC `created_at`, `next_run_at`, `status=active` и нулевой run count только после durable commit. Первый слот SHALL быть `created_at + interval`; create MUST NOT сам выполнять lookup.

#### Scenario: Register without executing
- **WHEN** принят валидный create с `max_runs=3`
- **THEN** watch сохранён, ответ содержит первый будущий слот, а executions и upstream calls пока отсутствуют

#### Scenario: Invalid or unbounded schedule
- **WHEN** max_runs отсутствует, равен нулю, превышает предел либо interval запрещён текущей конфигурацией
- **THEN** create отклонён без сохранения watch и без обращения к Google Maven

#### Scenario: Capacity or accelerated limit is reached
- **WHEN** создание превысит общий лимит active watches либо лимит ускоренных watches
- **THEN** возвращается явная capacity error без неявного удаления или замены существующего watch

### Requirement: Create does not promise deduplication
Service MUST NOT обещать idempotent create и MUST NOT требовать idempotency key или custom MCP HTTP header. Каждый отдельно принятый create SHALL создавать отдельный watch, даже при одинаковых координатах и расписании, в пределах лимитов. Уникальность execution slots MUST NOT описываться как защита от дублирующих watches.

#### Scenario: Two accepted identical creates
- **WHEN** service принимает два одинаковых create calls и хватает capacity
- **THEN** возвращаются разные watch IDs и оба задания существуют независимо

### Requirement: Scheduled execution outlives the originating request
Зарегистрированные watches SHALL выполняться на VPS независимо от исходного Responses request, Android и локального backend. Schedule SHALL использовать UTC timestamps и сетку `created_at + N * interval_seconds`. До due time lookup MUST NOT происходить. Каждый run SHALL иметь устойчивые watch/run/slot identifiers и outcome. На background tick MUST NOT вызываться LLM или собственный MCP endpoint. Одновременное выполнение одного watch MUST NOT допускаться. Durable история SHALL содержать не более одного execution для `(watch_id, scheduled_at)`.

#### Scenario: Backend is offline when a slot becomes due
- **WHEN** watch сохранён, локальный backend остановлен и наступило время слота
- **THEN** VPS самостоятельно выполняет lookup и сохраняет результат без Android/model request

#### Scenario: Repeated processing of one due slot
- **WHEN** обработка due jobs повторно вызывается для уже claimed или завершённого слота
- **THEN** второй execution и второй lookup этого слота не запускаются

### Requirement: Each lookup preserves Google Maven semantics
Lookup SHALL использовать только официальный group index Google Maven с проверенными координатами, конечным timeout и ограничением размера ответа. Snapshot SHALL сохранять source order, URL, lookup ID и фактическое UTC checked time. Outcomes `found`, `no_versions`, `group_not_found`, `artifact_not_found` SHALL различаться; network/timeout/HTTP/XML/response-limit errors MUST NOT становиться пустым успешным snapshot. Service MUST NOT утверждать latest/stable, compatibility или security версий. Ошибки SHALL сохранять безопасную категорию без секретов и stack trace в tool output.

#### Scenario: Negative lookup and failure differ
- **WHEN** один run получает group-index 404, а другой получает timeout
- **THEN** первый имеет нормальный outcome `group_not_found`, второй является failed execution с `upstream_timeout`

#### Scenario: Source returns published versions
- **WHEN** group index содержит точный artifact
- **THEN** snapshot содержит его версии в исходном порядке и коррелируемый upstream lookup ID

### Requirement: Completion and recovery have explicit bounded semantics
SQLite SHALL быть source of truth для watches, executions и сохранённых summaries. Каждый terminal execution, включая failure и interruption, SHALL расходовать один из `max_runs`; completed watch SHALL иметь `next_run_at=null` и не выполнять новых runs. После restart/reboot active watches SHALL восстанавливаться из сохранённых данных. Несколько пропущенных слотов SHALL объединяться в одну актуальную проверку без фиктивных исторических snapshots; после обычного выполнения выбирается первый будущий слот исходной сетки, строго позже уже выполненного слота даже при сдвиге часов назад. Незавершённый `running` execution SHALL становиться failed с категорией `interrupted`, неизвестным lookup outcome и без повторного исполнения того же слота. При наличии оставшегося лимита более поздние due slots после interrupted SHALL оставаться доступными обычному coalescing, а не отбрасываться только из-за startup recovery. Обычные lookup failures MUST NOT вызывать immediate retry. Service MUST NOT обещать exactly-once upstream execution или выполнение всех пропущенных слотов.

Startup recovery persisted `running` SHALL выполнять полноценную terminalization transaction: сохранить failed/interrupted execution, учесть его в max_runs, пересчитать deterministic aggregate с этим execution, сохранить aggregate_json и through_execution_id, обновить watch status и следующий допустимый next_run_at либо completed/next_run_at=null. Эти изменения SHALL фиксироваться одним commit до готовности service к summary; немедленный summary после startup SHALL видеть согласованное состояние без следующего scheduler tick и без отложенного исправления aggregate на чтении. Ошибка SHALL откатывать весь переход; повторный startup после commit MUST NOT повторно учитывать уже terminal execution.

#### Scenario: Finite watch includes one failure
- **WHEN** watch с max_runs=3 завершил два успешных и один failed execution
- **THEN** он completed, total=3, successful=2, failed=1 и четвёртый run не выполняется

#### Scenario: Restart after a long outage
- **WHEN** сохранённый active watch пропустил несколько слотов без running execution
- **THEN** выполняется одна проверка для последнего due слота, пропуски отражаются отдельно и backlog не запускается серией

#### Scenario: Crash leaves an unfinished run
- **WHEN** startup обнаруживает running execution предыдущего процесса
- **THEN** execution завершается как interrupted, не получает выдуманных версий или checked_at, расходует один run и не переисполняется

#### Scenario: Immediate summary after recovery retains an active watch
- **WHEN** watch с max_runs=3 имеет один succeeded и следующий persisted running execution, storage переоткрыт, startup recovery завершён и summary запрошен до первого scheduler tick
- **THEN** summary содержит interrupted=1, runs_total=2, successful=1, failed=1, through_execution_id восстановленного execution и тот же aggregate, который сохранён в aggregate_json
- **AND** watch active, next_run_at равен следующему допустимому слоту после interrupted, включая due slot для дальнейшего coalescing, running_execution отсутствует и новый lookup не выполнялся

#### Scenario: Immediate summary after recovery observes completion
- **WHEN** та же persisted история восстановлена для watch с max_runs=2 и summary запрошен сразу после startup без scheduler tick
- **THEN** summary содержит interrupted=1, runs_total=2, successful=1, failed=1, through_execution_id восстановленного execution, watch status=completed и next_run_at=null
- **AND** aggregate_json уже сохранён согласованно, а повторный startup не увеличивает counts и не меняет terminal result

#### Scenario: Storage cannot commit
- **WHEN** запись SQLite не может быть подтверждена либо БД повреждена
- **THEN** service не подтверждает успешный create/result, прекращает scheduling и сообщает unhealthy/error вместо перехода на память или пустую БД

### Requirement: Persisted aggregation is deterministic and explicit
После каждого terminal execution service SHALL атомарно сохранять его результат, следующее состояние watch и aggregate по persisted history. Summary SHALL содержать watch identity/parameters/status, `runs_total`, `successful`, `failed`, `interrupted`, `comparable_snapshots`, `first_checked_at`, `last_checked_at`, `first_version_count`, `last_version_count`, `changes_detected`, `newly_seen_versions`, `latest_execution`, `through_execution_id` и время формирования. `runs_total=successful+failed`; interrupted SHALL быть подмножеством failed. Normal negative lookups SHALL входить в successful, но только found/no_versions SHALL задавать сравнимые snapshots. Checked times SHALL относиться к реально завершённым lookup, не публикации или восстановлению interrupted run; недоступные значения SHALL быть null.

Изменение SHALL означать различие множеств соседних пригодных snapshots, без учёта порядка и без объявления первого snapshot изменением. Newly seen SHALL включать уникальные версии, впервые наблюдавшиеся после baseline; повторное появление версии MUST NOT считаться новой. Промежуточные ошибки/отсутствие artifact MUST NOT моделироваться как исчезновение всех версий. Summary MUST NOT делегировать модели подсчёт или сравнение.

#### Scenario: Three unchanged successful snapshots
- **WHEN** сохранены три одинаковых found snapshots
- **THEN** total=successful=3, failed=0, comparable_snapshots=3, changes_detected=0 и newly_seen_versions пуст

#### Scenario: Same count but different membership
- **WHEN** после baseline [a,b] сохранён [b,c]
- **THEN** changes_detected=1, оба version counts равны 2 и newly_seen_versions=[c]

#### Scenario: Failed lookup between comparable snapshots
- **WHEN** история содержит found [a], timeout, found [a,b]
- **THEN** failed=1, comparable_snapshots=2, changes_detected=1 и newly_seen_versions=[b], без фиктивного перехода к пустому набору

### Requirement: Summary reads never cause new work
Summary SHALL принимать `watch_id` и возвращать сохранённый aggregate вместе с актуальным состоянием watch/running execution в согласованном read snapshot. До первого execution SHALL возвращаться нулевой aggregate с null baseline/times и empty newly_seen_versions. После completion итог SHALL оставаться доступным. Неизвестный или неверный ID SHALL давать явную ошибку, не новый watch. Чтение MUST NOT обращаться к Google Maven, вызывать LLM либо продлевать расписание.

#### Scenario: Summary before and after execution
- **WHEN** summary запрошен до первого run либо после completion
- **THEN** возвращается соответствующий пустой/итоговый результат без изменения числа executions и upstream calls

### Requirement: Remote runtime remains supervised and bounded
VPS deployment SHALL автоматически запускаться после reboot, восстанавливаться после process failure и хранить SQLite вне заменяемого deployment directory. Только один scheduler owner SHALL управлять одной БД. Публичный transport SHALL использовать доверенный HTTPS и проверку public Host; health SHALL отражать доступность storage и scheduler без раскрытия credentials. Worker failure MUST NOT оставлять service falsely healthy. Зарегистрированная работа SHALL не зависеть от ноутбука; доступность локального conversational backend MUST NOT объявляться круглосуточной.

#### Scenario: Second owner or dead worker
- **WHEN** второй процесс пытается управлять той же БД либо scheduler первого процесса прекращает работу с ошибкой
- **THEN** второй owner не допускается, а отказ первого отражается как service failure/unhealthy вместо скрытой остановки jobs

#### Scenario: Reboot preserves active work
- **WHEN** VPS перезагружен с active watch и сохранённым data directory
- **THEN** service стартует без SSH launch, восстанавливает то же watch ID и продолжает по описанной recovery policy
