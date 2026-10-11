## Purpose

Добавить к локальному Android Architecture Assistant необязательный приватный HTTP-чат с текущими Kotlin/Markdown источниками, ограниченными ресурсами и проверкой двух клиентов на Windows, сохранив самостоятельную работу CLI.

## ADDED Requirements

### Requirement: Optional local service preserves the existing assistant

Система SHALL предоставлять HTTP-режим как отдельно устанавливаемую и запускаемую возможность существующего ассистента. CLI, Knowledge и локальная Ollama MUST оставаться доступными без установки HTTP-зависимостей, запуска HTTP или сетевой инфраструктуры. Прежние CLI-контракты, исторические результаты и verdicts SHALL сохраняться.

#### Scenario: CLI-only installation
- **WHEN** пользователь установил только прежние зависимости CLI и HTTP-пакеты отсутствуют
- **THEN** прежние CLI-команды запускаются с прежними аргументами, rendering и exit semantics без попытки импортировать HTTP-framework или подключаться к HTTP-сервису

#### Scenario: Disable the HTTP mode
- **WHEN** пользователь останавливает HTTP и отключает созданный для него приватный route
- **THEN** CLI, Knowledge/index и Ollama остаются доступными и не удаляются

### Requirement: Local-only defaults and private network access

HTTP-сервис SHALL по умолчанию слушать только `127.0.0.1`. Соединения сервиса с Ollama MUST использовать только `127.0.0.1`, локальную установленную модель и отключённые cloud features. Основная функциональность MUST NOT требовать VPS, публичного IP/домена, router port forwarding или облачной инфраструктуры. Удалённый доступ SHALL использовать проверяемый HTTPS и аутентификацию.

#### Scenario: Local startup
- **WHEN** владелец запускает штатный HTTP-режим с корректной локальной конфигурацией
- **THEN** доступен только loopback listener и не выполняются автоматические настройки маршрутизатора, firewall, туннеля, Ollama, загрузка модели или inference

#### Scenario: Remote model or endpoint is configured
- **WHEN** URL Ollama не использует разрешённый IPv4 loopback либо metadata указывает удалённую модель или неожиданный digest
- **THEN** сервис отказывает в готовности/выполнении и не делает генерацию, redirect, автоматическую замену или скачивание модели

#### Scenario: Private remote demonstration
- **WHEN** пользователь отдельно подтвердил установку/настройку Tailscale и разрешил удалённую демонстрацию
- **THEN** публикуется только HTTP-приложение через Tailscale Serve внутри разрешённой приватной сети, с HTTPS и Bearer auth, без прямой публикации Ollama или каталогов

#### Scenario: Public access was not authorized
- **WHEN** пользователь запускает локальный сервис или приватный Serve
- **THEN** Funnel не включается; временный публичный HTTPS требует отдельного запроса и подтверждения публикации и выключения

### Requirement: Authenticated access to a server-approved corpus

Сервис SHALL аутентифицировать запросы Bearer-токеном, кроме минимального health. Клиент MUST передавать только разрешённый `file_id`, а сервер SHALL самостоятельно определять Workspace, файл, Knowledge и профиль модели. API MUST NOT предоставлять чтение произвольных путей/каталогов, индексирование, команды, upload, model pull или изменение конфигурации.

#### Scenario: Missing or invalid credentials
- **WHEN** клиент без действительного токена обращается к chat, readiness или status
- **THEN** возвращается 401 без чтения Workspace/Knowledge или вызовов Ollama

#### Scenario: Unknown file
- **WHEN** аутентифицированный клиент передаёт неизвестный или недоступный file_id
- **THEN** возвращается 404 без раскрытия разрешённых путей и без inference

#### Scenario: Path or execution injection
- **WHEN** запрос содержит workspace, path, knowledge, model, URL, system/tool options или другие неразрешённые поля
- **THEN** возвращается 422, эти значения не используются для чтения файлов или выполнения команд

#### Scenario: A configured file becomes unsafe
- **WHEN** разрешённый файл заменён ссылкой/junction/reparse point, выходит за Workspace или нарушает ограничения обычного UTF-8 Kotlin-файла
- **THEN** запрос завершается безопасной ошибкой до inference, без следования запрещённому пути

