# stateful-rag-chat Specification

## Purpose

Day 25 соединяет durable conversation, отдельную пользовательскую Task Memory и поиск по pinned corpus, позволяя проверить сохранение цели после выпадения ранних сообщений из model history.

## Requirements

### Requirement: Durable sessions remain separate from recent model history

Day 25 SHALL хранить все подтверждённые user/assistant pairs текущей session и grounded results durable. Model recent history SHALL содержать только последние три полные подтверждённые пары до текущего user message, включая подтверждённые abstentions; остальные messages SHALL NOT передаваться через summary, provider-managed continuation или иной скрытый канал. Task Memory и RAG context SHALL быть отдельно размечены. Create/read/restore/delete SHALL не вызывать provider; restore SHALL продолжать тот же ID, неизвестный ID SHALL не создавать session. Reset SHALL удалять history/memory/results и инвалидировать ID. Namespace и данные прежних дней SHALL сохранять свои contracts.

#### Scenario: Sixth question uses a bounded window
- **WHEN** пять пар подтверждены и отправляется U6
- **THEN** durable history содержит U1/A1…U5/A5, actual model recent history содержит только U3/A3…U5/A5, а U6 передаётся отдельно как исходный вопрос

#### Scenario: Restore and reset preserve identity semantics
- **WHEN** service/store переоткрывается с существующей session, затем выполняется подтверждённый reset
- **THEN** до reset восстанавливаются точные history/memory/results/revision без provider calls, после reset прежний ID недоступен и его данные не попадают в новый диалог

#### Scenario: Repeated explicit delete is confirmed
- **WHEN** DELETE содержит валидный session ID, уже отсутствующий в Day 25 store
- **THEN** backend возвращает 204 без provider calls; GET/send того же ID продолжают возвращать 404

### Requirement: Task memory contains only extractive user conditions

Task Memory SHALL иметь отдельные goal, constraints, terms, clarifications. Каждый item SHALL содержать runtime-owned ID, literal text и provenance current USER turn/offsets. LLM SHALL предлагать patch, а runtime SHALL валидировать и детерминированно применять его целиком к pre-turn snapshot. Новые items SHALL NOT происходить из retrieved chunks, assistant history, предыдущих assistant statements, transcript summary или arbitrary notes. Неподтверждённые questions/hypotheses SHALL не трактоваться как явные user assertions. Limits, existing targets и duplicate operations SHALL проверяться; недопустимый patch SHALL не ремонтироваться. Exact no-op SHALL сохранять первоначальный provenance.

#### Scenario: A user establishes a condition
- **WHEN** valid patch цитирует literal fragment текущего U1 и предлагает constraint
- **THEN** runtime назначает ID/turn/offsets и после successful turn сохраняет item; subsequent reads возвращают этот provenance

#### Scenario: Patch cites another context layer
- **WHEN** quote есть только в RAG chunk или assistant history, но отсутствует в текущем USER message
- **THEN** memory validation fails, history/memory/result/revision не коммитятся как успешный turn

#### Scenario: Correction or invalid target
- **WHEN** пользователь явно исправляет item и patch указывает его существующий ID с текущей literal quote
- **THEN** valid reducer обновляет только этот item с новым user provenance; неизвестный ID, duplicate operation или exceeded limit отклоняет весь patch без частичных изменений

### Requirement: Contextual search uses memory before the turn

Каждый новый допустимый message SHALL запускать retrieval по deterministic query: current message, pre-turn goal, active constraints, terms, clarifications и последний recent user (не более 512 Unicode code points). Порядок и правила exact deduplication SHALL фиксироваться до live. Query SHALL использоваться только для embedding/search; generation SHALL отвечать на исходный message. Новый patch SHALL начинать влиять на retrieval только со следующего turn. Actual embedding input и его memory origins SHALL сохраняться в evidence.

#### Scenario: Context-dependent follow-up
- **WHEN** current message равен «А после рестарта?», а memory содержит Day 07 continuation goal
- **THEN** embedding input содержит current message и pre-turn goal/conditions; generation получает исходный вопрос, отдельно recent history/memory/RAG, без подмены вопроса технической query

