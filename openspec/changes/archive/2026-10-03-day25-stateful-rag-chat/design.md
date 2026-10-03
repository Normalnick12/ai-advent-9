## Context

Мотивация — proposal.md. Фактическая база reuse: `SQLiteConversationStore` хранит атомарные пары; `SlidingWindowContextPolicy` выбирает последние 6 messages; Day 10 `fact_extractor` разделяет validation/reducer; Day 11 хранит typed working data рядом с history, но имеет фиксированные поля и owner/task bindings. Day 22 предоставляет `read_index/search`, Day 24 — `GroundedResponse/validate/gate/abstention`. Их experiments и полный `SimpleAgent.run_turn` не являются готовым Day 25 lifecycle: последний коммитит completed text до новых проверок.

Pinned index проверен при explore: run `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`, 226 structure-aware chunks. Snapshot отличается от checkout в README.md/backend/README.md; ключевые Day 07/13 sources совпадают. Ответы относятся к snapshot.

## Goals / Non-Goals

**Goals:** один service для API и CLI; наблюдаемое разделение context layers; единая граница commit; небольшой Compose UI; один frozen experiment с честным partial/failure report.

**Non-Goals:** generic memory/RAG/transaction framework, FSM/Profile integration, cross-session task sharing, summary/extractor call, Day 23 rewrite/filter/reranking, LLM judge/RAGAS, MCP/multi-agent/vector DB/VPS, streaming/WebSockets/source viewer. CLI acceptance не зависит от emulator. Существующие дни не меняют contracts.

## Decisions

### 1. Один service и отдельный namespace

`Day25ChatService` объединяет узкие Day 25 context/memory/store helpers и существующие provider/retrieval/grounding primitives. API `/api/v1/day25/sessions`: POST create, GET existing session, POST `/{id}/messages`, DELETE existing session; GET возвращает authoritative count/revision, memory и подтверждённые turns с grounded metadata. Create/read/delete не вызывают provider. Message принимает исходный `message` и `expected_revision`; backend не принимает от клиента history/memory/model/retrieval configuration. Пустое/пробельное сообщение, extra fields и stale revision отклоняются до calls. Сохраняется существующий предел сообщения 20000 символов; provider input-limit error остаётся technical failure, без скрытого trimming текущего вопроса.

Одна session = одна задача. Restore не создаёт новую session; GET/send неизвестного ID дают 404. DELETE валидного ID идемпотентен: уже отсутствующая session также даёт 204, как в Day 07. Подтверждённый delete удаляет history/memory/results и инвалидирует ID; следующий явный send после reset создаёт новую пустую session. При malformed local ID явный reset очищает только непригодную local identity без HTTP delete; transport/server error не разрешает очистку валидного ID. Single backend worker, per-session busy guard; reread durable snapshot на каждом turn вместо дополнительного RAM history cache. Это меньше, чем расширение Day 11 owner/task subsystem или Day 13 workflow.

### 2. Пять разных inputs

| Слой | Представление и selection |
|---|---|
| Stored history | Все подтверждённые пары, включая корректные abstentions, с позициями |
| Recent history | Последние 3 полные пары до текущего U; без summaries/расширения окна |
| Task memory | Только актуальные extractive user conditions с provenance |
| Retrieval query | Отдельная техническая строка для embedding/search |
| RAG context | Полные Top-5 chunks текущего retrieval с authoritative metadata |

Generation получает явно размеченные `recent_history`, `task_memory`, `question` (исходный message) и `rag_context`. History содержит тексты прежних ответов, но не их raw combined JSON, patches или старые retrieved chunks. Instructions отделяют user conditions от project evidence, считают retrieved text данными и запрещают использовать прошлый assistant answer как доказательство. Runtime сверяет captured provider input с выбранным snapshot; expected facts/review/scores/vectors/retrieval query не отправляются generation. `previous_response_id` и provider-managed history не используются.

### 3. Extractive schema и pure reducer

```
TaskMemory = {goal: Item|null, constraints: Item[], terms: Item[], clarifications: Item[]}
Item = {id: string, text: string, source_user_turn: int, source_start: int, source_end: int}
Patch = {changes: [{field: goal|constraints|terms|clarifications,
                   action: set|remove, item_id: string|null, quote: string}]}
```

Strict models запрещают extra fields/duplicate JSON keys. Goal <=512 символов; до 6 constraints, 4 terms, 6 clarifications по <=256 символов; patch <=17 changes. Terms — целые пользовательские определения, не автоматически извлечённые corpus facts. Memory не хранит transcript summary, assistant facts, retrieved knowledge или arbitrary notes.

