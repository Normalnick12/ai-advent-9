## Purpose

Позволяет Android-разработчику подключить постоянную локальную Markdown-документацию и объяснить выбранный Kotlin-файл с учётом найденных архитектурных правил, проверяемых источников и явно обозначенных границ знания.

## ADDED Requirements

### Requirement: Extended commands preserve the standalone legacy workflow

Существующая утилита SHALL предоставлять операции preview/index/status для Knowledge, search с mode vector/text и extended explain с явным retrieval none/vector/text. Она SHALL работать без backend, Android UI, нового агента/MCP/server и облачных API. Прежний запуск Day 27 без subcommand SHALL сохранять свой code-only prompt, формат facts/assumptions/limitations и отсутствие persistent writes. Extended режим SHALL принимать один выбранный Kotlin-файл через существующую границу Workspace, без чтения соседних исходников. Вопрос/query SHALL приниматься аргументом или однократным интерактивным вводом; неверный ввод, EOF и отсутствие TTY без аргумента SHALL завершаться безопасной ошибкой.

#### Scenario: Legacy invocation still works
- **WHEN** запущена прежняя команда Day 27 с допустимыми workspace/file/model
- **THEN** выполняется прежнее однофайловое объяснение без чтения Knowledge и без embedding calls

#### Scenario: Extended baseline does not access knowledge
- **WHEN** extended explain запущен с retrieval none
- **THEN** используется общий extended answer contract, но документы и embeddings не запрашиваются
- **AND** передача Knowledge в этом режиме отвергается как неоднозначный ввод

#### Scenario: Search without a Kotlin file
- **WHEN** переданы Knowledge, query и один из mode vector/text
- **THEN** возвращаются найденные фрагменты без Workspace и без generation

### Requirement: Knowledge selection is visible and explicitly accepted

Knowledge path SHALL определяться как --knowledge > LAA_KNOWLEDGE. Пустое явное значение SHALL отклоняться. Extended none SHALL игнорировать environment Knowledge и отвергать явный --knowledge; legacy SHALL NOT читать эту переменную. Preview/status/search SHALL NOT быть обязательными перед explain: freshness проверяется автоматически.

#### Scenario: Daily explanation with configured Knowledge
- **WHEN** задан LAA_KNOWLEDGE и выполнен первый index
- **THEN** RAG explain использует этот путь без обязательных предварительных команд; явный --knowledge переопределяет environment

Утилита SHALL позволять подключить локальный каталог Markdown без ручного создания manifest. Preview SHALL показывать точный список candidate relative paths, исключения и added/changed/deleted/unchanged, не записывая данные и не вызывая модель. Selection SHALL поддерживать directory mode, явный список отдельных .md-файлов, исключение файла/подкаталога и возврат к directory mode. Успешный index SHALL сохранять policy и approved set автоматически. Первое построение, изменение policy и добавление/удаление paths SHALL требовать явного принятия показанного набора через TTY либо документированный --yes; принятие SHALL относиться только к показанному snapshot. Обновление содержимого уже разрешённых файлов SHALL выполняться явным index без повторного вопроса после показа изменений.

#### Scenario: Connect a documentation directory
- **WHEN** пользователь запускает preview, затем принимает список при первом index
- **THEN** индексируются только перечисленные допустимые Markdown-файлы и сохраняется selection для следующих запусков

#### Scenario: Add a document without editing a manifest
- **WHEN** в directory-mode Knowledge появляется новый .md и пользователь запускает index
- **THEN** новый path показан как added и попадает в новый snapshot только после принятия списка

#### Scenario: Cancel or run non-interactively without acceptance
- **WHEN** требуется принятие, но пользователь отменяет его либо нет TTY и --yes
- **THEN** persistent data не изменяются и embedding/generation не вызываются

#### Scenario: Narrow selection and remember it
- **WHEN** пользователь принимает список отдельных файлов и exclusions
- **THEN** следующие операции без selection overrides используют эту policy
- **AND** неселекционированные документы не индексируются

### Requirement: Knowledge and Workspace are separate bounded filesystem inputs

Утилита SHALL индексировать только разрешённые обычные Markdown-файлы внутри канонического локального Knowledge root. Она SHALL NOT следовать symlinks/junctions/reparse points внутри root, индексировать Kotlin или сканировать Workspace для пополнения Knowledge. Discovery SHALL исключать собственный index/state и служебные каталоги с видимыми причинами. Явный запрещённый путь, traversal/ADS/неоднозначное имя, сетевой root, нечитаемый разрешённый источник и невалидный UTF-8 SHALL приводить к безопасному отказу. RAG explain SHALL отвергать совпадающие или вложенные Knowledge/Workspace roots после канонизации.

