## Context

См. [proposal.md](proposal.md) — Why. Day 27 в текущем checkout реализован четырьмя небольшими Python-модулями; active change имеет 11/11 tasks и не архивирован. Его offline 101 passed / 1 skipped и live technical PASS / semantic PARTIAL — исторические результаты, не проверки Day 28. Код Week 5 привязан к backend, OpenAI 1536-dimensional embeddings, pinned runs и content evidence; runtime import этих модулей не подходит.

В Explore read-only проверен Day 21 run `3a3c3319-5516-4526-8e56-33ab1251da72`, corpus hash `b1b9595ab50e225e077a2b78b48a90119519a1dc36141ef369a7bfb8b302c91d`: 22 sources, 226 structure-aware chunks, из них 9 Markdown sources / 134 chunks. Источники и результаты прежних дней сохраняются. Design нужен из-за нового persistent data model, двух границ чтения и требований к источникам.

## Goals / Non-Goals

**Goals:** повседневный цикл «подключить docs → обновить → выбрать файл → спросить», переносимые локальные данные, проверяемая связь code/rule/application, видимые причины отказа и возможность отдельно оценивать retrieval.

**Non-Goals:** proof of architectural correctness, OS sandbox против конкурентно враждебной подмены, корпоративная аттестация безопасности или доказательство prompt-injection immunity. Нет будущих пустых provider/agent/multi-file abstractions. Ограничения scope перечислены в proposal.

## Decisions

### 1. One utility with a compatible legacy entry point

Вся runtime-логика остаётся в `day-27-local-architecture-assistant/`. Предлагаемая командная поверхность (пути в примерах — условные, вопрос можно ввести интерактивно):

```text
python assistant.py --workspace W --file A.kt --model MODEL
python assistant.py knowledge preview --knowledge K
python assistant.py knowledge index --knowledge K --embedding-model qwen3-embedding:0.6b
python assistant.py knowledge status --knowledge K
python assistant.py search --knowledge K --mode vector
python assistant.py search --knowledge K --mode text
python assistant.py explain --workspace W --file A.kt --model MODEL --retrieval none
python assistant.py explain --workspace W --file A.kt --model MODEL --knowledge K --retrieval vector
python assistant.py explain --workspace W --file A.kt --model MODEL --knowledge K --retrieval text
```

Первый вариант сохраняет prompt/schema и поведение Day 27; extended `explain` использует контракт решения 7 во всех трёх режимах. Retrieval выбирается явно; none не принимает Knowledge, не открывает SQLite и не вызывает embeddings. Search читает один query из `--query` или терминала и не требует Workspace/generation model. Explain сохраняет `--question`/TTY и существующие model/base-url rules. Новые команды используют exit 0 для завершённой операции, 2 для неверного ввода, 1 для выполнения/stale/incompatible/invalid output, 130 для отмены. Model-level insufficient context — валидный результат exit 0 с явным статусом.

Модули: текущий workspace reader, transport и legacy explain остаются; добавляются небольшие knowledge/chunking/index/retrieval и extended explanation функции. Конкретное разделение файлов уточняется при apply по размеру кода; registry, framework и новый server не нужны. Разделение source/context/render уже достаточно для будущей IDE интеграции; multi-file сейчас не моделируется.

### 2. Directory connection and explicit selection without a hand-edited manifest

Default index — `K/.laa/index.sqlite3`; `.laa/` всегда исключён из discovery. Перед чтением/записью state отдельно проверяются его компоненты: links/junctions/reparse points запрещены, конечный путь обязан оставаться внутри K. RAG explain до чтения Kotlin отвергает совпадающие или вложенные канонические Knowledge/Workspace roots. Корень пользовательской Knowledge должен находиться вне Git checkout; private Workspace тоже размещается вне Git. Это эксплуатационное размещение, не обещание автоматического управления Git чужого проекта. Runtime не вызывает git и не изменяет .gitignore. Синтетические тесты используют временные каталоги.

