## Purpose

Обеспечивает наблюдаемый первый RAG-запрос по сохранённому repository corpus и контролируемое сравнение с direct generation, позволяя вручную различать поиск фактов, их передачу модели и качество ответа на фиксированном наборе вопросов.

## ADDED Requirements

### Requirement: Retrieval consumes a pinned persisted index

Day 22 SHALL использовать read-only Day 21 run `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d` и только 226 structure-aware chunks для основного эксперимента. Тексты, metadata и vectors SHALL читаться из snapshot без повторной индексации, document embedding calls или подстановки актуальных файлов. Выбранные run/hash/strategy/config SHALL быть видимы в evidence. Отсутствие, повреждение или несовместимость индекса SHALL давать явную ошибку без fallback на latest run, другую strategy или fake vectors.

#### Scenario: Source files have changed after indexing
- **WHEN** поиск использует pinned build, а рабочий source file изменён или отсутствует
- **THEN** поиск и context assembly используют сохранённый текст и provenance выбранного snapshot без provider calls для документов

#### Scenario: Pinned build is unavailable
- **WHEN** SQLite не содержит выбранный run либо его vectors/config непригодны
- **THEN** retrieval прекращается с явной ошибкой до query embedding и RAG generation, без создания индекса

### Requirement: Query search exposes an unfiltered cosine Top-5

Для непустого question retrieval SHALL embedding-ить исходный question конфигурацией document index: OpenAI `text-embedding-3-small`, 1536 dimensions, float. Baseline SHALL вычислять cosine против каждого stored vector, сортировать по убыванию score со стабильным разрешением ties и возвращать ровно Top-5 для валидного индекса. Similarity threshold, reranking, query rewriting, hybrid search, фильтрация коротких chunks и добавление соседей SHALL отсутствовать. Невалидные dimension, nonfinite values и zero-norm vectors SHALL давать ошибку, не молчаливый пропуск.

#### Scenario: Search runs without generation
- **WHEN** пользователь явно запускает `search` с валидным question/index
- **THEN** выполняется один query embedding request и ноль generation requests; вывод показывает пять rank/score/source/section/line-range/chunk-preview и позволяет посмотреть полные chunks

#### Scenario: No answer exists in the corpus
- **WHEN** question не имеет ответа в indexed corpus, но embedding успешен
- **THEN** retrieval всё равно возвращает ближайшие пять chunks без обещания достаточности evidence и без специального threshold для negative control

### Requirement: Context assembly preserves retrieved evidence

RAG input SHALL содержать исходный question и полные тексты Top-5 в rank order, разделённые блоками `[S1]`–`[S5]` с source, section и исходными строками. Preview truncation SHALL NOT менять model input. Сохранённый actual input SHALL позволять проверить отсутствие потери или подмены retrieved facts. Embedding vectors, similarity scores, expected facts, acceptable sources, question difficulty и negative-control marker SHALL NOT передаваться generation model. Retrieved sources SHALL обозначаться как данные, а не инструкции к исполнению.

#### Scenario: A long preview is shortened in the terminal
- **WHEN** CLI сокращает preview одного hit
- **THEN** полный сохранённый chunk остаётся в actual RAG input и evidence с тем же source label

#### Scenario: Evaluation metadata accompanies a question
- **WHEN** eval загружает question вместе с expectations и labels
- **THEN** generation получает только общий instruction и question/context, без оценочных подсказок или retrieval scores

### Requirement: Direct and RAG share generation behavior

Оба режима SHALL получать идентичный question, одну и ту же общую instruction и одинаковую generation configuration: `gpt-5.6`, reasoning none, max output 600 tokens, plain text, store false, truncation disabled, без tools и retries. Instruction SHALL просить краткий русский ответ, запрещать выдуманные project-specific details, требовать использовать и цитировать предоставленные `[S#]` blocks и явно обозначать недостаточность доступных сведений. Основным различием SHALL быть отсутствие project context в direct и присутствие Top-5 в RAG. Sessions, history между вопросами, Memory/Profile и ответы другой ветки SHALL NOT добавляться. Defaults прежних дней SHALL сохраняться.

