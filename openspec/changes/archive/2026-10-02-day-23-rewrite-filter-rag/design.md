## Context

Мотивация — в proposal.md. Existing `app.first_rag` уже предоставляет read-only index validation, cosine search, `messages(original_question, hits)`, generation CONFIG, observed Responses client, JSON checkpoints и manual baseline report. `search()` сейчас возвращает только Top-5.

Pinned index: run `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`, 226 structure-aware chunks / 22 sources. Baseline: `backend/.local/day22/f7b78426-9672-437f-ab93-717a826934da`, question hash `47ab099c911d341fe15fb69e8cd6a9294c011877dace2ba43bbe523ba0190c97`.

Read-only explore воспроизвёл baseline Top-5 из saved vectors. У 50 hits min/median/max scores = 0.4278/0.5260/0.7413. В Q07 revision-checked writes/explicit transitions находятся примерно на ranks 20/32; основной Q08 send chunk — на rank 74. Это диагностические observations исходного поиска, не правила отбора.

## Goals / Non-Goals

**Goals:** переиспользовать действующие primitives; сделать observable границы original/retrieval query, candidates/final context и baseline/enhanced evidence; различать rewrite, ranking, filtering и generation причины без evaluator framework.

**Non-Goals:** гарантировать улучшение, исправлять generation/faithfulness отдельными prompts, реализовать Day 24 abstention policy или добавлять production retrieval infrastructure. Scope exclusions — в proposal.md.

## Decisions

### 1. Один небольшой Day 23 layer

Добавить `app.rewrite_filter_rag` и `backend/scripts/day23_rag.py`. Параметризовать shared `first_rag.core.search` количеством hits, сохранив default 5, прежнюю cosine formula и tie ordering. Day 21/22 CLI, configs и evidence не менять.

Переиспользовать `read_index`, `vector_norm`, `OpenAIEmbedder`, `ObservedClient`, `generation_payload`, `messages`, JSON read/write и baseline `load_report`. Не переиспользовать Day 22 orchestration целиком: она соединяет исходный query и generation в один проход. Новый слой обслуживает только два простых sequential stages и report; без abstraction hierarchy или новых dependencies.

### 2. Один LLM rewrite только по question

Rewrite использует existing Responses infrastructure: `gpt-5.6`, reasoning none, output budget 250 tokens, plain text, truncation disabled, store=false, retries=0. Отдельная versioned instruction требует один компактный retrieval query без ответа: сохранять смысл, отрицания, условия, Day/domain, обе стороны cross-source вопроса и точные identifiers/endpoints; не добавлять предполагаемые проектные правила/названия. В prompt нет примеров frozen questions, corpus, candidates, answers или evaluation metadata.

В user input передавать только original question. Exact completed reply сохранять как retrieval query и без дополнительного heuristic rewrite отправлять в embedder. Проверять лишь техническую пригодность/nonblank; семантика остаётся manual review. Incomplete/refused/error/unknown не заменять original question или повторным rewrite: downstream этого вопроса unavailable/not_dispatched.

Heuristic removal of stopwords проще, но мало помогает сложным формулировкам и соблазняет добавить специальные mappings. LLM rewrite выбран как проверяемая гипотеза, а не доказанно лучший алгоритм. Multiple queries, HyDE/предполагаемые ответы и отдельный agent исключены.

### 3. Fixed cosine filter

```text
original question --> rewrite --> exact retrieval query --> embedding
    --> cosine over all 226 stored vectors --> Top-10
    --> cosine >= 0.50 --> first maximum 5 --> final context
original question + full final context --> unchanged Day 22 generation
```

Embedding config прежний: `text-embedding-3-small`, 1536 float dimensions. Candidate rank остаётся исходным; context получает отдельные последовательные [S1]..[Sm] labels в порядке kept candidates. Для каждого candidate сохранить score/provenance/full text и ровно одно решение: ниже threshold — `dropped_below_threshold`; проходит threshold и входит в первые пять — `kept`; остальные прошедшие — `dropped_top_k_limit`. Equality 0.50 проходит. При m=0 передать `messages(original_question, [])`, без fallback или нового special abstention prompt.

Cosine threshold не меняет порядок: при одной query и таком filter итог является префиксом исходной пятёрки. Top-10 нужен для наблюдения candidates и K-limit, а не сам по себе для повышения recall final context. Cross-encoder мог бы менять порядок, но не вернуть отсутствующий среди candidates chunk; его модель/шкала не нужны выбранному эксперименту.

### 4. Threshold зафиксирован до rewritten-query live

Принято 0.50 по saved Day 22 evidence. На рассмотренной сетке 0.40/0.45/0.50/0.55/0.60 это минимальный порог, обнуляющий исходный Q10 (max 0.494346), оставляя хотя бы один hit каждому положительному вопросу. Для исходных Q01–Q10 retained counts = 4/1/3/2/3/5/5/5/5/0. При 0.55 Q01/Q02 пусты. Это rationale, не критерий максимальной fact coverage.

