## MODIFIED Requirements

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
