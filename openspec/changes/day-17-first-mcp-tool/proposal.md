## Why

Day 16 проверил discovery чужого MCP-сервера; Day 17 должен показать полный вызов собственного инструмента из Android-приложения через агентную операцию. Android Dependency MCP даёт небольшой полезный read-only сценарий с публичными данными, проверяемым результатом и возможностью дальнейшего развития без расширения scope текущего дня.

## What Changes

- Добавить самостоятельный Python-проект `day-17-android-dependency-mcp` на официальном `mcp==2.2.0`: один инструмент `get_google_maven_versions(group_id, artifact_id)`, регистрация через `MCPServer` / `@mcp.tool()`, генерируемая input schema, структурированный результат.
- Получать версии точной зависимости только из официального Google Maven group index. Проверять координаты до HTTP, сохранять порядок версий источника и различать negative lookup и технические ошибки.
- Подготовить ASGI / Uvicorn Streamable HTTP deployment на Render с публичным HTTPS `/mcp`, stateless HTTP semantics и явно настроенной защитой transport / allowed hosts.
- После реализации, offline checks, scoped diff review и strict OpenSpec validation выполнить отдельный pre-live commit/push deployable revision для Git-backed Render deployment. Зафиксировать фактически deployed commit SHA в live evidence; этот commit не завершает Day 17 и не закрывает live/video tasks.
- Добавить отдельный Day-17-specific backend service/provider path: один native remote MCP Responses API request возвращает typed operation result с final text и реальными `mcp_list_tools` / всеми `mcp_call`. Общий `LlmClient` и контракты Days 6–15 не расширяются.
- Добавить независимый Android Day 17 lab с запросом, режимами «Проверить вызов» / «Автовыбор», итогом и раскрываемым Inspector конкретной попытки.
- Проверить основной forced live по фактическим arguments, output и серверному `lookup_id`; auto оставить дополнительным наблюдением выбора модели. Не выполнять автоматический retry, regeneration или repair.

## Capabilities

### New Capabilities

- `android-dependency-mcp`: собственный remote MCP server, валидация, Google Maven lookup, результаты, ошибки и корреляция с upstream-логом.
- `first-mcp-tool-experiment`: native Responses integration, атомарный результат попытки, evidence, forced/auto semantics и критерии live acceptance.
- `first-mcp-tool-android`: независимый экран Day 17, представление результата и Inspector без повторной отправки при lifecycle/navigation.

### Modified Capabilities

- `learning-days-navigation`: добавить доступный Day 17 в каталог и отдельный destination с возвратом в каталог без повторного запроса.

## Impact

Новый standalone server имеет отдельные зависимости и deployment. Существующий backend получает изолированные Day 17 route, DTO и service/provider, конфигурацию URL remote MCP и регистрацию lifecycle. Android получает Day 17 repository/DTO/ViewModel/screen, DI и точечное расширение каталога/навигации. `OPENAI_API_KEY` остаётся только на backend; Google Maven секретов не требует.

При реализации обновляются README нового дня, backend/Android и ссылка в корневом README; добавляются offline проверки и фиксируются фактические live observations. На этапе proposal меняются только planning artifacts. Реализация, deployment и live ещё не выполнены.

Lifecycle: реализация → все offline checks → scoped review/validation → pre-live commit/push → Render deployment/readiness/discovery → forced live → optional auto → видео → `$finish-day Day 17`. Finish-day актуализирует evidence/docs, архивирует завершённый OpenSpec change и делает финальный commit/push при наличии последующих изменений. Docker registry, tunnel и альтернативный deployment mechanism ради одного финального commit не добавляются.

Не входят: Maven Central, OSV/vulnerabilities, latest/stable/recommendations, BOM/compatibility/dependency graph, изменения Gradle и upgrades, batching, дополнительные tools/servers, orchestration, Skills и MCP vs Skill + CLI, auth/generic framework, Memory/Profile/FSM/Invariants и изменения Day 15 Playground. Потенциал Week 4 не является обещанием реализации этих возможностей в Day 17.
