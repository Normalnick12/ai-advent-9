# Day 31 — фактическая проверка

Дата: 16 октября 2026, Windows. Этот документ дополняется фактическими результатами;
наличие planning-артефактов не считается выполнением runtime-проверок.

## Окружение и совместимость

- Python 3.14.7; OpenAI SDK 2.54.0; MCP SDK 2.2.0.
- FastAPI 0.141.1, HTTPX 0.28.1, Pydantic 2.13.5, tiktoken 0.14.0, pytest 9.1.1.
- `pip install -r backend/requirements-dev.txt` выполнен; существующие пакеты backend не обновлялись. `pip check`: **No broken requirements found**.
- Импорт `app.main` после установки MCP успешен, без запуска сервера или LLM.
- Официальная документация подтверждает alias `gpt-5.6`, reasoning `none`, Responses и Structured Outputs: [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol). Embedding profile: [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). Фактическая доступность проверяется live-запросами ниже; документация сама по себе её не доказывает.
- Наличие `OPENAI_API_KEY` проверено булевым результатом; значение не выводилось. Ключ используется только backend-клиентами, дочерний MCP-процесс его не наследует.

## Offline / integration

Целевой прогон:

```powershell
Push-Location .\backend
try {
    & .\.venv\Scripts\python.exe -m pytest tests/test_day31_index.py tests/test_day31_mcp.py tests/test_day31_help.py tests/test_document_indexing.py tests/test_first_rag.py tests/test_grounded_rag.py tests/test_agent_adapter.py tests/test_stateful_rag.py -q
} finally { Pop-Location }
```

Окончательный результат: **160 passed in 23.85s**. Из них новые Day 31:
23 index/corpus, 14 MCP и 19 help/CLI проверок; 104 проверки существующих
компонентов. OpenAI в тестах не вызывался. Ранее, до уточнений live-приёмки,
прогон содержал 158 тестов и также проходил; два дополнительных теста проверяют
границы schema и вводный контекст документа.

- Проверены exact five-file allowlist, запрещённые пути, дубликаты, UTF-8, размеры, reparse rejection, отсутствие link crawling.
- Проверены source slices/строки/Unicode, batches, одночанковый индекс, hash/config freshness, no-op без embedder, corruption/nonfinite vectors, сохранность старой базы при failed rebuild/write/replace.
- Настоящий MCP subprocess через stdio во временном Git repository: discovery, tool schema, read-only annotations, вызов, unborn branch, commit/branch switch/detached HEAD, call_id/PID/server-event correlation, завершение процесса.
- Проверены ошибки missing server/not-repository/missing tool/malformed result/disconnect/timeout, отсутствие parent Git fallback и provider calls, cleanup при exception/cancellation.
- Валидный MCP result успешно используется и при `server_event=unavailable`; stderr-событие не является prerequisite ответа.
- Проверены actual generation payload, один query embedding/одна generation, source/quote validation, abstention, refused/incomplete/error, безопасный trace, CLI из другого cwd и справка без API.

На первых targeted прогонах исправлены два тестовых/адаптерных дефекта:
fixture повторно конвертировал Windows CRLF; SDK оборачивает ошибки контекстных
менеджеров в ExceptionGroup, поэтому клиент разворачивает его в безопасную категорию.
Окончательный целевой прогон выше выполнен после исправлений.

Завершающие проверки: синтаксис 11 новых Python-файлов через `ast.parse`, JSON
manifest, относительные ссылки новых Markdown, единственная корневая ссылка Day 31
и существование её цели — PASS. Scoped secret/local-file scan 26 изменённых/новых
файлов и `git diff --check` — PASS; индекс и acceptance evidence подтверждены
через `git check-ignore`. `openspec validate day-31-developer-assistant --strict`:
**Change is valid**. После обновления отчёта и Day README read-only `fresh()`
подтвердил финальный fingerprint и 87 chunks без API-запросов.

## Настоящий индекс

Полный корпус: `README.md`, `docs/project-structure.md`, `backend/README.md`,
`android-app/README.md`, `scripts/README.md`. Его описание составлено по фактическим
файлам проекта; в ходе live-проверок `docs/project-structure.md` не менялся под вопросы.

Финальная сборка после уточнения документации поведения Day 31:

