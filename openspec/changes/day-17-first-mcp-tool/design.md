## Context

Мотивация и scope описаны в [proposal](proposal.md). Изменение пересекает standalone server, существующий Python backend и Android app, поэтому требует design.

Day 16 использует официальный `mcp==2.2.0` для discovery. В SDK v2 доступны `MCPServer`, `@mcp.tool()`, ASGI `streamable_http_app` и официальный in-process `Client(server)`; перенос примеров старого `FastMCP` не нужен. Standalone environment предотвращает смешение зависимостей SDK с backend.

В текущем backend `OpenAIResponsesLlmClient` нормализует Responses output до `LlmResult` с текстом, теряя MCP items. `SimpleAgent.generate()` работает через этот контракт. Android уже использует Compose/MVVM, Retrofit, ручной `AppContainer` и отдельные destinations. Эти механизмы подходят для точечного добавления Day 17 без изменения Playground.

## Goals / Non-Goals

**Goals:** атомарный результат одной попытки; различимые уровни ошибок; evidence от upstream до UI; конечный read-only tool, работающий локально в тесте и удалённо через HTTPS. Offline checks проверяют код, forced live проверяет интеграционную цепочку, auto наблюдает выбор модели.

**Non-Goals:** общий agent/tool framework, изменение provider-neutral `LlmClient`, сохранение истории в БД, скрытые повторы и автоматическая оценка истинности произвольного final prose. Полный продуктовый scope и исключения — в proposal.

## Decisions

### 1. Standalone MCP server на SDK v2

Проект `day-17-android-dependency-mcp` имеет собственные requirements (`mcp==2.2.0`), Python environment, тесты и README. Используем high-level `MCPServer` из `mcp.server`; один decorated tool с typed signature, Pydantic `Field` descriptions/constraints и Pydantic result model. Schema генерируется SDK. В description прямо указать exact lookup, Google Maven only и отсутствие рекомендации версии; задать read-only annotation.

ASGI-приложение создаётся через `streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True, transport_security=...)` и запускается Uvicorn. Параметры транспорта задаются в API приложения, а не переносятся из старых примеров конструктора. При необходимости lifespan upstream HTTP client соединяется с lifespan SDK. SDK отвечает за negotiation, discovery, вызовы и serialization. Stateless flag обеспечивает отсутствие зависимости от session state в поддерживаемом legacy HTTP transport; новую sessionless семантику SDK не переопределяем вручную.

Отклонены low-level protocol handlers и собственный test harness: они отвлекают от первого tool. Локальный stdio не является основным integration path, поскольку Responses вызывает публичный remote endpoint.

### 2. Одна проверенная группа — один upstream fetch

Typed strings валидируются без trim, lowercasing и URL decoding. Практический допустимый subset: group `[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*`, artifact `[A-Za-z0-9_][A-Za-z0-9_.-]*`, проверка полной строки; разумный лимит длины 256 символов на параметр. Это ограничение нашего tool, не утверждение о полном стандарте Maven. Нестрочные значения отклоняются без coercion.

Путь строится только после validation: точки group заменяются `/`, origin и suffix фиксированы: `https://dl.google.com/dl/android/maven2/{group_path}/group-index.xml`. Используем один async HTTP GET без automatic retry, redirect following и fallback. Upstream deadline — 15 секунд, отдельный от provider deadline. Для тестируемости HTTP transport инъецируется; допустим отдельный явно объявленный `httpx` клиент, не зависящий от внутренних HTTP abstractions MCP SDK.

404 означает `group_not_found`; остальные non-2xx, в том числе redirect, — HTTP execution error. Для 2xx парсим XML, проверяем root равным group и ищем прямой child с точным artifact tag. Нет child — `artifact_not_found`; ровно один child с `versions=""` — `no_versions`; непустой корректный CSV — `found`. Отсутствующий атрибут, дубли совпавшего artifact, пустой элемент непустого CSV, неверный root или повреждённый XML — XML execution error. Сохраняем исходный порядок; не сортируем и не вычисляем stable/latest. Не загружаем DTD/external entities; ограничиваем размер body (2 MiB), превышение — upstream response error, не пустой lookup.

