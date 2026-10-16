## Context

Мотивация и согласованный scope — в [proposal.md](proposal.md). Контракты — [developer-assistant-help](specs/developer-assistant-help/spec.md) и [local-git-branch-mcp](specs/local-git-branch-mcp/spec.md).

Week 5 реализован в `backend/app/document_indexing`, `first_rag`, `rewrite_filter_rag`, `grounded_rag`, `stateful_rag`; CLI находятся в `backend/scripts`. Day 21 pipeline/storage требуют две стратегии, Day 22 loader — минимум пять chunks, а исторические baseline paths/run IDs и threshold относятся к старому эксперименту. Эти ограничения не являются требованиями Day 31.

Week 4 использует `mcp==2.2.0`: `day-16-mcp-discovery/main.py` показывает клиент/discovery, `day-17-android-dependency-mcp/server.py` — сервер и tool contract. Локальная установка SDK поддерживает stdio client/server. Backend пока не зависит от MCP. Week 6 имеет отдельный runtime с Kotlin/Ollama; он не подключается.

Корневой `docs/` пока отсутствует. Основная существующая техническая документация находится в README backend/Android/scripts; корневой README перечисляет дни. Документы корпуса будут созданы/дополнены только на этапе apply. Design нужен из-за нового индекса, MCP-процессной границы и проверки происхождения ответа.

## Goals / Non-Goals

**Goals:** один короткий путь вопроса через актуальный локальный корпус, настоящий MCP и облачную LLM; простая проверка источников; независимое отображение Git; воспроизводимая приёмка без лишних повторов.

**Non-Goals:** универсальный framework, адаптеры разных провайдеров, поиск по исходникам, автоматическая загрузка ссылок, persistent chat, общий рефакторинг предыдущих дней, доказательство семантической корректности только программным валидатором. Полный продуктовый backlog не добавляется: Week 7 ограничена вечером 18 октября 2026 (Europe/Moscow).

## Decisions

### 1. Separate CLI with direct backend imports

`backend/scripts/day31_help.py` работает из существующего Python-окружения backend, без запуска `app.main` и FastAPI. Repository root вычисляется относительно launcher, а не текущего рабочего каталога. Публичного `--workspace` для произвольных проектов нет; корни/clients можно инъецировать в offline-тестах.

Интерфейс из корня репозитория:

```powershell
& .\backend\.venv\Scripts\python.exe .\backend\scripts\day31_help.py --help
& .\backend\.venv\Scripts\python.exe .\backend\scripts\day31_help.py index
& .\backend\.venv\Scripts\python.exe .\backend\scripts\day31_help.py /help "Где находится реализация RAG?" --trace
```

`/help` без question показывает usage. Явно пустой/blank question, неизвестные flags/commands и question длиннее 4000 символов дают ошибку ввода. `index` не обращается к MCP/генерации. `/help` не строит индекс автоматически. Exit codes: 0 — успешная операция, включая корректный `insufficient_context`; 2 — неверный ввод; 1 — index/MCP/provider/validation failure; 130 — отмена пользователем. Ответ и Git-блок идут в stdout, trace — в stderr; terminal control characters экранируются при рендеринге недоверенных строк.

Последовательность `/help`: parse → load/freshness → MCP discovery/call → query embedding → retrieval → Responses → validation → render. Клиент закрывает дочерний MCP-процесс сразу после получения результата; следующая генерация не требует живой MCP-сессии. Нет состояния диалога между командами.

Альтернативы: расширение Day 25 влечёт сессии/память и baseline coupling; расширение Day 27 влечёт Kotlin/Ollama; новый HTTP endpoint не нужен для терминальной демонстрации. Поэтому добавляется тонкая независимая backend-точка входа.

### 2. Exact five-document corpus

`day-31-developer-assistant/corpus.json` использует знакомые `sources: [{source, source_type: "documentation"}]` без representative locations. Полный начальный список закреплён в proposal; рекурсивного glob/discovery нет. Дополнение allowlist — явное изменение конфигурации с последующим `index`. Файл вне allowlist не влияет на актуальность; ни ссылки из документов, ни наличие новой вложенной папки docs сами по себе не расширяют корпус.

