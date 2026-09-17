# Backend

Локальный FastAPI-сервис для Android-приложения. Принимает запросы, обращается
к OpenAI Responses API и возвращает ответы с метриками. Поддерживает управление
форматом и длиной ответа, сравнение prompting-стратегий, значений temperature и моделей.
API-ключ используется только на сервере.

[Day 05](../day-05-model-benchmark/README.md): каталог доступен через
GET /api/v1/model-benchmark/catalog; POST /api/v1/model-benchmark/run принимает
три выбранных model id и возвращает независимую проверку пяти задач и метрики.
Каталог не требует ключа. Запуск делает по одному вызову на слот без retries.

[Day 06 — первый агент](../day-06-first-agent/README.md) добавляет изолированные
диалоги: POST `/api/v1/agent/sessions` с `{}`, POST
`/api/v1/agent/sessions/{session_id}/messages` с `{"message":"текст"}` и DELETE
`/api/v1/agent/sessions/{session_id}`. SimpleAgent передаёт полную историю явно
через отдельный OpenAIResponsesLlmClient. История и фиксированные настройки
остаются на сервере; клиент получает текущий ответ и число завершённых ходов.
[Day 07 — сохранение контекста](../day-07-context-persistence/README.md) развивает
тот же Agent subsystem: SQLite — источник сохранённой истории, AgentSession —
восстановимый снимок в RAM. Успешная пара user/assistant сначала фиксируется
одной транзакцией, затем обновляет RAM; ошибка записи не продвигает историю.
После restart mapping пустой, известный ID лениво восстанавливается из SQLite.
GET `/api/v1/agent/sessions/{session_id}` возвращает только `session_id` и
`history_turn_count`. Create/GET/delete не требуют ключа и не вызывают OpenAI.
Неизвестный ID даёт 404, одновременный turn/GET/delete занятой session — 409.
DELETE сначала надёжно удаляет историю, затем закрывает runtime session;
повторное удаление корректного ID возвращает 204.

Запускайте **один worker**: busy защищает session внутри одного процесса.
Стандартный Python `sqlite3` выполняет короткие синхронные операции в том же
потоке; connection открывается/закрывается в lifespan. Явные BEGIN/COMMIT/ROLLBACK,
foreign keys и обычный rollback journal обеспечивают атомарную запись пары.
База `.local/agent/conversations.sqlite3` находится относительно корня проекта,
независимо от shell cwd; файл и sidecars уже исключены из Git. Первый запуск
создаёт schema. История старого RAM-only процесса Day 06 не переносится.
Restart не очищает SQLite; используйте «Новый диалог» для явного удаления.
Busy, locks и незавершённые запросы не сохраняются. Day 06–08 используют полную
историю без summarization. Семантической памяти, ORM, автоматического TTL
и восстановления UI transcript нет.

## Day 10: независимые context strategies

[Лаборатория Day 10](../day-10-context-strategies/README.md) использует один `SimpleAgent`
с отдельным preparation/commit lifecycle и config `day10-gpt4o-mini-n6-v3`.
Новый store: `.local/context-strategies/day10-gpt4o-mini-n6-v3/experiments.sqlite3`.
Не переносит и не открывает Day 06–09 sessions. Запускать по-прежнему один worker.

Каталог: GET `/api/v1/context-strategies/scenario` возвращает восемь canonical
fixtures с presentation metadata и fixed A/B questions, без таблицы ответов verifier.
Базовый адрес run: `/api/v1/context-strategies/{window|facts|branches}/runs`.

| Операция | Метод и суффикс |
| --- | --- |
| Создать run (только перед первым явным Send) | POST base |
| Прочитать confirmed state / outputs | GET base/{id} |
| Отправить canonical fixture | POST base/{id}/messages |
| Создать checkpoint после шага 6 | POST base/{id}/checkpoint |
| Прочитать facts | GET base/{id}/facts |
| Прочитать принадлежащий run raw message | GET base/{id}/messages/{message_id} |
| Независимая final evaluation | POST base/{id}/evaluations/{A|B} |
| Сбросить весь run | DELETE base/{id} |

Create body: `{"config_version":"day10-gpt4o-mini-n6-v3","scenario_version":"meeting-rooms-v1"}`.
Send дополнительно принимает `expected_revision`, `attempt_id` (новый UUID),
`step_id`, explicit `target` (`root`, `A`, `B`) и точный `message` из каталога.
Checkpoint добавляет только `expected_revision`, evaluation — revision и attempt ID.
Settings/history/facts в request запрещены. Edited fixture отклоняется как
`scenario_not_applicable` до provider calls; подмены текста не происходит.