### Requirement: Bounded client-owned chat history

`POST /v1/chat` SHALL принимать `file_id`, непустой текущий `question` и необязательный `history` из полных пар `user`/`assistant` в хронологическом порядке. Сервис MUST поддерживать первоначальный вопрос и последующее уточнение. История SHALL ограничиваться двумя предыдущими парами и 8192 bytes сериализованного UTF-8 JSON массива с compact separators и неэкранированным Unicode. System/tool/произвольные role messages MUST отвергаться. Постоянные серверные сессии и transcript-хранилище MUST отсутствовать.

#### Scenario: Initial question and follow-up
- **WHEN** клиент сначала отправляет вопрос без history, а затем уточнение с предыдущей парой
- **THEN** сервер выполняет два независимых ограниченных хода, использует переданную историю для контекста уточнения и не требует session ID или сохранённой серверной истории

#### Scenario: Invalid or excessive history
- **WHEN** history содержит больше двух пар, превышает 8192 bytes, имеет неполную пару, пустой текст, invalid Unicode или посторонние поля
- **THEN** возвращается 422 до доступа к данным/Ollama; сервер не обрезает историю скрыто

#### Scenario: Client lifecycle
- **WHEN** пользователь меняет file_id, сбрасывает диалог или закрывает минимальный клиент
- **THEN** клиентская история очищается; клиент не пишет transcript, а при удалении старых пар для соблюдения лимита сообщает об этом явно

### Requirement: Current evidence and mechanically checked answers

Каждый ход SHALL заново читать разрешённый Kotlin и проверять актуальную Knowledge, используя существующий RAG и правила validation. Начальный HTTP-профиль SHALL использовать текстовый retrieval по Knowledge. История MUST считаться недоверенным контекстом, не источником фактов или привилегированных инструкций. Проверка ссылок SHALL опираться только на текущие строки Kotlin и переданные в этом ходе chunks.

#### Scenario: Stale or incompatible Knowledge
- **WHEN** Knowledge изменилась относительно индекса либо индекс отсутствует, повреждён или несовместим
- **THEN** возвращается 503 без generation, автоматического rebuild и fallback на ответ без Knowledge

#### Scenario: Context-dependent follow-up retrieval
- **WHEN** текущий вопрос «А когда это разрешено?» требует предыдущего пользовательского вопроса о навигации
- **THEN** retrieval использует текущий вопрос, последний user-вопрос истории и имя Kotlin-файла, находит текущие Markdown-фрагменты и проверяет новый ответ по ним; assistant history не участвует в поисковом query и не становится evidence

#### Scenario: Combined retrieval query exceeds limits
- **WHEN** текущий или исторический user-вопрос превышает 2000 символов, объединённый query превышает 4096 символов или 64 уникальных literal terms
- **THEN** возвращается 422 без inference, скрытого обрезания и LLM query rewrite

#### Scenario: Fabricated evidence in history
- **WHEN** история содержит выдуманную цитату, неизвестный chunk ID или инструкцию прочитать другой файл
- **THEN** она не расширяет полномочия сервера и не добавляет допустимые источники; ссылки ответа проверяются только по текущему evidence

#### Scenario: Valid structured result
- **WHEN** модель завершила ответ done/stop и прошла проверку schema, IDs, диапазонов строк и точных цитат
- **THEN** возвращается 200 с request_id, structured result, разрешёнными source descriptors, mechanical_validation passed и semantic_status not_evaluated

#### Scenario: Incomplete or invalid result
- **WHEN** ответ оборван по лимиту, не подтверждён done/stop или нарушает структуру/ссылки/цитаты
- **THEN** возвращается 502 без raw/частичного ответа как успеха, repair, retry или замены schema

### Requirement: Explicit health readiness and safe status

Сервис SHALL предоставлять `GET /healthz`, `GET /readyz`, `GET /v1/status` с разными значениями liveness, readiness и текущего допуска. Health MUST быть минимальным и не обращаться к модели/данным. Readiness MUST проверять предпосылки без load/embed/chat inference, с конечным timeout и кешем не дольше 5 секунд. Status SHALL возвращать только безопасные состояния, active/limit, ID профиля и лимиты.