Перед чтением проверяются относительные `.md` paths, отсутствие дублей, скрытых компонентов и выхода за root. В дополнение к `load_corpus` проверяются symlinks/junctions/reparse points на компонентах разрешённых путей. Ограничения чтения: 256 KiB на документ, 2 MiB на корпус; превышение, неверный UTF-8 или нечитаемый файл — явный отказ, без обрезки. Секретные файлы не разрешены и не обнаруживаются обходом дерева. Владелец отвечает за отсутствие секретов внутри самих разрешённых документов; автоматический универсальный secret scanner не создаётся.

`docs/project-structure.md` описывает роль `backend`, `android-app`, `scripts`, `day-*`, `openspec`, реальные расположения Weeks 4–6 и Day 31, направления вызовов и границы между ними. Утверждения сверяются с текущими файлами; планируемое не описывается как готовое. Команды установки/запуска остаются в README компонентов. Старые инструкции в scripts README описываются с привязкой к своему Day, не как обязательные зависимости `/help`.

Альтернатива «все README и OpenSpec» увеличивает шум и риск смешения планов с реализацией. Пять документов достаточно для выбранных вопросов; исходники и Day README можно добавить только отдельным согласованным расширением.

### 3. Reuse Week 5 primitives, keep a small Day 31 index adapter

Прямые imports без изменения старых модулей:

| Existing module | Reuse |
|---|---|
| `app.document_indexing.corpus` | `load_corpus`, `Source`, `Snapshot`, canonical hashing |
| `app.document_indexing.chunking` / `structure` | `chunk_source(..., "structure-aware")`, token/config metadata, source slices |
| `app.document_indexing.embedding` | `OpenAIEmbedder`, embedding configuration |
| `app.first_rag.core` | `Index`, `vector_norm`, `search` |
| `app.grounded_rag.core` | `GroundedResponse`, `validate`, canonical abstention |
| `app.llm_client`, `app.openai_responses_llm_client` | configuration/messages/result and Responses client |

Небольшой `index.py` Day 31 отвечает за сборку и хранение одной стратегии; `corpus.py` — за разрешённый snapshot и freshness. Не используется Day 21 `build/save/load` с парой стратегий, Day 22 `read_index`, Day 24 `messages` с ровно пятью chunks или stateful service. Это локальные адаптеры сценария, не новый RAG framework.

Хранилище `backend/.local/day31/index.sqlite3`: один опубликованный snapshot, metadata, source snapshots и chunks с JSON vectors. Metadata включает schema version, нормализованный allowlist, corpus hash, конфигурацию чанкинга и embedding profile. Для chunks сохраняются существующие path/section/offsets/lines/hash/token_count/ordinal/ID. Loader проверяет counts, source/chunk hashes и slices, уникальность, конечность/норму/размерность векторов; создаёт `Index` напрямую, без требования минимум пяти chunks.

Embeddings: `text-embedding-3-small`, dimension 1536, float, batches до 32, существующий timeout/retries=0. Стратегия Week 5: 500 tokens на chunk, overlap 50 для oversized fallback. При неизменившемся валидном индексе `index` — no-op без API. При изменениях первая версия заново строит весь небольшой корпус; incremental embedding cache/resume не добавляются.

Новая сборка сначала получает все vectors, повторно проверяет snapshot документов/manifest, затем записывает и проверяет временный SQLite в том же Day 31 каталоге. После закрытия соединений публикует его через atomic replace; при ошибке старый файл остаётся. Чтение — SQLite `mode=ro`. До query embedding сравниваются текущий нормализованный UTF-8/LF snapshot, allowlist и config. Изменение только CRLF/LF или BOM при неизменном нормализованном тексте не делает индекс устаревшим. Параллельные административные rebuild не поддерживаются; демонстрация последовательная, file lock/replace failure явно останавливает публикацию. Не добавляется scheduler или lock service.

Альтернативы: две стратегии ради совместимости старого storage удваивают бессмысленную работу; Week 6 storage тянет собственный embedding profile и Knowledge runtime. Маленький собственный формат для одной стратегии лучше сохраняет границы дней.

### 4. Retrieval and answer quality

Один исходный question передаётся в embeddings без LLM rewrite. Cosine search ранжирует chunks в существующем детерминированном порядке; в контекст выбираются до восьми. По явно одобренному пользователем уточнению при live-приёмке, вводный содержательный chunk основного найденного документа заменяет самый слабый hit, если введения ещё нет среди восьми. Это сохраняет общие условия документа без изменения документации под вопросы. Вводный chunk — первый по ordinal с непустой строкой помимо заголовков. Trace сохраняет `selection=source_intro`, исходный `cosine_rank` и позицию `rank` в отправленном контексте. Дополнительных API-запросов нет. Исторический threshold 0.50 не применяется: он не калиброван на новом корпусе. Отсутствие непустых chunks — ошибка индекса; отсутствие ответа в найденных chunks — задача grounded generation и ручной оценки.