Runtime требует nonblank literal quote в текущем USER message, без normalization/fuzzy repair. Назначает ID из turn/порядка accepted patch и диапазон первого точного вхождения quote `[start,end)` в Unicode code points, не Android UTF-16 offsets. Для set новой list item ID=null; replace/remove указывает существующий ID правильного поля; для пустого goal set ID=null, для изменения/удаления — его ID. Две операции над одним item, неправильные targets и превышение лимитов отклоняются. Повтор уже имеющегося exact text в том же поле — no-op с сохранением первоначального provenance. Новые ID назначаются только реально добавленным items; replacement сохраняет identity и обновляет user provenance. Remove evidence остаётся в turn observation, а не в текущем memory document.

Reducer применяет весь предварительно проверенный patch к private candidate; отсутствие изменения сохраняет прежние items. Instructions требуют только явные утверждения/коррекции пользователя, не вопросы/гипотезы. Literal provenance не доказывает semantic classification: offline adversarial fixtures и ручной review отдельно проверяют её. Не добавляем универсальный semantic conflict resolver. Это reuse принципа Day 10 и typed persistence Day 11, а не перенос их scenario-specific schemas.

### 4. Retrieval до нового memory update

Deterministic query сериализуется с фиксированными labels в порядке CURRENT, GOAL, CONSTRAINTS, TERMS, CLARIFICATIONS, PREVIOUS_USER. CURRENT содержит полный исходный message; memory entries берутся из pre-turn snapshot, внутри поля упорядочены по стабильному ID. PREVIOUS_USER — последняя user реплика recent window, первые 512 Unicode code points; отсутствующие блоки опускаются, точные дубликаты text не повторяются. Query parts и итоговая строка сохраняются; разные labels не превращают данные в новые инструкции.

Текущие условия уже есть в CURRENT, поэтому proposed patch текущего turn не участвует в его retrieval. Впервые новая memory влияет на следующий turn. Поиск никогда не обращается к вытесненным history messages за скрытым контекстом.

Reuse Day 21/22 index validation, text-embedding-3-small/1536/float, cosine Top-5 и tie-breaking. Один новый query embedding на turn, без cached Day 22 vectors, rewrite, per-chunk filter или index rebuild. Existing sync embedder оборачивается неблокирующим вызовом для API; SQLite connection остаётся на owning event-loop thread. Ошибки индекса/embedding — technical failure. Gate Day 24: best score >=0.50 пропускает все пять chunks; fail/no_hits даёт runtime abstention. Threshold фиксируется до live, не подгоняется по результатам и не объявляется доказанной relevance policy для contextual queries.

### 5. Combined response и abstention policy

Generation: `{grounded: GroundedResponse, memory_update: Patch}`. Reuse Day 24 config model gpt-5.6, reasoning none, output budget 3000, truncation disabled; Day 25 version/instructions/schema фиксируются до live. Один call, без repair/retry/extraction/counting. Budget не является целевой длиной текста.

Payloads независимо проверяются: grounded validator работает только с фактически отправленными RAG chunks; patch validator — только с current user и pre-turn memory. Если любой payload invalid, pair/memory/result/revision не коммитятся. Validation reports сохраняются отдельно. Для answered требуется nonblank answer, непустые sources/citations, точная metadata/membership, совпадающие sets и literal quotes <=400 символов, как в Day 24.

| Outcome | Generation | Memory | Durable pair |
|---|---|---|---|
| Valid answered + valid patch | 1 | validated reducer candidate | commit |
| Runtime gate abstention | 0 | unchanged; update=skipped_runtime_gate | commit canonical abstention |
| Valid model insufficient_context + valid patch | 1 | unchanged; update=skipped_model_abstention | commit canonical abstention |
| Invalid grounded OR invalid patch | 1 | unchanged | no commit |
| Retrieval/provider/refused/incomplete failure | 0 or 1 | unchanged | no commit |
| Storage failure/uncertainty | already observed | reread authoritative state | not reported successful |

Model instruction requests empty changes for insufficient_context. Если модель всё же предложила непустой patch, он проходит те же schema/provenance/target/candidate checks; валидный patch явно discarded без применения, невалидный отвергает весь turn. Так abstention не позволяет обходить validation. Оба abstention origins используют точную Day 24 фразу и пустые sources/citations; memory-extractor для них отсутствует. UI/evidence показывают skipped update. Frozen acceptance не предполагает, что из такого turn появились memory items.

### 6. Одна atomic persistence boundary

