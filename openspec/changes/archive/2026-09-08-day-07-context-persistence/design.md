## Context

Мотивация и границы — в [proposal](proposal.md). Контракты — в [conversation spec](specs/first-agent-conversation/spec.md), [Android spec](specs/first-agent-android/spec.md), [navigation spec](specs/learning-days-navigation/spec.md) и [presentation spec](specs/learning-days-presentation/spec.md).

После Day 06 `SimpleAgent.run_turn()` резервирует session, передаёт `(*session.history, user)` в LlmClient, проверяет completed reply, вызывает синхронный `session.commit(user, assistant)` и освобождает busy в finally. AgentSession хранит immutable tuple из frozen ConversationMessage; manager — dictionary по UUID. Lifespan создаёт manager заново. SQL, persistence и semantic memory отсутствуют. Архивная точка отсчёта — [Day 06 design](../2026-09-07-day-06-first-agent/design.md).

Python baseline проекта — 3.11+; существующий runtime при Explore: Python 3.14.7 со встроенным SQLite 3.50.4. В requirements нет ORM или SQLite wrapper. Backend работает одним async worker через scripts/dev.ps1. Android — один app module, MVVM, constructor injection/AppContainer, Retrofit/serialization/coroutines. SharedPreferences/DataStore/Room сейчас не используются. ChatViewModel хранит ID/count только в RAM и проверяет completed count как previous + 1; поэтому cold start с одним ID и нулевым count непригоден без metadata restore.

## Goals / Non-Goals

**Goals:** сохранить существующую границу `session.commit()`, сделать runtime sessions полностью восстановимыми, связать HTTP success с persistent commit, отделить Android identity от серверной history, переиспользовать chat UI с независимыми состояниями лабораторий.

**Non-Goals:** полный список — в proposal. Дополнительно не вводить cache eviction, TTL/cleanup jobs, session browser, auth subsystem, schema migration framework, distributed locks, фоновые flush tasks, универсальный repository/unit-of-work framework или автоперенос RAM history работающего Day 06. Локальная лаборатория не обещает high load, несколько writers/workers либо сохранение неопределённых HTTP operations через Android crash.

## Decisions

### 1. SQLite — источник истины, AgentSession — восстановимый snapshot

Добавить маленький синхронный `ConversationStore` Protocol и `SQLiteConversationStore`. Нейтральные результаты загрузки используют ID и tuple существующих ConversationMessage, без SDK/Pydantic/SQL types. `load_session` явно различает отсутствующую session и пустую history.

| Операция | Владелец orchestration | Store responsibility |
| --- | --- | --- |
| create | AgentSessionManager генерирует UUID и публикует объект только после записи | create_session(id): durable пустая session |
| get/restore | Manager возвращает cached объект либо восстанавливает один объект по ID | load_session(id): существующий ID и полная проверенная history либо отсутствие |
| successful turn | SimpleAgent решает, пригоден ли LLM outcome; AgentSession.commit сохраняет пару | append_turn(id, user, assistant): одна transaction, без append_message |
| delete | Manager проверяет busy и после записи закрывает/удаляет объект | delete_session(id): durable delete с каскадом, отсутствие идемпотентно |

Manager получает store через constructor и передаёт ту же зависимость созданным/restored AgentSession. Сессия не знает SQL, manager не формирует context, router не выполняет SQL. SimpleAgent и OpenAI adapter не меняют алгоритм, fixed config, инструкции, один вызов, full explicit history и критерий пригодного completed. Публичный LlmClient остаётся прежним.

```text
agent router --> AgentSessionManager --> ConversationStore
     |                   |
     |                   v
     +--> SimpleAgent --> AgentSession
               |              |
               v              +--> ConversationStore
           LlmClient                    |
                                        v
                              SQLiteConversationStore
```

Физическая копия history в RAM не второй источник истины: её можно уничтожить. Она обновляется только после каждой подтверждённой записи, без фоновой синхронизации. В одном worker manager хранит ровно один объект каждого ID; внешние процессы не редактируют БД во время работы приложения.

Альтернативы: RAM с flush на shutdown теряет подтверждённые turns при crash; чтение SQLite перед каждым turn корректно, но сильнее меняет AgentSession и не устраняет необходимость runtime busy registry. JSON требует собственной безопасной перезаписи файлов и atomic replace; SQLite даёт transaction границу пары без дополнительных Python dependencies. Новая универсальная memory abstraction не требуется.

### 2. Commit остаётся синхронной границей

После пригодного LLM completed AgentSession.commit выполняет:

