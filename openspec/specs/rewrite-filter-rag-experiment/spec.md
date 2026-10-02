# rewrite-filter-rag-experiment Specification

## Purpose

Обеспечивает небольшой наблюдаемый CLI эксперимент query rewrite и cosine filtering по сохранённому repository index, сравнивая найденные факты и ответы с frozen Day 22 baseline и сохраняя ошибки и регрессии.

## Requirements

### Requirement: Experiment reuses pinned index and saved baseline

Day 23 SHALL использовать read-only Day 21 run `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`, 226 structure-aware chunks и Day 22 baseline run `f7b78426-9672-437f-ab93-717a826934da`. Frozen Q01–Q10/expectations, baseline retrieval/answers/manual review SHALL переиспользоваться без новых baseline generation/embedding, document embedding или indexing calls. Enhanced path SHALL embedding-ить полученный retrieval query, в том числе если rewrite оставил исходную формулировку неизменной. Question hash, index provenance и generation settings SHALL проверяться до live; source baseline SHALL оставаться неизменным, его snapshot/provenance SHALL сохраняться в Day 23 evidence. Day 21/22 observable behavior SHALL оставаться прежним.

#### Scenario: Saved baseline and index are compatible
- **WHEN** пользователь запускает Day 23 с совместимыми saved artifacts
- **THEN** доступны исходные вопросы, baseline facts/answers/review и stored chunks; provider calls относятся только к enhanced path

#### Scenario: Required artifacts are unavailable or incompatible
- **WHEN** pinned index или baseline отсутствует, повреждён либо не соответствует frozen identity/config
- **THEN** эксперимент завершается с явной ошибкой до calls, без fallback на другой run, переиндексации или повторного baseline

### Requirement: Rewrite is observable and receives only original question

Для каждого frozen question система SHALL выполнять один LLM rewrite с фиксированной до live instruction, сохранять exact original question и exact completed retrieval query и embedding-ить только этот query. Rewrite input SHALL содержать только original question, без corpus/candidates, expected facts, acceptable sources, difficulty, review, answers и negative-control metadata. Instruction SHALL требовать сохранения смысла, условий, отрицаний и точных identifiers без ответа или добавления project assumptions. Rewrite SHALL NOT подменять user question в final generation. Неуспешный/непригодный rewrite SHALL сохраняться как technical outcome без semantic fallback или повторов.

#### Scenario: Rewrite succeeds
- **WHEN** provider возвращает пригодный completed retrieval query
- **THEN** его точный текст видим в evidence/report, именно он отправляется на query embedding, а original question остаётся неизменным

#### Scenario: Rewrite is incomplete or fails
- **WHEN** rewrite имеет incomplete/refused/error/unknown outcome либо пустой query
- **THEN** outcome сохраняется, downstream embedding/retrieval/generation вопроса не отправляются, остальные независимые вопросы могут обрабатываться однократно

### Requirement: Fixed filter preserves every candidate decision and empty context

Retrieval SHALL использовать `text-embedding-3-small`, 1536 float dimensions, вычислять cosine по всем pinned chunks, сортировать по убыванию со стабильным tie ordering и сохранять Top-10 до filtering. Threshold SHALL быть ровно 0.50 для всех вопросов; final context SHALL содержать первые максимум пять candidates с score >= 0.50 в cosine order. Каждый candidate SHALL иметь rank, score, source, section/chunk identity, line range, полный text и решение `kept`, `dropped_below_threshold` или `dropped_top_k_limit`. Дополнительный reranker, heuristic short-chunk filter и изменение порядка SHALL отсутствовать. Пустой успешный result SHALL сохраняться как empty context без fallback Top-5.

#### Scenario: More than five candidates meet threshold
- **WHEN** из Top-10 более пяти candidates имеют score >= 0.50
- **THEN** первые пять получают kept, остальные passing получают dropped_top_k_limit, lower-score candidates получают dropped_below_threshold; все остаются видимыми

#### Scenario: Candidate score equals threshold
- **WHEN** score равен ровно 0.50
- **THEN** candidate проходит threshold и отбирается с учётом maximum Top-K

#### Scenario: No candidates pass
- **WHEN** все десять scores ниже 0.50
- **THEN** final context пуст, ближайшие chunks не подставляются обратно, а пустой успешный retrieval отличим от technical failure

### Requirement: Calibration limitations and regressions remain visible

Experiment config SHALL фиксироваться до Day 23 live и сохранять N=10, K=5, threshold=0.50, rewrite instruction/settings и threshold rationale. Evidence/report/documentation SHALL явно указывать, что threshold выбран по Day 22 questions/evidence, включая Q10, на original queries; rewrite меняет embeddings/scores, comparison не является независимым benchmark, cosine не probability. Filtering SHALL NOT представляться исправлением ranking: baseline observations Q07 ranks примерно 20/32 и Q08 rank примерно 74 SHALL сохраняться как rationale роли rewrite. Semantic failures и regressions SHALL сохраняться без изменения threshold/prompt/expectations, скрытых retries или повторов ради лучших результатов; улучшение SHALL NOT объявляться заранее.

#### Scenario: Rewritten Q10 produces high-score candidates
- **WHEN** rewritten Q10 возвращает candidates выше 0.50
- **THEN** применяется общий filter и сохраняется полученный context без специального исключения Q10 или перенастройки threshold

