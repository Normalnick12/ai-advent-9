# first-agent-conversation Specification

## Purpose

Определяет общее поведение backend-агента Day 06–07: полную явную историю конкретной session, durable context после restart, изоляцию и атомарность хода, lifecycle удаления и небольшой HTTP-контракт без semantic memory пользователя.

## Requirements

### Requirement: Sessions isolate state while sharing fixed agent behavior

В namespace `/api/v1/agent/sessions` Day 06/07 backend SHALL предоставлять одно фиксированное поведение агента с server-side instructions и LLM configuration и независимые sessions этого агента. История каждой session SHALL сохраняться вне backend process в локальном durable storage, который является источником истины; потеря runtime objects SHALL NOT уничтожать подтверждённую history. Sessions SHALL работать в пределах одного backend worker. После restart обращение по существующему ID SHALL восстанавливать ту же session с полной history; отсутствующий ID SHALL давать `session_not_found`, без автоматического создания замены. После успешного reset/delete клиент SHALL оставаться без активного session ID; следующая явная отправка SHALL создавать новый ID с пустой history и прежним поведением агента. Удалённый ID SHALL NOT восстанавливаться. Day 06 и Day 07 SHALL использовать один накопительно развивающийся backend Agent subsystem; отдельный volatile Agent для Day 06 SHALL отсутствовать. Persistent history SHALL относиться только к конкретной session, без переноса фактов в semantic memory пользователя или другие sessions.


Day 08 SHALL использовать отдельный namespace и фиксированную лабораторную конфигурацию; обе конфигурации SHALL сохранять общий full-history алгоритм без второго implementation Agent. Ни одна session SHALL не продолжаться с конфигурацией другого namespace, включая восстановление после restart.

#### Scenario: Two sessions are independent
- **WHEN** в session A успешно сохранён факт, а в session B отправлено первое сообщение
- **THEN** LLM context B не содержит сообщений A
- **AND** обе sessions используют одинаковые instructions/configuration

#### Scenario: Backend restarts
- **WHEN** U1/A1 подтверждены, backend полностью остановлен и новый process получает U2 с прежним session ID
- **THEN** backend восстанавливает тот же ID и передаёт LLM ровно U1, A1, U2 в исходном порядке
- **AND** после успешного U2/A2 счётчик равен 2, без повторного create или replay U1

#### Scenario: Unknown session remains unknown
- **WHEN** после restart приходит message request с корректным, но отсутствующим ID
- **THEN** backend возвращает 404 `session_not_found` без LLM-вызова и создания session

#### Scenario: Restored sessions remain isolated
- **WHEN** после restart продолжаются две ранее сохранённые sessions
- **THEN** каждая использует только собственную полную history с прежними ролями и текстом
- **AND** ни одна session не получает контекст другого дня или диалога

#### Scenario: Day 08 does not change the existing agent configuration
- **WHEN** наряду с Day 06/07 работает Day 08
- **THEN** старый namespace по-прежнему использует `gpt-5.6`, прежние instructions, reasoning none и output budget 1200
- **AND** ID Day 08 не открывает history в старом namespace и наоборот

### Requirement: Session creation does not call the LLM

`POST /api/v1/agent/sessions` SHALL принимать пустой JSON-объект и возвращать HTTP 201 с новым непрозрачным уникальным `session_id` и `history_turn_count=0` только после durable сохранения пустой session. Создание SHALL NOT вызывать LLM или требовать доступности OpenAI/API key. Лишние request fields SHALL отклоняться с HTTP 422. Storage failure SHALL NOT возвращать 201 или изображать созданную только в RAM session как сохранённую.

#### Scenario: Create two empty sessions
- **WHEN** клиент дважды создаёт session с телом `{}`
- **THEN** получает разные IDs и нулевые счётчики без LLM-вызовов
- **AND** обе пустые sessions доступны после backend restart

#### Scenario: Client tries to configure the agent
- **WHEN** create request содержит model, instructions, history или иное лишнее поле
- **THEN** backend возвращает HTTP 422 и не создаёт session

#### Scenario: Creation cannot be persisted
- **WHEN** запись новой session завершается storage failure
- **THEN** клиент получает безопасную ошибку вместо HTTP 201
- **AND** незаписанная session не публикуется как рабочая runtime session

### Requirement: Every turn explicitly sends the entire saved conversation