Master index и artifact metadata альтернативно дают дополнительные round trips/семантику, не нужные для этого задания. Maven Central намеренно отсутствует: `group_not_found` относится лишь к Google Maven.

### 3. Normal result и tool execution error имеют разные каналы

Normal Pydantic result содержит `status`, `group_id`, `artifact_id`, `versions: list[str]`, `source_url`, UTC ISO-8601 `checked_at`, UUID `lookup_id`. `checked_at` — время завершения lookup, не публикации dependency. SDK публикует structured content/output schema и совместимый text content; ручная MCP serialization не нужна.

Validation/upstream ошибки идут через SDK tool error semantics (`isError`), с безопасной категорией: `invalid_input`, `upstream_timeout`, `upstream_network`, `upstream_http`, `upstream_xml`/`upstream_response`. Ожидаемые upstream ошибки преобразуются в `ToolError` с коротким сообщением и lookup id, без stack trace. Normal statuses не получают техническую ошибку в поле `versions`.

`lookup_id` создаётся перед upstream попыткой. Небольшой JSON log по завершении/ошибке содержит id, координаты, URL, время/elapsed, HTTP status при наличии, outcome и count при успехе. Validation без HTTP не создаёт ложный upstream completion log. Не логируем ключи, пользовательские prompts и весь XML. БД и tracing не нужны: для live достаточно найти event по возвращённому id. Такой лог коррелирует наблюдаемую попытку; при network error он не доказывает получение запроса самим Google.

### 4. Изолированный Day 17 provider возвращает всю операцию

Добавляем небольшой Day 17 module с transport DTO, route, service и provider, вызывающим `AsyncOpenAI.responses.create()` напрямую. Никаких subclass hooks с mutable `last_response`, расширения `LlmClient` или потери MCP items через `SimpleAgent.generate()`. Повторно используем существующие инфраструктурные conventions и чистые helpers только если они не нормализуют away evidence.

Предлагаемый route: `POST /api/v1/mcp-tool-lab/run`, body `{prompt, mode}` (`forced`/`auto`). `DAY17_MCP_SERVER_URL` задаётся только в backend environment и проверяется как public HTTPS `/mcp`; произвольный endpoint из Android не принимается. Отсутствие конфигурации проверяется при Day 17 operation, не ломает startup других Days. `OPENAI_API_KEY` остаётся на backend. Lifecycle закрывает выделенный provider client.

Payload: прежний model alias `gpt-5.6`, `reasoning.effort="none"`, `store=false`, non-streaming; MCP definition `type="mcp"`, `server_label="android_dependencies"`, configured `server_url`, `allowed_tools=["get_google_maven_versions"]`, `require_approval="never"`. Forced choice: `{"type":"mcp","server_label":"android_dependencies","name":"get_google_maven_versions"}`; auto choice: `"auto"`. Инструкция просит использовать фактический результат и сообщать ошибки/отсутствие lookup без догадок. Prompt не подменяется координатами на backend. Один SDK request, `max_retries=0`, отдельный 75-секундный deadline и конечный output budget (1200 tokens). При incomplete сохраняем evidence, не повторяем generation. Старые timeouts не меняем.

Typed operation result включает operation id, снимок submitted prompt/mode, configured MCP server, provider response status/id, final text при наличии, реальные MCP output items, imported tools, per-call parsed evidence и вычисленный outcome. Immutable/per-request data формируются из полученного response до возврата route. Нет глобального накопителя evidence; две конкурентные операции из разных клиентов независимы.

Извлечение идёт по всему `response.output` до обработки incomplete/refusal, сохраняя `mcp_list_tools` и все `mcp_call` в порядке источника. Исходные arguments/output/error и опциональный status сохраняются; parsed JSON — дополнительное представление. Imported tools выводятся из реальных discovery items, не из allowlist запроса. Ошибка API до response даёт operation error с отсутствующими response/call ids, а не синтетический MCP item. API response с unexpected approval request сохраняется как диагностируемая configuration/protocol проблема без второго request для approval.

