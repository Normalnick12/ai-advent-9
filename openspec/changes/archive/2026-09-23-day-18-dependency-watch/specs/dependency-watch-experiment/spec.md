# Spec Delta

## Purpose

Связать пользовательские create/summary операции Day 18 с native remote MCP и собрать проверяемое evidence автономной фоновой работы отдельно от точности ответа модели.

## ADDED Requirements

### Requirement: Native operations use standard authorization and isolated configuration
Каждое явное create/summary действие SHALL отправлять один Responses API request с native MCP, server-side HTTPS URL, узким allowed_tools для выбранной операции и штатным полем `authorization`. Bearer token SHALL загружаться только из backend environment и настраиваться на VPS; token MUST NOT попадать в Android, prompt, logs, сохранённый request evidence или Git. Backend SHALL передавать credential в каждом запросе через `authorization`, не через произвольные custom headers. OpenAI key SHALL оставаться на локальном backend. Отсутствие Day 18 URL/token SHALL возвращать configuration error без provider request и не ломать предыдущие Days.

#### Scenario: Authorized create request
- **WHEN** пользователь запускает создание watch при настроенном backend
- **THEN** Responses получает create-only allowlist, forced choice нужного MCP tool и `authorization` из environment; аргументы формирует модель, а секрет отсутствует в model input и клиентском результате

#### Scenario: Summary operation cannot create a watch
- **WHEN** пользователь запрашивает summary выбранного watch ID
- **THEN** provider request разрешает только summary tool; фактический ID сверяется с выбранным ID и mismatch не представляется результатом выбранного watch

#### Scenario: Day 18 is not configured
- **WHEN** URL или token отсутствует и пользователь обращается к Day 18
- **THEN** возвращается configuration error без provider invocation, остальные Days работают по прежним контрактам

### Requirement: Attempts retain all available calls without repair
Backend SHALL отключить automatic SDK retry, regeneration и repair. Он SHALL сохранять response id, final text при наличии, все доступные discovery/call/error items и фактические arguments/results каждой операции с безопасной редактированной копией request configuration. Несколько create calls MUST NOT скрываться за одним выбранным success. Наблюдение invocation SHALL отличаться от successful create и точности prose. Timeout без Responses result SHALL оставлять invocation unknown; приложение MUST NOT утверждать отсутствие созданного watch или автоматически повторять запрос.

#### Scenario: Multiple creates occur in one response
- **WHEN** Responses содержит несколько create calls
- **THEN** все вызовы, ошибки и возвращённые watch IDs остаются в evidence, а наличие дублей явно видно без обещания идемпотентности

#### Scenario: Provider result is unavailable
- **WHEN** deadline истёк до получения Responses result
- **THEN** попытка имеет unknown invocation, автоматический retry отсутствует; возможный созданный watch не объявляется отменённым

#### Scenario: Invalid or incomplete tool output
- **WHEN** output не соответствует schema/arguments либо Responses incomplete/refused
- **THEN** доступное evidence сохраняется, parsed result не фабрикуется и прежний success не подставляется

### Requirement: Program facts are separate from model prose
Backend SHALL валидировать typed create/summary result и связь с actual arguments. Counts и changes SHALL браться из service aggregate, не из model prose. Модель SHALL использовать готовые факты для объяснения, но приложение MUST NOT обещать корректность любого natural-language ответа. Background ticks MUST NOT создавать Responses calls.

#### Scenario: Model misstates a count
- **WHEN** model text называет число, отличное от typed aggregate
- **THEN** structured result остаётся неизменным, фактическая точность оценивается отдельно и автоматическое исправление текста не выполняется

### Requirement: Offline verification controls time and failure inputs
Automated scheduler/aggregation/recovery checks SHALL использовать управляемое время, изолированное persistent storage и детерминированный upstream без длинных sleep, реального Google Maven и OpenAI. Проверки SHALL включать not-due/due, max-runs, duplicate slots, restart restore, interrupted run, coalescing, negative/error outcomes, transactional failure, membership changes и summary до/после выполнения. Отдельные integration checks SHALL проверять auth/discovery и provider evidence contracts, включая отсутствие token в выводе.

#### Scenario: Time advances without waiting
- **WHEN** test clock проходит T0, T0+I, T0+2I, T0+3I для трёх быстрых успешных runs
- **THEN** в T0 lookup отсутствует, затем получены три executions и completed watch без real-time sleep

### Requirement: Live acceptance correlates independent background work
Основной live SHALL создавать watch `androidx.core:core-ktx` через Android agent/native MCP с interval=30 секунд и max_runs=3 после отдельной readiness. Evidence SHALL связывать deployed revision, create response/call/watch IDs, время завершения исходного Responses request, VPS execution/lookup logs, SQLite history и отдельный summary response/call. Во время фонового окна локальный backend SHALL быть остановлен и новые model calls SHALL отсутствовать. Успех сценария SHALL требовать три сохранённых успешных runs после завершения исходного request и aggregate, соответствующий БД. Реальное число версий MUST NOT hardcode-иться; ноль обнаруженных изменений SHALL быть допустимым успехом.

#### Scenario: Full short live chain
- **WHEN** три runs выполнены после create response при остановленном локальном backend и затем отдельный агентный запрос получает summary
- **THEN** logs, persisted history, structured tool output и проверка final prose сохранены с фактическими timestamps и revision

#### Scenario: Timing or prose prevents full acceptance
- **WHEN** run произошёл до завершения create request, evidence неполон либо final prose противоречит aggregate
- **THEN** соответствующий критерий отмечен failed/not proven отдельно от подтверждённой механики, без скрытого повторения попытки или repair

### Requirement: Recovery evidence and bounded claims accompany the result
До заявления reboot recovery SHALL быть выполнены отдельные live service-restart и VPS-reboot probes с active watch и сохранёнными IDs/history. Обязательный acceptance MUST NOT требовать ожидания суток; overnight observation SHALL быть явно необязательным. Документация SHALL разделять наблюдаемую автономность watches, scheduler correctness и model accuracy, не обещая production SLA, exactly-once, новые релизы или доступность локального backend при выключенном ноутбуке. Day README SHALL отражать только проверенные факты и иметь ссылку из корневого README.

#### Scenario: Recovery probe survives reboot
- **WHEN** active watch существует до reboot и service автоматически восстановлен
- **THEN** сохраняются тот же ID и прежняя история, subsequent execution соответствует recovery policy; фактические timestamps и состояние записаны

#### Scenario: Overnight was not run
- **WHEN** короткий live и recovery probes завершены, а overnight не выполнялся
- **THEN** результат может быть оформлен с явным указанием отсутствия overnight и без заявления бесконечной доступности
