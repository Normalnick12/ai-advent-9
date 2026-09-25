# Backend

Локальный сервер на Python и FastAPI для Android-приложения AI Advent.
Выполняет запросы к OpenAI, хранит состояние диалогов и экспериментов,
возвращает ответы и метрики. API-ключ используется только на сервере.

- [Android-клиент](../android-app/README.md)
- [Настройка, запуск и проверки](../scripts/README.md)
- [Описание и результаты экспериментов по дням](../README.md#задания)

## Agent Playground — Day 15

`/api/v1/agent-playground/catalog` и `/current` читают настройки и текущее состояние без создания задачи и обращения к модели. POST operations: `create-task`, `complete-setup`, `send`, `events`, `select-profile`, `new-conversation`. Контракты доступны в локальном Swagger UI.

Создание требует reviewed typed configuration: Compact Engineer/Mentor и четыре поля Coding Policy. Policy неизменна для task. Отдельная definition `checkout-v2` использует существующий resolver/CAS и добавляет REQUIREMENTS_REVISION_REQUIRED и VALIDATION_FAILED. Старый `checkout-v1` не изменён. Хранилища Memory, Profile, State, policy и setup находятся в отдельном локальном namespace `agent-playground/day15-v1`.

Send вызывает существующий generate–validate–commit gate с контрактом `coding-turn-v1`. Проверяются четыре decisions и структура answer; semantic correctness текста/кода не гарантируется. Конфигурация модели находится в [playground_coding.py](app/playground_coding.py): `gpt-5.6`, не более одного generation call на Send. В используемом provider client retries отключены.

Lifecycle возвращает `forward_applied`, `recovery_applied`, `rejected` либо отдельный Pause/Resume/technical outcome. Expected rejection имеет HTTP 409 и receipt; technical Send может иметь HTTP 500 с сохранённым receipt. Lifecycle не создаёт conversation pair и не вызывает provider.

Pending setup сохраняет reviewed choices и reserved IDs; после read пользователь явно вызывает complete-setup. При неизвестном результате записи authoritative read согласует conversation/State без replay. Runtime receipts не переживают restart: потерянная диагностика остаётся unavailable. Один локальный worker и общий guard защищают от конкурирующих операций.

Проверки и команды — в [scripts](../scripts/README.md). Live с передачей payload внешнему provider выполняется только после отдельного разрешения пользователя.


## Первый MCP-инструмент — Day 17

`POST /api/v1/mcp-tool-lab/run` принимает `prompt` и `mode` (`forced`/`auto`).
Отдельный service выполняет один native Responses MCP request и возвращает ответ
вместе со всеми MCP items/calls; общий `LlmClient` прежних Days не меняется.
Контракт доступен в Swagger UI. Automatic retries/regeneration отключены.

На backend задайте `DAY17_MCP_SERVER_URL=https://<render-service-host>/mcp`
в локальном игнорируемом `.env` или окружении. `OPENAI_API_KEY` используется только здесь.
Без Day 17 URL остальные Days работают; отправка Day 17 возвращает configuration error.
После изменения environment перезапустите backend через `scripts/dev.ps1 backend`.
MCP server разворачивается отдельно: [Day 17](../day-17-android-dependency-mcp/README.md).

Offline из `backend`: `.venv/Scripts/python.exe -m pytest tests/test_mcp_lab.py tests/test_agent_adapter.py -q`.
Forced live запускается из Android после Render discovery. Specific tool choice фиксирует
имя инструмента, но actual arguments обязательно сверяются. Запишите deployed Render
commit SHA/deployment reference, endpoint, response/call/lookup ids и сопоставление
server log с output. Final prose отдельно не доказывает invocation. Provider timeout
до получения response означает неизвестный факт вызова, а auto без call — `not_called`.

## Фоновые проверки — Day 18

`POST /api/v1/dependency-watch/run`: `operation=create|summary`, `prompt`, для summary
обязателен выбранный `watch_id`. Один Responses request (`gpt-5.6`, forced tool,
`store=false`, `max_retries=0`), без repair/regeneration. Создание не идемпотентно:
все фактические create calls и все подтверждённые IDs возвращаются в evidence.

В backend environment задайте `DAY18_MCP_SERVER_URL=https://<выбранный-hostname>/mcp`
и `DAY18_MCP_TOKEN`. Значение token передаётся штатным полем remote MCP `authorization`
в каждом запросе. Не добавляйте префикс `Bearer ` в значение environment. Token
остаётся только в backend environment и на VPS; Android, prompts, logs и Git его
не получают. Без настроек Day 18 возвращает configuration error; старые Days независимы.
`OPENAI_API_KEY` остаётся на локальном backend, VPS в нём не нуждается.

В `backend/.local/day18/evidence/` сохраняются redacted `.attempt` перед отправкой
и окончательный `.json` с operation snapshot. Отсутствующий terminal response
означает unknown, не отмену create. При недоступном evidence storage запрос не
отправляется. Provider prose сохраняется отдельно от typed receipt/aggregate;
неверный watch ID или контракт помечаются invalid_tool_result без повторного вызова.

Offline: из `backend` выполните `.venv/Scripts/python.exe -m pytest tests/test_dependency_watch.py tests/test_mcp_lab.py -q`.
Deployment, backup и recovery — в [scripts](../scripts/README.md#day-18--dependency-watch).

## Композиция MCP — Day 19

`POST /api/v1/mcp-composition/run` принимает только `{prompt: nonblank string}`
(до 12000 символов). Один native Responses request: `gpt-5.6`, reasoning none,
auto, три tools одного сервера, store=false, max_retries=0. Backend сохраняет
actual arguments и outputs, не составляет аргументы следующих steps.

В backend environment: `DAY19_MCP_SERVER_URL=https://<day19-host>/mcp`,
`DAY19_MCP_TOKEN` без префикса Bearer, `DAY19_MAX_OUTPUT_TOKENS` и
`DAY19_DEADLINE_SECONDS`. Последние два значения выбираются только по pre-live
sizing. Без полной конфигурации операция возвращает not_sent/configuration_error;
старые Days не зависят от этих настроек. `OPENAI_API_KEY` остаётся только на backend.
После настройки запускайте backend через `scripts/dev.ps1 backend` в управляемой
терминальной сессии; `/health` не подтверждает доступность OpenAI.

`backend/.local/day19/evidence/<operation_id>/` содержит предварительный
`attempt.json`, исходный `response.json` со всеми ordered native items и отдельный
`operation.json` (проекция calls/final_text/размеры). При provider error — `error.json`;
timeout означает unknown. При недоступном evidence до dispatch запрос не отправляется.
Секреты редактируются, данные tools не чинятся. Verifier сохраняет вердикт отдельно.

Проверки: из backend `.venv/Scripts/python.exe -m pytest tests/test_mcp_composition.py
tests/test_mcp_lab.py tests/test_dependency_watch.py tests/test_dependency_watch_evidence.py
tests/test_dependency_watch_summary.py tests/test_api.py -q` (одной командой).
CLI, gates и независимое чтение описаны в [scripts](../scripts/README.md#day-19--композиция-mcp).

## Multi-server orchestration — Day 20

`POST /api/v1/mcp-orchestration/run` принимает `{"prompt":"..."}`.
Один streaming Responses request регистрирует DeepWiki и существующий Day 19
Dependency Composition MCP одновременно. Модель выбирает tools и arguments;
Responses runtime вызывает нужный endpoint по descriptor, MCP передаёт schemas,
arguments и results, серверы выполняют свои операции. Backend задаёт возможности,
лимиты и задачу, сохраняет события; он не исполняет свой tool loop и не подставляет
следующий вызов. Offline verifier проверяет наблюдаемые переходы.

Используются `OPENAI_API_KEY`, `DAY19_MCP_SERVER_URL` и `DAY19_MCP_TOKEN`
из окружения backend или локального игнорируемого `.env`. Token не менее 32
символов, URL — существующий публичный HTTPS `/mcp`. Старый Day 19 launcher
использует SSH: **для Day 20 его не запускать**. Без локального token readiness
остаётся незавершённой; требуется заранее предоставить его локально, не в чат.
При подготовке единственной попытки существующий credential восстановили отдельным
разрешённым чтением env через SSH и передали process environment; VPS не менялся.
Остальные Days запускаются без Day 20 конфигурации.

По умолчанию `gpt-5.6`, reasoning `none`, `tool_choice="auto"`, `store=false`,
SDK retries 0, `DAY20_MAX_OUTPUT_TOKENS=32768`, `DAY20_DEADLINE_SECONDS=900`.
Лимиты конечные; выбранный бюджет основан на offline sizing сохранённого Day 19
payload с запасом для двух передач, research и финального ответа, а не на
предварительном исследовании Day 20. Подробности — в
[configuration summary](../day-20-mcp-orchestration/evidence/offline-configuration.json).
Инструмент сохранения не импортируется. Фактические DeepWiki tools по discovery
2026-09-25: `read_wiki_structure`, `read_wiki_contents`, `ask_wiki_question`.
Dependency tools — lookup и summary.

Новый UUID-каталог `backend/.local/day20/<operation-id>/` содержит
`attempt.json` (redacted request), `events.jsonl`, при получении terminal response —
`response.json`, при наличии ответа — `model-answer.txt`, и `operation.json`.
Всё это evidence одной отправки. На timeout/обрыв возможны неполные файлы;
не повторяйте запрос. Verifier создаёт новый `review/report.md` и вспомогательный
`verdict.json`, не меняя исходные файлы. При повторной offline-проверке задайте
другой output directory. Recovery/replay и серверная инспекция не предусмотрены.

Порядок проверяется по native `response.mcp_call.in_progress` и
`response.output_item.done`, а не по позиции элемента в итоговом массиве.
Две ветки связываются по coordinates/lookup_id и полному lookup object.
Summary count, last_three и canonical hash пересчитываются независимо.
Явная координата в research подтверждает наблюдавшееся evidence; истинность
DeepWiki, семантическая роль зависимости и актуальность revision остаются
`NOT_PROVEN`. Членство объявленной версии проверяется только при наличии
наблюдаемой цитаты. Можно вручную сверить исходники после live, но это не
обязательный workflow и не дополнительный model run.

Консоль backend показывает call ids/labels/names по мере получения items.
CLI после завершения выводит читаемый отчёт: задачу, выбранную research capability,
зависимости, переход к Maven, summaries и отдельные verdicts для flow и model facts.
Все дополнительные и ошибочные calls видны. Инструкции — в [scripts](../scripts/README.md).
