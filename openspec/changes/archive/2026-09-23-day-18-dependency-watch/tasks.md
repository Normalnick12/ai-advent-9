# Tasks

## 1. Standalone service и Google Maven lookup

- [x] 1.1 Создать `day-18-dependency-watch/` с отдельными runtime/dev requirements и небольшими lookup/storage/scheduler/MCP модулями; проверить import/syntax и отсутствие изменений Day 17 entrypoint/contracts.
- [x] 1.2 Адаптировать Google Maven lookup в предметный модуль без MCP ToolError coupling; fixture-тестами проверить coordinates, source order, normal negative outcomes, timeout/network/HTTP/XML/body-limit failures и отсутствие retries/redirects.
- [x] 1.3 Добавить Day README с тремя обзорными разделами и отметкой «live не проведён», а также упорядоченную относительную ссылку из корневого README; проверить существование target и отсутствие дубликата ссылки.

## 2. Persistence и bounded watch contract

- [x] 2.1 Реализовать initial versioned SQLite schema watches/executions с FK и UNIQUE(watch_id, scheduled_at), persistent path и fail-closed storage errors; проверить reopen файла, rollback и отказ неизвестной schema без очистки данных.
- [x] 2.2 Реализовать strict create validation, обязательный max_runs, default/normal interval, явную short-interval configuration и транзакционные quotas; тестами проверить invalid input, boolean/integer boundary, отсутствие lookup при create и commit-before-receipt.
- [x] 2.3 Зафиксировать non-idempotent create с новым UUID на каждый принятый вызов; тестами проверить два разных IDs для одинаковых разрешённых requests и отсутствие требования idempotency key/custom header.

## 3. Scheduler, recovery и aggregate

- [x] 3.1 Реализовать injectable clock и run_due_jobs(now) с атомарным claim, прямым async lookup и unique slots; без sleep проверить T0/not-due, три due runs, repeated/concurrent processing одного слота и отсутствие MCP/OpenAI call на tick.
- [x] 3.2 Реализовать terminal completion/max_runs, исходную UTC сетку, coalescing и skipped slots; тестами проверить failed run среди successful, отсутствие immediate retry/backlog burst и сдвиг clock вперёд/назад.
- [x] 3.3 Реализовать startup restore и interrupted recovery как одну terminalization transaction: execution, учёт max_runs, пересчёт aggregate, сохранение aggregate_json/through_execution_id, watch status и допустимый next_run_at/completed; failpoint/reopen тестами проверить атомарный rollback, commit до готовности summary, отсутствие replay/повторного учёта, дальнейший overdue slot и исчерпание max_runs.
- [x] 3.4 Реализовать deterministic aggregate и atomic finalize/result/next-run/summary; fixtures должны проверять unchanged sets, одинаковый count при разных версиях, reorder, removal/reappearance, negative/error gaps, null baseline, interrupted counter и rollback без частичной сводки.
- [x] 3.5 Реализовать summary read snapshot для empty/active/running/completed/unknown watch; проверить согласованность through_execution_id и отсутствие новых lookup, LLM calls или schedule mutations при чтении.

- [x] 3.6 Добавить deterministic test persisted running -> reopen/startup recovery -> немедленный summary без scheduler tick: при одном прежнем succeeded проверить interrupted=1, runs_total=2, successful=1, failed=1, through_execution_id восстановленного execution и совпадение с сохранённым aggregate_json; проверить обе ветки max_runs=3 (active/корректный следующий, в том числе due, next_run_at) и max_runs=2 (completed/next_run_at=null), отсутствие running/lookup и неизменность counts после повторного reopen, без sleep и внешних API.

## 4. MCP transport и supervised runtime

- [x] 4.1 Опубликовать ровно create/summary с корректными schemas, annotations и SDK error handling; in-process MCP integration tests должны подтвердить discovery и реальные structured/text result wrappers закреплённого SDK.
- [x] 4.2 Добавить стандартную Bearer проверку `/mcp` до dispatch и fail-closed startup без token; transport tests должны проверить 401 без/с неверным token, успех с валидным token, запрет постороннего Host и отсутствие credentials в logs/output.
- [x] 4.3 Соединить MCP lifespan и единственный supervised scheduler, добавить owner lock, shutdown и безопасный health; проверить отказ второго owner, worker failure/unhealthy и отсутствие оставшегося falsely healthy app после падения scheduler.
- [x] 4.4 Добавить безопасные JSON logs create/execution/lookup с watch/run/lookup IDs и timestamps; тестом с synthetic secret sentinel проверить redaction и корреляцию без полного XML/credential-bearing payload.

## 5. Локальный backend и native Responses evidence

