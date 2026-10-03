# grounded-rag-experiment Specification

## Purpose

Day 24 делает происхождение RAG-ответа проверяемым: фиксирует retrieval, проверяет точные sources/citations и отделяет deterministic abstention и технические проверки от ручной оценки смысловой поддержки ответа.

## Requirements

### Requirement: Frozen original-query retrieval isolates the answer contract

Основной eval SHALL использовать неизменные Q01–Q10/expected facts Day 22, baseline `f7b78426-9672-437f-ab93-717a826934da`, его сохранённые original-query vectors и read-only Day 21 index `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`, 226 structure-aware chunks, embedding config text-embedding-3-small/1536/float. Replay SHALL вычислять прежний cosine Top-5 со стабильными ties и проверять совпадение полных hits/scores с baseline, identity/hash questions, vectors и snapshot до generation. Новые embedding calls, rewrite, per-chunk filtering и retrieval tuning SHALL отсутствовать. Несовместимость, повреждение или недоступность исходных данных SHALL давать technical failure без fallback или insufficient_context.

#### Scenario: Valid frozen replay
- **WHEN** доступны совместимые saved baseline и pinned index
- **THEN** все десять original Top-5 воспроизводятся без provider calls для retrieval, а исходное evidence остаётся неизменным

#### Scenario: Replay input is missing or inconsistent
- **WHEN** index, question set, query vector или replayed hits не проходят проверку
- **THEN** eval останавливается до generation с technical failure, не создавая новый index и не возвращая semantic abstention

### Requirement: Best-score gate controls dispatch without filtering context

После успешного retrieval система SHALL сравнивать полный неокруглённый best cosine с фиксированным threshold 0.50. При best_score < 0.50 generation SHALL NOT dispatch; при best_score >= 0.50 generation SHALL получать все пять полных chunks в rank order, включая scores ниже threshold. Threshold SHALL фиксироваться до live и не меняться после результатов. Защитная обработка пустого успешного retrieval SHALL давать runtime abstention с причиной no_hits; ошибки retrieval/index SHALL оставаться technical failure.

#### Scenario: Frozen Q10 fails the gate
- **WHEN** best_score равен сохранённому Q10 score 0.4943461840748868
- **THEN** результат есть deterministic insufficient_context с пустыми sources/citations, origin=runtime_gate, generation attempted=false и отсутствующим actual model context

#### Scenario: Boundary and low-score evidence
- **WHEN** best_score >= 0.50, включая равенство
- **THEN** gate проходит без удаления остальных hits; в Q05 сохраняется полезный rank-5 chunk со score 0.4861241020301931

### Requirement: Unified structured response distinguishes answer and abstention

Generation SHALL использовать strict Structured Outputs с единственным объектом {status, answer, sources, citations}: status enum answered|insufficient_context, answer string, sources array объектов {source, section, chunk_id}, citations array объектов {chunk_id, quote}; все поля обязательны, дополнительных полей нет. Runtime SHALL проверять эту форму и условия статуса. Для answered SHALL требоваться nonblank answer, минимум один source и одна citation. Для insufficient_context SHALL требоваться пустые sources и citations и фраза «Не знаю ответа на основании текущей базы знаний. Уточните вопрос или укажите нужный документ.» Это SHALL быть корректным исключением из обязательных sources/citations: слабые или нерелевантные ссылки ради заполнения массивов SHALL NOT добавляться.

Model semantic abstention после PASS SHALL использовать тот же schema, но evidence SHALL указывать origin=model_semantic и выполненную generation. Runtime gate abstention SHALL иметь origin=runtime_gate и отсутствие dispatch. Instruction SHALL требовать краткий содержательный русский answer, короткие дословные citations и отсутствие неподтверждённых утверждений; допускается честно обозначить неизвестные части вопроса. Технический output budget 3000 SHALL NOT трактоваться как целевой объём ответа.

#### Scenario: Answer has no supporting references
- **WHEN** status=answered, но answer пустой/пробельный либо один из массивов пуст
- **THEN** response отвергается как validation_failed, даже если JSON соответствует schema

#### Scenario: Model abstains after a passing gate
- **WHEN** generation после PASS возвращает корректный insufficient_context
- **THEN** пустые массивы принимаются, raw output сохраняется, origin=model_semantic и attempted=true отличают этот результат от runtime abstention

#### Scenario: Abstention carries decorative references
- **WHEN** insufficient_context содержит непустые sources/citations или не соблюдает фиксированный текст
- **THEN** runtime отвергает response без очистки массивов или подмены текста

### Requirement: Provenance is validated against actual model context

Model context SHALL содержать исходный question, полные тексты пяти chunks и их authoritative source/section/full chunk_id; retrieved text SHALL трактоваться как данные, не инструкции. Scores, vectors, expected facts, acceptable sources и negative-control labels SHALL NOT передаваться generation. Для каждого referenced chunk_id runtime SHALL проверять membership именно в фактически отправленном context и точное совпадение source/section с metadata этого chunk. Sources SHALL содержать не более одного элемента на chunk_id, и sets sources.chunk_id и citations.chunk_id SHALL совпадать. Runtime SHALL NOT доверять скопированной моделью provenance только из-за schema validity.

#### Scenario: Citation references an indexed but unsent chunk
- **WHEN** referenced chunk существует в index, но отсутствует в actual model context
- **THEN** validation отвергает ссылку; наличие chunk в общей базе не заменяет membership check

