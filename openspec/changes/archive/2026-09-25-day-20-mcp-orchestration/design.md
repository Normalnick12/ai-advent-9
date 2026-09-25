## Context

Мотивация — [proposal.md](proposal.md). База exploration: `main` / `457751de874d9d3a3c137670820d57a1233d4d82`, Day 19 архивирован, сохранённая попытка независимо перепроверена без новых calls. Это не проверка текущей доступности remote endpoints.

Day 16 содержит прямой MCP discovery с пагинацией, но не tool invocation через модель. Days 17/19 используют отдельные сервисы backend и native Responses; общий `SimpleAgent`/`LlmClient` в этих путях не участвует. Day 19 уже сохраняет request/response, но задаёт модельный маршрут инструкцией и записывает полный response только после получения. Его verifier привязан к одному server, `core-ktx`, трём calls, серверным журналам и файлу.

Существующий VPS endpoint для этого дня — именно Dependency Composition Day 19, содержащий lookup и summary. Не путать его с однопроцедурным Day 17 endpoint или scheduler Day 18. Его код, конфигурация и tool descriptions остаются black-box. Описание lookup уже рекомендует передавать полный результат summarizer: эксперимент проверяет выбор возможностей по задаче и опубликованным descriptions, а не планирование без подсказок вообще.

## Goals / Non-Goals

**Goals:** один понятный developer-flow, два независимых server descriptors, наблюдаемые переходы данных для двух ролей, краткий локальный отчёт и проверка первой попытки. Design обязателен здесь из-за нового формата multi-server evidence и различия между trace attribution и source truth.

**Non-Goals:** универсальная регистрация произвольных servers, workflow engine/DSL, gateway, Agents SDK migration, автоматический аудит всех зависимостей, проверка совместимости, UI-разработка и серверная наблюдаемость. Source-review workflow, durable attempt/idempotency protocol, recovery/replay, универсальная JSON-валидация и семантический разбор произвольных ответов DeepWiki не строятся.

## Decisions

### 1. Изолированный backend service и простой CLI

Добавить `POST /api/v1/mcp-orchestration/run` с непустым `prompt`, выделенные service/models и минимальную регистрацию в `backend/app/main.py`. CLI в `day-20-mcp-orchestration/` показывает задание, инициирует один локальный POST и выводит путь к сохранённому результату. Отдельная offline-команда проверяет и отображает сохранённую попытку без сети. Backend работает как в предыдущих днях через `scripts/dev.ps1 backend`; нового listener/port не появляется.

Переиспользовать redaction, уникальный локальный каталог попытки, finite budget/deadline и небольшой разбор фактического MCP output. Не переносить весь verifier Day 19 и не выносить попутно общий framework. Контракты существующих endpoints не меняются. Альтернатива с доработкой `LlmClient` затрагивает прошлые Days без пользы для данного результата; standalone CLI с OpenAI credential на клиенте расходится с уже принятой backend-границей.

### 2. Фиксированные два server descriptors вместо registry framework

В каждом запросе одновременно передаются:

| Label | Endpoint/configuration | Allowed tools |
| --- | --- | --- |
| `deepwiki` | `https://mcp.deepwiki.com/mcp`, без auth | `read_wiki_structure`, `read_wiki_contents`, `ask_wiki_question` (фактический tools/list 2026-09-25) |
| `dependency_composition` | существующие server-side `DAY19_MCP_SERVER_URL` и `DAY19_MCP_TOKEN` | `get_google_maven_versions`, `summarize_dependency_versions` |

Сохраняются actual imported definitions и label → URL mapping, не только имена из ожидаемого allowlist. Ключ tool — `(server_label, name)`. `require_approval="never"` ограничено указанными read/research/summary возможностями; `save_dependency_report` не импортируется. Credentials находятся в native authorization, не в model input. Недоступность endpoint останавливает подготовку либо отражается в run, не инициирует ремонт VPS.

