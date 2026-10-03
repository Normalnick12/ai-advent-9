## Context

Мотивация — [proposal.md](proposal.md); внешний контракт — [spec](specs/grounded-rag-experiment/spec.md). Нужен design из-за нового structured response/evidence contract и разделения механической/смысловой проверки.

Explore проверил локальный baseline Day 22: read-only replay сохранённых vectors дал точное совпадение всех hits/scores и прежнего model input. Original best scores Q01–Q10: 0.548688, 0.542699, 0.624001, 0.626994, 0.564319, 0.628231, 0.590176, 0.595956, 0.741283, 0.494346. Все positive questions проходят gate 0.50; Q10 нет. Полезный Q05 chunk имеет original score 0.486124 (rank 5), а после Day 23 rewrite — 0.430896 (rank 6). Q07–Q08 сохраняют известные retrieval gaps.

## Goals / Non-Goals

**Goals:** небольшой слой над существующим search/Responses client, независимые исходы relevance/provenance/exactness/support/correctness, самодостаточный saved report.

**Non-Goals:** менять поведение Days 21–23 или общий agent runtime; строить универсальный validator/benchmark runner. Новый CLI ограничен frozen eval/report; arbitrary-question режим не нужен для задания.

## Decisions

### 1. Replay original retrieval, затем gate

Переиспользовать `first_rag.core.read_index(baseline=True)`, `question_set`, `vector_norm`, `search` и `rewrite_filter_rag.core.load_baseline` для чтения исходного baseline. Проверить соответствие question/vector input и embedding config; пересчитать все Top-5 и сравнить полные hits/scores с baseline до первого generation call. Использовать сохранённые snapshot texts, не актуальные файлы workspace. Зафиксировать hashes исходного evidence и question set; baseline не изменять.

Gate использует полный best score >= 0.50, не округлённый display. Runtime abstention не создаёт generation request; PASS сохраняет пять chunks целиком. Пустые hits защитно дают no_hits; испорченный index/replay остаётся ошибкой. Альтернативы (свежие query embeddings, Day 23 rewrite/filter) добавляют изменяемый retrieval и не нужны для изоляции answer contract. Ожидаемый live budget: 9 generation calls, 0 embeddings/rewrites/judge; это dispatch expectation, не обещание девяти answered.

### 2. Day-specific structured contract через существующий client

Новый `backend/app/grounded_rag/` содержит только schema/config/context/validation, runner и report; `backend/scripts/day24_rag.py` — argparse entry point. Использовать текущий `AgentConfig.text_format` -> `generation_payload` -> Responses `text.format` с `type=json_schema`, `strict=true`, `name=day24_grounded_answer`. Существующий `ObservedClient` сохраняет raw output и нормализует provider status; новый transport не нужен. Generation config: gpt-5.6, reasoning_effort=none, max_output_tokens=3000, truncation=disabled, store=false, max_retries=0, отдельная version day24-grounded-v1.

Schema — один root object с четырьмя полями из spec, required на всех уровнях и additionalProperties=false; status-dependent invariants проверяет runtime. Pydantic strict/extra-forbid models с model_json_schema и локальными checks позволяют избежать двух расходящихся описаний формы. Parser отклоняет duplicate JSON keys; schema validity не заменяет content validation. Prompt требует краткий русский answer, короткие literal quotes <=400 символов, поддержку каждого существенного утверждения цитатами, аккуратное обозначение неизвестных частей и фиксированную abstention-фразу из spec. Budget 3000 — только технический запас для длинных metadata/IDs.

