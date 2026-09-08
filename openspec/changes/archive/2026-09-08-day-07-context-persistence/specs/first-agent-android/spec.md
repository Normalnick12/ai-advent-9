## MODIFIED Requirements

### Requirement: Android sends only the new message and session identity

Android SHALL создавать backend session при первой явной отправке, если текущего ID нет, затем использовать этот ID для нескольких сообщений. В Day 07 после create локальное durable сохранение ID SHALL завершаться до первого message request; ошибка сохранения SHALL блокировать send и показывать ошибку без ложного успеха. Create request SHALL содержать `{}`, message request SHALL содержать только `message`, а session ID SHALL передаваться в URL. UI transcript SHALL служить только отображению; Android SHALL NOT передавать history, instructions, model, LLM settings, API key или обращаться к OpenAI напрямую. Создание экрана и возвращение через каталог SHALL NOT создавать session или запускать turn. В Day 07 разрешено read-only восстановление metadata сохранённого ID без replay сообщений.

#### Scenario: First send creates a session then sends text
- **WHEN** пользователь впервые нажимает «Отправить» с допустимым текстом
- **THEN** Android создаёт session и после успеха отправляет ровно один message request с её ID; Day 07 перед send подтверждает локальную запись ID
- **AND** при ошибке создания или локальной записи ID message request не выполняется, draft сохраняется

#### Scenario: Follow-up uses the same session
- **WHEN** после успешного ответа отправлено второе сообщение
- **THEN** Android использует прежний ID и отправляет только новый текст без transcript

#### Scenario: Local identity write fails
- **WHEN** Day 07 получил новый ID, но его локальное сохранение не подтверждено
- **THEN** UI показывает ошибку сохранения, не выполняет message request и не считает диалог готовым к отправке
- **AND** явный повтор не создаёт ещё одну session при наличии уже известного runtime ID, а сначала повторяет его сохранение

### Requirement: Chat distinguishes pending and committed messages

Android SHALL хранить UI transcript, draft, sending/resetting, ошибки и pending состояние в памяти текущего процесса. Day 07 SHALL отдельно сохранять только текущий session ID; transcript, pending operations и recoveryRequired SHALL NOT становиться persistent conversation history. Во время отправки SHALL отображаться ожидающее сообщение пользователя и индикатор ожидания. Только completed reply SHALL фиксировать завершённую пару user/agent в transcript. При подтверждённом неуспехе SHALL сохраняться предыдущий transcript, draft попытки и понятная ошибка; incomplete/refused/error SHALL NOT отображаться успешным ответом агента. Повтор SHALL выполняться только явно, без client_message_id/idempotency infrastructure. Во время create, сохранения ID, send, reset или активного восстановления ввод, повторная отправка и сброс SHALL быть заблокированы; навигация назад SHALL оставаться доступной. Ошибка восстановления SHALL предоставлять явное действие повтора, не оставляя UI в бесконечном loading.

#### Scenario: Send displays the returned response
- **WHEN** backend возвращает completed reply
- **THEN** ожидающее сообщение становится завершённым, за ним появляется фактический ответ, draft очищен и отправка снова доступна

#### Scenario: Known failure keeps the draft
- **WHEN** backend возвращает явный incomplete/refused/error либо подтверждённое отклонение без выполнения turn
- **THEN** предыдущие завершённые сообщения сохраняются, ожидающее сообщение не становится завершённым ходом, текст доступен для исправления или явного повтора
- **AND** автоматического повторного POST нет

#### Scenario: Duplicate taps do not duplicate requests
- **WHEN** пользователь повторно нажимает отправку во время create/save-ID/send
- **THEN** выполняется только исходная последовательность запросов и сохраняется одна пара при успехе

### Requirement: New dialogue deletes the previous session without replay

«Новый диалог» SHALL удалять существующую backend session перед очисткой identity, transcript, draft, ошибки и счётчика. В Day 07 после DELETE 204 SHALL подтверждаться очистка сохранённого Android ID вне main thread; только после обоих успехов UI SHALL изображать завершённый reset. Новая session SHALL создаваться лениво при следующей отправке и использовать то же поведение агента. Если после завершённого чтения локального storage ID нет, действие SHALL только очищать локальное состояние. HTTP 204 при удалении отсутствующей session SHALL считаться успехом. При неуспешном или неподтверждённом удалении либо очистке локального ID прежний transcript SHALL сохраняться с ошибкой и возможностью явно повторить reset; send SHALL быть заблокирован. Старые сообщения SHALL NOT пересылаться в новую session.

