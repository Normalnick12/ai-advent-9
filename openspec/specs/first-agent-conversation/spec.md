# first-agent-conversation Specification

## Purpose

Определяет поведение минимального backend-агента с краткосрочным состоянием диалога: явную передачу полной истории модели, изоляцию sessions, атомарность хода и HTTP-контракт для Android Day 06.

## Requirements

### Requirement: Sessions isolate state while sharing fixed agent behavior

Backend SHALL предоставлять одно фиксированное поведение агента с server-side instructions и LLM configuration и независимые sessions этого агента. Каждая session SHALL иметь собственную историю только в памяти backend. После успешного reset/delete клиент SHALL оставаться без активного session ID. Новая session SHALL создаваться лениво при следующей явной отправке и использовать то же фиксированное поведение SimpleAgent с новым ID и пустой историей; старый ID и его history SHALL NOT восстанавливаться. Sessions SHALL работать в пределах одного backend worker и SHALL исчезать после restart; долговременное хранение не требуется.

#### Scenario: Two sessions are independent
- **WHEN** в session A успешно сохранён факт, а в session B отправлено первое сообщение
- **THEN** LLM context B не содержит сообщений A
- **AND** обе sessions используют одинаковые instructions/configuration

#### Scenario: Backend restarts
- **WHEN** после restart клиент отправляет сообщение со старым session ID
- **THEN** backend возвращает HTTP 404 `session_not_found` без LLM-вызова
- **AND** не создаёт заменяющую session автоматически

### Requirement: Session creation does not call the LLM

`POST /api/v1/agent/sessions` SHALL принимать пустой JSON-объект и возвращать HTTP 201 с новым непрозрачным уникальным `session_id` и `history_turn_count=0`. Создание SHALL NOT вызывать LLM или требовать доступности OpenAI/API key. Лишние request fields SHALL отклоняться с HTTP 422.

#### Scenario: Create two empty sessions
- **WHEN** клиент дважды создаёт session с телом `{}`
- **THEN** получает разные IDs и нулевые счётчики без LLM-вызовов

#### Scenario: Client tries to configure the agent
- **WHEN** create request содержит model, instructions, history или иное лишнее поле
- **THEN** backend возвращает HTTP 422 и не создаёт session

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

Принятый turn SHALL выполнять не более одного вызова OpenAI Responses API без автоматических SDK/application retries или fallback. Только завершённый непустой текст без refusal SHALL атомарно добавлять user + assistant в историю. Incomplete, refusal, timeout, upstream error, некорректный ответ и отмена до commit SHALL оставлять историю неизменной и освобождать session. Ошибки SHALL NOT становиться assistant messages в LLM context; частичный текст SHALL NOT представляться успешным ходом.

#### Scenario: An exchange commits together
- **WHEN** LLM возвращает завершённый непустой текст
- **THEN** история пополняется ровно двумя сообщениями и одним завершённым ходом
- **AND** другая операция не видит промежуточную историю только с новым user message

#### Scenario: Failed turn preserves the prior context
- **WHEN** после первого успеха следующий turn получает incomplete, refusal, timeout, upstream error либо пустой completed ответ
- **THEN** история и счётчик 1 остаются неизменными, скрытого retry нет
- **AND** следующая допустимая попытка получает прежний контекст без неуспешного сообщения

#### Scenario: Cancellation before commit releases the session
- **WHEN** обработка отменена до атомарного commit
- **THEN** новая пара не сохраняется, а session перестаёт быть busy

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

`DELETE /api/v1/agent/sessions/{session_id}` SHALL удалять свободную session и её историю с HTTP 204. Удаление отсутствующего корректного ID SHALL также давать 204. Удаление busy session SHALL давать 409 `session_busy` без частичного сброса. Удалённый ID SHALL NOT восстанавливаться отложенным запросом. Reset/delete SHALL завершать текущую backend session без создания замены и без вызова OpenAI. После HTTP 204 клиент SHALL оставаться без активного session ID; только следующая явная отправка SHALL инициировать создание новой session с новым ID, пустой history и тем же фиксированным поведением SimpleAgent.

#### Scenario: Reset removes a saved fact
- **WHEN** A с сохранённым фактом успешно удалена, клиент остаётся без session ID, а следующая явная отправка создаёт B с новым ID и отправляет в ней первое сообщение
- **THEN** LLM context B не содержит сообщений A, а после первого успеха счётчик B равен 1
- **AND** отправка по ID A возвращает 404 `session_not_found`

#### Scenario: Reset races with a turn
- **WHEN** клиент удаляет session с выполняющимся turn
- **THEN** получает 409, а исходный turn продолжает обычный lifecycle
- **AND** успешное удаление после завершения turn не позволяет старому ID принять сообщение

### Requirement: Earlier days remain independent experiments

Day 06 SHALL сохранять HTTP contracts, prompts, controls, model selections, response schemas, timeout/retry semantics и число LLM-вызовов Day 02–05. Эти лаборатории SHALL NOT получать conversation state или использовать sessions нового агента. Ключ SHALL использоваться только backend из `OPENAI_API_KEY`.

#### Scenario: Existing experiments run after agent conversations
- **WHEN** после нескольких ходов Day 06 выполняются Day 02–05
- **THEN** их запросы и результаты соответствуют прежним контрактам без добавленных параметров Agent
- **AND** история Day 06 не попадает ни в один эксперимент