Window generation/count видят только последние шесть confirmed messages плюс
current user: **stored audit history != active model context**. Facts extractor
получает только JSON `{"current_user":"<exact raw current message>"}`.
Strict extraction schema `facts-v2` содержит scope/key/kind/state/value/evidence,
без op; state — set/cleared. Previous facts не передаются модели. Backend сначала
валидирует весь semantic patch по exact current assertions/type/value/evidence,
затем reducer применяет его к actual previous FactState. Set новой/cleared identity
добавляет значение, другое typed value обновляет запись, identical value сохраняет
прежние kind/evidence/provenance. Clear active создаёт tombstone, repeated clear —
no-op, never-existing clear отклоняет весь patch (`extraction_clear_missing`).
Wrong values и omissions не исправляются. Candidate facts с pair,
step и revision commit-ятся одной короткой SQLite transaction после успешного
ответа. Provider await никогда не держит transaction. Branch prefix хранится
один раз; A/B выбираются explicit target, backend current-branch отсутствует.

Evaluation использует fixed `gpt-4o-mini` strict schema из 11 nullable fields.
Expected values находятся только в verifier. Quality — проверенные требования
N/11, invalid/refused/incomplete — unavailable. Retention измеряет actual sources
перед generation, отдельно от quality. Closed grammar принимает named assertions,
scopes, strict JSON restatements и ACK «Принято.»; неоднозначный prose даёт
`unverifiable_restatement`. Старые значения уступают более поздним user corrections.

A/B outputs сохраняются отдельно; они не меняют conversation revision и не
поступают в источники/extractor. Checkpoint, reads и выбор ветки не вызывают
provider/count. При потерянном HTTP outcome читать state/attempt, не повторять
Send/evaluation автоматически. Runtime receipts содержат actual usage отдельно
от preflight; billing journal отсутствует. После потери Android process полный
расход обозначается неполным, без reconstruction из outputs.

При validation failure Facts backend выводит WARNING `facts_extraction_validation_failed`
с JSON diagnostic: run/client attempt IDs, server attempt ID (prospective user message UUID),
scenario step, exact raw extractor reply, parsed changes после успешной schema validation,
zero-based change index, scope/key, internal reason и прежний public error code.
Для invalid JSON/schema parsed changes и index равны null. Данные остаются в локальном
backend log: не записываются в SQLite, API results или Android. Credentials, headers и
configuration не логируются. Успешная extraction не создаёт этот diagnostic event.
Проверка: `python -m pytest tests/test_fact_extraction_diagnostics.py` (fake provider).

Targeted offline проверка из `backend`:
`python -m pytest tests/test_context_strategies.py tests/test_context_strategies_edges.py tests/test_context_strategies_validation.py`.
Полный regression: `python -m pytest`. Эти команды не запускают живые OpenAI calls.
V3 targeted проверка: `python -m pytest tests/test_fact_reducer.py tests/test_context_strategies_versions.py tests/test_fact_extraction_diagnostics.py`.
Config v3 меняет semantic extraction schema/input/instructions и переносит выбор
state transition в deterministic backend reducer. Scenario meeting-rooms-v1,
evaluation meeting-spec-v1, model/N, fixtures и response/evaluation settings прежние.
Исторические stores:
`.local/context-strategies/day10-gpt4o-mini-n6-v1/experiments.sqlite3` и
`.local/context-strategies/day10-gpt4o-mini-n6-v2/experiments.sqlite3`
не мигрируются, не удаляются и не используются как fallback. V1 Facts остановился
на 3/8 (omission и identity/evidence mix-up), v2 — на 7/8 (replace для новых B
identities, три explicit attempts). Оба failures отклонены без повреждения state;
успешный Window v1 остаётся historical evidence. Подробности — в
[validation](../openspec/changes/archive/2026-09-11-day-10-context-strategies/validation.md).
Финальное сравнение выполнено на новых Window/Facts/Branching v3 runs; live/video
и restart/reset подтверждены пользователем. Window/Facts имеют incomplete token
coverage, поэтому known totals не являются полными затратами. Fake tests проверяют
contracts отдельно от actual live observations в отчёте; один live run не гарантирует
корректность последующей extraction или generation.

## Требования

Python 3.11+, зависимости из [requirements.txt](requirements.txt)
и переменная окружения `OPENAI_API_KEY`. Для общего скрипта запуска нужен PowerShell 7.