1. Проверяет, что session не закрыта, и заранее подготавливает новый tuple snapshot.
2. Передаёт пару в append_turn; store проверяет существование session и записывает обе строки в одной SQLite transaction.
3. После успешного COMMIT заменяет RAM snapshot уже подготовленным tuple.
4. Возвращает управление агенту; только теперь router может отдать completed/count.

До результата LLM user существует только в локальном candidate. Incomplete/refused/error/invalid и cancellation до commit не вызывают append_turn. Между SQLite commit и присваиванием tuple нет await или повторной сборки больших структур. Busy снимается в существующем finally. Не переносить commit в router или manager как второй turn orchestrator.

Store оборачивает sqlite exceptions в безопасную доменную storage error без SQL/текстов сообщений; HTTP boundary возвращает существующий safe 500/internal_error, не completed. Это не нормализованный неуспех LLM и не причина повторно вызвать модель. Android сохраняет консервативное unknown-outcome поведение текущего процесса для 5xx на send. При неудаче записи RAM не продвигается; store делает rollback. Если rollback/connection не позволяет надёжно продолжать работу, дальнейшие storage operations завершаются безопасной ошибкой до повторной инициализации, без fallback в RAM-only mode.

Crash до SQLite commit оставляет старую history, crash после commit восстанавливает всю новую пару. Crash после commit, но до HTTP delivery, остаётся неопределённым для клиента: нет receipts, idempotency или exactly-once обещания.

### 3. Минимальная schema и явные transactions

| Таблица | Поля/ограничения |
| --- | --- |
| sessions | session_id TEXT PRIMARY KEY NOT NULL |
| messages | session_id TEXT NOT NULL; position INTEGER NOT NULL; role TEXT NOT NULL; content TEXT NOT NULL |
| Ключ сообщений | PRIMARY KEY(session_id, position) |
| Связь | FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE |
| Checks | position >= 0; role IN ('user', 'assistant') |

Position начинается с 0; последовательность непрерывная, чётные позиции — user, нечётные — assistant. Load сортирует по position и проверяет positions, допустимые роли и полные пары. Не исправлять повреждённую history, не выкидывать отдельные строки, не превращать ошибку чтения в session_not_found. Для отсутствующего ID load возвращает отсутствие; для существующего ID без messages — пустой tuple. Ни timestamps, ни history_turn_count в БД не добавляются: count выводится из числа полных пар.

На connection до transactions явно включить `PRAGMA foreign_keys=ON` и сохранить обычный rollback journal с `synchronous=FULL`; WAL и выключение journal/sync не нужны. Не вводить ORM/Alembic/aiosqlite.

Для Python 3.11+ выбрать один явный режим: `isolation_level=None` и SQL BEGIN/COMMIT/ROLLBACK. На версиях с параметром autocommit явно передавать `LEGACY_TRANSACTION_CONTROL` для этого режима; на 3.11 параметра нет. Так поведение не зависит от будущей смены sqlite3 defaults и не требует поднятия baseline. Writes используют короткий BEGIN IMMEDIATE; значения передаются SQL parameters. Не смешивать этот режим с неявными transactions или per-message autocommit.

Create: INSERT session и COMMIT до публикации runtime object/201. Append: проверить существование, получить следующие positions и вставить обе строки до единственного COMMIT; не делать upsert отсутствующей session. Delete: DELETE session с FK cascade и COMMIT до изменения runtime объекта/204. Schema initialization — отдельная короткая transaction при startup, без destructive recreate; несовместимая/повреждённая schema даёт явную ошибку запуска. Read заканчивается до возврата результата, без открытой transaction во время LLM I/O.

### 4. Connection, путь и lazy restore

Один store/connection на lifespan, созданный и используемый в том же event-loop thread. Синхронные короткие операции не имеют await; существующие busy/closed guards остаются атомарными относительно event loop. Не переносить отдельные вызовы общего connection в произвольный thread pool и не выключать check_same_thread для обхода ошибок. Ожидание SQLite lock ограничено коротким timeout; не добавлять application retry queue. Между LLM-вызовами разных sessions общий connection не держит transaction/lock.

Путь по умолчанию — `<repository-root>/.local/agent/conversations.sqlite3`, вычисленный от расположения backend package, не от shell cwd. Конкретный Path передаётся store извне, чтобы tests использовали tmp_path. `.local/` уже есть в .gitignore и включает journal/sidecar files; новые широкие ignore rules не требуются. Не хранить SQLite в backend source tree, test fixtures или tracked data.