#### Scenario: Healthy HTTP and unavailable Ollama
- **WHEN** HTTP работает, но Ollama недоступна или обязательные данные не готовы
- **THEN** health возвращает 200, авторизованный readiness возвращает 503, status отражает неготовность без путей или содержимого

#### Scenario: Capacity is exhausted but dependencies are ready
- **WHEN** оба chat slots заняты при исправных зависимостях
- **THEN** health/status остаются обслуживаемыми, status показывает active=2 и limit=2, readiness не объявляет semantic/inference PASS

### Requirement: Enforced input context and output limits

Сервис SHALL кодом ограничивать raw HTTP-body 32 KiB, получение тела 10 секундами, question 2000 Unicode code points, Kotlin 16 KiB, полный запрос к модели 24 KiB, ответ модели 256 KiB и контекст/выход модели 8192/2048 токенами. История SHALL учитываться в полном бюджете. Клиент MUST NOT переопределять лимиты. Byte caps MUST NOT описываться как доказательство полного token fit.

#### Scenario: Oversized streamed body
- **WHEN** фактически полученное тело превышает 32 KiB, в том числе без Content-Length или через chunked transfer
- **THEN** возвращается 413 до полного накопления/разбора тела и до обращения к данным/Ollama

#### Scenario: Unsupported or stalled body
- **WHEN** клиент передаёт сжатое/не-JSON тело либо не завершает получение тела за 10 секунд
- **THEN** возвращается соответственно 415 или 504 без inference

#### Scenario: Full context exceeds the budget
- **WHEN** Kotlin, вопрос, история и обязательная обвязка не помещаются в 24 KiB либо ни один найденный chunk не помещается
- **THEN** возвращается 422 context_budget_exceeded без generation; сервер не обрезает исходник/историю и не представляет отказ как отсутствие знаний

#### Scenario: Some complete chunks fit
- **WHEN** помещается только префикс ранжированных целых chunks
- **THEN** запрос включает этот префикс с учётом истории и сообщает selected/omitted counts; все citations проверяются относительно реально переданного набора

### Requirement: Predictable rate and concurrency admission

Сервис SHALL ограничивать chat частотой пополнения 6 запросов/мин и burst 2 на аутентифицированный token, readiness/status отдельным общим bucket 30/мин и burst 5. Не более двух chat SHALL одновременно находиться в обслуживании всего сервиса. Превышение capacity MUST отклоняться немедленно; неограниченная application queue MUST отсутствовать. Последовательный inference через очередь Ollama SHALL быть допустимым.

#### Scenario: Two accepted requests complete separately
- **WHEN** два клиента с доступным rate budget отправляют запросы с перекрывающимися интервалами обработки
- **THEN** оба допускаются, каждый получает собственный request_id и результат, данные не смешиваются, независимо от последовательности inference

#### Scenario: Third request while two are active
- **WHEN** rate budget позволяет запрос, но два chat уже обслуживаются
- **THEN** третий получает 503 capacity_exceeded с Retry-After, без чтения корпуса/inference и без ожидания в очереди приложения

#### Scenario: Token rate exhausted
- **WHEN** для аутентифицированного token исчерпан bucket соответствующей операции
- **THEN** возвращается 429 с Retry-After до обращения к данным/Ollama, другой token использует собственный rate budget

### Requirement: Bounded waiting and honest recovery

Допущенный chat SHALL иметь абсолютный deadline 120 секунд, включая retrieval, metadata, ожидание Ollama и validation. Ошибки соединения/перегрузки SHALL давать безопасный 503, deadline — 504. Сервис MUST NOT автоматически повторять inference или считать прекращение ожидания подтверждением остановки Ollama. Неизвестное завершение отправленного inference SHALL блокировать новый допуск до подтверждённого восстановления.

#### Scenario: Deadline with an outstanding operation
- **WHEN** deadline истёк после отправки inference, но его завершение неизвестно
- **THEN** клиент получает 504, оставшаяся операция продолжает учитываться, новые chat получают 503 recovery_required и не создают заменяющие генерации

#### Scenario: Client disconnect
- **WHEN** клиент закрывает соединение после начала inference
- **THEN** запрос не повторяется и его slot не освобождается преждевременно как доказательство завершения; неизвестное completion переводит сервис в recovery_required