#### Scenario: Start a fresh conversation
- **WHEN** пользователь нажимает «Новый диалог» после обмена и получает подтверждение удаления, а в Day 07 также подтверждение локальной очистки ID
- **THEN** видит пустой transcript и счётчик 0
- **AND** следующая отправка создаёт новый ID без прежнего факта

#### Scenario: Delete fails or the session is busy
- **WHEN** удаление получает ошибку, transport failure либо 409 `session_busy`
- **THEN** UI сохраняет сообщения и показывает ошибку сброса; Day 07 не очищает локальный ID
- **AND** не отправляет сообщения в предполагаемую новую session и позволяет явно повторить «Новый диалог»

#### Scenario: Local identity clear fails after backend delete
- **WHEN** Day 07 получил DELETE 204, но локальная очистка ID не подтверждена
- **THEN** UI не изображает успешный reset и блокирует send до явного повторного reset
- **AND** повтор может безопасно удалить уже отсутствующий backend ID и повторить локальную очистку без создания замены

#### Scenario: Confirmed reset survives cold start
- **WHEN** после полностью подтверждённого reset backend и Android перезапущены
- **THEN** Day 07 открывается без сохранённого ID, старых сообщений и автоматического create
- **AND** прежняя backend session не восстанавливается

### Requirement: Lost or uncertain sessions require explicit recovery

При 404 `session_not_found` Android SHALL сообщать «Диалог недоступен. Начните новый диалог», сохранять имеющийся transcript для просмотра и запрещать продолжение с утраченным ID. Сообщение SHALL NOT приписывать любую потерю session обычному backend restart. При transport failure или непригодном HTTP-ответе после message request, когда commit неизвестен, Android SHALL сообщать о неизвестном результате и требовать «Новый диалог» перед дальнейшей отправкой в текущем процессе. Сообщение SHALL NOT автоматически повторяться или переноситься в новую session. Разрешено восстановление Day 07 identity и metadata; API полной history, transcript recreation и exactly-once guarantees SHALL отсутствовать. Day 07 гарантирует cold-start восстановление подтверждённого состояния между завершёнными операциями; сохранение recoveryRequired, pending/in-flight operations и unknown transport outcome markers через Android process crash SHALL NOT входить в scope. GET count SHALL NOT трактоваться как receipt конкретной неопределённой отправки.

#### Scenario: Backend forgot the session
- **WHEN** отправка или восстановление получает 404 `session_not_found`, поскольку ID отсутствует в backend storage
- **THEN** UI сообщает о недоступном диалоге и предлагает явный сброс
- **AND** не создаёт session и не повторяет сообщение автоматически

#### Scenario: HTTP response is lost after a possible commit
- **WHEN** Android не получает достоверный результат отправки
- **THEN** в текущем процессе показывает «Результат отправки неизвестен. Начните новый диалог» и сохраняет прежний transcript и текст попытки
- **AND** дальнейшая отправка заблокирована до подтверждённого сброса, без автоматического retry

### Requirement: History diagnostics demonstrate backend context

UI SHALL показывать «Завершённых ходов: N» по backend `history_turn_count`, где ход равен сохранённой паре user/assistant. Новая лаборатория без ID и подтверждённо сброшенное состояние SHALL показывать 0. В Day 07 при cold start baseline count SHALL браться из metadata GET до разрешения send; во время восстановления или его ошибки неподтверждённый 0 SHALL NOT изображаться достоверным числом ходов существующей session. Счётчик SHALL NOT вычисляться по локальным bubbles или увеличиваться при неуспехе. UI SHALL NOT показывать внутренние instructions или backend history как diagnostic snapshot.

#### Scenario: Video demonstrates short-term recall and reset
- **WHEN** пользователь сообщает отличительный факт и затем спрашивает его в той же session
- **THEN** второй turn получает предыдущий контекст, UI показывает фактический ответ и счётчик 2 после двух успехов
- **AND** после «Новый диалог» первое сообщение отправляется без прежнего контекста; счётчик начинается с 0 и становится 1 после успеха