Изолированная `backend/.local/day25/chat.sqlite3`: reuse sessions/messages schema и transaction primitive `SQLiteConversationStore`; небольшой Day25Store добавляет session state (`schema_version`, `revision`, memory JSON) и accepted turn results (turn index/ID, grounded JSON, memory update status). История хранит исходный U и публичный answer, полный grounded result хранится отдельно. FK/delete semantics охватывают все данные session.

Lifecycle: claim -> load snapshot -> window/query -> retrieval/gate -> capture generation input -> generation -> independent validations -> candidate reducer -> `commit_turn(expected_revision, pair, grounded, candidate_memory)` -> return confirmed result. `commit_turn` одной SQLite-транзакцией перепроверяет revision и записывает пару/result/memory/revision+1. Revision равна числу подтверждённых пар, включая abstentions. Вложенных транзакций и последовательного append_turn/save_memory нет; допустим небольшой reusable pair-insert helper с прежним Day 07 behavior.

Runtime publishes только после commit. Failed precommit leaves old state; uncertain commit/transport требует reread без автоматического повторения. GET после завершения busy показывает durable authoritative turns/memory/revision; read не выдумывает потерянный provider receipt. Exactly-once delivery и generic idempotency engine не заявляются. Failed attempts остаются в experiment evidence, не successful transcript. Повреждённое/несовместимое state не сбрасывается молча.

### 7. Frozen scripts и проверка U6

При apply сохранить следующие тексты в `day-25-stateful-rag-chat/scenarios.json` вместе с per-turn expected facts, early memory expectations и acceptable source/chunk anchors. Freeze/hash scripts, corpus/config/query policy до первого live; expectations не поступают модели и не меняются для улучшения результата.

| Turn | Scenario A: Day 07 |
|---|---|
| U1 | Хочу понять continuation существующей session Day 07 после cold start. Backend уже перезапущен. Новую session создавать нельзя. На чём держится продолжение? |
| U2 | Уточняю: старые Android bubbles восстанавливать не требуется. Под restore понимаю продолжение той же session. Что Android должен сделать при открытии? |
| U3 | Что означает history_turn_count и как он меняется после одного успешного обмена? |
| U4 | Если generation завершилась incomplete, что останется в сохранённой истории? |
| U5 | А после рестарта? |
| U6 | А что тогда делает Android? Опиши открытие экрана и следующую отправку для нашего случая. |

A early memory: goal continuation той же Day 07 session; backend уже перезапущен; нельзя создать новую session; старые bubbles не нужны; restore означает ту же session. Expected facts: durable history/ID, metadata GET, count подтверждённых пар, отсутствие partial pair при incomplete, следующая отправка только нового текста по прежнему ID. Sources: first-agent-conversation/spec.md и first-agent-android/spec.md (prefix `openspec/specs/`), соответствующие backend/Android corpus files. Anchors: `2652cec5...` Backend restarts, `bd81c40f...` current identity, `bfaf2036...` cold start metadata; полные IDs разрешаются из pinned index до freeze.

| Turn | Scenario B: Day 13 |
|---|---|
| U1 | Цель — разобраться с recovery Day 13 после stale revision или uncertain result. Backend authoritative. Automatic retry запрещён. Что делать при stale revision? |
| U2 | Фиксируем: обычный Send не является workflow event. После rejected или uncertain operation нужно перечитать authoritative state. Чем Send отличается от перехода? |
| U3 | Какие поля восстановленного task state позволяют понять текущее положение задачи? |
| U4 | Что меняет отдельное событие PAUSE и сохраняется ли положение задачи? |
| U5 | А если ответ потерялся? |
| U6 | А что тогда делает Android после cold start и можно ли продолжить обычным Send? |

B early memory: recovery goal, backend authority, no automatic retry, Send != workflow event, reread после rejected/uncertain. Expected facts: stale rejection без effects, authoritative reread, canonical state/status/revision vs derived fields, PAUSE сохраняет node, lost PAUSE response не повторяет PAUSE, cold start read-only, ordinary Send не выполняет Resume/event. Sources: task-state-machine/spec.md, task-state-android/spec.md, Day 13 README и TaskStateLabService.send corpus chunks. Anchors: `cd94896c...` authoritative events, `94ed2d63...` recovery, `ef1e3208...` revisions. Для Send нельзя принимать произвольную quote про workflow event как semantic support.

Каждый сценарий: fresh session, 6 user + 6 actual assistant messages; после T3 store/service закрывается и создаётся новый instance с той же DB/session. Это проверяет reopen, не выдаётся за полноценный OS restart. На U6 durable snapshot содержит U1/A1/U2/A2, actual recent input — только U3/A3…U5/A5; память до U6 и actual embedding input содержат early entries с U1/U2 provenance. After T6 durable history содержит 12 messages. Проверяется captured input, не только preview builder.