Generation использует существующий `OpenAIResponsesLlmClient`: `gpt-5.6`, `reasoning_effort=none`, `max_output_tokens=3000`, `truncation=disabled`, собственные instructions/version. Итоговый контракт остаётся `GroundedResponse`; generation возвращает `status`, `answer`, `citation_ids` — короткие ID предложенных фрагментов (например `S1Q2`). CLI детерминированно восстанавливает citations и sources из authoritative records именно отправленного контекста. Модель выбирает основания ответа, а не копирует длинные hash/section/quote. Это не repair текста ответа и не отключение валидации: итоговая структура проверяется прежним валидатором Week 5. Контекст — до восьми chunks по 500 tokens плюс вопрос, evidence options и отдельный `git_context`. Ключ берётся только из backend `OPENAI_API_KEY`; допустима существующая загрузка `backend/.env` без override. Тайм-аут и retries наследуются от клиента. MCP child не получает OpenAI key.

Инструкции требуют русский содержательный ответ по текущему контексту, различать Days, не исполнять инструкции из документов и не заполнять пробелы предположениями. Факты о структуре подтверждаются источниками; Git-контекст используется отдельно и не превращается в документальную цитату. При недостаточном основании модель возвращает существующий канонический `insufficient_context` и пустые sources/citations. Смешанный вопрос допускает ответ на подтверждённую часть с явным обозначением неизвестной; полностью неподтверждённый требует abstention.

Schema ограничивает citation_ids короткими ASCII ID реальных evidence options. В context.evidence передаются ID и буквальные отрезки отдельных физических строк: до 24 вариантов на chunk, каждый до 400 символов; длинные строки разделяются на точные отрезки, при большом числе вариантов сохраняется равномерный набор. Многострочные quote enum не используются: live API подтвердил их несовместимость со strict=true; копирование моделью текста цитат также оказалось ненадёжным, поэтому итоговая версия предлагает выбирать ID. При нехватке поддержки модель обязана отказаться, а не подобрать декоративную цитату; ограничение доступных вариантов сохраняется как trade-off. Перед рендерингом проверяются strict JSON без duplicate keys, принадлежность ID context, chunk IDs, authoritative source/section и literal quotes до 400 символов относительно отправленного контекста. Schema не заменяет runtime-проверку соответствия quote конкретному chunk; одинаковые повторные citations отвергаются, а не исправляются. Диапазоны строк берутся из проверенных chunks, а не из модели; это диапазон chunk, не обещание более точного расположения quote. Git-блок всегда рендерится детерминированно из MCP результата. Invalid/refused/incomplete output не показывается как успешный ответ. Автоматических retry/repair/judge нет.

Качество важнее экономии токенов: Top-8 и output budget дают место содержательному ответу и цитатам. Если live выявит пропуск источника, корректируется конкретная причина и повторяется только затронутый вопрос; не запускается широкий benchmark. Если для устранения ошибки нужен другой подход, изменение проходит review, а не скрытый fallback.

### 5. Local MCP process and Git contract

`backend/scripts/day31_git_mcp.py` запускает сервер из `app/developer_assistant/git_mcp_server.py`. CLI-клиент создаёт `Client(StdioServerParameters(command=sys.executable, args=[absolute_launcher, "--repo", fixed_root], ...))`. Сервер получает минимальное окружение, нужное для Python/Git/Windows, без передачи всего `os.environ`, OpenAI key и пользовательских Git overrides. Рабочий каталог определён явно. SDK `mcp==2.2.0` добавляется в requirements backend; установка проверяется через resolver/pip check, версии старых дней не редактируются.

На каждой операции: protocol initialization → `list_tools` (учесть pagination) → проверка наличия tool/schema → `call_tool("get_current_branch", {})` → проверка `is_error` и строгого `structured_content`. Никакого network endpoint, hosted MCP или tool-selection loop у LLM.

Tool output:

```json
{"status":"branch","branch":"example-branch","call_id":"<uuid>","server_pid":1234}
```

