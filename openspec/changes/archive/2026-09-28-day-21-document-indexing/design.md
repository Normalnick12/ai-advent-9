## Context

Мотивация — [proposal.md](proposal.md), контракт — [delta spec](specs/document-indexing-experiment/spec.md). Day 21 делает наблюдаемой цепочку documents → chunks → embeddings → persistent index. В backend уже есть Python, OpenAI SDK и SQLite; запускаемый отдельно CLI не требует FastAPI или Android.

Explore измерил выбранные 22 файла: 141653 символа с LF, 2295 строк, включая 80347 символов Markdown (около 40 условных страниц по 2000 символов). Это инвентаризация исходников, не результат chunking/embeddings; actual tokens будут измерены при реализации.

## Goals / Non-Goals

**Goals:** как можно раньше получить понятный offline preview, затем добавить реальные embeddings и SQLite reopen. Общий snapshot и token budget делают сравнение объяснимым.

**Non-Goals:** retrieval, cosine search, FAISS, reranking, LLM generation, agent, MCP, Android UI, Kotlin parser, новые сервисы; также generic ingestion/tokenizer framework, byte-boundary subsystem, cache manager, resume/incremental indexing, расширенный lifecycle runs и exhaustive verifier/test suite.

## Decisions

### 1. Explicit corpus and snapshot

Manifest `day-21-document-indexing/corpus.json` содержит 22 согласованных пути, source_type и четыре representative locations:

| Source type | Paths relative to repository root |
| --- | --- |
| documentation | `README.md`; `backend/README.md`; `android-app/README.md`; `day-07-context-persistence/README.md`; `day-13-task-state-machine/README.md` |
| spec | `openspec/specs/first-agent-conversation/spec.md`; `openspec/specs/first-agent-android/spec.md`; `openspec/specs/task-state-machine/spec.md`; `openspec/specs/task-state-android/spec.md` |
| backend | `backend/app/conversation_store.py`; `backend/app/sqlite_conversation_store.py`; `backend/app/agent_sessions.py`; `backend/app/agent_api.py`; `backend/app/task_state.py`; `backend/app/task_state_store.py`; `backend/app/sqlite_task_state_store.py`; `backend/app/task_state_lab_service.py` |
| android | `android-app/app/src/main/java/com/example/responsecontrollab/data/CurrentSessionStore.kt`; `android-app/app/src/main/java/com/example/responsecontrollab/data/ChatRepository.kt`; `android-app/app/src/main/java/com/example/responsecontrollab/ui/chat/ChatViewModel.kt`; `android-app/app/src/main/java/com/example/responsecontrollab/data/TaskStateRepository.kt`; `android-app/app/src/main/java/com/example/responsecontrollab/ui/taskstate/TaskStateViewModel.kt` |

Простая проверка manifest: уникальные relative paths, существующие обычные UTF-8 файлы поддерживаемых типов, соответствие согласованному перечню. Не включать secrets, runtime/generated files, архивы или текущие Day 21 artifacts. Достаточно стандартного resolve + проверки принадлежности root; сложная поддержка symlinks и произвольных внешних corpora не нужна.

Прочитать corpus один раз, удалить initial BOM при наличии, нормализовать CRLF/CR в LF. Не strip/reflow текст. Обе стратегии используют один in-memory snapshot. SHA-256 normalized source text и отсортированные path/hash пары дают corpus hash. Сохранить snapshot в SQLite для дальнейшего inspect. Ошибка manifest/read останавливает build до API calls.

Content hashes являются provenance реально прочитанного текста, не гарантией атомарного снимка Git. После правок README при реализации объём измеряется заново; после live сохранённый snapshot не переписывается под новые документы.

### 2. Minimal token-constrained source slicing

Использовать `tiktoken/cl100k_base` и один `token_count(text)` через `encode_ordinary`. Max 500, target overlap около 50. Окна вычисляются по character offsets Python string; токены никогда не декодируются обратно в текст, byte maps не строятся.

Прямой вариант: увеличивать candidate end по character offsets до превышения бюджета/конца source, затем обычным делением диапазона искать подходящую границу, сохраняя проверенный допустимый candidate. Каждый замер — `token_count(source[start:end])`. Финальный candidate обязательно проверяется <=500; для непустого остатка end > start. Это приближённый выбор окна около лимита, не поиск математически максимального префикса: BPE counts не обязаны быть строго монотонными, поэтому допустимость определяется фактическим замером выбранного текста.

Overlap аналогично выбирается как приблизительно 50-token suffix готового chunk на character boundaries с фактическим count <=50 и next_start > current_start. Next start не может быть дальше предыдущего end: пробелов в покрытии нет. На конце source остановиться сразу. Пропускать только целиком пробельные окна, не менять содержимое остальных. Малый helper возвращает exact source spans; те же правила используются в structure-aware fallback. Повторная токенизация приемлема для 22 файлов; оптимизация tokenizer не является задачей дня.

