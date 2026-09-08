## Why

После Day 06 история существует только в runtime AgentSession и исчезает вместе с backend process; Android также теряет identity диалога при cold start. Day 07 меняет lifecycle состояния с volatile in-memory context на durable persistent context и демонстрирует продолжение той же session после перезапуска обоих процессов без изменения алгоритма SimpleAgent и полной явной передачи history.

## What Changes

- SQLite через стандартный Python sqlite3 становится durable source of truth; AgentSession держит восстановимый RAM snapshot. Минимальный ConversationStore отделяет create/load/append successful turn/delete от SQL.
- Только SQLite commit пары user/assistant разрешает обновить RAM snapshot и вернуть успешный turn. Ошибки хранения не продвигают RAM history и не изображают успех.
- **BREAKING lifecycle guarantee:** backend restart больше не уничтожает сохранённые sessions. Пустой runtime mapping заполняется lazy restore по известному ID; неизвестный ID по-прежнему не создаётся автоматически.
- Delete удаляет session/history durable до закрытия runtime object и HTTP 204; busy и прочие runtime flags не сохраняются.
- Добавляется read-only GET `/api/v1/agent/sessions/{session_id}` с ID/count, без LLM-вызова и экспорта history.
- Отдельная Android-карточка Day 07 «Сохранение контекста» переиспользует chat-компоненты Day 06. Только текущий Day 07 sessionId сохраняется через CurrentSessionStore/private SharedPreferences; после cold start GET восстанавливает identity/count, но не transcript.
- После create Android подтверждает локальную запись ID до первого send; reset сначала подтверждает backend delete, затем локальную очистку ID. Автоматического replay нет.
- Гарантия Android recovery относится к подтверждённому состоянию между завершёнными операциями. Pending operations, recoveryRequired и unknown transport outcome markers через process crash не восстанавливаются.
- Актуальные OpenSpec requirements обновляются по явному запросу уже на этапе planning; это целевые guarantees Day 07, не отметка о готовой реализации. Архив Day 06 и история Git сохраняют прежний lifecycle.

## Capabilities

### New Capabilities

Нет: persistence развивает существующие conversation/chat capabilities.

### Modified Capabilities

- `first-agent-conversation`: durable SQLite history, store boundary, атомарность persistent commit/delete, lazy restore и metadata GET при прежней Agent semantics.
- `first-agent-android`: общий chat lifecycle с отдельным Day 07 identity persistence, metadata restoration, подтверждённым reset и ограниченным crash-recovery scope.
- `learning-days-navigation`: шестая карточка Day 07 и независимые состояния двух лабораторий на переиспользуемых chat-компонентах.
- `learning-days-presentation`: русское название/описание Day 07 и понятные состояния восстановления без старого transcript.

## Impact

Backend: новые ConversationStore/SQLiteConversationStore, изменения AgentSession/AgentSessionManager, lifespan и agent router; нейтральный LlmClient, алгоритм SimpleAgent и OpenAI adapter сохраняются. БД находится в игнорируемой `.local/agent/conversations.sqlite3`, путь не зависит от shell cwd. Один worker и короткие синхронные SQLite operations сохраняют минимальную модель исполнения.

Android: CurrentSessionStore и SharedPreferences implementation, ChatRepository/API, ChatViewModel/Screen, AppContainer/Application/Activity wiring, каталог и строки. Day 06/07 используют один backend Agent subsystem, общий repository и один тип chat UI/ViewModel с отдельными экземплярами состояния; второй volatile backend Agent не вводится. Новые ORM, Alembic, WAL, Room, DataStore и persistence frameworks не требуются.

Проверки: реальный временный SQLite, close/reopen независимых Store/Manager, exact fake-LLM context, rollback/storage failures, isolation/delete/runtime lifecycle, HTTP и Android contracts, регрессии Day 02–06 и отдельный live restart. OS-level child-process crash test не обязателен. Документация реализации: `day-07-context-persistence/README.md` и README общих компонентов, без выдуманных результатов.

Non-goals: long-term semantic memory, MemoryManager/framework, vector DB/embeddings, summarization/compression, sliding window/token trimming, RAG/MCP, planning/tools, Agents SDK, Redis/Postgres/cloud persistence, full transcript recreation, idempotency/receipts/exactly-once, pending-operation recovery и второй volatile Agent implementation.
