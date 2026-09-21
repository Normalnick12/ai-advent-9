## Context

Мотивация и границы — в [proposal.md](proposal.md). В проекте уже есть standalone Python Day 01 с собственным requirements.txt; backend использует pip requirements, FastAPI и pytest. Его общий tests/conftest.py импортирует приложение и настраивает хранилища предыдущих Days. Для Day 16 это ненужная зависимость.

MCP-кода и runtime dependency в проекте пока нет. Design необходим из-за новой внешней зависимости и различия между современным protocol negotiation и legacy initialize handshake. Реальное подключение и каталог в рамках подготовки proposal не проверялись.

## Goals / Non-Goals

**Goals:** минимальный самостоятельный процесс с понятным выводом, ограниченным ожиданием сети, корректным освобождением ресурсов и раздельными offline/live доказательствами.

**Non-Goals:** расширение backend или универсальный слой интеграции. Полный OUT OF SCOPE задан в proposal; никакие server/tools orchestration, модель или agent state в этот путь не входят. Не реализовывать протокол вручную и не добавлять механизм выбора/переключения серверов.

## Decisions

### 1. Standalone directory and environment

Планируемый состав:

```text
day-16-mcp-discovery/
  main.py
  requirements.txt
  requirements-dev.txt
  tests/test_discovery.py
  README.md
README.md
```

В main.py достаточно точки входа и нескольких небольших функций только там, где выделяются получение каталога и форматирование. Не вводить adapter/service/repository классы, пакетный build configuration или capability registry.

Python 3.11+; собственный локальный .venv. requirements.txt содержит `mcp==2.2.0`; requirements-dev.txt включает runtime requirements и `pytest>=8.3,<10`, как в существующем проекте. Не нужны `mcp[cli]`, OpenAI SDK или общий backend requirements. Точная версия MCP фиксирует выбранный API, но не является полным lock транзитивных зависимостей.

Альтернатива backend module + CLI отклонена: полезного переиспользования нет, а общий test setup подключает FastAPI и базы. Расширение scripts/dev.ps1 также не требуется. Существующий .gitignore уже исключает .venv, Python bytecode и pytest cache.

### 2. Default SDK v2 Client owns protocol negotiation

Единственный endpoint — `https://mcp.deepwiki.com/mcp`, Streamable HTTP, без credentials. Использовать официальный `mcp.Client` с URL и default negotiation behavior внутри async context manager.

```text
process
  --> Client(DeepWiki endpoint)
  --> connect + protocol negotiation
  --> tools/list [remaining pages if present]
  --> print catalog
  --> leave client context
  --> normal exit
```

Современный MCP может использовать `server/discover`; legacy server — initialize handshake. SDK выбирает совместимый путь. Не форсировать wire revision, не вызывать вручную отдельный handshake и не объявлять initialize обязательным шагом CLI/acceptance. Фактический negotiated `protocol_version` берётся из подключённого клиента. Проверка конкретной wire sequence не нужна.

Альтернатива низкоуровневому session/transport коду отклонена: default Client уже решает lifecycle и совместимость. Альтернатива legacy SSE не используется: выбран Streamable HTTP endpoint. Microsoft Learn рассматривался в Explore, но не входит в реализацию или fallback.

