# Spec Delta

## Purpose

Дать пользователю компактный Day 18 экран регистрации наблюдения и получения сводки с проверяемыми фактами, сохранённым watch receipt и evidence отдельных агентных запросов.

## ADDED Requirements

### Requirement: Explicit actions guard duplicate sends
Day 18 SHALL предоставлять prompt, явное создание watch, current watch receipt и отдельное действие получения summary. Пока выполняется операция, повторные Sends SHALL блокироваться синхронным UI/ViewModel guard. Recomposition, rotation, navigation и восстановление процесса MUST NOT автоматически отправлять create/summary или выполнять retry/regeneration. Приложение MUST NOT называть create идемпотентным либо обещать отсутствие нескольких watches при нескольких фактических MCP calls.

#### Scenario: Rapid duplicate taps
- **WHEN** пользователь дважды нажимает Send до завершения первой операции
- **THEN** инициируется только одна backend operation

#### Scenario: Uncertain create result
- **WHEN** backend не вернул подтверждённый create result
- **THEN** UI сообщает о неизвестной судьбе операции и возможном создании watch, не переотправляет create и не объявляет его отменённым

### Requirement: Durable receipt restores identity without replay
Android SHALL сохранять подтверждённые watch IDs, coordinates, accepted schedule и selection в отдельном Day 18 namespace. После process death SHALL восстанавливаться receipt, а не выдуманный актуальный status или потерянный полный provider response. Summary SHALL запрашиваться только явно. Если одна операция вернула несколько валидных create receipts, UI SHALL показывать их наличие и позволять явно выбрать watch для summary; это MUST NOT требовать list MCP tool. Android MUST NOT участвовать в background ticks.

#### Scenario: Reopen after laptop and app shutdown
- **WHEN** приложение открыто заново с сохранённым watch receipt
- **THEN** доступен тот же watch ID для явного запроса summary, create не повторяется, сохранённые сведения обозначены как последние известные

#### Scenario: Multiple returned watches
- **WHEN** один response содержит два подтверждённых create results
- **THEN** оба IDs доступны, выбор для summary явный и ни один create call не скрыт в Inspector

### Requirement: Typed summary and model explanation remain distinct
Main SHALL показывать watch ID, фактическое расписание, последний известный status, runs, changes, checked times и errors из валидированного result. Model explanation SHALL показываться отдельно. Null/unavailable MUST NOT превращаться в ноль или success; summary с нулём executions SHALL объяснять ожидание первой проверки. Экран SHALL сообщать, что работа выполняется на VPS, а пользовательский запрос требует локальный backend. Русские labels и прокрутка SHALL сохранять доступность controls при узком экране, увеличенном шрифте и IME.

#### Scenario: No runs or failed run
- **WHEN** summary имеет ноль executions либо failed execution среди успешных
- **THEN** показаны соответствующие counts/outcomes без фиктивного baseline и без превращения failed lookup в отсутствие новых релизов

### Requirement: Inspector exposes complete attempt evidence safely
Inspector SHALL сохранять immutable submitted action/prompt/selected ID, response id, imported tools, каждый actual call с arguments/output/error, parsed receipt/aggregate и доступные run/lookup IDs. Новая failed попытка MUST NOT наследовать старое evidence как своё; прошлый watch receipt SHALL оставаться отдельной сущностью. MCP token и OpenAI key MUST NOT поступать в Android. Недоступные provider fields SHALL оставаться null/absent.

#### Scenario: Failed summary follows successful create
- **WHEN** summary request завершился ошибкой после ранее подтверждённого create
- **THEN** current attempt показывает своё error evidence, watch receipt остаётся доступен отдельно и предыдущий create не выдаётся за успешный summary
