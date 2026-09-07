## Context

Мотивация — в [proposal](proposal.md); поведение backend и Android — в [conversation spec](specs/first-agent-conversation/spec.md) и [Android spec](specs/first-agent-android/spec.md).

Сейчас Android использует один app module, Compose/Material 3 и простой MVVM: Activity-scoped ViewModel вызывает constructor-injected Repository, Retrofit отправляет DTO в FastAPI. AppContainer находится в `data/ResponseRepository.kt`; MainActivity создаёт ViewModels, AppRoot и LearningDaysHome обеспечивают каталог, возврат и сохранение состояния.

Backend-сервисы OpenAIResponseService, ReasoningLabService, TemperatureLabService и ModelBenchmarkService непосредственно вызывают `AsyncOpenAI.responses.create`, но каждый связан с контрактом своей лаборатории. Готового нейтрального LlmClient нет. Day 04 history — Android-история экспериментов, а не conversation context. Day 05 явно запрещает conversation state и фиксирует параметры и отсутствие retries. Это исключает массовое переустройство старых сервисов ради Day 06.

## Goals / Non-Goals

**Goals:** отделить поведение агента от состояния session и SDK, сделать обновление истории атомарным, сохранить HTTP и UI простыми и проверять агентную логику с fake LlmClient без сети.

**Non-Goals:** полный перечень находится в proposal. На уровне design дополнительно исключены переписывание старых сервисов, новый Android domain/use-case слой, общий workflow engine, API экспорта history, список/переключение сохранённых диалогов, TTL/фоновые уборщики и глобальный рефакторинг HTTP error handling. Один UI показывает один текущий диалог; backend поддерживает несколько независимых sessions.

## Decisions

### 1. Один backend, отдельный Agent subsystem

Добавить модули внутри `backend/app` и отдельный APIRouter. FastAPI route выполняет validation, получает зависимости, выбирает session по ID, вызывает Agent и отображает результат/ошибки в HTTP DTO. Route не собирает prompt, не обновляет history и не обращается к SDK.

```text
ChatScreen --> ChatViewModel --> ChatRepository --> ChatApi
                                                     |
                                             FastAPI agent router
                                               |           |
                                      AgentSessionManager  SimpleAgent
                                               |           |
                                      sessionId -> Session |
                                               +-----------+
                                                           |
                                                       LlmClient
                                                           |
                                              OpenAIResponsesLlmClient
                                                           |
                                                AsyncOpenAI.responses
```

Новый microservice добавил бы отдельный процесс, порт, deployment и сетевые ошибки без полезной изоляции для этой лаборатории. Переиспользование Day 02 `generate()` привязало бы Agent к recipe/controls DTO; оно отклонено. Маленький новый адаптер использует ту же интеграцию Responses API без таких зависимостей.

### 2. SimpleAgent — поведение, AgentSession — состояние

| Компонент | Содержимое и ответственность |
| --- | --- |
| `SimpleAgent` | Неизменяемый AgentConfig с instructions, ссылка на LlmClient, формирование context, один turn, критерии commit. Собственной общей conversation history нет |
| `AgentSession` | Непрозрачный ID, приватная история конкретного диалога, признак занятости и закрытия; snapshot только для внутреннего использования |
| `AgentSessionManager` | In-memory mapping `session_id -> AgentSession`, create/get/delete и lifecycle; без LLM configuration, prompts или SDK |
| `ConversationMessage`, `LlmResult`, `AgentConfig` | Небольшие Python dataclasses/enum; не FastAPI/Pydantic request models и не SDK types |
| `LlmClient` | Один async contract `complete(messages, config) -> LlmResult`, достаточный для реального адаптера и fake в тестах |

Один SimpleAgent можно разделять между sessions: конфигурация неизменяема, а весь mutable conversation state передаётся явно через конкретную AgentSession. Новый диалог меняет session, не AgentConfig и не тип агента. В `run_turn(session, message)` Agent владеет решением, какой context отправить и когда сохранить результат. Manager не превращается во второй Agent/оркестратор.

Сообщения хранить как неизменяемые значения с ролью user/assistant и текстом, историю — как приватную последовательность с внутренним snapshot. Не возвращать наружу изменяемый список, не использовать mutable class/default fields. Новый session ID — UUID4, отличный от диагностического request_id.