Discovery рекурсивно перечисляет обычные Markdown-файлы (.md, case-insensitive); по умолчанию пропускает hidden directories, .git, .venv/venv, __pycache__, node_modules, build и .laa. Не следует links/junctions/reparse points. Вложенный небезопасный объект исключается с показанной причиной; явно выбранный запрещённый путь даёт отказ. Разрешённый root канонизируется; сетевые пути и выход за него отвергаются. Отдельные повторяемые `--include relative/path.md` сужают набор до указанных файлов, `--exclude relative/path-or-directory` исключает файл/поддерево. Не требуется glob DSL; paths нормализуются относительно K, без traversal, ADS и неоднозначных Windows-компонентов.

Preview ничего не пишет и не вызывает Ollama: показывает нормализованные относительные пути, исключения и added/changed/deleted/unchanged относительно последнего успешного snapshot. Первая index операция и изменения selection/new/deleted paths показывают такой же список и требуют явного принятия в TTY. `--yes` — документированное явное принятие показанного текущего набора для automation; без TTY и без флага операция не пишет индекс и не вызывает Ollama. Cancel оставляет всё как было. Это UX команды индексирования, не дополнительное согласование при разработке.

Успешный index сохраняет discovery mode, includes/excludes и точный approved set в metadata SQLite. Последующие preview/status/index без selection flags используют сохранённую selection policy; `--all-markdown` явно сбрасывает ограничение на отдельные файлы к directory mode. Изменение только содержимого уже разрешённых файлов принимается самим вызовом index, после показа diff; повторного approval не требует. Новые files не получают разрешение из факта запуска search/explain. Для добавления достаточно положить .md в K и запустить index; для удаления — удалить файл и обновить индекс. Смена policy требует повторного принятия даже при совпавшем наборе.

Границы начального объёма: 500 выбранных документов, 256 KiB raw на документ, 4 MiB raw суммарно, 4096 chunks, 10000 directory entries за discovery. Превышение — явный отказ, без частичного индекса. Ошибки чтения разрешённых каталогов не превращаются в «документ удалён». Empty selection не индексируется. Альтернатива ручного manifest отклонена из-за ежедневного UX; watcher не нужен для обнаружения изменений при вызове.

Если удалён файл из сохранённого --include, status/preview показывают deleted; принятый index удаляет его и из approved set, и из сохранённого include list. Явно переданный сейчас отсутствующий --include остаётся ошибкой ввода. Удаление последнего выбранного документа не создаёт пустой индекс: прежний snapshot остаётся stale. Добавленные между показом списка и чтением/commit файлы не включаются автоматически; изменение candidate set требует нового preview/acceptance.

### 3. Freshness and atomic full rebuild

Status/search/RAG explain заново вычисляют candidate set по сохранённой policy и hashes нормализованного UTF-8-sig/LF текста. Не полагаются только на mtime/size. Added unapproved file в directory mode, changed/deleted approved file, смена policy/chunker или нечитаемый источник делают индекс stale/unverifiable. Поиск и RAG explain прекращаются до embedding/chat с перечнем относительных изменений и предложением index; silent stale, auto-reindex и auto-fallback отсутствуют. Исключённый файл не влияет на freshness. При --include изменение неселекционированного файла не делает индекс stale.

Index читает bounded snapshot одобренных sources в память, получает embeddings последовательно и проверяет, что набор/hashes не изменились за время построения. Только после полного успеха заменяет sources/chunks/FTS/metadata одной SQLite transaction. Сбой HTTP, валидации, диска или изменение files до commit оставляет предыдущий committed snapshot; никаких смешанных поколений. Один writer: штатная SQLite locking с конечным timeout и ясной busy error; не удалять locks и не убивать процессы. Полная переиндексация малого корпуса проще incremental invalidation; unchanged snapshot с тем же fingerprint — no-op без повторного embedding.

Index read — mode=ro, без migrations during query. Database metadata хранит относительные пути, не абсолютный K; перенос всей K/.laa между ОС допускается после проверки файлов/schema/runtime. Проверка freshness действует в границах локальной не-враждебной файловой системы; concurrent mutation не считается защищённой sandbox-сценариями.

### 4. Reuse source-preserving Markdown and a small SQLite schema

Адаптировать из Week 5 headings/paragraph spans, source slicing, canonical hashing, cosine validation/ranking и literal-citation checks. Добавить комментарии происхождения и перенести подходящие тесты; не менять Weeks 1–5 ради общей библиотеки. Импорт backend, его experiment/report writers, pinned defaults и OpenAI client отсутствует.

