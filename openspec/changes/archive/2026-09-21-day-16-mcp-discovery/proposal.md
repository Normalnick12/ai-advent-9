## Why

Day 16 открывает неделю MCP + Skills минимальным проверяемым экспериментом: standalone Python process подключается к реальному remote MCP server через официальный SDK и получает предоставляемый им tool catalog. Это позволяет проверить connection и discovery отдельно от выполнения инструментов и существующего агента.

## What Changes

- Добавить самостоятельный CLI в `day-16-mcp-discovery/` с runtime dependency `mcp==2.2.0`.
- Использовать единственный endpoint `https://mcp.deepwiki.com/mcp`, Streamable HTTP, без authentication.
- Реализовать flow `connect → protocol negotiation → tools/list → catalog` через default SDK v2 `Client`. Выбор современного discovery или legacy initialize handshake остаётся внутри SDK; конкретный handshake не является acceptance requirement.
- Вывести endpoint, успешное MCP connection, negotiated `protocol_version`, server identity/version при наличии, количество tools и name/description/input schema каждого инструмента; штатно завершить процесс.
- Получать каталог динамически, без фиксированных names/count; при pagination собрать страницы небольшим циклом по `next_cursor`.
- Добавить пропорциональные deterministic offline tests собственной логики и отдельный manual/live acceptance с непустым реальным каталогом и exit code 0.
- Добавить краткий русский Day README с фактическими результатами и относительную ссылку на него в разделе «Задания» root README.

## Capabilities

### New Capabilities

- `mcp-discovery-experiment`: изолированное подключение к DeepWiki, protocol negotiation, получение и читаемый вывод tool definitions, завершение процесса и раздельные offline/live доказательства.

### Modified Capabilities

Нет. Контракты существующих Days сохраняются.

## Impact

- Новые файлы ограничены standalone Day 16: CLI, requirements, небольшой тестовый файл и README; вне папки изменяется только ссылка в root README.
- Собственное Python-окружение; не добавлять MCP в backend dependencies. Backend, Android, scripts/dev.ps1 и существующие базы не затрагиваются.
- Live зависит от доступности внешнего DeepWiki и сети. Offline tests не доказывают remote connection или фактический каталог.
- OUT OF SCOPE: `tools/call` и вызов любого DeepWiki tool; LLM/OpenAI Responses API, передача definitions модели, tool selection, agent loop; multiple MCP servers, `ClientSessionGroup`, orchestration, собственный MCP server; Skills, MCP vs Skill + CLI, idle overhead/batching/schema weight experiments; Android, Day 15 Playground, Memory/Profile/State/Invariants/Lifecycle/LlmClient; generic MCP/tool/capability framework.