Один native request: существующий alias `gpt-5.6`, reasoning none, `tool_choice="auto"`, `store=false`, SDK retries=0, конечные Day 20 output budget/deadline из backend config. Значения выбираются до live по offline sizing двух полных lookup transfers и объёму research; 16384/600 из Day 19 не считаются автоматически достаточными. Никакого поочерёдного переключения allowlist для принуждения маршрута.

Альтернатива с Context7 не даёт необходимого типа информации для проверки публикаций и увеличивает неопределённость. Существующий Dependency MCP не требуется расширять: research делает DeepWiki, публикации/сводки — Dependency MCP, локальное сохранение — приложение.

### 3. Prompt задаёт задачу и результат, а не программу вызовов

Основной пользовательский сценарий:

> Исследуй в android/nowinandroid зависимости для локального хранения данных и фоновой работы/синхронизации. Для каждой задачи выбери один конкретный используемый Maven-артефакт, укажи его роль, координаты, объявленную версию и доступные ссылки на исходники/ревизию. Проверь публикации в Google Maven и подготовь отдельную проверяемую сводку: статус, количество и три последних элемента в порядке источника. Не делай выводов о совместимости или рекомендации обновления; неизвестные сведения обозначь явно.

Краткая системная инструкция просит использовать доступные источники, получить сводки средствами доступных инструментов, сохранять передаваемые данные, не повторять неудачные calls ради repair и не додумывать отсутствующие факты. Формат результата задаётся отдельно от маршрута. Tool names, готовые координаты и команды «сначала X, затем Y» в обеих инструкциях отсутствуют. Сами опубликованные schemas/descriptions tools доступны модели штатно.

Room/WorkManager не входят в expected answer production-кода. Выбор конкретного runtime/ktx артефакта допустим, если он поддержан repository evidence и относится к заданной роли; не требовать единственного заранее выбранного artifact. Две роли требуют двух различимых обоснованных dependency-веток. Дополнительный research с новым вопросом допустим, повтор идентичного lookup/summary для улучшения ответа не скрывается и нарушает no-repair policy. Дубликаты нельзя автоматически свести к последнему успешному call.

### 4. Проверять DAG зависимостей, не ровно N вызовов

```text
DeepWiki evidence A --> lookup A --> summary A --+
                                               +--> engineering result
DeepWiki evidence B --> lookup B --> summary B --+
```

Один DeepWiki output может обеспечивать обе ветки. Исследовательские уточнения допустимы, обязательного structure → contents → question нет. При достаточном одном research ожидаются пять calls; это объяснение длины, не acceptance по числу. Discovery не считается исследовательским tool call.

Ветки сопоставляются по координатам, полному lookup object и `lookup_id`; не по позиции «первый/второй». Для каждого ребра сохраняются ссылки на конкретные output items/events. Для временного PASS требуется завершённый upstream item с output до события начала downstream call. Если события отсутствуют, перекрываются или неоднозначны, не делать вывод из array indices: отсутствующее доказательство — NOT_PROVEN, явно обратный порядок — FAIL. Независимые ветки могут пересекаться.

Это порядок наблюдения Responses runtime. Не сопоставлять clocks разных серверов, не требовать journalctl и не утверждать независимое физическое измерение исполнения. Совпадение координат после research доказывает согласованность trace, но не источник внутренних знаний модели.

### 5. Простой локальный event log

В установленном `openai` SDK есть async streaming интерфейс. Один `responses.create(..., stream=True)` и простой локальный JSONL log позволяют сохранить native discovery, calls/results и доступный lifecycle order. Это один provider request, не client-side tool loop. Если SDK не предоставляет часть нужных событий без существенной перестройки, сохранить доступное и дать соответствующему утверждению NOT_PROVEN; не расширять сервис ради telemetry.

Для запуска создаётся уникальный локальный attempt directory без перезаписи. В нём сохраняются конфигурация без секретов, полученные events и terminal response при наличии, исходный model answer. Verifier отдельно создаёт `verdict.json` и читаемый `report.md`. Ошибка создания каталога завершает запуск; API idempotency, marker/reservation protocol, fsync-гарантии и повторная обработка одного attempt id не нужны.

