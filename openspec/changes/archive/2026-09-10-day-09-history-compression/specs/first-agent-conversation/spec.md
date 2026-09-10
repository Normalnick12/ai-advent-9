## MODIFIED Requirements

### Requirement: Sessions isolate state while sharing fixed agent behavior

В namespace `/api/v1/agent/sessions` Day 06/07 backend SHALL предоставлять одно фиксированное поведение агента с server-side instructions и LLM configuration и независимые sessions этого агента. История каждой session SHALL сохраняться вне backend process в локальном durable storage, который является источником истины; потеря runtime objects SHALL NOT уничтожать подтверждённую history. Sessions SHALL работать в пределах одного backend worker. После restart обращение по существующему ID SHALL восстанавливать ту же session с полной history; отсутствующий ID SHALL давать `session_not_found`, без автоматического создания замены. После успешного reset/delete клиент SHALL оставаться без активного session ID; следующая явная отправка SHALL создавать новый ID с пустой history и прежним поведением агента. Удалённый ID SHALL NOT восстанавливаться. Day 06 и Day 07 SHALL использовать один накопительно развивающийся backend Agent subsystem; отдельный volatile Agent для Day 06 SHALL отсутствовать. Persistent history SHALL относиться только к конкретной session, без переноса фактов в semantic memory пользователя или другие sessions.


Day 08 SHALL использовать отдельный namespace и фиксированную лабораторную конфигурацию; Day 06–08 SHALL сохранять общий full-history алгоритм без второго implementation Agent. Day 09 SHALL использовать тот же Agent subsystem с отдельными namespace/store/config и rolling-summary context policy по `history-compression-experiment`; это SHALL NOT менять full-history semantics старых namespaces. Ни одна session SHALL не продолжаться с конфигурацией другого namespace, включая восстановление после restart.

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

#### Scenario: Day 09 shares lifecycle without sharing context strategy
- **WHEN** одновременно доступны Day 06–09
- **THEN** старые namespaces сохраняют прежние payload/config/calls, Day 09 использует собственную policy и ни один ID не открывает другой namespace

### Requirement: Every turn explicitly sends the entire saved conversation

`POST /api/v1/agent/sessions/{session_id}/messages` SHALL принимать только поле `message`: строку длиной 1–20000 символов с хотя бы одним непробельным символом. В Day 06/07 namespace (и full-history Day 08 по его отдельному контракту) backend SHALL передавать модели все сохранённые user/assistant messages данной session в исходном порядке, текущее сообщение с ролью user и фиксированные instructions при каждом вызове. Допустимый исходный текст SHALL не переписываться. Android SHALL NOT передавать history, instructions, model, LLM settings или API key. Conversations API и `previous_response_id` SHALL NOT использоваться. Для Day 06–08 compression, sliding window, summarization, embeddings и token-based trimming SHALL отсутствовать; переполнение контекста SHALL давать явную ошибку без скрытого удаления истории.

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

Day 09 SHALL иметь отдельный контракт context assembly по `history-compression-experiment`: full raw source сохраняется, но response context использует summary + fixed tail; приведённые full-history scenarios SHALL относиться к Day 06–08.

#### Scenario: Compression is opt-in by namespace
- **WHEN** Day 09 сжимает старую часть своего диалога
- **THEN** очередной turn Day 06–08 по-прежнему отправляет всю собственную history без summarization

### Requirement: Only a completed text turn atomically commits history