#### Scenario: New condition first enters retrieval through current message
- **WHEN** пользователь добавляет условие, отсутствующее в pre-turn memory
- **THEN** оно уже доступно в current-message query part, но proposed update не подставляется в pre-turn memory; accepted item появляется в memory part следующего turn

### Requirement: Pinned retrieval and grounding preserve source validity

Retrieval SHALL читать index run `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`, 226 structure-aware chunks, text-embedding-3-small/1536/float и cosine Top-5 со стабильным tie-breaking. Day 23 rewrite/filter/reranking, index rebuild и cached original-question vectors SHALL отсутствовать. Best score >=0.50 SHALL передавать все пять chunks; threshold SHALL не меняться после live. Несовместимый index/embedding error SHALL быть technical failure, не abstention.

Grounded payload SHALL сохранять Day 24 форму `{status, answer, sources, citations}` и validation: answered требует nonblank answer и непустые sources/citations, точную source/section metadata и membership в actual sent chunks, совпадающие chunk ID sets, отсутствие duplicates и literal nonblank quotes <=400 символов без repair. History/task memory SHALL не считаться источником project knowledge. Provenance/exactness SHALL не объявляться semantic support или correctness.

#### Scenario: Valid sources are required for substantive answers
- **WHEN** completed candidate имеет status=answered
- **THEN** успешный ответ доступен только после проверки всех sources/citations против текущего actual RAG context; indexed-but-unsent chunk и изменённая quote отклоняются

#### Scenario: Weak hits and index failure differ
- **WHEN** успешный retrieval имеет best score <0.50 либо no_hits
- **THEN** runtime abstains без generation; повреждение или недоступность index вместо этого останавливает turn с technical failure

### Requirement: Combined generation has independent validation boundaries

После gate PASS система SHALL выполнять один structured generation call с двумя обязательными payloads `grounded` и `memory_update`, валидируемыми независимо. Runtime SHALL фиксировать обе validation outcomes, когда payload доступен. Invalid grounded OR invalid memory patch SHALL исключать normal successful atomic commit всего turn; хороший answer SHALL не сохраняться с плохой memory и наоборот. Incomplete/refused/provider errors SHALL не становиться successful assistant turns. Automatic retry/repair и отдельный memory-extractor SHALL отсутствовать.

#### Scenario: Good answer with bad memory patch
- **WHEN** grounded validation passes, а patch provenance/targets/schema invalid
- **THEN** результат есть validation failure, ни pair, ни grounded result, ни memory/revision не публикуются как successful turn

#### Scenario: Good patch with bad answer
- **WHEN** memory validation passes, а grounded citations/schema invalid
- **THEN** memory candidate не применяется и successful turn commit отсутствует

### Requirement: Confirmed abstention preserves memory explicitly

Runtime gate abstention и model insufficient_context SHALL возвращать точную фразу «Не знаю ответа на основании текущей базы знаний. Уточните вопрос или укажите нужный документ.» с пустыми sources/citations. Они SHALL сохраняться как подтверждённые abstention pairs с увеличением count/revision, но task memory SHALL оставаться неизменной, с явным skipped-update reason. Model abstention SHALL всё равно требовать валидных обоих payloads: валидный непустой patch игнорируется явно, invalid patch отклоняет весь turn. Только accepted answered SHALL применять validated patch. Отдельного extractor ради abstention SHALL не быть.

#### Scenario: Gate blocks an early condition update
- **WHEN** U1 содержит будущий critical constraint, но gate FAIL
- **THEN** сохраняется abstention pair без generation и без нового memory item; отсутствие этого item в frozen acceptance отмечается failure/limitation, а не предполагается успешным extraction

#### Scenario: Model abstains with a proposed update
- **WHEN** после PASS модель возвращает valid insufficient_context и valid patch
- **THEN** pair сохраняется с origin=model_semantic, memory не меняется, patch имеет skipped_model_abstention; invalid patch вместо этого даёт validation failure без commit