`POST /api/v1/agent/sessions/{session_id}/messages` SHALL принимать только поле `message`: строку длиной 1–20000 символов с хотя бы одним непробельным символом. Backend SHALL передавать модели все сохранённые user/assistant messages данной session в исходном порядке, текущее сообщение с ролью user и фиксированные instructions при каждом вызове. Допустимый исходный текст SHALL не переписываться. Android SHALL NOT передавать history, instructions, model, LLM settings или API key. Conversations API и `previous_response_id` SHALL NOT использоваться. Compression, sliding window, summarization, embeddings и token-based trimming SHALL отсутствовать; переполнение контекста SHALL давать явную ошибку без скрытого удаления истории.

#### Scenario: Second turn receives the first exchange
- **WHEN** после успешного обмена U1/A1 приходит U2
- **THEN** LLM input содержит ровно U1, A1, U2 с соответствующими ролями и порядком
- **AND** инструкции агента передаются снова, а после успеха счётчик равен 2

#### Scenario: Longer history is not shortened
- **WHEN** session с несколькими успешными ходами принимает следующее сообщение
- **THEN** все сохранённые сообщения входят в LLM input без обрезки или дополнительного вызова summarization

#### Scenario: Invalid input cannot reach the model
- **WHEN** message отсутствует, имеет неверный тип, состоит только из пробелов, длиннее 20000 символов или содержит лишние request fields
- **THEN** backend возвращает HTTP 422 без LLM-вызова и изменения history

### Requirement: Only a completed text turn atomically commits history

Принятый turn SHALL выполнять не более одного generation вызова OpenAI Responses API без автоматических SDK/application retries или fallback. Day 06/07 SHALL NOT выполнять дополнительные token-count network calls; отдельному Day 08 namespace SHALL разрешаться provider input-token counting до generation по требованиям `token-lab-experiment`. Только завершённый непустой текст без refusal SHALL атомарно добавлять user + assistant в durable history. Успех SHALL подтверждаться только после persistent commit всей пары; runtime history SHALL обновляться после этого commit. Storage failure SHALL оставлять прежний RAM snapshot и SHALL NOT возвращать успешный turn. Incomplete, refusal, timeout, upstream error, некорректный ответ и отмена до commit SHALL оставлять persistent и runtime history неизменными и освобождать session. Ошибки SHALL NOT становиться assistant messages в LLM context; частичный текст SHALL NOT представляться успешным ходом. Прерванная запись пары SHALL NOT оставлять половину turn при последующем открытии storage. Успешный persistent commit не является гарантией доставки HTTP-ответа клиенту.

#### Scenario: An exchange commits together
- **WHEN** LLM возвращает завершённый непустой текст
- **THEN** durable history пополняется ровно двумя сообщениями и одним завершённым ходом до сообщения об успехе
- **AND** другая операция не видит промежуточную history только с новым user message

#### Scenario: Failed turn preserves the prior context
- **WHEN** после первого успеха следующий turn получает incomplete, refusal, timeout, upstream error либо пустой completed ответ
- **THEN** history и счётчик 1 остаются неизменными, скрытого retry нет
- **AND** после повторного открытия storage следующая допустимая попытка получает прежний контекст без неуспешного сообщения

#### Scenario: Cancellation before commit releases the session
- **WHEN** обработка отменена до атомарного commit
- **THEN** новая пара не сохраняется, а session перестаёт быть busy
- **AND** повторное открытие storage не обнаруживает отменённое user message

#### Scenario: Storage commit fails after a valid LLM reply
- **WHEN** модель вернула пригодный completed reply, но сохранение пары завершается ошибкой
- **THEN** клиент не получает completed turn, RAM history/count остаются прежними и busy освобождается
- **AND** при подтверждённом rollback повторное открытие storage показывает прежнюю полную history

#### Scenario: A pair write rolls back
- **WHEN** запись завершается ошибкой после добавления user, но до commit пары
- **THEN** повторное открытие storage показывает прежнюю history без обоих новых сообщений

#### Scenario: Token diagnostics remain isolated from older calls
- **WHEN** Day 06/07 выполняет обычный turn после добавления Day 08
- **THEN** preflight network calls отсутствуют, выполняется максимум одна прежняя generation и сохраняется прежний HTTP response contract

### Requirement: Responses expose outcomes without exporting internal context