Объём SHALL ограничиваться 500 документами, 256 KiB raw на документ, 4 MiB raw суммарно, 4096 chunks и 10000 просмотренными directory entries. Превышение SHALL отвергать операцию без частичного результата. Пустой набор документов SHALL NOT создавать новый индекс. Это SHALL описываться как bounded access к невраждебной локальной файловой системе, не OS sandbox.

Index/state paths SHALL проходить отдельную проверку принадлежности Knowledge и отсутствия links/junctions/reparse points; исключение state из discovery SHALL NOT отменять эту проверку.

#### Scenario: Mixed directory
- **WHEN** Knowledge содержит выбранные .md, Kotlin, служебные папки и ссылку наружу
- **THEN** индексируются только допустимые разрешённые .md; исключения видны, содержимое ссылки и Kotlin не читается для индекса

#### Scenario: Overlapping roots
- **WHEN** RAG explain получает Knowledge внутри Workspace, Workspace внутри Knowledge или один root под двумя aliases
- **THEN** операция отклоняется до чтения Kotlin и inference

#### Scenario: Input exceeds bounds or cannot be verified
- **WHEN** один из объявленных лимитов превышен либо выбранный файл невозможно безопасно прочитать
- **THEN** операция завершается ошибкой без частично активированного индекса

#### Scenario: Linked index location
- **WHEN** index/state directory подменён ссылкой на другой каталог
- **THEN** чтение и запись индекса отклоняются без обращения к содержимому цели

### Requirement: Retrieval refuses stale or unverifiable knowledge

Status/search/RAG explain SHALL сравнивать текущий candidate set и content hashes разрешённых документов с committed snapshot и policy. Изменение/удаление выбранного файла, добавление непринятого candidate в directory mode, несовместимый chunking profile или невозможность проверить актуальность SHALL обозначаться как stale/unverifiable. Search/RAG explain SHALL прекращаться до embedding/chat; silent stale use, automatic reindex и fallback к code-only SHALL отсутствовать. Изменения исключённых файлов SHALL NOT влиять на актуальность.

#### Scenario: Same size and timestamp but different contents
- **WHEN** выбранный документ изменён с сохранёнными размером и mtime
- **THEN** несовпадающий hash обнаруживается, поиск блокируется и предлагается явный index

#### Scenario: Deleted or newly discovered document
- **WHEN** выбранный .md удалён либо новый candidate появился в directory mode
- **THEN** status показывает respective deleted/added, а RAG не использует старый snapshot

#### Scenario: Unselected file changes
- **WHEN** изменён документ вне сохранённой selection
- **THEN** snapshot остаётся current при неизменности всех разрешённых источников

### Requirement: Index rebuild is atomic and portable

Индекс SHALL сохраняться локально в SQLite с относительными source paths, section/line/character coordinates, chunk text/identity, vectors и configuration provenance. Полная перестройка SHALL публиковать только полностью проверенный snapshot. Сбой или изменение источников в ходе построения SHALL сохранять предыдущий committed index; смешивание поколений SHALL отсутствовать. Повторный index неизменного корпуса с тем же embedding/chunker fingerprint SHALL быть no-op без embeddings. Search SHALL открывать индекс read-only, не мигрировать его и не записывать историю. Неизвестная schema, повреждённые данные или busy writer SHALL давать явную безопасную ошибку.

#### Scenario: Interrupted rebuild
- **WHEN** часть embeddings получена, затем происходит ошибка API/валидации/записи
- **THEN** предыдущий committed snapshot не заменяется частичным

#### Scenario: Document changes during indexing
- **WHEN** прочитанный source snapshot уже отличается от файлов перед публикацией
- **THEN** новый index не активируется и пользователь получает требование повторить index явно

#### Scenario: Reopen after moving knowledge
- **WHEN** Knowledge вместе с индексом перенесена в другой локальный каталог поддерживаемой ОС
- **THEN** при совпадающих files/profiles индекс открывается без зависимости от старого абсолютного пути и без re-embedding

### Requirement: Markdown chunks retain verifiable source coordinates

Каждый chunk SHALL соответствовать непрерывному slice исходного Markdown после UTF-8 BOM/newline normalization и иметь source hash, section path, line/character bounds и однозначный ID. Заголовки внутри fenced code SHALL NOT становиться разделами; одинаковые заголовки в разных местах SHALL различаться координатами. Документированный bounded fallback SHALL делить слишком большой блок без утверждения, что character cap равен token cap. Citations SHALL ссылаться на реально переданные slices, а не на реконструированный текст.