#### Scenario: Upstream overload
- **WHEN** Ollama возвращает перегрузку
- **THEN** клиент получает 503 upstream_overloaded без raw upstream body и автоматического retry

#### Scenario: Recovery evidence
- **WHEN** получено подтверждённое позднее terminal completion либо оператор проверил и восстановил Ollama перед возобновлением
- **THEN** допуск может возобновиться; только наличие резидентной модели, истечение задержки или перезапуск HTTP не считаются подтверждением очистки

### Requirement: Content-free diagnostics and safe errors

Система SHALL журналировать только разрешённые технические метаданные и возвращать фиксированные error codes/messages с request_id. Код, Knowledge, вопросы, history, ответы, цитаты, токены, абсолютные пути и raw validation/upstream data MUST NOT сохраняться в HTTP/application/proxy logs. Ответы chat/status/errors SHALL запрещать HTTP-кеширование. Предыдущие файлы и Knowledge/index MUST NOT изменяться обслуживанием запроса.

#### Scenario: Sensitive input in a rejected request
- **WHEN** вопрос, history или неизвестное поле содержат уникальный контрольный маркер и запрос отклоняется
- **THEN** marker отсутствует в server logs и error response; стандартный validation input/traceback не раскрывается

#### Scenario: Runtime failure contains private text
- **WHEN** upstream или внутреннее исключение содержит путь, token или содержимое документа
- **THEN** клиент и логи получают только безопасную категорию ошибки и разрешённые метрики

### Requirement: Windows acceptance separates service quality and model quality

Обязательная серверная приёмка SHALL выполняться на Windows с синтетическими Kotlin/Markdown. Offline tests, live completion, HTTP concurrency, native queue observations и semantic review SHALL фиксироваться раздельно. Coder 7B MUST оставаться техническим кандидатом, а Day 29 NO SUITABLE PROFILE CONFIRMED — неизменным. Фактический запуск Mac M1 MUST NOT быть условием завершения Day 30.

#### Scenario: Local acceptance
- **WHEN** пройдены offline HTTP/security/CLI-regression tests и отдельно разрешённые Windows live вопрос/уточнение и конкурентная пара
- **THEN** локальная техническая приёмка фиксируется по каждому сценарию; 502-тест не заменяет два успешно завершённых live-ответа, semantic verdict не выводится из валидного JSON

#### Scenario: Remote acceptance remains pending
- **WHEN** установка Tailscale ещё не подтверждена или второе устройство недоступно
- **THEN** локальные работы могут продолжаться, а удалённая демонстрация остаётся pending и не объявляется выполненной по двум процессам одного ПК

#### Scenario: Remote acceptance is performed
- **WHEN** два физических устройства после отдельного разрешения обращаются к приватному сервису, одно из другой сети через интернет
- **THEN** фиксируются действительный маршрут, два принятых запроса и отдельное завершение каждого; VPN-доступ не называется публичным hosting или однозначно одобренным автором челленджа

#### Scenario: No inference parallelism evidence
- **WHEN** HTTP-запросы перекрывались, но параллельная работа runner не наблюдалась
- **THEN** HTTP concurrency может быть PASS, inference parallelism отмечается not measured/not confirmed и не является обязательным критерием

### Requirement: Installation shutdown and documentation remain small

Документация SHALL описывать отдельную установку HTTP, локальный запуск/остановку, секреты вне Git, приватную демонстрацию и отключение только её route. Day README SHALL кратко фиксировать фактические результаты и иметь относительную ссылку из корневого README. Автоматические установка Tailscale, inference, публикация Funnel и запись видео MUST NOT выполняться в рамках Proposal или offline Apply.

#### Scenario: Reviewable delivery
- **WHEN** готовится реализация Day 30
- **THEN** предоставляются короткий README и проверенная корневая ссылка, команды для Windows, отдельные pending/actual результаты сети и семантики, а Mac описывается как будущая проверка без ложного PASS

#### Scenario: Remote exposure is disabled
- **WHEN** пользователь завершает демонстрацию
- **THEN** отключается только созданный для неё route и проверяется его недоступность; чужие настройки, CLI, Knowledge и модели сохраняются