Timeout, storage error или stream interruption оставляют evidence неполным: использовать доступные полные записи, отметить пробелы и выдавать NOT_PROVEN для недоказуемых утверждений. Не восстанавливать partial JSONL, не делать replay/resume и не разрабатывать исчерпывающую матрицу pre/post-dispatch storage failures. Повторной отправки или repair нет. Секреты исключаются из evidence; отсутствие наблюдения не доказывает отсутствие remote calls. SDK retries=0 не является гарантией отсутствия внутренних retries внешних сервисов.

Выбор streaming нужен для наглядности порядка, а не для crash-safe observability. Альтернатива с одним финальным response допустима как источник фактов при неполном log, но не заменяет отсутствующее доказательство временного порядка.

### 6. Узкий verifier учебного flow

Verifier читает сохранённую попытку без model/MCP/network calls и не импортирует production summary. Его область — семь проверок:

1. В actual request зарегистрированы оба server, native discovery подтверждает доступность их tools.
2. В одном run есть реальные calls обоих labels; атрибуция использует `(server_label, name)`, учитываются фактические errors.
3. Raw DeepWiki output содержит однозначное evidence, согласованное с coordinates соответствующего lookup.
4. Каждый summary получает полный result своего lookup; independently пересчитываются count, last_three и canonical hash по контракту Day 19.
5. Доступный runtime order совместим с research → lookup → summary каждой ветки, без total order между ними.
6. Final model answer проверяется отдельно от tool flow.
7. Все дополнительные, неожиданные и повторные calls остаются видимыми; нельзя выбрать удобную успешную подпоследовательность.

Разбор ограничен фактическим provider format и контрактом Dependency MCP: обычный JSON parsing и при необходимости небольшой локальный adapter для observed envelope. Сохраняются полные lookup fields и порядок versions; malformed/неподдержанный output не получает PASS. Generic normalization, adversarial JSON framework, перебор всех возможных representations и semantic/source parser не нужны.

Для repository → lookup достаточно явных координат в связанном excerpt исходного DeepWiki output с указанием соответствующего call. Одного совпадения разрозненных слов недостаточно; неоднозначность означает NOT_PROVEN. Проверка строится по tool evidence, даже если final answer отсутствует или неверен. Истинность/актуальность repository и revision — отдельное ограничение: если сохранённые данные не позволяют независимо подтвердить их, отчёт прямо показывает NOT_PROVEN. Никаких reviewer records, source-review файлов или production workflow проверки исходников. Документация может предложить необязательное ручное чтение source после live, без отдельной задачи реализации.

Финальный ответ запрашивается как небольшой JSON с двумя branch records: роль, координаты, объявленная версия либо null, доступный repository excerpt/link/revision либо null, lookup_id, status, version_count, last_three и краткое объяснение. Provider call IDs знать модели не требуется. Hash проверяется по tool evidence и не становится центром пользовательского задания. Raw final сохраняется; ошибка его parsing не мешает оценке tools. Членство объявленной версии проверяется по lookup как утверждение относительно наблюдавшегося research, без выдачи заявления DeepWiki за подтверждённую repository truth.

Установленное несовпадение — FAIL, отсутствие достаточного evidence — NOT_PROVEN. Полный terminal response без обязательной ветки — FAIL по полноте; ненаблюдавшийся остаток прерванного run неизвестен. `observed_flow` сводит проверки механизма и сводок (FAIL сильнее NOT_PROVEN сильнее PASS). Рядом отдельно показываются final facts и ограничения source/revision, без общего «всё доказано» и без LLM judge.

### 7. Читаемый результат и одна отдельная попытка