Для detached: `status="detached", branch=null`. Неожиданные arguments отвергаются до Git. Root задаётся server launcher, проверяется как корень Git checkout; nested path нельзя молча принять за другой проект. Только сервер выполняет фиксированные read-only команды Git с argument arrays, `shell=False`, timeout 5 секунд на команду. Проверка repository root и `git symbolic-ref --quiet --short HEAD` различают обычную/unborn ветку, detached HEAD и ошибки; при необходимости валидность detached HEAD подтверждается отдельным read-only Git запросом. CLI не запускает Git и не читает `.git/HEAD` даже при ошибке.

Весь MCP этап ограничен 15 секундами. При ошибке до embeddings выводится безопасная категория (startup/discovery/transport/tool/invalid_result) и exit 1. Tool errors отдельно классифицируют Git missing/not-repository/timeout/failure. Stdout сервера зарезервирован протоколом; stderr содержит только собственные JSON events: event, call_id, server_pid, outcome. Секреты, raw Git stderr, полный путь пользователя и содержимое файлов не логируются. Клиент принимает только ожидаемые диагностические поля, не ретранслирует произвольный stderr.

Integration test использует настоящий subprocess/stdin/stdout transport и временный Git repository; in-process MCP и fake Git не считаются заменой этой проверки. Совпадение expected branch + call_id/PID в tool result и server event доказывает dispatch. По уточнению пользователя при apply, чтение stderr и совпадение события нужны для диагностики/integration tests и не являются условием успешного пользовательского ответа: валидный MCP result принимается и при `server_event=unavailable`. Тест отсутствующего сервера доказывает, что никакой Git fallback и никакой платный вызов не произошли. Session/process закрываются при success/error/KeyboardInterrupt, не затрагивая другие процессы.

Альтернатива прямого `subprocess git` в `/help` не выполняет задание; hosted MCP из Week 4 требует внешней доступности и здесь не используется. Отдельный read-only stdio процесс достаточен.

### 6. Trace and acceptance evidence

UX-уточнение перед видео: `--trace` по умолчанию остаётся JSONL (также явный
`--trace-format jsonl`), сериализация использует `ensure_ascii=False` и UTF-8.
`--trace --trace-format text` форматирует те же события только на границе CLI:
MCP discovery/tool/call/server_event; число найденных chunks и первые три
пути с диапазонами строк и score до трёх знаков; LLM model/status и доступные
input/output/total tokens; итог validation. Длинные идентификаторы, PID и
fingerprint в text не выводятся. Этот выбор не меняет stdout, provider payload,
retrieval, transport, validation или индекс; без `--trace` формат не включает вывод.

`--trace` печатает только whitelist метаданных: corpus/config fingerprint, chunk IDs/paths/sections/ranges/ranks/scores, MCP protocol/server identity, discovered tool, фактический call status, call_id/PID и совпадение серверного события, provider usage/status, итог validation. Trace не содержит query vector, raw question, prompt, полные chunks, credentials/env, raw stderr/upstream bodies. Обычные answer/citations являются ожидаемым пользовательским результатом и не дублируются в trace. Вопрос/ответ по умолчанию не сохраняются.

Для четырёх live-вопросов оператор может явно сохранить stdout/stderr в `backend/.local/day31/acceptance/` средствами shell; отдельный evidence framework не создаётся. `validation.md` внутри этого change на этапе реализации фиксирует corpus fingerprint, настройки, результаты и ручную оценку без секретов. Подготовленные сейчас критерии не являются результатами прогона.

### 7. Implementation footprint and acceptance sequence

Ориентир: пакет из `__init__.py` и пяти модулей (`corpus.py`, `index.py`, `service.py`, `mcp_client.py`, `git_mcp_server.py`), два launcher и три focused test files (`test_day31_index.py`, `test_day31_help.py`, `test_day31_mcp.py`). Допустима более компактная группировка без изменения контрактов. Документы: новый structure doc, Day README и corpus manifest; дополнения корневого/backend/scripts README; одна MCP dependency. Это примерно 18–20 новых/изменённых файлов реализации, без переработки общих модулей. Оценка не является квотой файлов или обещанием точного времени.

Работа выполняется тремя короткими частями: corpus/index с offline checks; MCP и CLI с integration checks; четыре live-вопроса, ручная оценка и видео. В tasks все проверки остаются незавершёнными до фактического выполнения. JVM/UI/Gradle не запускаются для Python-only изменений.

Focused regression: существующие `test_document_indexing.py`, `test_first_rag.py`, `test_grounded_rag.py`, `test_agent_adapter.py`, `test_stateful_rag.py` плюс три Day 31 test files. Новые fixtures используют fake embedder/LLM и temporary SQLite; MCP integration требует локальный Git, но не OpenAI. Широкий прогон нужен только при выявленной связанной регрессии/конфликте зависимостей.