Завершившийся обработчик turn SHALL возвращать HTTP 200 с `session_id`, `request_id`, `status`, `reply`, `history_turn_count`, `incomplete_reason`, `error`. Статус SHALL быть `completed`, `incomplete`, `refused` или `error`. Только completed SHALL иметь непустой reply; прочие статусы SHALL иметь `reply=null` и безопасную русскую ошибку `{code, message}`. Счётчик SHALL учитывать только сохранённые пары и не увеличиваться при неуспехе. Session/validation HTTP-ошибки SHALL иметь безопасный код и сообщение. `X-Request-ID` SHALL связывать ответ с диагностикой. Контракт и логи SHALL NOT раскрывать ключ, внутренние instructions, snapshot истории, raw SDK objects или exception dumps. История SHALL оставаться внутренней частью backend.

#### Scenario: Current reply and count are sufficient diagnostics
- **WHEN** успешно завершён третий turn
- **THEN** ответ содержит текущий reply и `history_turn_count=3`
- **AND** не возвращает предыдущие сообщения, instructions или LLM settings

#### Scenario: Incomplete is explicit
- **WHEN** модель возвращает incomplete
- **THEN** клиент получает `status=incomplete`, `reply=null`, безопасную причину и неизменный счётчик

### Requirement: Only one turn per session can be active

Конкурентная отправка в занятую session SHALL возвращать HTTP 409 `session_busy` без очереди, второго LLM-вызова или изменения истории. Занятость одной session SHALL NOT блокировать turn другой session.

#### Scenario: A concurrent turn is rejected
- **WHEN** LLM-вызов session A выполняется и приходит второе сообщение в A
- **THEN** второе сообщение получает 409 `session_busy`, а только первый turn может сохранить пару

#### Scenario: Another session can proceed
- **WHEN** A ожидает LLM и поступает сообщение в свободную B
- **THEN** B может начать свой turn до завершения A с независимым контекстом

### Requirement: Deletion removes context and invalidates the session ID

`DELETE /api/v1/agent/sessions/{session_id}` SHALL durable удалять свободную session и её history до HTTP 204. Удаление SHALL работать и для session, ещё не загруженной в runtime mapping после restart. Runtime object SHALL закрываться и удаляться только после успешного persistent delete. Storage failure SHALL NOT очищать runtime history или изображать успешный reset. Удаление отсутствующего корректного ID SHALL также давать 204. Удаление busy session SHALL давать 409 `session_busy` без частичного сброса. Удалённый ID SHALL NOT восстанавливаться отложенным запросом или restart. Reset/delete SHALL завершать текущую backend session без создания замены и без вызова OpenAI. После подтверждённого reset клиент SHALL оставаться без активного session ID; только следующая явная отправка SHALL инициировать создание новой session с новым ID, пустой history и прежним поведением агента.

#### Scenario: Reset removes a saved fact
- **WHEN** A с сохранённым фактом успешно удалена, клиент остаётся без session ID, а следующая явная отправка создаёт B с новым ID и отправляет в ней первое сообщение
- **THEN** LLM context B не содержит сообщений A, а после первого успеха счётчик B равен 1
- **AND** отправка по ID A возвращает 404 `session_not_found`

#### Scenario: Reset races with a turn
- **WHEN** клиент удаляет session с выполняющимся turn
- **THEN** получает 409, а исходный turn продолжает обычный lifecycle
- **AND** успешное удаление после завершения turn не позволяет старому ID принять сообщение

#### Scenario: Deleted history stays deleted after restart
- **WHEN** после DELETE 204 backend запускается заново и получает GET или send по удалённому ID
- **THEN** возвращает 404 `session_not_found` без восстановления history
- **AND** повторный DELETE возвращает 204 без LLM-вызова

#### Scenario: Delete an unloaded session
- **WHEN** backend перезапущен и до первого get/turn клиент удаляет существующую session
- **THEN** session и все её сообщения удаляются durable, несмотря на пустой runtime mapping

#### Scenario: Persistent delete fails
- **WHEN** удаление завершается storage failure до commit
- **THEN** клиент не получает 204, а существующий runtime object и history сохраняются для явного повторного reset

### Requirement: Earlier days remain independent experiments

Day 07 SHALL сохранять HTTP contracts, prompts, controls, model selections, response schemas, timeout/retry semantics и число LLM-вызовов Day 02–05. Эти лаборатории SHALL NOT получать conversation state или использовать sessions агента. Day 06 Agent semantics SHALL сохраняться: полная явная history, исходный текст, fixed config, изоляция, один LLM-вызов, commit только пригодного completed, busy/delete guards и отсутствие replay. Изменению подлежат только persistence lifecycle guarantees и связанное восстановление identity/metadata. Историческая volatile реализация Day 06 SHALL оставаться в OpenSpec archive и Git history, без второго backend stack. Ключ SHALL использоваться только backend из `OPENAI_API_KEY`.