#### Scenario: Nested and repeated headings
- **WHEN** документ содержит вложенные и повторяющиеся ATX headings и fenced examples
- **THEN** chunks имеют проверяемые разделы и координаты, а headings внутри fences не меняют section path

#### Scenario: Short document and oversized paragraph
- **WHEN** индексируются короткий документ с heading и документ с блоком больше chunk limit
- **THEN** первый сохраняет section identity, второй получает bounded source slices с явной fallback metadata

### Requirement: Embeddings are local and configuration compatible

Векторизация SHALL выполняться только установленной локальной моделью Ollama с подтверждённой embedding capability, через controlled local-only server. Cloud-model metadata, remote URL, proxy, redirect, автоматическое скачивание и cloud fallback SHALL быть запрещены. Входы embedding SHALL NOT молча обрезаться. Ответ SHALL проверяться на число vectors, согласованную dimension, finite components и ненулевую норму.

Vector index/query SHALL использовать совместимый fingerprint модели, installed digest, размерности, нормализации и document/query input profile. Несовпадение SHALL требовать явного rebuild даже при одинаковой dimension. OpenAI embeddings и query vectors Week 5 SHALL NOT переиспользоваться как локальные. Transport errors SHALL NOT приводить к retry/repair или выводу содержимого upstream error.

#### Scenario: Same dimension but different model
- **WHEN** установленный digest или input profile отличается от index metadata при совпадающей размерности
- **THEN** vector retrieval отклоняется до query embedding и generation

#### Scenario: Invalid or truncated embedding request
- **WHEN** endpoint сообщает превышение окна либо возвращает неверные/нечисловые/нулевые vectors
- **THEN** index/query завершается ошибкой без принятия неполного результата

#### Scenario: Local transport boundary
- **WHEN** настроен внешний proxy, получен redirect или модель имеет remote metadata
- **THEN** никакой внешний запрос не выполняется; запрещённая модель/redirect дают безопасную ошибку

### Requirement: Vector and text search are independently observable

Оба режима SHALL искать в одном актуальном snapshot и возвращать rank, method-specific score, source/section/lines/chunk ID и snippet. Default top-k SHALL быть 4 с явным диапазоном 1..10 и стабильным разрешением равных scores. Vector SHALL ранжировать по cosine; text SHALL искать literal case-insensitive terms/идентификаторы, сохраняя underscore в identifier, без интерпретации пользовательского ввода как query operators. Пунктуация/tokenization и отсутствие stemming/substring guarantees SHALL быть документированы. Text search SHALL работать без Ollama и без установленной embedding-модели. Search SHALL NOT вызывать generation, смешивать ранжирования или выдавать score за вероятность правильности.

#### Scenario: Exact identifier without inference
- **WHEN** text query содержит PaymentGateway или session_id и такие tokens есть в corpus
- **THEN** возвращаются соответствующие matching chunks и HTTP calls отсутствуют

#### Scenario: Query syntax is data
- **WHEN** query содержит кавычки, NOT, двоеточия или SQL-like текст
- **THEN** выполняется безопасный literal term search, без выполнения операторов или изменения базы

#### Scenario: No matching terms or missing factual answer
- **WHEN** text tokens не совпадают либо vector нашёл только тематически близкие chunks без нужного факта
- **THEN** text может вернуть пустой список, а непустой vector result не маркируется как подтверждённый ответ

#### Scenario: Oversized query
- **WHEN** query превышает 2000 code points либо содержит больше 64 text-search terms
- **THEN** операция отклоняется до retrieval/inference без скрытого сокращения query

### Requirement: Explain uses bounded retrieved context without hiding omissions

Explain retrieval SHALL детерминированно объединять исходный вопрос, basename Kotlin без расширения и CamelCase words без дублей. Generation SHALL отвечать на исходный question. Parser/AST/LLM rewrite и чтение других файлов SHALL отсутствовать. Raw question SHALL ограничиваться 2000 code points, enriched query — 4096, без скрытой обрезки.

#### Scenario: Generic question
- **WHEN** выбран CheckoutCoordinator.kt и задано «Что делает этот класс?»
- **THEN** vector/text получают также CheckoutCoordinator и Checkout Coordinator; generation question остаётся исходным

Extended explain SHALL передавать выбранный Kotlin и только authoritative retrieved chunks в один chat request. Общий body SHALL ограничиваться 24 KiB, Kotlin — 16 KiB, question — 2000 code points, response — 256 KiB; исходный Kotlin SHALL NOT автоматически сокращаться. Контекст SHALL упаковываться целыми chunks с видимыми selected/omitted counts. Если исходный запрос не помещается или ни один найденный chunk не помещается, SHALL быть explicit budget error без chat. Default generation budgets SHALL быть 8192/2048; bytes SHALL NOT выдаваться за точные model tokens или доказательство отсутствия server truncation.