#### Scenario: Copied source metadata differs
- **WHEN** source или section не совпадают точно либо source/citation chunk sets различаются
- **THEN** runtime возвращает validation_failed без исправления metadata или удаления лишних элементов

### Requirement: Citations are exact bounded fragments

Runtime SHALL проверять, что каждая quote содержит непробельный текст, имеет не более 400 символов после JSON decoding и является literal substring текста соответствующего переданного chunk. Проверка SHALL сохранять исходные whitespace, case и Unicode без normalization, fuzzy matching, склеивания раздельных фрагментов или semantic repair. Повтор одинаковой пары (chunk_id, quote) SHALL быть validation failure. Exactness SHALL NOT интерпретироваться как semantic support.

#### Scenario: Exact quote is accepted mechanically
- **WHEN** quote дословно присутствует в указанном переданном chunk и остальные проверки выполнены
- **THEN** citation exactness проходит; semantic support остаётся отдельной ручной оценкой

#### Scenario: Plausible quote was altered
- **WHEN** quote пустая, превышает лимит, дублируется или её исходная строка отсутствует в указанном chunk
- **THEN** validation отвергает candidate без fuzzy matching и поиска замены в других chunks

### Requirement: Validation failures remain observable failures

Raw provider output SHALL сохраняться до validation вместе с provider status, response ID и usage, когда они доступны. Некорректный JSON/schema/status contract/provenance/citation SHALL давать validation_failed, конкретные ошибки и normalized_result=null. Valid normalized result SHALL создаваться только после всех deterministic checks либо непосредственно runtime gate. Система SHALL NOT автоматически ремонтировать candidate, повторять generation, превращать validation failure в insufficient_context или представлять candidate как успешно grounded. Refusal, incomplete, upstream error и timeout SHALL оставаться отдельными technical outcomes; timeout/неожиданный обрыв после dispatch SHALL сохранять unknown outcome, а не выдуманный success или no-call.

#### Scenario: Well-formed JSON contains fabricated provenance
- **WHEN** provider завершил structured response, но source/citation validation не прошла
- **THEN** raw model result остаётся доступным, processing outcome=validation_failed и normalized_result=null; retry/repair не выполняется

#### Scenario: Incomplete output or timeout
- **WHEN** provider output неполный либо dispatch завершился timeout
- **THEN** доступный partial output/diagnostics сохраняются, grounded result отсутствует, повторный call не выполняется

### Requirement: Evidence and manual review preserve separate claims of success

Локальное evidence SHALL сохранять exact question, frozen input identity/hashes, retrieval hits/text/metadata/scores, gate threshold/decision/reason, abstention origin, actual request/context, dispatch state, raw structured output, provider outcome/usage, deterministic validation и normalized result. Checkpoint SHALL записываться до dispatch; ошибка записи SHALL останавливать новые calls. Review SHALL быть связан с конкретным run/question set и отдельно сохранять sources_present, citations_present, citations_exact, answer_supported_by_citations=yes|partial|no, unsupported meaningful claims с notes и expected-fact correctness/coverage при необходимости. Pending/unavailable/N/A SHALL отличаться от yes/no; для корректного abstention presence=no, exactness/support=N/A. Автоматически вычислимые labels SHALL согласовываться с validation; semantic review SHALL NOT выводиться из exactness или source-path hits. Общий grounding score и LLM judge SHALL отсутствовать.

#### Scenario: Literal citation does not support a meaningful claim
- **WHEN** quote exact, но подтверждает иной сценарий или только часть answer
- **THEN** manual review фиксирует partial/no и неподдержанное утверждение независимо от успешной deterministic validation; correctness/coverage оцениваются отдельно

#### Scenario: Evidence write fails before dispatch
- **WHEN** невозможно сохранить checkpoint до generation
- **THEN** call не отправляется; отчёт не показывает его как завершённый

#### Scenario: Review has not been completed
- **WHEN** run сохранён, но semantic labels ещё не заполнены
- **THEN** report показывает pending без автоматического присвоения support=yes

### Requirement: CLI reports expose the frozen experiment without new calls

CLI SHALL предоставлять один frozen eval и read-only report с выбором Qxx, подробным --full и компактным --video. Report SHALL работать по собственному evidence без API key, provider calls, исходного index или baseline folder. Answered video SHALL показывать QUESTION -> GATE -> ANSWER -> SOURCES -> CITATIONS -> VALIDATION -> SEMANTIC SUPPORT; Q10 video SHALL показывать QUESTION -> best score -> threshold -> GATE FAIL -> GENERATION CALL: NO -> deterministic abstention. Model abstention SHALL показывать PASS, выполненный call и origin. Invalid candidate SHALL явно обозначаться как непроверенный, без успешного grounded answer. Summary SHALL раздельно считать исходы и review status без общего score.

#### Scenario: Offline video of gate abstention
- **WHEN** report --question Q10 --video читает завершённое evidence runtime abstention
- **THEN** показывает best score, 0.50, FAIL, GENERATION CALL: NO и фиксированный ответ без вызова provider

#### Scenario: Conclusions are scoped to frozen evidence
- **WHEN** пользователь читает итоговый report или Day README
- **THEN** указано, что reused Day 22 vectors изолируют answer contract, threshold связан с теми же questions, один run не является независимым retrieval benchmark и не доказывает универсальную relevance, semantic support или correctness; только реально проверенные результаты представлены как факты