#### Scenario: A previously successful question regresses
- **WHEN** rewrite/filter теряет факт, который присутствовал в Day 22 context/answer
- **THEN** report показывает per-fact ухудшение и сохранённые candidates/decisions/query для диагностики без rerun

### Requirement: Staged CLI generates from saved context and original question

CLI SHALL предоставлять `retrieve`, `compare`, `report` без Android/FastAPI. `retrieve` SHALL выполнять и сохранять rewrite, rewritten-query embedding, Top-10 и filtering без enhanced generation. `compare` SHALL выполнять enhanced generation по сохранённому retrieval без повторного rewrite/embedding/search, используя ORIGINAL question и полные kept texts с последовательными [S#] labels. Config SHALL совпадать с saved Day 22 generation: gpt-5.6, reasoning none, 600 output tokens, та же общая instruction, plain text, store=false, disabled truncation, без tools/retries. Rewrite, scores/vectors, dropped chunks, evaluation metadata и baseline answers SHALL NOT попадать в enhanced generation input. При пустом успешном context generation SHALL получать original question и пустой context без новой abstention policy; строгий user-facing contract относится к Day 24.

#### Scenario: Generation follows saved retrieval
- **WHEN** compare обрабатывает question с completed saved retrieval
- **THEN** отправляется только одна enhanced generation с original question и полным final context; index/baseline source folders и новые retrieval calls не требуются

#### Scenario: Generation follows an empty successful selection
- **WHEN** completed retrieval имеет ноль kept chunks
- **THEN** generation получает пустой context без arbitrary sources, outcome сохраняется для review

#### Scenario: Calls fail or comparison is repeated
- **WHEN** prerequisite/generation имеет technical failure, storage перестаёт сохранять evidence или compare уже attempted generation
- **THEN** сохраняются реальные attempted/status/usage/input/output observations; failed prerequisite не заменяется empty success, storage failure прекращает новые calls, повторный compare не отправляет новые generation calls

### Requirement: Manual review separates rewrite fidelity and per-fact comparison

Manual review SHALL храниться отдельно от raw observations и baseline review. Для каждого question SHALL существовать `rewrite_preserves_intent` yes/partial/no и `rewrite_added_project_assumption` yes/no с короткой необязательной note; до review значения SHALL быть null/pending. Эти поля SHALL служить только диагностике rewrite, без quality score/автоматической semantic оценки или влияния на pipeline. Для каждого expected fact report SHALL показывать Day 22 context coverage, Day 23 final context coverage, Day 22 answer coverage и Day 23 answer coverage (yes/partial/no), а для существенных enhanced claims — groundedness в final context (yes/no) с notes. Недоступные stages SHALL помечаться unavailable, не semantic no. Report SHALL позволять различать rewrite failure, retrieval/ranking gap, filtering loss, assembly defect и generation/faithfulness failure через saved evidence/notes; единый Day 23 score, RAGAS и LLM judge SHALL отсутствовать.

#### Scenario: Rewrite changes the question meaning
- **WHEN** manual review обнаруживает потерянное условие или добавленное проектное предположение
- **THEN** reviewer заполняет два диагностических поля и при необходимости note, позволяя отличить rewrite failure от поиска по faithful query

#### Scenario: Facts are lost at different stages
- **WHEN** один факт не найден в Top-10, другой присутствовал в dropped candidate, а третий передан generation, но пропущен ответом
- **THEN** per-fact comparison и notes различают эти причины без общего verdict; baseline labels не переписываются

### Requirement: Offline reports expose the complete experiment

Day 23 evidence SHALL включать frozen questions/expectations, baseline snapshot, experiment config/limitations, exact queries, candidates/decisions/final context, actual provider inputs/settings/statuses/output/usage и отдельный manual review. `report` SHALL читать только saved Day 23 result без key, provider clients/calls, index или исходных baseline/source files и без изменения raw evidence. Карточка SHALL показывать ORIGINAL QUESTION → RETRIEVAL QUERY → TOP-10 BEFORE → threshold 0.50 → KEPT/DROPPED → FINAL CONTEXT → DAY 22 BASELINE ANSWER → DAY 23 ENHANCED ANSWER → EXPECTED FACTS / REVIEW; summary SHALL охватывать Q01–Q10 с per-fact coverage, groundedness, decision counts и technical/review status. Dropped count SHALL NOT объявляться числом доказанно нерелевантных chunks. Day README SHALL содержать краткий эксперимент/проверяемый эффект/фактический результат или отсутствие live; корневой README SHALL иметь упорядоченную ссылку, setup/commands SHALL размещаться в backend/scripts README. Secrets/local index/evidence SHALL оставаться вне Git.

#### Scenario: Video uses saved comparison
- **WHEN** report открыт без API key, index и original baseline folder
- **THEN** полная карточка, summary и manual rewrite/fact/claim labels доступны offline, full preview раскрывает saved texts и не меняет actual input

#### Scenario: Only offline validation exists
- **WHEN** реализация проверена offline, но live ещё не выполнен
- **THEN** документация прямо сообщает отсутствие live results, без вымышленных ответов, superiority claims или completed counts
