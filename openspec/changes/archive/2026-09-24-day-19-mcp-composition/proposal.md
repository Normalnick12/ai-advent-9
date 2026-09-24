# Proposal

## Why

Day 17 подтвердил MCP lookup, но модель неверно пересказала количество версий; Day 18 подтвердил фоновую работу scheduler и программную сводку, а не последовательную композицию tools моделью. Day 19 проверяет, сможет ли модель после одного запроса самостоятельно выбрать три MCP tools, точно передать данные между ними и сохранить проверяемый отчёт.

## What Changes

- Добавить отдельный entrypoint/HTTPS endpoint Day 19 с ровно тремя tools одного сервера: `get_google_maven_versions`, `summarize_dependency_versions`, `save_dependency_report`. Состав tools и поведение endpoints Days 17–18 сохраняются.
- Переиспользовать ограниченную Google Maven lookup-логику без запуска scheduler; передавать полный `LookupResult`, включая весь список версий, во второй tool, затем полный `DependencyReport` в третий.
- Программно вычислять `version_count=len(versions)`, `last_three=versions[-3:]` в исходном порядке и hash входа. Сохранять типизированный отчёт как канонический JSON в выделенном каталоге VPS; модель не управляет путём или произвольным содержимым файла. Обязательные файловые проверки покрывают ограничение пути, атомарность, последовательный идемпотентный повтор, ошибку записи и независимое чтение; конкурентность и crash-recovery проверяются по выявленному риску.
- Добавить отдельную backend operation с native Responses MCP, `tool_choice="auto"`, allowlist трёх tools и одной отправкой без retry/repair. Минимальный пользовательский вход — локальный backend API и CLI launcher; новый Android экран не требуется.
- Добавить независимый verifier: оба перехода actual arguments/outputs, ожидаемый расчёт, receipt и независимо прочитанные байты файла. Отдельные verdicts: tools, выбор/порядок, перенос данных, расчёт, файл и финальный текст; исходные данные не исправляются.
- Зафиксировать порядок offline → deployment/readiness → pre-live с измерением полного payload/оценкой token budget → один live. Технические gates не добавляют обязательных запросов разрешения сверх AGENTS.md и явных указаний пользователя. Фиксированная цепочка через три MCP client calls служит offline-контролем. Сокращение списка требует явного изменения proposal/specs/acceptance до live.
- Добавить краткий Day README и ссылку в корневой README при реализации; технические команды и эксплуатацию описать в README компонентов. Записать фактический результат, включая неуспешную попытку.

## Capabilities

### New Capabilities

- `mcp-composition-service`: изолированный сервер трёх tools, строгие контракты lookup/report/receipt, детерминированная обработка и ограниченная запись JSON.
- `mcp-composition-experiment`: одна auto-операция, неизменяемое evidence, независимый verifier, offline/pre-live/live gates и раздельные вердикты.

### Modified Capabilities

Нет. Контракты `android-dependency-mcp`, `first-mcp-tool-experiment`, `dependency-watch-service` и `dependency-watch-experiment` не меняются. Изменения Android navigation не планируются.

## Impact

Будущие изменения ограничены `day-19-mcp-composition/`, отдельными backend DTO/service/route и локальным launcher/verifier, deployment templates, профильными тестами и README. Переиспользование lookup не должно импортировать серверные entrypoints; при затрагивании общего кода обязательны регрессионные проверки Days 17–18. MCP runtime изолирован от backend environment; OpenAI key остаётся на локальном backend.

На существующем VPS предполагаются отдельный Day 19 process/endpoint и `/var/lib/day19/reports/` вне release tree. Этот proposal не разрешает текущие implementation, deployment или live-действия; подготовлены только planning artifacts для review.

Вне объёма: scheduler, SQLite/schema migration, очереди, универсальный workflow engine, semver/stable/latest-анализ, новый Android экран, несколько агентов, четвёртый модельный read-file tool, автоматический repair и скрытые повторные попытки. Полный список передаётся явно; server-side handles и подписи не входят в минимальный эксперимент. SHA-256 проверяет согласованность данных, но не удостоверяет их происхождение. Одна попытка не доказывает устойчивость модели; PASS цепочки и точность пересказа оцениваются независимо.