Lifespan открывает store, проверяет/создаёт schema и создаёт manager с пустым `_sessions`. Manager.get возвращает existing runtime object; при cache miss выполняет load, восстанавливает объект с тем же ID/history, `_busy=False`, `_closed=False` и помещает в mapping. Check/load/register не прерываются await, поэтому нет двух restored runtime objects одного ID. Startup не читает все conversations. Preload тратит RAM/startup time на неиспользуемые sessions; lazy restore соответствует существующему get.

Shutdown закрывает connection и созданный SDK client, в том числе при частичной ошибке инициализации. Shutdown не выполняет обязательный flush history: всё подтверждённое уже записано. Runtime busy/locks/requests/pending user/request_id/closed/client state не сериализуются. Локальная БД существует независимо от старых Store/Manager/AgentSession objects.

### 5. Durable delete без оживления старой ссылки

Manager.delete сначала проверяет busy, если объект есть в mapping. Persistent delete вызывается независимо от cache hit: после restart session может быть ещё не загружена. После успешного COMMIT cached object помечается closed, его RAM history очищается и mapping удаляется, без await между шагами. Старая ссылка отвергается begin_turn/commit как и в Day 06. Если запись удаления падает, cached object не закрывается и не очищается.

Отсутствующий UUID остаётся 204. Никаких tombstones или persisted closed flags: durable отсутствие строки достаточно при одном worker и запрете автоматически создавать неизвестные IDs. Если turn первым занял session, delete получает 409; если delete завершён первым, новый/stale turn получает 404.

### 6. Metadata GET сохраняет небольшой HTTP contract

Добавить GET `/api/v1/agent/sessions/{session_id}` с существующим SessionResponse `{session_id, history_turn_count}`. Router вызывает manager; metadata lookup возвращает ту же cached/restored session, а проверка свободного состояния выполняется в session/manager без резервирования turn и без SQL в router. Busy даёт 409, чтобы cold start не принимал count выполняющейся попытки за готовую baseline. 404/422/500, safe error envelope и X-Request-ID остаются в AgentRoute. GET не вызывает SDK и работает без OPENAI_API_KEY.

Нет GET history, model/config fields, instructions или diagnostic snapshot. `history_turn_count` относится ко всей durable history, а не числу Android bubbles. Тексты session_not_found в router, repository и ViewModel обновить на «Диалог недоступен. Начните новый диалог»: штатный restart теперь сохраняет ID.

Вариант без GET потребовал бы nullable count и особых проверок первого turn. С GET ViewModel восстанавливает baseline и сохраняет проверки completed = before + 1 / known failure = before. Это не receipt и не reconciliation неопределённого HTTP-запроса.

### 7. Один chat implementation, два независимых состояния лабораторий

Добавить Day 07 entry/destination после Day 06. Переиспользовать ChatScreen, ChatViewModel, ChatRepository/API и backend subsystem. Параметризовать header/lesson identity существующего ChatScreen; не копировать экран или ViewModel в почти идентичные классы.

В Activity создать два keyed activity-scoped экземпляра того же ChatViewModel: Day 06 и Day 07. У них независимы ID, transcript, draft, operation, count и scroll generation; repository общий. Только экземпляр Day 07 получает optional CurrentSessionStore. Day 06 остаётся без Android identity persistence, но его sessions обслуживает тот же SQLite-backed manager. Это разделение учебных состояний, не второй volatile backend Agent. Reset одного урока не затрагивает другой.

Добавить idempotent initialization Day 07 при первом входе на экран: ViewModel один раз читает локальный ID и, при наличии, получает metadata. Не стартовать restore при создании всех ViewModels в MainActivity, когда открыт каталог. Возврат/rotation не запускают второй GET; coroutine живёт в viewModelScope. Явное действие retry после завершившейся ошибки не нарушает это правило. Каталог после обычного cold launch остаётся entry screen; для live пользователь открывает карточку Day 07.

Альтернативы: один shared UI state для двух карточек смешивает эксперименты и reset; второй stack дублирует поведение. Два экземпляра одних компонентов сохраняют независимость без нового domain/use-case слоя.

### 8. CurrentSessionStore хранит только nullable sessionId

Добавить маленький constructor-injected интерфейс `CurrentSessionStore` с suspend read/save/clear и `SharedPreferencesCurrentSessionStore`. Использовать application context, private именованный preferences file и один ключ текущего Day 07 ID. Создание — в AppContainer, которому Application передаёт context. ViewModel не импортирует SharedPreferences или Context. Все reads/writes/clear выполняются на Dispatchers.IO; Editor.commit() проверяется, fire-and-forget apply() не используется для подтверждения durability.