- Strategy: structure-aware, 87 chunks, 500 tokens / oversized overlap 50.
- `text-embedding-3-small`, 1536 dimensions; **3 requests, 28 429 provider tokens**.
- Corpus hash: `2e11ad2341909880593d2c024dbf42c94061ada96a8446a79a488e841a32d605`.
- Fingerprint: `c8a219df6fcc17501daaf49524dd0616ead831ae453a05ca7e48cadac89bbf83`.
- Локальное evidence: `backend/.local/day31/acceptance/index-v8.json`.
- Повторный `index` после финальной сборки: **unchanged**, тот же fingerprint, **embedding_calls=0, provider_tokens=0**.

Первая сборка до уточнений README: 86 chunks, 3 requests, 28 228 tokens,
fingerprint `70f67529e8eb04849711f583909d698a163653fe235218f414153b0389adb497`.
Её повторный `index` вернул `unchanged`, `embedding_calls=0`, `provider_tokens=0`.
Промежуточная сборка v7: 87 chunks, 3 requests, 28 443 tokens. Таким образом,
все три явные сборки использовали 9 embedding requests и 85 100 tokens.
После изменения разрешённой документации индекс был явно перестроен;
исторические базы других дней не изменялись. Последние правки Day README и
OpenSpec не входят в allowlist и не меняют актуальность индекса.

## Ошибки и исправления live-приёмки

Все попытки сохранены локально в ignored `backend/.local/day31/acceptance/`;
успешные результаты не перезаписывались. Автоматических retries не было.

| Попытка | Фактический результат | Исправление / вывод |
|---|---|---|
| Q1, первый запуск | FAIL до OpenAI: `mcp_tool_error`; серверная причина `not_repository_root`, Git diagnostic — dubious ownership | Изолированный MCP не наследует глобальные Git trust settings. Сервер передаёт `-c safe.directory=<fixed root>` только своим read-only Git-командам; глобальная конфигурация не менялась. После этого 31 затронутый тест прошёл |
| Q1-retry, Q2, prompt v1 | PASS по фактам, API completed, источники прошли validation | Подтверждена фактическая совместимость `gpt-5.6` → `gpt-5.6-sol`, Responses и MCP |
| Q3, prompt v1 | FAIL: `section_mismatch`, два `quote_not_found` | Невалидный ответ не выдан как проверенный; instructions уточнены |
| Q1-final, Q2-final, prompt v2 | PASS; Q2 цитаты покрывают перечисление Days | Точные пути и известные команды подтверждены; неполнота retrieval для отдельных CLI обозначена |
| Q3-final, prompt v2 | FAIL: section mismatch и две неточные цитаты | Одной текстовой инструкции недостаточно; добавлены context-bounded enum |
| Q1-v3, Q3-v4 | FAIL: Responses HTTP 400, `llm_invalid_request`; generation usage не предоставлен | Strict schema содержала реальные переводы строк в quote enum |
| Разрешённый отдельный диагностический запрос | HTTP 400, `invalid_json_schema`, `text.format.schema`: перевод строки недопустим в enum string literal при strict=true | До явного разрешения пользователя запрос был отклонён auto-review и не исполнялся. После разрешения выполнен ровно один диагностический запрос; ключ/окружение не выводились. Точные enum варианты ограничены физическими строками |
| Q3-v5 | Technical PASS, semantic PARTIAL | Команды верны, но PowerShell 7 пропущен: введение README не попало в чистый cosine Top-8 |
| Q3-v6, Q1-v6 | PASS: введение вернуло общее условие PowerShell 7 | Правило source_intro отдельно одобрено пользователем; документация не подгонялась под Q3 |
| Q2-v6 | FAIL: `chunk_sets_mismatch` | LLM больше не дублирует metadata в sources; CLI формирует sources из проверяемых citation IDs, итог проверяет прежний валидатор. Текст/цитаты не исправляются, дополнительных генераций нет |
| Q2-v7 | PASS | Устранено дублирование sources, но копирование цитат моделью ещё оставалось |
| Q3-v7 | FAIL: `quote_not_found` | Текстовые quote enum недостаточно надёжны для буквального копирования. Финальный контракт выбирает короткие ASCII evidence IDs; CLI восстанавливает неизменённые цитаты и metadata из текущего контекста |