Четыре live-вопроса после окончательной подготовки индексируемой документации:

| ID | Question | Manual pass criteria |
|---|---|---|
| Q1 | «Как связаны backend, Android-приложение и scripts в этом репозитории?» | Верные роли, направление Android → backend → OpenAI, scripts как инструменты запуска/проверок; релевантные цитаты |
| Q2 | «Где находятся индексация и поиск RAG Days 21–25, и как запускаются их CLI?» | Реальные пути `backend/app/...` и `backend/scripts/...`; нет переноса Ollama/Week 6 в эту цепочку |
| Q3 | «Как запустить JVM-тесты Android и один выбранный UI-тест по правилам проекта?» | `scripts/dev.ps1 unit` и `ui -Test`, PowerShell 7, без обязательного OpenAI для существующих UI-тестов; основание в docs |
| Q4 | «Какой SLA доступности в процентах гарантирован этому проекту и кто указан владельцем production on-call?» | Явный insufficient_context без выдуманного SLA/владельца, пустые sources/citations |

Для каждого вопроса проверяются смысл каждого существенного утверждения, соответствие цитат выводу, валидность путей/строк и отдельная актуальная ветка. Проверяемое quote совпадение само по себе не PASS качества. Готовность: три положительных вопроса содержательно корректны и полезны, отрицательный честно отклонён, MCP доказан integration test и trace, технических ошибок нет. При PARTIAL/FAIL сохраняется честный результат и исправляется конкретная причина; критерии не смягчаются автоматически ради срока. Четыре вопроса — учебная приёмка, не статистический benchmark.

Сценарий короткого видео (2–3 минуты, можно совместить с live-приёмкой): показать пять файлов корпуса и команду `index`; на уже актуальном индексе показать no-op без новых embeddings; выполнить Q2 с `--trace`, показать источники/строки и MCP discovery/call_id/server event; выполнить Q4, показать отказ и отдельно полученную ветку; кратко показать итог offline/integration-проверок. Q1/Q3 проверяются вне короткого фрагмента, если не помещаются. Не повторять успешные платные запросы только ради подготовки отчёта: сохранять вывод при первом прогоне; показ сохранённого вывода явно обозначать как replay. Видео не показывает `.env` или терминальную историю с секретами.

## Risks / Trade-offs

- Большой scripts README содержит исторические сценарии → scope instructions, Day-aware citations и ручная оценка выбранных вопросов; не подавать весь документ в generation.
- Top-8 без порога может включать слабые hits → требовать grounded abstention и проверять отрицательный вопрос; не называть cosine вероятностью релевантности.
- Ссылки на правильный файл не гарантируют правильного вывода → отдельная смысловая оценка live-ответов.
- Изменение README после индексации → обязательный freshness check; документацию результатов дополнять до финального build либо явно перестроить индекс после правки. Day README не входит в корпус, поэтому его обновление результатами само по себе rebuild не вызывает.
- MCP subprocess на Windows может зависнуть/утечь → явный timeout, корректное закрытие SDK transport, real-process cleanup test и отсутствие вмешательства в посторонние процессы.
- Установка MCP меняет общие транзитивные зависимости → использовать backend environment, проверить dependency resolution/pip check и focused regressions; не обновлять весь стек без причины.
- Snapshot актуален на момент проверки, Git — на момент вызова → не обещать атомарный снимок всего проекта во время конкурентных edits/checkout; демонстрация проводится без параллельных изменений.
- Canonical path ошибка OpenSpec под Windows → при подготовке Day 31 использован тот же установленный CLI по фактическому пути `bin/openspec.js` через Node. Ошибка вызвана несовпадением native realpath папки npm и перенаправленного файла схемы. Глобальные файлы/схемы/config и changes Days 28–30 не изменялись; это способ запуска инструмента, не часть реализации Day 31.

## Migration Plan

Миграции старых данных нет. После отдельного разрешения apply добавить только Day 31 runtime/docs/tests и MCP dependency, пройти offline/integration/regression, построить собственный индекс, выполнить live-приёмку и подготовить видео. Обновить Day README только проверенными результатами. При отказе от Day 31 достаточно не использовать его CLI; старые маршруты и индексы остаются рабочими. Автоматические commit/push/archive не выполняются: завершение дня требует отдельного запроса пользователя.
