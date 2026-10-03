# Backend

Локальный сервер на Python и FastAPI для Android-приложения AI Advent.
Выполняет запросы к OpenAI, хранит состояние диалогов и экспериментов,
возвращает ответы и метрики. API-ключ используется только на сервере.

- [Android-клиент](../android-app/README.md)
- [Настройка, запуск и проверки](../scripts/README.md)
- [Описание и результаты экспериментов по дням](../README.md#задания)

## Day 25 — Stateful RAG mini-chat

`/api/v1/day25/sessions` — отдельный namespace: POST `{}` создаёт session (201),
GET `/{id}` читает authoritative snapshot, POST `/{id}/messages` принимает
`{message, expected_revision}`, DELETE `/{id}` возвращает 204, в том числе повторно.
GET/send неизвестного ID — 404; busy/stale revision — 409; invalid request — 422.
Snapshot содержит session_id, revision/history_turn_count, memory, history и turns
с сохранёнными grounded results. Android хранит только current ID; create/read/delete
не вызывают OpenAI. Store — ignored `backend/.local/day25/chat.sqlite3`.

Полная durable history отличается от model input: последние три подтверждённые
пары + отдельно Task Memory + исходный question + текущие Top-5 chunks. Memory
содержит только extractive user goal/constraints/terms/clarifications с literal
quote provenance (turn и Unicode offsets). Она не является summary или базой знаний.
Технический retrieval query сериализует current message, pre-turn memory и previous
recent user; patch влияет на search со следующего turn. Индекс Day 21/22 pinned,
text-embedding-3-small/1536, cosine Top-5, gate best>=0.50, без Day 23 rewrite/filter.

Один query embedding и максимум один Responses generation `gpt-5.6` на turn.
Strict combined response содержит `grounded` Day 24 и proposed `memory_update`.
Оба payload валидируются независимо; invalid любого исключает commit всей пары.
Atomic commit сохраняет pair, grounded metadata, memory и revision. Runtime gate
abstention и valid model insufficient_context сохраняются с пустыми sources/citations,
но memory не обновляют; skipped reason виден клиенту. Refused/incomplete/technical
failure не является successful turn. Unknown storage/transport outcome требует
reread; automatic retry/repair/extraction/counting/judge отсутствуют.

Sources/citations проверяются относительно actual sent chunks; quote <=400 символов
должна быть literal substring. Это проверяет provenance/exactness, не semantic support.
Day25ChatService общий для FastAPI и CLI. Runner сохраняет отдельные scenario DB,
pre-dispatch/raw-output checkpoints и manual review в ignored `.local/day25`.
Два frozen scripts по 6 user turns проверяют U6 после исключения U1/U2; после T3
store/service переоткрываются. Это reopen check, не доказательство OS crash recovery.
Наличие памяти в input не доказывает её единственную причинную роль без ablation.

Команды run и keyless saved report — в [scripts](../scripts/README.md).

## Day 24 — Проверяемые RAG-ответы

`scripts/day24_rag.py` — isolated CLI без FastAPI/Android. Он проверяет frozen
Day 22 baseline `f7b78426-9672-437f-ab93-717a826934da`, original-query vectors и
pinned Day 21 index, локально повторяет все десять cosine Top-5 и требует точного
совпадения hits/scores до generation. Новых embeddings/rewrite нет; старые
результаты не меняются. Ошибка index/replay — technical failure, не abstention.

Gate использует неокруглённый best_score >= 0.50. При PASS отправляется полный
Top-5 с source/section/full chunk_id/text, без scores и eval labels. Responses
`gpt-5.6`, reasoning none, strict JSON Schema, output budget 3000, truncation disabled,
store=false; prompt требует краткий русский ответ и дословные цитаты <=400 символов.
Model output содержит только status, answer, sources [{source, section, chunk_id}]
и citations [{chunk_id, quote}]. У answered все три содержательные части непусты;
у insufficient_context оба массива пусты и используется фиксированный ответ:
«Не знаю ответа на основании текущей базы знаний. Уточните вопрос или укажите нужный документ.»

Runtime сверяет membership в actual model context, точные metadata, равенство
source/citation chunk sets, отсутствие duplicate source IDs/citation pairs и
literal substring quote без изменения whitespace/case/Unicode. Schema/status/
provenance/citation failure сохраняется как validation_failed и normalized_result=null;
raw output не ремонтируется. Refused/incomplete/error/unknown остаются отдельными
исходами, retries отсутствуют. Exactness не доказывает semantic support/correctness.

Ignored `backend/.local/day24/<run-id>/` содержит run.json с frozen questions,
hashes/config/index provenance, Qxx.json с vectors/retrieval/gate/actual request,
raw provider output/usage/validation/normalized result и review.json. Checkpoint
записывается до dispatch, raw output — до validation; ошибка записи останавливает
новые calls. Runtime abstention: origin=runtime_gate, attempted=false, request/raw=null,
actual context=[]; model abstention: origin=model_semantic, attempted=true.

Manual review отдельно хранит presence, exactness, answer_supported_by_citations
yes/partial/no, unsupported_claims с notes и при необходимости per-fact correctness/
coverage. Pending, unavailable и N/A не являются успехом; корректный abstention
имеет presence=no и exactness/support=N/A. Общего score и LLM judge нет.
Report self-contained: не требует API key, original baseline или index; --video
показывает компактную последовательность ответа и проверок, --full — forensic
inputs/raw output/errors. Результаты одного frozen run — в [Day 24](../day-24-grounded-rag/README.md),
команды — в [scripts](../scripts/README.md#day-24--проверяемые-rag-ответы).

## Day 23 — Query rewrite и relevance filtering

`scripts/day23_rag.py` переиспользует pinned Day 21 structure-aware index и saved
Day 22 eval без новых baseline/indexing calls. Pipeline: original question →
Responses rewrite (`gpt-5.6`, reasoning none, 250 output tokens) → exact query
embedding → cosine Top-10 → threshold 0.50 → максимум Top-5 → generation по
ORIGINAL question с прежними Day 22 instruction/settings (600 output tokens).
Rewrite получает только question. Final generation не получает rewrite,
baseline answers, evaluation metadata, scores/vectors или dropped candidates.

`retrieve` сохраняет baseline snapshot/config и rewrite/embedding/candidates;
`compare` дополняет тот же run только enhanced generation. Пустой успешный
context допускается без fallback. Failed prerequisite блокирует generation;
unknown/incomplete сохраняются, retries/resume и повтор compare отсутствуют.
При полном успехе: 10 rewrite + 10 embedding + 10 enhanced calls, baseline=0.

В ignored `backend/.local/day23/<run-id>/` находятся run/baseline/Qxx JSON и
отдельный manual review. Retrieval hash позволяет заметить изменение saved
query/selection между stages. `report` читает только этот folder без provider,
key, index и original baseline; preview не меняет full model input. Review
содержит два rewrite diagnostic labels, per-fact context/answer coverage и
enhanced claims groundedness; semantic evaluator и общий score отсутствуют.

0.50 выбран по Day 22 questions/evidence, включая Q10, на original queries;
rewrite изменяет score distribution, comparison не независимый benchmark.
Filter не меняет ranking и не гарантирует полезность high-score chunk.
Результаты, регрессии и Q10 выше порога сохраняются без перенастройки.
Строгий abstention contract оставлен Day 24. Новых dependencies нет.
Единственный live run `facf8d92-bd1d-482f-bf6e-2585565f6904` от 2 октября 2026
сохранил 30 completed calls и manual review всех Q01–Q10. Из 100 candidates:
38 kept, 40 dropped_below_threshold, 22 dropped_top_k_limit; empty selection
в этом run не возникла (проверена offline). Resolved rewrite/generation model:
`gpt-5.6-sol`, requested alias прежний `gpt-5.6`. Фактические результаты —
в [Day 23](../day-23-rewrite-filter-rag/README.md).
Команды — в [scripts](../scripts/README.md#day-23--query-rewrite-и-relevance-filtering).

## Day 22 — Первый RAG-запрос

`scripts/day22_rag.py` работает локально без FastAPI/Android. Переиспользует
read-only Day 21 SQLite; основной eval закреплён за run
`3a3c3319-5516-4526-8e56-33ab1251da72`, structure-aware, 226 chunks.
Query получает `text-embedding-3-small`, 1536 float dimensions; поиск вычисляет
cosine по всем vectors и возвращает Top-5 без threshold, reranking или соседей.

Direct и RAG используют один stateless generation path, `gpt-5.6`, reasoning none,
600 output tokens, disabled truncation, store=false и retries=0. Общая инструкция
просит краткий ответ, citations предоставленных [S#] sources и честное обозначение
недостатка сведений. RAG добавляет полные chunk texts/source/section/lines;
scores, vectors и expectations модели не передаются. Defaults старых дней прежние.

`backend/.local/day22/<eval-id>/` содержит `run.json` с frozen question set/hash,
Q01–Q10 JSON с query vector/usage, retrieval hits, actual generation inputs,
normalized outcomes и полученным provider output (в том числе partial text).
Запись выполняется поэтапно с заменой целого JSON. Unknown checkpoint при обрыве
не является успешным ответом. Ошибка evidence storage останавливает новые calls;
resume/replay и автоматических retries нет. Нормализованный incomplete не имеет
completed reply, но полученный partial output остаётся в observed_output.

`review.json` — отдельная ручная таблица, изначально pending/null. По каждому факту:
`expected_fact_in_retrieved_context`, `direct_answer_covers_fact`,
`rag_answer_covers_fact` = yes/partial/no. При недоступном ответе report показывает
unavailable. В claims вручную перечисляются существенные RAG assertions с
`grounded_in_retrieved_context` = yes/no и notes, включая детали вне expected facts.
`source_path_hit@5` — только exact path intersection (в JSON source_path_hit_at_5),
для Q10 N/A. Отсутствие искомого ответа в corpus — coverage/no-answer case.

Один полный live eval после offline readiness: 10 query embedding + 10 direct +
10 RAG requests при отсутствии технических препятствий. Плохие результаты сохраняются;
предварительная semantic настройка на контрольных вопросах и повтор ради улучшения
не входят в эксперимент. `report` читает сохранённые данные без key, DB и provider.
Вопросник и результаты относятся к pinned snapshot, даже после изменения README.

Новых зависимостей нет. Команды и ручной review — в [scripts](../scripts/README.md#day-22--первый-rag-запрос).

## Day 21 — Индексация документов

Изолированный CLI `scripts/day21_index.py` работает без FastAPI/Android.
Manifest [corpus.json](../day-21-document-indexing/corpus.json) задаёт 22 файла
и четыре representative locations. Один snapshot UTF-8/LF используется для
fixed-size и structure-aware deterministic chunking; обе стратегии ограничены
500 tokens (`cl100k_base`), target overlap 50 применяется к baseline и oversized
fallback. Текст режется по character offsets с фактическим пересчётом tokens,
Unicode не декодируется из разрезанных token sequences. Kotlin использует
formatting boundaries, не parser. Первая загрузка tokenizer assets может требовать сети.

`preview` без OpenAI показывает исходный участок и все пересекающие его chunks
обеих стратегий с metadata. `build --strategy both` отправляет точные тексты
в OpenAI Embeddings API (`text-embedding-3-small`, 1536 dimensions), batches до 32,
timeout 60 секунд на request, SDK retries=0. Используются существующий OpenAI SDK
и `tiktoken==0.14.0` из requirements. Ключ читается из backend environment или
локального `backend/.env`, не выводится. Источники не исполняются как код.

SQLite `backend/.local/day21/index.sqlite3` содержит таблицы builds/sources/chunks:
snapshot, corpus/config provenance, metadata, chunk text и JSON vectors.
Обе стратегии сохраняются одной транзакцией после получения всех vectors;
ошибка не создаёт готового неполного run. Старые runs не изменяются.
Повторный build снова вызывает API; resume и embedding cache отсутствуют.
`compare`/`inspect` читают SQLite без ключа, исходных файлов и новых API calls.

Metadata: chunk_id, source/source_type, title, section, strategy, ordinal,
start_line/end_line, token_count, text_hash, split_reason. Дополнительные
start_char/end_char — half-open offsets нормализованного текста для точного
inspect. Ordinal начинается с 0, строки — с 1 включительно. IDs стабильны для
одинаковых snapshot/config, после изменения source могут измениться.

Сравнение: chunk count, min/median/max tokens, total embedded tokens (planned
в preview), fallback count и заранее выбранные примеры. Provider usage,
число calls, время и текущий общий размер SQLite — наблюдения конкретного run;
unknown usage не заменяется нулём. Retrieval quality и производительность
стратегии из этих наблюдений не следуют. Поиска и generation здесь нет.

Команды и offline checks — в [scripts](../scripts/README.md#day-21--индексация-документов).

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