Окончательная версия: `day31-help-v8`, одинаковый output budget 3000,
reasoning none, до восьми chunks с одобренным source_intro. Schema перечисляет
короткие evidence IDs, а не текст цитат. В контекст передаются исходный текст и
до 24 буквальных отрезков строк на chunk; цитаты и metadata формируются из
выбранных ID без изменения текста ответа. Неизвестные/повторные ID и невалидный
candidate отклоняются; итоговый контракт GroundedResponse и прежняя проверка
происхождения/совпадения цитат сохранены. Дополнительных генераций для исправления
ответа нет. Это устраняет ошибку копирования, но смысловая поддержка утверждений
по-прежнему требует оценки. Ограничения Structured Outputs сверены с
[официальным руководством](https://developers.openai.com/api/docs/guides/structured-outputs).

## Финальные четыре вопроса

Все четыре запуска выполнены настоящим CLI на финальном fingerprint и версии v8.
Каждый сделал одно query embedding, один Responses request и настоящий MCP-вызов.
`requested_model=gpt-5.6`, `resolved_model=gpt-5.6-sol`, provider status completed,
grounded validation passed. Ниже — ручная оценка после чтения stdout и trace.

| Вопрос | Ручной итог | Проверенные факты и источники |
|---|---|---|
| Q1: Как связаны backend, Android-приложение и scripts в этом репозитории? | **PASS** | Android → FastAPI backend → OpenAI, ключ только backend; scripts управляют разработкой/запуском/проверками. `docs/project-structure.md:3–24,25–34`, `android-app/README.md:1–10`, `backend/README.md:1–10`, `scripts/README.md:365–379` |
| Q2: Где находятся индексация и поиск RAG Days 21–25, и как запускаются их CLI? | **PASS** с явно указанной неполнотой retrieval | Правильно перечислены пять модулей и CLI, historical corpus, backend Python, примеры Day 22 и 24. `docs/project-structure.md:52–73`, `scripts/README.md:257–290,316–329,120–151`. Ответ прямо ограничивает знание точных подкоманд Days 21/23/25; отсутствие в найденных фрагментах не означает отсутствие во всём репозитории |
| Q3: Как запустить JVM-тесты Android и один выбранный UI-тест по правилам проекта? | **PASS** | PowerShell 7, корень проекта, `dev.ps1 unit -Test` и `ui -Test Class#method`, выбор затронутых тестов, запрет параллельных Gradle-запусков, backend не нужен. `scripts/README.md:1–7,520–532,365–379,533–542`. Вводный контекст содержит общее требование PowerShell 7 |
| Q4: Какой SLA доступности в процентах гарантирован этому проекту и кто указан владельцем production on-call? | **PASS**, отрицательный сценарий | `insufficient_context`, канонический отказ без выдуманного SLA/владельца, sources/citations пусты. Отдельно показана реально полученная MCP-ветка `main` |

Во всех четырёх ответах Git-блок отделён от документационного ответа. MCP trace:
protocol `2026-07-28`, server `Day 31 Git MCP`, tool `get_current_branch`, discovery
и call completed. Корреляция ниже диагностическая: отсутствие stderr event при
валидном result не блокирует пользовательский ответ.

| Вопрос | MCP call_id | Server PID | Server event | Query embedding tokens | Responses input / output / total |
|---|---|---:|---|---:|---:|
| Q1 | `d1700e25-912b-4a4f-b6d1-8ed0d2574953` | 24740 | matched | 26 | 5494 / 378 / 5872 |
| Q2 | `bf9b6db0-4e38-4bce-9aa9-e643fafdcf89` | 25048 | matched | 32 | 9434 / 704 / 10138 |
| Q3 | `4d0f389c-4ca4-4c7a-a403-ab804effdcbd` | 15240 | matched | 30 | 5574 / 422 / 5996 |
| Q4 | `9a5c89ba-988d-4a45-a8f4-2b51797e068d` | 25004 | matched | 36 | 5439 / 45 / 5484 |

Финальные четыре вопроса: **124 query embedding tokens, 27 490 Responses tokens**.
Это usage только итогового прогона, не всех диагностических попыток таблицы выше.
Локальные фактические ответы и trace: `backend/.local/day31/acceptance/Q1-v8.out.txt`
… `Q4-v8.out.txt` и соответствующие `Q1-v8.trace.jsonl` … `Q4-v8.trace.jsonl`.
Они ignored; отчёт хранит воспроизводимые команды, оценки, источники и идентификаторы,
а не секреты или сырые API payload.

## Видео

UX-исправление перед записью, 16 октября 2026: добавлен опциональный
`--trace --trace-format text`. По умолчанию сохранён JSONL со всеми полными
идентификаторами; Unicode сериализуется через `ensure_ascii=False`. Изменены
только CLI-форматирование, его тесты и OpenSpec-описание/команды; основной renderer,
retrieval, prompts, MCP transport, validation и документы корпуса не менялись.

Проверка после исправления:

```powershell
Push-Location .\backend
try {
    & .\.venv\Scripts\python.exe -m pytest tests/test_day31_help.py tests/test_day31_mcp.py -q
} finally { Pop-Location }
```

**38 passed in 13.01s**: default/explicit JSONL, text и отключённый trace,
Unicode/JSON roundtrip, полные IDs только в JSONL, три пути с округлённым score,
доступный/отсутствующий usage, серверное событие unavailable, экранирование
управляющих символов, отсутствие секретов/вопроса в trace и одинаковый stdout
основного ответа/Git/источников. MCP-регрессии используют настоящий локальный
сервер без OpenAI.

Отдельно в **PowerShell 7.6.5** выполнен offline replay сохранённых Q3-v8 stdout
и событий через новый formatter: кириллица, Git-блок и цитаты читаются корректно;
text trace занимает семь строк, без hash/chunk IDs/fingerprint. Это проверка
представления уже сохранённой приёмки, не новый live-запрос. Платные запросы,
переиндексация и новая live-приёмка для UX-изменения не выполнялись.
Проверки синтаксиса изменённых Python-файлов, `git diff --check`, CLI-справки и
строгая OpenSpec validation успешны. Read-only freshness подтвердил прежние
87 chunks и fingerprint; roundtrip сохранённого trace сохранил все JSONL поля.

Конкретные команды и порядок показа: [demo.md](demo.md). Сохранённый stdout/trace
можно показать как явно обозначенный replay; повтор API для чтения результата
не нужен. По подтверждению пользователя при финализации видео записано отдельно
от репозитория. Ассистент не проверял файл записи и не добавлял его в Git.

## Границы проверки

Программная проверка цитат подтверждает их происхождение и буквальное совпадение,
но не смысловую поддержку ответа. Четыре live-вопроса — учебная приёмка, не benchmark.
Android/JVM/UI/Gradle не затронуты и не запускались. На этапе реализации
commit, push и archive не выполнялись; финализация отдельно разрешена пользователем.

## Финализация 16 октября 2026

- **Reused:** целевой набор 160 тестов до UX-уточнения, 38 CLI/MCP-тестов после него, Q1–Q4 live PASS и проверка PowerShell 7.6.5. Это разные пересекающиеся наборы, их количества не складываются. После успешных прогонов runtime и тесты больше не менялись.
- **Run:** полный review состава Day 31, `git diff --check`, scoped scan секретов/локальных файлов, проверка root README, документационных ссылок/команд и синтаксиса. Для проверки контрактов просмотрены CLI, RAG service, настоящий MCP transport/server и целевые тесты; UX затронул только форматирование trace.
- Корпус сохранён без изменений при финализации. Обновления Day README и OpenSpec в индекс не входят; новый платный build/live не требуется.
- **Run:** read-only `fresh()` и `build(forbidden_provider_factory)` подтвердили прежний fingerprint, 87 chunks и `unchanged`/ноль API-вызовов. Все относительные Markdown-ссылки изменённых файлов и упорядоченная единственная root-ссылка Day 31 — PASS. `git check-ignore` подтверждает исключение `.env`, SQLite и acceptance evidence.
- Видео подтверждено пользователем; сам файл записи не проверялся.
- OpenSpec: все 24 задачи и planning-артефакты завершены. `validate day-31-developer-assistant --type change --strict --no-interactive` — PASS. Две новые основные спецификации `developer-assistant-help` (7 требований) и `local-git-branch-mcp` (4 требования) синхронизированы, полностью сверены с delta и прошли strict validation.
- Change архивирован штатным CLI как `openspec/changes/archive/2026-10-16-day-31-developer-assistant/`. `archive --yes --skip-specs --json` использован после отдельной завершённой синхронизации: флаг исключает её повторное применение, а не пропускает sync. Старые changes Days 28–30 сохраняются без изменений.
- После архивации полное сравнение обеих delta с основными спецификациями — PASS; контрольная сумма 39 файлов changes Days 28–30 не изменилась. Старые незавершённые задачи и конфигурация OpenSpec не исправлялись.
- `git fetch origin` успешен; перед commit локальная `main` и `origin/main` совпадали (0 ahead / 0 behind). Commit и штатный push выполняются после итоговой проверки staged snapshot; hash и результат сообщаются в финальном отчёте.