#### Scenario: A paired question is generated
- **WHEN** eval обрабатывает один question
- **THEN** обе ветки используют одинаковые instructions/config/question, RAG добавляет только retrieved context, а direct не получает результаты RAG или index contents

#### Scenario: Generation is incomplete or fails
- **WHEN** provider возвращает incomplete, refusal, error либо исход request неизвестен
- **THEN** outcome сохраняется отдельно, не выдаётся за completed answer и не вызывает скрытый retry, увеличение output budget или замену результата

### Requirement: A frozen question set spans increasing evidence difficulty

Versioned question set SHALL содержать ровно десять repository-specific questions: пять local, три cross-source, один multi-fact и один negative control. Каждый SHALL иметь id, question, difficulty, атомарные expected_facts со стабильными fact ids и acceptable_sources из pinned corpus; Q10 SHALL иметь negative_control=true и пустой acceptable_sources. Источники SHALL покрывать documentation/spec, backend Python и Android Kotlin. Формулировки и expectations SHALL быть зафиксированы до первого live eval, snapshot вопросника и его hash SHALL сохраняться в evidence. Ground truth SHALL NOT корректироваться после ответов для улучшения результата.

#### Scenario: The negative control is evaluated
- **WHEN** Q10 спрашивает утверждённые RPO/RTO восстановления Day 07 conversation SQLite из backup
- **THEN** expectation требует признать недостаточность indexed information без вымышленных значений, а source-path metric равен N/A

#### Scenario: Questions are frozen before live
- **WHEN** offline validation question set завершена
- **THEN** доступны все десять вопросов, факты, difficulty и допустимые source paths до любых semantic live trials этого набора

### Requirement: Evaluation separates path diagnostics and manual fact review

Отчёт SHALL вычислять только вспомогательный `source_path_hit@5` как пересечение acceptable source paths и retrieved paths. Он SHALL NOT трактовать path hit как найденный факт. Для каждого expected fact сохранённая ручная таблица SHALL иметь `expected_fact_in_retrieved_context`, `direct_answer_covers_fact`, `rag_answer_covers_fact` со значениями yes/partial/no. Для существенных утверждений RAG SHALL отдельно сохраняться ручное `grounded_in_retrieved_context` yes/no с текстом утверждения и evidence/note; лишние утверждения SHALL проверяться даже вне expected facts. До review поля SHALL оставаться null/pending, а недоступный ответ SHALL помечаться unavailable, не превращаться в семантический no. Semantic evaluator, LLM judge и deterministic semantic fact checker SHALL отсутствовать.

#### Scenario: Correct file but wrong fragment is retrieved
- **WHEN** source_path_hit@5=true, но нужный expected fact отсутствует в retrieved chunks
- **THEN** ручное expected_fact_in_retrieved_context=no остаётся видимым независимо от path hit

#### Scenario: One answer mixes supported and unsupported facts
- **WHEN** RAG покрывает один expected fact, пропускает другой и добавляет неподдержанную деталь
- **THEN** review сохраняет разные outcomes по фактам и отдельное unsupported claim без общего автоматического success verdict

### Requirement: Diagnosis follows the location of missing evidence

Review SHALL различать retrieval failure (факт есть в pinned corpus, но отсутствует в Top-5), context assembly defect (факт найден, но потерян до actual input), generation failure (факт передан, но пропущен/искажён) и faithfulness failure (добавлены неподдержанные context утверждения). Отсутствие ответа в corpus SHALL называться knowledge coverage/no-answer case, а не retrieval failure. Partial coverage SHALL разбираться по фактам; provider/storage failures SHALL учитываться отдельно. Для Q10 отсутствие RPO/RTO в retrieved context SHALL не означать провал retrieval при корректном no-answer outcome.