Для `mcp_call.output` нужен небольшой явный decoder реально документированного/наблюдённого SDK result envelope: JSON structured result либо SDK text content с таким JSON. Сначала распознаётся tool error envelope, затем валидируется normal result. Не использовать recursive поиск похожих ключей, parsing final prose или угадывание результата из arguments. Неизвестная форма сохраняется raw и получает `invalid_tool_result`; live проверит реальную форму. Parsed result проверяется на совпадение координат с actual arguments и fixed source URL; mismatch виден отдельно. Правильность requested coordinates проверяется в forced live, поскольку конкретные arguments всё равно формирует модель.

### 5. Provider status, invocation и lookup outcome различаются

Сохраняем raw provider fields независимо от собственного summary. Per-call outcome: `found`, один из negative statuses, `tool_error`, `mcp_error` либо `invalid_tool_result`. Ошибки классифицируем только по имеющемуся evidence; нераспознаваемая provider error остаётся `unclassified_error`, не выдуманным upstream timeout.

| Evidence | Краткий operation outcome |
|---|---|
| Конфигурация отсутствует, request не отправлен | `configuration_error` |
| API error/timeout без response | `provider_error`, invocation неизвестен |
| Discovery/transport failure, unexpected approval | `mcp_error`; доступные calls сохраняются |
| Provider incomplete/refused/failed | Соответствующий provider outcome плюс доступные per-call outcomes |
| Completed без calls и без discovery error | `not_called`; forced acceptance не пройден, auto — наблюдение |
| Completed с tool error/невалидным result | `tool_error`/`invalid_tool_result`; успешные соседние calls не скрываются |
| Completed с normal results и final text | `completed`; отдельно показаны все lookup statuses |
| Calls есть, но пригодного final text нет | `model_response_missing`; calls остаются evidence |

Если несколько failure видов сосуществуют, summary отдаёт приоритет provider/discovery failure, затем ошибочным calls; Inspector показывает полный набор. `completed` не является автоматическим verdict, что модель верно использовала данные. Один tool в allowlist не гарантирует ровно один call в одном Responses request; приложение сохраняет все и не обещает exactly-once исполнения remote tool. Не полагаемся на `max_tool_calls` как неподтверждённый лимит MCP calls.

### 6. Android lab показывает одну текущую попытку

Новые DTO/Retrofit repository, ViewModel и Compose screen регистрируются через существующий `AppContainer`/Activity conventions. Используем прежний HTTP client с отключённым connection retry. UI: draft prompt, mode selector, «Отправить», loading, final text, краткий outcome и раскрываемый Inspector. Никаких model settings, чата с памятью или зависимости от Playground state.

Default prompt: «Получи опубликованные версии androidx.core:core-ktx из Google Maven. Укажи количество и три последних элемента в порядке источника. Не оценивай стабильность или совместимость». Это заранее определённый forced acceptance input, а не контракт всех запросов.

При send ViewModel снимает prompt/mode snapshot, заменяет прежний attempt loading-состоянием и блокирует duplicate send. Любой результат/локальная ошибка принадлежит только этому attempt. Черновик можно отличить от submitted snapshot; редактирование не меняет подпись полученного результата. Inspector перечисляет discovery и все calls, отдельно provider status и computed outcome, raw arguments и читабельный result/error, response/call/lookup ids. Raw output доступен внутри деталей, не занимает основной экран.

Activity-scoped Day 17 ViewModel сохраняет работу и state при rotation/возврате в каталог. Ни composition, ни init, ни restored navigation не запускают generation. После process death нет автоматического replay; историю receipts постоянно не храним. Добавляется Day 17 card после Day 15, без искусственного Android destination для CLI Day 16.

### 7. Render разворачивает только MCP service

Используем обычный Git-backed Render deployment из доступного service Git commit. Поэтому после реализации, всех offline checks, scoped diff review и strict validation нужен отдельный pre-live commit/push deployable revision. Это согласованный этап lifecycle Day 17, а не finish-day: OpenSpec change остаётся активным, live/video tasks остаются незавершёнными. Текущая planning-правка сама по себе не запускает commit/push; этап выполняется после отдельного запуска реализации и выполнения его prerequisites. Не добавляем Docker registry, tunnel или другой deployment mechanism ради ограничения одним финальным commit.

