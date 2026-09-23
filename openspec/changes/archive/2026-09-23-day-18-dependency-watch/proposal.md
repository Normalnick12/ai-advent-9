# Proposal

## Why

Day 17 подтвердил немедленный remote MCP lookup, но работа завершалась вместе с запросом. Day 18 должен показать durable задание, которое после регистрации агентом самостоятельно выполняется на VPS и периодически сохраняет проверяемую сводку, независимо от Android и ноутбука.

## What Changes

- Добавить самостоятельный Android Dependency Watch service с двумя MCP tools: `create_dependency_watch` и `get_dependency_watch_summary`.
- Сохранять конечные watches с обязательным `max_runs`, расписание, execution slots, Google Maven snapshots и программно вычисленные aggregates в SQLite.
- Выполнять async lookup небольшим scheduler loop без LLM на tick; определить coalescing пропущенных слотов, interrupted executions и восстановление после restart/reboot.
- Защитить публичный HTTPS `/mcp` штатной Bearer authorization через поле `authorization` native remote MCP integration. Token хранится только в backend environment и на VPS; custom headers не являются архитектурной зависимостью.
- Не обещать idempotent create: каждый фактически принятый create может создать новый watch. Ограничить duplicate Send в Android, исключить automatic retry/regeneration/repair и сохранять все фактические create calls в evidence. Уникальность `(watch_id, scheduled_at)` относится только к execution slots.
- Добавить отдельные backend operation и компактный Android lab Day 18: create, сохранённый watch receipt, запрос summary, typed result и Inspector. Существующий agent backend остаётся локальным.
- Подготовить deployment через Python venv, systemd и Caddy, offline проверки без ожидания и короткий live с тремя фоновыми runs, отдельные restart/reboot probes и честный verdict точности model prose.
- Добавить краткий Day README и ссылку из корневого README; команды и эксплуатацию описать в README компонентов.

## Capabilities

### New Capabilities

- `dependency-watch-service`: конечные scheduled watches, два authenticated MCP tools, SQLite, lookup, recovery, aggregation и автономный VPS runtime.
- `dependency-watch-experiment`: изолированная native Responses integration, Bearer credential, полное evidence и проверяемый offline/live acceptance.
- `dependency-watch-android`: отдельный экран create/summary, duplicate Send guard, сохранённый receipt и Inspector без background execution на Android.

### Modified Capabilities

- `learning-days-navigation`: добавить независимый Day 18 после Day 17 без replay и изменения прежних destinations.

## Impact

Новый проект `day-18-dependency-watch/`, отдельные модули backend и Android, регистрация route/destination, документация и будущие deployment templates/scripts. Зависимости MCP service изолированы от backend; Google Maven lookup адаптируется из Day 17 в локальный предметный модуль без импорта его серверного entrypoint и без изменения доказанного контракта Day 17.

На Ubuntu VPS размещаются только Day 18 MCP, scheduler и SQLite за Caddy; OpenAI API и локальный FastAPI продолжают обслуживать явные пользовательские операции. Результат означает автономность зарегистрированных watches, а не полную круглосуточную доступность Android-агента, exactly-once upstream execution или production SLA.

В scope не входят endless schedules, cancel/list/update tools, push/Telegram/email, Docker, brokers, distributed workers, общий job framework, перенос Days 6–17 на VPS или изменение Days 11–17 contracts. Planning не запускает реализацию, VPS setup, live, commit или push.