Обычные string slices сохраняют Unicode code points; отдельного анализа UTF-8/token bytes не требуется. Гарантии: exact substring, <=500 actual tokens, approximate overlap <=50, продвижение и покрытие всего непробельного текста. Нет требования идеальных 500/50 или максимальной упаковки.

Установить tiktoken и один раз загрузить штатный encoding при подготовке окружения. Документировать обычную инициализацию (первое получение assets может требовать сети), записать установленную версию в config. Собственный cache manager, offline asset probing и тесты cache failures не добавлять. После стандартной подготовки preview/tests работают без OpenAI и сети.

### 3. Structure-aware deterministic chunking

Все границы извлекает обычный код; лимит и helper общие. Каждый chunk — непрерывный source slice; не повторять заголовки как enrichment, не переписывать код.

- Markdown: headings вне fenced code задают иерархию. Помещающийся раздел с дочерними секциями сохраняется целиком; большой делится по subsections/абзацам, затем token fallback. Preamble и fenced code не теряются; не нужен универсальный Markdown parser.
- Python: стандартный AST даёт top-level functions/classes и непосредственные методы крупного класса. Decorators входят в declaration, вложенные функции остаются у родителя. Imports, comments и gaps сохраняются как исходные spans; не нужно угадывать семантическую принадлежность каждого комментария. Oversized span делится общим helper. Для parse error достаточно file-level fallback с явной причиной.
- Kotlin: помещающийся файл целиком; иначе blank-line formatting blocks, последовательная упаковка до 500 и общий fallback. Никакого parser/regex declaration extraction или обещания сохранить функцию.

Между самостоятельными structural chunks overlap отсутствует; только oversized/parse fallback использует target 50. Split reasons: `token_window`, `structural_boundary`, `oversized_fallback`, `parse_fallback`. Различие overlap policies показывается пользователю.

### 4. Metadata without a platform

Core: chunk_id, source, source_type, title, section, strategy, ordinal, start_line/end_line, token_count, text_hash, split_reason. Source types: documentation/spec/backend/android. Strategy IDs: fixed-size/structure-aware; display name второй стратегии — structure-aware deterministic chunking.

Title — heading или basename. Ordinal 0-based внутри source/strategy, lines 1-based inclusive. Для fixed-size достаточно честного file-level section; вычисление deepest common ancestor/всех пересечённых sections не нужно. Structure-aware указывает известный heading/declaration либо file/formatting block.

Оставить start_char/end_char как единственную дополнительную пару: half-open offsets уже есть в slicer и упрощают exact-substring проверку, IDs и выбор пересекающих representative chunks. Они не обязывают реализовывать coverage analytics.

text_hash — SHA-256 UTF-8 chunk text. chunk_id — hash canonical source path/hash, strategy, chunking config и range; не содержит timestamp/build ID. Повторение на одном snapshot/config стабильно, одинаковый текст в разных местах различается. После редактирования source стабильность IDs не обещается.

Build config содержит manifest/source hashes/corpus hash, normalization, tokenizer/version, chunking parameters/простую algorithm revision, model/dimension, representative ranges и время. Git HEAD можно записать как дополнительную справку, но источником истины остаётся content hash. Отдельной provenance subsystem нет.

### 5. Preview first and preselected examples

CLI `backend/scripts/day21_index.py`: corpus → preview → build --strategy both → compare → inspect. Loader/chunking/report могут быть небольшими функциями в `backend/app/document_indexing/`; классы/интерфейсы нужны только где упрощают работу, отдельный Embedder сохраняется.

Manifest фиксирует те же locations до запуска:

| Source | Anchor / intended location |
| --- | --- |
| `openspec/specs/first-agent-conversation/spec.md` | heading `### Requirement: Only a completed text turn atomically commits history`, through its Scenario children until the next heading of the same/higher level |
| `backend/app/sqlite_conversation_store.py` | method `append_turn` declaration and its full body |
| `android-app/app/src/main/java/com/example/responsecontrollab/ui/chat/ChatViewModel.kt` | line `  private fun restore() {` (line location, not a parser-derived method range) |
| `backend/app/task_state_lab_service.py` | method `send` declaration and its full body |

Python ranges определяются уже имеющимся AST, Markdown — headings. Для Kotlin показывать anchor line с фиксированным контекстом 3 строки до и 12 после, обрезая у краёв файла; это formatting context, не распознанное тело метода. Missing/ambiguous anchor — простая ошибка, не повод подобрать более удачный пример.

Для каждого location `preview` печатает три последовательных блока:
1. Исходный участок с source path и номерами строк.
2. Все fixed-size chunks, пересекающие участок: полный текст и core metadata.
3. Все structure-aware chunks, пересекающие участок: полный текст и core metadata, включая section/token_count/split_reason.