Порог может удалить полезный context: Q05 canonical/derived-fields contract имеет score 0.486124. В Q07 заголовок из двух строк имеет 0.590176; весь проблемный Top-5 Q07/Q08 проходит 0.50. Scores не probabilities. Threshold использует те же вопросы/evidence, включая Q10, что comparison, и откалиброван на original queries. Rewrite изменит embeddings/scores. Сохранять limitation и любые outcomes; не калибровать повторно, даже если rewritten Q10 проходит threshold.

### 5. Staged CLI и evidence

```text
day23_rag.py retrieve --baseline <day22-folder>
day23_rag.py compare <day23-result-folder>
day23_rag.py report <day23-result-folder> [--question Q08] [--full]
```

`retrieve` проверяет pinned index, frozen question hash и совместимость baseline config до calls; создаёт `backend/.local/day23/<run-id>/`. Сохраняет baseline snapshot (questions, answers/statuses, retrieval, manual review и provenance/hashes исходных файлов), experiment config с threshold rationale/limitation и Qxx checkpoints. Каждый rewrite/embedding checkpoint содержит actual input/config, status, usage и полученный output/vector; candidates/decisions/final context сохраняются полностью. Source Day 22 files read-only. Нужны 10 rewrite + 10 embedding calls при успехе; enhanced generation здесь отсутствует.

`compare` дополняет тот же result folder enhanced generation checkpoints, используя только original question и сохранённый final context. Index, source files, baseline folder, повторный rewrite/search для этого не нужны. Config question/threshold/rewrite/final selection не редактировать между стадиями. Enhanced generation использует точный baseline CONFIG: gpt-5.6, reasoning none, 600 output tokens, общая инструкция, plain text, disabled truncation, store=false, retries=0. Это ещё 10 calls при успешных prerequisites; direct/baseline/document calls = 0. Перед dispatch сохранять attempted/unknown; incomplete/failed prerequisites не заменять fake context. Пустой валидный retrieval отличается от failed retrieval и допускает generation.

Переиспользовать существующую checkpoint практику: storage failure прекращает новые calls; плохие semantic results сохраняются; скрытых retries/resume нет. Повторный `compare` при уже attempted enhanced generation отклоняется без новых calls. Не строить concurrent runner, locking service или recovery subsystem.

`report` читает только result folder, не создаёт provider clients и не переписывает raw evidence. Summary показывает per-fact baseline/final context и baseline/enhanced answer coverage, enhanced claims groundedness, technical/review status и candidate decision counts. Карточка идёт ORIGINAL QUESTION → RETRIEVAL QUERY → TOP-10 BEFORE → threshold 0.50 / KEPT-DROPPED → FINAL CONTEXT → DAY 22 BASELINE ANSWER → DAY 23 ENHANCED ANSWER → EXPECTED FACTS / REVIEW. `--full` раскрывает full texts, preview не меняет model input.

### 6. Минимальный manual review

В отдельном Day 23 `review.json` для каждого question:
- `rewrite_preserves_intent`: null до review, затем yes/partial/no;
- `rewrite_added_project_assumption`: null до review, затем yes/no;
- необязательная короткая `rewrite_note`;
- existing-style per-fact final-context/answer labels и список enhanced claims с grounded yes/no/notes.

Baseline labels импортировать без переоценки. Диагностика rewrite не quality score, не автоматический semantic validator и не влияет на retrieval/config. В notes различать rewrite failure, факт вне Top-10 (retrieval/ranking), факт в candidate, но dropped (filter/K), факт потерян при assembly и факт передан, но пропущен/искажён generation. Отсутствующее знание Q10 сохраняет no-answer/coverage diagnosis; отсутствие RPO/RTO в context = no, корректный ответ о недостатке сведений может иметь answer coverage=yes. Dropped count не равен числу доказанно нерелевантных chunks.

## Risks / Trade-offs

- [Rewrite теряет условие или домысливает project rule] → сохранять exact original/query и два manual labels; не исправлять prompt по live answers.
- [Filter удаляет useful low-score chunks либо сохраняет high-score noise] → показывать all candidates/reasons и per-fact regressions, не объявлять улучшение заранее.
- [Same-set calibration и новая score distribution] → фиксировать 0.50 до calls, показывать limitation в evidence/report/docs; comparison — один локальный эксперимент.
- [Model/provider drift между saved baseline и новым run] → сохранять requested/resolved model и actual settings/statuses; одинаковый config не доказывает идентичность provider во времени.

## Migration Plan

Миграция index/evidence не нужна. Добавить isolated layer и совместимую параметризацию search, пройти focused offline tests и CLI smoke checks, затем один frozen retrieve/compare. Заполнить manual review и фактические результаты README; команды live и offline просмотра описать в scripts README. Rollback — убрать новый слой и восстановить shared search signature; старые Day 21/22 data не меняются.