- [x] 5.1 Добавить отдельные Day 18 DTO/service/route и environment configuration; fixture-тестами проверить `authorization` в каждом native MCP request, operation-specific allowlist/forced choice, прежний model alias и configuration error без влияния на старые Days.
- [x] 5.2 Реализовать один provider request с max_retries=0, без regeneration/repair, и normalization всех доступных MCP items; проверить несколько create calls, partial/refusal, timeout unknown, invalid result, summary ID mismatch и сохранность каждого фактического call.
- [x] 5.3 Добавить безопасное сохранение attempt evidence с redacted request configuration и immutable operation snapshot; тестами подтвердить отсутствие token в prompt/response/Android DTO/logs/files и независимость typed aggregate от ошибочного model prose.

## 6. Android lab и navigation

- [x] 6.1 Добавить Day 18 Repository/ViewModel/AppContainer integration, явные create/summary actions и синхронный duplicate Send guard; JVM tests должны подтвердить один POST при повторном нажатии и отсутствие automatic retry/replay.
- [x] 6.2 Добавить scoped durable receipts/selection с поддержкой нескольких возвращённых watch IDs; проверить process-death restore без generation, last-known status, явный выбор для summary и сохранение identity при неизвестном результате новой попытки.
- [x] 6.3 Создать компактный русский экран prompt/current watch/typed summary/model explanation/Inspector; targeted UI tests должны проверить все calls, empty/null/error states, отсутствие старого success у новой ошибки и читаемость на узком экране с IME.
- [x] 6.4 Добавить карточку/destination Day 18 после Day 17; через `scripts/dev.ps1` выполнить целевые JVM/UI navigation checks для возврата/rotation без replay и независимости прежних Days.

## 7. Deployment artifacts и offline integration

- [x] 7.1 Подготовить systemd unit и Caddy templates без секретов, один worker, persistent data path, safe env/permissions, logs и restart policy; проверить синтаксис доступными средствами и отсутствие SQLite/env внутри заменяемого release tree.
- [x] 7.2 Описать в backend/Android/scripts README настройку Bearer environment, запуск/проверки, DNS/TLS/firewall, backup/rollback и границу доступности локального backend; проверить ссылки и отсутствие секретов/дублирующих длинных инструкций в Day README.
- [x] 7.3 Выполнить целевые service/backend suites, Android unit/build и затронутые UI/navigation проверки через `scripts/dev.ps1`; сохранить результаты актуального кода и отдельно выполнить secret review, `git diff --check` и strict OpenSpec validation перед deployment.

## 8. VPS readiness и recovery probes

- [x] 8.1 Настроить согласованный VPS hostname/runtime/venv, непривилегированного пользователя, защищённый environment, постоянную БД, Caddy и enabled systemd unit; проверить SSH доступ, TLS, закрытый application port, права и startup без ноутбука, не печатая token.
- [x] 8.2 Развернуть проверенный service snapshot и сохранить сверенный на VPS manifest/revision; проверить health, authenticated tools/list/schema, отказ без token, upstream connectivity и доступность локального backend с эмулятора как отдельную readiness, не live acceptance.
- [x] 8.3 Выполнить отдельные active-watch service restart и VPS reboot probes; сохранить одинаковые watch IDs, историю до/после, автоматический boot startup и последующие executions согласно recovery semantics.

## 9. Короткий live и фактические результаты

- [x] 9.1 Выполнить одну явно зафиксированную Android create attempt для `androidx.core:core-ktx`, interval=30/max_runs=3; сохранить actual arguments, все create calls, IDs и время завершения Responses без retry/regeneration/repair.
- [x] 9.2 Остановить локальный backend и закрыть Android на background window; по VPS logs и SQLite проверить три runs, их фактическое время относительно response completion и отсутствие user/model calls, сохранив failed/not-proven критерии без подмены timestamps.
- [x] 9.3 Вернуть backend и получить summary отдельной Android agent operation; сверить typed aggregate с persisted history, сохранить MCP evidence и раздельные verdicts mechanism/temporal independence/aggregation/prose accuracy без hardcoded version count и исправления модельного ответа.
- [x] 9.4 Сохранить live/recovery report с deployed manifest/revision и безопасными evidence, вернуть normal interval configuration; проверить, что отсутствие новых версий не считается ошибкой, а overnight явно необязателен/не проводился, если фактов нет.
- [x] 9.5 Получить подтверждение пользователя о проверке результата и записи видео, обновить краткий Day README только по фактам и перепроверить root README link; не объявлять непрошедший full acceptance успешным и не выполнять finish/archive/commit/push внутри этой задачи без отдельного запроса.