Принятый обычный turn Day 06–08 SHALL выполнять не более одного generation вызова OpenAI Responses API без автоматических SDK/application retries или fallback. Day 06/07 SHALL NOT выполнять дополнительные token-count network calls; отдельному Day 08 namespace SHALL разрешаться provider input-token counting до generation по требованиям `token-lab-experiment`. Только завершённый непустой текст без refusal SHALL атомарно добавлять user + assistant в durable history. Успех SHALL подтверждаться только после persistent commit всей пары; runtime history SHALL обновляться после этого commit. Storage failure SHALL оставлять прежний RAM snapshot и SHALL NOT возвращать успешный turn. Incomplete, refusal, timeout, upstream error, некорректный ответ и отмена до commit SHALL оставлять persistent и runtime raw history неизменными и освобождать session. Ошибки SHALL NOT становиться assistant messages в LLM context; частичный текст SHALL NOT представляться успешным ходом. Прерванная запись пары SHALL NOT оставлять половину turn при последующем открытии storage. Успешный persistent commit не является гарантией доставки HTTP-ответа клиенту.

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

Для Day 09 normal turn SHALL разрешаться максимум одна controlled summarizer generation до максимум одной response generation; explicit compare SHALL разрешать максимум одну local summary generation и две response branches без commit. Гарантии atomic pair commit и отсутствия retries SHALL сохраняться. Уже committed Day 09 summary SHALL оставаться durable при последующей ошибке normal response; summary SHALL NOT считаться новой raw парой.

#### Scenario: Extra Day 09 phase does not commit a turn
- **WHEN** Day 09 summary успешно сохранена, но response не завершён
- **THEN** raw count не растёт, current не сохраняется и summary остаётся durable по отдельному контракту

### Requirement: Responses expose outcomes without exporting internal context

Завершившийся обработчик turn namespace Day 06/07 SHALL возвращать HTTP 200 с `session_id`, `request_id`, `status`, `reply`, `history_turn_count`, `incomplete_reason`, `error`. Статус SHALL быть `completed`, `incomplete`, `refused` или `error`. Только completed SHALL иметь непустой reply; прочие статусы SHALL иметь `reply=null` и безопасную русскую ошибку `{code, message}`. Счётчик SHALL учитывать только сохранённые пары и не увеличиваться при неуспехе. Session/validation HTTP-ошибки SHALL иметь безопасный код и сообщение. `X-Request-ID` SHALL связывать ответ с диагностикой. Контракт и логи SHALL NOT раскрывать ключ, внутренние instructions, snapshot истории, raw SDK objects или exception dumps. История SHALL оставаться внутренней частью backend.

#### Scenario: Current reply and count are sufficient diagnostics
- **WHEN** успешно завершён третий turn
- **THEN** ответ содержит текущий reply и `history_turn_count=3`
- **AND** не возвращает предыдущие сообщения, instructions или LLM settings

#### Scenario: Incomplete is explicit
- **WHEN** модель возвращает incomplete
- **THEN** клиент получает `status=incomplete`, `reply=null`, безопасную причину и неизменный счётчик

Day 08 SHALL сохранять свой token-lab response contract. Day 09 SHALL иметь отдельный operation response с summary/context/phase diagnostics и compare replies по `history-compression-experiment`; разрешённое раскрытие summary SHALL NOT расширять старые responses или экспортировать полный raw source/instructions/secrets.

#### Scenario: Summary diagnostics do not leak into historical APIs
- **WHEN** после внедрения Day 09 вызываются старые agent и token-lab endpoints
- **THEN** они возвращают прежние contracts без Day 09 summary или compare fields

### Requirement: Earlier days remain independent experiments

Day 07 SHALL сохранять HTTP contracts, prompts, controls, model selections, response schemas, timeout/retry semantics и число LLM-вызовов Day 02–05. Эти лаборатории SHALL NOT получать conversation state или использовать sessions агента. Day 06 Agent semantics SHALL сохраняться: полная явная history, исходный текст, fixed config, изоляция, один LLM-вызов, commit только пригодного completed, busy/delete guards и отсутствие replay. Для исторического Day 07 изменению подлежат только persistence lifecycle guarantees и связанное восстановление identity/metadata. Day 09 SHALL дополнительно сохранять все Day 02–08 contracts, model/config/payload, timeout/retry и число provider calls, включая Day 08 counting, actual usage/pricing и overflow behavior. Историческая volatile реализация Day 06 SHALL оставаться в OpenSpec archive и Git history, без второго backend stack. Ключ SHALL использоваться только backend из `OPENAI_API_KEY`.