Pre-live commit включает только проверенные Day 17 implementation/tests/docs/planning changes; root README уже содержит ссылку дня, а live/video отмечены как ещё не выполненные. Перед commit проверяются scoped working-tree и staged diffs, секреты/local files и `git diff --check`; выполняется обычный push в текущую upstream-ветку без force/amend. Фиксируются полный commit SHA, ветка и результат push. После публикации служебное обновление task checkbox не требует отдельного deployment commit.

Перед live сверяем SHA фактически запущенного Render deployment с опубликованной revision. В evidence каждой попытки сохраняем `deployed_commit_sha`, deployment id/ссылку, endpoint, время и response/call/lookup ids. SHA берём из подтверждённых сведений Render о deployment, а не просто из текущего локального HEAD. Этот metadata хранится в записи эксперимента; он не требует расширять Google Maven tool result или строить tracing platform. Если server code изменён, нужны затронутые checks, новый reviewed commit/push и redeploy до новой попытки; прежняя evidence остаётся привязана к прежнему SHA. Последующий docs/archive commit не переименовывает revision уже выполненного live.

Render Web Service использует root directory `day-17-android-dependency-mcp`, устанавливает его requirements и запускает Uvicorn на `0.0.0.0` / предоставленном `PORT`. Рабочий публичный endpoint — точный HTTPS `/mcp` без redirect на неподходящую схему/path. Отдельный простой `/health` допустим для readiness, но не заменяет `tools/list`.

Transport security включена: разрешены фактический Render hostname и нужные localhost hosts для development; origins задаются явно там, где применимы. Не использовать wildcard всех hosts и не отключать DNS-rebinding protection. Proxy headers/trusted proxy configuration проверяются под Render, чтобы TLS termination не создала ошибочный redirect. Google Maven не требует credentials; OpenAI key на этот service не переносится. MCP endpoint public read-only, без auth framework.

Cold start проверяется/прогревается отдельно до model attempt. Успешный health не доказывает MCP discovery или upstream access. Отказ deployment во время попытки сохраняется как фактический результат; автоматического повторного запроса нет. Другие hosting providers в текущий план не включаются.

### 8. Проверки отделяют код от поведения модели

Offline server tests используют fixtures и mock HTTP transport: registry/schema, validation с нулём HTTP calls, URL, source order, все normal statuses и error categories. Небольшой официальный `Client(server)` integration test проверяет discovery, schema, structured content и SDK error semantics. Отдельно проверяется allowed-host configuration. Никакого OpenAI или реального Google Maven в этих тестах.

Backend tests подставляют SDK Responses fixtures: точный forced/auto payload, allowlist/approval, отсутствие retries, list items, несколько calls, отсутствующие optional fields, structured/error/unparseable outputs, mismatch, incomplete/refusal, zero calls, timeout и независимость двух операций. Они не доказывают live integration.

Android tests покрывают DTO mapping, ViewModel transitions/snapshot/duplicate-send, Inspector outcomes/несколько calls, отсутствие старого evidence после failure, rotation/navigation without replay и root entry. Применяются целевые JVM/UI проверки и затронутые navigation regressions через `scripts/dev.ps1`; не менять инфраструктуру тестирования.

Forced live проводится один раз как явно зафиксированная попытка после readiness: remote `tools/list` подтверждает tool/schema; Android отправляет default prompt; actual call name/arguments сравниваются с `androidx.core:core-ktx`; result сравнивается с output, lookup id — с Render upstream log. Количество и последние три элемента final response проверяются по полученному массиву, без фиксированных ожидаемых версий. Сохраняются подтверждённый `deployed_commit_sha` Render deployment, endpoint/deployment reference, response/call/lookup ids и фактический verdict, включая неудачу. Исправление реальной ошибки допускает новую отдельно обозначенную попытку после изменения; нельзя незаметно повторять неизменный experiment ради желаемого текста. Auto — отдельное необязательное наблюдение с актуальным запросом, `not_called` допустим. Readiness и offline checks не объявляются завершённым Day 17 live.

## Risks / Trade-offs