### Requirement: Accepted turn state is atomic and authoritative

Pair, grounded result, task memory и revision SHALL сохраняться одной atomic operation с проверкой expected revision. Busy/stale request SHALL отклоняться до provider dispatch; после commit revision SHALL увеличиваться на один. Runtime SHALL публиковать state только после подтверждённой записи. Failed precommit SHALL сохранять прежний snapshot; storage/transport uncertainty SHALL не объявляться success или rollback без подтверждения. Recovery SHALL читать authoritative state без automatic replay; corrupted state SHALL не заменяться пустой session.

#### Scenario: Write fails between logical components
- **WHEN** ошибка возникает при записи pair/result/memory до transaction commit
- **THEN** reread/reopen возвращает прежние все компоненты и revision, без half-turn или memory без соответствующей пары

#### Scenario: Response is lost after commit
- **WHEN** accepted turn durable сохранён, но response не подтверждён клиентом
- **THEN** read восстанавливает authoritative count/history/results/memory; send не повторяется автоматически и недоступный runtime receipt не выдумывается

### Requirement: Frozen scenarios demonstrate early context surviving the window

CLI acceptance SHALL включать ровно два versioned сценария по шесть user turns и шесть фактических assistant replies: Day 07 same-session restore и Day 13 stale/uncertain recovery, с user scripts из design decision 7. До live SHALL фиксироваться texts, per-turn expected facts, early-memory expectations, acceptable pinned source anchors, config и hashes. После T3 SHALL проверяться reopen по тому же ID без replay/provider calls. Technical/validation failure SHALL оставлять partial scenario без retry; confirmed abstention SHALL оставаться видимым и не давать fabricated memory success.

Для U6 каждого сценария evidence SHALL подтверждать одновременно: durable U1/A1/U2/A2 сохранены; actual recent history их не содержит; нужные early goal/constraints есть в pre-U6 task memory с U1/U2 USER provenance; actual embedding input содержит эти entries; current answered result имеет validated sources/citations. Manual review SHALL отдельно проверять, что late answer не нарушает frozen early constraints, hits релевантны и claims поддерживаются citations. Missing criterion SHALL не маскироваться общим completed verdict.

#### Scenario: Successful sixth-turn evidence
- **WHEN** сценарий завершил шесть turns
- **THEN** доступны все шесть проверок U6, durable count=6/12 messages и отдельные mechanical/manual outcomes; pending review не обозначается passed

#### Scenario: Correct answer has more than one possible context channel
- **WHEN** раннее условие также повторилось в recent assistant text
- **THEN** review показывает это и не утверждает, что memory была единственной причиной правильного ответа; работа механизма без ablation не является доказательством exclusive causal benefit

### Requirement: Saved evidence supports offline review and compact video

Runner SHALL сохранять manifest, per-turn pre/post memory, patches/decisions, selected/excluded history positions, actual retrieval input/vector/hits/gate, captured generation input/raw output/status/usage, оба validation results и commit outcome. Checkpoints до dispatch SHALL различать not_attempted/unknown; raw output SHALL сохраняться до validation. Expected facts/review SHALL NOT поступать модели. Evidence errors SHALL останавливать дальнейшие calls без ложного заявления rollback уже committed turn.

Saved `report --video` SHALL работать без provider/key/index и компактно показывать для каждого сценария early U1/U2 constraints, U6, recent positions, memory before U6, contextual query, retrieved sources, grounded answer/citations и acceptance/review status. Vectors/raw JSON/full chunks SHALL оставаться вне compact report. Budget SHALL учитывать до 6 embeddings + 6 combined generations на сценарий, до 24 calls на два; restore/report/extraction/rewrite/judge/count/retry calls SHALL быть нулевыми. Android demo SHALL учитываться отдельно.

#### Scenario: Video report is generated offline
- **WHEN** доступны saved artifacts завершённого или partial run, но provider/key/index недоступны
- **THEN** report показывает подтверждённое evidence и явные unavailable/pending/failure поля без новых calls или синтеза успешных результатов