#### Scenario: Existing experiments run after agent conversations
- **WHEN** после нескольких ходов Day 06 или Day 07 выполняются Day 02–05
- **THEN** их запросы и результаты соответствуют прежним контрактам без добавленных параметров Agent
- **AND** история чата не попадает ни в один эксперимент

#### Scenario: Persistence does not change context strategy
- **WHEN** тот же full-history диалог Day 06–08 продолжается до или после backend restart
- **THEN** LLM получает всю подтверждённую history и только новое user message с прежними instructions/config
- **AND** дополнительные LLM-вызовы для restore, summaries, memory extraction или reconstruction отсутствуют

#### Scenario: Full-history diagnostics remain unchanged
- **WHEN** после добавления Day 09 запускается Day 08 short, long либо overflow scenario
- **THEN** сохраняются прежние exact count payloads, pricing semantics и non-committing overflow без summarization

### Requirement: Stored history restores exactly or fails explicitly

Backend SHALL загружать существующую session по обращению к её ID, без preload всех sessions при startup. Восстановленная history SHALL сохранять исходные роли, Unicode, пробелы, переводы строк и порядок всех сообщений. Пустая существующая session SHALL отличаться от отсутствующей. History SHALL состоять из полных последовательных пар user/assistant; недопустимые роли, нарушенные пары или порядок SHALL приводить к безопасной ошибке без LLM-вызова, обрезки, подмены пустой history или автоматического создания session. Storage errors SHALL NOT маскироваться как отсутствие session.

#### Scenario: Runtime state is initially empty
- **WHEN** backend открывает storage с несколькими сохранёнными sessions
- **THEN** history ещё не заполняет runtime mapping; первый запрос существующего ID восстанавливает только нужную session
- **AND** другой процесс/экземпляр не нужен для хранения runtime objects предыдущего запуска

#### Scenario: Text survives storage round trip
- **WHEN** session с Unicode, начальными/конечными пробелами и многострочными сообщениями восстанавливается
- **THEN** восстановленная raw history содержит точные исходные тексты и роли в прежнем порядке без сокращения
- **AND** следующий full-history LLM input Day 06–08 передаёт их целиком; Day 09 строит собственный context из точно восстановленного source по `history-compression-experiment`

#### Scenario: Invalid saved history is not silently repaired
- **WHEN** storage содержит неполную пару, недопустимую роль или нарушенную последовательность сообщений
- **THEN** загрузка завершается безопасной ошибкой, без вызова модели и изменения сохранённой history

### Requirement: Runtime activity never becomes durable conversation state

Persistent conversation Day 06–08 SHALL содержать только identity и завершённую history. Day 09 SHALL дополнительно хранить отдельную durable summary с boundary/config version как производное состояние, без изменения raw source. Busy, locks, active requests, pending user, request_id, closed/runtime flags и LLM client state SHALL NOT сохраняться или восстанавливаться. После backend restart существующая session SHALL начинать runtime lifecycle свободной; завершение и replay старых requests SHALL отсутствовать.

#### Scenario: Busy does not survive restart
- **WHEN** старый backend был занят turn без commit, затем полностью завершился, а новый backend открывает ту же session
- **THEN** session не busy, history содержит только прежде подтверждённые пары
- **AND** новая явная отправка разрешена без возобновления старого запроса

Day 09 SHALL NOT сохранять backend cumulative accounting/runtime_id или billing journal. Его backend SHALL возвращать только metrics операции, а Android SHALL держать cumulative observations текущего process в памяти.

#### Scenario: Durable summary is not a runtime request
- **WHEN** Day 09 backend перезапущен после сохранения summary
- **THEN** summary восстанавливается, но busy, pending calls и billing observations не восстанавливаются и не replay-ятся