Store хранит только nullable ID: не count, transcript, draft, flags, receipts или pending operations. Room/DataStore для одного значения не добавляются. Ошибки чтения/записи/очистки возвращаются как безопасные локальные ошибки и не маскируются под пустое storage. Непригодный сохранённый ID не используется для автоматического create: UI требует явного reset.

Первая отправка Day 07: create -> сохранить ID с подтверждённым результатом -> один send. Полученный ID сначала удерживается в runtime как ещё не подтверждённый локально, поэтому ошибка save сохраняет draft/ID и явный повтор повторяет save до send, без второго create. Этот runtime guard не persistится. Ошибка create не добавляет turn; неизвестный create outcome может оставить пустую orphan backend session, её автоматический сбор вне scope.

Cold start без ID заканчивается пустым UI без HTTP. С ID: RESTORING -> GET -> проверить совпадение ID и count >= 0 -> ready с пустыми messages и baseline count. Показывать сообщение восстановления и не использовать обычную подсказку нового пустого диалога. Во время restore count существующей session неизвестен, поэтому не показывать фиктивный 0 как достоверный результат. GET network/5xx/invalid response или 409 сохраняют ID, блокируют send и дают «Повторить восстановление»; 404 даёт явный reset. Ошибка локального read блокирует create/send/reset, пока повторное чтение не выяснит ID; не очищать неизвестную backend identity по предположению.

Reset Day 07: DELETE 204 -> подтверждённый local clear -> пустой ChatUiState/new generation. При delete failure local ID не очищается. При clear failure UI сохраняет прежний вид с recoveryRequired и разрешает только явный reset; повтор DELETE идемпотентен. Backend deletion и Android clear не образуют distributed transaction: crash между ними оставляет stale local ID и безопасный 404/повторный reset, но не resurrected backend conversation.

Для локальной некорректной identity после успешного чтения, когда валидного backend UUID нет, явный reset очищает только локальный ключ с проверкой результата, без попыток создать/угадать backend session.

### 9. Recovery scope и transcript

Day 07 гарантирует продолжение после подтверждённых завершённых operations: факт/count 1 получен, оба процесса остановлены, после запуска metadata восстанавливает identity/count, следующий вопрос использует полную backend history. Полный Android transcript намеренно не восстанавливается, LLM context не воссоздаётся из bubbles.

После transport failure send в живом процессе сохраняется правило Day 06: unknown outcome -> recoveryRequired -> явный reset. Не сохранять recoveryRequired, in-flight operations или outcome markers через process crash. Force-stop во время неопределённого send/reset за пределами Day 07 acceptance; GET count не доказывает судьбу конкретного запроса. Никогда не replay'ить сообщения при восстановлении и не обещать exactly-once.

### 10. Проверяемые границы

Backend tests используют реальный файл `tmp_path / conversations.sqlite3`, независимые Store/Manager A и B и fake LlmClient. A сохраняет U1/A1, закрывает connection; тест теряет ссылки на A/manager/sessions, B открывает тот же файл и получает тот же ID/history. Следующий fake input проверяется как точный tuple U1/A1/U2, не через смысл ответа. Дополнительно: многоходовый Unicode/text round-trip, isolation после reopen, пустая session, неизвестный ID, неподходящие outcomes/cancellation, storage failure без RAM advance, rollback между двумя INSERT, delete unloaded session/reopen, busy/runtime flags reset, schema/history integrity и connection lifecycle.

Для реального rollback-теста можно установить trigger только в test DB, прерывающий INSERT assistant: production append_turn выполнит первый INSERT, получит ошибку на втором и откатит transaction. Дополнительно fault injection commit failure проверяет запрет успешного ответа и сохранность RAM. Не добавлять test hooks или общий fault framework в production ради этих проверок. OS-level child-process crash test не обязателен; reopen/rollback и отдельный live restart достаточны для этого Day.

API tests получают выделенный DB path через test wiring до запуска lifespan, чтобы существующая fixture никогда не открывала пользовательскую `.local` БД. Проверяются POST/create/delete commits, точное тело GET ID/count, отсутствие LLM/key requirement, safe 404/409/422/500, X-Request-ID и неизменный strict message DTO.

Android JVM tests используют fake CurrentSessionStore и существующий coroutine test setup: save до send, errors/retry без повторного create, metadata до send, count baseline, no-ID без HTTP, no replay, reset order и failures. Retrofit interceptor проверяет настоящий serialized GET/POST/DELETE и body ровно с новым message. Небольшой instrumented test проверяет реальный private SharedPreferences store между экземплярами на отдельном test file и очистку, не трогая пользовательский ключ. Activity recreation не выдаётся за process restart.