## Подготовка

Из корня репозитория в PowerShell 7, один раз:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

Создайте локальный игнорируемый `backend/.env` с `OPENAI_API_KEY`
или задайте эту переменную в терминале. Не сохраняйте ключ в исходниках или Git.

## Запуск

Из корня репозитория:

```powershell
.\scripts\dev.ps1 backend
```

Скрипт использует `backend/.venv`, автоматически загружает `backend/.env`,
если он существует, и не запускает второй сервер на занятом порту `8000`.
Сервер работает в текущем терминале, здесь же доступны логи; остановка — Ctrl+C.
После изменения backend перезапустите его: автоматическая перезагрузка не включена.

В другом терминале выполните `.\scripts\dev.ps1 status` для проверки готовности.
После запуска доступны [Swagger UI](http://127.0.0.1:8000/docs)
и [проверка состояния](http://127.0.0.1:8000/health).
`/health` проверяет FastAPI, но не доступность OpenAI.
Подключение клиента описано в [Android README](../android-app/README.md),
работа с процессами и диагностика — в [окружении Windows](../scripts/README.md).

## Тесты

Из папки `backend` с активированным окружением:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Persistence-тесты открывают отдельные реальные SQLite-файлы в `tmp_path`,
закрывают старые store/manager и восстанавливают history новым экземпляром.
Пользовательская `.local` БД в pytest не открывается. Fake LLM проверяет точный
контекст U1/A1/U2; fault injection проверяет rollback и ошибки commit.
Живой restart обоих процессов проверяется отдельно, после завершённого ответа;
потеря HTTP-ответа или crash посреди неопределённого turn вне гарантии Day 07.


## Day 08 — токены

`/api/v1/token-lab/sessions` предоставляет отдельные create/GET/delete и
`/{id}/messages` с тем же message limit 20000. Day 08 использует второй instance
того же SimpleAgent: immutable `day08-gpt4o-mini-v1`, `gpt-4o-mini`,
reasoning omitted, output budget 1200, Standard tier, truncation disabled.
Отдельный manager и файл
`.local/token-lab/day08-gpt4o-mini-v1/conversations.sqlite3` используют прежнюю
schema sessions/messages. Одинаковые resolved DB paths блокируют startup.
Identity — namespace + UUID; чужие get/send/prepare/execute дают 404, cross-delete
безопасен. Metadata lifecycle не вызывает OpenAI. SQLite не хранит tokens/cost.

Normal Send выполняет current-only count, history-only count (пустая history=0
без запроса), full count с instructions, затем максимум одну generation.
Counts относятся к одному immutable snapshot до commit и неаддитивны.
Основная context utilization — full preflight/128000; reserve 1200 показывается
отдельно. Timeout count: 15 секунд, connect 5; normal preflight deadline 45,
generation deadline 75. SDK/application retries=0. Существующие Day 06/07
не выполняют count calls и сохраняют прежние generation payload/HTTP DTO.

Result возвращает outcome/attempt ID, committed count, diagnostics, nullable
usage/model/tier и estimated cost. Ни history, ни instructions не возвращаются.
Pricing использует Decimal и actual input/cached/output по rates
0.15/0.075/0.60 USD/MTok, проверенным 2026-09-09; источник приходит в response.
Reasoning входит в output, cache writes без отдельной надбавки.
Unknown model/tier, missing или inconsistent usage дают unavailable; pricing
failure не отменяет пригодный completed turn. Day 05 pricing не изменён.

`POST /{id}/overflow/prepare` с `{}` выполняет только counts: максимум четыре
full probes к target 140000, accepted 132000–160000, полный JSON <=2 MiB.
Это resource cap, не model limit. Рецепт/образцы/digest/размеры видны клиенту;
standalone current/history для probe не считаются. Подготовка хранится только
в RAM 10 минут, одна на session, максимум 16. Новый prepare, успешный normal
commit/reset или restart инвалидирует старое разрешение.

`POST /{id}/overflow/execute` принимает только
`{"preparation_id":"…","confirm":true}` после отдельного подтверждения.
Session/history/config/digest/expiry проверяются, ID потребляется до generation.
Probe никогда не commit'ится, даже при unexpected provider acceptance.
Только structured generation `context_length_exceeded` считается доказательством
переполнения; count rejection, 400 без этого code, 413/429/timeout — другие исходы.
Не повторяйте execute после unknown response: проверьте доступность/count через
GET, затем обычный turn допустим; это не подтверждение отсутствия расходов.

[Фактический provider-count smoke](../openspec/changes/archive/2026-09-09-day-08-token-lab/provider-count-smoke.md)
сохраняет первоначальный failed baseline, transient timeout и успешную проверку
новой схемы. Offline pytest использует mocks и временные SQLite-файлы, а не
платную generation. Реальный short/long/overflow acceptance выполняется отдельно
из Android; один live overflow требует отдельного явного подтверждения.

## Day 09 — сжатие истории

[Day 09](../day-09-history-compression/README.md) использует тот же SimpleAgent
с RollingSummaryContextPolicy. Default FullHistoryContextPolicy сохраняет
payloads, counts и HTTP contracts Day 06–08. Raw SQLite history остаётся полным
источником: summary меняет только LLM context.

Namespace `/api/v1/compression-lab/sessions`:

| Метод / suffix | Назначение |
| --- | --- |
| POST / с `{}` | Создать пустой диалог |
| GET /{id} | ID, confirmed turn count, config version и summary metadata |
| GET /{id}/summary | Прочитать текущую durable summary |
| DELETE /{id} | Атомарно удалить session, raw messages и summary |
| POST /{id}/messages с `{"message":"…"}` | Один normal turn |
| POST /{id}/compare с `{"question":"…","scenario_id":"three-facts-v1"}` | Явный scored compare; scenario_id можно опустить для сравнения без оценки |

Поля history/config/model не принимаются. Input limit — 20000 символов.
Metadata операции не вызывают OpenAI. Ошибки isolation/busy/validation —
404/409/422; corruption/version mismatch — явная безопасная ошибка без repair.
Отдельный файл
`.local/compression-lab/day09-gpt4o-mini-tail4-v1/conversations.sqlite3`
содержит прежние sessions/messages и таблицу conversation_summaries:
session_id, summary_text, covered_through_position, config_version.
Все три resolved DB paths должны различаться; по-прежнему нужен один worker.

Перед turn политика сохраняет summary всей confirmed части старше последних
4 сообщений (двух полных пар). Она использует предыдущую summary и только
новые eligible messages, без current user. Boundary — inclusive zero-based
position последнего assistant в covered prefix. Synthetic assistant message
с data-only marker стоит перед raw tail; в raw историю он не попадает.
Summary save — отдельная короткая транзакция после LLM await. Неудача summary
или save блокирует ответ; successful summary commit сохраняется даже при
последующей ошибке count, generation или atomic raw pair commit.

Normal response отправляет только COMPRESSED. FULL — counterfactual provider
count с теми же instructions/history/current; превышение FULL window не
блокирует допустимый COMPRESSED. Signed delta не обрезается. Standalone summary
count включает оформление synthetic message, без base instructions; эти
измерения неаддитивны. Отрицательная delta означает дополнительный расход.

Обе generation configs фиксированы: gpt-4o-mini, Standard tier, truncation
disabled, reasoning omitted; response budget 1200, summary budget 384.
Summarizer стремится к короткому тексту, но target не гарантирован; retries нет.
На операцию — deadline 210s; count — прежние 15s/connect 5s, preflight 45s,
отдельная generation — 75s. Ответ операции сохраняет известные phase receipts:
input/output/cache usage, estimated cost, latency, outcome. Unavailable не
подменяется нулём. Rates/actual usage используют Day 08 pricing.
Backend не накапливает расходы и не хранит billing journal.

Compare фиксирует один immutable snapshot. При необходимости готовится локальная
catch-up summary без SQLite save; затем FULL/COMPRESSED count→generation ветки
работают параллельно и независимо. Question/replies/local summary не commit'ятся;
partial failure не стирает второй результат. Deadline отменяет незавершённые
calls без replay. Scored compare до платных calls проверяет точные четыре
учебных user messages и отсутствие ORBIT-7319/standalone 37 в последних
четырёх raw messages обеих ролей. Загрязнённый tail даёт scenario_not_applicable.
Verifier оценивает только named fields identifier/limit/responsible, 137 != 37.

Offline проверки: `python -m pytest tests/test_compression.py` и полный
`python -m pytest` из backend. Используются fake clients и временные реальные
SQLite files. Counts и фактическое сохранение трёх фактов одного ручного прогона
зафиксированы в Day 09 README вместе с actual usage/estimated cost итогового
compare (FULL 2/3, COMPRESSED 1/3). Отдельные maintenance usage/cost подтверждены
пользователем; их численные значения не переданы, net экономия не заявляется. Четырёх-turn
recipe и acceptance описаны в
[OpenSpec design](../openspec/changes/archive/2026-09-10-day-09-history-compression/design.md).
Для restart-проверки дождитесь завершённого turn, перезапустите backend и
force-stop/reopen Android без очистки данных: GET восстанавливает ID/count/summary,
не вызывает paid repair и не возвращает старые UI bubbles/runtime observations.

Ручной restart Day 09 подтвердил восстановление session/count=4 без paid replay.
Пользователь также подтвердил чтение durable summary после restart и успешный
reset: старый диалог после сброса не восстанавливается.

## Day 11 — Memory Layers

Day 11 переиспользует `SimpleAgent`, `AgentSessionManager`, `ConversationStore`
и существующий `LlmClient`. `MemoryExperimentService` отвечает за explicit writes,
lifecycle и snapshots, а `MemoryContextPolicy` — за выбор данных. Здесь
conversation → Short-term, task → Working, owner → Long-term.

Отдельный файл `.local/memory-layers/day11-v1/memory.sqlite3` содержит raw
sessions/messages, `working_memory`, `long_term_memory`, `session_tasks`,
`memory_owners` и `memory_bindings`. Таблицы прежних Day не мигрируются.
Требуется один backend worker. Все resolved database paths должны
различаться. Startup создаёт schema, но не owner/task/session: для этого
нужен explicit Initialize. Restore читает durable binding и слои без provider.
Несовместимая schema или повреждённые данные дают ошибку без автоматического repair.

API prefix: `/api/v1/memory-layers`.

| Операция | Endpoint | Данные |
| --- | --- | --- |
| Read-only сценарий / состояние | GET `/scenario`, GET `/current` | Без identities от клиента |
| Idempotent Initialize | POST `/initialize` | `{}` |
| Explicit запись | POST `/memory` | `snapshot_id, layer, key, operation`; для set ещё `value` |
| Lifecycle | POST `/lifecycle/new-conversation`, `new-task`, `clear-long-term` | `snapshot_id` |
| Обычный committed turn | POST `/messages` | `snapshot_id, message` |
| Side-effect-free probe | POST `/verify/A` … `/verify/E` | `snapshot_id` |

Allowlist: WORKING — `task/current_architecture/release_marker`;
LONG_TERM — `project_code/preferred_architecture`. Значения — непустые строки
до 256 символов; remove передаётся без value. Null, лишние ключи и неизвестные
layers отклоняются. Chat не извлекает structured memory. Stale snapshot и busy
отклоняются без replay. После неизвестного HTTP outcome клиент только читает
current; повторный вызов требует явного действия.

New Conversation сохраняет current task и Long-term; New Task создаёт task
и session, сохраняя Long-term. Прежние rows остаются inactive. Изменения identities
проходят в одной SQLite transaction; runtime session загружается только после
commit. Clear Long-term не меняет Short/Working/IDs.

Provider input: два data-блока Long-term/Working, Full History только активной
session, один current query. Если задан Working.current_architecture, сохранённый
Long-term.preferred_architecture исключается из data-блока. Diagnostics с причиной
`working_override`, inactive refs и прошлые результаты в provider input не идут.
Normal Send использует `run_turn`, probe — `generate` без commit.
Модель: gpt-4o-mini, Standard tier, max_output_tokens=1200, truncation disabled,
reasoning omitted. Проверка использует strict JSON schema: пять nullable exact
fields и свободный `next_step`. Oracle не передаётся модели.

Две метрики независимы: input availability/absence/conflict и output exact/null.
Неверный ответ при корректном input — ошибка использования данных моделью.
Runtime observations содержат immutable stored/selection/request/response
snapshot; SQLite не хранит dashboard. Полный A–E проход: один seed до structured
writes и пять probes, максимум шесть generation calls; maintenance/count calls нет.

Детерминированные проверки из `backend`:
`python -m pytest tests/test_memory_layers.py -q`; regression — `python -m pytest -q`.
Используются временные SQLite и recording clients, без OpenAI. Ручной сценарий
и restart на A-state описаны в [Android README](../android-app/README.md#day-11-memory-layers).

Для запуска предпочтителен `pwsh -File scripts/dev.ps1 backend` из корня,
готовность проверяется `pwsh -File scripts/dev.ps1 status`. При недоступном
pwsh/ExecutionPolicy из `backend` в существующем Python-окружении:
`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
В fallback `OPENAI_API_KEY` должен быть доступен процессу через окружение;
при необходимости загрузите локальный `.env` штатным способом проекта.
`/health` и чтение памяти проверяют backend, а не OpenAI.
Исправление PowerShell/dev tooling в scope Day 11 не входит.

## Day 12: Personalization

Profile хранится отдельно от Long-term: `AgentProfile`, `ProfileStore`,
`SQLiteProfileStore` и pure `render_profile` не зависят от Memory namespace,
OpenAI SDK или experiment fixtures. `name` — metadata, не instructions.
Create не активирует профиль; edit/select проверяют ожидаемые revisions до no-op.
Explanation flags совместимы: базовый Android/Kotlin предполагается известным,
новые специальные термины можно объяснять. Generic prompt/JSON editor отсутствует.

Два adapter files: `backend/.local/personalization/day12-v1/memory.sqlite3`
и `profiles.sqlite3`. Все семь paths в composition root различаются. Layout
заменяем без изменения Profile API; schema проверяется при reopen без repair.
Single-worker coordinator держит общий operation guard во время snapshot + await,
но SQL transaction заканчивается до вызова provider. Stale/busy отклоняются;
известный pre-dispatch отказ помечается `not_dispatched`, неизвестный исход —
`unknown`. Клиент перечитывает state, запрос автоматически не повторяется.

API prefix: `/api/v1/profile-personalization`.

| Операция | Endpoint |
| --- | --- |
| Current / scenario / profiles | GET `/current`, `/scenario`, `/profiles`, `/profiles/{id}` |
| Initialize | POST `/initialize` с `{}` |
| Create | POST `/profiles`: owner_id, fields |
| Edit | PUT `/profiles/{id}`: owner_id, fields, expected_revision |
| Select | POST `/profiles/{id}/select`: owner_id, expected_profile_revision, expected_binding_revision |
| Memory / lifecycle | POST `/memory`, `/lifecycle/{action}` — Day 11 typed bodies |
| Seed / ordinary Send | POST `/seed`, `/messages` |
| Freeze / side-effect-free probe | POST `/freeze`, `/probe` |

Seed/Send/Freeze/probe принимают snapshot_id, profile_id, profile_revision,
binding_revision; Send добавляет message, Freeze — A/B IDs/revisions, probe —
comparison_id и slot. History, instructions и provider settings не приходят от UI.
Read/startup не создаёт identities и не вызывает модель. New Conversation/New Task/
Clear Long-term сохраняют Profile; Switch/edit сохраняют все Memory IDs, layers,
revision и hash. Runtime comparison и receipts не восстанавливаются как measurements.

Request: fixed neutral base + typed profile renderer в `AgentConfig.instructions`,
Day 11 memory selection/policy + history + query в messages. Working MVI исключает
Long-term MVVM из active input. `SimpleAgent.run_turn` коммитит ordinary completed
pair; `generate` выполняет probe без commit. Actual LlmClient arguments копируются
на dispatch boundary; inspector не пересобирает preview задним числом.

Фиксированные settings: gpt-4o-mini, Standard tier, output budget 2000,
truncation disabled, reasoning omitted, без text_format/Structured Output и retry.
Ответ — natural Markdown. Раздельные checks: selection/revisions, assembly,
adherence и literal memory mentions; human notes не попадают в запрос.
Failed/refused/incomplete дают unavailable output checks, не нулевой score.
Completed ответ сохраняется даже при нарушении формата: checks не являются commit gate.

Markdown checks: H2 heading/порядок/непустые sections, число ordered/unordered,
включая nested list items. Backtick/tilde fences исключаются из parsing структуры,
code может быть содержимым example section. `no_emoji` проверяет весь raw reply
только по набору `day12-common-v1`: U+1F600–1F64F, U+1F44D, U+1F44E, U+1F680,
U+1F4A1, U+2705, U+274C, U+26A0, U+2728, U+2764. Это ограниченный detector,
не Unicode Emoji compliance; отсутствие остальных emoji не гарантируется.
ORION-17/RC-42/Checkout/MVI — literal mentions, не оценка семантики MVI.

Проверки из backend: `python -m pytest tests/test_profiles.py tests/test_personalization.py tests/test_personalization_boundaries.py tests/test_memory_layers.py -q`.
Полная regression: `python -m pytest -q`. Live запускается отдельно по общему
[scripts guidance](../scripts/README.md); preferred `scripts/dev.ps1 backend`,
при недоступном pwsh/ExecutionPolicy допустим существующий uvicorn fallback выше.
Исправление PowerShell/tooling в Day 12 не входит.

State Machine/Invariants/validation-before-commit отложены. Будущее orchestration
использует generate → validate → commit → state transition; вызывать validate
после нынешнего run_turn уже поздно. Сам run_turn в Day 12 не изменён.

## Day 13 — Task State Machine

Day 13 использует существующие SimpleAgent/run_turn/generate и Memory/Profile,
добавляя независимые task-scoped FSM/store/renderer. Canonical state:
`task_id, machine_id, state_id, status, revision`; остальные поля выводятся из
versioned definition `checkout-v1`. Progress — только explicit event. Обычный
Send, включая PAUSED, не меняет State. `VALIDATION_CONFIRMED` — подтверждение
пользователя/application, не результат semantic Validator.

SQLite adapter хранит current state и CAS revision без transition history.
Namespace `backend/.local/task-state/day13-v1/` содержит `memory.sqlite3`,
`profiles.sqlite3`, `task-state.sqlite3`. Это layout лаборатории, не domain
архитектура будущего Runtime; TaskStateStore не знает пути остальных stores.
Single-worker application guard не удерживает SQL transaction на provider await.
Conversation commit и State transition не атомарны и остаются отдельными действиями.

API prefix: `/api/v1/task-state`.

| Операция | Endpoint / body |
| --- | --- |
| Read / fixture | GET `/current`, `/scenario` |
| Initialize Memory + State | POST `/initialize`: `{}` |
| Завершить partial State setup | POST `/initialize-state`: snapshot_id, task_id, machine_id |
| Profile create/edit/select | POST `/profiles`, PUT `/profiles/{id}`, POST `/profiles/{id}/select` — typed Day12 fields/revisions |
| Working / lifecycle | POST `/memory`, `/lifecycle/{action}` — Day11 typed bodies |
| Explicit event, включая PAUSE/RESUME | POST `/events`: snapshot_id, task_id, state_revision, event |
| Ordinary Send | POST `/messages`: snapshot_id, task_id, state_revision, profile_id, profile_revision, binding_revision, message |
| Current non-committing probe | POST `/probe`: те же references без message |

Read/startup не создаёт task records. Partial setup между stores виден в readiness:
Memory/Profile/State должны быть готовы для Send/events. `initialize-state`
завершает подготовку current task, не создаёт новую и не сбрасывает существующую.
После unknown outcome — read/reconcile; mutations и generation не повторяются.
New Conversation оставляет task/Working/Profile/State, New Task создаёт initial
State, старые task rows и conversations сохраняются.

Pure preparation получает resolved snapshots: neutral base + Profile section +
authoritative Task State section в instructions, selected Memory + active transcript
+ query в messages. IDs/revisions остаются receipt metadata. Inspector сохраняет
actual LlmClient arguments и разделяет storage/selection/assembly/model adherence.
Preview не является actual evidence. PAUSED semantic violation не блокирует commit;
LLM никогда не применяет events. Invariants/Validator/retry/Playground отложены.

Offline: из backend `python -m pytest tests/test_task_state.py tests/test_task_state_lab.py tests/test_task_state_boundaries.py -q`.
Live запускается отдельно: preferred `pwsh -File scripts/dev.ps1 backend`, затем
`status` и проверка HTTP с эмулятора. Если pwsh/ExecutionPolicy недоступны,
из backend допустим `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
Исправление PowerShell/tooling не входит в Day13.

Ручной HTTP acceptance runner (из backend):
`python scripts/day13_live.py --output ../.local/day13/live.json`.
Он требует свежий Day13 namespace, выполняет explicit fixture setup и ровно три
Send: execution → Pause → New Conversation → status → New Conversation → Resume
→ continuation. Затем отдельный IMPLEMENTATION_READY. Не очищает старые данные,
останавливается при ошибке, не повторяет calls. Existing tasks проходятся теми же
явными controls в UI. Проверки input/State/call budget автоматические; смысл ответа
оценивается отдельно. Local JSON содержит реальные requests/outcomes без headers
и ключей, не попадает в Git. Reopen проверяется offline, а не обязательным live restart.

## Day 14 — Invariants

Изолированная лаборатория `/api/v1/invariants` использует namespace
`backend/.local/invariants/day14-v1/`: Memory, Profile, Task State и отдельный
immutable task policy store. Read/open не создаёт task records и не вызывает модель.
`GET /scenario` возвращает fixture и два controlled action IDs. `GET /current`
возвращает источники, readiness, recovery и applicability.

Явная подготовка: `POST /initialize {}`, затем `POST /setup` с `task_id` и
`snapshot_id` текущей Memory. Setup дополняет отсутствующие Working/Profile/State/policy
на тех же IDs; конфликтующие значения не перезаписывает. В Working записываются
Checkout loading/error/success, MVI и RC-42; Profile — Compact Engineer;
policy coding-v1 — MVI, Compose, CoroutinesFlow и обязательное подтверждение оплаты.
`POST /events` принимает task/snapshot/state_revision/event. Подтвердите
REQUIREMENTS_READY, затем PLAN_APPROVED. Proposals доступны только в ACTIVE execution.

`POST /proposals`: task_id, snapshot_id, session_id, state_revision, profile_id,
profile_revision, binding_revision, policy_id, policy_version, policy_snapshot_id,
action_id. Допустимы `compatible-retry` и `conflicting-stack`; свободный intent,
instructions и неизвестные поля не принимаются. Source references проверяются до dispatch.
`POST /lifecycle/new-conversation` и `new-task` принимают task_id/snapshot_id.
Новая conversation сохраняет policy; новая task получает initial State, но требует
отдельного setup новой policy. Старые записи остаются вне active selection.

| Исход | Provider calls | Conversation |
| --- | --- | --- |
| Compatible typed candidate | 1 | user + trusted answer после validator |
| Controlled request conflict | 0 | user + deterministic refusal |
| Нарушение в parsed candidate | 1 | user + safe refusal, raw candidate не сохраняется |
| Configuration inconsistency | 0 | operation error, без пары |
| Parser/validator/renderer/provider failure | 0 или 1 | technical error, без semantic refusal |
| Ошибка pair commit | 0 или 1 | failed/unknown; authoritative reread, без replay |

Coordinator удерживает session guard, проверяет captured history и выполняет ровно
один atomic pair commit после acceptance gate. При storage uncertainty перечитывается
durable history и заменяется cache только Day 14; failed recovery блокирует новые
turns. State/events, Working, Long-term, Profile и policy не изменяются от ответа.

Reusable core получает уже parsed candidate и injected predicates/renderers.
OpenAI Structured Output и strict JSON parsing находятся в coding candidate adapter.
Policy — typed code, без field/operator/value DSL. Четыре конкретных predicates
проверяют decisions; произвольный код не анализируется. Prevention в instructions
не заменяет enforcement. Старые FSM/Profile и domain leakage TaskStateRenderer
не переработаны; integrated Playground и optional LLM reviewer остаются будущими задачами.

Настройки: gpt-4o-mini, max_output_tokens=1200, Standard tier, truncation disabled,
reasoning omitted, строгая CodingProposal schema, store=false, без automatic retries.
Receipt разделяет actual input, provider outcome/usage, parsed/raw candidate,
precheck/validation, decision и commit. Controlled conflict не имеет actual input.
Technical proposal response может иметь HTTP 500 и сохранённый observation —
его нельзя терять. Current preview не заменяет историческое evidence.
Raw candidate доступен только в diagnostics, не Short-term.

Offline из backend:
`python -m pytest tests/test_invariants.py tests/test_invariants_lab.py tests/test_invariants_boundaries.py tests/test_validated_turn.py -q`.
Общая regression: `python -m pytest -q`.

Для live preferred path: `pwsh -File scripts/dev.ps1 backend`, затем `status`.
При недоступном pwsh/ExecutionPolicy из backend:
`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
Readiness допускает прямой HTTP `/health` и `/api/v1/invariants/current`;
отдельно проверьте доступ с emulator. Исправление PowerShell не входит в Day 14.

Bounded live runner из backend:
`python scripts/day14_live.py --output ../.local/day14/live.json --approved-payload ../.local/day14/payload-preview.json`.
`--approved-payload` указывает заранее просмотренный локальный JSON с полями
`destination` и `payload`. Runner сверяет полное равенство с подготовленным запросом
до dispatch и с actual capture после ответа; SHA-256 файла сохраняется в evidence.
Файл evidence резервирует единственную попытку до HTTP и не перезаписывается.
Он требует свежий namespace, не сбрасывает данные, делает одну compatible generation
и controlled conflict (0 calls), сохраняет каждую операцию без headers/ключей.
Ошибки и нарушения сохраняются как факты; happy path подтверждается только accepted
и committed outcome. Не повторять ради успешного ответа. Runtime receipts исчезают
после restart; SQLite sources/history сохраняются.