#### Scenario: Some retrieved chunks do not fit
- **WHEN** только часть ранжированных целых chunks помещается в полный body
- **THEN** отправляются помещающиеся chunks, число пропусков видно, validator принимает ссылки только на отправленные chunks

#### Scenario: No retrieved chunk fits
- **WHEN** retrieval нашёл chunks, но все исключены бюджетом
- **THEN** возвращается context budget error, не ложное сообщение об отсутствии знания

### Requirement: Explanation separates code rules applications and uncertainty

Extended ответ SHALL содержать code_observations, documented_rules, applications, assumptions, limitations и knowledge_status. Code observations SHALL иметь непустые text, уникальные IDs и валидные уникальные integer Kotlin lines (bool запрещён). Rules SHALL иметь уникальные IDs, text и точные непустые цитаты длиной до 400 characters из chunks фактического context. Application SHALL иметь text и непустые ссылки на существующие code observation IDs и rule IDs. Unknown IDs/fields, malformed JSON, неверные диапазоны и неподтверждённое завершение SHALL отвергаться без repair/retry. Paths/sections SHALL подставляться из authoritative index metadata.

Rules SHALL представляться как документированные соглашения, applications — как интерпретация применимости, не доказанная истинность. Инструкция SHALL требовать учитывать scope правил, обозначать конфликт с кодом и не придумывать реализации зависимостей, callers или гарантии атомарности. Механическая валидация SHALL NOT объявляться semantic correctness.

#### Scenario: Supported architectural interpretation
- **WHEN** модель связала observation по коду с правилом из переданного chunk
- **THEN** пользователь видит отдельно Kotlin lines, Markdown section/citation и interpretation с обеими опорами

#### Scenario: Fabricated or non-context source
- **WHEN** rule цитирует неизвестный chunk, неотправленный hit или неточную quote
- **THEN** объяснение не принимается и источники не исправляются автоматически

#### Scenario: A real quote belongs to another scenario
- **WHEN** literal quote корректна, но ручной reviewer обнаруживает неприменимость правила
- **THEN** mechanical PASS остаётся отдельным outcome, а semantic review фиксирует unsupported application

### Requirement: Missing knowledge is distinct from technical failure

Retrieval none SHALL давать knowledge_status=not_requested с пустыми rules/applications. Empty hits SHALL давать no_candidates с пустыми rules/applications и непустым limitation. При candidates_provided модель SHALL иметь возможность признать, что chunks не поддерживают архитектурный ответ, с пустыми rules/applications и объяснённым недостатком контекста. Во всех случаях разрешены подтверждённые code observations. Ошибка индекса/embeddings/completion SHALL NOT подменяться нормальным ответом без RAG.

Knowledge status SHALL соответствовать фактическому режиму/context, а не свободному выбору модели; mismatch SHALL отклоняться. Для none SHALL требоваться непустой limitation о границе code-only анализа. Полностью пустое объяснение без limitation SHALL NOT приниматься.

#### Scenario: No documentation requested
- **WHEN** A выполняется с retrieval none
- **THEN** не придумываются документированные правила и ответ явно объясняет границы code-only анализа

#### Scenario: Retrieved documents are irrelevant
- **WHEN** B получает только distractors
- **THEN** допустим валидный отказ от architectural application при сохранении фактов видимого кода

### Requirement: Retrieved documents and source comments remain untrusted data

Инструкция, selected Kotlin/comments и retrieved Markdown SHALL быть структурно разделены. Data SHALL NOT становиться system/developer instructions, исполняемыми командами или tool requests. Приложение SHALL NOT выполнять действия из model output и SHALL безопасно отображать terminal text. Offline adversarial fixtures SHALL проверять реальный payload, неизменность доверенных instructions и отсутствие data-induced side effects. Успех этих проверок SHALL NOT объявляться доказательством невосприимчивости LLM к prompt injection.

#### Scenario: Injection in Markdown and Kotlin
- **WHEN** документы или комментарии содержат fake roles, ignore-instructions и команды записи/отправки
- **THEN** они остаются в data fields, system instruction неизменна и приложение не выполняет команды/внешние запросы

#### Scenario: Model returns control sequences or unsupported instructions
- **WHEN** ответ содержит terminal control characters или призыв выполнить команду
- **THEN** терминал получает безопасно отрендеренный текст, никакая команда не запускается

### Requirement: Persistence is limited to approved knowledge

