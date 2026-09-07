## Why

Day 02–05 показывают независимые LLM-вызовы, но не агента, который управляет контекстом разговора. Day 06 должен продемонстрировать переход `stateless LLM call → Agent abstraction with conversation state`: агент использует факт из предыдущего сообщения и перестаёт иметь этот контекст после создания нового диалога.

## What Changes

- Добавить в существующий FastAPI backend модуль First Agent: `SimpleAgent` с фиксированными server-side instructions/configuration и правилами выполнения turn, `AgentSession` с историей одного диалога и `AgentSessionManager` для lifecycle независимых sessions в памяти.
- Отделить внутренний `LlmClient` contract и реализацию `OpenAIResponsesLlmClient` от Agent и HTTP DTO. Передавать полную сохранённую историю явно через Responses API, без Conversations API и `previous_response_id`.
- Добавить создание session, отправку сообщения и удаление session через `/api/v1/agent/sessions`. Router ограничить HTTP contract/validation/error mapping. Успешный turn атомарно сохраняет user + assistant; ошибки и incomplete историю не изменяют; конкурентный turn той же session отклоняется безопасно.
- Добавить русскоязычный Day 06 «Первый агент» в текущий Android-каталог: chat transcript, draft, отправка нескольких сообщений, счётчик завершённых ходов, «Новый диалог» и явная обработка утраченной backend session. Android отправляет только новое сообщение и session ID; не передаёт history, instructions, model, LLM settings или API key.
- Сохранить простой MVVM и существующие Day 02–05 contracts, параметры, число вызовов и поведение навигации. Новый диалог создаёт новую session того же агента; состояние исчезает после backend restart.
- Во время реализации добавить тесты изоляции/context/reset/failure/concurrency, Android chat и регрессий; подготовить краткий Day README и сценарий видео «сообщить факт → вспомнить факт → новый диалог → прежний факт неизвестен».

## Capabilities

### New Capabilities

- `first-agent-conversation`: границы Agent/Session/LLM, in-memory lifecycle, полная история, атомарность turn, изоляция, ошибки и session HTTP contract.
- `first-agent-android`: русскоязычный chat UI, session lifecycle через Repository, отображение ответов и диагностики без управления LLM context на клиенте.

### Modified Capabilities

- `learning-days-navigation`: добавить Day 06 и сохранить независимое состояние уроков, переходы и отсутствие автоматических генераций.
- `learning-days-presentation`: добавить карточку «Первый агент» и русские подписи нового урока с сохранением существующего оформления.

## Impact

- Новые backend-модули Agent subsystem/LLM adapter/HTTP DTO/router; wiring в `backend/app/main.py`. Новые endpoints: `POST /api/v1/agent/sessions`, `POST /api/v1/agent/sessions/{session_id}/messages`, `DELETE /api/v1/agent/sessions/{session_id}`. Старые endpoints не меняются.
- Новые ChatApi/DTO/Repository/ViewModel/Screen в единственном Android `app` module, wiring в AppContainer/MainActivity/AppRoot/LearningDaysHome и строки ресурсов. Новый domain/use-case слой не требуется.
- Переиспользуются FastAPI, Pydantic, официальный OpenAI Python SDK, Retrofit, coroutines и Compose Material 3; дополнительные frameworks не нужны. Backend работает одним worker; sessions не переживают restart.
- Во время apply появится `day-06-first-agent/README.md` и необходимые ссылки в общих README. В текущем propose шаге создаются только OpenSpec planning artifacts, без реализации, commit, push или archive.

## Non-goals

Agents SDK / LangChain; tools и tool orchestration; planning; judge; RAG/MCP; long-term memory; SQL/NoSQL/vector storage; compression, sliding window, summarization, embeddings и token-based trimming; streaming/WebSocket; multi-agent; отдельный backend microservice; web UI; persistence между backend restarts; idempotency/client_message_id infrastructure; заранее созданные Planner/MemoryManager/ToolRegistry/BaseAgent abstractions. Переписывание существующих лабораторий и добавление общего framework для всех дней также не входят в Day 06.
