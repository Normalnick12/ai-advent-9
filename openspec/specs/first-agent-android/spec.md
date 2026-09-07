# first-agent-android Specification

## Purpose

Определяет русскоязычный экран Day 06 для общения с backend-агентом: отображение сообщений, lifecycle session, явные ошибки и демонстрацию краткосрочного контекста без управления LLM history на Android.

## Requirements

### Requirement: Day 06 presents a simple Russian chat

Экран «Первый агент» SHALL показывать сообщения в хронологическом порядке с подписями «Вы» и «Агент», поле «Сообщение», действия «Отправить» и «Новый диалог», ожидание и русские ошибки. Все статические пользовательские подписи SHALL быть русскими; фактический текст ответа SHALL не подменяться шаблонами или переводом. Экран SHALL быть доступен без backend и не показывать settings/model/instructions/API-key controls. Список SHALL прокручиваться, длинные сообщения переноситься; ввод и действия SHALL оставаться доступны при открытой клавиатуре и не перекрываться системными панелями.

#### Scenario: Empty chat is available offline
- **WHEN** пользователь открывает Day 06 при недоступном backend
- **THEN** видит пустой чат и может набрать текст
- **AND** открытие не отправляет сообщения и не вызывает LLM

#### Scenario: Messages remain readable
- **WHEN** длинные сообщения показаны на узком экране с увеличенным шрифтом и открыта клавиатура
- **THEN** текст переносится и доступен прокруткой, а ввод и действия не перекрыты

### Requirement: Android sends only the new message and session identity

Android SHALL создавать backend session при первой явной отправке, если текущего ID нет, затем использовать этот ID для нескольких сообщений. Create request SHALL содержать `{}`, message request SHALL содержать только `message`, а session ID SHALL передаваться в URL. UI transcript SHALL служить только отображению; Android SHALL NOT передавать history, instructions, model, LLM settings, API key или обращаться к OpenAI напрямую. Создание экрана и возвращение через каталог SHALL NOT создавать session или запускать turn.

#### Scenario: First send creates a session then sends text
- **WHEN** пользователь впервые нажимает «Отправить» с допустимым текстом
- **THEN** Android создаёт session и после успеха отправляет ровно один message request с её ID
- **AND** при ошибке создания message request не выполняется, draft сохраняется

#### Scenario: Follow-up uses the same session
- **WHEN** после успешного ответа отправлено второе сообщение
- **THEN** Android использует прежний ID и отправляет только новый текст без transcript

### Requirement: Chat distinguishes pending and committed messages

Android SHALL хранить session ID, UI transcript, draft, sending/resetting и ошибку в памяти текущего процесса. Во время отправки SHALL отображаться ожидающее сообщение пользователя и индикатор ожидания. Только completed reply SHALL фиксировать завершённую пару user/agent в transcript. При подтверждённом неуспехе SHALL сохраняться предыдущий transcript, draft попытки и понятная ошибка; incomplete/refused/error SHALL NOT отображаться успешным ответом агента. Повтор SHALL выполняться только явно, без client_message_id/idempotency infrastructure. Во время создания session, отправки или сброса ввод, повторная отправка и сброс SHALL быть заблокированы; навигация назад SHALL оставаться доступной.

#### Scenario: Send displays the returned response
- **WHEN** backend возвращает completed reply
- **THEN** ожидающее сообщение становится завершённым, за ним появляется фактический ответ, draft очищен и отправка снова доступна

#### Scenario: Known failure keeps the draft
- **WHEN** backend возвращает явный incomplete/refused/error либо подтверждённое отклонение без выполнения turn
- **THEN** предыдущие завершённые сообщения сохраняются, ожидающее сообщение не становится завершённым ходом, текст доступен для исправления или явного повтора
- **AND** автоматического повторного POST нет

#### Scenario: Duplicate taps do not duplicate requests
- **WHEN** пользователь повторно нажимает отправку во время create/send
- **THEN** выполняется только исходная последовательность запросов и сохраняется одна пара при успехе

### Requirement: New dialogue deletes the previous session without replay