#### Scenario: Existing experiments run after agent conversations
- **WHEN** после нескольких ходов Day 06 или Day 07 выполняются Day 02–05
- **THEN** их запросы и результаты соответствуют прежним контрактам без добавленных параметров Agent
- **AND** история чата не попадает ни в один эксперимент

#### Scenario: Persistence does not change context strategy
- **WHEN** тот же диалог продолжается до или после backend restart
- **THEN** LLM получает всю подтверждённую history и только новое user message с прежними instructions/config
- **AND** дополнительные LLM-вызовы для restore, summaries, memory extraction или reconstruction отсутствуют

### Requirement: Stored history restores exactly or fails explicitly

Backend SHALL загружать существующую session по обращению к её ID, без preload всех sessions при startup. Восстановленная history SHALL сохранять исходные роли, Unicode, пробелы, переводы строк и порядок всех сообщений. Пустая существующая session SHALL отличаться от отсутствующей. History SHALL состоять из полных последовательных пар user/assistant; недопустимые роли, нарушенные пары или порядок SHALL приводить к безопасной ошибке без LLM-вызова, обрезки, подмены пустой history или автоматического создания session. Storage errors SHALL NOT маскироваться как отсутствие session.

#### Scenario: Runtime state is initially empty
- **WHEN** backend открывает storage с несколькими сохранёнными sessions
- **THEN** history ещё не заполняет runtime mapping; первый запрос существующего ID восстанавливает только нужную session
- **AND** другой процесс/экземпляр не нужен для хранения runtime objects предыдущего запуска

#### Scenario: Text survives storage round trip
- **WHEN** session с Unicode, начальными/конечными пробелами и многострочными сообщениями восстанавливается
- **THEN** следующий LLM input содержит точные исходные тексты и роли в прежнем порядке без сокращения

#### Scenario: Invalid saved history is not silently repaired
- **WHEN** storage содержит неполную пару, недопустимую роль или нарушенную последовательность сообщений
- **THEN** загрузка завершается безопасной ошибкой, без вызова модели и изменения сохранённой history

### Requirement: Runtime activity never becomes durable conversation state

Persistent conversation SHALL содержать только identity и завершённую history. Busy, locks, active requests, pending user, request_id, closed/runtime flags и LLM client state SHALL NOT сохраняться или восстанавливаться. После backend restart существующая session SHALL начинать runtime lifecycle свободной; завершение и replay старых requests SHALL отсутствовать.

#### Scenario: Busy does not survive restart
- **WHEN** старый backend был занят turn без commit, затем полностью завершился, а новый backend открывает ту же session
- **THEN** session не busy, history содержит только прежде подтверждённые пары
- **AND** новая явная отправка разрешена без возобновления старого запроса

### Requirement: Session metadata can be read without exporting history

`GET /api/v1/agent/sessions/{session_id}` SHALL возвращать HTTP 200 с ровно `session_id` и `history_turn_count` для существующей свободной session, включая восстановленную после restart. GET SHALL NOT создавать session, менять conversation history, вызывать LLM, требовать API key или возвращать history, instructions, model/settings и другие internal данные. Для busy session GET SHALL возвращать 409 `session_busy`, чтобы клиент не принимал промежуточный count за baseline восстановления. Отсутствующий ID SHALL давать 404 `session_not_found`, некорректный UUID — 422; storage failure — безопасную серверную ошибку. Agent response SHALL сохранять `X-Request-ID` и безопасный error envelope; 404 SHALL NOT утверждать, что любой restart уничтожает session.

#### Scenario: Read metadata after restart
- **WHEN** GET получает ID session с одной подтверждённой парой после backend restart
- **THEN** ответ равен metadata того же ID с `history_turn_count=1`
- **AND** тело не содержит иных полей, LLM не вызывается

#### Scenario: Read empty session without credentials
- **WHEN** GET получает ID существующей пустой session без настроенного API key
- **THEN** возвращает 200 с тем же ID и count 0

#### Scenario: Metadata lookup fails safely
- **WHEN** GET получает отсутствующий или некорректный ID либо занятую session
- **THEN** возвращает соответственно 404, 422 или 409 без LLM-вызова и изменения history
