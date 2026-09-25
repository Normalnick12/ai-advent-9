## Why

Day 19 подтвердил композицию трёх tools одного MCP server, но инструкция задавала инструменты и их порядок. Day 20 нужен как практический шаг к developer-agent: одна инженерная задача требует исследования репозитория и проверки публикаций зависимостей в другой независимой системе, а следующий tool и arguments выбирает модель.

## What Changes

- Добавить изолированный эксперимент `day-20-mcp-orchestration`: исследовать в `android/nowinandroid` зависимости для локального хранения данных и фоновой работы/синхронизации, проверить соответствующие Google Maven publications и получить сводки. Room и WorkManager — кандидаты exploration, не зашитый ответ.
- В одном native Responses run одновременно зарегистрировать DeepWiki и существующий Dependency Composition MCP endpoint Day 19. Оставить `tool_choice="auto"`; пользовательская задача и системная инструкция описывают результат, но не перечисляют tool names и полный порядок вызовов. Backend не выполняет переходы вместо модели.
- Поддержать две связанные ветки repository evidence → lookup → summary, допускающие разный порядок независимых шагов. Не вызывать дополнительные tools ради длины flow; не включать серверный save.
- Сделать CLI и читаемый `report.md` главным результатом: какая задача решалась, какую DeepWiki capability выбрал агент, какие dependencies наблюдал, почему понадобился Dependency MCP и что подтверждает trace. Подготовить объяснимую демонстрацию для видео без чтения verifier JSON.
- Сохранить первую попытку в уникальном локальном каталоге без перезаписи: конфигурацию без секретов, native MCP discovery/calls/results, исходный финальный ответ и доступные события. Узкий verifier проверяет регистрацию/import, вызовы обоих servers, согласованность coordinates и переходов двух веток, порядок, сводки и отдельно финальные факты. Все лишние calls видимы; недоказанная repository truth/revision остаётся ограничением `NOT_PROVEN`, без source-review workflow.
- Предусмотреть offline-проверки и один отдельно запускаемый live-run без retry/repair. Простой SDK streaming/event log помогает наблюдать порядок. При неполном evidence — `NOT_PROVEN`; durable attempt protocol, idempotency, recovery/replay и универсальная JSON-валидация не входят в scope.

## Capabilities

### New Capabilities

- `mcp-orchestration-experiment`: выбор инструментов двух remote MCP servers в одной developer-задаче, две dependency-ветки, локальное evidence первой попытки и независимая ограниченная проверка наблюдаемого flow.

### Modified Capabilities

Нет. Контракты Days 16–19 и общего agent runtime сохраняются.

## Impact

- Новый каталог Day 20 с CLI, небольшим offline verifier, fixtures/tests и кратким README; локальные evidence/output paths изолированы от предыдущих дней.
- Отдельный Day 20 endpoint/service/models в существующем FastAPI backend, минимальное подключение в `backend/app/main.py`; официальный OpenAI Python SDK и patterns Day 16/17/19. Без рефакторинга `SimpleAgent`/`LlmClient` и без нового Android экрана.
- Документация запуска в `backend/README.md` и `scripts/README.md`, относительная ссылка на Day 20 README в корневом индексе. Никаких обязательных новых runtime-сервисов.
- Remote systems: DeepWiki и уже развёрнутый Day 19 Dependency MCP как black-box. Нет Context7, gateway, нового MCP server, VPS deployment, SSH, systemd/Caddy изменений, новых domain/port или server-side file inspection.
- Работа с planning artifacts не запускает implementation или live. Результат одной попытки не доказывает оптимальность выбора, истинность DeepWiki, актуальность `main`, совместимость или безопасность опубликованных версий.
