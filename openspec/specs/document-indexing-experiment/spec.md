# document-indexing-experiment Specification

## Purpose

Обеспечивает учебную индексацию инженерного corpus текущего repository и наблюдаемое сравнение двух детерминированных способов представления документов без выводов о качестве retrieval.

## Requirements

### Requirement: Both strategies use one explicit corpus snapshot

Система SHALL читать только явно перечисленные в manifest 22 файла согласованного тематического corpus: пять README, четыре актуальных OpenSpec specs, восемь backend Python files и пять Android Kotlin files о persistence и task state. Для одного comparison run система SHALL один раз подготовить snapshot UTF-8 текста с нормализованными LF, сохраняя содержимое, порядок строк и отступы. Обе стратегии SHALL использовать этот snapshot и одинаковую конфигурацию embeddings. Manifest, source hashes и config provenance SHALL быть доступны в сохранённом индексе. Система SHALL NOT автоматически расширять corpus до всего repository, архивов, runtime evidence, секретов или generated files.

#### Scenario: Indexing consumes identical source contents
- **WHEN** выполняется build обеих стратегий, а исходный рабочий файл меняется после подготовки snapshot
- **THEN** обе стратегии используют сохранённый ранее одинаковый текст и corpus hash
- **AND** новый текст участвует только в новом явном запуске

#### Scenario: Corpus input is invalid
- **WHEN** manifest содержит отсутствующий, повторный, неподдерживаемый или выходящий за repository файл либо текст не декодируется как UTF-8
- **THEN** подготовка завершается явной ошибкой до embedding calls без молчаливого пропуска файла

### Requirement: Fixed-size chunking uses a reproducible token budget

Fixed-size strategy SHALL использовать общий tokenizer/config, максимальный размер 500 tokens и целевой overlap 50 tokens внутри каждого файла. Размер SHALL измеряться по точному тексту отдельного chunk, который будет отправлен embedder. Допускается приближённый выбор окна/overlap по source character offsets с повторным подсчётом exact substring; идеальное заполнение окна не требуется; превышение token limit, искажение текста, пробелы в покрытии непробельного текста и отсутствие продвижения SHALL NOT допускаться. Границы SHALL NOT подстраиваться под смысл, headings или declarations. Последний chunk может быть короче; полностью пробельные chunks SHALL NOT сохраняться.

#### Scenario: Source contains Cyrillic and emoji
- **WHEN** текст с кириллицей и emoji делится на окна и перекрывающиеся suffixes
- **THEN** chunk остаётся точной подстрокой snapshot с целыми Unicode-символами и содержит не более 500 tokens
- **AND** следующий chunk продвигается без потери текста, искусственных replacement characters или повторения последнего окна

#### Scenario: Repeated preparation is stable
- **WHEN** одинаковый snapshot обрабатывается повторно с одинаковой chunking configuration
- **THEN** порядок, текст chunks, metadata и chunk IDs совпадают

### Requirement: Structure-aware deterministic chunking uses ordinary source boundaries

Стратегия SHALL называться `structure-aware deterministic chunking` и SHALL определять границы обычным кодом: Markdown headings/sections, Python declarations и Kotlin file/formatting boundaries. Она SHALL соблюдать тот же maximum 500 tokens и применять тот же token-based fallback с целевым overlap 50 для oversized неделимого блока. Между самостоятельными структурными блоками overlap SHALL отсутствовать. Система SHALL сохранять комментарии, decorators, imports и прочие непробельные участки текста. Kotlin formatting heuristic SHALL NOT представляться полноценным выделением declarations или semantic chunking; модель SHALL NOT выбирать границы.

#### Scenario: Markdown contains a code example with headings
- **WHEN** Markdown содержит headings внутри fenced code и вложенные Requirement/Scenario sections
- **THEN** headings внутри fence не создают sections, а реальные родительские и дочерние разделы получают корректную принадлежность
- **AND** помещающийся раздел сохраняется целиком, большой делится по доступной структуре, затем общим fallback

