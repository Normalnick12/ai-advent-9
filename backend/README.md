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