Справочные источники API: [официальный SDK](https://github.com/modelcontextprotocol/python-sdk), [Client](https://py.sdk.modelcontextprotocol.io/client/), [DeepWiki MCP](https://docs.devin.ai/work-with-devin/deepwiki-mcp). Установленная версия 2.2.0 и её доступная API surface проверяются при реализации; при несовместимости не заменять dependency или протокол молча.

### 3. Dynamic catalog and readable output

После успешного входа в Client context вывести endpoint, сообщение об успешном MCP connection/negotiation, `protocol_version` и доступные `server_info.name`/`server_info.version`. Если identity или её поле отсутствует, явно обозначить это; не подставлять версию SDK вместо server version.

Вызвать `list_tools()`, взять `.tools`; при наличии `.next_cursor` получить остальные страницы простым циклом. Сначала собрать полный результат, затем вывести общий count и каждое определение. Не считать частично полученные страницы полным каталогом при ошибке продолжения. Pagination остаётся локальной деталью, без отдельной abstraction.

Для каждого tool вывести name, description и полную `input_schema` как JSON с отступами и читаемым Unicode. При отсутствии description использовать явную пометку. Не сокращать вложенные properties, required, $defs/$ref и другие поля схемы. Порядок сервера сохраняется; сортировка и собственная schema normalization не нужны.

Не фиксировать names или count DeepWiki. Пустой корректный ответ выводится как 0 tools: discovery может технически завершиться с кодом 0, но критерий непустого каталога для live acceptance тогда не выполнен. Это не ошибка протокола и не основание подменять результат fixture.

### 4. Completion and errors

Контекст SDK владеет соединением и освобождает ресурсы при успехе и ошибке. Сообщение о нормальном завершении печатать после выхода из контекста; exit code 0 означает завершённое discovery, вывод и штатный cleanup.

Предусмотреть ограниченное ожидание: ориентир — общий 60-секундный timeout для async операции подключения и discovery с выходом из контекста при отмене. Это operational limit, не метрика latency и не benchmark. Ошибки connection/negotiation/listing/output/cleanup дают краткое сообщение в stderr и ненулевой код. Не печатать итоговый success при failure после уже показанного connection success. Не добавлять собственные retries, бесконечный reconnect или silent fallback; protocol behavior SDK остаётся default.

### 5. Proportional offline checks

Один tests/test_discovery.py проверяет нашу небольшую логику:

- Форматирование SDK tool definitions: имена, Unicode description, полная вложенная schema, отсутствие optional description/identity, пустой список.
- Если выделена функция сбора страниц: два controlled list results, передача next_cursor и итоговый count; failure второй страницы не выдаёт частичный success.
- Error outcome на границе CLI: ненулевой код и отсутствие финального success при controlled exception.

Достаточно SDK-моделей данных и нескольких локальных fake/monkeypatch объектов для реально выделенных функций. Async cases можно вызывать через asyncio.run; отдельный async pytest plugin не нужен. Не тестировать внутренний negotiation SDK, не создавать собственный MCP server, in-memory protocol harness или универсальную mock infrastructure. Offline suite не обращается к сети, OpenAI, backend или пользовательским базам.

### 6. Live acceptance and documentation

После реализации отдельно выполнить CLI с реальным DeepWiki. Условия приёмки одного запуска:

1. Реальное подключение к указанному endpoint через официальный SDK.
2. Успешное protocol negotiation и вывод negotiated protocol_version.
3. Реальный tools/list, без fixture и cached catalog.
4. Непустой итоговый каталог; names/count берутся только из ответа этого запуска.
5. Читаемые name, description (или пометка отсутствия), полная input schema каждого tool; identity/version при наличии.
6. Выход из client context и нормальное завершение процесса с code 0.

Для видео показать команду, вывод и exit code. В Day README использовать разделы «Суть эксперимента», «Что проверяет», «Результаты» и минимальную настройку standalone CLI: Python, установка requirements, команды запуска и offline tests. Не ссылаться на backend/Android как на необходимые компоненты и не требовать OPENAI_API_KEY. Пока live не проведён, явно это написать; после него записать только фактический итог с датой и count, без обещания стабильности внешнего каталога. Подробный acceptance остаётся здесь, без длинного сценария видео в Day README. Добавить существующую относительную ссылку на Day README в правильное место root README.

Успешный live доказывает способность данного процесса в данном запуске подключиться, согласовать протокол и получить/разобрать каталог. Он не доказывает выполнение tools, semantic correctness схем, выбор моделью, orchestration, качество MCP или MCP vs Skills.

## Risks / Trade-offs

- [DNS, HTTPS/proxy, сертификаты, потоковый transport или недоступность DeepWiki] → timeout и явный failure; live отмечается как не пройденный, без изменения endpoint и ослабления TLS.
- [Внешний каталог меняется] → runtime discovery, полный вывод, отсутствие фиксированных names/count в tests и acceptance.
- [Различия MCP revisions] → default SDK negotiation; protocol_version берётся из результата, initialize не является обязательной semantics.
- [Offline tests создают ложное ощущение remote compatibility] → их результаты отделены от live и видео.
- [Pin SDK не фиксирует всё окружение] → отдельный venv и проверка установки при реализации; не вводить новую систему управления зависимостями ради этого дня.

## Migration Plan

Изменение additive: добавить папку Day 16 и ссылку root README, установить зависимости только в её локальный venv. Миграции данных, deployment backend и Android проверки не нужны. Откат ограничен удалением добавленных файлов Day 16 и его ссылки; существующие Days не затрагиваются.