Текущий Day 22 `messages()` не передаёт chunk_id. Новый узкий builder добавляет full chunk_id к прежним полным blocks [S1]–[S5], source/section/line-range/text, сохраняя original question. Не передавать eval labels/scores/vectors. [S#] — удобные display labels, не замена authoritative chunk_id. Общий Day 22 builder не менять.

### 3. Validation без repair

Из actual request context строится mapping chunk_id -> source/section/text, сверенный с retrieval перед dispatch. Проверки идут в порядке provider outcome -> JSON/schema -> status contract -> sources -> citations. Полный контракт в spec; validation возвращает список стабильных error codes с index/field (например unknown_chunk_id, source_mismatch, quote_not_found), а не исправленный candidate. `quote in chunk.text` выполняется над исходными decoded строками; whitespace strip используется только для проверки nonblank. Дубликаты source IDs и citation pairs запрещены; source/citation sets равны.

`normalized_result` означает только прохождение deterministic checks, не доказанную semantic support. При ошибке он null, processing status=validation_failed; raw candidate остаётся forensic evidence. Модельный и runtime insufficient_context имеют одинаковые четыре поля и фиксированный текст; evidence origin различает runtime_gate/model_semantic (null у answered/technical failure). Не вводить error как третий model status. Refused/incomplete/error/unknown — внешние технические состояния runner. Альтернативы auto-repair, semantic retry и fallback abstention маскируют ошибки эксперимента, поэтому исключены.

### 4. Минимальное evidence и offline reports

Переиспользовать `first_rag.experiment.write_json/read_json/phase` и принцип checkpoints Days 22–23, не их whole experiment/comparison runner. В ignored `backend/.local/day24/<run-id>/`:

| File | Минимальное содержание |
|---|---|
| run.json | ID/time/traversal status, frozen Q01–Q10/expected facts/hash, index provenance, Day 22 ID/input file hashes, cached-vector mode, threshold и rationale/limitation, полные prompt/schema/config |
| Qxx.json | exact question, reused query vector и исходный input/provenance, полные replay hits/scores, gate best/threshold/decision/reason, actual request/context, generation attempted/status/provider outcome/usage/raw output, validation errors/status, normalized_result, abstention_origin |
| review.json | run/question hash, reviewer, pending/reviewed, presence/exactness/support labels, unsupported_claims+notes, optional per-fact correctness/coverage |

Сначала сохранить run и все исходные checkpoints; перед dispatch сохранить attempted=true/status=unknown и точный request; после возврата сохранить raw output/provider outcome до validation. Ошибка storage останавливает новые calls. Gate fail: attempted=false, not_dispatched, request/raw=null, actual context=[], retrieval hits сохранены, origin=runtime_gate. Timeout/unexpected interruption после dispatch остаётся unknown, не автоматически повторяется. Нормальное завершение traversal не означает semantic/provider success.

Report связывает review с run/question hash, проверяет labels и сверяет механические поля с saved response/validation. Непроверенный raw candidate не отображается как accepted answer. Тексты цитат не сокращать/не нормализовать; display aliases chunk IDs допустимы только с ясным обозначением, forensic report хранит полный ID. Report не обращается к оригинальному baseline/index, не загружает provider client и не требует ключа.

### 5. Ручная поддержка и correctness отдельно

Review template содержит sources_present/citations_present (yes/no при доступном response), citations_exact (yes/no/N/A), answer_supported_by_citations (yes/partial/no либо pending/N/A/unavailable), unsupported_claims [{claim, notes}] и notes; optional facts по неизменным F IDs содержат correctness/coverage labels. Механические labels вычисляются и сохраняются, semantic labels заполняет reviewer по полному answer, цитатам и окружающим chunks. Для abstention presence=no, exactness/support=N/A; notes позволяют оценить уместность отказа. Technical failure без usable candidate — unavailable. Invalid candidate, если читается вручную, явно остаётся unvalidated и не входит в accepted-answer totals.

Support=yes требует поддержки всех существенных claims, partial — только части, no — отсутствующей/противоречащей поддержки существенного ответа. Читатель проверяет применимость цитаты к Day/scenario; правильный ответ без подходящих citations не получает support=yes. Expected facts помогают оценить correctness/coverage, но не попадают в generation input. Никакого общего grounding score или автоматического LLM judge. Новый review не наследует старые answer labels Day 22.

### 6. CLI/video и проверки

Команды: `eval --baseline PATH [--db PATH] [--output-root PATH]`; `report RESULT [--question Qxx] [--full | --video]`. DB override меняет расположение, не pinned identity. Report без question показывает компактную таблицу Q01–Q10, отдельные dispatch/technical/validation/abstention/review counts. Video answered: QUESTION -> GATE -> ANSWER -> SOURCES -> CITATIONS -> VALIDATION -> SEMANTIC SUPPORT. Gate fail: question/best/threshold/FAIL/GENERATION CALL: NO/fixed abstention; model abstention: PASS/CALL: YES/origin/response. Подробный report отдельно показывает full inputs/raw/errors и per-fact notes, без повторных calls.

Focused fake-provider tests покрывают replay mismatch, gate boundary и сохранение low-score chunk, реальный model input, status invariants, membership/metadata/sets, literal quotes/length/duplicates, invalid/incomplete/refused/unknown без retry, storage failure и keyless report/video. Fixture с настоящей, но нерелевантной quote обязан проходить exactness, сохраняя отдельный support=no/pending. Существующие Day 22/23 тесты проверить на совместимость; Android/build не затронуты. После offline checks — один live eval, review всех 10 outcomes, frozen settings не менять ради результата; для видео достаточно offline report, новый live не нужен.

## Risks / Trade-offs

- Threshold уже связан с frozen questions; Q10 лишь на 0.005654 ниже 0.50 -> явно назвать run исследованием answer contract, не независимым retrieval benchmark, не перенастраивать порог.
- Q07–Q08 gaps сохраняются, pass не доказывает достаточность -> разрешить model abstention, оценивать support вручную.
- Literal quote не гарантирует правильность/поддержку -> отдельные semantic и expected-fact labels без общего score.
- Длинные metadata/IDs расходуют output budget -> 3000 фиксируется до live, prompt остаётся кратким; incomplete сохраняется как failure без repair.
- Фиксированная abstention-фраза уменьшает гибкость уточнения -> сознательный минимальный проверяемый контракт обеих веток.

## Migration Plan

Добавить isolated files и focused tests без миграции SQLite/старых результатов; описать setup/commands в backend/scripts README и короткий Day README с относительной ссылкой из корневого README. До live результаты помечать непроверенными, после него записывать только фактические наблюдения. Новые artifacts/evidence не меняют Days 21–23; rollback состоит в прекращении использования Day 24 CLI. Commit/push/archive остаются отдельным завершением дня по запросу пользователя.