`report.md` и CLI — главный human-facing результат. Они показывают исходную задачу, зачем понадобилось исследование repository, фактически выбранную DeepWiki capability и её evidence, найденные dependencies, зачем понадобился Dependency MCP, последовательность lookup/summary двух веток и инженерный итог. Компактная таблица «роль → координаты → публикации → результат» и ограничения source/revision сопровождаются указанием того, что trace подтверждает независимо; verifier internals остаются вторичными. Числа берутся из проверяемых tool facts, рядом сохраняется исходный model answer и его отдельная оценка. Отчёт, построенный verifier, явно маркируется как отчёт приложения; он не подменяет неудачный ответ модели.

Видео можно объяснить как исследование repository, переключение на registry и получение двух сводок. Для этого достаточно CLI/report, без новой UI, Mermaid renderer или web-dashboard. Сохранение локального отчёта не выдаётся за выбранный моделью MCP save.

Offline fixtures покрывают различные маршруты и сбои без network. После apply, tests и локальной подготовки — отдельный live этап по явному запросу пользователя; approval planning/apply само по себе не запускает live. Readiness ограничена config, storage, импортами и protocol/tools-list обоих endpoints, без выполнения research → lookup → summary заранее. Не репетировать полный flow через внешние сервисы, не выдавать readiness за доказательство вызовов модели. Недоступность endpoint фиксируется как blocker без SSH.

После единственного live можно сколько угодно перечитывать сохранённое evidence и запускать offline verifier, не повторяя модель и tools. Новые verdict files не переписывают исходную попытку. Day README обновляется по фактам, root README получает относительную ссылку при создании Day directory; технические инструкции находятся в backend/scripts README. Commit/push/archive — только отдельный finish workflow.

## Risks / Trade-offs

- DeepWiki впервые вызывается через наш Responses flow → до live проверяются только protocol/discovery, качество ответа не обещается; ошибка остаётся результатом первой попытки.
- DeepWiki индекс старее main или содержит AI-generated ошибку → разделить provenance, соответствие raw output и независимую source truth; не называть неизвестную ревизию текущей.
- Модель выберет мало tools, вычислит сводку сама или ошибётся в coordinates → полный наблюдаемый flow не PASS; не делать prompt всё более директивным через повторные live.
- Два полных массива versions и объёмный research расходуют output/context budget → ограничить задачу двумя артефактами и подобрать конечный бюджет по offline sizing; не резать исходные payload ради PASS.
- API events неполны либо не дают строгой границы времени → порядок NOT_PROVEN; provider trace не равен server logs.
- Текст DeepWiki не позволяет однозначно связать координаты → показать фактический excerpt и NOT_PROVEN, не добавлять semantic parser или reviewer-assessment subsystem.
- Публичный source/tool text может содержать посторонние инструкции → трактовать его как данные, credentials держать вне prompt, allowlist исключает remote write; сохранять фактические неожиданные calls/ошибки.
- Неизвестная текущая готовность Dependency endpoint → проверить штатный доступ перед live; отсутствие доступа не оправдывает новый deployment.

## Migration Plan

Добавить изолированный локальный Day 20 маршрут и CLI; запустить backend стандартным dev script. Серверные миграции, БД и VPS операции не нужны. Старые Days не зависят от Day 20 config. Отключение новой регистрации маршрута возвращает прежнюю локальную функциональность; evidence сохраняется. Реализация, live, финализация — отдельные стадии, этот change пока содержит только план.

## Open Questions

- Фактический объём research/versions и выбранные budget/deadline — определить до live без репетиции flow.
- Какие точные citations/revision вернёт DeepWiki — результат первой попытки, а не основание подменить неизвестное догадкой.

## References

- [Responses remote MCP](https://developers.openai.com/api/docs/guides/tools-connectors-mcp)
- [Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events)
- [DeepWiki MCP tools](https://docs.devin.ai/work-with-devin/deepwiki-mcp)
- [Day 19 service](../../../../backend/app/mcp_composition_service.py), [Day 19 verifier](../../../../day-19-mcp-composition/verify.py), [Day 16 discovery](../../../../day-16-mcp-discovery/main.py)

Официальные страницы проверены в exploration 2026-09-25; наличие async streaming API дополнительно сверено с установленным SDK при подготовке proposal. Это не live verification multi-server run.