#### Scenario: Failure does not increase the count
- **WHEN** после двух успешных ходов следующая попытка получает явную ошибку без commit
- **THEN** UI продолжает показывать 2 завершённых хода

#### Scenario: Restored count is independent of visible bubbles
- **WHEN** Day 07 восстановил metadata с count 1, а старый transcript отсутствует
- **THEN** UI показывает 1, после следующего успешного turn — 2 и только новую пару bubbles
- **AND** проверка count не считает этот успешный ответ ошибкой из-за пустого локального transcript

### Requirement: Navigation preserves chat without background replays

Переходы через каталог и пересоздание Activity без завершения процесса SHALL сохранять transcript, draft, session ID, ошибки, текущую операцию и положение списка каждого чата Day 06/07. Возврат SHALL NOT удалять session, повторять POST, отменять turn или повторно запускать уже завершённое восстановление. Day 02–05 SHALL сохранять независимое состояние. После завершения Android-процесса Day 07 SHALL восстанавливать сохранённую identity и metadata по отдельному требованию cold start; полный transcript и pending runtime state SHALL NOT восстанавливаться. Day 06 не требует локального persistent ID; это не меняет общий durable backend для обоих дней.

#### Scenario: A turn finishes while another day is open
- **WHEN** пользователь покидает Day 06 или Day 07 во время отправки, посещает другой день и возвращается
- **THEN** видит состояние той же попытки и тот же диалог без второго запроса
- **AND** состояние другого дня не подменяется данными чата

## ADDED Requirements

### Requirement: Day 07 restores only the current conversation identity

Лаборатория Day 07 SHALL сохранять только один nullable ID своего текущего диалога в private локальном хранилище. Чтение, подтверждённая запись и очистка SHALL выполняться вне main thread с явной обработкой ошибок. Android SHALL NOT сохранять LLM conversation history или использовать transcript для её восстановления. При первом открытии Day 07 в новом процессе UI SHALL прочитать ID: без ID показать пустую лабораторию без HTTP create; с ID выполнить read-only GET metadata и разрешить send только после успешной проверки совпадающего ID и неотрицательного count. После успеха SHALL отображаться «Диалог восстановлен. Предыдущие сообщения не отображаются»; старые bubbles SHALL отсутствовать. Следующая явная отправка SHALL использовать тот же ID и только новый текст. Восстановление SHALL выполняться один раз для экземпляра состояния; явный retry допустим после ошибки, автоматический replay сообщений — никогда.

#### Scenario: Cold start without an identity
- **WHEN** пользователь открывает Day 07 после cold start и локальный ID отсутствует
- **THEN** видит пустую лабораторию с count 0, без GET/create/send

#### Scenario: Cold start restores metadata before sending
- **WHEN** пользователь открывает Day 07 с сохранённым ID session, имеющей одну подтверждённую пару
- **THEN** Android сначала получает metadata того же ID, показывает восстановление и count 1 без старого transcript
- **AND** до явной отправки отсутствуют create/message requests; следующая отправка содержит только новый message с тем же ID

#### Scenario: Backend is temporarily unavailable during restore
- **WHEN** GET metadata не может получить подтверждённый ответ либо получает 409
- **THEN** локальный ID сохраняется, UI показывает ошибку и явное «Повторить восстановление», send остаётся заблокирован
- **AND** приложение не создаёт новый диалог и не удаляет прежний автоматически

#### Scenario: Local identity read fails
- **WHEN** локальное чтение ID завершается ошибкой
- **THEN** UI показывает ошибку и разрешает явный повтор чтения, не считает storage пустым и не выполняет create/send/reset по предположению об отсутствии ID

#### Scenario: Both processes restart between confirmed turns
- **WHEN** после успешного факта/count 1 backend полностью остановлен, Android force-stopped без очистки app data, затем оба запущены и пользователь открывает Day 07
- **THEN** Android восстанавливает прежний session ID/count 1 и позволяет явно спросить ранее сообщённый факт
- **AND** backend передаёт сохранённый контекст; успешный ответ даёт count 2 без повторной отправки факта