#### Scenario: Python has decorators and nested functions
- **WHEN** обрабатывается declaration с decorators, nested function и соседними комментариями
- **THEN** decorators относятся к declaration, nested function остаётся частью родителя и текст между declarations не теряется
- **AND** oversized declaration может быть разделена только с явным split reason

#### Scenario: Kotlin block exceeds the budget
- **WHEN** Kotlin file или блок форматирования не помещается в 500 tokens
- **THEN** используются доступные formatting boundaries и затем token fallback с отмеченным split reason
- **AND** отчёт не заявляет гарантии целостности Kotlin functions/classes

### Requirement: Chunks expose a small traceable metadata contract

Каждый сохранённый chunk SHALL иметь `chunk_id`, `source`, `source_type`, `title`, `section`, `strategy`, `ordinal`, `start_line`, `end_line`, `token_count`, `text_hash`, `split_reason`. Source SHALL быть repository-relative path с `/`; source_type SHALL принадлежать небольшому набору `documentation/spec/backend/android`. Title SHALL быть заголовком Markdown либо именем файла. Ordinal SHALL задавать порядок внутри source/strategy; line numbers SHALL быть 1-based inclusive относительно нормализованного snapshot. Section SHALL честно обозначать структурную принадлежность либо file-level/common parent при пересечении нескольких разделов. Chunk ID SHALL быть стабильным для одинакового источника и chunking configuration, различать повторяющийся текст в разных местах и не зависеть от времени live run. Стабильность после редактирования source не гарантируется.

#### Scenario: Fixed-size crosses several sections
- **WHEN** окно пересекает несколько Markdown sections либо Python declarations
- **THEN** metadata указывает общего родителя или уровень файла, не приписывая всё окно одной дочерней declaration
- **AND** inspect показывает точный исходный диапазон и текст

#### Scenario: Identical text occurs at different positions
- **WHEN** два chunks содержат одинаковый текст в разных исходных местах
- **THEN** их text_hash совпадает, но chunk IDs различаются и обе позиции доступны для inspect

### Requirement: Embeddings are isolated and validated

Embedding stage SHALL преобразовывать точный chunk text в vector через отдельный Embedder без generation, context enrichment или изменения metadata. Обе стратегии SHALL использовать OpenAI `text-embedding-3-small` с 1536 dimensions и одинаковыми параметрами. Provider adapter SHALL сохранять правильную связь chunk/vector и проверять количество и размерность embeddings до признания build завершённым. API key SHALL использоваться только в backend environment и SHALL NOT попадать в corpus, index, отчёт или Git. Fake embeddings SHALL использоваться только в offline tests и SHALL NOT предъявляться как результат live indexing.

#### Scenario: Embedding input is the inspected text
- **WHEN** выбранный chunk передаётся provider
- **THEN** input совпадает с текстом chunk в preview, а возвращённый vector связан с этим chunk

#### Scenario: Provider output is incomplete or malformed
- **WHEN** provider завершился ошибкой либо количество/размерность vectors не соответствует входу
- **THEN** build завершается ошибкой, неполный результат не доступен как готовый index и ошибка не заменяется fake vector

### Requirement: Completed indexes persist independently of the process

Система SHALL сохранять snapshot, текст chunks, metadata, vectors и build provenance в локальный SQLite file внутри игнорируемого каталога Day 21. Готовый run SHALL содержать результаты обеих стратегий; неудачная сборка SHALL NOT повреждать ранее завершённую. Новая сборка SHALL быть явной полной пересборкой. Если одна из стратегий или запись не завершилась, CLI SHALL завершаться с ошибкой и SHALL NOT выдавать неполный build за успешный. Промежуточная публикация одной стратегии и восстановление незавершённых runs не требуются.

#### Scenario: Index is reopened without provider access
- **WHEN** новый процесс открывает готовый SQLite file без API key и доступа к исходным рабочим файлам
- **THEN** текст, metadata, vectors, provenance и сохранённые результаты сравнения читаются из индекса без provider calls