- [Public endpoint и Render cold start] → конечные timeouts, ограниченный input/body, отдельная readiness перед live; дополнительную auth-инфраструктуру не вводим. Публичный deployment сам по себе не даёт production SLA.
- [Forced choice не фиксирует arguments и число calls] → сверка actual arguments, сохранение каждого call; никакой скрытой подстановки/repair и обещания exactly once.
- [Ответ Google Maven не является рейтингом версий] → source order и точные normal statuses; отсутствуют слова latest/stable как вывод tool.
- [Нативная форма output/error отличается от fixture] → сохранять raw items, явно проверять decoder в live, неизвестную форму не выдавать за успех.
- [Provider timeout скрывает дальнейшую судьбу remote call] → invocation unknown, не `not_called`; отсутствие retry предотвращает повтор со стороны нашего приложения.
- [Final prose может быть неверным при успешном call] → отдельная ручная сверка фактов forced live; UI не объявляет семантическую гарантию модели.
- [Новый SDK имеет собственный dependency graph] → отдельный environment; backend не получает MCP SDK и не меняет общий LlmClient.

## Migration Plan

1. Реализовать standalone MCP server, Day 17 backend и Android lab, подготовить component docs и корневую ссылку на Day README. Прежние Days работают без Day 17 URL; live/video пока не выполнены.
2. Пройти все предусмотренные offline server/backend/Android checks, сохранив конкретные результаты для актуального кода.
3. Выполнить scoped diff review, проверки секретов/local files и strict OpenSpec validation перед live. Подготовить deployable revision без незавершённых изменений, влияющих на server code.
4. Создать отдельный pre-live commit и выполнить обычный push deployable revision в текущую upstream-ветку. Зафиксировать SHA; не объявлять Day 17 завершённым, не архивировать change и не закрывать live/video tasks.
5. Развернуть только MCP service из этой revision на Render, подтвердить фактически deployed SHA, настроить allowed host и проверить HTTPS `/mcp`, readiness/discovery. Задать `DAY17_MCP_SERVER_URL`, проверить доступность backend с эмулятора.
6. Выполнить forced live и сохранить полную evidence-цепочку вместе с deployed SHA. Не выдавать Explore/readiness за acceptance.
7. Отдельно выполнить optional auto experiment или явно записать «не проводился»; при выполнении сохранить собственные evidence и deployed SHA.
8. Записать видео после live и получить явное подтверждение пользователя; pre-live commit и successful deployment не заменяют эту проверку.
9. По отдельному `$finish-day Day 17` актуализировать live evidence/docs и task statuses по фактам, проверить root README и scoped diff, переиспользовать подходящие checks либо повторить затронутые. После выполнения обязательных tasks и strict validation архивировать OpenSpec change штатным workflow. Создать финальный commit/push при наличии последующих изменений, включая docs/evidence/archive; пустой commit не создавать.

Pre-live и finish-day — разные Git checkpoints. Finish-day не требует откладывать публикацию deployable code до видео, а pre-live публикация не даёт оснований завершать день. Финализация/архивирование не включаются в implementation checklist как задачи, которые должны быть выполнены до самого архивирования: это последующий finish-day workflow.

DB migrations нет. Откат — убрать Day 17 регистрацию/карточку и configuration, остановить Render service; прежние day contracts и deployments не требуют миграции. Историю pre-live commit не переписываем; исправления публикуются отдельной revision.

## Open Questions

- Фактический hostname Render определяется при создании service и затем попадает в allowed hosts/backend configuration; архитектуру это не меняет.
- Фактическая обёртка `mcp_call.output` и полнота optional provider status проверяются в первом live; raw evidence сохраняется независимо от поддержки decoder.

Официальные опорные материалы из Explore: [MCP server tools](https://py.sdk.modelcontextprotocol.io/servers/tools/), [deployment](https://py.sdk.modelcontextprotocol.io/run/deploy/), [testing](https://py.sdk.modelcontextprotocol.io/get-started/testing/), [Google Maven repositories](https://developer.android.com/build/remote-repositories), [Responses remote MCP](https://developers.openai.com/api/docs/guides/tools-connectors-mcp), [Render Web Services](https://render.com/docs/web-services). При реализации сверять API с закреплённой версией SDK, не смешивать примеры v1 и v2.