Отдельный selector позволяет показать один заранее выбранный пример; default проходит все четыре. Preview не требует ключа, embeddings, SQLite или running backend. Нельзя заменять его только числовой таблицей, обрезать текст до неинформативных snippets или выбирать examples после результатов. Этот flow реализуется до provider/storage.

### 6. Embedder and a simple completed SQLite build

`Embedder.embed(texts)` возвращает vectors в соответствии с входами и reported usage. OpenAI adapter использует существующий SDK, text-embedding-3-small, dimensions=1536, float; exact chunk text без enrichment. Последовательные batches до 32, finite timeout, max_retries=0. Реальных вызовов в offline tests нет.

Обязательны правильная связь text/vector, количество ответов и размерность. Простое упорядочивание по response index и strict JSON serialization без NaN допустимы как несколько строк внутри adapter/store; отдельные subsystems и матрица тестов reorder/NaN/Infinity не требуются. Не делать молчаливую подмену отсутствующих vectors. Fake используется только в тестах.

Один `build --strategy both` сначала готовит и проверяет embeddings обеих стратегий в памяти, затем одной обычной SQLite-транзакцией сохраняет snapshot, два набора chunks и provenance. Для малого corpus память приемлема. Три простые таблицы sources/builds/chunks; JSON vectors в TEXT, общий run ID для пары. Нет промежуточных per-strategy publications, run state machine, resume и event journal. Успех печатается только после commit; ошибка API/count/dimension/write завершает команду nonzero без готового неполного run. Ранее завершённые runs не изменяются.

База `backend/.local/day21/index.sqlite3` изолирована от прошлых Days и игнорируется Git. Повторный build — явная полная пересборка с новым run ID (chunk IDs на неизменных входах сохраняются); не нужен embedding cache. После reopen compare/inspect читают сохранённый snapshot и vectors без API key, OpenAI или текущих corpus files.

Key остаётся в backend environment. OpenAI получает выбранный текст; SQLite хранится локально. Build — явное live действие, отсутствующее в preview и tests.

### 7. Minimum comparison, observations and tests

Для каждой стратегии обязательна одна небольшая таблица: chunk count, min/median/max actual token_count, сумма chunk token_count (total embedded tokens готового build, planned tokens в preview), fallback count. Общий snapshot/config берётся из run; перед сравниванием достаточно проверки сохранённых значений. Затем показываются те же representative locations и chunks. Для ещё не выполненного live не писать, что planned tokens уже отправлены provider.

p95, repeated coverage, structural crossing/preservation не входят в обязательный результат или tasks. Их отсутствие не блокирует Day 21; добавление допустимо только если это несколько простых операций над уже готовыми данными, без отдельного evaluator. По умолчанию их не реализовывать.

Timing, provider usage, calls и размер SQLite — небольшой отдельный блок наблюдений run. Usage unknown остаётся unknown; local token counts и provider usage имеют разные подписи. Размер файла — общий размер базы при наблюдении, а не размер второй стратегии. Никаких выводов о retrieval superiority или generalized chunking performance по одному API run.

Минимальные проверки:
- Mixed-language fixture: exact source slices, Unicode, <=500 tokens, overlap/progress/coverage, отсутствие пустых chunks и стабильность metadata/IDs.
- По небольшому примеру Markdown/Python/Kotlin для границ и oversized fallback; проверить, что текст не теряется.
- Invalid manifest, wrong embedding count/dimension и ошибка provider не дают успешного build.
- SQLite round-trip/reopen: текст, metadata и vectors доступны без provider; успешный fake integration проходит corpus → preview → build → compare/inspect.

Это компактные scoped tests, не отдельные harness/verifier, fuzz suite, platform matrix или exhaustive failure injection. Одна проверка может покрывать несколько invariants; реальный offline preview также используется для review.

## Risks / Trade-offs

- Повторный token_count дороже прямого slicing tokens → принимаем для небольшого corpus; измерять/оптимизировать только при реальной проблеме, byte engine не строить.
- Структура не всегда помещается в 500 tokens → явный fallback и видимый split_reason; никакой retrieval гарантии.
- Kotlin formatting слабее declarations → честные labels и исходный текст в preview.
- Сбой второго embedding batch/strategy теряет незаписанный прогресс → простая ошибка и отсутствие готового run; resume не нужен для учебного объёма.
- README/specs/code могут расходиться → сохранять источник и snapshot, не синтезировать «истину» моделью.

## Migration Plan

Изолированный module/CLI, corpus manifest, tiktoken в существующем backend environment. Сначала offline preview, затем Embedder/SQLite/compare/inspect. Обновить Day README и root link, команды — в backend/scripts README. Выполнить scoped offline checks, затем авторизованный live build и reopen. В README фиксировать только фактический run с его исходным corpus hash; поздние правки docs не меняют сохранённую provenance. Миграций старых API/DB, Android build или deployments нет.