Приложение SHALL сохранять только approved Knowledge/index/configuration provenance. Оно SHALL NOT сохранять Workspace code, questions, query vectors, prompts, answers, history и raw upstream errors в index/cache/logs/reports. Search/preview/answer SHALL показывать запрошенные материалы только в терминале; diagnostic metrics SHALL быть без содержимого и пользовательских путей. Документация SHALL требовать размещения пользовательских данных вне Git и объяснять, что index содержит читаемые тексты, а shell/server logs не контролируются CLI. Git и результаты эксперимента SHALL содержать только implementation, synthetic fixtures и content-free metrics/verdicts.

#### Scenario: Success and reflected upstream failure
- **WHEN** explain завершён либо upstream error содержит отражённый вопрос/исходник
- **THEN** index остаётся read-only, content artifacts не создаются, диагностика не отражает private text

#### Scenario: Knowledge build does not ingest workspace
- **WHEN** временный Kotlin и question содержат уникальные sentinel strings
- **THEN** после index/search/explain эти строки отсутствуют в persistent application storage

### Requirement: Portability and resource claims are verified separately

Основная логика SHALL поддерживать Windows и macOS без обязательных Windows APIs/dependencies; OS-specific path protections SHALL быть изолированы. Среда SHALL явно проверять необходимые SQLite text-search capabilities без загрузки сторонних extensions. Индексация и explain SHALL поддерживать последовательную работу локальных моделей с ограниченными batches/context. Измеренные Windows outcomes SHALL NOT выдаваться за проверку Mac M1 16 GB.

#### Scenario: Unsupported SQLite runtime
- **WHEN** необходимая text-search capability отсутствует
- **THEN** команда сообщает неподдерживаемое окружение до индексации/inference, не заменяет поиск молча и не устанавливает зависимости

#### Scenario: Mac validation not yet available
- **WHEN** target Mac отсутствует или установка запрещена корпоративной политикой
- **THEN** actual run остаётся PENDING / NOT TESTED отдельно от подготовки переносимости; Windows acceptance и Day 29 не блокируются, Mac PASS не заявляется

#### Scenario: Target-device observation
- **WHEN** проводится M1 verification
- **THEN** фиксируются actual model/settings, завершение, timings и memory/swap observations; пригодность подтверждается только по реальному compact сценарию

### Requirement: Evaluation compares evidence and reuses the Week 5 corpus

До live SHALL быть зафиксированы synthetic Kotlin/Markdown scenario, вопрос, expected facts/rules, distractors, forbidden claims и review rubric. A/B SHALL использовать один код/вопрос, одинаковые extended instructions/schema и generation model/settings, меняя наличие retrieved docs; исторический Day 27 ответ SHALL NOT заменять A. Одна новая пара SHALL выполняться без автоматических повторов/подбора результата. Retrieval quality, correctness/coverage, source support, applicability, unsupported claims и uncertainty SHALL оцениваться отдельно; улучшение SHALL требовать дополнительного верного поддержанного architectural application без новых unsupported claims и потери существенного верного code fact. Недостижение SHALL записываться как PARTIAL/no improvement/regression, не technical failure по определению.

Week 5 SHALL использоваться через исходные девять Markdown snapshots из проверенного Day 21 corpus с пересчётом embeddings локально и отдельной тестовой Knowledge; старый index SHALL читаться только read-only. Vector/text проверки SHALL включать Q01, Q07, Q10 с оценкой supporting facts, а не только source paths. Старые vectors/thresholds/content-report pipeline SHALL NOT переноситься. При недоступном исходном snapshot SHALL фиксироваться unavailable, без подмены текущими файлами или облачного восстановления.

#### Scenario: Comparable A and B
- **WHEN** основной live experiment завершён
- **THEN** review отдельно показывает outcomes каждой ветки и сравнение по зафиксированным критериям; mechanical PASS не означает semantic PASS

#### Scenario: Week 5 reuse
- **WHEN** доступен проверенный Day 21 snapshot
- **THEN** его Markdown экспортируется в отдельную локальную Knowledge, индексируется локально и проверяется обоими search modes без записи в старую базу

#### Scenario: Unavailable corpus or unperformed human review
- **WHEN** snapshot недоступен либо ручной review ещё не проведён
- **THEN** соответствующий outcome остаётся unavailable/pending и не отмечается выполненным по факту наличия кода

#### Scenario: Report and documentation
- **WHEN** результаты фиксируются для Day 28
- **THEN** Day README содержит фактические наблюдения и ограничение одного прогона, setup находится в документации общей утилиты, корневой README содержит относительную ссылку на Day 28 README
- **AND** пользовательские код/документы/вопросы/ответы в Git и отчёты не включаются