«Новый диалог» SHALL удалять существующую backend session перед очисткой session ID, transcript, draft, ошибки и счётчика. Новая session SHALL создаваться лениво при следующей отправке и использовать то же поведение агента. Если ID нет, действие SHALL только очищать локальное состояние. HTTP 204 при удалении отсутствующей session SHALL считаться успехом. При неуспешном или неподтверждённом удалении UI SHALL NOT изображать успешный сброс; прежний transcript SHALL сохраняться с ошибкой и возможностью явно повторить сброс. Старые сообщения SHALL NOT пересылаться в новую session.

#### Scenario: Start a fresh conversation
- **WHEN** пользователь нажимает «Новый диалог» после обмена и получает подтверждение удаления
- **THEN** видит пустой transcript и счётчик 0
- **AND** следующая отправка создаёт новый ID без прежнего факта

#### Scenario: Delete fails or the session is busy
- **WHEN** удаление получает ошибку, transport failure либо 409 `session_busy`
- **THEN** UI сохраняет сообщения и показывает ошибку сброса
- **AND** не отправляет сообщения в предполагаемую новую session и позволяет явно повторить «Новый диалог»

### Requirement: Lost or uncertain sessions require explicit recovery

При 404 `session_not_found` Android SHALL сообщать «Диалог потерян после перезапуска сервера. Начните новый диалог», сохранять transcript для просмотра и запрещать продолжение с утраченным ID. При transport failure или непригодном HTTP-ответе после message request, когда commit неизвестен, Android SHALL сообщать о неизвестном результате и требовать «Новый диалог» перед дальнейшей отправкой. Сообщение SHALL NOT автоматически повторяться или переноситься в новую session. Восстановление истории через дополнительный endpoint, persistence и exactly-once guarantees SHALL отсутствовать.

#### Scenario: Backend forgot the session
- **WHEN** после restart отправка возвращает 404 `session_not_found`
- **THEN** UI сообщает о потерянном диалоге и предлагает явный сброс
- **AND** не создаёт session и не повторяет сообщение автоматически

#### Scenario: HTTP response is lost after a possible commit
- **WHEN** Android не получает достоверный результат отправки
- **THEN** показывает «Результат отправки неизвестен. Начните новый диалог» и сохраняет прежний transcript и текст попытки
- **AND** дальнейшая отправка заблокирована до подтверждённого сброса, без автоматического retry

### Requirement: History diagnostics demonstrate backend context

UI SHALL показывать «Завершённых ходов: N» по backend `history_turn_count`, где ход равен сохранённой паре user/assistant. Начальное и сброшенное состояние SHALL показывать 0. Счётчик SHALL NOT вычисляться по локальным bubbles или увеличиваться при неуспехе. UI SHALL NOT показывать внутренние instructions или backend history как diagnostic snapshot.

#### Scenario: Video demonstrates short-term recall and reset
- **WHEN** пользователь сообщает отличительный факт и затем спрашивает его в той же session
- **THEN** второй turn получает предыдущий контекст, UI показывает фактический ответ и счётчик 2 после двух успехов
- **AND** после «Новый диалог» первое сообщение отправляется без прежнего контекста; счётчик начинается с 0 и становится 1 после успеха

#### Scenario: Failure does not increase the count
- **WHEN** после двух успешных ходов следующая попытка получает явную ошибку без commit
- **THEN** UI продолжает показывать 2 завершённых хода

### Requirement: Navigation preserves chat without background replays

Переходы через каталог и пересоздание Activity без завершения процесса SHALL сохранять transcript, draft, session ID, ошибки, текущую операцию и положение списка. Возврат SHALL NOT удалять session, повторять POST или отменять turn. Day 02–05 SHALL сохранять независимое состояние. После завершения Android-процесса восстановление session/transcript не требуется.

#### Scenario: A turn finishes while another day is open
- **WHEN** пользователь покидает Day 06 во время отправки, посещает другой день и возвращается
- **THEN** видит состояние той же попытки и тот же диалог без второго запроса
- **AND** состояние другого дня не подменяется данными чата