#### Scenario: Writing a build fails
- **WHEN** сохранение run завершается ошибкой до commit
- **THEN** частичные строки не становятся готовым индексом, а ранее завершённые сборки остаются читаемыми

### Requirement: Comparison reports representation differences without retrieval claims

Сравнение SHALL проверять совпадение corpus snapshot, tokenizer, token limit и embedding configuration. Оно SHALL показывать chunk count, min/median/max token_count, сумму токенов точных embedding inputs (total embedded tokens завершённого build) и fallback count для каждой стратегии. В preview сумма SHALL называться планируемым объёмом, а не фактически отправленными токенами. Дополнительные p95/coverage/crossing/preservation метрики не являются обязательными и не блокируют готовность Day 21. Representative source locations SHALL быть зафиксированы до получения результатов; просмотр SHALL включать все chunks обеих стратегий, пересекающие эти locations. Timing, provider-reported usage, число embedding calls и SQLite size SHALL показываться только как наблюдения данного run; отсутствующий usage SHALL оставаться unknown. Система SHALL NOT объявлять superiority по retrieval quality или выводить производительность chunking из одного внешнего API run.

#### Scenario: Corpus or model differs
- **WHEN** пользователь пытается сопоставить builds с разным corpus hash, tokenizer/limit либо embedding configuration
- **THEN** CLI сообщает несовместимость и не формирует обычное сравнение как контролируемый эксперимент

#### Scenario: Report shows structural preservation
- **WHEN** structure-aware сохраняет выбранный блок целиком, а fixed-size разрывает его
- **THEN** отчёт показывает конкретные диапазоны и representation difference без вывода о качестве retrieval
- **AND** timing и usage остаются отдельными характеристиками run

### Requirement: CLI demonstrates indexing without expanding Day 21 scope

CLI SHALL предоставлять corpus inventory, offline preview двух стратегий, explicit live build обеих стратегий, compare и inspect по source/chunk ID. Corpus/preview SHALL NOT вызывать embedding provider; после подготовки tokenizer assets они SHALL работать offline. Compare/inspect сохранённого индекса SHALL NOT требовать backend server, Android, API key или повторной генерации embeddings. Day 21 SHALL NOT добавлять retrieval, cosine search, FAISS, reranking, LLM generation, agent, MCP, Android UI или новую сервисную инфраструктуру.

#### Scenario: Preview makes chunking visible without OpenAI
- **WHEN** пользователь запускает preview без API key до live build
- **THEN** для заранее выбранного location видны исходный участок с source/номерами строк, затем полный текст всех пересекающих его fixed-size chunks, затем structure-aware chunks с core metadata, section, token_count и split_reason
- **AND** preview не требует embeddings, SQLite или running backend и не заменяет тексты только числовыми метриками

#### Scenario: User records the demonstration
- **WHEN** пользователь последовательно показывает corpus, preview, live build, compare и inspect в новом процессе
- **THEN** видны corpus → chunks двух стратегий → actual embeddings с metadata → persisted index
- **AND** полный vector не загромождает default output: показываются размерность и короткий фрагмент с возможностью полного просмотра

### Requirement: Documentation distinguishes measured evidence from planned outcomes

Day README SHALL кратко описывать эксперимент, проверяемые свойства и только фактические результаты либо отсутствие live проверки. Root README SHALL содержать ровно одну относительную ссылку на Day 21 README в порядке дней. Команды, dependencies и setup SHALL находиться в README компонентов/scripts. Offline checks SHALL подтверждать chunking invariants и storage round trip, но SHALL NOT представляться подтверждением semantic usefulness embeddings или качества будущего dev-agent.

#### Scenario: Implementation exists before live indexing
- **WHEN** offline checks завершены, а live indexing ещё не выполнен
- **THEN** документация прямо отмечает отсутствие live результата и не выдумывает tokens, стоимость, responses или превосходство стратегии