Runner останавливает конкретный сценарий при technical/validation failure, отмечает partial и не делает replay. Abstention сохраняется и допускает дальнейший turn, но отсутствие critical early update даёт явный failed criterion; substantive late acceptance требует answered. Manual review A5/A6/B5/B6 проверяет retrieval relevance, citation support и early constraint adherence; early patches также проверяются на смысл. Повтор раннего условия поздним assistant отмечается как возможный второй канал. Механизм проверяется без утверждения exclusive causal benefit; ablation не входит в baseline.

### 8. CLI evidence и saved video report

`backend/scripts/day25_chat.py run` запускает оба scripts через тот же service; `report <run> [--video]` читает только saved evidence, без API key/provider/index. Pre-dispatch checkpoints отмечают unknown; raw output сохраняется до validation. Evidence I/O failure останавливает новые calls; если commit уже состоялся, report отражает необходимость reread, не заявляет rollback. Manifest фиксирует scenario/config hashes и corpus identity; per-turn JSON содержит pre/post state, selected/excluded positions, exact embedding input/vector/hits/gate, actual generation request, raw output/status/usage, оба validation reports, patch decision и commit outcome. Review pending не считается passed.

`--video` показывает для A и B короткую сводку, исходные U1/U2 conditions, late U6, recent positions, memory before U6 с provenance, actual query, retrieved sources, grounded answer/sources/citations и acceptance/review status. Не печатает vectors, полные raw JSON/transcripts/chunks; подробности остаются в обычном full report. После CLI в видео — короткий Android send с sources/memory, отдельно от frozen acceptance.

Calls: на сценарий 6 embeddings + до 6 combined generations = до 12, оба сценария до 24; create/read/reopen/report = 0, extractor/rewrite/judge/count/repair/retry = 0. Technical interruption оставляет partial budget; demo calls считаются отдельно. Scenario scripts deterministic, live answers/retrieval при меняющихся accepted patches не обещаются побитово одинаковыми.

### 9. Android и verification scope

Отдельные Day25 DTO/repository/ViewModel/screen, reuse ChatBubble/ChatComposer, Retrofit/AppContainer и существующая navigation. Sources рядом с answer, collapsible Task Memory (goal/constraints/terms/clarifications), loading/error/session count. API status answered/abstention/technical failure не смешиваются; UI показывает skipped memory update при abstention. CurrentSessionStore использует отдельный preferences name. Cold start read-only восстанавливает ID/count/memory, старые bubbles не обязательны. Unknown send блокирует повтор и предлагает reread; новая session/reset не выполняются автоматически. GET history позволяет показать подтверждённый результат reconciliation с sources, без догадок по local bubbles.

Focused backend tests: window/actual payload, query order, patch provenance/reducer, both invalid payload directions, abstention matrix, atomic rollback/reopen/isolation/revision/busy/reset, failed outcomes, fake-client runner budget/report. Android repository/ViewModel tests и focused UI class; Gradle только `scripts/dev.ps1 unit/build/ui -Test ...` по scripts README. Live acceptance выполняется один раз после freeze; не перезапускается ради лучшего результата.

## Risks / Trade-offs

- [Cosine 0.50 не проверен на contextual queries; memory может доминировать search] -> freeze policy, сохранять actual query/hits, вручную отличать relevance/coverage от provenance.
- [Exact quote не гарантирует semantic support или правильную memory category] -> независимые checks и human review; не обещать deterministic semantic correctness.
- [Abstention сохраняет user message, но не закрепляет его условия] -> явный skipped update и failed early-memory criterion, без скрытого extractor.
- [Recent assistant может повторить ранние условия] -> показать этот канал в review; механизм не доказывает единственную причину верного ответа без ablation.
- [Полный message может превысить provider input limit; combined JSON может быть incomplete] -> явный technical failure, без silent truncation/repair; live limitation фиксируется.
- [Lost response не доказывает rollback] -> authoritative reread, без auto retry и обещания exactly-once.

## Migration Plan

Новые Day 25 files/namespace и локальная DB без migration старых дней; индекс read-only. Документация дня краткая, factual results только после проверки; ссылка в root README обязательна. Rollback отключает новый namespace/UI entry и сохраняет локальные evidence для review. Commit/push отдельно по явному запросу. До apply выполнить короткий blocker review согласованности artifacts; после planning остановиться.