Markdown splitting: ATX headings с полным ancestor path, заголовки внутри fenced code игнорируются, абзацы пакуются внутри раздела. Короткий документ тоже получает корректные section coordinates. Setext headings в первой версии трактуются как обычный текст; это документированное ограничение. Повторяющиеся headings различаются offset/line/chunk ID. Хранятся точные непрерывные slices нормализованного текста; LF определяет строки, не Unicode splitlines.

Стартовый максимум chunk text — 1800 Unicode code points; большие блоки делятся с overlap до 180 code points, обычные section chunks overlap не получают. Fence/paragraph сохраняется целиком, если помещается; oversized fallback явно отмечен. Heading path добавляется в embedding input отдельно и тоже входит в bounded request. Эти числа не называются токенами; cl100k_base/tiktoken не используется как Qwen tokenizer.

SQLite: metadata (schema version, policy, approved set, corpus hash, embedding/chunker fingerprints), documents (relative path/hash), chunks (ID, path, section, offsets/lines, text/hash, ordinal, float32 vector) и обычная FTS5 table с rowid mapping к chunks. Векторы имеют фиксированное little-endian encoding; длина, конечность и ненулевая норма проверяются при записи/чтении. Full source text можно не дублировать рядом с chunks. Chunk IDs зависят от source hash, coordinates и chunker version. Foreign keys/count/hash checks защищают от неполного или несогласованного snapshot; неизвестная schema не обновляется молча.

FTS5 capability проверяется в :memory: до persistent writes и inference. При отсутствии — ясная ошибка поддерживаемого окружения, без скачивания loadable extensions/другого Python из CLI. Это переносимая проверяемая зависимость, не Windows library.

### 5. Local embedding identity and sequential inference

Default для нового index: `qwen3-embedding:0.6b`, native 1024 dimensions; явный override допустим при поддержке embedding capability и проверяемой фактической размерности. Повторный index без override сохраняет выбранную ранее модель; query использует профиль из index. Fingerprint: provider=ollama, exact model name + installed digest, returned dimension, normalization, document-input version и query-instruction version; chunker хранится отдельно. Перед vector use проверяется установленный digest. Изменение даже при совпадающей размерности требует explicit rebuild. Text mode не требует установленной embedding-модели и не проверяет её текущий digest: он не использует векторы, но проверяет source/schema/chunker integrity.

Metadata /api/show проверяет embedding capability и отсутствие remote_host/remote_model; /api/tags даёт digest. Все metadata/embedding/chat calls используют проверки loopback, no proxy/redirect, bounded responses/timeouts и sanitized errors Day 27. Server должен быть local-only; alias/loopback сами по себе этого не доказывают. CLI не запускает pull, cloud fallback, subprocess модели или настройки сервера.

Embedding: /api/embed, truncate=false, batches до 8 chunks и 64 KiB фактического JSON body; response <=2 MiB. Проверять число векторов, одинаковую dimension, finite nonzero norm. Query — один embedding call, без rewrite/retry/repair. Qwen query input имеет фиксированную английскую retrieval instruction + исходный query; docs получают heading path + source text, без query instruction. Рецепт профиля фиксируется и не меняется незаметно.

Для explain retrieval query = исходный вопрос + basename Kotlin без .kt + CamelCase words без дублей (CheckoutCoordinator → Checkout Coordinator). Одинаковый enriched query используется для vector/text; generation отвечает на исходный question. Нет parser/AST/LLM rewrite/чтения других файлов. Raw question/query <=2000 code points, enriched <=4096; превышение — ошибка без обрезки. Общий вопрос «Что делает этот класс?» — обязательный retrieval test.

Для Mac index batches последовательны; embedding model может оставаться загруженной между batches, после последнего освобождается. При explain query embedding использует keep_alive=0; extended chat также keep_alive=0. Для исключения остаточной одновременной загрузки в целевом memory-constrained профиле пользователь отдельно настраивает OLLAMA_MAX_LOADED_MODELS=1 и OLLAMA_NUM_PARALLEL=1; CLI не меняет server config и не выгружает чужие models произвольными командами. Model loading/cache зависит от controlled server, не гарантируется одними клиентскими флагами.