#### Scenario: Retrieved fact disappears from the prompt
- **WHEN** факт присутствует в сохранённом hit, но отсутствует в actual model input
- **THEN** причина отмечается как context assembly defect, не ошибка модели или поиска

#### Scenario: No-answer control honestly abstains
- **WHEN** Q10 получает непустой Top-5 без утверждённых RPO/RTO и RAG сообщает об отсутствии достаточных сведений
- **THEN** review фиксирует no-answer case и соответствие expectation, а не ложный retrieval failure

### Requirement: One live evaluation preserves every observed outcome

После offline checks и фиксации question set основной live experiment SHALL состоять из одного полного eval: по одному query embedding и одной direct/RAG generation на каждый из десяти вопросов, всего 10 embedding и 20 generation requests при отсутствии препятствующих технических ошибок. Предварительные semantic live runs этих вопросов для настройки K, prompt, expectations или output budget SHALL NOT выполняться. Плохие ответы SHALL сохраняться и анализироваться без повторов ради улучшения. Actual attempted/completed/not-dispatched/unknown counts SHALL отражать реальность; failed prerequisite SHALL не заменяться fake input. Автоматические retries, resume/replay и повтор полного eval SHALL отсутствовать.

#### Scenario: A completed answer is poor
- **WHEN** модель дала неверный ответ или retrieval не нашёл expected fact
- **THEN** запуск продолжает оставшиеся вопросы с прежней конфигурацией и сохраняет ошибку как evidence без повторной попытки

#### Scenario: Query embedding fails
- **WHEN** embedding одного question завершается технической ошибкой
- **THEN** этот outcome сохраняется, RAG generation для question отмечается not_dispatched, direct и независимые оставшиеся вопросы могут быть выполнены однократно, а report не заявляет 30 успешных calls

### Requirement: Saved reports are independent of provider access

CLI SHALL предоставлять `search`, `ask --mode direct|rag`, `eval`, `report` без FastAPI server и Android. Evidence SHALL сохранять run/config, frozen expectations, Top-5 scores/provenance/full texts, actual inputs, ответы/status/usage и actual call counts; manual review SHALL храниться отдельно от исходных observations. `report` SHALL читать сохранённые данные без API key, provider calls, исходного SQLite и рабочих source files, без перезаписи raw evidence. Вывод одного вопроса SHALL показывать QUESTION → RETRIEVED TOP-5 → DIRECT ANSWER → RAG ANSWER → EXPECTED FACTS / REVIEW; итоговая таблица SHALL охватывать все десять вопросов с difficulty и статусом review. Report SHALL явно отмечать чтение сохранённого запуска.

#### Scenario: Video is recorded from saved evidence
- **WHEN** пользователь открывает report одного вопроса, Q10 и сводку без ключа и доступа к provider
- **THEN** видны фактические тексты, scores, provenance, answers и review без новых embeddings/generation

#### Scenario: Evidence cannot be saved
- **WHEN** output location недоступна до dispatch либо сохранение evidence перестало работать
- **THEN** новые provider calls не отправляются, ранее сохранённые observations не затираются, CLI сообщает техническое ограничение

### Requirement: Documentation bounds conclusions to the observed run

Day README SHALL кратко описывать эксперимент, проверяемые свойства и фактические результаты либо отсутствие live проверки. Root README SHALL содержать одну упорядоченную ссылку на Day 22 README; setup/commands SHALL находиться в backend/scripts README. Выводы SHALL относиться только к выбранным десяти вопросам и одному сохранённому run, без общего «RAG лучше», superiority structure-aware, оптимальности Top-5 или гарантии отсутствия галлюцинаций. Credentials SHALL читаться только из backend environment/local ignored .env и SHALL NOT попадать в evidence, prompts или Git; локальный index/evidence SHALL оставаться игнорируемыми.

#### Scenario: Only offline checks have completed
- **WHEN** реализация прошла offline tests, а полный live eval ещё не выполнен
- **THEN** README не сообщает вымышленные answers/metrics и прямо отмечает отсутствие live результата