В lifespan FastAPI создать один manager, один SimpleAgent и один OpenAIResponsesLlmClient; получить их через зависимости из app.state. Сам SDK client создаётся лениво при первом turn, чтобы app import, health, create/delete session и тесты без ключа работали. На shutdown закрыть созданный SDK client. Не менять lifecycle старых лабораторных сервисов.

Альтернатива «новый Agent с новой конфигурацией на каждый диалог» смешивает поведение и session lifecycle. Глобальный Agent с общей history нарушает изоляцию. Реестр, создаваемый внутри каждого request dependency, теряет историю после одного запроса. Все три варианта исключены.

### 3. Один turn — кандидат context, вызов, атомарный commit

Agent сначала резервирует свободную незакрытую session, делает snapshot всей истории и добавляет новое user message в локальный кандидат. До успешного результата история session не меняется. После completed непустого текста без refusal Agent за один синхронный commit заменяет историю на прежнюю историю плюс user/assistant. `history_turn_count` равен числу сохранённых пар. Commit не содержит await. Busy освобождается в finally, в том числе при отмене.

Не использовать ранний append user с последующим rollback: лишнее сообщение легко оставить после ошибки/отмены. Не сохранять incomplete, refusal или error как assistant message. Для Day 06 даже доступный частичный текст не добавляется в reply/transcript; показывается статус и безопасная причина, а пользовательский draft доступен для явного повтора после подтверждённого неуспеха.

Правила допуска и delete используют одну per-session синхронизацию. В одном async worker достаточно атомарного относительно event loop резервирования busy без await между проверкой и установкой. Альтернатива — per-session asyncio.Lock с немедленным отказом занятому запросу; очередь ожидания не нужна. Не держать общий lock manager во время LLM I/O.

Delete свободной session помечает её закрытой и удаляет mapping без await между этими действиями. Попытка запустить turn по уже полученной, но затем закрытой ссылке отклоняется как session_not_found. Если turn первым занял session, DELETE получает 409; если delete был первым, turn получает 404. Это предотвращает оживление удалённого ID. Разные sessions могут одновременно ждать LLM.

### 4. Нейтральный LLM boundary и фиксированный Responses payload

OpenAIResponsesLlmClient преобразует ConversationMessage/AgentConfig в SDK kwargs и нормализует ответ в LlmResult. Он не хранит history, session map или previous response ID. SimpleAgent и AgentSession не импортируют FastAPI, OpenAI или transport DTO. Публичный контракт LlmClient не принимает произвольный SDK kwargs bag.

Фиксированные server-side defaults для Day 06: model `gpt-5.6`, `reasoning.effort=none`, `max_output_tokens=1200`, plain text output, `store=false`; instructions передаются каждый turn. Не передавать tools, temperature, top_p, experiment/cache параметры, conversation или previous_response_id. Автоматическое truncation не включать: вся сохранённая history должна попасть в input. Значение 1200 ограничивает только output и не является trimming истории.

Фиксированная инструкция для реализации:

> Ты — помощник учебного приложения. Отвечай по-русски, ясно и кратко. Учитывай сообщения текущего диалога. Если пользователь спрашивает о личном факте или условном обозначении, которого нет в текущем диалоге, скажи, что не знаешь, и не выдумывай его. Не утверждай, что помнишь другие диалоги.

Это server-side behavior, не поле HTTP-контракта или UI diagnostic. Инструкция не содержит демонстрационного факта или ожидаемого ответа.