Официальные основания: [Ollama embed API](https://docs.ollama.com/api/embed), [Qwen 0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [Ollama model](https://ollama.com/library/qwen3-embedding:0.6b), [memory/local-only FAQ](https://docs.ollama.com/faq). 639 MB — размер распространяемой embedding-модели, не измерение RAM.

### 6. Two search modes, one evidence contract

Vector: точный cosine по всем chunks, finite-vector validation, score descending; ties по relative path, ordinal, chunk ID. Не нужен ANN/vector server для установленного ограничения корпуса.

Text: FTS5 unicode61 с underscore как token character; case-insensitive целые tokens, без stemming, fuzzy/prefix inference. CamelCase identifier сохраняется целым. Query превращается в ограниченные (до 64) literal quoted terms, соединённые OR, SQL parameters; сырой ввод не становится FTS grammar. Оператор NOT, кавычки, двоеточие и SQL-like строка не исполняют поисковую программу пользователя. Если terms нет — пустой результат. Ранжирование bm25 ascending, ties как vector. Это поиск токенов, не гарантированный substring search по endpoint с пунктуацией; ограничения видны в help. [SQLite FTS5](https://www.sqlite.org/fts5.html) выбран вместо собственной token-scoring реализации, поскольку уже хранится SQLite и доступен ранкер.

Оба search mode возвращают до top-k=4 (допустимо 1..10), rank, method-specific score, source/section/lines/chunk ID и snippet в терминале. Text search делает 0 HTTP calls. Search не запускает generation. Scores разных режимов несопоставимы и не вероятность знания; threshold 0.50 из Week 5 не переносится. Нет скрытого fallback или fusion.

Search query ограничен 2000 Unicode code points, как explain question. Больше 64 literal terms в text mode — явная ошибка ввода; query не обрезается молча. Список terms не сохраняется. Отсутствие backend/embedding model у text mode проверяется отдельным offline сценарием.

Explain использует выбранный режим и тот же authoritative hit set. Ограничить context максимум четырьмя hits по умолчанию, не дублировать идентичные chunk IDs. При паковке исключаются целые нижестоящие chunks, не подрезаются quotations/source slices. Модель видит только фактически упакованные hits; validator сверяется именно с ними, не со всем index.

### 7. Extended explanation distinguishes evidence and application

Extended schema: обязательные code_observations, documented_rules, applications, assumptions, limitations и knowledge_status (not_requested / candidates_provided / no_candidates). Code observation: локальный ID, text, непустые уникальные Kotlin line numbers. Documented rule: ID, text, непустые citations, каждая {chunk_id, quote}; quote <=400 characters и точная непрерывная подстрока переданного chunk. Application: text и непустые ссылки на существующие observation IDs и rule IDs. IDs уникальны в своих массивах; все текстовые поля непусты; unknown fields/IDs/дубликаты/invalid lines отклоняются.

Приложение подставляет source paths/sections/line ranges из authoritative context. Номера строк code и docs показываются раздельно; rule description не выдаётся за проверенное выполнение правила. Interpretation должна объяснять, почему scope документа относится к текущему коду; конфликт кода и правила обозначается, а не «исправляется» сочинённым поведением.

При retrieval none: knowledge_status=not_requested, rules/applications пусты. При отсутствии hits: no_candidates, rules/applications пусты, limitation обязательна; видимый Kotlin всё равно объясняется. При candidates_provided модель может вернуть пустые rules/applications с limitation о неподходящем или недостаточном контексте. Непустые references подтверждают только механическую связь. Schema/quote validity != semantic support != applicability != correctness; кодом семантика не оценивается.

Knowledge status определяется runtime по режиму и фактическому context; модель обязана вернуть то же значение, mismatch отклоняется. Для none также обязателен limitation о границе code-only анализа; полностью пустое объяснение без limitation недопустимо. Между arrays допускаются только ссылки установленного типа: application не может подменить rule ID номером строки или observation ID.

Один JSON user payload отдельно содержит question, numbered Kotlin и retrieved documentation. Stable system instructions объявляют код/комментарии/документы недоверенными данными; источники не добавляются в system/developer roles. Нет tools/command execution; safe_text сохраняет защиту терминала. Offline тесты с «ignore instructions», fake roles и командами в Markdown/комментариях проверяют фактическую форму payload, неизменность system instructions и отсутствие side effects. Mock ответ не является тестом реальной устойчивости LLM: отдельно нужен adversarial synthetic live observation, без обещания immunity.

Done/stop, JSON/schema validation, no retries/repair и failure rendering наследуются из Day 27. Byte limits extended: Kotlin <=16 KiB, question <=2000 code points, full chat body <=24 KiB, response <=256 KiB; num_ctx=8192, num_predict=2048, think:false при capability. Сначала проверять минимальный body без docs; потом упаковывать целые chunks в оставшийся budget. Если найденные chunks ни один не помещается, выдавать context_budget_exceeded без chat, не представлять это как «знаний нет». При частичном исключении показывать число selected/omitted. Byte cap не гарантирует token fit: точный chat tokenizer/preflight отсутствует, silent server truncation остаётся ограничением; synthetic input держать компактным.

### 8. Privacy and useful diagnostics

Knowledge persistence — отдельная явная функция: только approved docs/chunks/vectors и configuration metadata. Workspace Kotlin, question/query vector, assembled prompts, answers, history и raw provider errors никогда не сохраняются приложением в index/cache/files/reports. Search snippets/answer выводятся только в терминал по запросу; preview/status вправе показывать relative paths. Diagnostic metrics не содержат source paths или content. Ошибки не отражают provider body или сырой argparse value.

Нет default transcript/evidence writer Week 5. В Git допускаются код утилиты, синтетические fixtures/rubric и краткие безопасные результаты; пользовательские документы и их цитаты в отчёты не переносятся. Shell history, terminal scrollback, server logs, backups и отсутствие encryption-at-rest не объявляются контролируемыми CLI; пользоваться interactive question и controlled local-only server без body logging. Индекс содержит выбранную документацию в читаемом виде.

### 9. Evaluation ties practical value to evidence

Основной fixture — существующий CheckoutCoordinator.kt плюс небольшие synthetic Markdown rules (назначение координатора, границы обязанностей, навигация после approved payment, отсутствие доказательств transaction/rollback) и distractor другого scope. До live фиксируются вопрос, expected fact IDs, expected document sections, unacceptable claims и ручная rubric. Documents описывают договорённости, не готовый эталонный ответ.

Одна новая A/B пара extended explain none/vector: одинаковые код, вопрос, system instruction, schema, generation model+digest, token/thinking settings и sampling settings. Для extended режима зафиксировать temperature=0 и seed=28 в обеих ветках; это уменьшает вариативность, но не обещает детерминизм между ОС/версиями. Legacy параметры не меняются. Различается только retrieved-documents payload и объявленное отсутствие/наличие context. Исторический Day 27 PARTIAL не заменяет A. Один заранее определённый negative/adversarial случай с unrelated docs и injection в синтетических data проверяет uncertainty отдельно от основной пары. Нет автоматических повторов и подбора удачного результата.

Retrieval проверяется до generation отдельно для vector/text на одинаковом snapshot: точный identifier, перефразированное правило, distractor/scope conflict и вопрос без знания. Оценка — наличие конкретных supporting spans/expected rules в top-k, а не source_path_hit. Negative vector top-k вправе быть непустым; отсутствие знания определяется rubric/ответом, не cosine threshold.

Ручной review каждой ветки: expected-fact correctness/coverage, source support, applicability, unsupported claims и uncertainty. Полезность подтверждается, если B добавляет хотя бы один правильный поддержанный архитектурный вывод к A, не теряет существенный верный code fact и не добавляет unsupported claims. Если нет — PARTIAL/no improvement/regression; completed experiment не равен semantic PASS. Reviewer identity/роль и вердикт фиксируются без transcript; pending review не считается завершённым review.

Week 5: узкий fixture-preparation helper в материалах Day 28 читает старый SQLite mode=ro, проверяет pinned run/corpus/source hashes и экспортирует только девять Markdown snapshots в отдельную тестовую K вне Git, сохраняя relative paths. Пользовательский CLI не получает importer произвольных старых баз. Не брать текущие изменившиеся README вместо snapshot; если старый index отсутствует — явно сообщить unavailable, без OpenAI fallback и ложной отметки выполненного corpus requirement. Существующие embeddings/query vectors не импортировать. Тем же index command строится новый local index. Из Day 22 используются Q01, Q07, Q10 и expected-fact rubric, без старого loader, требующего OpenAI provenance. Vector/text retrieval проверяется на всех трёх; Q10 оценивается как отсутствие подтверждающего фрагмента, не обязательный нулевой top-k. На небольшом публичном/синтетическом корпусе показать new index reopen и no re-embedding on search.

Offline suite включает legacy regression, path/privacy/injection payload tests, chunk provenance, stale/atomic rebuild, FTS literal queries, vector compatibility, budget и citation validation. Не нужны backend/Android/Gradle проверки: они не меняются.

Mac acceptance делится на переносимость и измеренную пригодность. Portable code/tests/reopen на Windows обязательны; actual M1 run фиксирует модель/settings, build/search/chat timings, memory pressure/swap и peak process memory доступным OS инструментом. Нет измерений — macOS pending, не PASS. Для практической пригодности требуются завершённый compact A/B без OOM и постоянно растущего swap при последовательных запросах; latency записывается и оценивается пользователем без выдуманного SLA. Смена generation model требует отдельной пары A/B с одинаковыми настройками внутри пары. Нет Mac — не блокировать завершение Windows implementation, но не закрывать macOS validation task как выполненный запуск.

## Risks / Trade-offs

- [Настоящая цитата из чужого scenario] → отдельные applications, scope distractors и ручная оценка, без automatic semantic PASS.
- [Prompt injection] → data-only layout, no tools, валидатор и adversarial observation; не заявлять гарантированную устойчивость LLM.
- [Свежесть требует чтения docs на каждый запрос] → bounded corpus/hash scan; incremental/watch cache отложен до измерений.
- [Большой файл не помещается вместе с docs] → explicit budget failure/whole-chunk omission; пользователь сужает выбранный файл вручную, auto-summary отсутствует.
- [Model drift и разные embedding spaces] → fingerprints/digests, explicit rebuild; никакого смешивания OpenAI/local vectors.
- [FTS5 не собран в Python SQLite] → early capability error и документированное окружение, без незаметного изменения algorithm.
- [9B model на M1 медленна или не помещается] → последовательный server profile и реальные измерения; меньшая model — отдельная зафиксированная A/B пара.
- [Постоянный index содержит private docs] → хранение вне Git и только explicit approved Knowledge; это не encrypted vault.
- [Незакоммиченный Day 27] → scoped diff/hash review, не менять его OpenSpec artifacts/исторический verdict; legacy regression при apply.

## Migration Plan

Простой путь Knowledge: --knowledge > LAA_KNOWLEDGE, пустой явно заданный путь — ошибка. Extended none игнорирует environment Knowledge, но отвергает явный --knowledge; legacy переменную не читает. После одного index пользователь задаёт переменную и вызывает explain; preview/status/search не обязательны. Freshness проверяется автоматически, обновление выполняется явно через index с прежними правилами scope approval.

1. На этапе apply добавить новые команды/модули в существующую утилиту, сохранить legacy invocation и выполнить его тесты. Day 27 не требуется архивировать.
2. Первый Knowledge index создаётся отдельно; старый Day 21 SQLite остаётся read-only fixture source. Никакой in-place migration OpenAI embeddings.
3. Обновление compatible Knowledge — atomic full rebuild. При unsupported schema/model change требуется явный rebuild, старые данные не интерпретируются как совместимые.
4. Rollback пользователя — запуск legacy Day 27 без Knowledge; новые команды не меняют Workspace. Обновление docs/index остаётся отдельным действием; автоматического удаления базы при ошибке нет.
5. Документация общей утилиты содержит setup/commands/limits, Day 28 README — три кратких раздела и фактические результаты, корневой README — относительную ссылку. Нынешний proposal не создаёт эти implementation files.

## Open Questions

- Фактические retrieval coverage и latency выбранного embedding profile будут измерены на зафиксированных fixtures; порог/модель не подстраиваются после наблюдения ради PASS.
- Actual Mac run при отсутствии устройства или запрете корпоративной политики остаётся PENDING / NOT TESTED. Подготовка переносимости и запуск разделены; это не блокирует Windows acceptance и Day 29 и не считается Mac PASS.