UI tests покрывают отдельную карточку/заголовок Day 07, restore/error/empty-transcript notice/count, доступность IME, независимость состояний Day 06/07, navigation/rotation без повторного restore/turn/reset. Regressions Day 02–05 и Agent semantics Day 06 сохраняются. Только тест старого volatile restart намеренно заменяется persistence expectation; не ослаблять context/payload/assertions для прохождения.

Live/video после offline checks: подготовить backend и проверить доступность с эмулятора; открыть Day 07; отправить выдуманный факт «Мой условный код — сиреневый маяк 731» и дождаться фактического успеха/count 1; полностью остановить backend; force-stop Android без clear app data; снова запустить backend и проверить доступность; запустить Android и открыть Day 07; увидеть restore/count 1; явно спросить код и получить фактический ответ/count 2. Не повторять автоматически платные запросы ради нужной формулировки. Fake input — oracle для context, live результат фиксируется только после проверки/подтверждения пользователя.

## Risks / Trade-offs

- [SQLite I/O блокирует event loop] -> короткие synchronous transactions и ограниченный lock timeout, один worker; high-load async database layer вне scope.
- [Несколько backend managers одновременно пишут одну session] -> production wiring содержит один manager/worker; тестовые reopen instances последовательны. SQLite commit не заменяет session busy на всём интервале LLM await.
- [RAM и БД расходятся] -> подготовка tuple до записи, COMMIT до присваивания, без await в критической границе; storage failure не включает RAM-only fallback.
- [Повреждённый storage принят за пустой диалог] -> fail explicitly, проверять пары/roles/order, не восстанавливать из UI и не исправлять данные молча.
- [Ответ потерян после persistent commit] -> текущий процесс требует reset; нет replay, receipts или гарантии доставки. Crash внутри неопределённой операции не входит в acceptance.
- [Local ID пережил backend delete] -> GET 404 и идемпотентный явный reset; удалить backend conversation заново безопасно.
- [Накопление orphan sessions и рост full context] -> для лаборатории явный delete; TTL, автоматическая уборка и trimming не добавляются. Restart больше не является очисткой истории.
- [Day 06 случайно перехватывает Day 07 ID] -> разные keyed ViewModel instances и отдельное подключение CurrentSessionStore только для Day 07; один backend stack.
- [Основные specs опережают код] -> синхронизация сделана по явному запросу на этапе planning; proposal фиксирует целевой статус, tasks остаются незавершёнными, архив Day 06 не переписывается.

## Migration Plan

1. Создать store/schema и offline tests; подключить store к session/manager и lifespan, не меняя SimpleAgent algorithm. Старые services Day 02–05 не переводить на Agent API.
2. Добавить metadata GET и безопасные ошибки. Все tests направить в отдельную test DB; `.local` application DB не использовать в pytest.
3. Добавить Android identity store, restore/reset state transitions, затем вторую lesson identity на общих chat-компонентах и navigation/presentation.
4. В apply создать `day-07-context-persistence/README.md` по трём разделам AGENTS.md; обновить backend/Android README и при необходимости scripts README с lifecycle/DB path/restart commands. Day 06 README сохранить как итог исторического эксперимента, кратко отделив его in-memory реализацию от текущего накопительного backend; не переписывать архивные фактические результаты.
5. Выполнить backend pytest, Android unit/build через PowerShell 7 scripts/dev.ps1 и полный UI suite после связанных navigation изменений. Live restart выполнить отдельно, в управляемом backend терминале; /health не считать проверкой OpenAI. Записать только проверенные результаты.
6. Перед завершением проверить OpenSpec strict validation, Git diff и отсутствие локальной БД/секретов. Commit/push/archive только по отдельному запросу завершения задания.

Data migration из RAM Day 06 отсутствует: первый запуск SQLite начинает с пустой БД, затем подтверждённые sessions сохраняются. Данные до внедрения не обещаются сохранёнными. Архив Day 06 и Git commit остаются историческим воспроизводимым состоянием; не создавать совместимый volatile backend параллельно.

Rollback реализации — вернуть прежнее wiring/UI через отдельное согласованное изменение; SQLite file не удалять автоматически. Прежний код не прочитает durable sessions, поэтому rollback теряет доступ к ним в приложении, но не должен физически уничтожать файл. Схема и данные Day 07 не мигрируют в RAM предыдущего процесса.

Все решения, влияющие на scope и acceptance, определены; блокирующих вопросов для apply нет.