Для этой текстовой лаборатории история содержит явные user/assistant messages. Responses API поддерживает такую передачу [conversation state](https://developers.openai.com/api/docs/guides/conversation-state). Если в следующих днях появятся reasoning/tool items, текстового output_text будет недостаточно для их round-trip: расширение внутреннего результата и адаптера относится к соответствующему будущему change. Сейчас reasoning отключён, tools отсутствуют; SDK output objects не протекают в AgentSession.

Адаптер использует официальный AsyncOpenAI, credentials только из OPENAI_API_KEY, connect timeout 5 s, SDK timeout 75 s, `max_retries=0` и общий wall-clock deadline 75 s для единственного вызова. Отмена распространяется корректно; timeout не означает отсутствия обработки/списания у провайдера, но неуспешный локальный turn не коммитит history. Не добавлять fallback модели, repair или скрытые повторы.

Нормализовать completed с непустым текстом, incomplete с безопасным reason, refusal, timeout, upstream/internal error и пустой/непригодный ответ. Отсутствующий текст не заменять выдуманным ответом. Ошибки возвращать безопасными русскими формулировками, без str(exception) или SDK dump. Для Day 06 достаточно history_turn_count; добавление pricing/dashboard/полного usage-контракта не требуется.

### 5. Три HTTP endpoints и небольшой контракт

| Endpoint | Request | Успех |
| --- | --- | --- |
| POST `/api/v1/agent/sessions` | `{}` | 201: `{session_id, history_turn_count: 0}` |
| POST `/api/v1/agent/sessions/{session_id}/messages` | `{message: string}` | 200: `{session_id, request_id, status, reply, history_turn_count, incomplete_reason, error}` |
| DELETE `/api/v1/agent/sessions/{session_id}` | Без body | 204 без body, в том числе при отсутствующем корректном ID |

В JSON используются snake_case поля. UUID path проверяется до обработки. Create/message DTO запрещают extra fields; message — strict string 1–20000 символов, whitespace-only недопустим. Проверка пробельности не переписывает допустимый исходный текст. Ни create, ни turn не принимают history, roles, instructions, model, settings или credentials.

Для completed: reply непустой, error и incomplete_reason null, счётчик после commit. Для incomplete/refused/error: reply null, счётчик неизменен, error содержит стабильный code и безопасное русское message. Incomplete reason ограничен безопасными значениями `max_output_tokens`, `content_filter`, `unknown`; для других статусов null. Коды ошибок LLM: `llm_incomplete`, `llm_refused`, `llm_timeout`, `llm_upstream_error`, `llm_invalid_response`, `internal_error`.

HTTP 404 (`session_not_found`), 409 (`session_busy`) и 422 (`validation_error`) возвращают `{request_id, error: {code, message}}`. Все agent responses получают X-Request-ID; в ответе turn/error значение совпадает с body request_id. Validation не возвращает исходное тело запроса в error. Реализовать отображение ошибок локально для agent router, не менять глобальные handlers/контракты старых endpoints. Pydantic StrictModel/ErrorInfo можно переиспользовать только в HTTP DTO.

При программной ошибке вне обычной нормализации HTTP boundary возвращает безопасный 500 без traceback в body; Android не считает его доказательством отсутствия commit. Логи содержат request ID, session ID, статус и count, но не сообщения, instructions, ключ или полные upstream exceptions.

Альтернативы «один endpoint с optional session ID» и «автоматически создать неизвестный ID» упрощают число операций, но скрывают потерю server-side истории. Явные create/send/delete делают restart/reset наблюдаемыми без дополнительных history/status endpoints.

### 6. Минимальная семантика ошибок без idempotency infrastructure

request_id используется только для диагностики. Нет client_message_id, receipt cache, deduplication, retry queue и exactly-once обещаний. Повторный HTTP message request является новым turn.

Достоверный HTTP 200 со статусом неуспеха сообщает, что пара не сохранена; после такого результата пользователь может явно исправить/повторить текст в той же session. HTTP 422/409 также не выполняет новый turn. Успешный upstream вызов с потерянным HTTP-ответом — другой случай: backend уже мог сохранить пару, а Android этого не знает. После transport failure, непригодного response или неожиданного 5xx на send UI сохраняет transcript/draft для просмотра, ставит recoveryRequired и блокирует дальнейшую отправку до «Новый диалог».

Такой консервативный путь выбран вместо автоматического повтора: он оставляет Day 06 без запрещённой инфраструктуры и не создаёт скрытые дубли в context. Он жертвует продолжением текущего диалога после неопределённой сетевой ошибки. Сервер не может гарантировать отсутствие списания OpenAI при timeout.

Ошибка create не может добавить conversation turn: draft сохраняется, повтор возможен явно; при потерянном create response может остаться пустая orphan session до restart. Ошибка/timeout DELETE не очищает UI и блокирует продолжение до успешного явного повтора DELETE; повтор удаления безопасен по контракту. При 409 нужно дождаться окончания server turn и повторить сброс, без polling infrastructure.

### 7. Android остаётся простым MVVM

Добавить `data/ChatApiModels.kt` и `data/ChatRepository.kt` с ChatApi, ChatRepository и DefaultChatRepository. Repository выполняет create/send/delete и локально отображает HTTP failures в небольшие типизированные результаты/ошибки data layer. Отдельный domain module, use cases, Hilt или Dagger не нужны.

Использовать существующий Retrofit/OkHttp instance AppContainer с URL `http://10.0.2.2:8000/`, `retryOnConnectionFailure(false)`, connect 10 s/write 30 s/read 180 s/call 190 s. Backend deadline 75 s укладывается в него; budgets старых лабораторий не меняются. Все объекты создаются через AppContainer; ChatViewModel получает Repository через constructor/factory в MainActivity.

ChatUiState: nullable sessionId, список завершённых UI messages, draft, optional pending user text, operation (idle/creating/sending/resetting), error, recoveryRequired и historyTurnCount. DTO могут использоваться в существующем стиле data/UI; UI message — простая presentation-модель, не backend history. ViewModel не формирует LLM context.

Первая явная отправка при sessionId=null выполняет create, запоминает ID, затем один send. Экран и конструктор ViewModel не выполняют HTTP. На время операции input/send/reset заблокированы, snapshot текста фиксирован. Pending user показывается отдельно от завершённого transcript. После completed пара фиксируется для отображения, draft очищается, count берётся из backend. При подтверждённом неуспехе pending снимается, draft восстанавливается, прежний transcript/count сохранены. Coroutine CancellationException не поглощать как обычную ошибку.

«Новый диалог» с известным ID сначала ожидает DELETE 204, затем очищает ID/transcript/draft/count/error/recoveryRequired. Новая session создаётся только при следующей отправке. С неизвестным backend ID после restart DELETE всё равно даёт 204. При отсутствии локального ID очистка локальна. Не создавать новую session после неуспешного DELETE.

HTTP 404 на send сохраняет прежние сообщения только для просмотра и показывает «Диалог потерян после перезапуска сервера. Начните новый диалог». Не восстанавливать context из UI transcript. Потеря Android-процесса также не требует восстановления; session ID/transcript не писать в Room/DataStore/SavedStateHandle для межпроцессного восстановления.

Activity-scoped ViewModel сохраняет текущий диалог и запрос при навигации/rotation. AppRoot SaveableStateHolder сохраняет scroll UI; «Назад к дням» не DELETE и не отмена turn. Положение списка привязать к локальному поколению диалога, чтобы успешный reset также сбрасывал scroll; это UI key, не idempotency token.

### 8. Русский экран и демонстрация

ChatScreen использует существующие theme и LearningDayTopBar, LazyColumn с user/agent messages, composer с IME insets и строку «Завершённых ходов: N». Все статические подписи/ошибки русские; никакого редактора model/instructions или скрытого history viewer. Day 06 добавляется пятой карточкой после Day 05. При новой паре обеспечить доступность свежего ответа; сохранять scroll при обычном уходе/возврате, не дублировать системные отступы.

Один live-сценарий для видео после offline tests: сообщить «Мой условный пароль для этой демонстрации — сиреневый маяк 731» (выдуманный несекретный факт), дождаться ответа/count 1, спросить «Какой условный пароль я назвал?» и увидеть ответ/count 2. Нажать «Новый диалог», дождаться очистки/count 0, задать тот же вопрос без повторения факта. Новый LLM input не содержит старого факта; ожидаем честный ответ о неизвестном факте/count 1. Не использовать настоящий пароль или секрет.

Детерминированные тесты доказывают переданный context, а live-видео показывает фактическое поведение модели; точные формулировки ответов не являются test oracle. Отсутствие контекста после reset не доказывается одним удачным или случайно угаданным LLM-ответом — оно проверяется fake client inputs.

### 9. Файлы, переиспользование и проверяемые границы

Предполагаемые новые backend files: `agent.py` (SimpleAgent), `agent_sessions.py` (AgentSession/AgentSessionManager и lifecycle errors), `llm_client.py` (Protocol и нейтральные ConversationMessage/AgentConfig/LlmResult), `openai_responses_llm_client.py` (SDK adapter), `agent_models.py` (HTTP DTO), `agent_api.py` (router). Нейтральные типы не импортируют Agent/Session: agent, sessions и adapter зависят от них в одном направлении, без циклических импортов. Это не требует отдельных packages или дополнительных abstractions.

Из существующих backend files изменяется wiring `main.py`; existing services остаются отдельными. Переиспользуются библиотеки, модели безопасной transport-ошибки, dependency overrides и fake SDK patterns. Приватные laboratory normalizers не становятся импортами нового LLM adapter; общую миграцию сервисов отложить до реальной необходимости.

Android добавляет ChatApiModels/ChatRepository/ChatViewModel/ChatScreen и wiring в ResponseRepository(AppContainer), MainActivity, AppRoot, LearningDaysHome, strings.xml. Новые JVM/Compose tests используют fake Repository и существующий coroutine test setup. RootNavigationUiTest расширяется с четырёх до пяти дней, сохраняя прежние сценарии.

Backend tests: exact context U1/A1/U2; полная многоходовая history; изоляция двух sessions одного SimpleAgent; атомарный commit и неизменность истории при всех неуспехах/отмене; concurrent turn rejection через управляемые events без sleeps; параллельность разных sessions; delete/busy/stale-reference/restart; строгие HTTP bodies и отсутствие утечек diagnostics; ровно один SDK call с фиксированными kwargs. Существующие tests Day 02–05 должны остаться успешными с прежними ожиданиями payload и метрик.

Android tests: create-before-send, reuse ID и точный body без transcript; pending/completed/failure, duplicate taps, lost/uncertain session, успешный/неуспешный delete, count из backend, navigation/rotation и отсутствие auto requests. Для UI использовать fake Repository; сеть, ключ и LLM не нужны.

### 10. Будущие темы имеют место расширения, но не реализацию

Формирование context находится внутри SimpleAgent: сейчас это вся history; будущая политика context management изменит именно этот шаг. AgentSession хранит short-term history, не long-term memory; последняя будет отдельной ответственностью будущего change. Выполнение turn находится в SimpleAgent: будущие planning/tools смогут изменить один шаг вызова на цикл и расширить LlmResult. Сейчас не создавать пустые Planner, MemoryManager, ToolRegistry, BaseAgent, plugins, callbacks или стратегии на будущее.

## Risks / Trade-offs

- [Общая mutable history] → История только внутри отдельной AgentSession; SimpleAgent/LLM adapter разделяют лишь неизменяемые настройки и transport client; изоляция проверяется на одном экземпляре агента.
- [Гонки turn/delete и поздние ответы] → Per-session busy/closed lifecycle, 409 без очереди, атомарный commit и закрытие; UI reset недоступен во время текущей операции.
- [Несколько workers имеют разные dictionaries] → Day 06 запускается одним worker. Зафиксировать это в backend README; текущие команды запуска через scripts/dev.ps1 сохраняются, без параллельных backend copies.
- [Restart теряет sessions] → Ожидаемый 404 и явный новый диалог. SQL/Redis не добавляются.
- [Рост history и orphan sessions] → Учебный сценарий короткий, message ограничен 20000 символами, явный DELETE и restart освобождают состояние. Session TTL, token budgets/trimming и фоновая очистка не реализуются; долгоживущий публичный сервис не обещается.
- [Полная история увеличивает input cost и может превысить context window] → Ошибка без изменения history и новый диалог; никакой скрытой compression или automatic truncation.
- [Потерянный HTTP response после commit] → Без idempotency продолжение возможно только через новый диалог; никаких автоматических повторов. Это сознательное ограничение лаборатории.
- [Session ID ошибочно принимается за авторизацию] → UUID разделяет sessions, но не аутентифицирует пользователей. Day 06 остаётся локальной лабораторией, не добавляет публичный deployment/auth subsystem.
- [SDK coupling и регрессии старых дней] → Нейтральный LlmClient, отдельный adapter/router и неизменные existing experiment contracts, включая специальные timeout/retry настройки Day 05.

## Migration Plan

Изменение добавочное: сначала внутренний Agent subsystem и offline tests, затем adapter/router, затем Android data/ViewModel/UI и навигация. Миграций данных нет. Во время apply создать краткий `day-06-first-agent/README.md` с назначением, зависимостями/ссылками на setup, запуском, OPENAI_API_KEY только на backend, ограничением in-memory sessions и сценарием видео; актуализировать общие README. Подробные контракты остаются здесь и в component docs.

После реализации выполнить backend pytest, Android unit/build через PowerShell 7 scripts/dev.ps1, затем полный UI suite после всех связанных navigation изменений. Живой сценарий — отдельно: управляемая backend session, status, доступность с эмулятора, три явных LLM-запроса из сценария; не повторять платные прогоны ради точной формулировки ответа. Проверить OpenSpec strict validation и git diff/status; commit/push/archive автоматически не выполнять.

Rollback — убрать подключение нового router и Day 06 из UI вместе с его добавочными компонентами; существующие лаборатории не зависят от него. Перезапуск backend удаляет только эфемерное Agent state; восстановления данных не требуется. Блокирующих или отложенных архитектурных вопросов нет.
